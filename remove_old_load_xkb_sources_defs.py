#!/usr/bin/env python3
import ast
from pathlib import Path

p = Path("uok_xkb_sources.py")
text = p.read_text(encoding="utf-8")
lines = text.splitlines(keepends=True)
tree = ast.parse(text)

# Conservamos:
# - load_xkb_sources de línea >= 1402, porque es la base real usada por KDE final.
# - los posteriores de KDE/Cinnamon/LXQt.
# Eliminamos solo los load_xkb_sources viejos de desarrollo.
remove = []

for node in tree.body:
    if isinstance(node, ast.FunctionDef) and node.name == "load_xkb_sources":
        if node.lineno < 1402:
            remove.append((node.lineno, node.end_lineno))

if not remove:
    print("No hay load_xkb_sources antiguos que eliminar.")
    raise SystemExit(0)

backup = p.with_suffix(p.suffix + ".bak-remove-old-loads")
backup.write_text(text, encoding="utf-8")

remove_lines = set()
for start, end in remove:
    for n in range(start, end + 1):
        remove_lines.add(n)

new_lines = [
    line
    for i, line in enumerate(lines, start=1)
    if i not in remove_lines
]

new_text = "".join(new_lines)
ast.parse(new_text)
p.write_text(new_text, encoding="utf-8")

print(f"{p}: {len(lines)} -> {len(new_lines)} líneas")
print(f"Backup: {backup}")
print("Eliminado:")
for start, end in remove:
    print(f"  load_xkb_sources líneas {start}-{end}")
