import subprocess
from uok_backends.session import desktop_text

def _is_cinnamon():
    return "cinnamon" in desktop_text()

def _open_cinnamon_keyboard_settings(app, base_open_keyboard_settings, _item=None):
    if not _is_cinnamon():
        if base_open_keyboard_settings is not None:
            return base_open_keyboard_settings(_item)
        return
    for cmd in (["cinnamon-settings", "keyboard"],["cinnamon-settings", "region"]):
        try:
            subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=app.menu_env(),start_new_session=True)
            return
        except FileNotFoundError:
            continue
        except Exception:
            continue
    app.notify("UrOwnKeyboard","No se pudo abrir la configuración de teclado de Cinnamon.")

def install(app):
    base_open_keyboard_settings = getattr(app, "abrir_ajustes_teclado", None)
    base_hide_xfce_menu = getattr(app, "ocultar_menu_xfce", None)

    def abrir_ajustes_teclado(_item=None):
        return _open_cinnamon_keyboard_settings(app,base_open_keyboard_settings,_item)

    def ocultar_menu_xfce():
        if _is_cinnamon():
            # No tocar XFCE ni GNOME desde Cinnamon.
            # Tampoco eliminamos applets de Cinnamon automáticamente.
            return
        if base_hide_xfce_menu is not None:
            return base_hide_xfce_menu()

    def uok_cinnamon_append_sources(_menu):
        # Las fuentes del sistema ya se leen desde get_sources()/uok_xkb_sources.py.
        return

    app.uok_cinnamon_active = _is_cinnamon
    app.uok_cinnamon_append_sources = uok_cinnamon_append_sources
    app.abrir_ajustes_teclado = abrir_ajustes_teclado
    app.ocultar_menu_xfce = ocultar_menu_xfce