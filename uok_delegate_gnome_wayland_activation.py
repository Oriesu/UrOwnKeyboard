#!/usr/bin/env python3
from pathlib import Path
import py_compile

ROOT = Path.cwd()
INDICATOR = ROOT / "teclado-indicador.py"
BACKENDS = ROOT / "uok_backends"

DELEGATION_BLOCK = '''
# UOK GNOME Wayland activation backend delegation
# This block must stay late, after older activar_gnome_source() definitions
# and after keyd delegation, but before uok_backends.overrides.install().
try:
    from uok_backends.session import is_gnome_wayland as uok_is_gnome_wayland_activation
    from uok_backends import gnome_wayland as uok_gnome_wayland_backend

    __uok_pre_backend_activar_gnome_source = activar_gnome_source

    def activar_gnome_source(index, source_type, source_id):
        if not uok_is_gnome_wayland_activation():
            return __uok_pre_backend_activar_gnome_source(index, source_type, source_id)

        label = source_label(source_type, source_id)

        if source_type != "xkb":
            show_error(
                "UrOwnKeyboard - GNOME Wayland",
                "Esta fuente no es XKB y todavía no está soportada en GNOME Wayland.",
            )
            return

        # Nunca dejar keyd activo al volver a una fuente normal del sistema.
        if not aplicar_keyd_off_sync():
            return

        if not uok_gnome_wayland_backend.set_current_index(index):
            show_error(
                "UrOwnKeyboard - GNOME Wayland",
                "No se pudo cambiar la fuente de entrada de GNOME.",
            )
            return

        try:
            from uok_backends.overrides import _force_ibus_engine
            _force_ibus_engine(__import__(__name__), source_type, source_id)
        except Exception:
            pass

        if not uok_gnome_wayland_backend.verify_index(index):
            show_error(
                "UrOwnKeyboard - verificación",
                "GNOME no cambió al índice esperado. "
                f"Esperado: {index}. Actual: {uok_gnome_wayland_backend.current_index()}",
            )
            return

        current = {
            "type": "gnome-source",
            "name": label,
            "source_type": source_type,
            "source_id": source_id,
            "desktop": "gnome-wayland",
            "keyd_conf": None,
        }

        CURRENT_PROFILE.write_text(
            json.dumps(current, indent=2, ensure_ascii=False)
        )

        notify("Keyboard", label + " activated")

except Exception as exc:
    print(f"UOK GNOME Wayland activation delegation disabled: {exc}")

'''


def remove_existing_block(text):
    marker = "# UOK GNOME Wayland activation backend delegation"
    while marker in text:
        start = text.find(marker)
        candidates = [
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
    marker = "# UOK backend overrides"
    if marker in text:
        return text.replace(marker, DELEGATION_BLOCK + marker, 1)

    call = "\nuok_hide_kde_ibus_native_menu()\n"
    if call in text:
        return text.replace(call, "\n" + DELEGATION_BLOCK + "uok_hide_kde_ibus_native_menu()\n", 1)

    raise SystemExit("No encontré punto de inserción para delegar activación GNOME Wayland.")


def main():
    if not INDICATOR.exists():
        raise SystemExit("Ejecuta este script en la raíz de UrOwnKeyboard.")
    if not (BACKENDS / "gnome_wayland.py").exists():
        raise SystemExit("No existe uok_backends/gnome_wayland.py.")

    text = INDICATOR.read_text(encoding="utf-8")
    text = remove_existing_block(text)
    text = insert_block(text)
    INDICATOR.write_text(text, encoding="utf-8")

    py_compile.compile(str(INDICATOR), doraise=True)
    py_compile.compile(str(BACKENDS / "gnome_wayland.py"), doraise=True)

    print("OK: activar_gnome_source() delegado a gnome_wayland.py solo en GNOME Wayland.")
    print()
    print("Comprueba con:")
    print("  python3 -m py_compile teclado-indicador.py uok_backends/*.py uok")
    print("  grep -n \"UOK GNOME Wayland activation\\|UOK backend overrides\" teclado-indicador.py | tail -40")
    print()
    print("Instala con:")
    print("  cp teclado-indicador.py ~/.local/bin/teclado-indicador.py")
    print("  mkdir -p ~/.local/bin/uok_backends")
    print("  cp uok_backends/*.py ~/.local/bin/uok_backends/")
    print("  chmod +x ~/.local/bin/teclado-indicador.py")


if __name__ == "__main__":
    main()
