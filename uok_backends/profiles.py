def profile_name(profile):
    return profile.get("name") or profile.get("id") or "perfil UOK"


def profile_is_custom_xkb(profile):
    return profile.get("type") != "gnome-source"


def unsupported_gnome_wayland_message(profile):
    name = profile_name(profile)

    return (
        "Este perfil UOK usa una distribución XKB propia.\n\n"
        "En GNOME Wayland UOK todavía no puede aplicar perfiles XKB personalizados "
        "con setxkbmap/xkbcomp, porque no cambian el layout real del compositor.\n\n"
        f"Perfil no aplicado: {name}\n\n"
        "Usa GNOME X11 para perfiles propios, o instala esta distribución como "
        "fuente XKB del sistema/GNOME."
    )
