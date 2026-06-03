from .session import is_gnome_wayland
from . import gnome_wayland


def verify_gnome_source(index=None, expected_xkb=None, raw_xkb_layout_func=None):
    """
    En GNOME Wayland no se debe verificar con setxkbmap.
    En X11 sí puede verificarse con el layout XKB real.
    """
    if is_gnome_wayland():
        if index is None:
            return True, ""

        ok = gnome_wayland.verify_index(index)
        if ok:
            return True, ""

        return False, (
            "GNOME no cambió al índice esperado. "
            f"Esperado: {index}. Actual: {gnome_wayland.current_index()}."
        )

    if expected_xkb is None or raw_xkb_layout_func is None:
        return True, ""

    got = raw_xkb_layout_func()

    if got != expected_xkb:
        return False, (
            "XKB no cambió al layout esperado. "
            f"Esperado: {expected_xkb}. Actual: {got or 'desconocido'}."
        )

    return True, ""
