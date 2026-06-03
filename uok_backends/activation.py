from .result import ActivationResult
from . import keyd
from .profiles import unsupported_gnome_wayland_message

def _set_ibus_engine(app, ibus_engine):
    try:
        app.subprocess.run(["ibus", "engine", ibus_engine],text=True,stdout=app.subprocess.PIPE,stderr=app.subprocess.PIPE,check=False)
    except Exception:
        pass

def reset_gnome_wayland_to_safe_source(app, index=0, ibus_engine="xkb:es::spa"):
    keyd.off()
    try:
        from . import gnome_wayland
        gnome_wayland.set_current_index(index)
    except Exception:
        pass
    _set_ibus_engine(app, ibus_engine)

def block_custom_profile_in_gnome_wayland(app, profile):
    reset_gnome_wayland_to_safe_source(app)
    return ActivationResult.fail(unsupported_gnome_wayland_message(profile) + "\n\nNo se ha aplicado ni XKB ni keyd. "
        "UOK ha vuelto a una fuente GNOME segura para evitar que el teclado quede incoherente.",rolled_back=True)