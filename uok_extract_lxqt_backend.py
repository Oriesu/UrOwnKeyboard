#!/usr/bin/env python3
from pathlib import Path
import py_compile

ROOT = Path.cwd()
IND = ROOT / "teclado-indicador.py"
BACKENDS = ROOT / "uok_backends"
LXQT = BACKENDS / "lxqt.py"

START1 = "# UOK LXQt: system layouts and native indicator hiding"
END1 = "def crear_menu():"

START2 = "# UOK LXQt helpers"
END2 = "uok_main_menu = crear_menu()"

REPLACEMENT1 = """# UOK LXQt backend delegation
try:
    from uok_backends.lxqt import install as uok_install_lxqt_backend
    uok_install_lxqt_backend(__import__(__name__))
except Exception as exc:
    print(f'UOK LXQt backend disabled: {exc}')

"""


def slice_block(text, start_marker, end_marker):
    start = text.find(start_marker)
    end = text.find(end_marker)

    if start == -1:
        raise SystemExit(f"No encontré marcador inicial: {start_marker}")

    if end == -1 or end <= start:
        raise SystemExit(f"No encontré marcador final válido: {end_marker}")

    return start, end, text[start:end]


def main():
    if not IND.exists():
        raise SystemExit("No encuentro teclado-indicador.py. Ejecuta esto en la raíz del repo.")

    text = IND.read_text(encoding="utf-8")

    start1, end1, block1 = slice_block(text, START1, END1)
    start2, end2, block2 = slice_block(text, START2, END2)

    if start2 <= end1:
        raise SystemExit("Los bloques LXQt no están en el orden esperado; no modifico nada.")

    required1 = [
        "def uok_lxqt_panel_conf_path",
        "def uok_lxqt_append_system_sources_to_menu",
        "def uok_lxqt_remove_legacy_tray_keep_statusnotifier",
    ]
    required2 = [
        "def uok_is_lxqt_desktop",
        "def abrir_ajustes_teclado",
    ]

    missing = [item for item in required1 if item not in block1]
    missing += [item for item in required2 if item not in block2]
    if missing:
        raise SystemExit("Los bloques LXQt no parecen completos. Faltan: " + ", ".join(missing))

    BACKENDS.mkdir(exist_ok=True)

    module_text = (
        "#!/usr/bin/env python3\n"
        "\"\"\"\n"
        "LXQt compatibility backend for UrOwnKeyboard.\n\n"
        "This module executes the previously inline LXQt compatibility blocks\n"
        "inside the indicator module namespace. It is behavior-preserving and\n"
        "keeps teclado-indicador.py smaller without rewriting LXQt logic yet.\n"
        "\"\"\"\n\n"
        "_LXQT_CODE_1 = " + repr(block1) + "\n\n"
        "_LXQT_CODE_2 = " + repr(block2) + "\n\n\n"
        "def install(app):\n"
        "    namespace = app.__dict__\n"
        "    exec(_LXQT_CODE_1, namespace, namespace)\n"
        "    exec(_LXQT_CODE_2, namespace, namespace)\n"
    )

    backup = IND.with_suffix(IND.suffix + ".bak-lxqt-backend")
    backup.write_text(text, encoding="utf-8")

    LXQT.write_text(module_text, encoding="utf-8")

    # Reemplazar de atrás hacia delante para no invalidar índices.
    new_text = text[:start2] + text[end2:]
    new_text = new_text[:start1] + REPLACEMENT1 + new_text[end1:]

    IND.write_text(new_text, encoding="utf-8")

    py_compile.compile(str(IND), doraise=True)
    py_compile.compile(str(LXQT), doraise=True)

    before = len(text.splitlines())
    after = len(new_text.splitlines())
    lxqt_lines = len(module_text.splitlines())

    print("OK: bloques LXQt extraídos sin reescritura lógica.")
    print(f"teclado-indicador.py: {before} -> {after} líneas ({before - after} menos)")
    print(f"uok_backends/lxqt.py: {lxqt_lines} líneas")
    print(f"Backup: {backup}")
    print()
    print("Comprueba:")
    print("  python3 -m py_compile teclado-indicador.py uok uok_backends/*.py")
    print("  grep -n \"UOK LXQt\\|uok_backends.lxqt\\|uok_lxqt\\|uok_is_lxqt\" teclado-indicador.py uok_backends/lxqt.py | head -140")
    print("  wc -l teclado-indicador.py uok_backends/lxqt.py")


if __name__ == "__main__":
    main()
