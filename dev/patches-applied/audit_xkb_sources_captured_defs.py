#!/usr/bin/env python3
import ast
from pathlib import Path
from collections import defaultdict

p = Path("uok_xkb_sources.py")
text = p.read_text(encoding="utf-8")
tree = ast.parse(text)

defs_by_name = defaultdict(list)
current_def = {}

captured = []

for node in tree.body:
    if isinstance(node, ast.FunctionDef):
        defs_by_name[node.name].append((node.lineno, node.end_lineno))
        current_def[node.name] = (node.lineno, node.end_lineno)

    elif isinstance(node, ast.Try):
        # Buscar asignaciones dentro de try/except tipo:
        # __uok_base = load_xkb_sources
        for sub in ast.walk(node):
            if isinstance(sub, ast.Assign):
                if not isinstance(sub.value, ast.Name):
                    continue

                src_name = sub.value.id
                src_def = current_def.get(src_name)

                if not src_def:
                    continue

                for target in sub.targets:
                    if isinstance(target, ast.Name):
                        captured.append((target.id, src_name, src_def[0], src_def[1], sub.lineno))

    elif isinstance(node, ast.Assign):
        if isinstance(node.value, ast.Name):
            src_name = node.value.id
            src_def = current_def.get(src_name)

            if src_def:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        captured.append((target.id, src_name, src_def[0], src_def[1], node.lineno))

captured_ranges = {(src_name, start, end) for _alias, src_name, start, end, _line in captured}

print("== DEFINICIONES CAPTURADAS EN ALIAS ==")
for alias, src_name, start, end, line in captured:
    print(f"{alias} = {src_name}  captura {src_name}:{start}-{end} en línea {line}")

print()
print("== DUPLICADAS PROTEGIDAS / CANDIDATAS ==")
for name, entries in sorted(defs_by_name.items()):
    if len(entries) <= 1:
        continue

    print()
    print(name)
    for start, end in entries:
        if (name, start, end) in captured_ranges:
            print(f"  {start:5d}-{end:<5d} PROTEGIDA por alias")
        else:
            print(f"  {start:5d}-{end:<5d} candidata, revisar uso")
