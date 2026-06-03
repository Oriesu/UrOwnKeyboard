import re
import subprocess
from pathlib import Path

from uok_backends.session import desktop_text
from uok_backends._x11_common import install_x11_source_wrappers, popen_first

_KEYBOARD_PLUGINS = {
    "org.kde.plasma.keyboardlayout",
    "org.kde.plasma.manage-inputmethod",
    "org.kde.plasma.inputmethod",
    "org.kde.plasma.ibus",
}


def _is_kde():
    text = desktop_text()
    return "kde" in text or "plasma" in text


def _split_csv(value):
    return [x.strip() for x in str(value or "").split(",") if x.strip()]


def _join_csv(items):
    out = []
    seen = set()
    for item in items:
        if item and item not in seen:
            out.append(item)
            seen.add(item)
    return ",".join(out)


def _plasma_applets_conf():
    return Path.home() / ".config" / "plasma-org.kde.plasma.desktop-appletsrc"


def _hide_kde_kxkbrc_indicator(app):
    if not _is_kde():
        return
    for tool in ("kwriteconfig6", "kwriteconfig5"):
        for key, value in (("ShowLayoutIndicator", "false"), ("ShowSingle", "false")):
            try:
                subprocess.run(
                    [tool, "--file", "kxkbrc", "--group", "Layout", "--key", key, value],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=app.menu_env(),
                    check=False,
                )
            except Exception:
                pass
    path = Path.home() / ".config" / "kxkbrc"
    try:
        text = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
        lines = text.splitlines()
        out = []
        in_layout = False
        saw_layout = False
        saw_indicator = False
        saw_single = False
        for line in lines:
            group_match = re.match(r"^\[(.+)\]\s*$", line)
            if group_match:
                if in_layout:
                    if not saw_indicator:
                        out.append("ShowLayoutIndicator=false")
                    if not saw_single:
                        out.append("ShowSingle=false")
                in_layout = group_match.group(1) == "Layout"
                if in_layout:
                    saw_layout = True
                    saw_indicator = False
                    saw_single = False
                out.append(line)
                continue
            if in_layout and "=" in line:
                key, _value = line.split("=", 1)
                if key.strip() == "ShowLayoutIndicator":
                    line = "ShowLayoutIndicator=false"
                    saw_indicator = True
                elif key.strip() == "ShowSingle":
                    line = "ShowSingle=false"
                    saw_single = True
            out.append(line)
        if in_layout:
            if not saw_indicator:
                out.append("ShowLayoutIndicator=false")
            if not saw_single:
                out.append("ShowSingle=false")
        if not saw_layout:
            if out and out[-1].strip():
                out.append("")
            out.extend(["[Layout]", "ShowLayoutIndicator=false", "ShowSingle=false"])
        fixed = "\n".join(out) + "\n"
        if fixed != text:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(fixed, encoding="utf-8")
    except Exception:
        pass


def _hide_kde_systemtray_keyboard_items(app):
    if not _is_kde():
        return
    conf = _plasma_applets_conf()
    if not conf.exists():
        return
    try:
        text = conf.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return
    match = re.search(r"SystrayContainmentId=(\d+)", text)
    if not match:
        return
    tray_id = match.group(1)
    target_group = f"Containments][{tray_id}][General"
    lines = text.splitlines()
    out = []
    in_tray_general = False
    seen_tray_general = False
    seen_hidden = False
    seen_shown = False
    seen_extra = False

    def flush_tray_general():
        added = []
        if in_tray_general:
            if not seen_hidden:
                added.append("hiddenItems=" + _join_csv(sorted(_KEYBOARD_PLUGINS)))
            if not seen_shown:
                added.append("shownItems=")
            if not seen_extra:
                added.append("extraItems=")
        return added

    for line in lines:
        group_match = re.match(r"^\[(.+)\]\s*$", line)
        if group_match:
            if in_tray_general:
                out.extend(flush_tray_general())
            group = group_match.group(1)
            in_tray_general = group == target_group
            if in_tray_general:
                seen_tray_general = True
                seen_hidden = False
                seen_shown = False
                seen_extra = False
            out.append(line)
            continue
        if in_tray_general and "=" in line:
            key, value = line.split("=", 1)
            if key == "hiddenItems":
                items = _split_csv(value)
                for item in sorted(_KEYBOARD_PLUGINS):
                    if item not in items:
                        items.append(item)
                line = "hiddenItems=" + _join_csv(items)
                seen_hidden = True
            elif key == "shownItems":
                line = "shownItems=" + _join_csv([x for x in _split_csv(value) if x not in _KEYBOARD_PLUGINS])
                seen_shown = True
            elif key == "extraItems":
                line = "extraItems=" + _join_csv([x for x in _split_csv(value) if x not in _KEYBOARD_PLUGINS])
                seen_extra = True
        out.append(line)
    if in_tray_general:
        out.extend(flush_tray_general())
    if not seen_tray_general:
        out.extend(["", f"[Containments][{tray_id}][General]", "hiddenItems=" + _join_csv(sorted(_KEYBOARD_PLUGINS)), "shownItems=", "extraItems="])
    fixed = "\n".join(out) + "\n"
    if fixed != text:
        try:
            backup = conf.with_suffix(conf.suffix + ".before-uok-hide-kde-systemtray")
            if not backup.exists():
                backup.write_text(text, encoding="utf-8")
            conf.write_text(fixed, encoding="utf-8")
        except Exception:
            pass


def _hide_native_keyboard_menus(app):
    if not _is_kde():
        return
    _hide_kde_kxkbrc_indicator(app)
    _hide_kde_systemtray_keyboard_items(app)


def _open_kde_keyboard_settings(app, base_open_keyboard_settings=None, _item=None):
    if not _is_kde():
        if base_open_keyboard_settings is not None:
            return base_open_keyboard_settings(_item)
        return
    return popen_first(
        app,
        [
            ["kcmshell6", "kcm_keyboard"],
            ["kcmshell5", "kcm_keyboard"],
            ["systemsettings", "kcm_keyboard"],
            ["systemsettings6", "kcm_keyboard"],
            ["systemsettings5", "kcm_keyboard"],
        ],
        "No se pudo abrir la configuración de teclado de KDE.",
    )


def install(app):
    base_open_keyboard_settings = getattr(app, "abrir_ajustes_teclado", None)

    def abrir_ajustes_teclado(_item=None):
        return _open_kde_keyboard_settings(app, base_open_keyboard_settings, _item)

    app.uok_is_kde = _is_kde
    app.uok_kde_desktop_name = desktop_text
    app.uok_hide_kde_native_keyboard_menus = lambda: _hide_native_keyboard_menus(app)
    app.abrir_ajustes_teclado = abrir_ajustes_teclado
    install_x11_source_wrappers(app, _is_kde, "KDE")
    _hide_native_keyboard_menus(app)
