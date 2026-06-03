from .session import is_gnome_wayland
from . import gnome_wayland

def verify_gnome_source(index=None, expected_xkb=None, raw_xkb_layout_func=None):
    if is_gnome_wayland():
        if index is None:
            return True, ""
        if gnome_wayland.verify_index(index):
            return True, ""
        current = gnome_wayland.current_index()
        return False, ("GNOME no cambió al índice esperado. "f"Esperado: {index}. Actual: {current}.")
    if expected_xkb is None or raw_xkb_layout_func is None:
        return True, ""
    expected = str(expected_xkb or "").strip()
    got = str(raw_xkb_layout_func() or "").strip()
    if got != expected:
        return False, ("XKB no cambió al layout esperado. "f"Esperado: {expected}. Actual: {got or 'desconocido'}.")
    return True, ""
