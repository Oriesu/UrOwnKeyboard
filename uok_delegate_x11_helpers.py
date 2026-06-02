#!/usr/bin/env python3
from pathlib import Path
import py_compile

ROOT = Path.cwd()
INDICATOR = ROOT / "teclado-indicador.py"
BACKENDS = ROOT / "uok_backends"

X11_DELEGATION_BLOCK = '''
# UOK X11 helper backend delegation
# This block must stay late in the file, after older XKB helper definitions.
try:
    from uok_backends.session import is_wayland as uok_session_is_wayland
    from uok_backends import x11 as uok_x11_backend

    def raw_xkb_layout():
        # setxkbmap is not a reliable source in Wayland/Xwayland.
        # Returning empty here avoids using X11 state as truth in Wayland.
        if uok_session_is_wayland():
            return ""

        spec = uok_x11_backend.current_spec()

        if "(" in spec and spec.endswith(")"):
            layout, variant = spec[:-1].split("(", 1)
            return f"{layout}+{variant}"

        return spec

    def get_raw_setxkbmap_spec():
        if uok_session_is_wayland():
            return ""

        return uok_x11_backend.current_spec()

    def gnome_source_to_setxkbmap_cmd(source_type, source_id):
        return uok_x11_backend.source_to_setxkbmap_cmd(source_type, source_id) or ""

    def expected_source_spec(source_id):
        return (source_id or "").strip()

except Exception as exc:
    print(f"UOK X11 helper backend delegation disabled: {exc}")

'''


def remove_existing_block(text):
    marker = "# UOK X11 helper backend delegation"
    while marker in text:
        start = text.find(marker)
        candidates = [
            text.find("# UOK keyd backend delegation", start),
            text.find("# UOK backend overrides", start),
            text.find("uok_hide_kde_ibus_native_menu()", start),
        ]
        candidates = [x for x in candidates if x != -1]
        if candidates:
            end = min(candidates)
            text = text[:start] + text[end:]
        else:
            end = text.find("\n\n", start)
            if end == -1:
                text = text[:start]
            else:
                text = text[:start] + text[end + 2:]
    return text


def insert_block(text):
    marker = "# UOK keyd backend delegation"
    if marker in text:
        return text.replace(marker, X11_DELEGATION_BLOCK + marker, 1)

    marker = "# UOK backend overrides"
    if marker in text:
        return text.replace(marker, X11_DELEGATION_BLOCK + marker, 1)

    call = "\nuok_hide_kde_ibus_native_menu()\n"
    if call in text:
        return text.replace(call, "\n" + X11_DELEGATION_BLOCK + "uok_hide_kde_ibus_native_menu()\n", 1)

    raise SystemExit("No encontré punto de inserción tardío para delegar helpers X11.")


def main():
    if not INDICATOR.exists():
        raise SystemExit("Ejecuta este script en la raíz de UrOwnKeyboard.")
    if not BACKENDS.exists():
        raise SystemExit("No existe uok_backends.")
    if not (BACKENDS / "x11.py").exists():
        raise SystemExit("No existe uok_backends/x11.py.")

    text = INDICATOR.read_text(encoding="utf-8")
    text = remove_existing_block(text)
    text = insert_block(text)
    INDICATOR.write_text(text, encoding="utf-8")

    py_compile.compile(str(INDICATOR), doraise=True)
    py_compile.compile(str(BACKENDS / "x11.py"), doraise=True)

    print("OK: helpers X11 delegados tardíamente a uok_backends/x11.py")
    print()
    print("Comprueba con:")
    print("  python3 -m py_compile teclado-indicador.py uok_backends/*.py uok")
    print("  grep -n \"UOK X11 helper backend delegation\\|UOK keyd backend delegation\\|UOK backend overrides\" teclado-indicador.py | tail -40")
    print()
    print("Instala con:")
    print("  cp teclado-indicador.py ~/.local/bin/teclado-indicador.py")
    print("  mkdir -p ~/.local/bin/uok_backends")
    print("  cp uok_backends/*.py ~/.local/bin/uok_backends/")
    print("  chmod +x ~/.local/bin/teclado-indicador.py")


if __name__ == "__main__":
    main()
