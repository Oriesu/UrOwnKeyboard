#!/usr/bin/env python3
import json
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


def read_gnome_added_sources():
    result = run(["gsettings", "get", "org.gnome.desktop.input-sources", "sources"])
    if result.returncode != 0:
        return []

    out = []

    for source_type, source_id in re.findall(r"\('([^']+)'\s*,\s*'([^']+)'\)", result.stdout):
        if source_type != "xkb":
            continue

        include = source_id_to_include(source_id)
        out.append({
            "section": "Added to system",
            "kind": "system-added",
            "id": f"added:{source_id}",
            "source_id": source_id,
            "include": include,
            "label": include,
            "description": "",
            "xkb_file": "",
        })

    return out


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


def load_xkb_sources(current_profile_file, profiles_dir):
    uok_items = read_uok_profiles(profiles_dir)
    added_items = read_gnome_added_sources()
    system_items = parse_system_xkb_sources()

    added_source_ids = {item["source_id"] for item in added_items}
    added_includes = {item["include"] for item in added_items}

    # Mejorar etiquetas de "Added to system" usando la descripción de evdev.xml.
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

    return uok_items + added_items + other_items
