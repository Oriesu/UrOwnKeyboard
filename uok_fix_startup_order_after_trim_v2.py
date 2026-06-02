#!/usr/bin/env python3
from pathlib import Path
import py_compile

ROOT = Path.cwd()
P = ROOT / "teclado-indicador.py"

CALLS = {
    "uok_hide_kde_ibus_native_menu()",
    "ocultar_menu_xfce()",
    "sincronizar_estado_al_arrancar()",
}

STARTUP = """uok_hide_kde_ibus_native_menu()
ocultar_menu_xfce()
sincronizar_estado_al_arrancar()

"""

INSERT_MARKER = "uok_main_menu = crear_menu()"


def main():
    if not P.exists():
        raise SystemExit("Ejecuta esto en la raíz de UrOwnKeyboard.")

    old = P.read_text(encoding="utf-8")
    lines = old.splitlines(keepends=True)

    removed = []
    kept = []

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()

        # Quita cualquier llamada suelta de arranque que haya quedado antes
        # de que las funciones finales existan.
        if stripped in CALLS and not line.startswith((" ", "\t")):
            removed.append((i, stripped))
            continue

        kept.append(line)

    text = "".join(kept)

    idx = text.find(INSERT_MARKER)
    if idx == -1:
        raise SystemExit(f"No encontré {INSERT_MARKER!r}.")

    text = text[:idx] + STARTUP + text[idx:]

    backup = P.with_suffix(P.suffix + ".bak-startup-order-v2")
    backup.write_text(old, encoding="utf-8")
    P.write_text(text, encoding="utf-8")

    py_compile.compile(str(P), doraise=True)

    print("OK: llamadas de arranque unificadas antes de crear_menu().")
    print(f"Backup: {backup}")
    print()
    print("Llamadas eliminadas:")
    for lineno, call in removed:
        print(f"  {lineno}: {call}")
    print()
    print("Comprueba:")
    print("  python3 -m py_compile teclado-indicador.py uok uok_backends/*.py")
    print("  grep -n \"uok_hide_kde_ibus_native_menu()\\|ocultar_menu_xfce()\\|sincronizar_estado_al_arrancar()\\|uok_main_menu = crear_menu()\" teclado-indicador.py | tail -60")
    print("  wc -l teclado-indicador.py")


if __name__ == "__main__":
    main()
