#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path.cwd()
README = ROOT / "README.md"

SECTION = """## GNOME Wayland support

UrOwnKeyboard supports GNOME Wayland for normal system input sources, such as the layouts configured in GNOME Settings.

Supported in GNOME Wayland:

- Switching between GNOME system XKB sources, for example `es`, `de`, `us`, etc.
- Keeping `keyd` neutral when a normal GNOME source is selected.
- Blocking custom UOK XKB profiles safely when they cannot be applied to the real Wayland compositor.

Not supported yet in GNOME Wayland:

- Applying custom UOK XKB profiles generated/imported by UrOwnKeyboard through `setxkbmap`, `xkbcomp` or `~/.xkb`.
- Applying the profile-specific `keyd` mapping when the corresponding custom XKB layout could not be verified.

This limitation is intentional. In GNOME Wayland, `setxkbmap` may only affect Xwayland and does not reliably change the real Mutter/Wayland keyboard layout. For that reason, UrOwnKeyboard blocks custom profiles in GNOME Wayland instead of applying only the `keyd` part and leaving the keyboard incoherent.

To use custom UOK profiles, use a GNOME X11 session or another supported X11 desktop.

"""

def normalize_newlines(text):
    return text.replace("\r\n", "\n").replace("\r", "\n")

def remove_existing_section(text):
    patterns = [
        r"\n## GNOME Wayland support\n.*?(?=\n## |\Z)",
        r"\n## Soporte GNOME Wayland\n.*?(?=\n## |\Z)",
        r"\n## GNOME Wayland\n.*?(?=\n## |\Z)",
    ]
    for pattern in patterns:
        text = re.sub(pattern, "\n", text, flags=re.S)
    return text

def choose_insert_point(text):
    candidates = [
        "## Desktop support",
        "## Supported desktops",
        "## Compatibility",
        "## Installation",
        "## Instalación",
        "## Uso",
        "## Usage",
    ]

    for heading in candidates:
        idx = text.find("\n" + heading)
        if idx != -1:
            return idx

    return len(text)

def main():
    if not README.exists():
        raise SystemExit("No encuentro README.md. Ejecuta esto en la raíz del repositorio.")

    text = normalize_newlines(README.read_text(encoding="utf-8"))
    text = remove_existing_section(text).rstrip() + "\n"

    insert_at = choose_insert_point(text)

    if insert_at == len(text):
        new_text = text + "\n" + SECTION
    else:
        new_text = text[:insert_at] + "\n" + SECTION + text[insert_at:]

    README.write_text(new_text.rstrip() + "\n", encoding="utf-8")

    print("OK: README.md actualizado con la sección GNOME Wayland support.")
    print()
    print("Comprueba con:")
    print('  grep -n "GNOME Wayland support\\|custom UOK XKB\\|keyd" README.md | head -80')
    print("  git diff -- README.md")
    print()
    print("Si está bien:")
    print("  git add README.md")
    print('  git commit -m "Document GNOME Wayland limitations"')

if __name__ == "__main__":
    main()
