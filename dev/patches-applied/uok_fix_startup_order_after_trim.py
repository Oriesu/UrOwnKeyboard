#!/usr/bin/env python3
from pathlib import Path
import py_compile

ROOT = Path.cwd()
P = ROOT / "teclado-indicador.py"

STARTUP = """uok_hide_kde_ibus_native_menu()
ocultar_menu_xfce()
sincronizar_estado_al_arrancar()
"""

MARKERS = [
    "uok_main_menu = crear_menu()",
    "indicator.set_menu(",
    "Gtk.main()",
]

def remove_startup(text):
    count = text.count(STARTUP)
    text = text.replace(STARTUP, "")
    return text, count

def insert_before_marker(text):
    for marker in MARKERS:
        idx = text.find(marker)
        if idx != -1:
            return text[:idx] + STARTUP + "\n" + text[idx:], marker
    raise SystemExit("No encontré punto seguro para reinsertar llamadas de arranque.")

def main():
    if not P.exists():
        raise SystemExit("Ejecuta esto en la raíz de UrOwnKeyboard.")

    text = P.read_text(encoding="utf-8")
    old = text

    text, count = remove_startup(text)
    if count == 0:
        raise SystemExit("No encontré el bloque de llamadas de arranque.")

    text, marker = insert_before_marker(text)

    backup = P.with_suffix(P.suffix + ".bak-startup-order")
    backup.write_text(old, encoding="utf-8")
    P.write_text(text, encoding="utf-8")

    py_compile.compile(str(P), doraise=True)

    print(f"OK: movidas llamadas de arranque ({count}) antes de {marker!r}.")
    print(f"Backup: {backup}")
    print()
    print("Comprueba:")
    print("  python3 -m py_compile teclado-indicador.py uok uok_backends/*.py")
    print("  grep -n \"uok_hide_kde_ibus_native_menu()\\|ocultar_menu_xfce()\\|sincronizar_estado_al_arrancar()\\|def ocultar_menu_xfce\" teclado-indicador.py | tail -40")
    print("  wc -l teclado-indicador.py")

if __name__ == "__main__":
    main()
