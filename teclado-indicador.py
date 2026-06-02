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



indicator = AppIndicator3.Indicator.new(
    "teclado-custom",
    "input-keyboard",
    AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
)

indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
indicator.set_title("Keyboard")


# --------------------------------------------------------------------
# UOK XFCE backend delegation
try:
    from uok_backends.xfce import install as uok_install_xfce_backend
    uok_install_xfce_backend(__import__(__name__))
except Exception as exc:
    print(f'UOK XFCE backend disabled: {exc}')

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



def show_warning(title, msg):
    uok_v7_nonblocking_dialog("warning", title, msg)





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
# UOK KDE backend delegation
try:
    from uok_backends.kde import install as uok_install_kde_backend
    uok_install_kde_backend(__import__(__name__))
except Exception as exc:
    print(f'UOK KDE backend disabled: {exc}')

# UOK backend overrides
try:
    from uok_backends.overrides import install as uok_install_backend_overrides
    uok_install_backend_overrides(__import__(__name__))
except Exception as exc:
    print(f'UOK backend overrides disabled: {exc}')


# --------------------------------------------------------------------
uok_hide_kde_ibus_native_menu()
ocultar_menu_xfce()
sincronizar_estado_al_arrancar()

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

