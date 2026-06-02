#!/usr/bin/env python3
from pathlib import Path
import py_compile

ROOT = Path.cwd()
INDICATOR = ROOT / "teclado-indicador.py"
BACKENDS = ROOT / "uok_backends"

SOURCES_DELEGATION_BLOCK = '''
# UOK GNOME Wayland system sources backend delegation
# This block must stay late in the file, after older get_sources() definitions.
try:
    from uok_backends.session import is_gnome_wayland as uok_is_gnome_wayland
    from uok_backends import system_sources as uok_system_sources

    __uok_pre_backend_get_sources = get_sources

    def get_sources():
        # In GNOME Wayland, setxkbmap/IBus are not reliable sources of truth.
        # Use only GNOME's configured input sources.
        if uok_is_gnome_wayland():
            return uok_system_sources.current_sources()

        return __uok_pre_backend_get_sources()

except Exception as exc:
    print(f"UOK GNOME Wayland system sources delegation disabled: {exc}")

'''


def remove_existing_block(text):
    marker = "# UOK GNOME Wayland system sources backend delegation"
    while marker in text:
        start = text.find(marker)
        candidates = [
            text.find("# UOK X11 helper backend delegation", start),
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
    marker = "# UOK X11 helper backend delegation"
    if marker in text:
        return text.replace(marker, SOURCES_DELEGATION_BLOCK + marker, 1)

    marker = "# UOK keyd backend delegation"
    if marker in text:
        return text.replace(marker, SOURCES_DELEGATION_BLOCK + marker, 1)

    marker = "# UOK backend overrides"
    if marker in text:
        return text.replace(marker, SOURCES_DELEGATION_BLOCK + marker, 1)

    call = "\nuok_hide_kde_ibus_native_menu()\n"
    if call in text:
        return text.replace(call, "\n" + SOURCES_DELEGATION_BLOCK + "uok_hide_kde_ibus_native_menu()\n", 1)

    raise SystemExit("No encontré punto de inserción tardío para delegar get_sources.")


def main():
    if not INDICATOR.exists():
        raise SystemExit("Ejecuta este script en la raíz de UrOwnKeyboard.")
    if not (BACKENDS / "system_sources.py").exists():
        raise SystemExit("No existe uok_backends/system_sources.py.")

    text = INDICATOR.read_text(encoding="utf-8")
    text = remove_existing_block(text)
    text = insert_block(text)
    INDICATOR.write_text(text, encoding="utf-8")

    py_compile.compile(str(INDICATOR), doraise=True)
    py_compile.compile(str(BACKENDS / "system_sources.py"), doraise=True)

    print("OK: get_sources() delegado a system_sources.py solo en GNOME Wayland.")
    print()
    print("Comprueba con:")
    print("  python3 -m py_compile teclado-indicador.py uok_backends/*.py uok")
    print("  grep -n \"UOK GNOME Wayland system sources\\|UOK X11 helper backend delegation\\|UOK keyd backend delegation\\|UOK backend overrides\" teclado-indicador.py | tail -60")
    print()
    print("Instala con:")
    print("  cp teclado-indicador.py ~/.local/bin/teclado-indicador.py")
    print("  mkdir -p ~/.local/bin/uok_backends")
    print("  cp uok_backends/*.py ~/.local/bin/uok_backends/")
    print("  chmod +x ~/.local/bin/teclado-indicador.py")


if __name__ == "__main__":
    main()
