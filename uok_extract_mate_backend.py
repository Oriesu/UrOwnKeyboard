#!/usr/bin/env python3
from pathlib import Path
import py_compile

ROOT = Path.cwd()
IND = ROOT / "teclado-indicador.py"
BACKENDS = ROOT / "uok_backends"
MATE = BACKENDS / "mate.py"

START1 = "\ndef uok_is_mate_desktop():"
END1 = "# UOK Cinnamon backend delegation"

START2 = "# UOK MATE override: Add from settings before crear_menu"
END2 = "uok_hide_kde_ibus_native_menu()"

REPLACEMENT = """# UOK MATE backend delegation
try:
    from uok_backends.mate import install as uok_install_mate_backend
    uok_install_mate_backend(__import__(__name__))
except Exception as exc:
    print(f'UOK MATE backend disabled: {exc}')

"""


def slice_block(text, start_marker, end_marker, start_offset=0):
    pos = text.find(start_marker)
    if pos == -1:
        raise SystemExit(f"No encontré marcador inicial: {start_marker!r}")

    start = pos + start_offset
    end = text.find(end_marker, start)

    if end == -1 or end <= start:
        raise SystemExit(f"No encontré marcador final válido: {end_marker!r}")

    return start, end, text[start:end]


def main():
    if not IND.exists():
        raise SystemExit("No encuentro teclado-indicador.py. Ejecuta esto en la raíz del repo.")

    text = IND.read_text(encoding="utf-8")

    if "uok_backends.mate" in text:
        raise SystemExit("Parece que MATE ya está delegado en uok_backends.mate; no modifico nada.")

    # START1 empieza con salto de línea para no comernos texto anterior.
    start1, end1, block1 = slice_block(text, START1, END1, start_offset=1)
    start2, end2, block2 = slice_block(text, START2, END2)

    if start2 <= end1:
        raise SystemExit("Los bloques MATE no están en el orden esperado; no modifico nada.")

    required1 = [
        "def uok_is_mate_desktop",
        "def uok_mate_system_sources",
        "def uok_mate_hide_native_input_indicators",
        "def uok_mate_append_system_sources_to_menu",
    ]
    required2 = [
        "def uok_mate_settings_is_mate",
        "def abrir_ajustes_teclado",
    ]

    missing = [item for item in required1 if item not in block1]
    missing += [item for item in required2 if item not in block2]
    if missing:
        raise SystemExit("Los bloques MATE no parecen completos. Faltan: " + ", ".join(missing))

    # Seguridad: las llamadas de arranque no deben entrar en el backend.
    forbidden = [
        "uok_hide_kde_ibus_native_menu()",
        "ocultar_menu_xfce()",
        "sincronizar_estado_al_arrancar()",
        "uok_main_menu = crear_menu()",
    ]
    bad = [x for x in forbidden if x in block1 or x in block2]
    if bad:
        raise SystemExit("El bloque MATE capturaría llamadas de arranque. No modifico. Detectado: " + ", ".join(bad))

    BACKENDS.mkdir(exist_ok=True)

    module_text = (
        "#!/usr/bin/env python3\n"
        "\"\"\"\n"
        "MATE compatibility backend for UrOwnKeyboard.\n\n"
        "This module executes the previously inline MATE compatibility blocks\n"
        "inside the indicator module namespace. It is behavior-preserving and\n"
        "keeps teclado-indicador.py smaller without rewriting MATE logic yet.\n"
        "\"\"\"\n\n"
        "_MATE_CODE_1 = " + repr(block1) + "\n\n"
        "_MATE_CODE_2 = " + repr(block2) + "\n\n\n"
        "def install(app):\n"
        "    namespace = app.__dict__\n"
        "    exec(_MATE_CODE_1, namespace, namespace)\n"
        "    exec(_MATE_CODE_2, namespace, namespace)\n"
    )

    backup = IND.with_suffix(IND.suffix + ".bak-mate-backend")
    backup.write_text(text, encoding="utf-8")

    MATE.write_text(module_text, encoding="utf-8")

    # Reemplazar de atrás hacia delante.
    new_text = text[:start2] + text[end2:]
    new_text = new_text[:start1] + REPLACEMENT + new_text[end1:]

    IND.write_text(new_text, encoding="utf-8")

    py_compile.compile(str(IND), doraise=True)
    py_compile.compile(str(MATE), doraise=True)

    before = len(text.splitlines())
    after = len(new_text.splitlines())
    mate_lines = len(module_text.splitlines())

    print("OK: bloques MATE extraídos sin reescritura lógica.")
    print(f"teclado-indicador.py: {before} -> {after} líneas ({before - after} menos)")
    print(f"uok_backends/mate.py: {mate_lines} líneas")
    print(f"Backup: {backup}")
    print()
    print("Comprueba:")
    print("  python3 -m py_compile teclado-indicador.py uok uok_backends/*.py")
    print("  grep -n \"UOK MATE\\|uok_backends.mate\\|uok_mate\\|uok_is_mate\" teclado-indicador.py uok_backends/mate.py | head -180")
    print("  grep -n \"uok_hide_kde_ibus_native_menu()\\|ocultar_menu_xfce()\\|sincronizar_estado_al_arrancar()\\|uok_main_menu = crear_menu()\" teclado-indicador.py uok_backends/mate.py")
    print("  wc -l teclado-indicador.py uok_backends/mate.py")


if __name__ == "__main__":
    main()
