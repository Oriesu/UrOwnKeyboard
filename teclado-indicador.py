import os
for _var in ("LD_LIBRARY_PATH","LD_PRELOAD","GTK_PATH","GIO_EXTRA_MODULES","GI_TYPELIB_PATH"):
    if "/snap/" in os.environ.get(_var, ""):
        os.environ.pop(_var, None)
import json
import re
import shlex
import subprocess
from pathlib import Path
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")
from gi.repository import Gtk, GLib
from gi.repository import AyatanaAppIndicator3 as AppIndicator3
from uok_backends import system_sources
from uok_backends import x11 as uok_x11_backend
from uok_backends import keyd as uok_keyd_backend
from uok_backends.profile_store import safe_id, unique_layout_id

HOME = Path.home()
CONFIG = HOME / ".config" / "teclado-indicador"
PROFILES = CONFIG / "profiles"
XKB_DIR = CONFIG / "xkb"
KEYD_DIR = CONFIG / "keyd"
USER_XKB = HOME / ".xkb" / "symbols"
CURRENT_PROFILE = CONFIG / "current-profile.json"
SCRIPT_DIR = Path(__file__).resolve().parent
LOCAL_UOK_BIN = SCRIPT_DIR / "uok"
UOK_BIN = LOCAL_UOK_BIN if LOCAL_UOK_BIN.exists() else HOME / ".local" / "bin" / "uok"

for d in [PROFILES, XKB_DIR, KEYD_DIR, USER_XKB]:
    d.mkdir(parents=True, exist_ok=True)

def sh(cmd):
    return subprocess.check_output(["bash", "-lc", cmd], text=True).strip()

def run(cmd):
    subprocess.Popen(["bash", "-lc", cmd])

def notify(title, msg):
    run(f'notify-send {shlex.quote(title)} {shlex.quote(msg)}')

def source_label(source_type, source_id):
    names = {"es":"Spanish","us":"US English","de":"German","fr":"French","it":"Italiano","pt":"Portuguese",}
    if source_type == "xkb":
        return names.get(source_id, source_id)
    if source_type == "ibus":
        return f"IBus: {source_id}"
    return f"{source_type}: {source_id}"

def sync_xwayland_for_xkb_source(source_type, source_id):
    if source_type != "xkb":
        return False
    layout = (source_id or "").split("+", 1)[0].split(":", 1)[0]
    if not layout:
        return False
    ok = False
    for cmd in (["setxkbmap", layout],["bash", "-lc", f"sleep 0.35; setxkbmap {shlex.quote(layout)}"]):
        try:
            if cmd[0] == "bash":
                subprocess.Popen(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=menu_env(),start_new_session=True)
                ok = True
            else:
                result = subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=menu_env(),check=False)
                ok = ok or result.returncode == 0
                try:
                    log = HOME / ".cache" / "urownkeyboard" / "xwayland-sync.log"
                    log.parent.mkdir(parents=True, exist_ok=True)
                    with log.open("a", encoding="utf-8") as fh:
                        fh.write("\n---- sync_xwayland_for_xkb_source ----\n")
                        fh.write(f"source_type={source_type!r}\n")
                        fh.write(f"source_id={source_id!r}\n")
                        fh.write(f"layout={layout!r}\n")
                        fh.write(f"returncode={result.returncode}\n")
                        fh.write(f"stdout={result.stdout}\n")
                        fh.write(f"stderr={result.stderr}\n")
                except Exception:
                    pass
        except Exception as exc:
            try:
                log = HOME / ".cache" / "urownkeyboard" / "xwayland-sync.log"
                log.parent.mkdir(parents=True, exist_ok=True)
                with log.open("a", encoding="utf-8") as fh:
                    fh.write("\n---- sync_xwayland_for_xkb_source exception ----\n")
                    fh.write(f"{exc}\n")
            except Exception:
                pass
    return ok

def get_sources():
    return system_sources.current_sources()

def get_gnome_current_source():
    sources = get_sources()
    if not sources:
        return None
    source_type, source_id = sources[0][:2]
    return {"index":0,"source_type":source_type,"source_id":source_id,"name":source_label(source_type,source_id)}

def guardar_gnome_source_actual(source):
    current = {"type":"gnome-source","name":source["name"],"source_type":source["source_type"],"source_id":source["source_id"],"keyd_conf":None}
    CURRENT_PROFILE.write_text(json.dumps(current, indent=2, ensure_ascii=False))

def aplicar_keyd_off_sync():
    result = uok_keyd_backend.off()
    if not result.ok:
        try:
            show_error("UrOwnKeyboard - keyd","No se pudo desactivar keyd. Se continuará si el backend lo permite.\n\n" + result.combined)
        except Exception:
            pass
    return result.ok

def aplicar_keyd_de_profile_o_apagar(profile):
    result = uok_keyd_backend.apply_profile_or_off(profile)
    if not result.ok:
        try:
            show_error("UrOwnKeyboard - keyd","No se pudo aplicar keyd para este perfil.\n\n" + result.combined)
        except Exception:
            pass
    return result.ok

def aplicar_gnome_source_sync(index):
    try:
        subprocess.run(["gsettings","set","org.gnome.desktop.input-sources","current",str(int(index))],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
            check=False)
        return True
    except Exception:
        return False

def aplicar_xkb_source_sync(source_type, source_id):
    result = uok_x11_backend.apply_source(source_type, source_id)
    if result.ok:
        return True
    show_error("UrOwnKeyboard - XKB",result.message + ("\n\n" + result.details if result.details else ""))
    return False

def activar_gnome_source(index, source_type, source_id):
    label = source_label(source_type, source_id)
    try:
        aplicar_keyd_off_sync()
    except Exception:
        pass
    aplicar_gnome_source_sync(index)
    if source_type == "xkb" and not aplicar_xkb_source_sync(source_type, source_id):
        return
    ok, message = verify_gnome_source_applied(source_type, source_id)
    if not ok:
        show_error("UrOwnKeyboard - verificación", message)
        return
    current = {
        "type":"gnome-source",
        "name":label,
        "source_type":source_type,
        "source_id":source_id,
        "keyd_conf":None,
    }
    CURRENT_PROFILE.write_text(json.dumps(current, indent=2, ensure_ascii=False))
    notify("Keyboard", label + " activated")

def call_optional_hook(name, *args):
    func = globals().get(name)
    if callable(func):
        try:
            return func(*args)
        except Exception:
            return None
    return None

def menu_env():
    env = dict(os.environ)
    env["PATH"] = (str(HOME / ".local" / "bin") + ":/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin")
    return env

def run_menu_cmd(cmd):
    return subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=menu_env())

def abrir_ajustes_teclado(_item=None):
    candidates = [["gnome-control-center", "keyboard"],["gnome-control-center", "region"],["ibus-setup"]]
    for cmd in candidates:
        try:
            subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=menu_env(),start_new_session=True)
            return
        except FileNotFoundError:
            continue
        except Exception:
            continue
    notify("UrOwnKeyboard", "No se pudo abrir la configuración de teclado del sistema.")

def verify_uok_profile_applied(profile_id):
    # Los perfiles UOK se aplican con xkbcomp. En ese caso setxkbmap -query
    # puede seguir mostrando el layout base anterior, por ejemplo "es".
    # La fuente fiable aquí es current-profile.json, escrito por uok activate.
    try:
        profile = json.loads(CURRENT_PROFILE.read_text(encoding="utf-8"))
    except Exception:
        return False, "No se pudo leer current-profile.json después de activar el perfil."
    got = profile.get("id", "")
    profile_type = profile.get("type", "")
    if profile_type != "imported-profile" or got != profile_id:
        return False, ("El perfil activo guardado no coincide. "f"Esperado: {profile_id}. Actual: {got or 'desconocido'}.")
    return True, ""

# UOK profile UI backend delegation
try:
    from uok_backends.profiles import install as uok_install_profiles_backend
    uok_install_profiles_backend(__import__(__name__))
except Exception as exc:
    print(f'UOK profile UI backend disabled: {exc}')

def sincronizar_estado_al_arrancar():
    profile = get_current_profile()
    if profile and profile.get("type") == "imported-profile" and profile.get("id"):
        uok_bin = UOK_BIN if UOK_BIN.exists() else Path.home() / ".local" / "bin" / "uok"
        subprocess.run([str(uok_bin), "activate", profile["id"]],text=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        return
    source = get_gnome_current_source()
    if source:
        guardar_gnome_source_actual(source)
        source_type = source["source_type"]
        source_id = source["source_id"]
        cmds = ["sudo /usr/local/sbin/keyd-aplicar-conf --off"]
        setxkbmap_cmd = uok_x11_backend.source_to_setxkbmap_cmd(source_type, source_id) or ""
        if setxkbmap_cmd:
            cmds.append(setxkbmap_cmd)
        run(" && ".join(cmds))
        return
    aplicar_keyd_de_profile_o_apagar(profile)

# UOK MATE backend delegation
try:
    from uok_backends.mate import install as uok_install_mate_backend
    uok_install_mate_backend(__import__(__name__))
except Exception as exc:
    print(f'UOK MATE backend disabled: {exc}')
# UOK Cinnamon backend delegation
try:
    from uok_backends.cinnamon import install as uok_install_cinnamon_backend
    uok_install_cinnamon_backend(__import__(__name__))
except Exception as exc:
    print(f'UOK Cinnamon backend disabled: {exc}')
# UOK LXQt backend delegation
try:
    from uok_backends.lxqt import install as uok_install_lxqt_backend
    uok_install_lxqt_backend(__import__(__name__))
except Exception as exc:
    print(f'UOK LXQt backend disabled: {exc}')


def _uok_norm_source_id(value):
    return re.sub(r"_+", "_", str(value or "").strip()).lower()

def _uok_profile_system_ids(profiles):
    ids = set()
    for p in profiles or []:
        for key in ("system_xkb_id", "id"):
            value = p.get(key) if isinstance(p, dict) else None
            if value:
                ids.add(str(value))
                ids.add(_uok_norm_source_id(value))
    return ids

def _uok_source_candidates_for_profile(profile):
    raw = []
    for key in ("system_xkb_id", "source_id", "id"):
        value = profile.get(key) if isinstance(profile, dict) else None
        if value:
            raw.append(str(value))
    profile_id = str((profile or {}).get("id") or "")
    if profile_id:
        raw.append(profile_id)
        raw.append(profile_id.replace("__", "_"))
        if not profile_id.startswith("uok_"):
            raw.append("uok_" + profile_id)
        raw.append("uok_" + profile_id.replace("__", "_"))
    out = []
    seen = set()
    for value in raw:
        for candidate in (value, value.replace("__", "_")):
            norm = _uok_norm_source_id(candidate)
            if candidate and norm not in seen:
                seen.add(norm)
                out.append(candidate)
    return out

def _uok_find_source_index_by_id(source_id):
    wanted = _uok_norm_source_id(source_id)
    for i, src in enumerate(get_sources()):
        if len(src) >= 2 and src[0] == "xkb" and _uok_norm_source_id(src[1]) == wanted:
            return i, src[0], src[1]
    return None

def _uok_find_profile_system_source(profile):
    for candidate in _uok_source_candidates_for_profile(profile):
        found = _uok_find_source_index_by_id(candidate)
        if found is not None:
            return found
    return None

def crear_menu():
    call_optional_hook("uok_lxqt_cleanup_tray")
    menu = Gtk.Menu()
    sources = get_sources()
    for hook in ("uok_mate_append_system_sources_to_menu","uok_cinnamon_append_sources","uok_lxqt_append_sources"):
        call_optional_hook(hook, menu)
    profiles = load_profiles()
    uok_system_ids = _uok_profile_system_ids(profiles)
    for index, source in enumerate(sources):
        if len(source) != 2:
            continue
        source_type, source_id = source
        if source_type == "xkb" and (str(source_id) in uok_system_ids or _uok_norm_source_id(source_id) in uok_system_ids):
            continue
        label = source_label(source_type, source_id)
        item = Gtk.MenuItem(label=label)
        item.connect("activate",lambda _,i=index,t=source_type,s=source_id:activar_gnome_source(i,t,s))
        menu.append(item)
    if sources and profiles:
        menu.append(Gtk.SeparatorMenuItem())
    for profile in profiles:
        item = Gtk.MenuItem(label=profile["name"])
        item.connect("activate", lambda _, p=profile: activar_profile(p))
        menu.append(item)
    menu.append(Gtk.SeparatorMenuItem())
    item_complete = Gtk.MenuItem(label="Show full configuration")
    item_complete.connect("activate", mostrar_configuracion_completa)
    menu.append(item_complete)
    item_delete = Gtk.MenuItem(label="Delete configuration…")
    item_delete.connect("activate", eliminar_configuracion)
    menu.append(item_delete)
    item_new_config = Gtk.MenuItem(label="New configuration…")
    submenu_new_config = Gtk.Menu()
    item_editor = Gtk.MenuItem(label="Open visual editor…")
    item_editor.connect("activate", abrir_editor_visual)
    submenu_new_config.append(item_editor)
    item_import = Gtk.MenuItem(label="Import configuration…")
    item_import.connect("activate", importar_configuracion)
    submenu_new_config.append(item_import)
    item_settings = Gtk.MenuItem(label="Add from settings…")
    item_settings.connect("activate", abrir_ajustes_teclado)
    submenu_new_config.append(item_settings)
    item_new_config.set_submenu(submenu_new_config)
    menu.append(item_new_config)
    uok_reload_separator = Gtk.SeparatorMenuItem()
    menu.append(uok_reload_separator)
    item_refresh = Gtk.MenuItem(label="Reload list")
    item_refresh.connect("activate", lambda _: reiniciar_indicador())
    menu.append(item_refresh)
    menu.show_all()
    return menu


# Auto-refresh: when profiles or GNOME input sources change outside the
# indicator process (for example, after saving from the visual editor), refresh
# the menu in-place instead of killing/relaunching the indicator.
def _uok_menu_state_signature():
    try:
        src_sig = tuple((str(a), str(b)) for a, b in get_sources())
    except Exception:
        src_sig = ()
    try:
        prof_sig = tuple(sorted(
            (str(p.get("id", "")), str(p.get("name", "")), str(p.get("system_xkb_id", "")), str(p.get("wayland_ready", "")))
            for p in load_profiles()
        ))
    except Exception:
        prof_sig = ()
    return (src_sig, prof_sig)

_uok_last_menu_signature = None

def _uok_autorefresh_menu_tick():
    global _uok_last_menu_signature
    try:
        sig = _uok_menu_state_signature()
        if _uok_last_menu_signature is None:
            _uok_last_menu_signature = sig
            return True
        if sig != _uok_last_menu_signature:
            _uok_last_menu_signature = sig
            try:
                refrescar_menu_indicador()
            except Exception as exc:
                try:
                    notify("UrOwnKeyboard", f"No se pudo refrescar el menú: {exc}")
                except Exception:
                    pass
    except Exception:
        pass
    return True

def refrescar_menu_indicador():
    global uok_main_menu
    try:
        uok_main_menu = crear_menu()
        indicator.set_menu(uok_main_menu)
        return True
    except Exception as exc:
        try:
            notify("UrOwnKeyboard", f"No se pudo refrescar el menú: {exc}")
        except Exception:
            pass
        return False

def reiniciar_indicador():
    # Reload list debe ser un refresco in-process. No cerramos ni relanzamos
    # el indicador, porque en Wayland/terminal de pruebas eso se percibe como
    # que añadir/borrar una configuración cierra el programa.
    if not refrescar_menu_indicador():
        notify("UrOwnKeyboard", "No se pudo refrescar el menú; abre el indicador de nuevo si la lista no cambia.")
try:
    __uok_mate_base_abrir_ajustes_teclado = abrir_ajustes_teclado
except Exception:

    def __uok_mate_base_abrir_ajustes_teclado(_item=None):
        notify("UrOwnKeyboard", "No se pudo abrir la configuración de teclado del sistema.")
indicator = AppIndicator3.Indicator.new("teclado-custom","input-keyboard",AppIndicator3.IndicatorCategory.APPLICATION_STATUS)
indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
indicator.set_title("Keyboard")
# UOK XFCE backend delegation
try:
    from uok_backends.xfce import install as uok_install_xfce_backend
    uok_install_xfce_backend(__import__(__name__))
except Exception as exc:
    print(f'UOK XFCE backend disabled: {exc}')

def uok_keyd_profile_diagnostic(profile):
    if not profile:
        return "Perfil vacío."
    keyd_conf = profile.get("keyd_conf")
    if not keyd_conf:
        return ""
    path = Path(keyd_conf).expanduser()
    if not path.exists():
        return ("El perfil tiene keyd_conf, pero el archivo no existe:\n"f"{path}")
    try:
        content = path.read_text(encoding="utf-8", errors="ignore").strip()
    except Exception as exc:
        return f"No se pudo leer el keyd.conf asociado:\n{path}\n\n{exc}"
    if not content:
        return f"El keyd.conf asociado existe, pero está vacío:\n{path}"
    return ""

def activar_profile(profile):
    profile_id = profile.get("id")
    if not profile_id:
        show_error("UrOwnKeyboard", "Invalid imported configuration.")
        return

    # GNOME Wayland: a custom UOK profile is implemented as a hidden GNOME
    # system input source. When the hidden source exists, activate it through
    # the exact same path as the working system-source menu item, then record
    # the visible state as the UOK profile. This avoids the duplicate visible
    # item while preserving the behaviour that GNOME accepts.
    if os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland" and "gnome" in os.environ.get("XDG_CURRENT_DESKTOP", "").lower():
        found = _uok_find_profile_system_source(profile)
        if found is not None:
            index, source_type, source_id = found
            activar_gnome_source(index, source_type, source_id)
            current = dict(profile)
            current["type"] = "imported-profile"
            current["desktop"] = "gnome-wayland"
            current["system_xkb_id"] = source_id
            current["wayland_ready"] = True
            try:
                CURRENT_PROFILE.write_text(json.dumps(current, indent=2, ensure_ascii=False))
            except Exception:
                pass
            try:
                aplicar_keyd_de_profile_o_apagar(profile)
            except Exception:
                pass
            notify("Keyboard", f"Active configuration: {profile.get('name', profile_id)}")
            return

    diagnostic = uok_keyd_profile_diagnostic(profile)
    uok_bin = UOK_BIN if UOK_BIN.exists() else Path("uok")
    result = run_menu_cmd([str(uok_bin), "activate", profile_id])
    combined = "\n".join(x.strip()
        for x in [result.stdout, result.stderr]
        if x and x.strip())
    if diagnostic:
        show_error("UrOwnKeyboard - keyd", diagnostic)
    if result.returncode != 0:
        show_error("UrOwnKeyboard",combined or "Could not activate configuration.")
        return
    if "WARNING:" in combined or "keyd" in result.stderr.lower():
        show_error("UrOwnKeyboard - keyd", combined)
    ok, msg = verify_uok_profile_applied(profile_id)
    if not ok:
        show_error("UrOwnKeyboard - verificación", msg)
        return
    notify("Keyboard", result.stdout.strip() or f"{profile.get('name', profile_id)} activated")

def show_error(title, msg):
    import subprocess as _sp
    import os as _os
    title = str(title or "UrOwnKeyboard")
    msg = str(msg or "")
    # Falso positivo: keyd puede seguir activo como daemon.
    # Al volver a una configuración normal lo correcto es que quede neutral,
    # no que systemctl keyd deje de estar activo.
    suppress_parts = ["La distribución XKB se ha cambiado, pero keyd sigue activo","keyd sigue activo","Si notas remapeos antiguos"]
    if any(part in msg for part in suppress_parts):
        return
    try:
        cache = HOME / ".cache" / "urownkeyboard"
        cache.mkdir(parents=True, exist_ok=True)
        with (cache / "indicator.log").open("a", encoding="utf-8") as fh:
            fh.write("\n---- UOK warning ----\n")
            fh.write(title + "\n")
            fh.write(msg + "\n")
    except Exception:
        pass
    # Notificación no bloqueante. Nunca Gtk.MessageDialog modal.
    try:
        _sp.Popen(["notify-send","--app-name=UrOwnKeyboard","--icon=input-keyboard",title,msg],stdin=_sp.DEVNULL,stdout=_sp.DEVNULL,stderr=_sp.DEVNULL,
            env=globals().get("menu_env",lambda: _os.environ.copy())(),start_new_session=True)
    except Exception:
        pass

def verify_gnome_source_applied(source_type, source_id):
    # keyd puede seguir activo como servicio.
    # No se debe avisar por "systemctl is-active keyd".
    if source_type != "xkb":
        return True, ""
    got = uok_x11_backend.current_spec()
    expected = (source_id or "").strip()
    if got != expected:
        return False, f"XKB no cambió al layout esperado. Esperado: {expected}. Actual: {got or 'desconocido'}."
    return True, ""
try:
    from uok_backends.kde import install as uok_install_kde_backend
    uok_install_kde_backend(__import__(__name__))
except Exception as exc:
    print(f'UOK KDE backend disabled: {exc}')
try:
    from uok_backends.overrides import install as uok_install_backend_overrides
    uok_install_backend_overrides(__import__(__name__))
except Exception as exc:
    print(f'UOK backend overrides disabled: {exc}')
call_optional_hook("uok_hide_kde_ibus_native_menu")
call_optional_hook("ocultar_menu_xfce")
sincronizar_estado_al_arrancar()
uok_main_menu = crear_menu()
indicator.set_menu(uok_main_menu)
try:
    _uok_last_menu_signature = _uok_menu_state_signature()
    GLib.timeout_add_seconds(2, _uok_autorefresh_menu_tick)
except Exception:
    pass

def uok_enable_cinnamon_status_icon(menu):
    try:
        if not uok_cinnamon_active():
            return None
    except Exception:
        return None
    try:
        status_icon = Gtk.StatusIcon.new_from_icon_name("input-keyboard")
        status_icon.set_title("UrOwnKeyboard")
        status_icon.set_tooltip_text("UrOwnKeyboard")
        status_icon.set_visible(True)

        def popup(_icon, button, activate_time):
            menu.popup(None,None,Gtk.StatusIcon.position_menu,status_icon,button,activate_time)

        def activate(_icon):
            menu.popup(None,None,Gtk.StatusIcon.position_menu,status_icon,0,Gtk.get_current_event_time())
        status_icon.connect("popup-menu", popup)
        status_icon.connect("activate", activate)
        return status_icon
    except Exception as exc:
        try:
            notify("UrOwnKeyboard", f"No se pudo activar fallback Cinnamon: {exc}")
        except Exception:
            pass
        return None

uok_cinnamon_status_icon = uok_enable_cinnamon_status_icon(uok_main_menu)
# En Cinnamon, si el fallback Gtk.StatusIcon existe, ocultamos el AppIndicator
# para que no aparezcan dos menús UOK. En GNOME/XFCE no cambia nada.
try:
    if uok_cinnamon_status_icon is not None and uok_cinnamon_active():
        indicator.set_status(AppIndicator3.IndicatorStatus.PASSIVE)
except Exception:
    pass
Gtk.main()