import os
for _var in ("LD_LIBRARY_PATH","LD_PRELOAD","GTK_PATH","GIO_EXTRA_MODULES","GI_TYPELIB_PATH"):
    if "/snap/" in os.environ.get(_var, ""):
        os.environ.pop(_var, None)
import json
import re
import shlex
import subprocess
import unicodedata
from pathlib import Path
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")
from gi.repository import Gtk
from gi.repository import AyatanaAppIndicator3 as AppIndicator3
from uok_backends import system_sources
from uok_backends import x11 as uok_x11_backend
from uok_backends import keyd as uok_keyd_backend

HOME = Path.home()
CONFIG = HOME / ".config" / "teclado-indicador"
PROFILES = CONFIG / "profiles"
XKB_DIR = CONFIG / "xkb"
KEYD_DIR = CONFIG / "keyd"
USER_XKB = HOME / ".xkb" / "symbols"
CURRENT_PROFILE = CONFIG / "current-profile.json"
UOK_BIN = HOME / ".local" / "bin" / "uok"

for d in [PROFILES, XKB_DIR, KEYD_DIR, USER_XKB]:
    d.mkdir(parents=True, exist_ok=True)

def sh(cmd):
    return subprocess.check_output(["bash", "-lc", cmd], text=True).strip()

def run(cmd):
    subprocess.Popen(["bash", "-lc", cmd])

def notify(title, msg):
    run(f'notify-send {shlex.quote(title)} {shlex.quote(msg)}')

def safe_id(name):
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode("ascii")
    name = name.lower()
    name = re.sub(r"[^a-z0-9]+", "_", name)
    name = name.strip("_")
    return name or "configuracion"

def unique_layout_id(base_id):
    candidate = base_id
    counter = 2
    while True:
        profile_file = PROFILES / f"{candidate}.json"
        xkb_file = USER_XKB / candidate
        keyd_file = KEYD_DIR / f"{candidate}.conf"
        if not profile_file.exists() and not xkb_file.exists() and not keyd_file.exists():
            return candidate
        candidate = f"{base_id}_{counter}"
        counter += 1

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
            app.show_error("UrOwnKeyboard - GNOME Wayland","No se pudo cambiar la fuente de entrada de GNOME.")
            return
        if not gnome_wayland.verify_index(index):
            app.show_error("UrOwnKeyboard - verificación", f"GNOME no cambió al índice esperado. "
                f"Esperado: {index}. Actual: {gnome_wayland.current_index()}")
        try:
            app.sync_xwayland_for_xkb_source(source_type, source_id)
        except Exception:
            pass
        current = {"type":"gnome-source","name":label,"source_type":source_type,"source_id":source_id,"desktop":"gnome-wayland","keyd_conf":None}
        app.CURRENT_PROFILE.write_text(app.json.dumps(current, indent=2, ensure_ascii=False))
        app.notify("Keyboard", label + " activated")

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

def crear_menu():
    call_optional_hook("uok_lxqt_remove_legacy_tray_keep_statusnotifier")
    menu = Gtk.Menu()
    sources = get_sources()
    for hook in ("uok_mate_append_system_sources_to_menu","uok_cinnamon_append_system_sources_to_menu","uok_lxqt_append_system_sources_to_menu"):
        call_optional_hook(hook, menu)
    for index, source in enumerate(sources):
        if len(source) != 2:
            continue
        source_type, source_id = source
        label = source_label(source_type, source_id)
        item = Gtk.MenuItem(label=label)
        item.connect("activate",lambda _,i=index,t=source_type,s=source_id:activar_gnome_source(i,t,s))
        menu.append(item)
    profiles = load_profiles()
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

def reiniciar_indicador():
    Gtk.main_quit()
    run("$HOME/.local/bin/teclado-indicador.py")
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
        return ("Este perfil no tiene archivo keyd_conf asociado.\n"
            "Eso significa que el editor visual no importó ningún keyd.conf para esta configuración.\n\n"
            "Vuelve a abrir el editor visual, añade al menos un atajo keyd o activa el bloqueo global de atajos, "
            "y guarda/importa de nuevo.")
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

def uok_enable_cinnamon_status_icon(menu):
    try:
        if not uok_is_cinnamon():
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
    if uok_cinnamon_status_icon is not None and uok_is_cinnamon():
        indicator.set_status(AppIndicator3.IndicatorStatus.PASSIVE)
except Exception:
    pass

Gtk.main()

