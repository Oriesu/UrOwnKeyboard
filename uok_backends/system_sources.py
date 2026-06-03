import ast
import configparser
import os
import subprocess
from pathlib import Path

GNOME_INPUT_SOURCES_SCHEMA = "org.gnome.desktop.input-sources"
GNOME_INPUT_SOURCES_KEY = "sources"
IBUS_GENERAL_SCHEMA = "org.freedesktop.ibus.general"
IBUS_ENGINE_KEYS = ("engines-order", "preload-engines")

def run(cmd):
    return subprocess.run([str(x) for x in cmd],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)

def unique_sources(sources):
    out = []
    seen = set()
    for item in sources:
        if not item:
            continue
        try:
            source_type = str(item[0])
            source_id = str(item[1])
        except Exception:
            continue
        label = item[2] if len(item) > 2 else None
        key = (source_type, source_id)
        if key in seen:
            continue
        seen.add(key)
        if label is None:
            out.append(key)
        else:
            out.append((source_type, source_id, label))
    return out

def split_csv_nonempty(text):
    return [x.strip() for x in str(text or "").split(",") if x.strip()]

def split_csv_keep_empty(text):
    return [x.strip() for x in str(text or "").split(",")]

def source_id_from_layout_variant(layout, variant=""):
    layout = str(layout or "").strip()
    variant = str(variant or "").strip()
    if not layout:
        return ""
    return f"{layout}+{variant}" if variant else layout

def sources_from_layouts_variants(layouts, variants=None):
    layouts = split_csv_nonempty(layouts)
    variants = split_csv_keep_empty(variants) if variants else []
    while len(variants) < len(layouts):
        variants.append("")
    out = []
    for layout, variant in zip(layouts, variants):
        source_id = source_id_from_layout_variant(layout, variant)
        if source_id:
            out.append(("xkb", source_id))
    return unique_sources(out)

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

def gsettings_get(schema, key):
    result = run(["gsettings", "get", schema, key])
    if result.returncode != 0:
        return ""
    return result.stdout.strip()

def gnome_sources():
    raw = gsettings_get(GNOME_INPUT_SOURCES_SCHEMA, GNOME_INPUT_SOURCES_KEY)
    return parse_gsettings_sources_literal(raw)

def xfconf_get(channel, prop):
    result = run(["xfconf-query", "-c", channel, "-p", prop])
    if result.returncode != 0:
        return ""
    return result.stdout.strip()

def xfce_keyboard_layout_sources():
    layouts = xfconf_get("keyboard-layout", "/Default/XkbLayout")
    variants = xfconf_get("keyboard-layout", "/Default/XkbVariant")
    return sources_from_layouts_variants(layouts, variants)

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
    return sources_from_layouts_variants(layout, variant)

def kde_kxkbrc_sources():
    paths = [Path.home() / ".config" / "kxkbrc",Path.home() / ".kde" / "share" / "config" / "kxkbrc"]
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
    layouts = parser.get(section, "LayoutList", fallback="")
    variants = parser.get(section, "VariantList", fallback="")
    return sources_from_layouts_variants(layouts, variants)


def _lxqt_clean_conf_value(value):
    value = str(value or "").strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]
    return value


def lxqt_session_sources():
    path = Path.home() / ".config" / "lxqt" / "session.conf"
    if not path.exists():
        return []
    parser = configparser.ConfigParser(strict=False)
    parser.optionxform = str
    try:
        parser.read(path, encoding="utf-8")
    except Exception:
        return []
    if not parser.has_section("Keyboard"):
        return []
    layouts = _lxqt_clean_conf_value(parser.get("Keyboard", "layout", fallback=""))
    variants = _lxqt_clean_conf_value(parser.get("Keyboard", "variant", fallback=""))
    return sources_from_layouts_variants(layouts, variants)


def ibus_engine_to_source(engine):
    engine = str(engine or "").strip().strip("'\"")
    if not engine.startswith("xkb:"):
        return None
    parts = engine.split(":")
    if len(parts) < 2:
        return None
    source_id = source_id_from_layout_variant(parts[1],parts[2] if len(parts) >= 3 else "")
    if not source_id:
        return None
    return ("xkb", source_id)

def read_gsettings_array(schema, key):
    raw = gsettings_get(schema, key)
    if not raw:
        return []
    try:
        value = ast.literal_eval(raw)
    except Exception:
        import re
        value = re.findall(r"'([^']+)'", raw)
    if isinstance(value, (list, tuple)):
        return [str(x) for x in value]
    return []


def ibus_xkb_sources():
    # Do not use `ibus list-engine`: it returns every installed engine and
    # pollutes UOK's system-source menu with hundreds of layouts. Keep only
    # engines explicitly configured by the user.
    engines = []
    for key in IBUS_ENGINE_KEYS:
        for engine in read_gsettings_array(IBUS_GENERAL_SCHEMA, key):
            if engine not in engines:
                engines.append(engine)
    out = []
    for engine in engines:
        source = ibus_engine_to_source(engine)
        if source:
            out.append(source)
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
        return unique_sources(lxqt_session_sources() + setxkbmap_sources() + ibus_xkb_sources())
    # GNOME Wayland must avoid setxkbmap as a source of truth.
    if "gnome" in text and session == "wayland":
        return unique_sources(gnome_sources())
    if "gnome" in text:
        return unique_sources(gnome_sources() + setxkbmap_sources())
    return unique_sources(gnome_sources() + setxkbmap_sources())

def current_desktop_text():
    return " ".join([os.environ.get("XDG_CURRENT_DESKTOP", ""),os.environ.get("DESKTOP_SESSION", ""),os.environ.get("XDG_SESSION_DESKTOP", "")]).lower()

def current_session_type():
    return os.environ.get("XDG_SESSION_TYPE", "").lower()

def current_sources():
    return sources_for_desktop(current_desktop_text(), current_session_type())