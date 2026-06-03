import configparser
import os
from pathlib import Path
from .source_utils import (
    run, unique_sources, split_csv_nonempty, split_csv_keep_empty,
    source_id_from_layout_variant, sources_from_layouts_variants,
    parse_gsettings_sources_literal, gsettings_get, xfconf_get,
    setxkbmap_layout_variant_pairs,
    ibus_engine_to_source_id,
)

GNOME_INPUT_SOURCES_SCHEMA = "org.gnome.desktop.input-sources"
GNOME_INPUT_SOURCES_KEY = "sources"
IBUS_GENERAL_SCHEMA = "org.freedesktop.ibus.general"
IBUS_ENGINE_KEYS = ("engines-order", "preload-engines")

def gnome_sources():
    raw = gsettings_get(GNOME_INPUT_SOURCES_SCHEMA, GNOME_INPUT_SOURCES_KEY)
    return parse_gsettings_sources_literal(raw)

def xfce_keyboard_layout_sources():
    layouts = xfconf_get("keyboard-layout", "/Default/XkbLayout")
    variants = xfconf_get("keyboard-layout", "/Default/XkbVariant")
    return sources_from_layouts_variants(layouts, variants)

def setxkbmap_sources():
    return unique_sources(("xkb", source_id_from_layout_variant(layout, variant))
        for layout, variant in setxkbmap_layout_variant_pairs())

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

def ibus_engine_to_source(engine):
    source_id = ibus_engine_to_source_id(engine)
    return ("xkb", source_id) if source_id else None

def ibus_xkb_sources():
    # IBus can expose many engines. Keep only xkb engines.
    result = run(["ibus", "list-engine"])
    if result.returncode != 0:
        return []
    out = []
    for line in result.stdout.splitlines():
        source = ibus_engine_to_source(line.strip())
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
        return unique_sources(setxkbmap_sources() + ibus_xkb_sources())
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