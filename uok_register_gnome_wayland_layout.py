#!/usr/bin/env python3
from pathlib import Path
import argparse
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time


EVDEV_XML = Path("/usr/share/X11/xkb/rules/evdev.xml")
EVDEV_LST = Path("/usr/share/X11/xkb/rules/evdev.lst")
XKB_DTD = Path("/usr/share/X11/xkb/rules/xkb.dtd")
SYSTEM_SYMBOLS = Path("/usr/share/X11/xkb/symbols")


def run(cmd, *, check=False, capture=False):
    print("+", " ".join(str(x) for x in cmd))
    return subprocess.run(
        [str(x) for x in cmd],
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        check=check,
    )


def sudo_copy(src: Path, dst: Path):
    run(["sudo", "cp", str(src), str(dst)], check=True)


def sudo_install_file(src: Path, dst: Path, mode="0644"):
    run(["sudo", "install", "-m", mode, str(src), str(dst)], check=True)


def backup(path: Path):
    if not path.exists():
        return None
    stamp = time.strftime("%Y%m%d-%H%M%S")
    dst = Path("/tmp") / f"{path.name}.uok-backup-{stamp}"
    run(["cp", str(path), str(dst)], check=True)
    print(f"Backup: {dst}")
    return dst


def validate_layout_id(layout_id: str):
    if not re.fullmatch(r"[A-Za-z0-9_]+", layout_id):
        raise SystemExit(f"Layout id inválido: {layout_id!r}")


def symbol_file_compiles(layout_id: str):
    result = run(
        ["xkbcli", "compile-keymap", "--layout", layout_id],
        capture=True,
    )
    if result.returncode != 0:
        print(result.stdout or "", end="")
        print(result.stderr or "", end="", file=sys.stderr)
        raise SystemExit(f"xkbcli no puede compilar el layout {layout_id}")


def install_symbols(profile_id: str, layout_id: str):
    src = Path.home() / ".xkb" / "symbols" / profile_id
    if not src.exists():
        raise SystemExit(f"No existe el archivo de símbolos: {src}")

    dst = SYSTEM_SYMBOLS / layout_id
    backup(dst)
    sudo_install_file(src, dst)
    symbol_file_compiles(layout_id)


def layout_xml_block(layout_id: str, description: str, short: str):
    return f"""    <layout>
      <configItem>
        <name>{html.escape(layout_id)}</name>
        <shortDescription>{html.escape(short)}</shortDescription>
        <description>{html.escape(description)}</description>
        <languageList>
          <iso639Id>spa</iso639Id>
        </languageList>
      </configItem>
      <variantList/>
    </layout>
"""


def register_evdev_xml(layout_id: str, description: str, short: str):
    if not EVDEV_XML.exists():
        raise SystemExit(f"No existe {EVDEV_XML}")

    text = EVDEV_XML.read_text(encoding="utf-8", errors="strict")

    if f"<name>{layout_id}</name>" in text:
        print(f"{layout_id} ya está registrado en evdev.xml")
        return

    close = "  </layoutList>"
    if close not in text:
        raise SystemExit("No encontré </layoutList> en evdev.xml; no modifico el archivo.")

    backup(EVDEV_XML)

    block = layout_xml_block(layout_id, description, short)
    new_text = text.replace(close, block + close, 1)

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
                raise SystemExit("El evdev.xml generado no valida; no se instala.")

        sudo_copy(tmp, EVDEV_XML)
    finally:
        tmp.unlink(missing_ok=True)


def register_evdev_lst(layout_id: str, description: str):
    if not EVDEV_LST.exists():
        return

    text = EVDEV_LST.read_text(encoding="utf-8", errors="replace")

    if re.search(rf"^\s*{re.escape(layout_id)}\s+", text, re.MULTILINE):
        print(f"{layout_id} ya está registrado en evdev.lst")
        return

    marker = "! layout"
    if marker not in text:
        print("No encontré sección ! layout en evdev.lst; salto evdev.lst.")
        return

    backup(EVDEV_LST)

    lines = text.splitlines()
    out = []
    inserted = False

    for i, line in enumerate(lines):
        out.append(line)
        if not inserted and line.strip() == marker:
            out.append(f"  {layout_id:<22} {description}")
            inserted = True

    new_text = "\n".join(out) + "\n"

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as f:
        tmp = Path(f.name)
        f.write(new_text)

    try:
        sudo_copy(tmp, EVDEV_LST)
    finally:
        tmp.unlink(missing_ok=True)


def reset_gnome_sources(layout_id: str, base_sources):
    sources = list(base_sources)
    custom = ("xkb", layout_id)

    if custom not in sources:
        sources.append(custom)

    literal = "[" + ", ".join(f"('{a}', '{b}')" for a, b in sources) + "]"
    index = sources.index(custom)

    run([
        "gsettings",
        "set",
        "org.gnome.desktop.input-sources",
        "sources",
        literal,
    ], check=True)
    run([
        "gsettings",
        "set",
        "org.gnome.desktop.input-sources",
        "current",
        str(index),
    ], check=True)

    print(f"GNOME sources: {literal}")
    print(f"Índice activado: {index}")


def parse_source_arg(value: str):
    if ":" in value:
        a, b = value.split(":", 1)
        return (a, b)
    return ("xkb", value)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("profile_id", help="ID del perfil UOK, por ejemplo mi_teclado_visual")
    ap.add_argument("--layout-id", help="ID XKB del sistema. Por defecto: uok_<profile_id>")
    ap.add_argument("--description", help="Descripción visible")
    ap.add_argument("--short", default="UOK", help="Short description XKB")
    ap.add_argument("--base-source", action="append", default=["xkb:es", "xkb:de"],
                    help="Fuente base a conservar. Formato xkb:es. Puede repetirse.")
    args = ap.parse_args()

    profile_id = args.profile_id
    layout_id = args.layout_id or f"uok_{profile_id}"
    description = args.description or f"UrOwnKeyboard {profile_id}"

    validate_layout_id(layout_id)

    install_symbols(profile_id, layout_id)
    register_evdev_xml(layout_id, description, args.short)
    register_evdev_lst(layout_id, description)

    # Revalidate registry after registration.
    if shutil.which("xmllint") and XKB_DTD.exists():
        run(["xmllint", "--noout", "--dtdvalid", str(XKB_DTD), str(EVDEV_XML)], check=True)

    symbol_file_compiles(layout_id)

    base_sources = [parse_source_arg(x) for x in args.base_source]
    reset_gnome_sources(layout_id, base_sources)

    print()
    print("Hecho.")
    print("Ahora cierra sesión y vuelve a entrar en GNOME Wayland.")
    print("Después prueba Super+Espacio o UOK con el layout registrado.")


if __name__ == "__main__":
    main()
