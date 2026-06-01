import os


def session_type():
    return os.environ.get("XDG_SESSION_TYPE", "").lower()


def desktop_text():
    return " ".join([
        os.environ.get("XDG_CURRENT_DESKTOP", ""),
        os.environ.get("DESKTOP_SESSION", ""),
        os.environ.get("XDG_SESSION_DESKTOP", ""),
    ]).lower()


def is_wayland():
    return session_type() == "wayland"


def is_gnome():
    return "gnome" in desktop_text()


def is_gnome_wayland():
    return is_gnome() and is_wayland()
