#!/usr/bin/env python3
from pathlib import Path
import argparse
import ast
import re
import shutil
import subprocess
import sys
import tempfile
import time

EVDEV_XML = Path("/usr/share/X11/xkb/rules/evdev.xml")
EVDEV_LST = Path("/usr/share/X11/xkb/rules/evdev.lst")
XKB_DTD = Path("/usr/share/X11/xkb/rules/xkb.dtd")
SYMBOLS_DIR = Path("/usr/share/X11/xkb/symbols")


def run(cmd, *, capture=False, check=False):
    print("+", " ".join(str(x) for x in cmd))
    return subprocess.run(
        [str(x) for x in cmd],
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        check=check,
    )


def backup(path: Path):
    if not path.exists():
        return None
    stamp = time.strftime("%Y%m%d-%H%M%S")
    dst = Path("/tmp") / f"{path.name}.uok-clean-backup-{stamp}"
    run(["cp", str(path), str(dst)], check=True)
    print(f"Backup: {dst}")
    return dst


def gsettings_sources():
    result = run(
        ["gsettings", "get", "org.gnome.desktop.input-sources", "sources"],
        capture=True,
        check=True,
    )
    text = result.stdout.strip()
    try:
        value = ast.literal_eval(text)
    except Exception:
        print(f"No pude parsear sources: {text}", file=sys.stderr)
        return []
    return [(str(a), str(b)) for a, b in value]


def set_gsettings_sources(sources):
    if not sources:
        sources = [("xkb", "es")]

    literal = "[" + ", ".join(f"('{a}', '{b}')" for a, b in sources) + "]"
    run(["gsettings", "set", "org.gnome.desktop.input-sources", "sources", literal], check=True)
    run(["gsettings", "set", "org.gnome.desktop.input-sources", "current", "0"], check=True)


def remove_from_gsettings(layout_id):
    sources = gsettings_sources()
    new_sources = [(a, b) for a, b in sources if not (a == "xkb" and b == layout_id)]

    if new_sources == sources:
        print(f"{layout_id} no estaba en GNOME sources.")
    else:
        print(f"Quitando {layout_id} de GNOME sources.")
        set_gsettings_sources(new_sources)


def remove_symbols(layout_id):
    path = SYMBOLS_DIR / layout_id
    if path.exists():
        backup(path)
        run(["sudo", "rm", "-f", str(path)], check=True)
    else:
        print(f"No existe {path}")


def remove_evdev_xml(layout_id):
    if not EVDEV_XML.exists():
        print(f"No existe {EVDEV_XML}")
        return

    text = EVDEV_XML.read_text(encoding="utf-8", errors="strict")

    # Remove the exact <layout> block whose configItem/name is layout_id.
    pattern = re.compile(
        r"\n\s*<layout>\s*"
        r"<configItem>.*?"
        r"<name>" + re.escape(layout_id) + r"</name>.*?"
        r"</configItem>\s*"
        r"<variantList\s*/>\s*"
        r"</layout>\s*",
        re.DOTALL,
    )

    new_text, count = pattern.subn("\n", text)

    if count == 0:
        print(f"{layout_id} no aparecía como bloque simple en evdev.xml.")
        return

    backup(EVDEV_XML)

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as f:
        tmp = Path(f.name)
        f.write(new_text)

    try:
        if shutil.which("xmllint") and XKB_DTD.exists():
            result = run(
                ["xmllint", "--noout", "--dtdvalid", str(XKB_DTD), str(tmp)],
                capture=True,
            )
            if result.returncode != 0:
                print(result.stdout or "", end="")
                print(result.stderr or "", end="", file=sys.stderr)
                raise SystemExit("El evdev.xml limpiado no valida; no se instala.")

        run(["sudo", "cp", str(tmp), str(EVDEV_XML)], check=True)
    finally:
        tmp.unlink(missing_ok=True)


def remove_evdev_lst(layout_id):
    if not EVDEV_LST.exists():
        return

    text = EVDEV_LST.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    new_lines = [line for line in lines if not re.match(rf"^\s*{re.escape(layout_id)}\s+", line)]

    if len(new_lines) == len(lines):
        print(f"{layout_id} no aparecía en evdev.lst.")
        return

    backup(EVDEV_LST)

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as f:
        tmp = Path(f.name)
        f.write("\n".join(new_lines) + "\n")

    try:
        run(["sudo", "cp", str(tmp), str(EVDEV_LST)], check=True)
    finally:
        tmp.unlink(missing_ok=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("profile_id", help="ID del perfil UOK, por ejemplo mi_teclado_visual")
    ap.add_argument("--layout-id", help="ID XKB del sistema. Por defecto: uok_<profile_id>")
    args = ap.parse_args()

    layout_id = args.layout_id or f"uok_{args.profile_id}"

    if not re.fullmatch(r"[A-Za-z0-9_]+", layout_id):
        raise SystemExit(f"Layout id inválido: {layout_id}")

    remove_from_gsettings(layout_id)
    remove_symbols(layout_id)
    remove_evdev_xml(layout_id)
    remove_evdev_lst(layout_id)

    print()
    print("Limpieza terminada.")
    print("Cierra sesión y vuelve a entrar para que GNOME deje de cachear la fuente eliminada.")
    print("El perfil UOK importado no se ha borrado; solo se ha eliminado la copia registrada como layout del sistema.")


if __name__ == "__main__":
    main()
