#!/usr/bin/env python3
from pathlib import Path
import py_compile

ROOT = Path.cwd()
IND = ROOT / "teclado-indicador.py"
LXQT = ROOT / "uok_backends" / "lxqt.py"

CALLS = [
    "uok_hide_kde_ibus_native_menu()",
    "ocultar_menu_xfce()",
    "sincronizar_estado_al_arrancar()",
]

STARTUP = """uok_hide_kde_ibus_native_menu()
ocultar_menu_xfce()
sincronizar_estado_al_arrancar()

"""

MARKER = "uok_main_menu = crear_menu()"


def remove_top_level_startup_calls(text):
    out = []
    removed = []
    for lineno, line in enumerate(text.splitlines(keepends=True), start=1):
        stripped = line.strip()
        if stripped in CALLS and not line.startswith((" ", "\t")):
            removed.append((lineno, stripped))
            continue
        out.append(line)
    return "".join(out), removed


def main():
    if not IND.exists() or not LXQT.exists():
        raise SystemExit("Ejecuta esto en la raíz del repo, con uok_backends/lxqt.py existente.")

    ind_old = IND.read_text(encoding="utf-8")
    lxqt_old = LXQT.read_text(encoding="utf-8")

    IND.with_suffix(IND.suffix + ".bak-lxqt-startup-fix").write_text(ind_old, encoding="utf-8")
    LXQT.with_suffix(LXQT.suffix + ".bak-startup-fix").write_text(lxqt_old, encoding="utf-8")

    lxqt_new, removed_lxqt = remove_top_level_startup_calls(lxqt_old)
    ind_tmp, removed_ind = remove_top_level_startup_calls(ind_old)

    idx = ind_tmp.find(MARKER)
    if idx == -1:
        raise SystemExit(f"No encontré {MARKER!r} en teclado-indicador.py.")

    ind_new = ind_tmp[:idx] + STARTUP + ind_tmp[idx:]

    LXQT.write_text(lxqt_new, encoding="utf-8")
    IND.write_text(ind_new, encoding="utf-8")

    py_compile.compile(str(IND), doraise=True)
    py_compile.compile(str(LXQT), doraise=True)

    print("OK: startup sacado de uok_backends/lxqt.py y restaurado en teclado-indicador.py.")
    print("Eliminado de lxqt.py:")
    for lineno, call in removed_lxqt:
        print(f"  {lineno}: {call}")
    print("Eliminado de teclado-indicador.py antes de reinsertar:")
    for lineno, call in removed_ind:
        print(f"  {lineno}: {call}")


if __name__ == "__main__":
    main()
