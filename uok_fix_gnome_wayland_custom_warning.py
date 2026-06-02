#!/usr/bin/env python3
from pathlib import Path
import py_compile
import re

ROOT = Path.cwd()
INDICATOR = ROOT / "teclado-indicador.py"
OVERRIDES = ROOT / "uok_backends" / "overrides.py"

NEW_ACTIVAR_PROFILE = '''    def activar_profile(profile):
        # La política de bloqueo ya vive en activation.py.
        if is_gnome_wayland() and profile_is_custom_xkb(profile):
            result = block_custom_profile_in_gnome_wayland(app, profile)
            title = "UrOwnKeyboard - GNOME Wayland"
            short = "Configuraciones propias bloqueadas en GNOME Wayland"
            message = result.message

            # Aviso persistente/visible: algunos lanzadores de AppIndicator no
            # muestran zenity de forma fiable en Wayland, así que usamos también
            # notify/notify-send y dejamos traza en stdout.
            try:
                app.notify("UrOwnKeyboard", short)
            except Exception:
                pass

            try:
                app.subprocess.run(
                    ["notify-send", title, message],
                    text=True,
                    stdout=app.subprocess.PIPE,
                    stderr=app.subprocess.PIPE,
                    check=False,
                )
            except Exception:
                pass

            try:
                app.show_error(title, message)
            except Exception:
                pass

            try:
                print(f"{title}: {message}")
            except Exception:
                pass

            return

        return base_activar_profile(profile)
'''


def remove_main_activation_block(text):
    marker = "# UOK GNOME Wayland activation backend delegation"
    if marker not in text:
        return text

    start = text.find(marker)
    end_marker = "# UOK backend overrides"
    end = text.find(end_marker, start)

    if end == -1:
        raise SystemExit("Encontré el bloque GNOME Wayland activation, pero no el marcador UOK backend overrides.")

    return text[:start] + text[end:]


def patch_overrides(text):
    start_marker = "    def activar_profile(profile):"
    start = text.find(start_marker)

    if start == -1:
        raise SystemExit("No encontré def activar_profile(profile) en uok_backends/overrides.py.")

    end_marker = "\n    app.run_menu_cmd = run_menu_cmd"
    end = text.find(end_marker, start)

    if end == -1:
        raise SystemExit("No encontré el final del bloque activar_profile en overrides.py.")

    return text[:start] + NEW_ACTIVAR_PROFILE + text[end:]


def main():
    if not INDICATOR.exists() or not OVERRIDES.exists():
        raise SystemExit("Ejecuta este script en la raíz de UrOwnKeyboard.")

    indicator_text = INDICATOR.read_text(encoding="utf-8")
    indicator_text = remove_main_activation_block(indicator_text)
    INDICATOR.write_text(indicator_text, encoding="utf-8")

    overrides_text = OVERRIDES.read_text(encoding="utf-8")
    overrides_text = patch_overrides(overrides_text)
    OVERRIDES.write_text(overrides_text, encoding="utf-8")

    py_compile.compile(str(INDICATOR), doraise=True)
    py_compile.compile(str(OVERRIDES), doraise=True)

    print("OK: aviso de perfiles propios GNOME Wayland reforzado.")
    print("OK: eliminado bloque duplicado de activación GNOME Wayland en teclado-indicador.py.")
    print()
    print("Comprueba con:")
    print("  python3 -m py_compile teclado-indicador.py uok_backends/*.py uok")
    print("  grep -n \"UOK GNOME Wayland activation\\|UOK backend overrides\" teclado-indicador.py | tail -40")
    print("  grep -n \"Configuraciones propias bloqueadas\\|def activar_profile\" uok_backends/overrides.py")
    print()
    print("Instala con:")
    print("  cp teclado-indicador.py ~/.local/bin/teclado-indicador.py")
    print("  mkdir -p ~/.local/bin/uok_backends")
    print("  cp uok_backends/*.py ~/.local/bin/uok_backends/")
    print("  chmod +x ~/.local/bin/teclado-indicador.py")


if __name__ == "__main__":
    main()
