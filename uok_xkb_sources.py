#!/usr/bin/env python3
import json
import os
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path


SYSTEM_RULE_FILES = [
    Path("/usr/share/X11/xkb/rules/evdev.xml"),
    Path("/usr/share/X11/xkb/rules/base.xml"),
]


def run(cmd):
    try:
        return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError as e:
        return subprocess.CompletedProcess(cmd, 127, "", str(e))


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


def make_added_item(source_id, kind="system-added"):
    include = source_id_to_include(source_id)
    return {
        "section": "Added to system",
        "kind": kind,
        "id": f"added:{source_id}",
        "source_id": source_id,
        "include": include,
        "label": include,
        "description": "",
        "xkb_file": "",
    }


def split_csv_list(value):
    return [x.strip() for x in (value or "").split(",")]


def source_id_from_layout_variant(layout, variant=""):
    layout = (layout or "").strip()
    variant = (variant or "").strip()

    if not layout:
        return ""

    return f"{layout}+{variant}" if variant else layout


def read_gnome_added_sources():
    result = run(["gsettings", "get", "org.gnome.desktop.input-sources", "sources"])
    if result.returncode != 0:
        return []

    out = []

    for source_type, source_id in re.findall(r"\('([^']+)'\s*,\s*'([^']+)'\)", result.stdout):
        if source_type != "xkb":
            continue

        out.append(make_added_item(source_id, "gnome-added"))

    return out


def read_setxkbmap_added_sources():
    result = run(["setxkbmap", "-query"])
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
            out.append(make_added_item(source_id, "xkb-active"))

    return out


def xfconf_get(prop):
    result = run(["xfconf-query", "-c", "keyboard-layout", "-p", prop])
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def read_xfce_added_sources():
    layouts = split_csv_list(xfconf_get("/Default/XkbLayout"))
    variants = split_csv_list(xfconf_get("/Default/XkbVariant"))

    while len(variants) < len(layouts):
        variants.append("")

    out = []

    for layout, variant in zip(layouts, variants):
        source_id = source_id_from_layout_variant(layout, variant)
        if source_id:
            out.append(make_added_item(source_id, "xfce-added"))

    return out


def read_added_sources():
    out = []
    out.extend(read_gnome_added_sources())
    out.extend(read_xfce_added_sources())
    out.extend(read_setxkbmap_added_sources())

    seen = set()
    unique = []

    for item in out:
        key = item["source_id"]
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    return unique


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

            out.append({
                "section": "UOK",
                "kind": "uok",
                "id": f"uok:{profile_id}",
                "source_id": profile_id,
                "include": profile_id,
                "label": name,
                "description": profile_id,
                "xkb_file": xkb_file,
            })

    # También mostrar archivos XKB propios aunque no tengan perfil JSON.
    if symbols_dir.exists():
        for xkb_file in sorted(symbols_dir.iterdir()):
            if not xkb_file.is_file():
                continue

            profile_id = xkb_file.name

            # Evita duplicar layouts de sistema copiados o perfiles ya detectados.
            if profile_id in seen_ids:
                continue

            # Archivos ocultos, backups o temporales no deberían salir como configuración.
            if profile_id.startswith(".") or profile_id.endswith(("~", ".bak", ".tmp")):
                continue

            seen_ids.add(profile_id)

            out.append({
                "section": "UOK",
                "kind": "uok",
                "id": f"uok:{profile_id}",
                "source_id": profile_id,
                "include": profile_id,
                "label": profile_id,
                "description": str(xkb_file),
                "xkb_file": str(xkb_file),
            })

    return out


def parse_system_xkb_sources():
    xml_file = next((p for p in SYSTEM_RULE_FILES if p.exists()), None)

    if not xml_file:
        return []

    tree = ET.parse(xml_file)
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

        out.append({
            "section": "Others",
            "kind": "system-other",
            "id": f"other:{layout_name}",
            "source_id": layout_name,
            "include": layout_name,
            "label": layout_desc,
            "description": layout_name,
            "xkb_file": "",
        })

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

            source_id = f"{layout_name}+{variant_name}"
            include = f"{layout_name}({variant_name})"

            out.append({
                "section": "Others",
                "kind": "system-other",
                "id": f"other:{source_id}",
                "source_id": source_id,
                "include": include,
                "label": variant_desc,
                "description": source_id,
                "xkb_file": "",
            })

    return out



def read_gnome_input_sources_added():
    """
    Lee fuentes añadidas en GNOME/Cinnamon:
    org.gnome.desktop.input-sources sources

    Devuelve elementos compatibles con el editor visual.
    """
    out = []
    seen = set()

    try:
        result = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.input-sources", "sources"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return out

    if result.returncode != 0:
        return out

    entries = re.findall(r"\('([^']+)',\s*'([^']+)'\)", result.stdout)

    for kind, value in entries:
        if kind != "xkb":
            continue

        raw = (value or "").strip()

        if not raw:
            continue

        if "+" in raw:
            layout, variant = raw.split("+", 1)
            include = f"{layout}({variant})"
            source_id = raw
        elif "(" in raw and raw.endswith(")"):
            layout, variant = raw[:-1].split("(", 1)
            include = raw
            source_id = f"{layout}+{variant}"
        else:
            layout, variant = raw, ""
            include = layout
            source_id = layout

        if source_id in seen:
            continue

        seen.add(source_id)

        label = layout_label(layout, variant) if "layout_label" in globals() else source_id

        out.append({
            "section": "Added to system",
            "kind": "gnome-input-source",
            "id": f"gnome-source:{source_id}",
            "source_id": source_id,
            "include": include,
            "label": label,
            "description": source_id,
            "xkb_file": "",
        })

    return out


def merge_gnome_input_sources_added(items):
    added = read_gnome_input_sources_added()

    if not added:
        return items

    seen = set()
    merged = []

    for item in added:
        key = item.get("source_id") or item.get("include") or item.get("id")

        if key in seen:
            continue

        seen.add(key)
        merged.append(item)

    for item in items:
        key = item.get("source_id") or item.get("include") or item.get("id")

        if key in seen and item.get("section") != "UOK":
            continue

        merged.append(item)

    return merged



def read_libgnomekbd_keyboard_layouts_added():
    """
    Lee distribuciones añadidas por Cinnamon/libgnomekbd:
    org.gnome.libgnomekbd.keyboard layouts
    """
    import os
    import re
    import subprocess

    desktop = " ".join([
        os.environ.get("XDG_CURRENT_DESKTOP", ""),
        os.environ.get("DESKTOP_SESSION", ""),
        os.environ.get("XDG_SESSION_DESKTOP", ""),
    ]).lower()

    if "cinnamon" not in desktop:
        return []

    try:
        result = subprocess.run(
            ["gsettings", "get", "org.gnome.libgnomekbd.keyboard", "layouts"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return []

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
            include = f"{layout}({variant})"
            source_id = raw
        elif "(" in raw and raw.endswith(")"):
            layout, variant = raw[:-1].split("(", 1)
            include = raw
            source_id = f"{layout}+{variant}"
        else:
            layout, variant = raw, ""
            include = layout
            source_id = layout

        if source_id in seen:
            continue

        seen.add(source_id)

        try:
            label = layout_label(layout, variant)
        except Exception:
            label = source_id

        out.append({
            "section": "Added to system",
            "kind": "libgnomekbd-layout",
            "id": f"libgnomekbd:{source_id}",
            "source_id": source_id,
            "include": include,
            "label": label,
            "description": source_id,
            "xkb_file": "",
        })

    return out


def merge_libgnomekbd_keyboard_layouts_added(items):
    added = read_libgnomekbd_keyboard_layouts_added()

    if not added:
        return items

    seen = set()
    merged = []

    for item in added:
        key = item.get("source_id") or item.get("include") or item.get("id")

        if key in seen:
            continue

        seen.add(key)
        merged.append(item)

    for item in items:
        key = item.get("source_id") or item.get("include") or item.get("id")

        if key in seen and item.get("section") != "UOK":
            continue

        merged.append(item)

    return merged




# --------------------------------------------------------------------
# UOK desktop compatibility overrides: XFCE sources for visual editor
# --------------------------------------------------------------------

def uok_desktop_name():
    return ":".join([
        os.environ.get("XDG_CURRENT_DESKTOP", ""),
        os.environ.get("DESKTOP_SESSION", ""),
    ]).lower()


def uok_is_xfce():
    return "xfce" in uok_desktop_name()


def uok_split_csv(value):
    return [x.strip() for x in (value or "").split(",") if x.strip()]


def uok_source_id_from_layout_variant(layout, variant=""):
    layout = (layout or "").strip()
    variant = (variant or "").strip()

    if not layout:
        return ""

    return f"{layout}+{variant}" if variant else layout


def uok_make_added_item(source_id, kind="system-added"):
    include = source_id_to_include(source_id)

    return {
        "section": "Added to system",
        "kind": kind,
        "id": f"added:{source_id}",
        "source_id": source_id,
        "include": include,
        "label": include,
        "description": "",
        "xkb_file": "",
    }


def uok_read_setxkbmap_added_sources():
    result = run(["setxkbmap", "-query"])
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

    out = []

    for layout, variant in zip(layouts, variants):
        source_id = uok_source_id_from_layout_variant(layout, variant)
        if source_id:
            out.append(uok_make_added_item(source_id, "xkb-active"))

    return out


def uok_xfconf_get(prop):
    result = run(["xfconf-query", "-c", "keyboard-layout", "-p", prop])
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def uok_read_xfce_added_sources():
    layouts = uok_split_csv(uok_xfconf_get("/Default/XkbLayout"))
    variants_raw = uok_xfconf_get("/Default/XkbVariant")
    variants = [x.strip() for x in variants_raw.split(",")] if variants_raw else []

    while len(variants) < len(layouts):
        variants.append("")

    out = []

    for layout, variant in zip(layouts, variants):
        source_id = uok_source_id_from_layout_variant(layout, variant)
        if source_id:
            out.append(uok_make_added_item(source_id, "xfce-added"))

    return out


def uok_read_gnome_added_sources():
    return read_gnome_added_sources()


def uok_unique_added_items(items):
    out = []
    seen = set()

    for item in items:
        key = item.get("source_id", "")
        if not key or key in seen:
            continue

        seen.add(key)
        out.append(item)

    return out


def uok_read_added_sources():
    if uok_is_xfce():
        active = uok_read_setxkbmap_added_sources()
        xfce = uok_read_xfce_added_sources()

        if len(active) >= 2:
            return uok_unique_added_items(active)

        if xfce:
            return uok_unique_added_items(xfce)

        return uok_unique_added_items(active)

    return uok_unique_added_items(uok_read_gnome_added_sources())





# --------------------------------------------------------------------
# UOK desktop compatibility overrides: XFCE visual editor sources v2
# --------------------------------------------------------------------

def uok_desktop_name():
    return ":".join([
        os.environ.get("XDG_CURRENT_DESKTOP", ""),
        os.environ.get("DESKTOP_SESSION", ""),
    ]).lower()


def uok_is_xfce():
    return "xfce" in uok_desktop_name()


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


def uok_make_added_item(source_id, kind="system-added"):
    include = source_id_to_include(source_id)

    return {
        "section": "Added to system",
        "kind": kind,
        "id": f"added:{source_id}",
        "source_id": source_id,
        "include": include,
        "label": include,
        "description": "",
        "xkb_file": "",
    }


def uok_unique_added_items(items):
    out = []
    seen = set()

    for item in items:
        key = item.get("source_id", "")
        if not key or key in seen:
            continue

        seen.add(key)
        out.append(item)

    return out


def uok_xfconf_get(channel, prop):
    result = run(["xfconf-query", "-c", channel, "-p", prop])
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def uok_xfconf_list(channel):
    result = run(["xfconf-query", "-c", channel, "-l"])
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def uok_xfconf_values(channel, prop):
    result = run(["xfconf-query", "-c", channel, "-p", prop])
    if result.returncode != 0:
        return []

    values = []

    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue

        if ":" in line:
            line = line.split(":", 1)[1].strip()

        for part in line.split(","):
            part = part.strip()
            if part:
                values.append(part)

    return values


def uok_read_setxkbmap_added_sources():
    result = run(["setxkbmap", "-query"])
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

    out = []

    for layout, variant in zip(layouts, variants):
        source_id = uok_source_id_from_layout_variant(layout, variant)
        if source_id:
            out.append(uok_make_added_item(source_id, "xkb-active"))

    return out


def uok_read_xfce_keyboard_sources():
    layouts = uok_split_csv_nonempty(
        uok_xfconf_get("keyboard-layout", "/Default/XkbLayout")
    )
    variants = uok_split_csv_keep_empty(
        uok_xfconf_get("keyboard-layout", "/Default/XkbVariant")
    )

    while len(variants) < len(layouts):
        variants.append("")

    out = []

    for layout, variant in zip(layouts, variants):
        source_id = uok_source_id_from_layout_variant(layout, variant)
        if source_id:
            out.append(uok_make_added_item(source_id, "xfce-keyboard"))

    return out


def uok_xfce_plugin_ids():
    ids = []

    for prop in uok_xfconf_list("xfce4-panel"):
        m = re.fullmatch(r"/plugins/plugin-(\d+)", prop)
        if not m:
            continue

        plugin_id = m.group(1)
        name = uok_xfconf_get("xfce4-panel", f"/plugins/plugin-{plugin_id}").lower()

        if "xkb" in name or "keyboard-layout" in name or "keyboard layouts" in name:
            ids.append(int(plugin_id))

    return ids


def uok_read_xfce_panel_plugin_sources():
    out = []

    for plugin_id in uok_xfce_plugin_ids():
        prefix = f"/plugins/plugin-{plugin_id}"
        props = [
            prop for prop in uok_xfconf_list("xfce4-panel")
            if prop == prefix or prop.startswith(prefix + "/")
        ]

        layouts = []
        variants = []

        for prop in props:
            low = prop.lower()

            if "layout" in low and not low.endswith("display-name"):
                layouts.extend(uok_xfconf_values("xfce4-panel", prop))

            if "variant" in low:
                variants.extend(uok_xfconf_values("xfce4-panel", prop))

        clean_layouts = []
        for value in layouts:
            value = value.strip()
            if re.fullmatch(r"[a-z]{2,3}([+_][A-Za-z0-9_-]+)?", value):
                clean_layouts.append(value.replace("_", "+"))

        clean_variants = []
        for value in variants:
            value = value.strip()
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
                out.append(uok_make_added_item(source_id, "xfce-panel-plugin"))

    return out


def uok_read_added_sources():
    if uok_is_xfce():
        items = []
        items.extend(uok_read_xfce_panel_plugin_sources())
        items.extend(uok_read_xfce_keyboard_sources())
        items.extend(uok_read_setxkbmap_added_sources())
        return uok_unique_added_items(items)

    return uok_unique_added_items(read_gnome_added_sources())





# --------------------------------------------------------------------
# UOK desktop compatibility overrides: XFCE visual editor sources v3
# --------------------------------------------------------------------

def uok_desktop_name():
    return ":".join([
        os.environ.get("XDG_CURRENT_DESKTOP", ""),
        os.environ.get("DESKTOP_SESSION", ""),
    ]).lower()


def uok_is_xfce():
    return "xfce" in uok_desktop_name()


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


def uok_make_added_item(source_id, kind="system-added"):
    include = source_id_to_include(source_id)

    return {
        "section": "Added to system",
        "kind": kind,
        "id": f"added:{source_id}",
        "source_id": source_id,
        "include": include,
        "label": include,
        "description": "",
        "xkb_file": "",
    }


def uok_unique_added_items(items):
    out = []
    seen = set()

    for item in items:
        key = item.get("source_id", "")
        if not key or key in seen:
            continue

        seen.add(key)
        out.append(item)

    return out


def uok_xfconf_get(channel, prop):
    result = run(["xfconf-query", "-c", channel, "-p", prop])
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def uok_read_setxkbmap_added_sources():
    result = run(["setxkbmap", "-query"])
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

    out = []

    for layout, variant in zip(layouts, variants):
        source_id = uok_source_id_from_layout_variant(layout, variant)
        if source_id:
            out.append(uok_make_added_item(source_id, "xkb-active"))

    return out


def uok_read_xfce_keyboard_sources():
    layouts = uok_split_csv_nonempty(
        uok_xfconf_get("keyboard-layout", "/Default/XkbLayout")
    )
    variants = uok_split_csv_keep_empty(
        uok_xfconf_get("keyboard-layout", "/Default/XkbVariant")
    )

    while len(variants) < len(layouts):
        variants.append("")

    out = []

    for layout, variant in zip(layouts, variants):
        source_id = uok_source_id_from_layout_variant(layout, variant)
        if source_id:
            out.append(uok_make_added_item(source_id, "xfce-keyboard"))

    return out


def uok_xkb_plugin_rc_files():
    panel_dir = Path.home() / ".config" / "xfce4" / "panel"
    if not panel_dir.exists():
        return []

    return sorted(panel_dir.glob("xkb-plugin-*.rc"))


def uok_parse_xkb_plugin_rc_file(path):
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
            layouts.extend(uok_split_csv_nonempty(value))

        if key in {"variant", "variants", "kbd_variants", "model_variants"}:
            variants.extend(uok_split_csv_keep_empty(value))

    if not layouts:
        for m in re.finditer(r"(?im)^\s*[^=\n]*layout[^=\n]*=\s*([^\n]+)$", text):
            layouts.extend(uok_split_csv_nonempty(m.group(1).strip()))

    if not variants:
        for m in re.finditer(r"(?im)^\s*[^=\n]*variant[^=\n]*=\s*([^\n]+)$", text):
            variants.extend(uok_split_csv_keep_empty(m.group(1).strip()))

    clean_layouts = []

    for value in layouts:
        value = value.strip()
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

    out = []

    for layout, variant in zip(clean_layouts, clean_variants):
        source_id = layout if "+" in layout else uok_source_id_from_layout_variant(layout, variant)

        if source_id:
            out.append(uok_make_added_item(source_id, "xfce-xkb-plugin"))

    return out


def uok_read_xkb_plugin_sources():
    out = []

    for file in uok_xkb_plugin_rc_files():
        out.extend(uok_parse_xkb_plugin_rc_file(file))

    return out


def uok_read_added_sources():
    if uok_is_xfce():
        items = []
        items.extend(uok_read_xkb_plugin_sources())
        items.extend(uok_read_xfce_keyboard_sources())
        items.extend(uok_read_setxkbmap_added_sources())
        return uok_unique_added_items(items)

    return uok_unique_added_items(read_gnome_added_sources())





# --------------------------------------------------------------------
# UOK XFCE compatibility override v5 for visual editor
# --------------------------------------------------------------------

def uok_v5_sources_desktop_name():
    return ":".join([
        os.environ.get("XDG_CURRENT_DESKTOP", ""),
        os.environ.get("DESKTOP_SESSION", ""),
    ]).lower()


def uok_v5_sources_is_xfce():
    return "xfce" in uok_v5_sources_desktop_name()


def uok_v5_sources_make_item(source_id, kind):
    include = source_id_to_include(source_id)

    return {
        "section": "Added to system",
        "kind": kind,
        "id": f"added:{source_id}",
        "source_id": source_id,
        "include": include,
        "label": include,
        "description": "",
        "xkb_file": "",
    }


def uok_v5_sources_unique(items):
    out = []
    seen = set()

    for item in items:
        source_id = item.get("source_id", "")
        if not source_id or source_id in seen:
            continue

        seen.add(source_id)
        out.append(item)

    return out


def uok_v5_sources_from_keyboard_layout():
    result = run(["xfconf-query", "-c", "keyboard-layout", "-p", "/Default/XkbLayout"])
    if result.returncode != 0:
        return []

    return [
        uok_v5_sources_make_item(layout, "xfce-keyboard")
        for layout in [x.strip() for x in result.stdout.strip().split(",") if x.strip()]
    ]


def uok_v5_sources_from_setxkbmap():
    result = run(["setxkbmap", "-query"])
    if result.returncode != 0:
        return []

    items = []

    for line in result.stdout.splitlines():
        if line.strip().startswith("layout:"):
            layouts = [x.strip() for x in line.split(":", 1)[1].split(",") if x.strip()]
            for layout in layouts:
                items.append(uok_v5_sources_make_item(layout, "xkb-active"))

    return items


def uok_v5_sources_from_gnome():
    return read_gnome_added_sources()





# --------------------------------------------------------------------
# UOK XFCE compatibility override v6 for visual editor: IBus sources
# --------------------------------------------------------------------

def uok_v6_sources_desktop_name():
    return ":".join([
        os.environ.get("XDG_CURRENT_DESKTOP", ""),
        os.environ.get("DESKTOP_SESSION", ""),
    ]).lower()


def uok_v6_sources_is_xfce():
    return "xfce" in uok_v6_sources_desktop_name()


def uok_v6_sources_make_item(source_id, kind):
    include = source_id_to_include(source_id)

    return {
        "section": "Added to system",
        "kind": kind,
        "id": f"added:{source_id}",
        "source_id": source_id,
        "include": include,
        "label": include,
        "description": "",
        "xkb_file": "",
    }


def uok_v6_sources_unique(items):
    out = []
    seen = set()

    for item in items:
        source_id = item.get("source_id", "")
        if not source_id or source_id in seen:
            continue

        seen.add(source_id)
        out.append(item)

    return out


def uok_v6_sources_from_keyboard_layout():
    result = run(["xfconf-query", "-c", "keyboard-layout", "-p", "/Default/XkbLayout"])
    if result.returncode != 0:
        return []

    return [
        uok_v6_sources_make_item(layout, "xfce-keyboard")
        for layout in [x.strip() for x in result.stdout.strip().split(",") if x.strip()]
    ]


def uok_v6_sources_from_setxkbmap():
    result = run(["setxkbmap", "-query"])
    if result.returncode != 0:
        return []

    items = []

    for line in result.stdout.splitlines():
        if line.strip().startswith("layout:"):
            layouts = [x.strip() for x in line.split(":", 1)[1].split(",") if x.strip()]
            for layout in layouts:
                items.append(uok_v6_sources_make_item(layout, "xkb-active"))

    return items


def uok_v6_ibus_engine_to_source_id(engine):
    engine = (engine or "").strip()

    if not engine.startswith("xkb:"):
        return ""

    parts = engine.split(":")

    if len(parts) < 2:
        return ""

    layout = parts[1].strip()
    variant = parts[2].strip() if len(parts) >= 3 else ""

    if not layout:
        return ""

    return f"{layout}+{variant}" if variant else layout


def uok_v6_sources_from_ibus():
    items = []

    for key in ["preload-engines", "engines-order"]:
        result = run(["gsettings", "get", "org.freedesktop.ibus.general", key])

        if result.returncode != 0:
            continue

        try:
            engines = ast.literal_eval(result.stdout.strip())
        except Exception:
            engines = re.findall(r"'([^']+)'", result.stdout)

        for engine in engines:
            source_id = uok_v6_ibus_engine_to_source_id(engine)
            if source_id:
                items.append(uok_v6_sources_make_item(source_id, "ibus"))

    return items


def load_xkb_sources(current_profile_file, profiles_dir):
    uok_items = read_uok_profiles(profiles_dir)

    if uok_v6_sources_is_xfce():
        added_items = []
        added_items.extend(uok_v6_sources_from_keyboard_layout())
        added_items.extend(uok_v6_sources_from_setxkbmap())
        added_items.extend(read_gnome_added_sources())
        added_items.extend(uok_v6_sources_from_ibus())
        added_items = uok_v6_sources_unique(added_items)
    else:
        added_items = read_gnome_added_sources()

    system_items = parse_system_xkb_sources()

    added_source_ids = {item["source_id"] for item in added_items}
    added_includes = {item["include"] for item in added_items}

    system_by_source_id = {item["source_id"]: item for item in system_items}
    system_by_include = {item["include"]: item for item in system_items}

    for item in added_items:
        match = system_by_source_id.get(item["source_id"]) or system_by_include.get(item["include"])
        if match:
            item["label"] = match["label"]
            item["description"] = match["description"]

    other_items = [
        item
        for item in system_items
        if item["source_id"] not in added_source_ids and item["include"] not in added_includes
    ]

    return merge_libgnomekbd_keyboard_layouts_added(merge_gnome_input_sources_added(uok_items + added_items + other_items))


# --------------------------------------------------------------------
# UOK KDE Plasma visual editor sources override
# --------------------------------------------------------------------
# Sólo KDE/Plasma:
# - lee ~/.config/kxkbrc
# - lee setxkbmap -query
# - lee IBus, porque KDE puede mostrar fuentes desde IBus también
# GNOME/XFCE/Cinnamon quedan como estaban.

try:
    __uok_kde_editor_base_read_added_sources = read_added_sources
except Exception:
    def __uok_kde_editor_base_read_added_sources():
        return []


def uok_kde_editor_desktop_name():
    return " ".join([
        os.environ.get("XDG_CURRENT_DESKTOP", ""),
        os.environ.get("DESKTOP_SESSION", ""),
        os.environ.get("XDG_SESSION_DESKTOP", ""),
    ]).lower()


def uok_kde_editor_is_kde():
    desktop = uok_kde_editor_desktop_name()
    return "kde" in desktop or "plasma" in desktop


def uok_kde_editor_unique_items(items):
    out = []
    seen = set()

    for item in items:
        source_id = item.get("source_id", "")
        if not source_id or source_id in seen:
            continue

        seen.add(source_id)
        out.append(item)

    return out


def uok_kde_editor_source_id_from_layout_variant(layout, variant=""):
    layout = (layout or "").strip()
    variant = (variant or "").strip()

    if not layout:
        return ""

    return f"{layout}+{variant}" if variant else layout


def uok_kde_editor_sources_from_kxkbrc():
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
            layouts = [x.strip() for x in value.split(",") if x.strip()]
        elif key in {"variantlist", "variants"}:
            variants = [x.strip() for x in value.split(",")]

    while len(variants) < len(layouts):
        variants.append("")

    out = []

    for layout, variant in zip(layouts, variants):
        source_id = uok_kde_editor_source_id_from_layout_variant(layout, variant)
        if source_id:
            out.append(make_added_item(source_id, "kde-kxkbrc"))

    return out


def uok_kde_editor_sources_from_setxkbmap():
    return read_setxkbmap_added_sources()


def uok_kde_editor_read_gsettings_array(schema, key):
    result = run(["gsettings", "get", schema, key])

    if result.returncode != 0:
        return []

    try:
        import ast
        value = ast.literal_eval(result.stdout.strip())
    except Exception:
        return []

    if isinstance(value, (list, tuple)):
        return [str(x) for x in value]

    return []


def uok_kde_editor_ibus_engine_to_source_id(engine):
    engine = str(engine or "").strip().strip("'\"")

    if not engine.startswith("xkb:"):
        return ""

    parts = engine.split(":")

    if len(parts) < 2:
        return ""

    layout = parts[1].strip()
    variant = parts[2].strip() if len(parts) >= 3 else ""

    if not layout:
        return ""

    return uok_kde_editor_source_id_from_layout_variant(layout, variant)


def uok_kde_editor_sources_from_ibus():
    engines = []

    for key in ("engines-order", "preload-engines"):
        for engine in uok_kde_editor_read_gsettings_array("org.freedesktop.ibus.general", key):
            if engine not in engines:
                engines.append(engine)

    out = []

    for engine in engines:
        source_id = uok_kde_editor_ibus_engine_to_source_id(engine)
        if source_id:
            out.append(make_added_item(source_id, "kde-ibus"))

    return out


def read_added_sources():
    if not uok_kde_editor_is_kde():
        return __uok_kde_editor_base_read_added_sources()

    items = []

    items.extend(uok_kde_editor_sources_from_kxkbrc())
    items.extend(uok_kde_editor_sources_from_setxkbmap())
    items.extend(uok_kde_editor_sources_from_ibus())

    return uok_kde_editor_unique_items(items)

# --------------------------------------------------------------------
# UOK KDE Plasma visual editor sources override
# --------------------------------------------------------------------
# Sólo KDE/Plasma:
# - lee ~/.config/kxkbrc
# - lee setxkbmap -query
# - lee IBus, porque KDE puede mostrar fuentes desde IBus también
# GNOME/XFCE/Cinnamon quedan como estaban.

try:
    __uok_kde_editor_base_read_added_sources = read_added_sources
except Exception:
    def __uok_kde_editor_base_read_added_sources():
        return []


def uok_kde_editor_desktop_name():
    return " ".join([
        os.environ.get("XDG_CURRENT_DESKTOP", ""),
        os.environ.get("DESKTOP_SESSION", ""),
        os.environ.get("XDG_SESSION_DESKTOP", ""),
    ]).lower()


def uok_kde_editor_is_kde():
    desktop = uok_kde_editor_desktop_name()
    return "kde" in desktop or "plasma" in desktop


def uok_kde_editor_unique_items(items):
    out = []
    seen = set()

    for item in items:
        source_id = item.get("source_id", "")
        if not source_id or source_id in seen:
            continue

        seen.add(source_id)
        out.append(item)

    return out


def uok_kde_editor_source_id_from_layout_variant(layout, variant=""):
    layout = (layout or "").strip()
    variant = (variant or "").strip()

    if not layout:
        return ""

    return f"{layout}+{variant}" if variant else layout


def uok_kde_editor_sources_from_kxkbrc():
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
            layouts = [x.strip() for x in value.split(",") if x.strip()]
        elif key in {"variantlist", "variants"}:
            variants = [x.strip() for x in value.split(",")]

    while len(variants) < len(layouts):
        variants.append("")

    out = []

    for layout, variant in zip(layouts, variants):
        source_id = uok_kde_editor_source_id_from_layout_variant(layout, variant)
        if source_id:
            out.append(make_added_item(source_id, "kde-kxkbrc"))

    return out


def uok_kde_editor_sources_from_setxkbmap():
    return read_setxkbmap_added_sources()


def uok_kde_editor_read_gsettings_array(schema, key):
    result = run(["gsettings", "get", schema, key])

    if result.returncode != 0:
        return []

    try:
        import ast
        value = ast.literal_eval(result.stdout.strip())
    except Exception:
        return []

    if isinstance(value, (list, tuple)):
        return [str(x) for x in value]

    return []


def uok_kde_editor_ibus_engine_to_source_id(engine):
    engine = str(engine or "").strip().strip("'\"")

    if not engine.startswith("xkb:"):
        return ""

    parts = engine.split(":")

    if len(parts) < 2:
        return ""

    layout = parts[1].strip()
    variant = parts[2].strip() if len(parts) >= 3 else ""

    if not layout:
        return ""

    return uok_kde_editor_source_id_from_layout_variant(layout, variant)


def uok_kde_editor_sources_from_ibus():
    engines = []

    for key in ("engines-order", "preload-engines"):
        for engine in uok_kde_editor_read_gsettings_array("org.freedesktop.ibus.general", key):
            if engine not in engines:
                engines.append(engine)

    out = []

    for engine in engines:
        source_id = uok_kde_editor_ibus_engine_to_source_id(engine)
        if source_id:
            out.append(make_added_item(source_id, "kde-ibus"))

    return out


def read_added_sources():
    if not uok_kde_editor_is_kde():
        return __uok_kde_editor_base_read_added_sources()

    items = []

    items.extend(uok_kde_editor_sources_from_kxkbrc())
    items.extend(uok_kde_editor_sources_from_setxkbmap())
    items.extend(uok_kde_editor_sources_from_ibus())

    return uok_kde_editor_unique_items(items)

# --------------------------------------------------------------------
# UOK KDE Plasma visual editor sources override
# --------------------------------------------------------------------
# Sólo KDE/Plasma:
# - lee ~/.config/kxkbrc
# - lee setxkbmap -query
# - lee IBus, porque KDE puede mostrar fuentes desde IBus también
# GNOME/XFCE/Cinnamon quedan como estaban.

try:
    __uok_kde_editor_base_read_added_sources = read_added_sources
except Exception:
    def __uok_kde_editor_base_read_added_sources():
        return []


def uok_kde_editor_desktop_name():
    return " ".join([
        os.environ.get("XDG_CURRENT_DESKTOP", ""),
        os.environ.get("DESKTOP_SESSION", ""),
        os.environ.get("XDG_SESSION_DESKTOP", ""),
    ]).lower()


def uok_kde_editor_is_kde():
    desktop = uok_kde_editor_desktop_name()
    return "kde" in desktop or "plasma" in desktop


def uok_kde_editor_unique_items(items):
    out = []
    seen = set()

    for item in items:
        source_id = item.get("source_id", "")
        if not source_id or source_id in seen:
            continue

        seen.add(source_id)
        out.append(item)

    return out


def uok_kde_editor_source_id_from_layout_variant(layout, variant=""):
    layout = (layout or "").strip()
    variant = (variant or "").strip()

    if not layout:
        return ""

    return f"{layout}+{variant}" if variant else layout


def uok_kde_editor_sources_from_kxkbrc():
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
            layouts = [x.strip() for x in value.split(",") if x.strip()]
        elif key in {"variantlist", "variants"}:
            variants = [x.strip() for x in value.split(",")]

    while len(variants) < len(layouts):
        variants.append("")

    out = []

    for layout, variant in zip(layouts, variants):
        source_id = uok_kde_editor_source_id_from_layout_variant(layout, variant)
        if source_id:
            out.append(make_added_item(source_id, "kde-kxkbrc"))

    return out


def uok_kde_editor_sources_from_setxkbmap():
    return read_setxkbmap_added_sources()


def uok_kde_editor_read_gsettings_array(schema, key):
    result = run(["gsettings", "get", schema, key])

    if result.returncode != 0:
        return []

    try:
        import ast
        value = ast.literal_eval(result.stdout.strip())
    except Exception:
        return []

    if isinstance(value, (list, tuple)):
        return [str(x) for x in value]

    return []


def uok_kde_editor_ibus_engine_to_source_id(engine):
    engine = str(engine or "").strip().strip("'\"")

    if not engine.startswith("xkb:"):
        return ""

    parts = engine.split(":")

    if len(parts) < 2:
        return ""

    layout = parts[1].strip()
    variant = parts[2].strip() if len(parts) >= 3 else ""

    if not layout:
        return ""

    return uok_kde_editor_source_id_from_layout_variant(layout, variant)


def uok_kde_editor_sources_from_ibus():
    engines = []

    for key in ("engines-order", "preload-engines"):
        for engine in uok_kde_editor_read_gsettings_array("org.freedesktop.ibus.general", key):
            if engine not in engines:
                engines.append(engine)

    out = []

    for engine in engines:
        source_id = uok_kde_editor_ibus_engine_to_source_id(engine)
        if source_id:
            out.append(make_added_item(source_id, "kde-ibus"))

    return out


def read_added_sources():
    if not uok_kde_editor_is_kde():
        return __uok_kde_editor_base_read_added_sources()

    items = []

    items.extend(uok_kde_editor_sources_from_kxkbrc())
    items.extend(uok_kde_editor_sources_from_setxkbmap())
    items.extend(uok_kde_editor_sources_from_ibus())

    return uok_kde_editor_unique_items(items)

# --------------------------------------------------------------------
# UOK KDE Plasma final load_xkb_sources override
# --------------------------------------------------------------------
# Este bloque es final y sólo actúa en KDE/Plasma.
# Corrige el editor visual para que "Added to system" muestre:
# - KDE ~/.config/kxkbrc
# - setxkbmap -query
# - IBus
# GNOME/XFCE/Cinnamon delegan en load_xkb_sources anterior.

try:
    __uok_kde_final_base_load_xkb_sources = load_xkb_sources
except Exception:
    __uok_kde_final_base_load_xkb_sources = None


def uok_kde_final_is_kde():
    import os as _os

    desktop = " ".join([
        _os.environ.get("XDG_CURRENT_DESKTOP", ""),
        _os.environ.get("DESKTOP_SESSION", ""),
        _os.environ.get("XDG_SESSION_DESKTOP", ""),
    ]).lower()

    return "kde" in desktop or "plasma" in desktop


def uok_kde_final_source_id(layout, variant=""):
    layout = (layout or "").strip()
    variant = (variant or "").strip()

    if not layout:
        return ""

    return f"{layout}+{variant}" if variant else layout


def uok_kde_final_make_added_item(source_id, kind):
    include = source_id_to_include(source_id)

    return {
        "section": "Added to system",
        "kind": kind,
        "id": f"added:{source_id}",
        "source_id": source_id,
        "include": include,
        "label": include,
        "description": "",
        "xkb_file": "",
    }


def uok_kde_final_unique(items):
    out = []
    seen = set()

    for item in items:
        source_id = item.get("source_id", "")

        if not source_id or source_id in seen:
            continue

        seen.add(source_id)
        out.append(item)

    return out


def uok_kde_final_from_kxkbrc():
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
            layouts = [x.strip() for x in value.split(",") if x.strip()]
        elif key in {"variantlist", "variants"}:
            variants = [x.strip() for x in value.split(",")]

    while len(variants) < len(layouts):
        variants.append("")

    out = []

    for layout, variant in zip(layouts, variants):
        source_id = uok_kde_final_source_id(layout, variant)

        if source_id:
            out.append(uok_kde_final_make_added_item(source_id, "kde-kxkbrc"))

    return out


def uok_kde_final_from_setxkbmap():
    result = run(["setxkbmap", "-query"])

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

    out = []

    for layout, variant in zip(layouts, variants):
        source_id = uok_kde_final_source_id(layout, variant)

        if source_id:
            out.append(uok_kde_final_make_added_item(source_id, "xkb-active"))

    return out


def uok_kde_final_read_gsettings_array(schema, key):
    import ast as _ast

    result = run(["gsettings", "get", schema, key])

    if result.returncode != 0:
        return []

    raw = result.stdout.strip()

    try:
        value = _ast.literal_eval(raw)
    except Exception:
        value = re.findall(r"'([^']+)'", raw)

    if isinstance(value, (list, tuple)):
        return [str(x) for x in value]

    return []


def uok_kde_final_ibus_engine_to_source_id(engine):
    engine = str(engine or "").strip().strip("'\"")

    if not engine.startswith("xkb:"):
        return ""

    parts = engine.split(":")

    if len(parts) < 2:
        return ""

    layout = parts[1].strip()
    variant = parts[2].strip() if len(parts) >= 3 else ""

    if not layout:
        return ""

    return uok_kde_final_source_id(layout, variant)


def uok_kde_final_from_ibus():
    engines = []

    for key in ("engines-order", "preload-engines"):
        for engine in uok_kde_final_read_gsettings_array("org.freedesktop.ibus.general", key):
            if engine not in engines:
                engines.append(engine)

    out = []

    for engine in engines:
        source_id = uok_kde_final_ibus_engine_to_source_id(engine)

        if source_id:
            out.append(uok_kde_final_make_added_item(source_id, "kde-ibus"))

    return out


def load_xkb_sources(current_profile_file, profiles_dir):
    if not uok_kde_final_is_kde():
        if __uok_kde_final_base_load_xkb_sources is not None:
            return __uok_kde_final_base_load_xkb_sources(current_profile_file, profiles_dir)

        uok_items = read_uok_profiles(profiles_dir)
        added_items = read_gnome_added_sources()
        system_items = parse_system_xkb_sources()
        return uok_items + added_items + system_items

    uok_items = read_uok_profiles(profiles_dir)

    added_items = []
    added_items.extend(uok_kde_final_from_kxkbrc())
    added_items.extend(uok_kde_final_from_setxkbmap())
    added_items.extend(uok_kde_final_from_ibus())
    added_items = uok_kde_final_unique(added_items)

    system_items = parse_system_xkb_sources()

    system_by_source_id = {item["source_id"]: item for item in system_items}
    system_by_include = {item["include"]: item for item in system_items}

    for item in added_items:
        match = system_by_source_id.get(item["source_id"]) or system_by_include.get(item["include"])

        if match:
            item["label"] = match["label"]
            item["description"] = match["description"]

    added_source_ids = {item["source_id"] for item in added_items}
    added_includes = {item["include"] for item in added_items}

    other_items = [
        item
        for item in system_items
        if item["source_id"] not in added_source_ids and item["include"] not in added_includes
    ]

    return merge_libgnomekbd_keyboard_layouts_added(merge_gnome_input_sources_added(uok_items + added_items + other_items))

# --------------------------------------------------------------------
# UOK Cinnamon visual editor sources override
# --------------------------------------------------------------------
# Sólo Cinnamon:
# - lee IBus, que es donde Cinnamon suele exponer los teclados añadidos;
# - lee setxkbmap -query, que refleja el XKB activo;
# - conserva el comportamiento anterior para GNOME, XFCE y KDE.

try:
    __uok_cinnamon_editor_base_load_xkb_sources = load_xkb_sources
except Exception:
    __uok_cinnamon_editor_base_load_xkb_sources = None


def uok_cinnamon_editor_is_cinnamon():
    import os as _os

    desktop = " ".join([
        _os.environ.get("XDG_CURRENT_DESKTOP", ""),
        _os.environ.get("DESKTOP_SESSION", ""),
        _os.environ.get("XDG_SESSION_DESKTOP", ""),
    ]).lower()

    return "cinnamon" in desktop


def uok_cinnamon_editor_source_id(layout, variant=""):
    layout = (layout or "").strip()
    variant = (variant or "").strip()

    if not layout:
        return ""

    return f"{layout}+{variant}" if variant else layout


def uok_cinnamon_editor_make_added_item(source_id, kind):
    include = source_id_to_include(source_id)

    return {
        "section": "Added to system",
        "kind": kind,
        "id": f"added:{source_id}",
        "source_id": source_id,
        "include": include,
        "label": include,
        "description": "",
        "xkb_file": "",
    }


def uok_cinnamon_editor_unique(items):
    out = []
    seen = set()

    for item in items:
        source_id = item.get("source_id", "")

        if not source_id or source_id in seen:
            continue

        seen.add(source_id)
        out.append(item)

    return out


def uok_cinnamon_editor_from_setxkbmap():
    result = run(["setxkbmap", "-query"])

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

    out = []

    for layout, variant in zip(layouts, variants):
        source_id = uok_cinnamon_editor_source_id(layout, variant)

        if source_id:
            out.append(uok_cinnamon_editor_make_added_item(source_id, "cinnamon-xkb-active"))

    return out


def uok_cinnamon_editor_read_gsettings_array(schema, key):
    import ast as _ast

    result = run(["gsettings", "get", schema, key])

    if result.returncode != 0:
        return []

    raw = result.stdout.strip()

    try:
        value = _ast.literal_eval(raw)
    except Exception:
        value = re.findall(r"'([^']+)'", raw)

    if isinstance(value, (list, tuple)):
        return [str(x) for x in value]

    return []


def uok_cinnamon_editor_ibus_engine_to_source_id(engine):
    engine = str(engine or "").strip().strip("'\"")

    if not engine.startswith("xkb:"):
        return ""

    parts = engine.split(":")

    if len(parts) < 2:
        return ""

    layout = parts[1].strip()
    variant = parts[2].strip() if len(parts) >= 3 else ""

    if not layout:
        return ""

    return uok_cinnamon_editor_source_id(layout, variant)


def uok_cinnamon_editor_from_ibus():
    engines = []

    for key in ("engines-order", "preload-engines"):
        for engine in uok_cinnamon_editor_read_gsettings_array("org.freedesktop.ibus.general", key):
            if engine not in engines:
                engines.append(engine)

    out = []

    for engine in engines:
        source_id = uok_cinnamon_editor_ibus_engine_to_source_id(engine)

        if source_id:
            out.append(uok_cinnamon_editor_make_added_item(source_id, "cinnamon-ibus"))

    return out


def load_xkb_sources(current_profile_file, profiles_dir):
    if not uok_cinnamon_editor_is_cinnamon():
        if __uok_cinnamon_editor_base_load_xkb_sources is not None:
            return __uok_cinnamon_editor_base_load_xkb_sources(current_profile_file, profiles_dir)

        uok_items = read_uok_profiles(profiles_dir)
        added_items = read_added_sources()
        system_items = parse_system_xkb_sources()
        return uok_items + added_items + system_items

    uok_items = read_uok_profiles(profiles_dir)

    added_items = []
    added_items.extend(read_gnome_added_sources())
    added_items.extend(uok_cinnamon_editor_from_ibus())
    added_items.extend(uok_cinnamon_editor_from_setxkbmap())
    added_items = uok_cinnamon_editor_unique(added_items)

    system_items = parse_system_xkb_sources()

    system_by_source_id = {item["source_id"]: item for item in system_items}
    system_by_include = {item["include"]: item for item in system_items}

    for item in added_items:
        match = system_by_source_id.get(item["source_id"]) or system_by_include.get(item["include"])

        if match:
            item["label"] = match["label"]
            item["description"] = match["description"]

    added_source_ids = {item["source_id"] for item in added_items}
    added_includes = {item["include"] for item in added_items}

    other_items = [
        item
        for item in system_items
        if item["source_id"] not in added_source_ids and item["include"] not in added_includes
    ]

    return merge_libgnomekbd_keyboard_layouts_added(merge_gnome_input_sources_added(uok_items + added_items + other_items))


# --------------------------------------------------------------------
# UOK LXQt source wrapper
# --------------------------------------------------------------------

def uok_lxqt_is_desktop():
    import os

    desktop = " ".join([
        os.environ.get("XDG_CURRENT_DESKTOP", ""),
        os.environ.get("DESKTOP_SESSION", ""),
        os.environ.get("XDG_SESSION_DESKTOP", ""),
    ]).lower()

    return "lxqt" in desktop


def uok_lxqt_sources_from_setxkbmap():
    import re
    import subprocess

    if not uok_lxqt_is_desktop():
        return []

    try:
        result = subprocess.run(
            ["setxkbmap", "-query"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return []

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

        source_id = layout if not variant else f"{layout}+{variant}"
        include = layout if not variant else f"{layout}({variant})"

        if source_id in seen:
            continue

        seen.add(source_id)

        try:
            label = layout_label(layout, variant)
        except Exception:
            label = source_id

        rows.append({
            "section": "Added to system",
            "kind": "lxqt-setxkbmap",
            "id": f"lxqt:{source_id}",
            "source_id": source_id,
            "include": include,
            "label": label,
            "description": source_id,
            "xkb_file": "",
        })

    return rows


def uok_lxqt_merge_sources(items):
    extra = uok_lxqt_sources_from_setxkbmap()

    if not extra:
        return items

    seen = set()
    merged = []

    for item in extra:
        key = item.get("source_id") or item.get("include") or item.get("id")
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)

    for item in items:
        key = item.get("source_id") or item.get("include") or item.get("id")
        if key in seen and item.get("section") != "UOK":
            continue
        merged.append(item)

    return merged


try:
    __uok_base_load_xkb_sources_lxqt = load_xkb_sources

    def load_xkb_sources(current_profile, profiles_dir):
        return uok_lxqt_merge_sources(
            __uok_base_load_xkb_sources_lxqt(current_profile, profiles_dir)
        )
except Exception:
    pass

