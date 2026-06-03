import ast
import json
import os
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from uok_backends.session import desktop_text

SYSTEM_RULE_FILES = [Path("/usr/share/X11/xkb/rules/evdev.xml"), Path("/usr/share/X11/xkb/rules/base.xml")]

def run(cmd):
    try:
        return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError as e:
        return subprocess.CompletedProcess(cmd, 127, "", str(e))

def desktop_name():
    return desktop_text()

def is_desktop(*names):
    desktop = desktop_name()
    return any(name.lower() in desktop for name in names)

def split_csv_keep_empty(value):
    return [x.strip() for x in (value or "").split(",")]

def split_csv_nonempty(value):
    return [x.strip() for x in (value or "").split(",") if x.strip()]

def source_id_from_layout_variant(layout, variant=""):
    layout = (layout or "").strip()
    variant = (variant or "").strip()
    if not layout:
        return ""
    return f"{layout}+{variant}" if variant else layout

def source_id_to_include(source_id):
    source_id = (source_id or "").strip()
    if "+" in source_id:
        layout, variant = source_id.split("+", 1)
        return f"{layout}({variant})" if variant else layout
    return source_id

def include_to_source_id(include_name):
    include_name = (include_name or "").strip()
    m = re.fullmatch(r"([^()]+)\(([^()]+)\)", include_name)
    if m:
        return f"{m.group(1)}+{m.group(2)}"
    return include_name

LAYOUT_LABELS = {"es":"Español","de":"Alemán","us":"Inglés(EE. UU.)","gb":"Inglés (Reino Unido)","fr":"Francés","it":"Italiano","pt":"Portugués",
    "br":"Portugués (Brasil)"}

def layout_label(layout, variant=""):
    layout = (layout or "").strip()
    variant = (variant or "").strip()
    label = LAYOUT_LABELS.get(layout, layout.upper() if layout else "")
    if variant:
        label = f"{label} ({variant})"
    return label

def normalize_source_id(raw):
    raw = (raw or "").strip().strip("'\"")
    if not raw:
        return ""
    if raw.startswith("xkb:"):
        return ibus_engine_to_source_id(raw)
    if "(" in raw and raw.endswith(")"):
        return include_to_source_id(raw)
    if "+" in raw:
        layout, variant = raw.split("+", 1)
        return source_id_from_layout_variant(layout, variant)
    return raw

def make_added_item(source_id, kind="system-added"):
    source_id = normalize_source_id(source_id)
    include = source_id_to_include(source_id)
    return {"section":"Added to system","kind":kind,"id":f"added:{source_id}","source_id":source_id,"include":include,"label":include,"description":"",
        "xkb_file":""}

def unique_items(items, key_name="source_id"):
    out = []
    seen = set()
    for item in items:
        key = item.get(key_name) or item.get("include") or item.get("id")
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out

def item_key(item):
    return item.get("source_id") or item.get("include") or item.get("id")

def parse_system_xkb_sources():
    xml_file = next((p for p in SYSTEM_RULE_FILES if p.exists()), None)
    if not xml_file:
        return []
    try:
        tree = ET.parse(xml_file)
    except Exception:
        return []
    root = tree.getroot()
    out = []
    for layout in root.findall("./layoutList/layout"):
        config = layout.find("configItem")
        if config is None:
            continue
        layout_name = (config.findtext("name") or "").strip()
        layout_desc = (config.findtext("description") or layout_name).strip()
        if not layout_name:
            continue
        out.append({"section":"Others","kind":"system-other","id":f"other:{layout_name}","source_id":layout_name,"include":layout_name,
            "label":layout_desc,"description":layout_name,"xkb_file":""})
        variant_list = layout.find("variantList")
        if variant_list is None:
            continue
        for variant in variant_list.findall("variant"):
            vconfig = variant.find("configItem")
            if vconfig is None:
                continue
            variant_name = (vconfig.findtext("name") or "").strip()
            variant_desc = (vconfig.findtext("description") or variant_name).strip()
            if not variant_name:
                continue
            source_id = source_id_from_layout_variant(layout_name, variant_name)
            include = source_id_to_include(source_id)

            out.append({"section":"Others","kind":"system-other","id":f"other:{source_id}","source_id":source_id,"include":include,"label":variant_desc,
                "description":source_id,"xkb_file":""})
    return out

def enrich_added_items_from_system(added_items, system_items):
    system_by_source_id = {item["source_id"]: item for item in system_items}
    system_by_include = {item["include"]: item for item in system_items}
    for item in added_items:
        match = system_by_source_id.get(item["source_id"]) or system_by_include.get(item["include"])
        if match:
            item["label"] = match["label"]
            item["description"] = match["description"]
    return added_items

def read_uok_profiles(profiles_dir):
    profiles_dir = Path(profiles_dir).expanduser()
    symbols_dir = Path.home() / ".xkb" / "symbols"
    out = []
    seen_ids = set()
    if profiles_dir.exists():
        for profile_file in sorted(profiles_dir.glob("*.json")):
            try:
                data = json.loads(profile_file.read_text(encoding="utf-8"))
            except Exception:
                continue
            if data.get("type") != "imported-profile":
                continue
            profile_id = data.get("id") or profile_file.stem
            name = data.get("name") or profile_id
            xkb_file = data.get("xkb_file") or str(symbols_dir / profile_id)
            seen_ids.add(profile_id)
            out.append({"section":"UOK","kind":"uok","id":f"uok:{profile_id}","source_id":profile_id,"include":profile_id,"label":name,"description":profile_id,
                "xkb_file":xkb_file})
    # Also show user XKB symbol files that do not have a JSON profile.
    if symbols_dir.exists():
        for xkb_file in sorted(symbols_dir.iterdir()):
            if not xkb_file.is_file():
                continue
            profile_id = xkb_file.name
            if profile_id in seen_ids:
                continue
            if profile_id.startswith(".") or profile_id.endswith(("~", ".bak", ".tmp")):
                continue
            seen_ids.add(profile_id)
            out.append({"section":"UOK","kind":"uok","id":f"uok:{profile_id}","source_id":profile_id,"include":profile_id,"label":profile_id,
                "description":str(xkb_file),"xkb_file":str(xkb_file)})
    return out

def read_gsettings_array(schema, key):
    result = run(["gsettings", "get", schema, key])
    if result.returncode != 0:
        return []
    raw = result.stdout.strip()
    try:
        value = ast.literal_eval(raw)
    except Exception:
        value = re.findall(r"'([^']+)'", raw)
    if isinstance(value, (list, tuple)):
        return [str(x) for x in value]
    return []

def read_gnome_added_sources():
    result = run(["gsettings", "get", "org.gnome.desktop.input-sources", "sources"])
    if result.returncode != 0:
        return []
    out = []
    for source_type, source_id in re.findall(r"\('([^']+)'\s*,\s*'([^']+)'\)", result.stdout):
        if source_type != "xkb":
            continue
        source_id = normalize_source_id(source_id)
        if source_id:
            out.append(make_added_item(source_id, "gnome-input-source"))
    return unique_items(out)

def read_libgnomekbd_keyboard_layouts_added():
    # Used mainly by Cinnamon/MATE. Harmless if the schema/key does not exist.
    layouts = read_gsettings_array("org.gnome.libgnomekbd.keyboard", "layouts")
    return unique_items(make_added_item(normalize_source_id(layout), "libgnomekbd-layout") for layout in layouts if normalize_source_id(layout))

def read_setxkbmap_added_sources(kind="xkb-active"):
    result = run(["setxkbmap", "-query"])
    if result.returncode != 0:
        return []
    layouts = []
    variants = []
    for line in result.stdout.splitlines():
        clean = line.strip()
        if clean.startswith("layout:"):
            layouts = split_csv_nonempty(clean.split(":", 1)[1].strip())
        elif clean.startswith("variant:"):
            variants = split_csv_keep_empty(clean.split(":", 1)[1].strip())
    while len(variants) < len(layouts):
        variants.append("")
    out = []
    for layout, variant in zip(layouts, variants):
        source_id = source_id_from_layout_variant(layout, variant)
        if source_id:
            out.append(make_added_item(source_id, kind))
    return unique_items(out)

def ibus_engine_to_source_id(engine):
    engine = str(engine or "").strip().strip("'\"")
    if not engine.startswith("xkb:"):
        return ""
    parts = engine.split(":")
    if len(parts) < 2:
        return ""
    layout = parts[1].strip()
    variant = parts[2].strip() if len(parts) >= 3 else ""
    return source_id_from_layout_variant(layout, variant)

def read_ibus_added_sources(kind="ibus"):
    engines = []
    for key in ("engines-order", "preload-engines"):
        for engine in read_gsettings_array("org.freedesktop.ibus.general", key):
            if engine not in engines:
                engines.append(engine)
    out = []
    for engine in engines:
        source_id = ibus_engine_to_source_id(engine)
        if source_id:
            out.append(make_added_item(source_id, kind))
    return unique_items(out)

def xfconf_get(channel, prop):
    result = run(["xfconf-query", "-c", channel, "-p", prop])
    if result.returncode != 0:
        return ""
    return result.stdout.strip()

def read_xfce_keyboard_sources():
    layouts = split_csv_nonempty(xfconf_get("keyboard-layout", "/Default/XkbLayout"))
    variants = split_csv_keep_empty(xfconf_get("keyboard-layout", "/Default/XkbVariant"))
    while len(variants) < len(layouts):
        variants.append("")
    out = []
    for layout, variant in zip(layouts, variants):
        source_id = source_id_from_layout_variant(layout, variant)
        if source_id:
            out.append(make_added_item(source_id, "xfce-keyboard"))
    return unique_items(out)

def xkb_plugin_rc_files():
    panel_dir = Path.home() / ".config" / "xfce4" / "panel"
    if not panel_dir.exists():
        return []
    return sorted(panel_dir.glob("xkb-plugin-*.rc"))

def parse_xkb_plugin_rc_file(path):
    try:
        text = Path(path).read_text(encoding="utf-8", errors="ignore")
    except Exception:
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
        if key in {"layout", "layouts", "kbd_layouts", "model_layouts"}:
            layouts.extend(split_csv_nonempty(value))
        elif key in {"variant", "variants", "kbd_variants", "model_variants"}:
            variants.extend(split_csv_keep_empty(value))
    if not layouts:
        for match in re.finditer(r"(?im)^\s*[^=\n]*layout[^=\n]*=\s*([^\n]+)$", text):
            layouts.extend(split_csv_nonempty(match.group(1).strip()))
    if not variants:
        for match in re.finditer(r"(?im)^\s*[^=\n]*variant[^=\n]*=\s*([^\n]+)$", text):
            variants.extend(split_csv_keep_empty(match.group(1).strip()))
    clean_layouts = []
    clean_variants = []
    for value in layouts:
        value = value.strip()
        value = value.split()[0] if value.split() else value
        if re.fullmatch(r"[a-z]{2,3}([+_][A-Za-z0-9_-]+)?", value):
            clean_layouts.append(value.replace("_", "+"))
    for value in variants:
        value = value.strip()
        value = value.split()[0] if value.split() else value
        if re.fullmatch(r"[A-Za-z0-9_-]*", value):
            clean_variants.append(value)
    while len(clean_variants) < len(clean_layouts):
        clean_variants.append("")
    out = []
    for layout, variant in zip(clean_layouts, clean_variants):
        source_id = layout if "+" in layout else source_id_from_layout_variant(layout, variant)
        if source_id:
            out.append(make_added_item(source_id, "xfce-xkb-plugin"))
    return unique_items(out)

def read_xfce_xkb_plugin_sources():
    out = []
    for path in xkb_plugin_rc_files():
        out.extend(parse_xkb_plugin_rc_file(path))
    return unique_items(out)

def read_kde_kxkbrc_sources():
    path = Path.home() / ".config" / "kxkbrc"
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
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
            layouts = split_csv_nonempty(value)
        elif key in {"variantlist", "variants"}:
            variants = split_csv_keep_empty(value)
    while len(variants) < len(layouts):
        variants.append("")
    out = []
    for layout, variant in zip(layouts, variants):
        source_id = source_id_from_layout_variant(layout, variant)
        if source_id:
            out.append(make_added_item(source_id, "kde-kxkbrc"))
    return unique_items(out)

def read_added_sources():
    items = []
    if is_desktop("xfce"):
        # Prefer saved XFCE panel/editor data, then current XKB state, then common fallbacks.
        items.extend(read_xfce_xkb_plugin_sources())
        items.extend(read_xfce_keyboard_sources())
        items.extend(read_setxkbmap_added_sources("xkb-active"))
        items.extend(read_gnome_added_sources())
        items.extend(read_ibus_added_sources("ibus"))
    elif is_desktop("kde", "plasma"):
        items.extend(read_kde_kxkbrc_sources())
        items.extend(read_setxkbmap_added_sources("xkb-active"))
        items.extend(read_ibus_added_sources("kde-ibus"))
    elif is_desktop("cinnamon"):
        items.extend(read_gnome_added_sources())
        items.extend(read_libgnomekbd_keyboard_layouts_added())
        items.extend(read_ibus_added_sources("cinnamon-ibus"))
        items.extend(read_setxkbmap_added_sources("cinnamon-xkb-active"))
    elif is_desktop("mate"):
        items.extend(read_libgnomekbd_keyboard_layouts_added())
        items.extend(read_gnome_added_sources())
        items.extend(read_ibus_added_sources("mate-ibus"))
        items.extend(read_setxkbmap_added_sources("mate-xkb-active"))
    elif is_desktop("lxqt"):
        items.extend(read_setxkbmap_added_sources("lxqt-setxkbmap"))
        items.extend(read_ibus_added_sources("lxqt-ibus"))
    else:
        # GNOME and generic GTK environments.
        items.extend(read_gnome_added_sources())
        if not items:
            items.extend(read_setxkbmap_added_sources("xkb-active"))
    return unique_items(items)

def build_sources(uok_items, added_items, system_items):
    added_items = enrich_added_items_from_system(unique_items(added_items), system_items)
    added_source_ids = {item["source_id"] for item in added_items}
    added_includes = {item["include"] for item in added_items}
    other_items = [item for item in system_items
        if item["source_id"] not in added_source_ids and item["include"] not in added_includes]
    return uok_items + added_items + other_items

def load_xkb_sources(current_profile_file, profiles_dir):
    # current_profile_file is kept for API compatibility with the rest of UOK.
    del current_profile_file
    added_items = read_added_sources()
    system_items = parse_system_xkb_sources()
    return build_sources(uok_items, added_items, system_items)