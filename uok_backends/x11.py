import shlex
import subprocess
from .result import ActivationResult
from .session import is_wayland

def run(cmd):
    return subprocess.run(
        [str(x) for x in cmd],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def query():
    return run(["setxkbmap", "-query"])


def parse_query_text(text):
    data = {}

    for line in (text or "").splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip()

    return data


def current_layout():
    result = query()
    if result.returncode != 0:
        return ""
    return parse_query_text(result.stdout).get("layout", "")


def current_variant():
    result = query()
    if result.returncode != 0:
        return ""
    return parse_query_text(result.stdout).get("variant", "")


def current_spec():
    if is_wayland():
        return ""
    result = query()
    if result.returncode != 0:
        return ""
    data = parse_query_text(result.stdout)
    layout_raw = (data.get("layout") or "").strip()
    variant_raw = (data.get("variant") or "").strip()
    if not layout_raw:
        return ""
    layouts = [x.strip() for x in layout_raw.split(",") if x.strip()]
    variants = [x.strip() for x in variant_raw.split(",")] if variant_raw else []
    if not layouts:
        return ""
    while len(variants) < len(layouts):
        variants.append("")
    layout = layouts[0]
    variant = variants[0]
    return f"{layout}({variant})" if variant else layout


def source_to_setxkbmap_cmd(source_type, source_id):
    if source_type != "xkb" or not source_id:
        return None

    if "+" in source_id:
        layout, variant = source_id.split("+", 1)
        return f"setxkbmap {shlex.quote(layout)} {shlex.quote(variant)}"

    return f"setxkbmap {shlex.quote(source_id)}"


def apply_source(source_type, source_id):
    cmd = source_to_setxkbmap_cmd(source_type, source_id)

    if not cmd:
        return ActivationResult.fail(
            "Fuente XKB no válida para X11.",
            f"{source_type}:{source_id}",
        )

    result = run(shlex.split(cmd))

    if result.returncode != 0:
        return ActivationResult.fail(
            "No se pudo aplicar setxkbmap.",
            (result.stdout + "\n" + result.stderr).strip(),
        )

    return ActivationResult.ok_result("Fuente X11 aplicada.")


def verify_source(source_type, source_id):
    if source_type != "xkb":
        return ActivationResult.fail("Solo se verifican fuentes XKB en X11.")

    wanted_layout = source_id.split("+", 1)[0]
    got = current_layout()

    if not got:
        return ActivationResult.fail("No se pudo leer setxkbmap -query.")

    active_layouts = [x.strip() for x in got.split(",") if x.strip()]

    if wanted_layout in active_layouts:
        return ActivationResult.ok_result("Fuente X11 verificada.")

    return ActivationResult.fail(
        "La fuente X11 aplicada no coincide.",
        f"esperado={wanted_layout}, actual={got}",
    )


def verify_current_profile_json(current_profile_path, profile_id):
    try:
        import json
        profile = json.loads(current_profile_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, f"No se pudo leer current-profile.json: {exc}"

    got = profile.get("id") or profile.get("profile_id")

    if got == profile_id:
        return True, "Perfil UOK verificado por current-profile.json."

    return False, f"Perfil activo distinto. esperado={profile_id}, actual={got}"


def rollback_default(layout="es"):
    result = run(["setxkbmap", layout])

    if result.returncode != 0:
        return ActivationResult.fail(
            "No se pudo restaurar layout X11.",
            (result.stdout + "\n" + result.stderr).strip(),
        )

    return ActivationResult.ok_result("Rollback X11 aplicado.")
