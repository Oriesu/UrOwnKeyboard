#!/usr/bin/env python3
from pathlib import Path
import py_compile

ROOT = Path.cwd()
IND = ROOT / "teclado-indicador.py"
BACKENDS = ROOT / "uok_backends"
KDE = BACKENDS / "kde.py"

START = "# UOK KDE Plasma-only compatibility override"
END = "# UOK backend overrides"

REPLACEMENT = """# UOK KDE backend delegation
try:
    from uok_backends.kde import install as uok_install_kde_backend
    uok_install_kde_backend(__import__(__name__))
except Exception as exc:
    print(f'UOK KDE backend disabled: {exc}')

"""


def main():
    if not IND.exists():
        raise SystemExit("No encuentro teclado-indicador.py. Ejecuta esto en la raíz del repo.")

    text = IND.read_text(encoding="utf-8")
    start = text.find(START)
    end = text.find(END)

    if start == -1:
        raise SystemExit(f"No encontré marcador inicial: {START}")

    if end == -1 or end <= start:
        raise SystemExit(f"No encontré marcador final válido: {END}")

    kde_block = text[start:end]

    required = [
        "def uok_is_kde",
        "def get_sources",
        "def activar_gnome_source",
        "def uok_hide_kde_native_keyboard_menus",
        "def uok_hide_kde_ibus_native_menu",
    ]

    missing = [item for item in required if item not in kde_block]
    if missing:
        raise SystemExit("El bloque KDE no parece completo. Faltan: " + ", ".join(missing))

    BACKENDS.mkdir(exist_ok=True)

    module_text = (
        "#!/usr/bin/env python3\n"
        "\"\"\"\n"
        "KDE/Plasma compatibility backend for UrOwnKeyboard.\n\n"
        "This module intentionally executes the previously inline KDE compatibility block\n"
        "inside the indicator module namespace. That makes this extraction behavior-preserving:\n"
        "the same functions are defined/overridden in the same global namespace, but the large\n"
        "KDE block no longer lives in teclado-indicador.py.\n"
        "\"\"\"\n\n"
        "_KDE_CODE = " + repr(kde_block) + "\n\n\n"
        "def install(app):\n"
        "    namespace = app.__dict__\n"
        "    exec(_KDE_CODE, namespace, namespace)\n"
    )

    backup = IND.with_suffix(IND.suffix + ".bak-kde-backend-v2")
    backup.write_text(text, encoding="utf-8")

    KDE.write_text(module_text, encoding="utf-8")

    new_text = text[:start] + REPLACEMENT + text[end:]
    IND.write_text(new_text, encoding="utf-8")

    py_compile.compile(str(IND), doraise=True)
    py_compile.compile(str(KDE), doraise=True)

    before = len(text.splitlines())
    after = len(new_text.splitlines())
    kde_lines = len(module_text.splitlines())

    print("OK: bloque KDE extraído sin reescritura lógica.")
    print(f"teclado-indicador.py: {before} -> {after} líneas ({before - after} menos)")
    print(f"uok_backends/kde.py: {kde_lines} líneas")
    print(f"Backup: {backup}")
    print()
    print("Comprueba:")
    print("  python3 -m py_compile teclado-indicador.py uok uok_backends/*.py")
    print("  grep -n \"UOK KDE\\|uok_backends.kde\\|uok_hide_kde\" teclado-indicador.py uok_backends/kde.py | head -120")
    print("  wc -l teclado-indicador.py uok_backends/kde.py")


if __name__ == "__main__":
    main()
