#!/usr/bin/env python3
from pathlib import Path
import py_compile

ROOT = Path.cwd()
IND = ROOT / "teclado-indicador.py"
BACKENDS = ROOT / "uok_backends"
CIN = BACKENDS / "cinnamon.py"

START1 = "# UOK Cinnamon: system layouts from libgnomekbd"
END1 = "# UOK LXQt backend delegation"

START2 = "# UOK Cinnamon-only compatibility override"
END2 = "# UOK KDE backend delegation"

REPLACEMENT = """# UOK Cinnamon backend delegation
try:
    from uok_backends.cinnamon import install as uok_install_cinnamon_backend
    uok_install_cinnamon_backend(__import__(__name__))
except Exception as exc:
    print(f'UOK Cinnamon backend disabled: {exc}')

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
        raise SystemExit("Los bloques Cinnamon no están en el orden esperado; no modifico nada.")

    required1 = [
        "def uok_is_cinnamon_desktop",
        "def uok_cinnamon_system_sources",
        "def uok_cinnamon_append_system_sources_to_menu",
    ]
    required2 = [
        "def uok_is_cinnamon",
        "def uok_cinnamon_ibus_sources",
        "def abrir_ajustes_teclado",
        "def ocultar_menu_xfce",
    ]

    missing = [item for item in required1 if item not in block1]
    missing += [item for item in required2 if item not in block2]
    if missing:
        raise SystemExit("Los bloques Cinnamon no parecen completos. Faltan: " + ", ".join(missing))

    # Evitar repetir si se ejecuta dos veces.
    if "uok_backends.cinnamon" in text:
        raise SystemExit("Parece que Cinnamon ya está delegado en uok_backends.cinnamon; no modifico nada.")

    BACKENDS.mkdir(exist_ok=True)

    module_text = (
        "#!/usr/bin/env python3\n"
        "\"\"\"\n"
        "Cinnamon compatibility backend for UrOwnKeyboard.\n\n"
        "This module executes the previously inline Cinnamon compatibility blocks\n"
        "inside the indicator module namespace. It is behavior-preserving and\n"
        "keeps teclado-indicador.py smaller without rewriting Cinnamon logic yet.\n"
        "\"\"\"\n\n"
        "_CINNAMON_CODE_1 = " + repr(block1) + "\n\n"
        "_CINNAMON_CODE_2 = " + repr(block2) + "\n\n\n"
        "def install(app):\n"
        "    namespace = app.__dict__\n"
        "    exec(_CINNAMON_CODE_1, namespace, namespace)\n"
        "    exec(_CINNAMON_CODE_2, namespace, namespace)\n"
    )

    backup = IND.with_suffix(IND.suffix + ".bak-cinnamon-backend-v2")
    backup.write_text(text, encoding="utf-8")

    CIN.write_text(module_text, encoding="utf-8")

    # Reemplazar de atrás hacia delante.
    new_text = text[:start2] + text[end2:]
    new_text = new_text[:start1] + REPLACEMENT + new_text[end1:]

    IND.write_text(new_text, encoding="utf-8")

    py_compile.compile(str(IND), doraise=True)
    py_compile.compile(str(CIN), doraise=True)

    before = len(text.splitlines())
    after = len(new_text.splitlines())
    cin_lines = len(module_text.splitlines())

    print("OK: bloques Cinnamon extraídos sin reescritura lógica.")
    print(f"teclado-indicador.py: {before} -> {after} líneas ({before - after} menos)")
    print(f"uok_backends/cinnamon.py: {cin_lines} líneas")
    print(f"Backup: {backup}")
    print()
    print("Comprueba:")
    print("  python3 -m py_compile teclado-indicador.py uok uok_backends/*.py")
    print("  grep -n \"UOK Cinnamon\\|uok_backends.cinnamon\\|uok_cinnamon\\|uok_is_cinnamon\" teclado-indicador.py uok_backends/cinnamon.py | head -180")
    print("  grep -n \"uok_hide_kde_ibus_native_menu()\\|ocultar_menu_xfce()\\|sincronizar_estado_al_arrancar()\\|uok_main_menu = crear_menu()\" teclado-indicador.py uok_backends/cinnamon.py")
    print("  wc -l teclado-indicador.py uok_backends/cinnamon.py")


if __name__ == "__main__":
    main()
