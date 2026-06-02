#!/usr/bin/env python3
from pathlib import Path
import py_compile

ROOT = Path.cwd()
BACKENDS = ROOT / "uok_backends"
SYSTEM = BACKENDS / "system_sources.py"
INDICATOR = ROOT / "teclado-indicador.py"

SYSTEM_SOURCES_PY = '''import ast
import configparser
import os
import subprocess
from pathlib import Path


def run(cmd):
    return subprocess.run(
        [str(x) for x in cmd],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def unique_sources(sources):
    out = []
    seen = set()

    for item in sources:
        if not item:
            continue

        if len(item) == 2:
            source_type, source_id = item
            label = None
        else:
            source_type, source_id, label = item[0], item[1], item[2]

        key = (str(source_type), str(source_id))

        if key in seen:
            continue

        seen.add(key)

        if label is None:
            out.append((key[0], key[1]))
        else:
            out.append((key[0], key[1], label))

    return out


def parse_gsettings_sources_literal(raw):
    try:
        value = ast.literal_eval((raw or "").strip())
    except Exception:
        return []

    out = []

    for item in value:
        try:
            source_type, source_id = item[0], item[1]
        except Exception:
            continue

        if source_type and source_id:
            out.append((str(source_type), str(source_id)))

    return unique_sources(out)


def gnome_sources():
    result = run([
        "gsettings",
        "get",
        "org.gnome.desktop.input-sources",
        "sources",
    ])

    if result.returncode != 0:
        return []

    return parse_gsettings_sources_literal(result.stdout)


def xfconf_get(channel, prop):
    result = run(["xfconf-query", "-c", channel, "-p", prop])

    if result.returncode != 0:
        return ""

    return result.stdout.strip()


def xfce_keyboard_layout_sources():
    layouts = xfconf_get("keyboard-layout", "/Default/XkbLayout")
    variants = xfconf_get("keyboard-layout", "/Default/XkbVariant")

    if not layouts:
        return []

    layout_list = [x.strip() for x in layouts.split(",") if x.strip()]
    variant_list = [x.strip() for x in variants.split(",")] if variants else []

    out = []

    for i, layout in enumerate(layout_list):
        variant = variant_list[i] if i < len(variant_list) else ""
        source_id = f"{layout}+{variant}" if variant else layout
        out.append(("xkb", source_id))

    return unique_sources(out)


def setxkbmap_sources():
    result = run(["setxkbmap", "-query"])

    if result.returncode != 0:
        return []

    layout = ""
    variant = ""

    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("layout:"):
            layout = line.split(":", 1)[1].strip()
        elif line.startswith("variant:"):
            variant = line.split(":", 1)[1].strip()

    if not layout:
        return []

    layouts = [x.strip() for x in layout.split(",") if x.strip()]
    variants = [x.strip() for x in variant.split(",")] if variant else []

    out = []

    for i, item in enumerate(layouts):
        var = variants[i] if i < len(variants) else ""
        source_id = f"{item}+{var}" if var else item
        out.append(("xkb", source_id))

    return unique_sources(out)


def kde_kxkbrc_sources():
    paths = [
        Path.home() / ".config" / "kxkbrc",
        Path.home() / ".kde" / "share" / "config" / "kxkbrc",
    ]

    config_path = next((p for p in paths if p.exists()), None)

    if not config_path:
        return []

    parser = configparser.ConfigParser(strict=False)
    parser.optionxform = str

    try:
        parser.read(config_path, encoding="utf-8")
    except Exception:
        return []

    section = "Layout"
    if not parser.has_section(section):
        return []

    layout_raw = parser.get(section, "LayoutList", fallback="")
    variant_raw = parser.get(section, "VariantList", fallback="")

    layouts = [x.strip() for x in layout_raw.split(",") if x.strip()]
    variants = [x.strip() for x in variant_raw.split(",")] if variant_raw else []

    out = []

    for i, layout in enumerate(layouts):
        variant = variants[i] if i < len(variants) else ""
        source_id = f"{layout}+{variant}" if variant else layout
        out.append(("xkb", source_id))

    return unique_sources(out)


def ibus_xkb_sources():
    # IBus can expose many engines. Keep only xkb engines and convert common
    # names to plain XKB ids when possible.
    result = run(["ibus", "list-engine"])

    if result.returncode != 0:
        return []

    out = []

    for line in result.stdout.splitlines():
        text = line.strip()
        if not text.startswith("xkb:"):
            continue

        # Examples:
        # xkb:es::spa - Spanish
        # xkb:de::ger - German
        parts = text.split(":", 3)
        if len(parts) >= 2 and parts[1]:
            out.append(("xkb", parts[1]))

    return unique_sources(out)


def sources_for_desktop(desktop_text, session_type=""):
    text = (desktop_text or "").lower()
    session = (session_type or "").lower()

    if "kde" in text or "plasma" in text:
        return unique_sources(kde_kxkbrc_sources() + setxkbmap_sources() + ibus_xkb_sources())

    if "xfce" in text:
        return unique_sources(xfce_keyboard_layout_sources() + setxkbmap_sources())

    if "mate" in text:
        return unique_sources(gnome_sources() + ibus_xkb_sources() + setxkbmap_sources())

    if "cinnamon" in text:
        return unique_sources(gnome_sources() + ibus_xkb_sources() + setxkbmap_sources())

    if "lxqt" in text:
        return unique_sources(setxkbmap_sources() + ibus_xkb_sources())

    # GNOME Wayland must avoid setxkbmap as a source of truth.
    if "gnome" in text and session == "wayland":
        return unique_sources(gnome_sources())

    if "gnome" in text:
        return unique_sources(gnome_sources() + setxkbmap_sources())

    return unique_sources(gnome_sources() + setxkbmap_sources())


def current_desktop_text():
    return " ".join([
        os.environ.get("XDG_CURRENT_DESKTOP", ""),
        os.environ.get("DESKTOP_SESSION", ""),
        os.environ.get("XDG_SESSION_DESKTOP", ""),
    ]).lower()


def current_session_type():
    return os.environ.get("XDG_SESSION_TYPE", "").lower()


def current_sources():
    return sources_for_desktop(current_desktop_text(), current_session_type())
'''


def main():
    if not BACKENDS.exists():
        raise SystemExit("No existe uok_backends.")
    if not INDICATOR.exists():
        raise SystemExit("Ejecuta este script en la raíz de UrOwnKeyboard.")

    SYSTEM.write_text(SYSTEM_SOURCES_PY, encoding="utf-8")

    py_compile.compile(str(SYSTEM), doraise=True)
    py_compile.compile(str(INDICATOR), doraise=True)

    print("OK: creado uok_backends/system_sources.py")
    print("No se ha modificado teclado-indicador.py todavía.")
    print()
    print("Comprueba con:")
    print("  python3 -m py_compile teclado-indicador.py uok_backends/*.py uok")
    print("  python3 - <<'PY'")
    print("from uok_backends import system_sources")
    print("print(system_sources.current_sources())")
    print("PY")


if __name__ == "__main__":
    main()
