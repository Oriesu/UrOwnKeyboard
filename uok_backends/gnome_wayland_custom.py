from .result import ActivationResult
from .profiles import profile_name


def apply_profile(profile):
    return ActivationResult.fail(
        "Perfil UOK propio no soportado todavía en GNOME Wayland.",
        f"Perfil: {profile_name(profile)}",
    )


def verify_profile(profile):
    return ActivationResult.fail(
        "No hay verificación fiable para perfiles propios en GNOME Wayland todavía."
    )


def rollback():
    return None
