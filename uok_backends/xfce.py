import re
import subprocess

from uok_backends.session import desktop_text
from uok_backends._x11_common import install_x11_source_wrappers, popen_first


def _is_xfce():
    return "xfce" in desktop_text()


def _xfconf_run(args):
    return subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def _xfconf_get(channel, prop):
    result = _xfconf_run(["xfconf-query", "-c", channel, "-p", prop])
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _xfconf_list(channel):
    result = _xfconf_run(["xfconf-query", "-c", channel, "-l"])
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _xfce_panel_array(prop):
    result = _xfconf_run(["xfconf-query", "-c", "xfce4-panel", "-p", prop])
    if result.returncode != 0:
        return []
    values = []
    for line in result.stdout.splitlines():
        match = re.search(r"(-?\d+)\s*$", line.strip())
        if match:
            values.append(int(match.group(1)))
    return values


def _xfce_set_panel_array(prop, values):
    cmd = ["xfconf-query", "-c", "xfce4-panel", "-p", prop, "--force-array"]
    for value in values:
        cmd.extend(["-t", "int", "-s", str(value)])
    return _xfconf_run(cmd).returncode == 0


def _xfce_keyboard_plugin_ids():
    ids = []
    for prop in _xfconf_list("xfce4-panel"):
        match = re.fullmatch(r"/plugins/plugin-(\d+)", prop)
        if not match:
            continue
        plugin_id = match.group(1)
        name = _xfconf_get("xfce4-panel", prop).strip().lower()
        if name in {"xkb", "keyboard-layout", "keyboard-layouts"} or "xkb" in name or "keyboard" in name:
            ids.append(int(plugin_id))
    return ids


def _hide_xfce_native_keyboard_menu(app):
    if not _is_xfce():
        return
    plugin_ids = set(_xfce_keyboard_plugin_ids())
    if plugin_ids:
        for prop in ("/panels/panel-0/plugin-ids", "/panels/panel-1/plugin-ids"):
            current = _xfce_panel_array(prop)
            if current:
                filtered = [x for x in current if x not in plugin_ids]
                if filtered != current:
                    _xfce_set_panel_array(prop, filtered)
    for cmd in (
        ["gsettings", "set", "org.freedesktop.ibus.panel", "show-icon-on-systray", "false"],
        ["gsettings", "set", "org.freedesktop.ibus.panel", "show-im-name", "false"],
    ):
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=app.menu_env(), check=False)
        except Exception:
            pass


def _open_xfce_keyboard_settings(app, base_open_keyboard_settings=None, _item=None):
    if not _is_xfce():
        if base_open_keyboard_settings is not None:
            return base_open_keyboard_settings(_item)
        return
    return popen_first(
        app,
        [
            ["xfce4-keyboard-settings"],
            ["xfce4-settings-manager", "keyboard"],
            ["xfce4-settings-manager"],
        ],
        "No se pudo abrir la configuración de teclado de XFCE.",
    )


def install(app):
    base_open_keyboard_settings = getattr(app, "abrir_ajustes_teclado", None)
    base_hide_xfce_menu = getattr(app, "ocultar_menu_xfce", None)

    def abrir_ajustes_teclado(_item=None):
        return _open_xfce_keyboard_settings(app, base_open_keyboard_settings, _item)

    def ocultar_menu_xfce():
        if _is_xfce():
            return _hide_xfce_native_keyboard_menu(app)
        if base_hide_xfce_menu is not None:
            return base_hide_xfce_menu()

    app.uok_is_xfce = _is_xfce
    app.ocultar_menu_xfce = ocultar_menu_xfce
    app.abrir_ajustes_teclado = abrir_ajustes_teclado
    install_x11_source_wrappers(app, _is_xfce, "XFCE")
    _hide_xfce_native_keyboard_menu(app)
