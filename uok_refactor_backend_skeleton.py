#!/usr/bin/env python3
from pathlib import Path
import py_compile
import subprocess

ROOT = Path.cwd()
BACKENDS = ROOT / "uok_backends"
INDICATOR = ROOT / "teclado-indicador.py"
INSTALL = ROOT / "install.sh"
MAKE_RELEASE = ROOT / "make-release.sh"
UNINSTALL = ROOT / "uninstall.sh"

KEYD_PY = '''from pathlib import Path
import subprocess

HELPER = Path("/usr/local/sbin/keyd-aplicar-conf")


class KeydResult:
    def __init__(self, ok, stdout="", stderr="", returncode=0):
        self.ok = ok
        self.stdout = stdout or ""
        self.stderr = stderr or ""
        self.returncode = returncode

    @property
    def combined(self):
        return (self.stdout + "\\n" + self.stderr).strip()


def _run(cmd):
    return subprocess.run(
        [str(x) for x in cmd],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def off():
    if not HELPER.exists():
        return KeydResult(True)

    result = _run(["sudo", "-n", str(HELPER), "--off"])
    return KeydResult(result.returncode == 0, result.stdout, result.stderr, result.returncode)


def apply_conf(path):
    if not path:
        return off()

    keyd_path = Path(path).expanduser()

    if not keyd_path.exists():
        return KeydResult(False, stderr=f"keyd.conf no existe: {keyd_path}", returncode=1)

    result = _run(["sudo", "-n", str(HELPER), str(keyd_path)])
    return KeydResult(result.returncode == 0, result.stdout, result.stderr, result.returncode)


def stop_service():
    result = _run(["sudo", "systemctl", "stop", "keyd"])
    return KeydResult(result.returncode == 0, result.stdout, result.stderr, result.returncode)
'''

RESULT_PY = '''class ActivationResult:
    def __init__(self, ok, message="", details="", applied_keyd=False, rolled_back=False):
        self.ok = ok
        self.message = message
        self.details = details
        self.applied_keyd = applied_keyd
        self.rolled_back = rolled_back

    def __bool__(self):
        return self.ok

    @classmethod
    def ok_result(cls, message="", applied_keyd=False):
        return cls(True, message=message, applied_keyd=applied_keyd)

    @classmethod
    def fail(cls, message, details="", rolled_back=False):
        return cls(False, message=message, details=details, rolled_back=rolled_back)
'''

ACTIVATION_PY = '''from .result import ActivationResult
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
            + "\\n\\nNo se ha aplicado ni XKB ni keyd para evitar dejar el teclado incoherente.",
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
'''

X11_PY = '''from .result import ActivationResult


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
'''

GNOME_WAYLAND_CUSTOM_PY = '''from .result import ActivationResult
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
'''

RECOVER_SH = '''#!/usr/bin/env bash
set -u

echo "== Parando UOK y keyd =="
pkill -f teclado-indicador.py 2>/dev/null || true
sudo systemctl stop keyd 2>/dev/null || true

echo "== Quitando layout experimental UOK registrado en sistema =="
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
gsettings get org.gnome.desktop.input-sources sources
gsettings get org.gnome.desktop.input-sources current
ibus engine 2>/dev/null || true
'''


def ensure_compile(path: Path):
    py_compile.compile(str(path), doraise=True)


def patch_install():
    if not INSTALL.exists():
        return

    s = INSTALL.read_text(encoding="utf-8")

    if "uok_backends" in s and "cp -r uok_backends" in s:
        print("OK: install.sh ya parece instalar uok_backends.")
        return

    marker = 'cp "$APP_NAME" "$BIN_DIR/$APP_NAME"'

    if marker in s:
        replacement = marker + '''
if [ -d "uok_backends" ]; then
  mkdir -p "$BIN_DIR/uok_backends"
  cp -r uok_backends/*.py "$BIN_DIR/uok_backends/"
fi'''
        INSTALL.write_text(s.replace(marker, replacement, 1), encoding="utf-8")
        print("OK: install.sh parcheado para uok_backends.")
    else:
        print("AVISO: no encontré punto claro para install.sh; revísalo manualmente.")


def patch_make_release():
    if not MAKE_RELEASE.exists():
        return

    s = MAKE_RELEASE.read_text(encoding="utf-8")

    if "copy_dir uok_backends" in s:
        print("OK: make-release.sh ya copia uok_backends.")
        return

    if "copy_dir helpers" in s:
        s = s.replace("copy_dir helpers", "copy_dir helpers\ncopy_dir uok_backends", 1)
    else:
        s += "\ncopy_dir uok_backends\n"

    MAKE_RELEASE.write_text(s, encoding="utf-8")
    print("OK: make-release.sh parcheado para uok_backends.")


def patch_uninstall():
    if not UNINSTALL.exists():
        return

    s = UNINSTALL.read_text(encoding="utf-8")

    if "uok_backends" in s:
        print("OK: uninstall.sh ya menciona uok_backends.")
        return

    s += '\n# UOK backend modules\nrm -rf "$HOME/.local/bin/uok_backends" 2>/dev/null || true\n'
    UNINSTALL.write_text(s, encoding="utf-8")
    print("OK: uninstall.sh parcheado para borrar uok_backends.")


def main():
    if not INDICATOR.exists():
        raise SystemExit("Ejecuta este script en ~/UrOwnKeyboard.")

    BACKENDS.mkdir(exist_ok=True)
    (BACKENDS / "__init__.py").write_text("", encoding="utf-8")
    (BACKENDS / "keyd.py").write_text(KEYD_PY, encoding="utf-8")
    (BACKENDS / "result.py").write_text(RESULT_PY, encoding="utf-8")
    (BACKENDS / "activation.py").write_text(ACTIVATION_PY, encoding="utf-8")
    (BACKENDS / "x11.py").write_text(X11_PY, encoding="utf-8")
    (BACKENDS / "gnome_wayland_custom.py").write_text(GNOME_WAYLAND_CUSTOM_PY, encoding="utf-8")

    recover = ROOT / "uok_recover_gnome_wayland.sh"
    recover.write_text(RECOVER_SH, encoding="utf-8")
    recover.chmod(0o755)

    for path in BACKENDS.glob("*.py"):
        ensure_compile(path)
    ensure_compile(INDICATOR)

    patch_install()
    patch_make_release()
    patch_uninstall()

    print()
    print("OK: esqueleto de reestructuración creado.")
    print("Archivos nuevos:")
    for name in ["result.py", "keyd.py", "activation.py", "x11.py", "gnome_wayland_custom.py"]:
        print(f"  uok_backends/{name}")
    print("  uok_recover_gnome_wayland.sh")


if __name__ == "__main__":
    main()
