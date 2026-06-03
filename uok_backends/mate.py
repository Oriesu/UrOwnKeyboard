import subprocess

from uok_backends.session import desktop_text
from uok_backends._x11_common import install_x11_source_wrappers, popen_first


def _is_mate():
    return "mate" in desktop_text()


def _open_mate_keyboard_settings(app, base_open_keyboard_settings=None, _item=None):
    if not _is_mate():
        if base_open_keyboard_settings is not None:
            return base_open_keyboard_settings(_item)
        return
    return popen_first(
        app,
        [
            ["mate-keyboard-properties"],
            ["mate-control-center", "keyboard"],
            ["mate-control-center", "region"],
            ["mate-control-center"],
        ],
        "No se pudo abrir la configuración de teclado de MATE.",
    )


def _hide_mate_native_input_indicators(app):
    if not _is_mate():
        return
    # Hide IBus visual menu if MATE started it. This does not remove layouts.
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

    def abrir_ajustes_teclado(_item=None):
        return _open_mate_keyboard_settings(app, base_open_keyboard_settings, _item)

    def uok_mate_append_system_sources_to_menu(_menu):
        _hide_mate_native_input_indicators(app)
        return None

    app.uok_is_mate = _is_mate
    app.uok_mate_append_system_sources_to_menu = uok_mate_append_system_sources_to_menu
    app.uok_hide_mate_native_input_indicators = lambda: _hide_mate_native_input_indicators(app)
    app.abrir_ajustes_teclado = abrir_ajustes_teclado
    install_x11_source_wrappers(app, _is_mate, "MATE")
    _hide_mate_native_input_indicators(app)
