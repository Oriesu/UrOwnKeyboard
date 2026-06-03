import ast
import re
import subprocess


def run(cmd):
    try:
        return subprocess.run([str(x) for x in cmd], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    except FileNotFoundError as exc:
        return subprocess.CompletedProcess(cmd, 127, "", str(exc))


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
        out.append((source_type, source_id) if label is None else (source_type, source_id, label))
    return out


def split_csv_nonempty(value):
    return [x.strip() for x in str(value or "").split(",") if x.strip()]


def split_csv_keep_empty(value):
    return [x.strip() for x in str(value or "").split(",")]


def source_id_from_layout_variant(layout, variant=""):
    layout = str(layout or "").strip()
    variant = str(variant or "").strip()
    if not layout:
        return ""
    return f"{layout}+{variant}" if variant else layout


def source_id_to_include(source_id):
    source_id = str(source_id or "").strip()
    if "+" in source_id:
        layout, variant = source_id.split("+", 1)
        return f"{layout}({variant})" if variant else layout
    return source_id


def include_to_source_id(include_name):
    include_name = str(include_name or "").strip()
    match = re.fullmatch(r"([^()]+)\(([^()]+)\)", include_name)
    if match:
        return f"{match.group(1)}+{match.group(2)}"
    return include_name


def normalize_source_id(raw):
    raw = str(raw or "").strip().strip("'\"")
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


def read_gsettings_array(schema, key):
    raw = gsettings_get(schema, key)
    if not raw:
        return []
    try:
        value = ast.literal_eval(raw)
    except Exception:
        value = re.findall(r"'([^']+)'", raw)
    if isinstance(value, (list, tuple)):
        return [str(x) for x in value]
    return []


def xfconf_get(channel, prop):
    result = run(["xfconf-query", "-c", channel, "-p", prop])
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def setxkbmap_layout_variant_pairs():
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
    return list(zip(layouts, variants))


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
