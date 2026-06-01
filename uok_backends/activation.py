from .result import ActivationResult
from . import keyd
from .session import is_gnome_wayland
from .profiles import profile_is_custom_xkb, unsupported_gnome_wayland_message


def profile_keyd_conf(profile):
    if not profile:
        return None
    return profile.get("keyd_conf")


def activate_profile_transactional(profile, layout_apply, layout_verify, rollback, *, allow_custom_wayland=False):
    # Orden seguro:
    # 1. En GNOME Wayland, bloquear perfiles propios salvo modo explícito.
    # 2. Apagar keyd antes de tocar layout.
    # 3. Aplicar layout.
    # 4. Verificar layout.
    # 5. Aplicar keyd solo si el layout se verificó.
    # 6. Rollback + keyd off si falla algo.
    if is_gnome_wayland() and profile_is_custom_xkb(profile) and not allow_custom_wayland:
        keyd.off()
        try:
            rollback()
        except Exception:
            pass

        return ActivationResult.fail(
            unsupported_gnome_wayland_message(profile)
            + "\n\nNo se ha aplicado ni XKB ni keyd para evitar dejar el teclado incoherente.",
            rolled_back=True,
        )

    keyd.off()

    layout_result = layout_apply(profile)
    if not layout_result.ok:
        keyd.off()
        try:
            rollback()
        except Exception:
            pass
        return ActivationResult.fail(layout_result.message, layout_result.details, rolled_back=True)

    verify_result = layout_verify(profile)
    if not verify_result.ok:
        keyd.off()
        try:
            rollback()
        except Exception:
            pass
        return ActivationResult.fail(verify_result.message, verify_result.details, rolled_back=True)

    keyd_conf = profile_keyd_conf(profile)
    if keyd_conf:
        keyd_result = keyd.apply_conf(keyd_conf)
        if not keyd_result.ok:
            return ActivationResult.fail(
                "El layout se aplicó, pero keyd no pudo aplicarse.",
                keyd_result.combined,
            )
        return ActivationResult.ok_result("Perfil aplicado con keyd.", applied_keyd=True)

    return ActivationResult.ok_result("Perfil aplicado sin keyd.", applied_keyd=False)


def reset_gnome_wayland_to_safe_source(app, index=0, ibus_engine="xkb:es::spa"):
    # Rollback conservador para estados incoherentes GNOME/IBus/keyd.
    keyd.off()

    try:
        from . import gnome_wayland
        gnome_wayland.set_current_index(index)
    except Exception:
        pass

    try:
        app.subprocess.run(
            ["ibus", "engine", ibus_engine],
            text=True,
            stdout=app.subprocess.PIPE,
            stderr=app.subprocess.PIPE,
            check=False,
        )
    except Exception:
        pass


def block_custom_profile_in_gnome_wayland(app, profile):
    reset_gnome_wayland_to_safe_source(app)

    return ActivationResult.fail(
        unsupported_gnome_wayland_message(profile)
        + "\n\nNo se ha aplicado ni XKB ni keyd. "
        "UOK ha vuelto a una fuente GNOME segura para evitar que el teclado quede incoherente.",
        rolled_back=True,
    )
