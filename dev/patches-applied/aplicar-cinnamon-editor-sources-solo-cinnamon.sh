#!/usr/bin/env bash
set -euo pipefail

if [ ! -f "uok_xkb_sources.py" ]; then
  echo "Ejecuta esto desde la raíz de UrOwnKeyboard."
  exit 1
fi

cp -n uok_xkb_sources.py "uok_xkb_sources.py.bak.cinnamon-editor.$(date +%Y%m%d-%H%M%S)"

cat >> uok_xkb_sources.py <<'PY'

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

    return uok_items + added_items + other_items
PY

python3 -m py_compile uok_xkb_sources.py

echo "OK: editor visual Cinnamon sources aplicado."
