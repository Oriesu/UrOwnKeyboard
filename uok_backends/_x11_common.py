import json
import subprocess

from uok_backends.session import desktop_text
from uok_backends import keyd, system_sources


def desktop_contains(*needles):
    text = desktop_text()
    return any(needle in text for needle in needles)


def popen_first(app, candidates, error_message=None):
    env = app.menu_env() if hasattr(app, "menu_env") else None
    last_error = ""
    for cmd in candidates:
        try:
            subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
                start_new_session=True,
            )
            return True
        except FileNotFoundError as exc:
            last_error = str(exc)
        except Exception as exc:
            last_error = str(exc)
    if error_message:
        try:
            app.notify("UrOwnKeyboard", error_message)
        except Exception:
            pass
        try:
            app.show_error("UrOwnKeyboard", error_message + (f"\n\nÚltimo error: {last_error}" if last_error else ""))
        except Exception:
            pass
    return False


def current_source(app, desktop_name):
    sources = system_sources.current_sources()
    if not sources:
        return None
    source_type, source_id = sources[0][:2]
    return {
        "index": 0,
        "source_type": source_type,
        "source_id": source_id,
        "name": app.source_label(source_type, source_id),
        "desktop": desktop_name,
    }


def install_x11_source_wrappers(app, is_current_desktop, desktop_name):
    base_get_sources = getattr(app, "get_sources", None)
    base_apply_gnome_source_sync = getattr(app, "aplicar_gnome_source_sync", None)
    base_get_gnome_current_source = getattr(app, "get_gnome_current_source", None)
    base_apply_keyd_off_sync = getattr(app, "aplicar_keyd_off_sync", None)
    base_activate_gnome_source = getattr(app, "activar_gnome_source", None)

    def get_sources():
        if is_current_desktop():
            return system_sources.current_sources()
        if base_get_sources is not None:
            return base_get_sources()
        return []

    def aplicar_gnome_source_sync(index):
        if is_current_desktop():
            # Non-GNOME X11 desktops are applied through setxkbmap/xkbcomp.
            return True
        if base_apply_gnome_source_sync is not None:
            return base_apply_gnome_source_sync(index)
        return True

    def get_gnome_current_source():
        if is_current_desktop():
            return current_source(app, desktop_name)
        if base_get_gnome_current_source is not None:
            return base_get_gnome_current_source()
        return None

    def aplicar_keyd_off_sync():
        if not is_current_desktop():
            if base_apply_keyd_off_sync is not None:
                return base_apply_keyd_off_sync()
            return True
        try:
            result = keyd.off()
            return getattr(result, "ok", True)
        except Exception:
            return True

    def activar_gnome_source(index, source_type, source_id):
        if not is_current_desktop():
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
        try:
            ok, message = app.verify_gnome_source_applied(source_type, source_id)
            if not ok:
                app.show_error("UrOwnKeyboard - verificación", message)
                return
        except Exception:
            pass
        current = {
            "type": "gnome-source",
            "name": label,
            "source_type": source_type,
            "source_id": source_id,
            "desktop": desktop_name,
            "keyd_conf": None,
        }
        try:
            app.CURRENT_PROFILE.write_text(json.dumps(current, indent=2, ensure_ascii=False))
        except Exception:
            pass
        app.notify("Keyboard", label + " activated")

    app.get_sources = get_sources
    app.aplicar_gnome_source_sync = aplicar_gnome_source_sync
    app.get_gnome_current_source = get_gnome_current_source
    app.aplicar_keyd_off_sync = aplicar_keyd_off_sync
    app.activar_gnome_source = activar_gnome_source
