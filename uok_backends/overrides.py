from .session import is_gnome_wayland
from . import gnome_wayland
from .profiles import profile_is_custom_xkb
from .activation import block_custom_profile_in_gnome_wayland

IBUS_ENGINE_BY_XKB = {"es": "xkb:es::spa","de": "xkb:de::ger","us": "xkb:us::eng","gb": "xkb:gb::eng","fr": "xkb:fr::fra","it": "xkb:it::ita",
    "pt": "xkb:pt::por"}

class _DummyProcess:
    returncode = 0
    pid = 0
    def poll(self):
        return 0
    def wait(self, timeout=None):
        return 0
    def communicate(self, input=None, timeout=None):
        return "", ""

def _is_setxkbmap_cmd(cmd):
    if isinstance(cmd, (list, tuple)):
        return bool(cmd) and str(cmd[0]) == "setxkbmap"
    text = str(cmd).strip()
    return (text == "setxkbmap" or text.startswith("setxkbmap ") or " setxkbmap " in text or text.endswith("/setxkbmap") or "/setxkbmap " in text)

def _ibus_engine_for_source(source_type, source_id):
    if source_type != "xkb":
        return None
    return IBUS_ENGINE_BY_XKB.get(source_id)

def _force_ibus_engine(app, source_type, source_id):
    engine = _ibus_engine_for_source(source_type, source_id)
    if not engine:
        return
    try:
        app.subprocess.run(["ibus", "engine", engine],text=True,stdout=app.subprocess.PIPE,stderr=app.subprocess.PIPE,check=False)
    except Exception:
        pass

def _fake_completed(app, cmd, returncode=0):
    return app.subprocess.CompletedProcess(cmd,returncode,stdout="",stderr="")

def _show_blocked_profile_warning(app, profile):
    result = block_custom_profile_in_gnome_wayland(app, profile)
    title = "UrOwnKeyboard - GNOME Wayland"
    short = "Configuraciones propias bloqueadas en GNOME Wayland"
    message = result.message
    # Aviso persistente/visible: algunos lanzadores de AppIndicator no
    # muestran zenity de forma fiable en Wayland, así que usamos también
    # notify/notify-send y dejamos traza en stdout.
    try:
        app.notify("UrOwnKeyboard", short)
    except Exception:
        pass
    try:
        app.subprocess.run(["notify-send", title, message],text=True,stdout=app.subprocess.PIPE,stderr=app.subprocess.PIPE,check=False)
    except Exception:
        pass
    try:
        app.show_error(title, message)
    except Exception:
        pass
    try:
        print(f"{title}: {message}")
    except Exception:
        pass

def install(app):
    print("UOK DEBUG: overrides.py install cargado")
    base_run_menu_cmd = app.run_menu_cmd
    base_sh = getattr(app, "sh", None)
    base_subprocess_run = app.subprocess.run
    base_popen = app.subprocess.Popen
    base_activate_gnome_source = app.activar_gnome_source
    base_activate_profile = app.activar_profile

    def run_menu_cmd(cmd, *args, **kwargs):
        if is_gnome_wayland() and _is_setxkbmap_cmd(cmd):
            return _fake_completed(app, cmd)
        return base_run_menu_cmd(cmd, *args, **kwargs)

    def sh(cmd, *args, **kwargs):
        if is_gnome_wayland() and _is_setxkbmap_cmd(cmd):
            return ""
        if base_sh is None:
            return ""
        return base_sh(cmd, *args, **kwargs)

    def subprocess_run(cmd, *args, **kwargs):
        if is_gnome_wayland() and _is_setxkbmap_cmd(cmd):
            return _fake_completed(app, cmd)
        return base_subprocess_run(cmd, *args, **kwargs)

    def subprocess_popen(cmd, *args, **kwargs):
        if is_gnome_wayland() and _is_setxkbmap_cmd(cmd):
            return _DummyProcess()
        return base_popen(cmd, *args, **kwargs)

    def activar_gnome_source(index, source_type, source_id):
        if not is_gnome_wayland():
            return base_activate_gnome_source(index, source_type, source_id)
        label = app.source_label(source_type, source_id)
        if source_type != "xkb":
            app.show_error("UrOwnKeyboard - GNOME Wayland","Esta fuente no es XKB y todavía no está soportada en GNOME Wayland.")
            return
        try:
            app.aplicar_keyd_off_sync()
        except Exception:
            pass
        if not gnome_wayland.set_current_index(index):
            if not app.sync_xwayland_for_xkb_source(source_type, source_id):
                app.show_error("UrOwnKeyboard - Xwayland",f"GNOME cambió a {label}, pero no se pudo sincronizar Xwayland/Code.\n\n"
                    f"Revisa: {app.HOME}/.cache/urownkeyboard/xwayland-sync.log",)
                return
        if not app.sync_xwayland_for_xkb_source(source_type, source_id):
            app.show_error("UrOwnKeyboard - Xwayland",f"GNOME cambió a {label}, pero no se pudo sincronizar Xwayland/Code.\n\n"
                f"Revisa: {app.HOME}/.cache/urownkeyboard/xwayland-sync.log")
        current = {"type":"gnome-source",
            "name":label,"source_type":source_type,"source_id":source_id,"desktop":"gnome-wayland","keyd_conf":None}
        app.CURRENT_PROFILE.write_text(app.json.dumps(current, indent=2, ensure_ascii=False))
        app.notify("Keyboard", label + " activated")

    def activar_profile(profile):
        if is_gnome_wayland() and profile_is_custom_xkb(profile):
            _show_blocked_profile_warning(app, profile)
            return
        return base_activate_profile(profile)
    app.run_menu_cmd = run_menu_cmd
    app.subprocess.run = subprocess_run
    app.subprocess.Popen = subprocess_popen
    if base_sh is not None:
        app.sh = sh
    app.activar_gnome_source = activar_gnome_source
    app.activar_profile = activar_profile
