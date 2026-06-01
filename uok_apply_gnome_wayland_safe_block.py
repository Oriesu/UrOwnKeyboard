#!/usr/bin/env python3
from pathlib import Path
import py_compile

ROOT = Path.cwd()
BACKENDS = ROOT / "uok_backends"
OVERRIDES = BACKENDS / "overrides.py"
RECOVER = ROOT / "uok_recover_gnome_wayland.sh"

OVERRIDES_PY = '''from .session import is_gnome_wayland
from . import gnome_wayland
from .profiles import profile_is_custom_xkb, unsupported_gnome_wayland_message


IBUS_ENGINE_BY_XKB = {
    "es": "xkb:es::spa",
    "de": "xkb:de::ger",
    "us": "xkb:us::eng",
    "gb": "xkb:gb::eng",
    "fr": "xkb:fr::fra",
    "it": "xkb:it::ita",
    "pt": "xkb:pt::por",
}


def _cmd_text(cmd):
    if isinstance(cmd, (list, tuple)):
        return " ".join(str(x) for x in cmd)
    return str(cmd)


def _is_setxkbmap_cmd(cmd):
    return "setxkbmap" in _cmd_text(cmd)


def _ibus_engine_for_source(source_type, source_id):
    if source_type != "xkb":
        return None
    return IBUS_ENGINE_BY_XKB.get(source_id)


def _force_ibus_engine(app, source_type, source_id):
    engine = _ibus_engine_for_source(source_type, source_id)
    if not engine:
        return

    try:
        app.subprocess.run(
            ["ibus", "engine", engine],
            text=True,
            stdout=app.subprocess.PIPE,
            stderr=app.subprocess.PIPE,
            check=False,
        )
    except Exception:
        pass


def _safe_reset_to_first_gnome_source(app):
    try:
        app.aplicar_keyd_off_sync()
    except Exception:
        pass

    try:
        gnome_wayland.set_current_index(0)
    except Exception:
        pass

    try:
        app.subprocess.run(
            ["ibus", "engine", "xkb:es::spa"],
            text=True,
            stdout=app.subprocess.PIPE,
            stderr=app.subprocess.PIPE,
            check=False,
        )
    except Exception:
        pass


def install(app):
    base_run_menu_cmd = app.run_menu_cmd
    base_sh = getattr(app, "sh", None)
    base_subprocess_run = app.subprocess.run
    base_popen = app.subprocess.Popen

    base_activar_gnome_source = app.activar_gnome_source
    base_activar_profile = app.activar_profile

    def _fake_completed(cmd, returncode=0):
        return app.subprocess.CompletedProcess(cmd, returncode, stdout="", stderr="")

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

    def subprocess_popen(cmd, *args, **kwargs):
        if is_gnome_wayland() and _is_setxkbmap_cmd(cmd):
            class DummyProcess:
                returncode = 0
                pid = 0
                def poll(self): return 0
                def wait(self, timeout=None): return 0
                def communicate(self, input=None, timeout=None): return ("", "")
            return DummyProcess()
        return base_popen(cmd, *args, **kwargs)

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

        _force_ibus_engine(app, source_type, source_id)

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
        # GNOME Wayland: bloqueo duro de perfiles propios/importados.
        # No debe llamar a uok activate, porque esa ruta puede aplicar keyd aunque
        # el XKB real no cambie.
        if is_gnome_wayland() and profile_is_custom_xkb(profile):
            _safe_reset_to_first_gnome_source(app)
            app.show_error(
                "UrOwnKeyboard - GNOME Wayland",
                unsupported_gnome_wayland_message(profile)
                + "\\n\\nNo se ha aplicado ni XKB ni keyd. "
                "UOK ha vuelto a una fuente GNOME segura para evitar que el teclado quede incoherente.",
            )
            return

        return base_activar_profile(profile)

    app.run_menu_cmd = run_menu_cmd
    app.subprocess.run = subprocess_run
    app.subprocess.Popen = subprocess_popen

    if base_sh is not None:
        app.sh = sh

    app.activar_gnome_source = activar_gnome_source
    app.activar_profile = activar_profile
'''

RECOVER_SH = '''#!/usr/bin/env bash
set -u

echo "== Parando UOK y keyd =="
pkill -f teclado-indicador.py 2>/dev/null || true
sudo systemctl stop keyd 2>/dev/null || true

echo "== Quitando layout experimental =="
sudo rm -f /usr/share/X11/xkb/symbols/uok_mi_teclado_visual 2>/dev/null || true

echo "== Reinstalando xkb-data =="
sudo apt install --reinstall -y xkb-data

echo "== Restaurando GNOME sources =="
gsettings set org.gnome.desktop.input-sources sources "[('xkb', 'es'), ('xkb', 'de')]"
gsettings set org.gnome.desktop.input-sources mru-sources "[('xkb', 'es'), ('xkb', 'de')]"
gsettings set org.gnome.desktop.input-sources current 0
gsettings set org.gnome.desktop.input-sources xkb-options "[]"

echo "== Restaurando IBus =="
gsettings set org.freedesktop.ibus.general preload-engines "['xkb:es::spa', 'xkb:de::ger']"
gsettings set org.freedesktop.ibus.general engines-order "['xkb:es::spa', 'xkb:de::ger']"
gsettings set org.freedesktop.ibus.general use-xmodmap false

ibus restart 2>/dev/null || true
sleep 2
ibus engine xkb:es::spa 2>/dev/null || true

echo "== Limpiando estado UOK =="
rm -f "$HOME/.config/teclado-indicador/current-profile.json"
rm -f "$HOME/.config/teclado-indicador/gnome-wayland-source-request"

echo "== Estado =="
echo "GNOME sources:"
gsettings get org.gnome.desktop.input-sources sources
echo "GNOME current:"
gsettings get org.gnome.desktop.input-sources current
echo "IBus:"
ibus engine 2>/dev/null || true

echo
echo "Si IBus sigue en us, cierra sesión y vuelve a entrar en GNOME Wayland."
'''


def main():
    if not BACKENDS.exists():
        raise SystemExit("No existe uok_backends. Ejecuta antes el split de backends.")

    OVERRIDES.write_text(OVERRIDES_PY, encoding="utf-8")
    RECOVER.write_text(RECOVER_SH, encoding="utf-8")
    RECOVER.chmod(0o755)

    py_compile.compile(str(OVERRIDES), doraise=True)
    py_compile.compile(str(ROOT / "teclado-indicador.py"), doraise=True)

    print("OK: parche aplicado.")
    print(" - GNOME Wayland bloquea perfiles UOK propios/importados antes de uok activate/keyd.")
    print(" - Al cambiar es/de fuerza también el engine IBus conocido.")
    print(" - Creado helper: ./uok_recover_gnome_wayland.sh")
    print()
    print("Instala con:")
    print("  cp teclado-indicador.py ~/.local/bin/teclado-indicador.py")
    print("  mkdir -p ~/.local/bin/uok_backends")
    print("  cp uok_backends/*.py ~/.local/bin/uok_backends/")
    print("  chmod +x ~/.local/bin/teclado-indicador.py")
    print("  pkill -f teclado-indicador.py 2>/dev/null || true")
    print("  ~/.local/bin/teclado-indicador.py &")


if __name__ == "__main__":
    main()
