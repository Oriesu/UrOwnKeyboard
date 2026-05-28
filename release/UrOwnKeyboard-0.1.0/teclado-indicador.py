#!/usr/bin/env python3
import ast
import os
import json
import re
import shlex
import shutil
import subprocess
import unicodedata
from pathlib import Path

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")

from gi.repository import Gtk
from gi.repository import AyatanaAppIndicator3 as AppIndicator3


HOME = Path.home()
CONFIG = HOME / ".config" / "teclado-indicador"
PROFILES = CONFIG / "profiles"
XKB_DIR = CONFIG / "xkb"
KEYD_DIR = CONFIG / "keyd"
USER_XKB = HOME / ".xkb" / "symbols"
CURRENT_PROFILE = CONFIG / "current-profile.json"
UOK_BIN = HOME / ".local" / "bin" / "uok"
KEYD_HELPER = Path("/usr/local/sbin/keyd-aplicar-conf")

for d in [PROFILES, XKB_DIR, KEYD_DIR, USER_XKB]:
    d.mkdir(parents=True, exist_ok=True)


def sh(cmd):
    return subprocess.check_output(["bash", "-lc", cmd], text=True).strip()


def run(cmd):
    subprocess.Popen(["bash", "-lc", cmd])


def notify(title, msg):
    run(f'notify-send {shlex.quote(title)} {shlex.quote(msg)}')


def show_error(title, msg):
    subprocess.run([
        "zenity", "--error",
        "--title", title,
        "--text", msg,
    ], check=False)


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


def get_sources():
    try:
        raw = sh("gsettings get org.gnome.desktop.input-sources sources")
        return ast.literal_eval(raw)
    except Exception:
        return []


def source_label(source_type, source_id):
    names = {
        "es": "Spanish",
        "us": "US English",
        "de": "German",
        "fr": "French",
        "it": "Italiano",
        "pt": "Portuguese",
    }

    if source_type == "xkb":
        return names.get(source_id, source_id)

    if source_type == "ibus":
        return f"IBus: {source_id}"

    return f"{source_type}: {source_id}"



def menu_env():
    env = dict(os.environ) if "os" in globals() else {}
    env["PATH"] = (
        str(HOME / ".local" / "bin")
        + ":/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    )
    return env


def run_checked_for_menu(cmd, error_title="UrOwnKeyboard"):
    result = subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=menu_env(),
    )

    if result.returncode != 0:
        msg = result.stderr.strip() or result.stdout.strip() or "El comando falló."
        show_error(error_title, msg)
        return False

    return True


def aplicar_keyd_off_sync():
    return run_checked_for_menu(
        ["sudo", str(KEYD_HELPER), "--off"],
        "UrOwnKeyboard - keyd",
    )


def aplicar_gnome_source_sync(index):
    return run_checked_for_menu(
        ["gsettings", "set", "org.gnome.desktop.input-sources", "current", str(index)],
        "UrOwnKeyboard - GNOME",
    )


def aplicar_xkb_source_sync(source_type, source_id):
    if source_type != "xkb":
        return True

    if "+" in source_id:
        layout, variant = source_id.split("+", 1)
        cmd = ["setxkbmap", layout, variant]
    else:
        cmd = ["setxkbmap", source_id]

    return run_checked_for_menu(cmd, "UrOwnKeyboard - XKB")



def show_error(title, msg):
    subprocess.run([
        "zenity", "--error",
        "--title", title,
        "--text", msg,
    ], check=False)


def menu_env():
    env = dict(os.environ)
    env["PATH"] = (
        str(HOME / ".local" / "bin")
        + ":/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    )
    return env


def run_menu_cmd(cmd):
    return subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=menu_env(),
    )


def command_error(result, fallback="El comando falló."):
    return result.stderr.strip() or result.stdout.strip() or fallback


def keyd_is_active():
    result = run_menu_cmd(["systemctl", "is-active", "keyd"])
    return result.returncode == 0 and result.stdout.strip() == "active"


def raw_xkb_layout():
    result = run_menu_cmd(["setxkbmap", "-query"])
    if result.returncode != 0:
        return ""

    layout = ""
    variant = ""

    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("layout:"):
            layout = line.split(":", 1)[1].strip().split(",")[0]
        elif line.startswith("variant:"):
            variant = line.split(":", 1)[1].strip().split(",")[0]

    if not layout:
        return ""

    return f"{layout}+{variant}" if variant else layout


def expected_source_spec(source_id):
    return source_id.strip()


def verify_gnome_source_applied(source_type, source_id):
    if keyd_is_active():
        return False, "keyd sigue activo después de volver a una fuente normal."

    if source_type != "xkb":
        return True, ""

    got = raw_xkb_layout()
    expected = expected_source_spec(source_id)

    if got != expected:
        return False, f"XKB no cambió al layout esperado. Esperado: {expected}. Actual: {got or 'desconocido'}."

    return True, ""


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
        return False, (
            "El perfil activo guardado no coincide. "
            f"Esperado: {profile_id}. Actual: {got or 'desconocido'}."
        )

    return True, ""


def aplicar_keyd_off_sync():
    result = run_menu_cmd(["sudo", "-n", str(KEYD_HELPER), "--off"])

    if result.returncode != 0:
        show_error("UrOwnKeyboard - keyd", command_error(result, "No se pudo desactivar keyd."))
        return False

    return True


def aplicar_gnome_source_sync(index):
    result = run_menu_cmd([
        "gsettings",
        "set",
        "org.gnome.desktop.input-sources",
        "current",
        str(index),
    ])

    if result.returncode != 0:
        show_error("UrOwnKeyboard - GNOME", command_error(result, "No se pudo cambiar la fuente GNOME."))
        return False

    return True


def aplicar_xkb_source_sync(source_type, source_id):
    if source_type != "xkb":
        return True

    if "+" in source_id:
        layout, variant = source_id.split("+", 1)
        cmd = ["setxkbmap", layout, variant]
    else:
        cmd = ["setxkbmap", source_id]

    result = run_menu_cmd(cmd)

    if result.returncode != 0:
        show_error("UrOwnKeyboard - XKB", command_error(result, "No se pudo aplicar XKB."))
        return False

    return True


def set_xkb_from_id(source_id):
    if "+" in source_id:
        layout, variant = source_id.split("+", 1)
        return f"setxkbmap {shlex.quote(layout)} {shlex.quote(variant)}"
    return f"setxkbmap {shlex.quote(source_id)}"


def activar_gnome_source(index, source_type, source_id):
    label = source_label(source_type, source_id)

    if not aplicar_keyd_off_sync():
        return

    if not aplicar_gnome_source_sync(index):
        return

    if not aplicar_xkb_source_sync(source_type, source_id):
        return

    ok, msg = verify_gnome_source_applied(source_type, source_id)
    if not ok:
        show_error("UrOwnKeyboard - verificación", msg)
        return

    current = {
        "type": "gnome-source",
        "name": label,
        "source_type": source_type,
        "source_id": source_id,
        "keyd_conf": None,
    }

    CURRENT_PROFILE.write_text(
        json.dumps(current, indent=2, ensure_ascii=False)
    )

    notify("Keyboard", label + " activated")

def load_profiles():
    profiles = []
    for file in sorted(PROFILES.glob("*.json")):
        try:
            profile = json.loads(file.read_text())
            profile["_profile_file"] = str(file)
            profiles.append(profile)
        except Exception:
            pass
    return profiles


def activar_profile(profile):
    profile_id = profile.get("id")

    if not profile_id:
        show_error("UrOwnKeyboard", "Invalid imported configuration.")
        return

    uok_bin = UOK_BIN if UOK_BIN.exists() else Path("uok")

    result = run_menu_cmd([str(uok_bin), "activate", profile_id])

    if result.returncode != 0:
        show_error(
            "UrOwnKeyboard",
            command_error(result, "Could not activate configuration."),
        )
        return

    ok, msg = verify_uok_profile_applied(profile_id)
    if not ok:
        show_error("UrOwnKeyboard - verificación", msg)
        return

    notify("Keyboard", result.stdout.strip() or f"{profile.get('name', profile_id)} activated")

def crear_layout_visual(_):
    editor = HOME / ".local" / "bin" / "uok-layout-editor.py"
    if not editor.exists():
        editor = Path(__file__).resolve().parent / "uok-layout-editor.py"
    run(f'{shlex.quote(str(editor))} || notify-send "Keyboard" "Could not open layout editor"')

def importar_configuracion(_):
    name = sh(
        'zenity --entry '
        '--title="Import keyboard" '
        '--text="Configuration name:" '
        '|| true'
    )

    if not name:
        return

    base_id = safe_id(name)
    layout_id = unique_layout_id(base_id)

    xkb_file = sh(
        'zenity --file-selection '
        '--title="Select XKB / symbols file" '
        '|| true'
    )

    if not xkb_file:
        return

    keyd_file = sh(
        'zenity --file-selection '
        '--title="Selecciona keyd.conf opcional" '
        '--filename="$HOME/" '
        '|| true'
    )

    dest_xkb = USER_XKB / layout_id
    shutil.copyfile(xkb_file, dest_xkb)

    profile = {
        "id": layout_id,
        "name": name,
        "xkb_file": str(dest_xkb),
    }

    if keyd_file:
        dest_keyd = KEYD_DIR / f"{layout_id}.conf"
        shutil.copyfile(keyd_file, dest_keyd)
        profile["keyd_conf"] = str(dest_keyd)

    (PROFILES / f"{layout_id}.json").write_text(
        json.dumps(profile, indent=2, ensure_ascii=False)
    )

    if layout_id != base_id:
        notify("Keyboard", f"Configuration {name} imported as {layout_id}")
    else:
        notify("Keyboard", f"Configuration {name} imported")

    reiniciar_indicador()


def borrar_si_seguro(path_str):
    if not path_str:
        return

    path = Path(path_str).expanduser().resolve()

    zonas_permitidas = [
        USER_XKB.resolve(),
        KEYD_DIR.resolve(),
        XKB_DIR.resolve(),
    ]

    permitido = any(
        str(path).startswith(str(zona) + "/") or path == zona
        for zona in zonas_permitidas
    )

    if permitido and path.exists() and path.is_file():
        path.unlink()


def eliminar_configuracion(_):
    profiles = load_profiles()

    if not profiles:
        notify("Keyboard", "There are no imported configurations to delete")
        return

    opciones = []
    for profile in profiles:
        opciones.append(profile["id"])
        opciones.append(profile["name"])

    quoted_options = " ".join(shlex.quote(x) for x in opciones)

    cmd = (
        'zenity --list '
        '--title="Delete configuration" '
        '--text="Select the configuration you want to delete:" '
        '--column="ID" '
        '--column="Name" '
        '--hide-column=1 '
        '--print-column=1 '
        f'{quoted_options} '
        '|| true'
    )

    selected_id = sh(cmd)

    if not selected_id:
        return

    profile = next((p for p in profiles if p["id"] == selected_id), None)

    if not profile:
        return

    confirm = sh(
        'zenity --question '
        '--title="Delete configuration" '
        f'--text={shlex.quote("Delete configuration “" + profile["name"] + "”?")} '
        '&& echo yes || true'
    )

    if confirm != "yes":
        return

    borrar_si_seguro(profile.get("xkb_file"))
    borrar_si_seguro(profile.get("keyd_conf"))

    profile_file = Path(profile["_profile_file"]).resolve()

    if str(profile_file).startswith(str(PROFILES.resolve()) + "/") and profile_file.exists():
        profile_file.unlink()

    notify("Keyboard", f"Configuration {profile['name']} deleted")
    reiniciar_indicador()


def get_current_profile():
    if CURRENT_PROFILE.exists():
        try:
            return json.loads(CURRENT_PROFILE.read_text())
        except Exception:
            return None
    return None


def get_xkb_spec_actual():
    profile = get_current_profile()

    if profile and profile.get("type") == "imported-profile" and profile.get("id"):
        return profile["id"]

    query = sh("setxkbmap -query")
    layout = ""
    variant = ""

    for line in query.splitlines():
        if line.startswith("layout:"):
            layout = line.split(":", 1)[1].strip().split(",")[0]
        elif line.startswith("variant:"):
            variant = line.split(":", 1)[1].strip().split(",")[0]

    if not layout:
        return ""

    if variant:
        return f"{layout}({variant})"

    return layout



def mostrar_distribucion_actual(_):
    try:
        spec = get_xkb_spec_actual()

        if not spec:
            notify("Keyboard", "Could not detect the current layout")
            return

        run(
            f'gkbd-keyboard-display -l {shlex.quote(spec)} '
            f'|| notify-send "Keyboard" "No se pudo abrir el visor para {spec}"'
        )

    except Exception:
        notify("Keyboard", "Could not open the current layout viewer")


def mostrar_texto(title, content):
    try:
        proc = subprocess.Popen(
            [
                "zenity",
                "--text-info",
                f"--title={title}",
                "--width=900",
                "--height=700",
                "--font=monospace",
            ],
            stdin=subprocess.PIPE,
            text=True,
        )

        if proc.stdin:
            proc.stdin.write(content)
            proc.stdin.close()

    except Exception:
        notify("Keyboard", "Could not open the information window")


def mostrar_configuracion_completa(_):
    try:
        spec = get_xkb_spec_actual()

        if spec:
            run(
                f'gkbd-keyboard-display -l {shlex.quote(spec)} '
                f'|| notify-send "Keyboard" "No se pudo abrir el visor para {spec}"'
            )

        info = []

        info.append("CURRENT CONFIGURATION")
        info.append("=" * 80)
        info.append("")

        if spec:
            info.append(f"Active XKB layout: {spec}")
        else:
            info.append("Active XKB layout: no detectado")

        info.append("")
        info.append("setxkbmap -query")
        info.append("-" * 80)

        try:
            info.append(sh("setxkbmap -query"))
        except Exception:
            info.append("No se pudo leer setxkbmap -query")

        info.append("")
        info.append("UR OWN KEYBOARD PROFILE")
        info.append("=" * 80)
        info.append("")

        profile = get_current_profile()

        if profile:
            info.append(f"Name: {profile.get('name', 'unnamed')}")
            info.append(f"Type: {profile.get('type', 'unknown')}")

            if profile.get("id"):
                info.append(f"ID: {profile.get('id')}")

            if profile.get("source_id"):
                info.append(f"GNOME source: {profile.get('source_id')}")

            if profile.get("xkb_file"):
                info.append(f"XKB file: {profile.get('xkb_file')}")

                info.append("")
                info.append("XKB FILE CONTENT")
                info.append("=" * 80)
                info.append("")

                try:
                    info.append(Path(profile.get("xkb_file")).read_text())
                except Exception:
                    info.append("Could not read the associated XKB file.")

            keyd_conf = profile.get("keyd_conf")

            info.append("")

            if keyd_conf:
                info.append("ACTIVE KEYD")
                info.append("=" * 80)
                info.append("")
                info.append(f"keyd file: {keyd_conf}")
                info.append("")
                info.append("-" * 80)

                try:
                    info.append(Path(keyd_conf).read_text())
                except Exception:
                    info.append("Could not read the associated keyd file.")
            else:
                info.append("ACTIVE KEYD")
                info.append("=" * 80)
                info.append("")
                info.append("This configuration has no associated keyd.conf.")
                info.append("If this is a regular GNOME input source, keyd is used in normal mode.")
        else:
            info.append("No active profile registered by UrOwnKeyboard.")
            info.append("")
            info.append("This can happen if the current keyboard was changed outside the indicator.")

        mostrar_texto("Full configuration", "\n".join(info))

    except Exception:
        notify("Keyboard", "Could not show the full configuration")



def abrir_editor_visual(_item=None):
    import sys

    candidates = [
        Path(__file__).resolve().parent / "uok-layout-editor.py",
        HOME / ".local" / "bin" / "uok-layout-editor.py",
        Path.cwd() / "uok-layout-editor.py",
    ]

    editor = next((path for path in candidates if path.exists()), None)

    if editor is None:
        notify("UrOwnKeyboard", "No se encontró el editor visual.")
        return

    subprocess.Popen(
        [sys.executable, str(editor)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )



def abrir_ajustes_teclado(_item=None):
    commands = [
        ["gnome-control-center", "keyboard"],
        ["cinnamon-settings", "keyboard"],
        ["xfce4-keyboard-settings"],
        ["systemsettings", "kcm_keyboard"],
    ]

    for cmd in commands:
        try:
            subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return
        except FileNotFoundError:
            continue
        except Exception:
            continue

    notify("UrOwnKeyboard", "No se pudo abrir la configuración de teclado del sistema.")




def get_raw_setxkbmap_spec():
    """
    Lee el XKB real desde setxkbmap, sin fiarse del perfil guardado por UOK.
    Devuelve algo como:
    - es
    - de
    - us(intl)
    - dvorakesprogrammer
    """
    try:
        query = sh("setxkbmap -query")
    except Exception:
        return ""

    layout = ""
    variant = ""

    for line in query.splitlines():
        if line.startswith("layout:"):
            layout = line.split(":", 1)[1].strip().split(",")[0].strip()
        elif line.startswith("variant:"):
            variant = line.split(":", 1)[1].strip().split(",")[0].strip()

    if not layout:
        return ""

    if variant:
        return f"{layout}({variant})"

    return layout


def gnome_source_to_setxkbmap_cmd(source_type, source_id):
    if source_type != "xkb":
        return ""

    if "+" in source_id:
        layout, variant = source_id.split("+", 1)
        return f"setxkbmap {shlex.quote(layout)} {shlex.quote(variant)}"

    return f"setxkbmap {shlex.quote(source_id)}"


def get_gnome_current_source():
    sources = get_sources()

    if not sources:
        return None

    try:
        current_raw = sh("gsettings get org.gnome.desktop.input-sources current")
        current = int(str(current_raw).replace("uint32", "").strip())
    except Exception:
        current = 0

    if current < 0 or current >= len(sources):
        current = 0

    source = sources[current]

    if len(source) != 2:
        return None

    source_type, source_id = source

    return {
        "index": current,
        "source_type": source_type,
        "source_id": source_id,
        "name": source_label(source_type, source_id),
    }


def guardar_gnome_source_actual(source):
    current = {
        "type": "gnome-source",
        "name": source["name"],
        "source_type": source["source_type"],
        "source_id": source["source_id"],
        "keyd_conf": None,
    }

    CURRENT_PROFILE.write_text(
        json.dumps(current, indent=2, ensure_ascii=False)
    )


def aplicar_keyd_de_profile_o_apagar(profile):
    keyd_conf = profile.get("keyd_conf") if profile else None

    if keyd_conf:
        keyd_path = Path(keyd_conf).expanduser()

        if keyd_path.exists():
            run(f"sudo /usr/local/sbin/keyd-aplicar-conf {shlex.quote(str(keyd_path))}")
            return

    run("sudo /usr/local/sbin/keyd-aplicar-conf --off")


def sincronizar_estado_al_arrancar():
    current = get_current_profile()

    if current and current.get("type") == "imported-profile" and current.get("id"):
        uok_bin = UOK_BIN if "UOK_BIN" in globals() and UOK_BIN.exists() else Path.home() / ".local" / "bin" / "uok"

        subprocess.run(
            [str(uok_bin), "activate", current["id"]],
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return

    """
    Al arrancar:
    1. Mira el XKB real.
    2. Si el XKB real coincide con un perfil importado de UOK, aplica su keyd.
    3. Si no coincide, toma la fuente real de GNOME como verdad, guarda ese estado
       y apaga keyd personalizado.
    Así evitamos arrancar con QWERTY normal pero keyd personalizado antiguo.
    """
    profile = get_current_profile()
    raw_spec = get_raw_setxkbmap_spec()

    if profile and profile.get("type") == "imported-profile" and profile.get("id"):
        profile_id = profile.get("id")

        if raw_spec == profile_id or raw_spec.startswith(profile_id + "("):
            aplicar_keyd_de_profile_o_apagar(profile)
            return

    source = get_gnome_current_source()

    if source:
        guardar_gnome_source_actual(source)

        cmds = ["sudo /usr/local/sbin/keyd-aplicar-conf --off"]

        setxkbmap_cmd = gnome_source_to_setxkbmap_cmd(
            source["source_type"],
            source["source_id"],
        )

        if setxkbmap_cmd:
            cmds.append(setxkbmap_cmd)

        run(" && ".join(cmds))
        return

    aplicar_keyd_de_profile_o_apagar(profile)


def crear_menu():
    menu = Gtk.Menu()

    sources = get_sources()

    for index, source in enumerate(sources):
        if len(source) != 2:
            continue

        source_type, source_id = source
        label = source_label(source_type, source_id)

        item = Gtk.MenuItem(label=label)
        item.connect(
            "activate",
            lambda _, i=index, t=source_type, s=source_id: activar_gnome_source(i, t, s)
        )
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


indicator = AppIndicator3.Indicator.new(
    "teclado-custom",
    "input-keyboard",
    AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
)

indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
indicator.set_title("Keyboard")

sincronizar_estado_al_arrancar()
indicator.set_menu(crear_menu())

Gtk.main()
