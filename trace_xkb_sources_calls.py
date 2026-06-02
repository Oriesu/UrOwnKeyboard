#!/usr/bin/env python3
import functools
import inspect
import json
import os
import sys
from pathlib import Path

import uok_xkb_sources

CONFIG = Path.home() / ".config" / "teclado-indicador"
CURRENT_PROFILE = CONFIG / "current-profile.json"
PROFILES_DIR = CONFIG / "profiles"

called = []
seen = set()


def wrap_function(name, func):
    if getattr(func, "_uok_traced", False):
        return func

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        key = (name, getattr(func, "__code__", None).co_firstlineno if hasattr(func, "__code__") else 0)
        if key not in seen:
            seen.add(key)
            try:
                file = inspect.getsourcefile(func) or "?"
                line = func.__code__.co_firstlineno
                called.append((line, name, file))
                print(f"CALL {line:5d} {name}", file=sys.stderr)
            except Exception:
                called.append((0, name, "?"))
                print(f"CALL ????? {name}", file=sys.stderr)

        return func(*args, **kwargs)

    wrapper._uok_traced = True
    wrapper._uok_original = func
    return wrapper


# Envolver todas las funciones globales del módulo, incluidas aliases __uok_*
for name, value in list(uok_xkb_sources.__dict__.items()):
    if inspect.isfunction(value) and getattr(value, "__module__", "") == "uok_xkb_sources":
        setattr(uok_xkb_sources, name, wrap_function(name, value))


items = uok_xkb_sources.load_xkb_sources(CURRENT_PROFILE, PROFILES_DIR)

print()
print("== ITEMS ==")
for item in items[:80]:
    print(
        item.get("section", ""),
        "|",
        item.get("kind", ""),
        "|",
        item.get("source_id", ""),
        "|",
        item.get("label", ""),
    )

print()
print("== CALLED FUNCTIONS ==")
for line, name, file in sorted(called):
    print(f"{line:5d} {name}")

print()
print(f"Total items: {len(items)}")
print(f"Total called functions: {len(called)}")
