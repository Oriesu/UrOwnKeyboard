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


def desktop_name():
    values = [
        os.environ.get("XDG_CURRENT_DESKTOP", ""),
        os.environ.get("DESKTOP_SESSION", ""),
    ]
    return ":".join(values).lower()


def is_xfce():
    return "xfce" in desktop_name()


def is_gnome():
    return "gnome" in desktop_name()


def split_csv_list(value):
    return [x.strip() for x in (value or "").split(",")]


def source_id_from_layout_variant(layout, variant=""):
    layout = (layout or "").strip()
    variant = (variant or "").strip()

    if not layout:
        return ""

    return f"{layout}+{variant}" if variant else layout


def parse_setxkbmap_sources():
    result = run_menu_cmd(["setxkbmap", "-query"])
    if result.returncode != 0:
        return []

    layouts = []
    variants = []

    for line in result.stdout.splitlines():
        clean = line.strip()

        if clean.startswith("layout:"):
            layouts = split_csv_list(clean.split(":", 1)[1].strip())
        elif clean.startswith("variant:"):
            variants = split_csv_list(clean.split(":", 1)[1].strip())

    while len(variants) < len(layouts):
        variants.append("")

    out = []

    for layout, variant in zip(layouts, variants):
        source_id = source_id_from_layout_variant(layout, variant)
        if source_id:
            out.append(("xkb", source_id))

    return out


def xfconf_get(prop):
    result = run_menu_cmd(["xfconf-query", "-c", "keyboard-layout", "-p", prop])
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def parse_xfce_sources():
    layouts = split_csv_list(xfconf_get("/Default/XkbLayout"))
    variants = split_csv_list(xfconf_get("/Default/XkbVariant"))

    while len(variants) < len(layouts):
        variants.append("")

    out = []

    for layout, variant in zip(layouts, variants):
        source_id = source_id_from_layout_variant(layout, variant)
        if source_id:
            out.append(("xkb", source_id))

    # XFCE a veces no guarda todavía la lista en xfconf aunque XKB sí la tenga activa.
    # Por eso mezclamos también lo que ve setxkbmap.
    out.extend(parse_setxkbmap_sources())

    seen = set()
    unique = []

    for item in out:
        if item not in seen:
            seen.add(item)
            unique.append(item)

    return unique


def parse_gnome_sources():
    try:
        raw = sh("gsettings get org.gnome.desktop.input-sources sources")
        return ast.literal_eval(raw)
    except Exception:
        return []


def get_sources():
    if is_xfce():
        sources = parse_xfce_sources()
        if sources:
            return sources

    return parse_gnome_sources()


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
    # keyd puede y debe seguir activo como servicio.
    # Al volver a una fuente normal, aplicar_keyd_off_sync() deja /etc/keyd/default.conf neutral.
    # Por tanto no verificamos "systemctl is-active keyd", porque eso sólo indica que el daemon está arrancado.

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
    if is_xfce():
        return True

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
        "desktop": "xfce" if is_xfce() else "gnome" if is_gnome() else "xkb",
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



def uok_profile_is_current(profile):
    if not profile or not CURRENT_PROFILE.exists():
        return False

    try:
        current = json.loads(CURRENT_PROFILE.read_text(encoding="utf-8"))
    except Exception:
        return False

    return (
        current.get("type") == "imported-profile"
        and current.get("id")
        and current.get("id") == profile.get("id")
    )


def uok_safe_before_delete_profile(profile):
    """
    Si se borra el perfil activo, keyd no debe quedarse aplicando un .conf
    que va a desaparecer.

    También dejamos XKB en una distribución segura para no seguir apuntando
    a un archivo ~/.xkb/symbols/<perfil> borrado.
    """
    if not uok_profile_is_current(profile):
        return True

    # Primero apagar keyd si el perfil activo tenía keyd asociado.
    if profile.get("keyd_conf"):
        if not aplicar_keyd_off_sync():
            return False

    # Luego cambiar a un XKB seguro.
    run_menu_cmd(["setxkbmap", "es"])

    # Y eliminar el marcador de perfil activo para que el arranque no intente reactivarlo.
    try:
        if CURRENT_PROFILE.exists():
            CURRENT_PROFILE.unlink()
    except Exception:
        pass

    return True


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

    if not uok_safe_before_delete_profile(profile):
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
    """
    Abre la configuración de teclado del escritorio actual.

    En MATE usamos mate-keyboard-properties / mate-control-center keyboard.
    Al cerrar la ventana, reiniciamos el indicador para releer las fuentes
    añadidas desde ajustes.
    """
    import shutil

    if uok_is_mate_desktop():
        commands = [
            ["mate-keyboard-properties"],
            ["mate-control-center", "keyboard"],
        ]
    else:
        commands = [
            ["gnome-control-center", "keyboard"],
            ["cinnamon-settings", "keyboard"],
            ["xfce4-keyboard-settings"],
            ["systemsettings", "kcm_keyboard"],
        ]

    for cmd in commands:
        if not shutil.which(cmd[0]):
            continue

        try:
            # El shell espera a que se cierre la ventana y luego reinicia UOK.
            shell_cmd = (
                " ".join(shlex.quote(x) for x in cmd)
                + "; "
                + "pkill -f teclado-indicador.py 2>/dev/null || true; "
                + "$HOME/.local/bin/teclado-indicador.py >/dev/null 2>&1 &"
            )

            subprocess.Popen(
                ["bash", "-lc", shell_cmd],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return

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


def xfce_keyboard_plugin_ids():
    result = run_menu_cmd(["xfconf-query", "-c", "xfce4-panel", "-l"])
    if result.returncode != 0:
        return []

    plugin_ids = []

    for line in result.stdout.splitlines():
        m = re.fullmatch(r"/plugins/plugin-(\d+)", line.strip())
        if not m:
            continue

        plugin_id = m.group(1)
        name = run_menu_cmd([
            "xfconf-query",
            "-c",
            "xfce4-panel",
            "-p",
            f"/plugins/plugin-{plugin_id}",
        ])

        if name.returncode == 0 and name.stdout.strip() in {"xkb", "keyboard-layouts"}:
            plugin_ids.append(int(plugin_id))

    return plugin_ids


def xfconf_panel_array(prop):
    result = run_menu_cmd(["xfconf-query", "-c", "xfce4-panel", "-p", prop])
    if result.returncode != 0:
        return []

    return [int(x) for x in re.findall(r"=\s*(\d+)", result.stdout)]


def xfconf_set_panel_array(prop, values):
    if not values:
        return False

    cmd = ["xfconf-query", "-c", "xfce4-panel", "-p", prop, "--force-array"]

    for value in values:
        cmd.extend(["-t", "int", "-s", str(value)])

    result = run_menu_cmd(cmd)
    return result.returncode == 0


def ocultar_menu_xfce():
    if not is_xfce():
        return

    plugin_ids = set(xfce_keyboard_plugin_ids())
    if not plugin_ids:
        return

    result = run_menu_cmd(["xfconf-query", "-c", "xfce4-panel", "-l"])
    if result.returncode != 0:
        return

    changed = False

    for line in result.stdout.splitlines():
        prop = line.strip()

        if not re.fullmatch(r"/panels/panel-\d+/plugin-ids", prop):
            continue

        current = xfconf_panel_array(prop)
        if not current:
            continue

        new_values = [x for x in current if x not in plugin_ids]

        if new_values != current:
            if xfconf_set_panel_array(prop, new_values):
                changed = True

    if changed:
        run_menu_cmd(["xfce4-panel", "-r"])
        notify("UrOwnKeyboard", "XFCE keyboard layout indicator hidden")


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



def uok_is_mate_desktop():
    desktop = (
        os.environ.get("XDG_CURRENT_DESKTOP", "") + ":" +
        os.environ.get("DESKTOP_SESSION", "")
    ).lower()
    return "mate" in desktop


def uok_mate_layout_label(layout, variant=""):
    names = {
        "es": "Español",
        "de": "Alemán",
        "us": "Inglés (US)",
        "gb": "Inglés (UK)",
        "fr": "Francés",
        "it": "Italiano",
        "pt": "Portugués",
    }
    label = names.get(layout, layout)
    if variant:
        label = f"{label} ({variant})"
    return label




def uok_is_cinnamon_desktop():
    desktop = " ".join([
        os.environ.get("XDG_CURRENT_DESKTOP", ""),
        os.environ.get("DESKTOP_SESSION", ""),
        os.environ.get("XDG_SESSION_DESKTOP", ""),
    ]).lower()

    return "cinnamon" in desktop


def uok_libgnomekbd_system_sources():
    """
    Cinnamon guarda las distribuciones añadidas aquí:
    org.gnome.libgnomekbd.keyboard layouts
    """
    if not uok_is_cinnamon_desktop():
        return []

    result = run_menu_cmd([
        "gsettings",
        "get",
        "org.gnome.libgnomekbd.keyboard",
        "layouts",
    ])

    if result.returncode != 0:
        return []

    raw_layouts = re.findall(r"'([^']+)'", result.stdout.strip())
    out = []
    seen = set()

    for raw in raw_layouts:
        raw = (raw or "").strip()

        if not raw:
            continue

        if "+" in raw:
            layout, variant = raw.split("+", 1)
        elif "(" in raw and raw.endswith(")"):
            layout, variant = raw[:-1].split("(", 1)
        else:
            layout, variant = raw, ""

        layout = layout.strip()
        variant = variant.strip()

        if not layout:
            continue

        sid = layout if not variant else f"{layout}+{variant}"

        if sid in seen:
            continue

        seen.add(sid)

        out.append({
            "kind": "xkb",
            "id": sid,
            "label": uok_mate_layout_label(layout, variant) if "uok_mate_layout_label" in globals() else sid,
        })

    return out


def uok_merge_libgnomekbd_system_sources(rows):
    extra = uok_libgnomekbd_system_sources()

    if not extra:
        return rows

    seen = set()
    merged = []

    for row in extra:
        key = row.get("id")

        if key in seen:
            continue

        seen.add(key)
        merged.append(row)

    for row in rows:
        key = row.get("id")

        if key in seen:
            continue

        seen.add(key)
        merged.append(row)

    return merged


def uok_mate_system_sources():
    """
    Devuelve solo las distribuciones configuradas en la sesión MATE actual.

    En MATE la lista real de teclados añadidos está en:
    org.mate.peripherals-keyboard-xkb.kbd layouts

    setxkbmap -query solo muestra el estado activo o efectivo, así que no basta
    para saber que, por ejemplo, alemán está añadido al sistema.
    """
    out = []
    seen = set()

    def add_xkb(layout, variant=""):
        layout = (layout or "").strip()
        variant = (variant or "").strip()

        if not layout:
            return

        sid = layout if not variant else f"{layout}+{variant}"

        if sid in seen:
            return

        seen.add(sid)
        out.append({
            "kind": "xkb",
            "id": sid,
            "label": uok_mate_layout_label(layout, variant),
        })

    # 1) Fuente principal en MATE: layouts añadidos desde la configuración.
    result = run_menu_cmd([
        "gsettings",
        "get",
        "org.mate.peripherals-keyboard-xkb.kbd",
        "layouts",
    ])

    if result.returncode == 0:
        import re
        layouts = re.findall(r"'([^']+)'", result.stdout.strip())

        for raw in layouts:
            raw = (raw or "").strip()

            if not raw:
                continue

            if "+" in raw:
                layout, variant = raw.split("+", 1)
            elif "(" in raw and raw.endswith(")"):
                layout, variant = raw[:-1].split("(", 1)
            else:
                layout, variant = raw, ""

            add_xkb(layout, variant)

    # 2) Fuente secundaria: XKB activo/configurado en la sesión.
    result = run_menu_cmd(["setxkbmap", "-query"])

    if result.returncode == 0:
        layout_line = ""
        variant_line = ""

        for line in result.stdout.splitlines():
            line = line.strip()

            if line.startswith("layout:"):
                layout_line = line.split(":", 1)[1].strip()
            elif line.startswith("variant:"):
                variant_line = line.split(":", 1)[1].strip()

        layouts = [x.strip() for x in layout_line.split(",") if x.strip()]
        variants = [x.strip() for x in variant_line.split(",")] if variant_line else []

        while len(variants) < len(layouts):
            variants.append("")

        for layout, variant in zip(layouts, variants):
            add_xkb(layout, variant)

    # 3) Fuente terciaria: solo motores IBus añadidos/preconfigurados.
    result = run_menu_cmd([
        "gsettings",
        "get",
        "org.freedesktop.ibus.general",
        "preload-engines",
    ])

    if result.returncode == 0:
        import re
        engine_ids = re.findall(r"'([^']+)'", result.stdout.strip())

        for engine_id in engine_ids:
            if not engine_id.startswith("xkb:"):
                continue

            parts = engine_id.split(":")
            layout = parts[1] if len(parts) > 1 else ""
            variant = parts[2] if len(parts) > 2 else ""

            if not layout:
                continue

            sid = layout if not variant else f"{layout}+{variant}"

            if sid in seen:
                continue

            seen.add(sid)
            out.append({
                "kind": "ibus",
                "id": engine_id,
                "label": uok_mate_layout_label(layout, variant),
            })

    return uok_merge_libgnomekbd_system_sources(out)



def uok_mate_disable_keyd():
    try:
        run_menu_cmd(["sudo", "/usr/local/sbin/keyd-aplicar-conf", ""])
    except Exception:
        pass


def uok_mate_apply_system_source(source):
    uok_mate_disable_keyd()

    if source.get("kind") == "ibus":
        result = run_menu_cmd(["ibus", "engine", source["id"]])
    else:
        sid = source["id"]
        parts = sid.split("+", 1)
        layout = parts[0]
        variant = parts[1] if len(parts) > 1 else ""

        if variant:
            result = run_menu_cmd(["setxkbmap", layout, variant])
        else:
            result = run_menu_cmd(["setxkbmap", layout])

    if result.returncode != 0:
        show_error(
            "UrOwnKeyboard",
            command_error(result, "No se pudo activar la distribución del sistema."),
        )
        return

    actualizar_menu()


def uok_mate_hide_native_input_indicators():
    if not uok_is_mate_desktop():
        return

    # Indicador nativo XKB/libgnomekbd de MATE.
    try:
        run_menu_cmd([
            "gsettings",
            "set",
            "org.mate.peripherals-keyboard-xkb.general",
            "disable-indicator",
            "true",
        ])
    except Exception:
        pass

    try:
        run_menu_cmd([
            "gsettings",
            "set",
            "org.mate.peripherals-keyboard-xkb.indicator",
            "show-flags",
            "false",
        ])
    except Exception:
        pass

    try:
        run_menu_cmd([
            "gsettings",
            "set",
            "org.gnome.libgnomekbd.indicator",
            "show-flags",
            "false",
        ])
    except Exception:
        pass

    # Indicador Canonical/MATE.
    try:
        run_menu_cmd([
            "gsettings",
            "set",
            "com.canonical.indicator.keyboard",
            "visible",
            "false",
        ])
    except Exception:
        pass

    # Icono IBus, sin apagar IBus.
    try:
        run_menu_cmd([
            "gsettings",
            "set",
            "org.freedesktop.ibus.panel",
            "show-icon-on-systray",
            "false",
        ])
        run_menu_cmd([
            "gsettings",
            "set",
            "org.freedesktop.ibus.panel",
            "show-im-name",
            "false",
        ])
    except Exception:
        pass


def uok_mate_append_system_sources_to_menu(menu):
    if not uok_is_mate_desktop():
        return

    uok_mate_hide_native_input_indicators()

    mate_sources = uok_mate_system_sources()
    if not mate_sources:
        return

    title = Gtk.MenuItem(label="Distribuciones del sistema")
    title.set_sensitive(False)
    menu.append(title)

    for source in mate_sources:
        item = Gtk.MenuItem(label=source["label"])
        item.connect(
            "activate",
            lambda _item, src=source: uok_mate_apply_system_source(src),
        )
        menu.append(item)

    menu.append(Gtk.SeparatorMenuItem())



# --------------------------------------------------------------------
# UOK Cinnamon: system layouts from libgnomekbd
# --------------------------------------------------------------------

def uok_is_cinnamon_desktop():
    desktop = " ".join([
        os.environ.get("XDG_CURRENT_DESKTOP", ""),
        os.environ.get("DESKTOP_SESSION", ""),
        os.environ.get("XDG_SESSION_DESKTOP", ""),
    ]).lower()

    return "cinnamon" in desktop


def uok_cinnamon_layout_label(layout, variant=""):
    labels = {
        "es": "Español",
        "de": "Alemán",
        "us": "Inglés (EE. UU.)",
        "gb": "Inglés (Reino Unido)",
        "fr": "Francés",
        "it": "Italiano",
        "pt": "Portugués",
        "br": "Portugués (Brasil)",
    }

    base = labels.get(layout, layout.upper())

    if variant:
        return f"{base} ({variant})"

    return base


def uok_cinnamon_system_sources():
    """
    Cinnamon guarda las distribuciones añadidas en:
    org.gnome.libgnomekbd.keyboard layouts
    """
    if not uok_is_cinnamon_desktop():
        return []

    try:
        result = run_menu_cmd([
            "gsettings",
            "get",
            "org.gnome.libgnomekbd.keyboard",
            "layouts",
        ])
    except Exception:
        return []

    if result.returncode != 0:
        return []

    rows = []
    seen = set()

    for raw in re.findall(r"'([^']+)'", result.stdout.strip()):
        raw = (raw or "").strip()

        if not raw:
            continue

        if "+" in raw:
            layout, variant = raw.split("+", 1)
        elif "(" in raw and raw.endswith(")"):
            layout, variant = raw[:-1].split("(", 1)
        else:
            layout, variant = raw, ""

        layout = layout.strip()
        variant = variant.strip()

        if not layout:
            continue

        sid = layout if not variant else f"{layout}+{variant}"

        if sid in seen:
            continue

        seen.add(sid)

        rows.append({
            "kind": "xkb",
            "id": sid,
            "layout": layout,
            "variant": variant,
            "label": uok_cinnamon_layout_label(layout, variant),
        })

    return rows


def uok_cinnamon_disable_keyd():
    """
    Al cambiar a una distribución del sistema, keyd no debe seguir aplicando
    el perfil UOK anterior.
    """
    for cmd in [
        ["sudo", "-n", "/usr/local/sbin/keyd-aplicar-conf", ""],
        ["/usr/local/sbin/keyd-aplicar-conf", ""],
    ]:
        try:
            result = run_menu_cmd(cmd)

            if result.returncode == 0:
                return True
        except Exception:
            pass

    return False


def uok_cinnamon_apply_system_source(row):
    layout = row.get("layout") or row.get("id", "").split("+", 1)[0]
    variant = row.get("variant", "")

    if not layout:
        return

    uok_cinnamon_disable_keyd()

    cmd = ["setxkbmap", layout]

    if variant:
        cmd += ["-variant", variant]

    try:
        result = run_menu_cmd(cmd)

        if result.returncode != 0:
            notify("UrOwnKeyboard", "No se pudo activar la distribución del sistema.")
            return

        notify("UrOwnKeyboard", f"Distribución activada: {row.get('label', layout)}")

    except Exception as exc:
        notify("UrOwnKeyboard", f"No se pudo activar la distribución: {exc}")


def uok_cinnamon_append_system_sources_to_menu(menu):
    if not uok_is_cinnamon_desktop():
        return

    rows = uok_cinnamon_system_sources()

    if not rows:
        return

    menu.append(Gtk.SeparatorMenuItem())

    title = Gtk.MenuItem(label="Distribuciones del sistema")
    title.set_sensitive(False)
    menu.append(title)

    for row in rows:
        item = Gtk.MenuItem(label=row.get("label", row.get("id", "")))
        item.connect("activate", lambda _item, selected=row: uok_cinnamon_apply_system_source(selected))
        menu.append(item)



# --------------------------------------------------------------------
# UOK LXQt: system layouts and native indicator hiding
# --------------------------------------------------------------------

def uok_lxqt_panel_conf_path():
    return Path.home() / ".config/lxqt/panel.conf"


def uok_lxqt_hide_native_input_indicators():
    if not uok_is_lxqt_desktop():
        return

    # IBus.
    for cmd in [
        ["gsettings", "set", "org.freedesktop.ibus.panel", "show-icon-on-systray", "false"],
        ["gsettings", "set", "org.freedesktop.ibus.panel", "show-im-name", "false"],
    ]:
        try:
            run_menu_cmd(cmd)
        except Exception:
            pass

    # LXQt keyboard indicator plugin: kbindicator.
    # No tocamos tray/statusnotifier, porque ahí puede vivir UOK.
    conf = uok_lxqt_panel_conf_path()

    if not conf.exists():
        return

    try:
        text = conf.read_text(encoding="utf-8")
    except Exception:
        return

    original = text

    # Quitar kbindicator de listas tipo plugins=...
    text = re.sub(
        r"(^plugins=.*)$",
        lambda m: re.sub(r",?kbindicator,?|kbindicator,?", lambda x: "," if "," in x.group(0) else "", m.group(1)).replace(",,", ",").rstrip(","),
        text,
        flags=re.M,
    )

    # Quitar sección [kbindicator].
    text = re.sub(
        r"\n?\[kbindicator\]\n.*?(?=\n\[[^\]]+\]|\Z)",
        "\n",
        text,
        flags=re.S,
    )

    if text != original:
        try:
            backup = conf.with_suffix(".conf.uok-backup")
            if not backup.exists():
                backup.write_text(original, encoding="utf-8")
            conf.write_text(text, encoding="utf-8")
        except Exception:
            pass


def uok_lxqt_layout_label(layout, variant=""):
    labels = {
        "es": "Español",
        "de": "Alemán",
        "us": "Inglés (EE. UU.)",
        "gb": "Inglés (Reino Unido)",
        "fr": "Francés",
        "it": "Italiano",
        "pt": "Portugués",
        "br": "Portugués (Brasil)",
    }

    base = labels.get(layout, layout.upper())

    if variant:
        return f"{base} ({variant})"

    return base


def uok_lxqt_system_sources():
    if not uok_is_lxqt_desktop():
        return []

    result = run_menu_cmd(["setxkbmap", "-query"])

    if result.returncode != 0:
        return []

    layout_line = ""
    variant_line = ""

    for line in result.stdout.splitlines():
        line = line.strip()

        if line.startswith("layout:"):
            layout_line = line.split(":", 1)[1].strip()
        elif line.startswith("variant:"):
            variant_line = line.split(":", 1)[1].strip()

    layouts = [x.strip() for x in layout_line.split(",") if x.strip()]
    variants = [x.strip() for x in variant_line.split(",")] if variant_line else []

    while len(variants) < len(layouts):
        variants.append("")

    rows = []
    seen = set()

    for layout, variant in zip(layouts, variants):
        if not layout:
            continue

        sid = layout if not variant else f"{layout}+{variant}"

        if sid in seen:
            continue

        seen.add(sid)

        rows.append({
            "kind": "xkb",
            "id": sid,
            "layout": layout,
            "variant": variant,
            "label": uok_lxqt_layout_label(layout, variant),
        })

    return rows


def uok_lxqt_disable_keyd():
    for cmd in [
        ["sudo", "-n", "/usr/local/sbin/keyd-aplicar-conf", ""],
        ["/usr/local/sbin/keyd-aplicar-conf", ""],
    ]:
        try:
            result = run_menu_cmd(cmd)
            if result.returncode == 0:
                return True
        except Exception:
            pass

    return False


def uok_lxqt_apply_system_source(row):
    layout = row.get("layout") or row.get("id", "").split("+", 1)[0]
    variant = row.get("variant", "")

    if not layout:
        return

    uok_lxqt_disable_keyd()

    cmd = ["setxkbmap", layout]

    if variant:
        cmd += ["-variant", variant]

    result = run_menu_cmd(cmd)

    if result.returncode == 0:
        notify("UrOwnKeyboard", f"Distribución activada: {row.get('label', layout)}")
    else:
        notify("UrOwnKeyboard", "No se pudo activar la distribución del sistema.")


def uok_lxqt_append_system_sources_to_menu(menu):
    if not uok_is_lxqt_desktop():
        return

    uok_lxqt_hide_native_input_indicators()

    rows = uok_lxqt_system_sources()

    if not rows:
        return

    menu.append(Gtk.SeparatorMenuItem())

    title = Gtk.MenuItem(label="Distribuciones del sistema")
    title.set_sensitive(False)
    menu.append(title)

    for row in rows:
        item = Gtk.MenuItem(label=row.get("label", row.get("id", "")))
        item.connect("activate", lambda _item, selected=row: uok_lxqt_apply_system_source(selected))
        menu.append(item)



# --------------------------------------------------------------------
# UOK LXQt: remove legacy tray, keep statusnotifier
# --------------------------------------------------------------------

def uok_lxqt_remove_legacy_tray_keep_statusnotifier():
    if not uok_is_lxqt_desktop():
        return

    conf = Path.home() / ".config/lxqt/panel.conf"

    if not conf.exists():
        return

    try:
        text = conf.read_text(encoding="utf-8")
    except Exception:
        return

    if "[tray]" not in text:
        return

    backup = conf.with_suffix(".conf.uok-before-remove-tray")

    try:
        if not backup.exists():
            backup.write_text(text, encoding="utf-8")
    except Exception:
        pass

    # Quitar solo el tray clásico. Mantener statusnotifier.
    new_text = re.sub(
        r"(?ms)^\[tray\]\n.*?(?=^\[[^\]]+\]\n|\Z)",
        "",
        text,
    )

    new_text = re.sub(r"\n{3,}", "\n\n", new_text).strip() + "\n"

    if new_text != text:
        try:
            conf.write_text(new_text, encoding="utf-8")
        except Exception:
            pass


def crear_menu():
    uok_lxqt_remove_legacy_tray_keep_statusnotifier()
    menu = Gtk.Menu()

    sources = get_sources()
    uok_mate_append_system_sources_to_menu(menu)
    uok_cinnamon_append_system_sources_to_menu(menu)
    uok_lxqt_append_system_sources_to_menu(menu)

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

# --------------------------------------------------------------------

try:
    __uok_mate_base_abrir_ajustes_teclado = abrir_ajustes_teclado
except Exception:
    def __uok_mate_base_abrir_ajustes_teclado(_item=None):
        notify("UrOwnKeyboard", "No se pudo abrir la configuración de teclado del sistema.")


def uok_mate_settings_is_mate():
    desktop = " ".join([
        os.environ.get("XDG_CURRENT_DESKTOP", ""),
        os.environ.get("DESKTOP_SESSION", ""),
        os.environ.get("XDG_SESSION_DESKTOP", ""),
    ]).lower()

    return "mate" in desktop


def abrir_ajustes_teclado(_item=None):
    if not uok_mate_settings_is_mate():
        return __uok_mate_base_abrir_ajustes_teclado(_item)

    commands = [
        ["mate-keyboard-properties"],
        ["mate-control-center"],
    ]

    for cmd in commands:
        try:
            check = subprocess.run(
                ["bash", "-lc", "command -v " + shlex.quote(cmd[0])],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=menu_env(),
            )

            if check.returncode != 0:
                continue

            shell_cmd = (
                " ".join(shlex.quote(x) for x in cmd)
                + "; "
                + "pkill -f teclado-indicador.py 2>/dev/null || true; "
                + "$HOME/.local/bin/teclado-indicador.py >/dev/null 2>&1 &"
            )

            subprocess.Popen(
                ["bash", "-lc", shell_cmd],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                env=menu_env(),
            )
            return

        except Exception:
            continue

    notify("UrOwnKeyboard", "No se pudo abrir la configuración de teclado de MATE.")


indicator = AppIndicator3.Indicator.new(
    "teclado-custom",
    "input-keyboard",
    AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
)

indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
indicator.set_title("Keyboard")

ocultar_menu_xfce()

# --------------------------------------------------------------------
# UOK desktop compatibility overrides: XFCE input sources
# --------------------------------------------------------------------
# Este bloque está colocado al final para no romper GNOME:
# - En GNOME se mantienen gsettings + extensión GNOME.
# - En XFCE se leen layouts desde XFCE/setxkbmap.
# - En XFCE se oculta el plugin nativo de teclado del panel si existe.

def uok_desktop_name():
    return ":".join([
        os.environ.get("XDG_CURRENT_DESKTOP", ""),
        os.environ.get("DESKTOP_SESSION", ""),
    ]).lower()


def uok_is_xfce():
    return "xfce" in uok_desktop_name()


def uok_is_gnome():
    return "gnome" in uok_desktop_name()


def uok_split_csv(value):
    return [x.strip() for x in (value or "").split(",") if x.strip()]


def uok_source_id_from_layout_variant(layout, variant=""):
    layout = (layout or "").strip()
    variant = (variant or "").strip()

    if not layout:
        return ""

    return f"{layout}+{variant}" if variant else layout


def uok_unique_sources(sources):
    out = []
    seen = set()

    for source in sources:
        if len(source) != 2:
            continue

        source_type, source_id = source

        if not source_id:
            continue

        key = (source_type, source_id)

        if key in seen:
            continue

        seen.add(key)
        out.append(key)

    return out


def uok_parse_setxkbmap_sources():
    result = run_menu_cmd(["setxkbmap", "-query"])
    if result.returncode != 0:
        return []

    layouts = []
    variants = []

    for line in result.stdout.splitlines():
        clean = line.strip()

        if clean.startswith("layout:"):
            layouts = uok_split_csv(clean.split(":", 1)[1].strip())
        elif clean.startswith("variant:"):
            raw_variants = clean.split(":", 1)[1].strip()
            variants = [x.strip() for x in raw_variants.split(",")]

    while len(variants) < len(layouts):
        variants.append("")

    sources = []

    for layout, variant in zip(layouts, variants):
        source_id = uok_source_id_from_layout_variant(layout, variant)
        if source_id:
            sources.append(("xkb", source_id))

    return uok_unique_sources(sources)


def uok_xfconf_get(prop):
    result = run_menu_cmd(["xfconf-query", "-c", "keyboard-layout", "-p", prop])
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def uok_parse_xfce_keyboard_sources():
    layouts = uok_split_csv(uok_xfconf_get("/Default/XkbLayout"))
    variants_raw = uok_xfconf_get("/Default/XkbVariant")
    variants = [x.strip() for x in variants_raw.split(",")] if variants_raw else []

    while len(variants) < len(layouts):
        variants.append("")

    sources = []

    for layout, variant in zip(layouts, variants):
        source_id = uok_source_id_from_layout_variant(layout, variant)
        if source_id:
            sources.append(("xkb", source_id))

    return uok_unique_sources(sources)


def uok_parse_gnome_sources():
    try:
        raw = sh("gsettings get org.gnome.desktop.input-sources sources")
        return ast.literal_eval(raw)
    except Exception:
        return []


def get_sources():
    if uok_is_xfce():
        # Prioridad en XFCE:
        # 1. setxkbmap si ya tiene varios layouts activos, porque refleja lo que realmente se está usando.
        # 2. xfconf si XFCE tiene layouts configurados.
        # 3. setxkbmap como fallback.
        active_sources = uok_parse_setxkbmap_sources()
        xfce_sources = uok_parse_xfce_keyboard_sources()

        if len(active_sources) >= 2:
            return active_sources

        if xfce_sources:
            return xfce_sources

        return active_sources

    # En GNOME mantenemos el comportamiento anterior.
    return uok_parse_gnome_sources()


def aplicar_gnome_source_sync(index):
    # En XFCE no existe org.gnome.desktop.input-sources como fuente fiable.
    # El cambio real se hace después con setxkbmap en aplicar_xkb_source_sync().
    if uok_is_xfce():
        return True

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
        "desktop": "xfce" if uok_is_xfce() else "gnome" if uok_is_gnome() else "xkb",
        "keyd_conf": None,
    }

    CURRENT_PROFILE.write_text(
        json.dumps(current, indent=2, ensure_ascii=False)
    )

    notify("Keyboard", label + " activated")


def get_gnome_current_source():
    # En XFCE devolvemos la primera fuente XKB conocida para que la sincronización
    # inicial no dependa de gsettings de GNOME.
    if uok_is_xfce():
        sources = get_sources()
        if not sources:
            return None

        source_type, source_id = sources[0]

        return {
            "index": 0,
            "source_type": source_type,
            "source_id": source_id,
            "name": source_label(source_type, source_id),
        }

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


def uok_xfce_keyboard_plugin_ids():
    result = run_menu_cmd(["xfconf-query", "-c", "xfce4-panel", "-l"])
    if result.returncode != 0:
        return []

    plugin_ids = []

    for line in result.stdout.splitlines():
        prop = line.strip()
        m = re.fullmatch(r"/plugins/plugin-(\d+)", prop)
        if not m:
            continue

        plugin_id = m.group(1)

        name = run_menu_cmd([
            "xfconf-query",
            "-c",
            "xfce4-panel",
            "-p",
            f"/plugins/plugin-{plugin_id}",
        ])

        if name.returncode != 0:
            continue

        plugin_name = name.stdout.strip().lower()

        if plugin_name in {"xkb", "keyboard-layouts", "keyboard-layout"}:
            plugin_ids.append(int(plugin_id))

    return plugin_ids


def uok_xfce_panel_array(prop):
    result = run_menu_cmd(["xfconf-query", "-c", "xfce4-panel", "-p", prop])
    if result.returncode != 0:
        return []

    values = []

    for line in result.stdout.splitlines():
        line = line.strip()

        if not line:
            continue

        # xfconf puede imprimir:
        #   1
        #   2
        # o:
        #   Value[0]: 1
        m = re.search(r"(-?\d+)\s*$", line)
        if m:
            values.append(int(m.group(1)))

    return values


def uok_xfce_set_panel_array(prop, values):
    cmd = [
        "xfconf-query",
        "-c",
        "xfce4-panel",
        "-p",
        prop,
        "--force-array",
    ]

    for value in values:
        cmd.extend(["-t", "int", "-s", str(value)])

    result = run_menu_cmd(cmd)
    return result.returncode == 0


def ocultar_menu_xfce():
    if not uok_is_xfce():
        return

    plugin_ids = set(uok_xfce_keyboard_plugin_ids())

    if not plugin_ids:
        return

    result = run_menu_cmd(["xfconf-query", "-c", "xfce4-panel", "-l"])
    if result.returncode != 0:
        return

    changed = False

    for line in result.stdout.splitlines():
        prop = line.strip()

        if not re.fullmatch(r"/panels/panel-\d+/plugin-ids", prop):
            continue

        current = uok_xfce_panel_array(prop)

        if not current:
            continue

        new_values = [x for x in current if x not in plugin_ids]

        if new_values != current:
            if uok_xfce_set_panel_array(prop, new_values):
                changed = True

    if changed:
        run_menu_cmd(["xfce4-panel", "-r"])
        notify("UrOwnKeyboard", "XFCE keyboard layout indicator hidden")


# --------------------------------------------------------------------
# UOK desktop compatibility overrides: XFCE input sources v2
# --------------------------------------------------------------------
# En GNOME se mantiene gsettings.
# En XFCE se leen layouts desde:
# - setxkbmap -query
# - xfconf keyboard-layout
# - configuración del plugin xfce4-xkb-plugin del panel
# Además se intenta ocultar el plugin nativo de XFCE.

def uok_desktop_name():
    return ":".join([
        os.environ.get("XDG_CURRENT_DESKTOP", ""),
        os.environ.get("DESKTOP_SESSION", ""),
    ]).lower()


def uok_is_xfce():
    return "xfce" in uok_desktop_name()


def uok_is_gnome():
    return "gnome" in uok_desktop_name()


def uok_split_csv_keep_empty(value):
    return [x.strip() for x in (value or "").split(",")]


def uok_split_csv_nonempty(value):
    return [x.strip() for x in (value or "").split(",") if x.strip()]


def uok_source_id_from_layout_variant(layout, variant=""):
    layout = (layout or "").strip()
    variant = (variant or "").strip()

    if not layout:
        return ""

    return f"{layout}+{variant}" if variant else layout


def uok_unique_sources(sources):
    out = []
    seen = set()

    for source in sources:
        if len(source) != 2:
            continue

        source_type, source_id = source
        source_type = (source_type or "").strip()
        source_id = (source_id or "").strip()

        if source_type != "xkb" or not source_id:
            continue

        key = (source_type, source_id)

        if key in seen:
            continue

        seen.add(key)
        out.append(key)

    return out


def uok_parse_setxkbmap_sources():
    result = run_menu_cmd(["setxkbmap", "-query"])
    if result.returncode != 0:
        return []

    layouts = []
    variants = []

    for line in result.stdout.splitlines():
        clean = line.strip()

        if clean.startswith("layout:"):
            layouts = uok_split_csv_nonempty(clean.split(":", 1)[1].strip())
        elif clean.startswith("variant:"):
            variants = uok_split_csv_keep_empty(clean.split(":", 1)[1].strip())

    while len(variants) < len(layouts):
        variants.append("")

    sources = []

    for layout, variant in zip(layouts, variants):
        source_id = uok_source_id_from_layout_variant(layout, variant)
        if source_id:
            sources.append(("xkb", source_id))

    return uok_unique_sources(sources)


def uok_xfconf_get(channel, prop):
    result = run_menu_cmd(["xfconf-query", "-c", channel, "-p", prop])
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def uok_xfconf_list(channel):
    result = run_menu_cmd(["xfconf-query", "-c", channel, "-l"])
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def uok_parse_xfce_keyboard_sources():
    layouts = uok_split_csv_nonempty(
        uok_xfconf_get("keyboard-layout", "/Default/XkbLayout")
    )
    variants = uok_split_csv_keep_empty(
        uok_xfconf_get("keyboard-layout", "/Default/XkbVariant")
    )

    while len(variants) < len(layouts):
        variants.append("")

    sources = []

    for layout, variant in zip(layouts, variants):
        source_id = uok_source_id_from_layout_variant(layout, variant)
        if source_id:
            sources.append(("xkb", source_id))

    return uok_unique_sources(sources)


def uok_xfce_plugin_ids():
    props = uok_xfconf_list("xfce4-panel")
    ids = []

    for prop in props:
        m = re.fullmatch(r"/plugins/plugin-(\d+)", prop)
        if not m:
            continue

        plugin_id = m.group(1)
        name = uok_xfconf_get("xfce4-panel", f"/plugins/plugin-{plugin_id}")
        name_l = name.strip().lower()

        if (
            "xkb" in name_l
            or "keyboard-layout" in name_l
            or "keyboard layouts" in name_l
        ):
            ids.append(int(plugin_id))

    return ids


def uok_xfconf_values(channel, prop):
    result = run_menu_cmd(["xfconf-query", "-c", channel, "-p", prop])
    if result.returncode != 0:
        return []

    values = []

    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue

        # Formatos típicos:
        # Value[0]: es
        # Value[1]: de
        # es,de
        # es
        if ":" in line:
            line = line.split(":", 1)[1].strip()

        for part in line.split(","):
            part = part.strip()
            if part:
                values.append(part)

    return values


def uok_parse_xfce_panel_xkb_plugin_sources():
    sources = []

    for plugin_id in uok_xfce_plugin_ids():
        prefix = f"/plugins/plugin-{plugin_id}"
        props = [
            prop for prop in uok_xfconf_list("xfce4-panel")
            if prop == prefix or prop.startswith(prefix + "/")
        ]

        layout_values = []
        variant_values = []

        for prop in props:
            low = prop.lower()

            if "layout" in low and not low.endswith("display-name"):
                layout_values.extend(uok_xfconf_values("xfce4-panel", prop))

            if "variant" in low:
                variant_values.extend(uok_xfconf_values("xfce4-panel", prop))

        # Limpieza: quedarse con códigos tipo es, us, de, fr, us+intl...
        layouts = []
        for value in layout_values:
            value = value.strip()
            if re.fullmatch(r"[a-z]{2,3}([+_][A-Za-z0-9_-]+)?", value):
                layouts.append(value.replace("_", "+"))

        variants = []
        for value in variant_values:
            value = value.strip()
            if re.fullmatch(r"[A-Za-z0-9_-]*", value):
                variants.append(value)

        while len(variants) < len(layouts):
            variants.append("")

        for layout, variant in zip(layouts, variants):
            if "+" in layout:
                source_id = layout
            else:
                source_id = uok_source_id_from_layout_variant(layout, variant)

            if source_id:
                sources.append(("xkb", source_id))

    return uok_unique_sources(sources)


def uok_parse_gnome_sources():
    try:
        raw = sh("gsettings get org.gnome.desktop.input-sources sources")
        return ast.literal_eval(raw)
    except Exception:
        return []


def get_sources():
    if uok_is_xfce():
        sources = []

        # Unimos todas las fuentes conocidas. Esto corrige el caso:
        # setxkbmap muestra es/us, pero el plugin XFCE muestra es/de.
        sources.extend(uok_parse_xfce_panel_xkb_plugin_sources())
        sources.extend(uok_parse_xfce_keyboard_sources())
        sources.extend(uok_parse_setxkbmap_sources())

        return uok_unique_sources(sources)

    return uok_parse_gnome_sources()


def aplicar_gnome_source_sync(index):
    if uok_is_xfce():
        return True

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
        "desktop": "xfce" if uok_is_xfce() else "gnome" if uok_is_gnome() else "xkb",
        "keyd_conf": None,
    }

    CURRENT_PROFILE.write_text(
        json.dumps(current, indent=2, ensure_ascii=False)
    )

    notify("Keyboard", label + " activated")


def get_gnome_current_source():
    if uok_is_xfce():
        sources = get_sources()
        if not sources:
            return None

        source_type, source_id = sources[0]

        return {
            "index": 0,
            "source_type": source_type,
            "source_id": source_id,
            "name": source_label(source_type, source_id),
        }

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


def uok_xfce_panel_array(prop):
    result = run_menu_cmd(["xfconf-query", "-c", "xfce4-panel", "-p", prop])
    if result.returncode != 0:
        return []

    values = []

    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue

        m = re.search(r"(-?\d+)\s*$", line)
        if m:
            values.append(int(m.group(1)))

    return values


def uok_xfce_set_panel_array(prop, values):
    cmd = [
        "xfconf-query",
        "-c", "xfce4-panel",
        "-p", prop,
        "--force-array",
    ]

    for value in values:
        cmd.extend(["-t", "int", "-s", str(value)])

    result = run_menu_cmd(cmd)
    return result.returncode == 0


def ocultar_menu_xfce():
    if not uok_is_xfce():
        return

    plugin_ids = set(uok_xfce_plugin_ids())

    if not plugin_ids:
        return

    changed = False

    for prop in uok_xfconf_list("xfce4-panel"):
        if not re.fullmatch(r"/panels/panel-\d+/plugin-ids", prop):
            continue

        current = uok_xfce_panel_array(prop)
        if not current:
            continue

        new_values = [x for x in current if x not in plugin_ids]

        if new_values != current:
            if uok_xfce_set_panel_array(prop, new_values):
                changed = True

    if changed:
        run_menu_cmd(["xfce4-panel", "-r"])
        notify("UrOwnKeyboard", "XFCE keyboard layout indicator hidden")


# --------------------------------------------------------------------
# UOK desktop compatibility overrides: XFCE input sources v3
# --------------------------------------------------------------------
# GNOME queda igual: gsettings.
# XFCE lee:
# - ~/.config/xfce4/panel/xkb-plugin-*.rc
# - xfconf keyboard-layout
# - setxkbmap -query
# Y oculta el plugin nativo xkb-plugin-N del panel.

def uok_desktop_name():
    return ":".join([
        os.environ.get("XDG_CURRENT_DESKTOP", ""),
        os.environ.get("DESKTOP_SESSION", ""),
    ]).lower()


def uok_is_xfce():
    return "xfce" in uok_desktop_name()


def uok_is_gnome():
    return "gnome" in uok_desktop_name()


def uok_split_csv_keep_empty(value):
    return [x.strip() for x in (value or "").split(",")]


def uok_split_csv_nonempty(value):
    return [x.strip() for x in (value or "").split(",") if x.strip()]


def uok_source_id_from_layout_variant(layout, variant=""):
    layout = (layout or "").strip()
    variant = (variant or "").strip()

    if not layout:
        return ""

    return f"{layout}+{variant}" if variant else layout


def uok_unique_sources(sources):
    out = []
    seen = set()

    for source in sources:
        if len(source) != 2:
            continue

        source_type, source_id = source
        source_type = (source_type or "").strip()
        source_id = (source_id or "").strip()

        if source_type != "xkb" or not source_id:
            continue

        key = (source_type, source_id)

        if key in seen:
            continue

        seen.add(key)
        out.append(key)

    return out


def uok_parse_setxkbmap_sources():
    result = run_menu_cmd(["setxkbmap", "-query"])
    if result.returncode != 0:
        return []

    layouts = []
    variants = []

    for line in result.stdout.splitlines():
        clean = line.strip()

        if clean.startswith("layout:"):
            layouts = uok_split_csv_nonempty(clean.split(":", 1)[1].strip())
        elif clean.startswith("variant:"):
            variants = uok_split_csv_keep_empty(clean.split(":", 1)[1].strip())

    while len(variants) < len(layouts):
        variants.append("")

    sources = []

    for layout, variant in zip(layouts, variants):
        source_id = uok_source_id_from_layout_variant(layout, variant)
        if source_id:
            sources.append(("xkb", source_id))

    return uok_unique_sources(sources)


def uok_xfconf_get(channel, prop):
    result = run_menu_cmd(["xfconf-query", "-c", channel, "-p", prop])
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def uok_xfconf_list(channel):
    result = run_menu_cmd(["xfconf-query", "-c", channel, "-l"])
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def uok_parse_xfce_keyboard_sources():
    layouts = uok_split_csv_nonempty(
        uok_xfconf_get("keyboard-layout", "/Default/XkbLayout")
    )
    variants = uok_split_csv_keep_empty(
        uok_xfconf_get("keyboard-layout", "/Default/XkbVariant")
    )

    while len(variants) < len(layouts):
        variants.append("")

    sources = []

    for layout, variant in zip(layouts, variants):
        source_id = uok_source_id_from_layout_variant(layout, variant)
        if source_id:
            sources.append(("xkb", source_id))

    return uok_unique_sources(sources)


def uok_xkb_plugin_rc_files():
    panel_dir = HOME / ".config" / "xfce4" / "panel"
    if not panel_dir.exists():
        return []

    return sorted(panel_dir.glob("xkb-plugin-*.rc"))


def uok_xkb_plugin_ids_from_rc():
    ids = []

    for file in uok_xkb_plugin_rc_files():
        m = re.fullmatch(r"xkb-plugin-(\d+)\.rc", file.name)
        if m:
            ids.append(int(m.group(1)))

    return ids


def uok_parse_xkb_plugin_rc_file(path):
    try:
        text = Path(path).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []

    sources = []

    # Formatos habituales posibles:
    # layout=es,de
    # layouts=es,de
    # group_policy=...
    # variant=,
    # variants=,
    layouts = []
    variants = []

    for line in text.splitlines():
        clean = line.strip()

        if not clean or clean.startswith("#") or "=" not in clean:
            continue

        key, value = clean.split("=", 1)
        key = key.strip().lower()
        value = value.strip()

        if key in {"layout", "layouts", "kbd_layouts", "model_layouts"}:
            layouts.extend(uok_split_csv_nonempty(value))

        if key in {"variant", "variants", "kbd_variants", "model_variants"}:
            variants.extend(uok_split_csv_keep_empty(value))

    # Rescate genérico: busca códigos tras claves que contengan layout.
    if not layouts:
        for m in re.finditer(r"(?im)^\s*[^=\n]*layout[^=\n]*=\s*([^\n]+)$", text):
            layouts.extend(uok_split_csv_nonempty(m.group(1).strip()))

    if not variants:
        for m in re.finditer(r"(?im)^\s*[^=\n]*variant[^=\n]*=\s*([^\n]+)$", text):
            variants.extend(uok_split_csv_keep_empty(m.group(1).strip()))

    clean_layouts = []

    for value in layouts:
        value = value.strip()

        # A veces puede venir como "es\tSpanish" o "es Spanish".
        value = value.split()[0] if value.split() else value

        if re.fullmatch(r"[a-z]{2,3}([+_][A-Za-z0-9_-]+)?", value):
            clean_layouts.append(value.replace("_", "+"))

    clean_variants = []

    for value in variants:
        value = value.strip()
        value = value.split()[0] if value.split() else value

        if re.fullmatch(r"[A-Za-z0-9_-]*", value):
            clean_variants.append(value)

    while len(clean_variants) < len(clean_layouts):
        clean_variants.append("")

    for layout, variant in zip(clean_layouts, clean_variants):
        if "+" in layout:
            source_id = layout
        else:
            source_id = uok_source_id_from_layout_variant(layout, variant)

        if source_id:
            sources.append(("xkb", source_id))

    return uok_unique_sources(sources)


def uok_parse_xkb_plugin_rc_sources():
    sources = []

    for file in uok_xkb_plugin_rc_files():
        sources.extend(uok_parse_xkb_plugin_rc_file(file))

    return uok_unique_sources(sources)


def uok_parse_gnome_sources():
    try:
        raw = sh("gsettings get org.gnome.desktop.input-sources sources")
        return ast.literal_eval(raw)
    except Exception:
        return []


def get_sources():
    if uok_is_xfce():
        sources = []

        # Prioridad: lo que muestra el propio menú nativo de XFCE.
        sources.extend(uok_parse_xkb_plugin_rc_sources())

        # Después, la configuración de teclado XFCE.
        sources.extend(uok_parse_xfce_keyboard_sources())

        # Finalmente, el XKB activo real.
        sources.extend(uok_parse_setxkbmap_sources())

        return uok_unique_sources(sources)

    return uok_parse_gnome_sources()


def aplicar_gnome_source_sync(index):
    if uok_is_xfce():
        return True

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
        "desktop": "xfce" if uok_is_xfce() else "gnome" if uok_is_gnome() else "xkb",
        "keyd_conf": None,
    }

    CURRENT_PROFILE.write_text(
        json.dumps(current, indent=2, ensure_ascii=False)
    )

    notify("Keyboard", label + " activated")


def get_gnome_current_source():
    if uok_is_xfce():
        sources = get_sources()
        if not sources:
            return None

        source_type, source_id = sources[0]

        return {
            "index": 0,
            "source_type": source_type,
            "source_id": source_id,
            "name": source_label(source_type, source_id),
        }

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


def uok_xfce_panel_array(prop):
    result = run_menu_cmd(["xfconf-query", "-c", "xfce4-panel", "-p", prop])
    if result.returncode != 0:
        return []

    values = []

    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue

        m = re.search(r"(-?\d+)\s*$", line)
        if m:
            values.append(int(m.group(1)))

    return values


def uok_xfce_set_panel_array(prop, values):
    cmd = [
        "xfconf-query",
        "-c", "xfce4-panel",
        "-p", prop,
        "--force-array",
    ]

    for value in values:
        cmd.extend(["-t", "int", "-s", str(value)])

    result = run_menu_cmd(cmd)
    return result.returncode == 0


def ocultar_menu_xfce():
    if not uok_is_xfce():
        return

    plugin_ids = set(uok_xkb_plugin_ids_from_rc())

    # También detecta plugin xkb si xfconf lo declara directamente.
    for prop in uok_xfconf_list("xfce4-panel"):
        m = re.fullmatch(r"/plugins/plugin-(\d+)", prop)
        if not m:
            continue

        plugin_id = int(m.group(1))
        name = uok_xfconf_get("xfce4-panel", prop).lower()

        if "xkb" in name or "keyboard-layout" in name or "keyboard layouts" in name:
            plugin_ids.add(plugin_id)

    if not plugin_ids:
        return

    changed = False

    for prop in uok_xfconf_list("xfce4-panel"):
        if not re.fullmatch(r"/panels/panel-\d+/plugin-ids", prop):
            continue

        current = uok_xfce_panel_array(prop)
        if not current:
            continue

        new_values = [x for x in current if x not in plugin_ids]

        if new_values != current:
            if uok_xfce_set_panel_array(prop, new_values):
                changed = True

    if changed:
        run_menu_cmd(["xfce4-panel", "-r"])
        notify("UrOwnKeyboard", "XFCE keyboard layout indicator hidden")


# --------------------------------------------------------------------
# UOK XFCE compatibility override v5
# --------------------------------------------------------------------
# GNOME:
#   - conserva gsettings org.gnome.desktop.input-sources.
#
# XFCE:
#   - muestra en UOK la unión de:
#       1. XFCE keyboard-layout
#       2. setxkbmap activo
#       3. GNOME/IBus input-sources, si existen
#   - oculta del systray los indicadores nativos de IBus:
#       ibus-ui-gtk3
#       panel ibus
#
# Esto no desinstala nada y no cambia GNOME.

def uok_v5_desktop_name():
    return ":".join([
        os.environ.get("XDG_CURRENT_DESKTOP", ""),
        os.environ.get("DESKTOP_SESSION", ""),
    ]).lower()


def uok_v5_is_xfce():
    return "xfce" in uok_v5_desktop_name()


def uok_v5_is_gnome():
    return "gnome" in uok_v5_desktop_name()


def uok_v5_run(cmd):
    try:
        return subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=menu_env(),
        )
    except Exception as exc:
        return subprocess.CompletedProcess(cmd, 1, "", str(exc))


def uok_v5_split_nonempty(value):
    return [x.strip() for x in (value or "").split(",") if x.strip()]


def uok_v5_split_keep_empty(value):
    return [x.strip() for x in (value or "").split(",")]


def uok_v5_source_id(layout, variant=""):
    layout = (layout or "").strip()
    variant = (variant or "").strip()

    if not layout:
        return ""

    return f"{layout}+{variant}" if variant else layout


def uok_v5_unique_sources(sources):
    out = []
    seen = set()

    for item in sources:
        if len(item) != 2:
            continue

        source_type, source_id = item
        source_type = (source_type or "").strip()
        source_id = (source_id or "").strip()

        if source_type != "xkb" or not source_id:
            continue

        key = (source_type, source_id)

        if key in seen:
            continue

        seen.add(key)
        out.append(key)

    return out


def uok_v5_gnome_sources():
    try:
        raw = sh("gsettings get org.gnome.desktop.input-sources sources")
        parsed = ast.literal_eval(raw)
    except Exception:
        return []

    return uok_v5_unique_sources([
        item for item in parsed
        if len(item) == 2 and item[0] == "xkb"
    ])


def uok_v5_xfconf_get(channel, prop):
    result = uok_v5_run(["xfconf-query", "-c", channel, "-p", prop])
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def uok_v5_xfconf_list(channel):
    result = uok_v5_run(["xfconf-query", "-c", channel, "-l"])
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def uok_v5_sources_from_keyboard_layout():
    layouts = uok_v5_split_nonempty(
        uok_v5_xfconf_get("keyboard-layout", "/Default/XkbLayout")
    )
    variants = uok_v5_split_keep_empty(
        uok_v5_xfconf_get("keyboard-layout", "/Default/XkbVariant")
    )

    while len(variants) < len(layouts):
        variants.append("")

    out = []

    for layout, variant in zip(layouts, variants):
        source_id = uok_v5_source_id(layout, variant)
        if source_id:
            out.append(("xkb", source_id))

    return uok_v5_unique_sources(out)


def uok_v5_sources_from_setxkbmap():
    result = uok_v5_run(["setxkbmap", "-query"])
    if result.returncode != 0:
        return []

    layouts = []
    variants = []

    for line in result.stdout.splitlines():
        clean = line.strip()

        if clean.startswith("layout:"):
            layouts = uok_v5_split_nonempty(clean.split(":", 1)[1].strip())
        elif clean.startswith("variant:"):
            variants = uok_v5_split_keep_empty(clean.split(":", 1)[1].strip())

    while len(variants) < len(layouts):
        variants.append("")

    out = []

    for layout, variant in zip(layouts, variants):
        source_id = uok_v5_source_id(layout, variant)
        if source_id:
            out.append(("xkb", source_id))

    return uok_v5_unique_sources(out)


def get_sources():
    if uok_v5_is_xfce():
        sources = []
        sources.extend(uok_v5_sources_from_keyboard_layout())
        sources.extend(uok_v5_sources_from_setxkbmap())
        sources.extend(uok_v5_gnome_sources())
        return uok_v5_unique_sources(sources)

    return uok_v5_gnome_sources()


def aplicar_gnome_source_sync(index):
    if uok_v5_is_xfce():
        return True

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
        "desktop": "xfce" if uok_v5_is_xfce() else "gnome" if uok_v5_is_gnome() else "xkb",
        "keyd_conf": None,
    }

    CURRENT_PROFILE.write_text(
        json.dumps(current, indent=2, ensure_ascii=False)
    )

    notify("Keyboard", label + " activated")


def get_gnome_current_source():
    sources = get_sources()

    if not sources:
        return None

    if uok_v5_is_xfce():
        source_type, source_id = sources[0]

        return {
            "index": 0,
            "source_type": source_type,
            "source_id": source_id,
            "name": source_label(source_type, source_id),
        }

    try:
        current_raw = sh("gsettings get org.gnome.desktop.input-sources current")
        current = int(str(current_raw).replace("uint32", "").strip())
    except Exception:
        current = 0

    if current < 0 or current >= len(sources):
        current = 0

    source_type, source_id = sources[current]

    return {
        "index": current,
        "source_type": source_type,
        "source_id": source_id,
        "name": source_label(source_type, source_id),
    }


def uok_v5_xfconf_array_values(channel, prop):
    result = uok_v5_run(["xfconf-query", "-c", channel, "-p", prop])
    if result.returncode != 0:
        return []

    values = []

    for line in result.stdout.splitlines():
        line = line.strip()

        if not line:
            continue

        if ":" in line:
            line = line.split(":", 1)[1].strip()

        if line.startswith("El valor es un vector"):
            continue

        for part in line.split(","):
            part = part.strip()
            if part:
                values.append(part)

    return values


def uok_v5_set_xfconf_string_array(channel, prop, values):
    values = [v for v in values if v]

    if not values:
        return False

    cmd = [
        "xfconf-query",
        "-c", channel,
        "-p", prop,
        "--create",
        "--force-array",
    ]

    for value in values:
        cmd.extend(["-t", "string", "-s", value])

    result = uok_v5_run(cmd)
    return result.returncode == 0


def uok_v5_systray_plugin_ids():
    ids = []

    for prop in uok_v5_xfconf_list("xfce4-panel"):
        m = re.fullmatch(r"/plugins/plugin-(\d+)", prop)
        if not m:
            continue

        plugin_id = m.group(1)
        name = uok_v5_xfconf_get("xfce4-panel", prop).strip().lower()

        if name in {"systray", "statusnotifier", "notification-plugin"}:
            ids.append(plugin_id)

    return ids


def ocultar_menu_xfce():
    if not uok_v5_is_xfce():
        return

    # En esta sesión el indicador nativo aparece como legacy systray item:
    # ibus-ui-gtk3 / panel ibus.
    native_items = [
        "ibus-ui-gtk3",
        "panel ibus",
        "indicator-keyboard",
        "indicator-keyboard-service",
    ]

    changed = False

    for plugin_id in uok_v5_systray_plugin_ids():
        for prop_name in ["hidden-legacy-items", "hidden-items"]:
            prop = f"/plugins/plugin-{plugin_id}/{prop_name}"
            current = uok_v5_xfconf_array_values("xfce4-panel", prop)

            merged = []
            seen = set()

            for item in current + native_items:
                if item not in seen:
                    seen.add(item)
                    merged.append(item)

            if merged != current:
                if uok_v5_set_xfconf_string_array("xfce4-panel", prop, merged):
                    changed = True

    if changed:
        uok_v5_run(["xfce4-panel", "-r"])
        notify("UrOwnKeyboard", "XFCE native keyboard indicator hidden")


# --------------------------------------------------------------------
# UOK XFCE compatibility override v6: read IBus keyboard sources
# --------------------------------------------------------------------
# GNOME queda igual.
# XFCE muestra la unión de:
# - XFCE keyboard-layout
# - setxkbmap
# - GNOME input-sources, si existen
# - IBus preload-engines / engines-order
#
# Esto cubre el caso en que el menú nativo ocultado mostraba German/Alemán
# desde IBus o indicator-keyboard.

def uok_v6_desktop_name():
    return ":".join([
        os.environ.get("XDG_CURRENT_DESKTOP", ""),
        os.environ.get("DESKTOP_SESSION", ""),
    ]).lower()


def uok_v6_is_xfce():
    return "xfce" in uok_v6_desktop_name()


def uok_v6_is_gnome():
    return "gnome" in uok_v6_desktop_name()


def uok_v6_run(cmd):
    try:
        return subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=menu_env(),
        )
    except Exception as exc:
        return subprocess.CompletedProcess(cmd, 1, "", str(exc))


def uok_v6_split_nonempty(value):
    return [x.strip() for x in (value or "").split(",") if x.strip()]


def uok_v6_split_keep_empty(value):
    return [x.strip() for x in (value or "").split(",")]


def uok_v6_source_id(layout, variant=""):
    layout = (layout or "").strip()
    variant = (variant or "").strip()

    if not layout:
        return ""

    return f"{layout}+{variant}" if variant else layout


def uok_v6_unique_sources(sources):
    out = []
    seen = set()

    for item in sources:
        if len(item) != 2:
            continue

        source_type, source_id = item
        source_type = (source_type or "").strip()
        source_id = (source_id or "").strip()

        if source_type != "xkb" or not source_id:
            continue

        key = (source_type, source_id)

        if key in seen:
            continue

        seen.add(key)
        out.append(key)

    return out


def uok_v6_gnome_sources():
    try:
        raw = sh("gsettings get org.gnome.desktop.input-sources sources")
        parsed = ast.literal_eval(raw)
    except Exception:
        return []

    return uok_v6_unique_sources([
        item for item in parsed
        if len(item) == 2 and item[0] == "xkb"
    ])


def uok_v6_xfconf_get(channel, prop):
    result = uok_v6_run(["xfconf-query", "-c", channel, "-p", prop])
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def uok_v6_sources_from_keyboard_layout():
    layouts = uok_v6_split_nonempty(
        uok_v6_xfconf_get("keyboard-layout", "/Default/XkbLayout")
    )
    variants = uok_v6_split_keep_empty(
        uok_v6_xfconf_get("keyboard-layout", "/Default/XkbVariant")
    )

    while len(variants) < len(layouts):
        variants.append("")

    out = []

    for layout, variant in zip(layouts, variants):
        source_id = uok_v6_source_id(layout, variant)
        if source_id:
            out.append(("xkb", source_id))

    return uok_v6_unique_sources(out)


def uok_v6_sources_from_setxkbmap():
    result = uok_v6_run(["setxkbmap", "-query"])
    if result.returncode != 0:
        return []

    layouts = []
    variants = []

    for line in result.stdout.splitlines():
        clean = line.strip()

        if clean.startswith("layout:"):
            layouts = uok_v6_split_nonempty(clean.split(":", 1)[1].strip())
        elif clean.startswith("variant:"):
            variants = uok_v6_split_keep_empty(clean.split(":", 1)[1].strip())

    while len(variants) < len(layouts):
        variants.append("")

    out = []

    for layout, variant in zip(layouts, variants):
        source_id = uok_v6_source_id(layout, variant)
        if source_id:
            out.append(("xkb", source_id))

    return uok_v6_unique_sources(out)


def uok_v6_ibus_engine_to_source_id(engine):
    engine = (engine or "").strip()

    # Ejemplos:
    # xkb:es::spa
    # xkb:de::ger
    # xkb:us::eng
    # xkb:us:intl:eng
    if not engine.startswith("xkb:"):
        return ""

    parts = engine.split(":")
    if len(parts) < 2:
        return ""

    layout = parts[1].strip()
    variant = ""

    if len(parts) >= 3:
        variant = parts[2].strip()

    if not layout:
        return ""

    return uok_v6_source_id(layout, variant)


def uok_v6_sources_from_ibus():
    out = []

    keys = [
        "preload-engines",
        "engines-order",
    ]

    for key in keys:
        result = uok_v6_run([
            "gsettings",
            "get",
            "org.freedesktop.ibus.general",
            key,
        ])

        if result.returncode != 0:
            continue

        try:
            engines = ast.literal_eval(result.stdout.strip())
        except Exception:
            engines = re.findall(r"'([^']+)'", result.stdout)

        for engine in engines:
            source_id = uok_v6_ibus_engine_to_source_id(engine)
            if source_id:
                out.append(("xkb", source_id))

    return uok_v6_unique_sources(out)


def get_sources():
    if uok_v6_is_xfce():
        sources = []
        sources.extend(uok_v6_sources_from_keyboard_layout())
        sources.extend(uok_v6_sources_from_setxkbmap())
        sources.extend(uok_v6_gnome_sources())
        sources.extend(uok_v6_sources_from_ibus())
        return uok_v6_unique_sources(sources)

    return uok_v6_gnome_sources()


def aplicar_gnome_source_sync(index):
    if uok_v6_is_xfce():
        return True

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
        "desktop": "xfce" if uok_v6_is_xfce() else "gnome" if uok_v6_is_gnome() else "xkb",
        "keyd_conf": None,
    }

    CURRENT_PROFILE.write_text(
        json.dumps(current, indent=2, ensure_ascii=False)
    )

    notify("Keyboard", label + " activated")


def get_gnome_current_source():
    sources = get_sources()

    if not sources:
        return None

    if uok_v6_is_xfce():
        source_type, source_id = sources[0]

        return {
            "index": 0,
            "source_type": source_type,
            "source_id": source_id,
            "name": source_label(source_type, source_id),
        }

    try:
        current_raw = sh("gsettings get org.gnome.desktop.input-sources current")
        current = int(str(current_raw).replace("uint32", "").strip())
    except Exception:
        current = 0

    if current < 0 or current >= len(sources):
        current = 0

    source_type, source_id = sources[current]

    return {
        "index": current,
        "source_type": source_type,
        "source_id": source_id,
        "name": source_label(source_type, source_id),
    }


# --------------------------------------------------------------------
# UOK desktop compatibility override: Add from settings
# --------------------------------------------------------------------
# GNOME:
#   abre gnome-control-center keyboard.
#
# XFCE:
#   abre xfce4-keyboard-settings.
#
# Cinnamon:
#   abre cinnamon-settings keyboard.
#
# KDE Plasma:
#   abre systemsettings kcm_keyboard.
#
# Fallback:
#   prueba todos sin romper el comportamiento anterior.

def uok_settings_desktop_name():
    return ":".join([
        os.environ.get("XDG_CURRENT_DESKTOP", ""),
        os.environ.get("DESKTOP_SESSION", ""),
    ]).lower()


def uok_settings_command_candidates():
    desktop = uok_settings_desktop_name()

    if "xfce" in desktop:
        return [
            ["xfce4-keyboard-settings"],
            ["xfce4-settings-manager"],
        ]

    if "gnome" in desktop or "ubuntu" in desktop:
        return [
            ["gnome-control-center", "keyboard"],
            ["gnome-control-center", "region"],
        ]

    if "cinnamon" in desktop:
        return [
            ["cinnamon-settings", "keyboard"],
            ["cinnamon-settings", "region"],
        ]

    if "kde" in desktop or "plasma" in desktop:
        return [
            ["systemsettings", "kcm_keyboard"],
            ["systemsettings5", "kcm_keyboard"],
            ["kcmshell6", "kcm_keyboard"],
            ["kcmshell5", "kcm_keyboard"],
        ]

    return [
        ["gnome-control-center", "keyboard"],
        ["xfce4-keyboard-settings"],
        ["cinnamon-settings", "keyboard"],
        ["systemsettings", "kcm_keyboard"],
        ["systemsettings5", "kcm_keyboard"],
        ["kcmshell6", "kcm_keyboard"],
        ["kcmshell5", "kcm_keyboard"],
    ]


def abrir_ajustes_teclado(_item=None):
    for cmd in uok_settings_command_candidates():
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

    notify(
        "UrOwnKeyboard",
        "No se pudo abrir la configuración de teclado del sistema."
    )


# --------------------------------------------------------------------
# UOK non-blocking errors + non-fatal keyd off override v7
# --------------------------------------------------------------------
# Aplica a todos los escritorios.
#
# Objetivo:
# - Los errores gráficos no deben bloquear el uso del sistema.
# - Si keyd falla al apagarse, no debe impedir cambiar a un teclado normal.
# - Se intenta aplicar XKB/GNOME/XFCE aunque keyd dé error.
# - keyd activo se convierte en aviso, no en bloqueo.

def uok_v7_nonblocking_dialog(kind, title, msg):
    icon = "--error" if kind == "error" else "--warning"

    try:
        subprocess.Popen(
            [
                "zenity",
                icon,
                "--title", str(title),
                "--text", str(msg),
                "--no-wrap",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            env=menu_env(),
        )
        return
    except Exception:
        pass

    try:
        subprocess.Popen(
            [
                "notify-send",
                str(title),
                str(msg),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            env=menu_env(),
        )
    except Exception:
        pass


def show_error(title, msg):
    uok_v7_nonblocking_dialog("error", title, msg)


def show_warning(title, msg):
    uok_v7_nonblocking_dialog("warning", title, msg)


def aplicar_keyd_off_sync():
    result = run_menu_cmd(["sudo", "-n", str(KEYD_HELPER), "--off"])

    if result.returncode != 0:
        msg = command_error(
            result,
            "No se pudo desactivar keyd. Se continuará aplicando el teclado XKB normal."
        )

        show_warning(
            "UrOwnKeyboard - keyd",
            msg + "\n\nSe continuará aplicando la distribución normal del sistema."
        )

        # Importante:
        # Antes devolvía False y bloqueaba el cambio al teclado por defecto.
        # Ahora no bloquea: XKB/GNOME/XFCE deben aplicarse igualmente.
        return True

    return True


def verify_gnome_source_applied(source_type, source_id):
    if source_type != "xkb":
        return True, ""

    got = raw_xkb_layout()
    expected = expected_source_spec(source_id)

    if got != expected:
        return False, (
            "XKB no cambió al layout esperado. "
            f"Esperado: {expected}. Actual: {got or 'desconocido'}."
        )

    if keyd_is_active():
        show_warning(
            "UrOwnKeyboard - keyd",
            "La distribución XKB se ha cambiado, pero keyd sigue activo. "
            "Si notas remapeos antiguos, reinicia keyd o revisa su configuración."
        )

    return True, ""


def activar_gnome_source(index, source_type, source_id):
    label = source_label(source_type, source_id)

    # No bloquea aunque keyd falle.
    aplicar_keyd_off_sync()

    if not aplicar_gnome_source_sync(index):
        return

    if not aplicar_xkb_source_sync(source_type, source_id):
        return

    ok, msg = verify_gnome_source_applied(source_type, source_id)
    if not ok:
        show_warning("UrOwnKeyboard - verificación", msg)
        # No hacemos return duro: el usuario ya intentó cambiar de teclado
        # y el error no debe dejar el menú bloqueado.

    current = {
        "type": "gnome-source",
        "name": label,
        "source_type": source_type,
        "source_id": source_id,
        "desktop": (
            "xfce"
            if "xfce" in ":".join([
                os.environ.get("XDG_CURRENT_DESKTOP", ""),
                os.environ.get("DESKTOP_SESSION", ""),
            ]).lower()
            else "gnome"
            if "gnome" in ":".join([
                os.environ.get("XDG_CURRENT_DESKTOP", ""),
                os.environ.get("DESKTOP_SESSION", ""),
            ]).lower()
            else "xkb"
        ),
        "keyd_conf": None,
    }

    CURRENT_PROFILE.write_text(
        json.dumps(current, indent=2, ensure_ascii=False)
    )

    notify("Keyboard", label + " activated")


def run_checked_for_menu(cmd, title):
    result = run_menu_cmd(cmd)

    if result.returncode != 0:
        show_error(title, command_error(result))
        return False

    return True


# --------------------------------------------------------------------
# UOK non-blocking error handling + optional keyd activation
# --------------------------------------------------------------------
# Los errores no abren diálogos modales.
# Se registran en log y se muestran como notificaciones.
# keyd no bloquea la aplicación de XKB.

def uok_nb_log_path():
    return HOME / ".cache" / "urownkeyboard" / "indicator.log"


def uok_nb_log(title, msg):
    try:
        path = uok_nb_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write("\n---- UOK warning ----\n")
            fh.write(str(title).strip() + "\n")
            fh.write(str(msg).strip() + "\n")
    except Exception:
        pass


def show_error(title, msg):
    title = str(title or "UrOwnKeyboard")
    msg = str(msg or "Unknown error")

    uok_nb_log(title, msg)

    # Notificación no bloqueante. No detiene el indicador ni captura el foco.
    try:
        subprocess.Popen(
            [
                "notify-send",
                "--app-name=UrOwnKeyboard",
                "--icon=input-keyboard",
                title,
                msg,
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=menu_env(),
            start_new_session=True,
        )
        return
    except Exception:
        pass

    # Fallback también no bloqueante si notify-send no existe.
    try:
        subprocess.Popen(
            [
                "zenity",
                "--warning",
                "--title", title,
                "--text", msg,
                "--no-wrap",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=menu_env(),
            start_new_session=True,
        )
    except Exception:
        pass


def aplicar_keyd_off_sync():
    result = run_menu_cmd(["sudo", "-n", str(KEYD_HELPER), "--off"])

    if result.returncode != 0:
        show_error(
            "UrOwnKeyboard - keyd",
            "No se pudo desactivar keyd. Se continuará aplicando XKB.\n\n"
            + command_error(result, "No se pudo desactivar keyd.")
        )
        return True

    return True


def activar_profile(profile):
    profile_id = profile.get("id")

    if not profile_id:
        show_error("UrOwnKeyboard", "Invalid imported configuration.")
        return

    uok_bin = UOK_BIN if UOK_BIN.exists() else Path("uok")

    result = run_menu_cmd([str(uok_bin), "activate", profile_id])

    combined = "\n".join(
        x.strip()
        for x in [result.stdout, result.stderr]
        if x and x.strip()
    )

    if result.returncode != 0:
        show_error(
            "UrOwnKeyboard",
            combined or "Could not activate configuration.",
        )
        return

    # Si uok pudo activar XKB pero avisó de keyd, mostramos notificación no bloqueante.
    if "WARNING:" in combined or "keyd" in result.stderr.lower():
        show_error("UrOwnKeyboard - keyd", combined)

    ok, msg = verify_uok_profile_applied(profile_id)
    if not ok:
        show_error("UrOwnKeyboard - verificación", msg)
        return

    notify("Keyboard", result.stdout.strip() or f"{profile.get('name', profile_id)} activated")


# --------------------------------------------------------------------
# UOK keyd diagnostics override
# --------------------------------------------------------------------
# Añade diagnóstico claro cuando un perfil no tiene keyd_conf o el archivo
# asociado no existe. No bloquea la aplicación del XKB.

def uok_keyd_profile_diagnostic(profile):
    if not profile:
        return "Perfil vacío."

    keyd_conf = profile.get("keyd_conf")

    if not keyd_conf:
        return (
            "Este perfil no tiene archivo keyd_conf asociado.\n"
            "Eso significa que el editor visual no importó ningún keyd.conf para esta configuración.\n\n"
            "Vuelve a abrir el editor visual, añade al menos un atajo keyd o activa el bloqueo global de atajos, "
            "y guarda/importa de nuevo."
        )

    path = Path(keyd_conf).expanduser()

    if not path.exists():
        return (
            "El perfil tiene keyd_conf, pero el archivo no existe:\n"
            f"{path}"
        )

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

    combined = "\n".join(
        x.strip()
        for x in [result.stdout, result.stderr]
        if x and x.strip()
    )

    if diagnostic:
        show_error("UrOwnKeyboard - keyd", diagnostic)

    if result.returncode != 0:
        show_error(
            "UrOwnKeyboard",
            combined or "Could not activate configuration.",
        )
        return

    if "WARNING:" in combined or "keyd" in result.stderr.lower():
        show_error("UrOwnKeyboard - keyd", combined)

    ok, msg = verify_uok_profile_applied(profile_id)

    if not ok:
        show_error("UrOwnKeyboard - verificación", msg)
        return

    notify("Keyboard", result.stdout.strip() or f"{profile.get('name', profile_id)} activated")


# --------------------------------------------------------------------
# UOK final override: no modal dialogs and suppress false keyd warning
# --------------------------------------------------------------------
# Este bloque debe estar justo antes de sincronizar_estado_al_arrancar()
# para que sus definiciones sean las últimas.

def show_error(title, msg):
    import subprocess as _sp
    import os as _os

    title = str(title or "UrOwnKeyboard")
    msg = str(msg or "")

    # Falso positivo: keyd puede seguir activo como daemon.
    # Al volver a una configuración normal lo correcto es que quede neutral,
    # no que systemctl keyd deje de estar activo.
    suppress_parts = [
        "La distribución XKB se ha cambiado, pero keyd sigue activo",
        "keyd sigue activo",
        "Si notas remapeos antiguos",
    ]

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
        _sp.Popen(
            [
                "notify-send",
                "--app-name=UrOwnKeyboard",
                "--icon=input-keyboard",
                title,
                msg,
            ],
            stdin=_sp.DEVNULL,
            stdout=_sp.DEVNULL,
            stderr=_sp.DEVNULL,
            env=globals().get("menu_env", lambda: _os.environ.copy())(),
            start_new_session=True,
        )
    except Exception:
        pass


def verify_gnome_source_applied(source_type, source_id):
    # keyd puede seguir activo como servicio.
    # No se debe avisar por "systemctl is-active keyd".
    if source_type != "xkb":
        return True, ""

    got = raw_xkb_layout()
    expected = expected_source_spec(source_id)

    if got != expected:
        return False, f"XKB no cambió al layout esperado. Esperado: {expected}. Actual: {got or 'desconocido'}."

    return True, ""


# --------------------------------------------------------------------
# UOK Cinnamon-only compatibility override
# --------------------------------------------------------------------
# Este bloque NO modifica GNOME ni XFCE.
# En escritorios que no sean Cinnamon delega en las funciones anteriores.

try:
    __uok_base_get_sources = get_sources
except Exception:
    def __uok_base_get_sources():
        return []

try:
    __uok_base_abrir_ajustes_teclado = abrir_ajustes_teclado
except Exception:
    def __uok_base_abrir_ajustes_teclado(_item=None):
        return

try:
    __uok_base_ocultar_menu_xfce = ocultar_menu_xfce
except Exception:
    def __uok_base_ocultar_menu_xfce():
        return


def uok_desktop_name():
    return " ".join([
        os.environ.get("XDG_CURRENT_DESKTOP", ""),
        os.environ.get("DESKTOP_SESSION", ""),
        os.environ.get("XDG_SESSION_DESKTOP", ""),
    ]).lower()


def uok_is_cinnamon():
    return "cinnamon" in uok_desktop_name()


def uok_read_gsettings_array(schema, key):
    try:
        raw = subprocess.check_output(
            ["gsettings", "get", schema, key],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return []

    try:
        import ast
        value = ast.literal_eval(raw)
    except Exception:
        return []

    if isinstance(value, (list, tuple)):
        return [str(x) for x in value]

    return []


def uok_ibus_engine_to_source(engine):
    engine = str(engine or "").strip().strip("'\"")

    if not engine.startswith("xkb:"):
        return None

    parts = engine.split(":")

    if len(parts) < 2:
        return None

    layout = parts[1].strip()
    variant = parts[2].strip() if len(parts) >= 3 else ""

    if not layout:
        return None

    if variant:
        return ("xkb", f"{layout}+{variant}")

    return ("xkb", layout)


def uok_cinnamon_ibus_sources():
    engines = []

    for key in ("engines-order", "preload-engines"):
        for engine in uok_read_gsettings_array("org.freedesktop.ibus.general", key):
            if engine not in engines:
                engines.append(engine)

    sources = []

    for engine in engines:
        source = uok_ibus_engine_to_source(engine)

        if source and source not in sources:
            sources.append(source)

    return sources


def get_sources():
    if not uok_is_cinnamon():
        return __uok_base_get_sources()

    sources = uok_cinnamon_ibus_sources()

    try:
        current = get_raw_setxkbmap_spec()
    except Exception:
        current = ""

    if current:
        current_source = ("xkb", current.replace("(", "+").replace(")", ""))

        if current_source not in sources:
            sources.insert(0, current_source)

    return sources


def abrir_ajustes_teclado(_item=None):
    if not uok_is_cinnamon():
        return __uok_base_abrir_ajustes_teclado(_item)

    for cmd in (
        ["cinnamon-settings", "keyboard"],
        ["cinnamon-settings", "region"],
    ):
        try:
            subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=menu_env(),
                start_new_session=True,
            )
            return
        except FileNotFoundError:
            continue
        except Exception:
            continue

    notify("UrOwnKeyboard", "No se pudo abrir la configuración de teclado de Cinnamon.")


def ocultar_menu_xfce():
    if uok_is_cinnamon():
        # No tocar XFCE ni GNOME desde Cinnamon.
        # Tampoco eliminamos applets de Cinnamon automáticamente.
        return

    return __uok_base_ocultar_menu_xfce()




# --------------------------------------------------------------------
# UOK KDE Plasma-only compatibility override
# --------------------------------------------------------------------
# Este bloque sólo actúa en KDE/Plasma.
# GNOME, XFCE y Cinnamon delegan en las funciones anteriores.

try:
    __uok_kde_base_get_sources = get_sources
except Exception:
    def __uok_kde_base_get_sources():
        return []

try:
    __uok_kde_base_aplicar_gnome_source_sync = aplicar_gnome_source_sync
except Exception:
    def __uok_kde_base_aplicar_gnome_source_sync(index):
        return True

try:
    __uok_kde_base_get_gnome_current_source = get_gnome_current_source
except Exception:
    def __uok_kde_base_get_gnome_current_source():
        return None

try:
    __uok_kde_base_aplicar_keyd_off_sync = aplicar_keyd_off_sync
except Exception:
    def __uok_kde_base_aplicar_keyd_off_sync():
        return True


def uok_kde_desktop_name():
    return " ".join([
        os.environ.get("XDG_CURRENT_DESKTOP", ""),
        os.environ.get("DESKTOP_SESSION", ""),
        os.environ.get("XDG_SESSION_DESKTOP", ""),
    ]).lower()


def uok_is_kde():
    desktop = uok_kde_desktop_name()
    return "kde" in desktop or "plasma" in desktop


def uok_kde_source_id_from_layout_variant(layout, variant=""):
    layout = (layout or "").strip()
    variant = (variant or "").strip()

    if not layout:
        return ""

    return f"{layout}+{variant}" if variant else layout


def uok_kde_unique_sources(sources):
    out = []
    seen = set()

    for item in sources:
        if not item or len(item) != 2:
            continue

        source_type, source_id = item
        source_type = str(source_type or "").strip()
        source_id = str(source_id or "").strip()

        if source_type != "xkb" or not source_id:
            continue

        key = (source_type, source_id)

        if key in seen:
            continue

        seen.add(key)
        out.append(key)

    return out


def uok_kde_sources_from_setxkbmap():
    result = run_menu_cmd(["setxkbmap", "-query"])

    if result.returncode != 0:
        return []

    layouts = []
    variants = []

    for line in result.stdout.splitlines():
        clean = line.strip()

        if clean.startswith("layout:"):
            layouts = [x.strip() for x in clean.split(":", 1)[1].split(",") if x.strip()]
        elif clean.startswith("variant:"):
            variants = [x.strip() for x in clean.split(":", 1)[1].split(",")]

    while len(variants) < len(layouts):
        variants.append("")

    sources = []

    for layout, variant in zip(layouts, variants):
        source_id = uok_kde_source_id_from_layout_variant(layout, variant)

        if source_id:
            sources.append(("xkb", source_id))

    return uok_kde_unique_sources(sources)


def uok_kde_sources_from_kxkbrc():
    paths = [
        HOME / ".config" / "kxkbrc",
        HOME / ".kde" / "share" / "config" / "kxkbrc",
    ]

    text = ""

    for path in paths:
        try:
            if path.exists():
                text = path.read_text(encoding="utf-8", errors="ignore")
                break
        except Exception:
            pass

    if not text:
        return []

    layouts = []
    variants = []

    for line in text.splitlines():
        clean = line.strip()

        if not clean or clean.startswith("#") or "=" not in clean:
            continue

        key, value = clean.split("=", 1)
        key = key.strip().lower()
        value = value.strip()

        if key in {"layoutlist", "layouts"}:
            layouts = [x.strip() for x in value.split(",") if x.strip()]
        elif key in {"variantlist", "variants"}:
            variants = [x.strip() for x in value.split(",")]

    while len(variants) < len(layouts):
        variants.append("")

    sources = []

    for layout, variant in zip(layouts, variants):
        source_id = uok_kde_source_id_from_layout_variant(layout, variant)

        if source_id:
            sources.append(("xkb", source_id))

    return uok_kde_unique_sources(sources)


def get_sources():
    if not uok_is_kde():
        return __uok_kde_base_get_sources()

    sources = []

    # KDE suele guardar la lista completa en ~/.config/kxkbrc.
    sources.extend(uok_kde_sources_from_kxkbrc())

    # setxkbmap refleja lo que está activo realmente.
    sources.extend(uok_kde_sources_from_setxkbmap())

    return uok_kde_unique_sources(sources)


def aplicar_gnome_source_sync(index):
    if uok_is_kde():
        # En KDE no usamos org.gnome.desktop.input-sources.
        # El cambio real lo hace aplicar_xkb_source_sync() con setxkbmap.
        return True

    return __uok_kde_base_aplicar_gnome_source_sync(index)


def get_gnome_current_source():
    if not uok_is_kde():
        return __uok_kde_base_get_gnome_current_source()

    sources = get_sources()

    if not sources:
        return None

    source_type, source_id = sources[0]

    return {
        "index": 0,
        "source_type": source_type,
        "source_id": source_id,
        "name": source_label(source_type, source_id),
    }


def aplicar_keyd_off_sync():
    if not uok_is_kde():
        return __uok_kde_base_aplicar_keyd_off_sync()

    result = run_menu_cmd(["sudo", "-n", str(KEYD_HELPER), "--off"])

    if result.returncode == 0:
        return True

    # En KDE no bloqueamos ni mostramos aviso si sudo no puede apagar keyd.
    # XKB debe poder volver a un teclado normal igualmente.
    # El instalador crea sudoers NOPASSWD para el helper; si no existe, se corrige aparte.
    return True


# --------------------------------------------------------------------
# UOK KDE activation override
# --------------------------------------------------------------------
# Sólo cambia la activación de fuentes normales en KDE.
# GNOME/XFCE/Cinnamon delegan en la función anterior.

try:
    __uok_kde_base_activar_gnome_source = activar_gnome_source
except Exception:
    def __uok_kde_base_activar_gnome_source(index, source_type, source_id):
        return


def activar_gnome_source(index, source_type, source_id):
    if not uok_is_kde():
        return __uok_kde_base_activar_gnome_source(index, source_type, source_id)

    label = source_label(source_type, source_id)

    # En KDE: keyd es opcional. Si no se puede apagar, no bloqueamos XKB.
    try:
        aplicar_keyd_off_sync()
    except Exception:
        pass

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
        "desktop": "kde",
        "keyd_conf": None,
    }

    CURRENT_PROFILE.write_text(
        json.dumps(current, indent=2, ensure_ascii=False)
    )

    notify("Keyboard", label + " activated")


# --------------------------------------------------------------------
# UOK KDE IBus source merge override
# --------------------------------------------------------------------
# Sólo KDE/Plasma:
# - KDE aporta fuentes desde ~/.config/kxkbrc y setxkbmap.
# - IBus puede aportar otras fuentes visibles en el menú nativo, por ejemplo de.
# GNOME/XFCE/Cinnamon no se modifican.

try:
    __uok_kde_ibus_base_get_sources = get_sources
except Exception:
    def __uok_kde_ibus_base_get_sources():
        return []


def uok_kde_ibus_read_gsettings_array(schema, key):
    try:
        raw = subprocess.check_output(
            ["gsettings", "get", schema, key],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return []

    try:
        value = ast.literal_eval(raw)
    except Exception:
        return []

    if isinstance(value, (list, tuple)):
        return [str(x) for x in value]

    return []


def uok_kde_ibus_engine_to_source(engine):
    engine = str(engine or "").strip().strip("'\"")

    if not engine.startswith("xkb:"):
        return None

    parts = engine.split(":")

    if len(parts) < 2:
        return None

    layout = parts[1].strip()
    variant = parts[2].strip() if len(parts) >= 3 else ""

    if not layout:
        return None

    if variant:
        return ("xkb", f"{layout}+{variant}")

    return ("xkb", layout)


def uok_kde_ibus_sources():
    engines = []

    for key in ("engines-order", "preload-engines"):
        for engine in uok_kde_ibus_read_gsettings_array("org.freedesktop.ibus.general", key):
            if engine not in engines:
                engines.append(engine)

    sources = []

    for engine in engines:
        source = uok_kde_ibus_engine_to_source(engine)

        if source and source not in sources:
            sources.append(source)

    return sources


def get_sources():
    if not uok_is_kde():
        return __uok_kde_ibus_base_get_sources()

    sources = []

    # Lo que ya detectaba KDE: kxkbrc + setxkbmap.
    sources.extend(__uok_kde_ibus_base_get_sources())

    # Lo que aparece en el menú nativo de IBus.
    sources.extend(uok_kde_ibus_sources())

    try:
        return uok_kde_unique_sources(sources)
    except Exception:
        out = []
        seen = set()

        for item in sources:
            if not item or len(item) != 2:
                continue

            key = tuple(item)

            if key in seen:
                continue

            seen.add(key)
            out.append(key)

        return out


# --------------------------------------------------------------------
# UOK KDE Plasma native keyboard menu hider
# --------------------------------------------------------------------
# Sólo KDE/Plasma. No toca layouts, idiomas ni kxkbrc.
# Oculta/elimina del panel los iconos nativos de teclado/input method
# para que quede visible sólo el menú de UrOwnKeyboard.

def uok_hide_kde_native_keyboard_menus():
    try:
        desktop = " ".join([
            os.environ.get("XDG_CURRENT_DESKTOP", ""),
            os.environ.get("DESKTOP_SESSION", ""),
            os.environ.get("XDG_SESSION_DESKTOP", ""),
        ]).lower()

        if "kde" not in desktop and "plasma" not in desktop:
            return

        conf = HOME / ".config" / "plasma-org.kde.plasma.desktop-appletsrc"

        if not conf.exists():
            return

        plugins = {
            "org.kde.plasma.keyboardlayout",
            "org.kde.plasma.manage-inputmethod",
        }

        text = conf.read_text(encoding="utf-8", errors="ignore")
        lines = text.splitlines()

        import re as _re

        groups = []
        current = None

        for i, line in enumerate(lines):
            m = _re.match(r"^\[(.+)\]\s*$", line)
            if m:
                current = {
                    "name": m.group(1),
                    "start": i,
                    "end": len(lines),
                    "body": [],
                }
                groups.append(current)
            elif current is not None:
                current["body"].append(line)

        for i in range(len(groups) - 1):
            groups[i]["end"] = groups[i + 1]["start"]

        target_ids = set()

        for group in groups:
            body = "\n".join(group["body"])

            if any(f"plugin={plugin}" in body for plugin in plugins):
                m = _re.search(r"Applets\]\[(\d+)", group["name"])
                if m:
                    target_ids.add(m.group(1))

        def split_csv(value):
            return [x.strip() for x in value.split(",") if x.strip()]

        def join_csv(items):
            out = []
            seen = set()

            for item in items:
                if item and item not in seen:
                    seen.add(item)
                    out.append(item)

            return ",".join(out)

        remove_line = [False] * len(lines)

        for group in groups:
            name = group["name"]

            remove_group = False

            for applet_id in target_ids:
                # Ojo: el último corchete no está dentro de group["name"].
                if _re.search(rf"Applets\]\[{_re.escape(applet_id)}(?:\]|$|\[)", name):
                    remove_group = True

            if "\\x5bConfiguration" in name:
                remove_group = True

            if remove_group:
                for i in range(group["start"], group["end"]):
                    remove_line[i] = True

        new = []
        in_general = False
        hidden_seen = False

        for i, line in enumerate(lines):
            if remove_line[i]:
                continue

            m = _re.match(r"^\[(.+)\]\s*$", line)

            if m:
                if in_general and not hidden_seen:
                    new.append("hiddenItems=" + join_csv(sorted(plugins)))

                group = m.group(1)
                in_general = group.endswith("[General]")
                hidden_seen = False
                new.append(line)
                continue

            if "=" in line:
                key, value = line.split("=", 1)

                if key == "AppletOrder" and target_ids:
                    parts = [x.strip() for x in value.split(";") if x.strip()]
                    parts = [x for x in parts if x not in target_ids]
                    line = key + "=" + ";".join(parts)

                elif key in {"extraItems", "knownItems", "shownItems"}:
                    parts = [x for x in split_csv(value) if x not in plugins]
                    line = key + "=" + join_csv(parts)

                elif key == "hiddenItems":
                    parts = split_csv(value)
                    for plugin in sorted(plugins):
                        if plugin not in parts:
                            parts.append(plugin)
                    line = key + "=" + join_csv(parts)
                    hidden_seen = True

            new.append(line)

        if in_general and not hidden_seen:
            new.append("hiddenItems=" + join_csv(sorted(plugins)))

        fixed = "\n".join(new) + "\n"

        if fixed != text:
            conf.write_text(fixed, encoding="utf-8")

        try:
            subprocess.run(
                ["gsettings", "set", "org.freedesktop.ibus.panel", "show-icon-on-systray", "false"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=menu_env(),
                check=False,
            )
        except Exception:
            pass

    except Exception:
        return

uok_hide_kde_native_keyboard_menus()

# --------------------------------------------------------------------
# UOK KDE Plasma IBus native menu hider
# --------------------------------------------------------------------
# Sólo KDE/Plasma.
# Cierra el panel/menú visual de IBus para que no aparezca el menú nativo
# Español/Alemán, pero NO borra las fuentes IBus. UOK las sigue leyendo
# desde gsettings.

def uok_hide_kde_ibus_native_menu():
    try:
        desktop = " ".join([
            os.environ.get("XDG_CURRENT_DESKTOP", ""),
            os.environ.get("DESKTOP_SESSION", ""),
            os.environ.get("XDG_SESSION_DESKTOP", ""),
        ]).lower()

        if "kde" not in desktop and "plasma" not in desktop:
            return

        # Evita que IBus muestre icono propio en la bandeja.
        subprocess.run(
            ["gsettings", "set", "org.freedesktop.ibus.panel", "show-icon-on-systray", "false"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=menu_env(),
            check=False,
        )

        # Cierra sólo la interfaz/panel de IBus. No borra engines-order ni preload-engines.
        for cmd in (
            ["ibus", "exit"],
            ["pkill", "-f", "ibus-ui"],
            ["pkill", "-f", "ibus-panel"],
        ):
            try:
                subprocess.run(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=menu_env(),
                    check=False,
                )
            except Exception:
                pass

    except Exception:
        return






# UOK GNOME Wayland system sources backend delegation
# This block must stay late in the file, after older get_sources() definitions.
try:
    from uok_backends.session import is_gnome_wayland as uok_is_gnome_wayland
    from uok_backends import system_sources as uok_system_sources

    __uok_pre_backend_get_sources = get_sources

    def get_sources():
        # In GNOME Wayland, setxkbmap/IBus are not reliable sources of truth.
        # Use only GNOME's configured input sources.
        if uok_is_gnome_wayland():
            return uok_system_sources.current_sources()

        return __uok_pre_backend_get_sources()

except Exception as exc:
    print(f"UOK GNOME Wayland system sources delegation disabled: {exc}")

# UOK X11 helper backend delegation
# This block must stay late in the file, after older XKB helper definitions.
try:
    from uok_backends.session import is_wayland as uok_session_is_wayland
    from uok_backends import x11 as uok_x11_backend

    def raw_xkb_layout():
        # setxkbmap is not a reliable source in Wayland/Xwayland.
        # Returning empty here avoids using X11 state as truth in Wayland.
        if uok_session_is_wayland():
            return ""

        spec = uok_x11_backend.current_spec()

        if "(" in spec and spec.endswith(")"):
            layout, variant = spec[:-1].split("(", 1)
            return f"{layout}+{variant}"

        return spec

    def get_raw_setxkbmap_spec():
        if uok_session_is_wayland():
            return ""

        return uok_x11_backend.current_spec()

    def gnome_source_to_setxkbmap_cmd(source_type, source_id):
        return uok_x11_backend.source_to_setxkbmap_cmd(source_type, source_id) or ""

    def expected_source_spec(source_id):
        return (source_id or "").strip()

except Exception as exc:
    print(f"UOK X11 helper backend delegation disabled: {exc}")

# UOK keyd backend delegation
# This block must stay late in the file, after older keyd helper definitions.
try:
    from uok_backends import keyd as uok_keyd_backend

    def aplicar_keyd_off_sync():
        result = uok_keyd_backend.off()
        if not result.ok:
            try:
                show_error(
                    "UrOwnKeyboard - keyd",
                    "No se pudo desactivar keyd. Se continuará si el backend lo permite.\n\n"
                    + result.combined,
                )
            except Exception:
                pass
        return result.ok

    def aplicar_keyd_de_profile_o_apagar(profile):
        result = uok_keyd_backend.apply_profile_or_off(profile)
        if not result.ok:
            try:
                show_error(
                    "UrOwnKeyboard - keyd",
                    "No se pudo aplicar keyd para este perfil.\n\n" + result.combined,
                )
            except Exception:
                pass
        return result.ok

    def keyd_is_active():
        return uok_keyd_backend.is_service_active()

except Exception as exc:
    print(f"UOK keyd backend delegation disabled: {exc}")


# UOK GNOME Wayland activation backend delegation
# This block must stay late, after older activar_gnome_source() definitions
# and after keyd delegation, but before uok_backends.overrides.install().
try:
    from uok_backends.session import is_gnome_wayland as uok_is_gnome_wayland_activation
    from uok_backends import gnome_wayland as uok_gnome_wayland_backend

    __uok_pre_backend_activar_gnome_source = activar_gnome_source

    def activar_gnome_source(index, source_type, source_id):
        if not uok_is_gnome_wayland_activation():
            return __uok_pre_backend_activar_gnome_source(index, source_type, source_id)

        label = source_label(source_type, source_id)

        if source_type != "xkb":
            show_error(
                "UrOwnKeyboard - GNOME Wayland",
                "Esta fuente no es XKB y todavía no está soportada en GNOME Wayland.",
            )
            return

        # Nunca dejar keyd activo al volver a una fuente normal del sistema.
        if not aplicar_keyd_off_sync():
            return

        if not uok_gnome_wayland_backend.set_current_index(index):
            show_error(
                "UrOwnKeyboard - GNOME Wayland",
                "No se pudo cambiar la fuente de entrada de GNOME.",
            )
            return

        try:
            from uok_backends.overrides import _force_ibus_engine
            _force_ibus_engine(__import__(__name__), source_type, source_id)
        except Exception:
            pass

        if not uok_gnome_wayland_backend.verify_index(index):
            show_error(
                "UrOwnKeyboard - verificación",
                "GNOME no cambió al índice esperado. "
                f"Esperado: {index}. Actual: {uok_gnome_wayland_backend.current_index()}",
            )
            return

        current = {
            "type": "gnome-source",
            "name": label,
            "source_type": source_type,
            "source_id": source_id,
            "desktop": "gnome-wayland",
            "keyd_conf": None,
        }

        CURRENT_PROFILE.write_text(
            json.dumps(current, indent=2, ensure_ascii=False)
        )

        notify("Keyboard", label + " activated")

except Exception as exc:
    print(f"UOK GNOME Wayland activation delegation disabled: {exc}")

# UOK backend overrides
try:
    from uok_backends.overrides import install as uok_install_backend_overrides
    uok_install_backend_overrides(__import__(__name__))
except Exception as exc:
    print(f'UOK backend overrides disabled: {exc}')

uok_hide_kde_ibus_native_menu()
ocultar_menu_xfce()
sincronizar_estado_al_arrancar()

# --------------------------------------------------------------------
# UOK MATE override: Add from settings before crear_menu
# --------------------------------------------------------------------

try:
    __uok_mate_base_abrir_ajustes_teclado = abrir_ajustes_teclado
except Exception:
    def __uok_mate_base_abrir_ajustes_teclado(_item=None):
        notify("UrOwnKeyboard", "No se pudo abrir la configuración de teclado del sistema.")


def uok_mate_settings_is_mate():
    desktop = " ".join([
        os.environ.get("XDG_CURRENT_DESKTOP", ""),
        os.environ.get("DESKTOP_SESSION", ""),
        os.environ.get("XDG_SESSION_DESKTOP", ""),
    ]).lower()

    return "mate" in desktop


def abrir_ajustes_teclado(_item=None):
    if not uok_mate_settings_is_mate():
        return __uok_mate_base_abrir_ajustes_teclado(_item)

    cmd = ["mate-keyboard-properties"]

    try:
        check = subprocess.run(
            ["bash", "-lc", "command -v mate-keyboard-properties"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=menu_env(),
        )

        if check.returncode != 0:
            notify("UrOwnKeyboard", "No se encontró mate-keyboard-properties.")
            return

        shell_cmd = (
            "mate-keyboard-properties; "
            "pkill -f teclado-indicador.py 2>/dev/null || true; "
            "$HOME/.local/bin/teclado-indicador.py >/dev/null 2>&1 &"
        )

        subprocess.Popen(
            ["bash", "-lc", shell_cmd],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            env=menu_env(),
        )
        return

    except Exception as exc:
        notify("UrOwnKeyboard", f"No se pudo abrir la configuración de teclado de MATE: {exc}")



# --------------------------------------------------------------------
# UOK LXQt helpers
# --------------------------------------------------------------------

def uok_is_lxqt_desktop():
    desktop = " ".join([
        os.environ.get("XDG_CURRENT_DESKTOP", ""),
        os.environ.get("DESKTOP_SESSION", ""),
        os.environ.get("XDG_SESSION_DESKTOP", ""),
    ]).lower()

    return "lxqt" in desktop


try:
    __uok_base_abrir_ajustes_teclado_lxqt = abrir_ajustes_teclado
except Exception:
    def __uok_base_abrir_ajustes_teclado_lxqt(_item=None):
        notify("UrOwnKeyboard", "No se pudo abrir la configuración de teclado del sistema.")


def abrir_ajustes_teclado(_item=None):
    if not uok_is_lxqt_desktop():
        return __uok_base_abrir_ajustes_teclado_lxqt(_item)

    commands = [
        ["lxqt-config-input"],
        ["lxqt-config"],
    ]

    for cmd in commands:
        try:
            check = run_menu_cmd(["bash", "-lc", "command -v " + shlex.quote(cmd[0])])

            if check.returncode != 0:
                continue

            shell_cmd = (
                " ".join(shlex.quote(x) for x in cmd)
                + "; "
                + "pkill -f teclado-indicador.py 2>/dev/null || true; "
                + "$HOME/.local/bin/teclado-indicador.py >/dev/null 2>&1 &"
            )

            subprocess.Popen(
                ["bash", "-lc", shell_cmd],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                env=menu_env(),
            )
            return

        except Exception:
            continue

    notify("UrOwnKeyboard", "No se pudo abrir la configuración de teclado de LXQt.")


uok_main_menu = crear_menu()
indicator.set_menu(uok_main_menu)

# --------------------------------------------------------------------
# UOK Cinnamon Gtk.StatusIcon fallback
# --------------------------------------------------------------------
# Cinnamon a veces no muestra el AppIndicator/Ayatana aunque el proceso esté vivo.
# Este fallback sólo se activa en Cinnamon y no modifica GNOME ni XFCE.

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
            menu.popup(
                None,
                None,
                Gtk.StatusIcon.position_menu,
                status_icon,
                button,
                activate_time,
            )

        def activate(_icon):
            menu.popup(
                None,
                None,
                Gtk.StatusIcon.position_menu,
                status_icon,
                0,
                Gtk.get_current_event_time(),
            )

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

