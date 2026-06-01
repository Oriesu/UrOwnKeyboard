#!/usr/bin/env python3
from pathlib import Path
import py_compile
import shutil
import textwrap

ROOT = Path.cwd()
INDICATOR = ROOT / "teclado-indicador.py"
BACKUP = ROOT / "teclado-indicador.py.bak-gnome-wayland-switch"
BACKENDS = ROOT / "uok_backends"

SESSION_PY = '''import os


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
'''

GNOME_WAYLAND_PY = '''import subprocess
from pathlib import Path
import time


CONFIG = Path.home() / ".config" / "teclado-indicador"


def run(cmd):
    return subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def current_index():
    result = run([
        "gsettings",
        "get",
        "org.gnome.desktop.input-sources",
        "current",
    ])

    text = result.stdout.strip()

    if text.startswith("uint32 "):
        text = text.split(None, 1)[1]

    try:
        return int(text)
    except Exception:
        return None


def set_current_index(index):
    CONFIG.mkdir(parents=True, exist_ok=True)

    token = int(time.time() * 1000)
    (CONFIG / "gnome-wayland-source-request").write_text(
        f"{index} {token}\\n",
        encoding="utf-8",
    )

    result = run([
        "gsettings",
        "set",
        "org.gnome.desktop.input-sources",
        "current",
        str(index),
    ])

    return result.returncode == 0


def verify_index(index):
    return current_index() == int(index)
'''

PROFILES_PY = '''def profile_name(profile):
    return profile.get("name") or profile.get("id") or "perfil UOK"


def profile_is_custom_xkb(profile):
    return profile.get("type") != "gnome-source"


def unsupported_gnome_wayland_message(profile):
    name = profile_name(profile)

    return (
        "Este perfil UOK usa una distribución XKB propia.\\n\\n"
        "En GNOME Wayland UOK todavía no puede aplicar perfiles XKB personalizados "
        "con setxkbmap/xkbcomp, porque no cambian el layout real del compositor.\\n\\n"
        f"Perfil no aplicado: {name}\\n\\n"
        "Usa GNOME X11 para perfiles propios, o instala esta distribución como "
        "fuente XKB del sistema/GNOME."
    )
'''

OVERRIDES_PY = '''from .session import is_gnome_wayland
from . import gnome_wayland
from .profiles import profile_is_custom_xkb, unsupported_gnome_wayland_message


def _is_setxkbmap_cmd(cmd):
    if isinstance(cmd, (list, tuple)):
        return len(cmd) > 0 and cmd[0] == "setxkbmap"
    if isinstance(cmd, str):
        return "setxkbmap" in cmd
    return False


def install(app):
    base_run_menu_cmd = app.run_menu_cmd
    base_sh = getattr(app, "sh", None)
    base_subprocess_run = app.subprocess.run

    base_activar_gnome_source = app.activar_gnome_source
    base_activar_profile = app.activar_profile

    def _fake_completed(cmd):
        return app.subprocess.CompletedProcess(cmd, 1, stdout="", stderr="")

    def run_menu_cmd(cmd, *args, **kwargs):
        if is_gnome_wayland() and _is_setxkbmap_cmd(cmd):
            return _fake_completed(cmd)
        return base_run_menu_cmd(cmd, *args, **kwargs)

    def sh(cmd, *args, **kwargs):
        if is_gnome_wayland() and _is_setxkbmap_cmd(cmd):
            return ""
        if base_sh is None:
            return ""
        return base_sh(cmd, *args, **kwargs)

    def subprocess_run(cmd, *args, **kwargs):
        if is_gnome_wayland() and _is_setxkbmap_cmd(cmd):
            return _fake_completed(cmd)
        return base_subprocess_run(cmd, *args, **kwargs)

    def activar_gnome_source(index, source_type, source_id):
        if not is_gnome_wayland():
            return base_activar_gnome_source(index, source_type, source_id)

        label = app.source_label(source_type, source_id)

        if source_type != "xkb":
            app.show_error(
                "UrOwnKeyboard - GNOME Wayland",
                "Esta fuente no es XKB y todavía no está soportada en GNOME Wayland.",
            )
            return

        app.aplicar_keyd_off_sync()

        if not gnome_wayland.set_current_index(index):
            app.show_error(
                "UrOwnKeyboard - GNOME Wayland",
                "No se pudo cambiar la fuente de entrada de GNOME.",
            )
            return

        if not gnome_wayland.verify_index(index):
            app.show_error(
                "UrOwnKeyboard - verificación",
                f"GNOME no cambió al índice esperado. Esperado: {index}. Actual: {gnome_wayland.current_index()}",
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

        app.CURRENT_PROFILE.write_text(
            app.json.dumps(current, indent=2, ensure_ascii=False)
        )

        app.notify("Keyboard", label + " activated")

    def activar_profile(profile):
        if is_gnome_wayland() and profile_is_custom_xkb(profile):
            app.show_error(
                "UrOwnKeyboard - GNOME Wayland",
                unsupported_gnome_wayland_message(profile),
            )
            return

        return base_activar_profile(profile)

    app.run_menu_cmd = run_menu_cmd
    app.subprocess.run = subprocess_run

    if base_sh is not None:
        app.sh = sh

    app.activar_gnome_source = activar_gnome_source
    app.activar_profile = activar_profile
'''

INSERT = '''# UOK backend overrides
try:
    from uok_backends.overrides import install as uok_install_backend_overrides
    uok_install_backend_overrides(__import__(__name__))
except Exception as exc:
    print(f'UOK backend overrides disabled: {exc}')

'''


def compile_one(path: Path):
    py_compile.compile(str(path), doraise=True)


def remove_old_insertions(s: str) -> str:
    # Remove earlier complete backend override loader blocks.
    while "# UOK backend overrides" in s:
        start = s.find("# UOK backend overrides")
        marker_after = "uok_hide_kde_ibus_native_menu()"
        end = s.find(marker_after, start)
        if end == -1:
            # fallback: remove until double newline after except/print block
            end = s.find("\n\n", start)
            if end == -1:
                break
            s = s[:start] + s[end + 2:]
        else:
            s = s[:start] + s[end:]
    return s


def main():
    if not INDICATOR.exists():
        raise SystemExit("No existe teclado-indicador.py en este directorio.")

    if BACKUP.exists():
        print("Restaurando teclado-indicador.py desde backup estable...")
        shutil.copy2(BACKUP, INDICATOR)
    else:
        print("AVISO: no existe backup estable; se parchea el archivo actual.")

    BACKENDS.mkdir(exist_ok=True)
    (BACKENDS / "__init__.py").write_text("", encoding="utf-8")
    (BACKENDS / "session.py").write_text(SESSION_PY, encoding="utf-8")
    (BACKENDS / "gnome_wayland.py").write_text(GNOME_WAYLAND_PY, encoding="utf-8")
    (BACKENDS / "profiles.py").write_text(PROFILES_PY, encoding="utf-8")
    (BACKENDS / "overrides.py").write_text(OVERRIDES_PY, encoding="utf-8")

    for path in [
        BACKENDS / "session.py",
        BACKENDS / "gnome_wayland.py",
        BACKENDS / "profiles.py",
        BACKENDS / "overrides.py",
    ]:
        compile_one(path)

    s = INDICATOR.read_text(encoding="utf-8")
    s = remove_old_insertions(s)

    marker = "uok_hide_kde_ibus_native_menu()"
    if marker not in s:
        raise SystemExit("No encontré uok_hide_kde_ibus_native_menu().")

    # Must run before uok_hide_kde_ibus_native_menu(), ocultar_menu_xfce(),
    # and sincronizar_estado_al_arrancar().
    s = s.replace(marker, INSERT + marker, 1)

    INDICATOR.write_text(s, encoding="utf-8")
    compile_one(INDICATOR)

    print("OK: backend split fixed.")
    print("OK: teclado-indicador.py and uok_backends/*.py compile.")
    print()
    print("Now run:")
    print("  cp teclado-indicador.py ~/.local/bin/teclado-indicador.py")
    print("  mkdir -p ~/.local/bin/uok_backends")
    print("  cp uok_backends/*.py ~/.local/bin/uok_backends/")
    print("  chmod +x ~/.local/bin/teclado-indicador.py")
    print("  pkill -f teclado-indicador.py 2>/dev/null || true")
    print("  ~/.local/bin/teclado-indicador.py &")


if __name__ == "__main__":
    main()
