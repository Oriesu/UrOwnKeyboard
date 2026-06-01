from .result import ActivationResult


def apply_profile(profile):
    # Fase de transición: la implementación antigua sigue en teclado-indicador.py/uok.
    # Este módulo será el destino de setxkbmap/xkbcomp.
    return ActivationResult.fail(
        "Backend X11 todavía no migrado.",
        "La ruta antigua sigue activa hasta mover aquí setxkbmap/xkbcomp.",
    )


def verify_profile(profile):
    return ActivationResult.fail(
        "Verificación X11 todavía no migrada.",
        "Mover aquí la verificación real de XKB en X11.",
    )


def rollback():
    return None
