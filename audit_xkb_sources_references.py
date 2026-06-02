#!/usr/bin/env python3
import ast
from pathlib import Path
from collections import defaultdict

p = Path("uok_xkb_sources.py")
text = p.read_text(encoding="utf-8")
tree = ast.parse(text)

defs = defaultdict(list)

for node in tree.body:
    if isinstance(node, ast.FunctionDef):
        defs[node.name].append((node.lineno, node.end_lineno, node))

duplicate_names = {name for name, entries in defs.items() if len(entries) > 1}

print("== REFERENCIAS A FUNCIONES DUPLICADAS ==")

for name, entries in sorted(defs.items()):
    for start, end, node in entries:
        used = sorted({
            sub.id
            for sub in ast.walk(node)
            if isinstance(sub, ast.Name)
            and sub.id in duplicate_names
            and sub.id != name
        })

        if used:
            print(f"{name}:{start}-{end} usa duplicadas: {', '.join(used)}")
