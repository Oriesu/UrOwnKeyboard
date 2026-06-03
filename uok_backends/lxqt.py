import re
import subprocess
from pathlib import Path

from uok_backends.session import desktop_text
from uok_backends._x11_common import install_x11_source_wrappers, popen_first


def _is_lxqt():
    return "lxqt" in desktop_text()


def _panel_conf_path():
    return Path.home() / ".config" / "lxqt" / "panel.conf"


def _rewrite_panel_conf(backup_suffix, rewrite):
    conf = _panel_conf_path()
    if not conf.exists():
        return
    try:
        text = conf.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return
    fixed = rewrite(text)
    if fixed == text:
        return
    try:
        backup = conf.with_suffix(backup_suffix)
        if not backup.exists():
            backup.write_text(text, encoding="utf-8")
        conf.write_text(fixed, encoding="utf-8")
    except Exception:
        pass


def _hide_native_input_indicators(app):
    if not _is_lxqt():
        return
    for cmd in (
        ["gsettings", "set", "org.freedesktop.ibus.panel", "show-icon-on-systray", "false"],
        ["gsettings", "set", "org.freedesktop.ibus.panel", "show-im-name", "false"],
    ):
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=app.menu_env(), check=False)
        except Exception:
            pass

    def rewrite(text):
        def plugins_repl(match):
            line = match.group(1)
            line = re.sub(r",?kbindicator,?|kbindicator,?", lambda m: "," if "," in m.group(0) else "", line)
            line = line.replace(",,", ",").rstrip(",")
            return line
        text = re.sub(r"(^plugins=.*)$", plugins_repl, text, flags=re.M)
        text = re.sub(r"\n?\[kbindicator\]\n.*?(?=\n\[[^\]]+\]|\Z)", "\n", text, flags=re.S)
        return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"

    _rewrite_panel_conf(".conf.uok-backup", rewrite)


def _remove_legacy_tray_keep_statusnotifier():
    if not _is_lxqt():
        return

    def rewrite(text):
        if "[tray]" not in text:
            return text
        fixed = re.sub(r"(?ms)^\[tray\]\n.*?(?=^\[[^\]]+\]\n|\Z)", "", text)
        return re.sub(r"\n{3,}", "\n\n", fixed).strip() + "\n"

    _rewrite_panel_conf(".conf.uok-before-remove-tray", rewrite)


def _open_lxqt_keyboard_settings(app, base_open_keyboard_settings=None, _item=None):
    if not _is_lxqt():
        if base_open_keyboard_settings is not None:
            return base_open_keyboard_settings(_item)
        return
    return popen_first(
        app,
        [
            ["lxqt-config-input"],
            ["lxqt-config", "input"],
            ["lxqt-config"],
        ],
        "No se pudo abrir la configuración de teclado de LXQt.",
    )


def install(app):
    base_open_keyboard_settings = getattr(app, "abrir_ajustes_teclado", None)

    def abrir_ajustes_teclado(_item=None):
        return _open_lxqt_keyboard_settings(app, base_open_keyboard_settings, _item)

    def uok_lxqt_append_sources(_menu):
        _hide_native_input_indicators(app)
        return None

    app.uok_lxqt_cleanup_tray = _remove_legacy_tray_keep_statusnotifier
    app.uok_lxqt_append_sources = uok_lxqt_append_sources
    app.abrir_ajustes_teclado = abrir_ajustes_teclado
    install_x11_source_wrappers(app, _is_lxqt, "LXQt")
    _hide_native_input_indicators(app)
