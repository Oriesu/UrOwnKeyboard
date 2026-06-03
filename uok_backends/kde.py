import json
import re
import subprocess
from pathlib import Path
from uok_backends.session import desktop_text
from uok_backends import keyd, system_sources

_KEYBOARD_PLUGINS = {"org.kde.plasma.keyboardlayout","org.kde.plasma.manage-inputmethod"}

def _is_kde():
    text = desktop_text()
    return "kde" in text or "plasma" in text

def _plasma_applets_conf():
    return Path.home() / ".config" / "plasma-org.kde.plasma.desktop-appletsrc"

def _split_csv(value):
    return [x.strip() for x in value.split(",") if x.strip()]

def _join_csv(items):
    out = []
    seen = set()
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return ",".join(out)

def _hide_native_keyboard_menus(app):
    if not _is_kde():
        return
    conf = _plasma_applets_conf()
    if not conf.exists():
        return
    try:
        text = conf.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return
    lines = text.splitlines()
    groups = []
    current = None
    for index, line in enumerate(lines):
        match = re.match(r"^\[(.+)\]\s*$", line)
        if match:
            current = {"name":match.group(1),"start":index,"end":len(lines),"body":[]}
            groups.append(current)
        elif current is not None:
            current["body"].append(line)
    for index in range(len(groups) - 1):
        groups[index]["end"] = groups[index + 1]["start"]
    target_ids = set()
    for group in groups:
        body = "\n".join(group["body"])
        if any(f"plugin={plugin}" in body for plugin in _KEYBOARD_PLUGINS):
            match = re.search(r"Applets\]\[(\d+)", group["name"])
            if match:
                target_ids.add(match.group(1))
    remove_line = [False] * len(lines)
    for group in groups:
        name = group["name"]
        remove_group = False
        for applet_id in target_ids:
            if re.search(rf"Applets\]\[{re.escape(applet_id)}(?:\]|$|\[)", name):
                remove_group = True
        if "\\x5bConfiguration" in name:
            remove_group = True
        if remove_group:
            for index in range(group["start"], group["end"]):
                remove_line[index] = True
    new_lines = []
    in_general = False
    hidden_seen = False
    for index, line in enumerate(lines):
        if remove_line[index]:
            continue
        match = re.match(r"^\[(.+)\]\s*$", line)
        if match:
            if in_general and not hidden_seen:
                new_lines.append("hiddenItems=" + _join_csv(sorted(_KEYBOARD_PLUGINS)))
            group = match.group(1)
            in_general = group.endswith("[General]")
            hidden_seen = False
            new_lines.append(line)
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            if key == "AppletOrder" and target_ids:
                parts = [x.strip() for x in value.split(";") if x.strip()]
                parts = [x for x in parts if x not in target_ids]
                line = key + "=" + ";".join(parts)
            elif key in {"extraItems", "knownItems", "shownItems"}:
                parts = [x for x in _split_csv(value) if x not in _KEYBOARD_PLUGINS]
                line = key + "=" + _join_csv(parts)
            elif key == "hiddenItems":
                parts = _split_csv(value)
                for plugin in sorted(_KEYBOARD_PLUGINS):
                    if plugin not in parts:
                        parts.append(plugin)
                line = key + "=" + _join_csv(parts)
                hidden_seen = True
        new_lines.append(line)
    if in_general and not hidden_seen:
        new_lines.append("hiddenItems=" + _join_csv(sorted(_KEYBOARD_PLUGINS)))
    fixed = "\n".join(new_lines) + "\n"
    if fixed != text:
        try:
            conf.write_text(fixed, encoding="utf-8")
        except Exception:
            pass
    _hide_ibus_systray(app)

def _hide_ibus_systray(app):
    if not _is_kde():
        return
    try:
        subprocess.run(["gsettings", "set", "org.freedesktop.ibus.panel", "show-icon-on-systray", "false"],stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,env=app.menu_env(),check=False)
    except Exception:
        pass

def _hide_ibus_native_menu(app):
    if not _is_kde():
        return
    _hide_ibus_systray(app)
    for cmd in (["ibus", "exit"],["pkill", "-f", "ibus-ui"],["pkill", "-f", "ibus-panel"]):
        try:
            subprocess.run(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=app.menu_env(),check=False)
        except Exception:
            pass

def _kde_current_source(app):
    sources = system_sources.current_sources()
    if not sources:
        return None
    source_type, source_id = sources[0][:2]
    return {"index": 0,"source_type": source_type,"source_id": source_id,"name": app.source_label(source_type, source_id)}

def install(app):
    base_get_sources = getattr(app, "get_sources", None)
    base_apply_gnome_source_sync = getattr(app, "aplicar_gnome_source_sync", None)
    base_get_gnome_current_source = getattr(app, "get_gnome_current_source", None)
    base_apply_keyd_off_sync = getattr(app, "aplicar_keyd_off_sync", None)
    base_activate_gnome_source = getattr(app, "activar_gnome_source", None)

    def get_sources():
        if _is_kde():
            return system_sources.current_sources()
        if base_get_sources is not None:
            return base_get_sources()
        return []

    def aplicar_gnome_source_sync(index):
        if _is_kde():
            # En KDE no usamos org.gnome.desktop.input-sources.
            # El cambio real lo hace aplicar_xkb_source_sync()/setxkbmap.
            return True
        if base_apply_gnome_source_sync is not None:
            return base_apply_gnome_source_sync(index)
        return True

    def get_gnome_current_source():
        if _is_kde():
            return _kde_current_source(app)
        if base_get_gnome_current_source is not None:
            return base_get_gnome_current_source()
        return None

    def aplicar_keyd_off_sync():
        if not _is_kde():
            if base_apply_keyd_off_sync is not None:
                return base_apply_keyd_off_sync()
            return True
        # En KDE, keyd no debe bloquear volver a una fuente XKB normal.
        try:
            keyd.off()
        except Exception:
            pass
        return True

    def activar_gnome_source(index, source_type, source_id):
        if not _is_kde():
            if base_activate_gnome_source is not None:
                return base_activate_gnome_source(index, source_type, source_id)
            return
        label = app.source_label(source_type, source_id)
        try:
            aplicar_keyd_off_sync()
        except Exception:
            pass
        if not app.aplicar_xkb_source_sync(source_type, source_id):
            return
        ok, message = app.verify_gnome_source_applied(source_type, source_id)
        if not ok:
            app.show_error("UrOwnKeyboard - verificación", message)
            return
        current = {"type":"gnome-source","name": label,"source_type":source_type,"source_id":source_id,"desktop":"kde","keyd_conf":None}
        app.CURRENT_PROFILE.write_text(json.dumps(current, indent=2, ensure_ascii=False))
        app.notify("Keyboard", label + " activated")

    app.uok_is_kde = _is_kde
    app.uok_kde_desktop_name = desktop_text
    app.uok_hide_kde_native_keyboard_menus = lambda: _hide_native_keyboard_menus(app)
    app.uok_hide_kde_ibus_native_menu = lambda: _hide_ibus_native_menu(app)
    app.get_sources = get_sources
    app.aplicar_gnome_source_sync = aplicar_gnome_source_sync
    app.get_gnome_current_source = get_gnome_current_source
    app.aplicar_keyd_off_sync = aplicar_keyd_off_sync
    app.activar_gnome_source = activar_gnome_source
    _hide_native_keyboard_menus(app)