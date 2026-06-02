#!/usr/bin/env python3
import ast
import os
import subprocess
import sys
from pathlib import Path
from collections import defaultdict

TARGET = Path("uok_xkb_sources.py")
TRACE = Path("trace_xkb_sources_calls.py")

DESKTOPS = [
    ("GNOME", "gnome", "wayland"),
    ("XFCE", "xfce", "x11"),
    ("MATE", "mate", "x11"),
    ("KDE", "KDE", "x11"),
    ("LXQt", "LXQt", "x11"),
    ("Cinnamon", "X-Cinnamon", "x11"),
]

text = TARGET.read_text(encoding="utf-8")
tree = ast.parse(text)

defs = defaultdict(list)

for node in tree.body:
    if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
        defs[node.name].append((node.lineno, node.end_lineno, type(node).__name__))

duplicate_lines = {
    line
    for entries in defs.values()
    if len(entries) > 1
    for line, _end, _kind in entries
}

called_by_desktop = defaultdict(set)

for label, current, session in DESKTOPS:
    env = os.environ.copy()
    env.update({
        "XDG_CURRENT_DESKTOP": current,
        "DESKTOP_SESSION": current,
        "XDG_SESSION_DESKTOP": current,
        "XDG_SESSION_TYPE": session,
    })

    result = subprocess.run(
        [sys.executable, str(TRACE)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        check=False,
    )

    for line in result.stdout.splitlines():
        if not line.startswith("CALL"):
            continue

        parts = line.split()
        if len(parts) >= 3 and parts[1].isdigit():
            lineno = int(parts[1])
            name = parts[2]
            called_by_desktop[(name, lineno)].add(label)

print("== FUNCIONES DUPLICADAS ==")
for name, entries in sorted(defs.items()):
    if len(entries) <= 1:
        continue

    print()
    print(name)
    for line, end, kind in entries:
        desktops = sorted(called_by_desktop.get((name, line), []))
        status = "LLAMADA: " + ",".join(desktops) if desktops else "NO llamada en la matriz"
        print(f"  {line:5d}-{end:<5d} {status}")

print()
print("== CANDIDATAS OBVIAS A BORRAR ==")
print("Duplicadas que no fueron llamadas en GNOME/XFCE/MATE/KDE/LXQt/Cinnamon.")
print("No borres aún automáticamente; primero revisamos esta lista.")
for name, entries in sorted(defs.items()):
    if len(entries) <= 1:
        continue

    for line, end, kind in entries:
        if not called_by_desktop.get((name, line)):
            print(f"  {name}: {line}-{end}")
