import subprocess

from uok_backends.session import desktop_text
from uok_backends._x11_common import install_x11_source_wrappers, popen_first


def _is_cinnamon():
    return "cinnamon" in desktop_text()


def _open_cinnamon_keyboard_settings(app, base_open_keyboard_settings=None, _item=None):
    if not _is_cinnamon():
        if base_open_keyboard_settings is not None:
            return base_open_keyboard_settings(_item)
        return
    return popen_first(
        app,
        [
            ["cinnamon-settings", "keyboard"],
            ["cinnamon-settings", "region"],
            ["cinnamon-settings"],
        ],
        "No se pudo abrir la configuración de teclado de Cinnamon.",
    )


def _hide_cinnamon_ibus_indicator(app):
    if not _is_cinnamon():
        return
    for cmd in (
        ["gsettings", "set", "org.freedesktop.ibus.panel", "show-icon-on-systray", "false"],
        ["gsettings", "set", "org.freedesktop.ibus.panel", "show-im-name", "false"],
    ):
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=app.menu_env(), check=False)
        except Exception:
            pass


def install(app):
    base_open_keyboard_settings = getattr(app, "abrir_ajustes_teclado", None)
    base_hide_xfce_menu = getattr(app, "ocultar_menu_xfce", None)

    def abrir_ajustes_teclado(_item=None):
        return _open_cinnamon_keyboard_settings(app, base_open_keyboard_settings, _item)

    def ocultar_menu_xfce():
        if _is_cinnamon():
            return
        if base_hide_xfce_menu is not None:
            return base_hide_xfce_menu()

    def uok_cinnamon_append_sources(_menu):
        _hide_cinnamon_ibus_indicator(app)
        return None

    app.uok_cinnamon_active = _is_cinnamon
    app.uok_cinnamon_append_sources = uok_cinnamon_append_sources
    app.abrir_ajustes_teclado = abrir_ajustes_teclado
    app.ocultar_menu_xfce = ocultar_menu_xfce
    install_x11_source_wrappers(app, _is_cinnamon, "Cinnamon")
    _hide_cinnamon_ibus_indicator(app)
