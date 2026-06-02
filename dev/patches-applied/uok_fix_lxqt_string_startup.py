#!/usr/bin/env python3
from pathlib import Path
import py_compile

LXQT = Path("uok_backends/lxqt.py")
IND = Path("teclado-indicador.py")

lxqt = LXQT.read_text(encoding="utf-8")
ind = IND.read_text(encoding="utf-8")

LXQT.with_suffix(".py.bak-string-startup").write_text(lxqt, encoding="utf-8")
IND.with_suffix(".py.bak-string-startup").write_text(ind, encoding="utf-8")

bad = (
    "\\n\\n\\nuok_hide_kde_ibus_native_menu()"
    "\\nocultar_menu_xfce()"
    "\\nsincronizar_estado_al_arrancar()"
    "\\n\\n"
)

if bad not in lxqt:
    raise SystemExit("No encontré las llamadas de arranque dentro del string LXQt.")

lxqt = lxqt.replace(bad, "\\n\\n", 1)
LXQT.write_text(lxqt, encoding="utf-8")

# Asegurar que el arranque está una sola vez antes de crear_menu().
calls = [
    "uok_hide_kde_ibus_native_menu()",
    "ocultar_menu_xfce()",
    "sincronizar_estado_al_arrancar()",
]

lines = []
for line in ind.splitlines(keepends=True):
    if line.strip() in calls and not line.startswith((" ", "\t")):
        continue
    lines.append(line)

ind = "".join(lines)
marker = "uok_main_menu = crear_menu()"
idx = ind.find(marker)

if idx == -1:
    raise SystemExit("No encontré uok_main_menu = crear_menu().")

startup = (
    "uok_hide_kde_ibus_native_menu()\n"
    "ocultar_menu_xfce()\n"
    "sincronizar_estado_al_arrancar()\n\n"
)

ind = ind[:idx] + startup + ind[idx:]
IND.write_text(ind, encoding="utf-8")

py_compile.compile(str(IND), doraise=True)
py_compile.compile(str(LXQT), doraise=True)

print("OK: llamadas de arranque eliminadas del string LXQt y restauradas antes de crear_menu().")
