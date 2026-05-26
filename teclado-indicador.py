#!/usr/bin/env python3
import ast
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


def get_sources():
    try:
        raw = sh("gsettings get org.gnome.desktop.input-sources sources")
        return ast.literal_eval(raw)
    except Exception:
        return []


def source_label(source_type, source_id):
    names = {
        "es": "Español",
        "us": "Inglés US",
        "de": "Alemán",
        "fr": "Francés",
        "it": "Italiano",
        "pt": "Portugués",
    }

    if source_type == "xkb":
        return names.get(source_id, source_id)

    if source_type == "ibus":
        return f"IBus: {source_id}"

    return f"{source_type}: {source_id}"


def set_xkb_from_id(source_id):
    if "+" in source_id:
        layout, variant = source_id.split("+", 1)
        return f"setxkbmap {shlex.quote(layout)} {shlex.quote(variant)}"
    return f"setxkbmap {shlex.quote(source_id)}"


def activar_gnome_source(index, source_type, source_id):
    label = source_label(source_type, source_id)

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

    cmds = [
        "sudo /usr/local/sbin/keyd-teclado-modo normal",
        f"gsettings set org.gnome.desktop.input-sources current {index}",
    ]

    if source_type == "xkb":
        cmds.append(set_xkb_from_id(source_id))

    cmds.append(
        f'notify-send "Teclado" {shlex.quote(label + " activado")}'
    )

    run(" && ".join(cmds))

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
    layout_id = profile["id"]
    keyd_conf = profile.get("keyd_conf")

    current = dict(profile)
    current["type"] = "imported-profile"

    CURRENT_PROFILE.write_text(
        json.dumps(current, indent=2, ensure_ascii=False)
    )

    cmds = [
        f'setxkbmap -I"$HOME/.xkb" {shlex.quote(layout_id)}',
    ]

    if keyd_conf:
        cmds.append(f"sudo /usr/local/sbin/keyd-aplicar-conf {shlex.quote(keyd_conf)}")
    else:
        cmds.append("sudo /usr/local/sbin/keyd-teclado-modo normal")

    cmds.append(
        f'notify-send "Teclado" {shlex.quote(profile["name"] + " activado")}'
    )

    run(" && ".join(cmds))

def importar_configuracion(_):
    name = sh(
        'zenity --entry '
        '--title="Importar teclado" '
        '--text="Nombre de la configuración:" '
        '|| true'
    )

    if not name:
        return

    base_id = safe_id(name)
    layout_id = unique_layout_id(base_id)

    xkb_file = sh(
        'zenity --file-selection '
        '--title="Selecciona archivo XKB / symbols" '
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
        notify("Teclado", f"Configuración {name} importada como {layout_id}")
    else:
        notify("Teclado", f"Configuración {name} importada")

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
        notify("Teclado", "No hay configuraciones importadas para eliminar")
        return

    opciones = []
    for profile in profiles:
        opciones.append(profile["id"])
        opciones.append(profile["name"])

    quoted_options = " ".join(shlex.quote(x) for x in opciones)

    cmd = (
        'zenity --list '
        '--title="Eliminar configuración" '
        '--text="Selecciona la configuración que quieres eliminar:" '
        '--column="ID" '
        '--column="Nombre" '
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
        '--title="Eliminar configuración" '
        f'--text={shlex.quote("¿Eliminar la configuración «" + profile["name"] + "»?")} '
        '&& echo yes || true'
    )

    if confirm != "yes":
        return

    borrar_si_seguro(profile.get("xkb_file"))
    borrar_si_seguro(profile.get("keyd_conf"))

    profile_file = Path(profile["_profile_file"]).resolve()

    if str(profile_file).startswith(str(PROFILES.resolve()) + "/") and profile_file.exists():
        profile_file.unlink()

    notify("Teclado", f"Configuración {profile['name']} eliminada")
    reiniciar_indicador()


def get_xkb_spec_actual():
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
            notify("Teclado", "No se pudo detectar la distribución actual")
            return

        run(
            f'gkbd-keyboard-display -l {shlex.quote(spec)} '
            f'|| notify-send "Teclado" "No se pudo abrir el visor para {spec}"'
        )

    except Exception:
        notify("Teclado", "No se pudo abrir el visor de distribución actual")


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
        notify("Teclado", "No se pudo abrir la ventana de información")


def mostrar_configuracion_completa(_):
    try:
        spec = get_xkb_spec_actual()

        if spec:
            run(
                f'gkbd-keyboard-display -l {shlex.quote(spec)} '
                f'|| notify-send "Teclado" "No se pudo abrir el visor para {spec}"'
            )

        info = []

        info.append("CONFIGURACIÓN ACTUAL")
        info.append("=" * 80)
        info.append("")

        if spec:
            info.append(f"Layout XKB activo: {spec}")
        else:
            info.append("Layout XKB activo: no detectado")

        info.append("")
        info.append("setxkbmap -query")
        info.append("-" * 80)

        try:
            info.append(sh("setxkbmap -query"))
        except Exception:
            info.append("No se pudo leer setxkbmap -query")

        info.append("")
        info.append("PERFIL UR OWN KEYBOARD")
        info.append("=" * 80)
        info.append("")

        profile = None

        if CURRENT_PROFILE.exists():
            try:
                profile = json.loads(CURRENT_PROFILE.read_text())
            except Exception:
                profile = None

        if profile:
            info.append(f"Nombre: {profile.get('name', 'sin nombre')}")
            info.append(f"Tipo: {profile.get('type', 'desconocido')}")

            if profile.get("id"):
                info.append(f"ID: {profile.get('id')}")

            if profile.get("source_id"):
                info.append(f"Fuente GNOME: {profile.get('source_id')}")

            if profile.get("xkb_file"):
                info.append(f"Archivo XKB: {profile.get('xkb_file')}")

            keyd_conf = profile.get("keyd_conf")

            info.append("")

            if keyd_conf:
                info.append("KEYD ACTIVO")
                info.append("=" * 80)
                info.append("")
                info.append(f"Archivo keyd: {keyd_conf}")
                info.append("")
                info.append("-" * 80)

                try:
                    info.append(Path(keyd_conf).read_text())
                except Exception:
                    info.append("No se pudo leer el archivo keyd asociado.")
            else:
                info.append("KEYD ACTIVO")
                info.append("=" * 80)
                info.append("")
                info.append("Esta configuración no tiene keyd.conf asociado.")
                info.append("Si es una fuente normal de GNOME, se usa keyd en modo normal.")
        else:
            info.append("No hay perfil activo registrado por UrOwnKeyboard.")
            info.append("")
            info.append("Esto puede pasar si el teclado actual fue cambiado fuera del indicador.")

        mostrar_texto("Configuración completa", "\n".join(info))

    except Exception:
        notify("Teclado", "No se pudo mostrar la configuración completa")


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

    item_complete = Gtk.MenuItem(label="Mostrar configuración completa")
    item_complete.connect("activate", mostrar_configuracion_completa)
    menu.append(item_complete)

    item_import = Gtk.MenuItem(label="Importar configuración…")
    item_import.connect("activate", importar_configuracion)
    menu.append(item_import)

    item_delete = Gtk.MenuItem(label="Eliminar configuración…")
    item_delete.connect("activate", eliminar_configuracion)
    menu.append(item_delete)

    item_refresh = Gtk.MenuItem(label="Recargar lista")
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
indicator.set_title("Teclado")

try:
    indicator.set_label("⌨", "")
except Exception:
    pass

indicator.set_menu(crear_menu())

Gtk.main()
