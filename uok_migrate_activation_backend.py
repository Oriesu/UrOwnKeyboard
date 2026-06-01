#!/usr/bin/env python3
from pathlib import Path
import py_compile

ROOT = Path.cwd()
INDICATOR = ROOT / "teclado-indicador.py"
BACKENDS = ROOT / "uok_backends"
ACTIVATION = BACKENDS / "activation.py"
OVERRIDES = BACKENDS / "overrides.py"

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
        + "\\n\\nNo se ha aplicado ni XKB ni keyd. "
        "UOK ha vuelto a una fuente GNOME segura para evitar que el teclado quede incoherente.",
        rolled_back=True,
    )
'''

OVERRIDES_PY = '''from .session import is_gnome_wayland
from . import gnome_wayland
from .profiles import profile_is_custom_xkb
from .activation import block_custom_profile_in_gnome_wayland


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
        # La política de bloqueo ya vive en activation.py.
        if is_gnome_wayland() and profile_is_custom_xkb(profile):
            result = block_custom_profile_in_gnome_wayland(app, profile)
            app.show_error("UrOwnKeyboard - GNOME Wayland", result.message)
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


def main():
    if not INDICATOR.exists():
        raise SystemExit("Ejecuta este script en la raíz de UrOwnKeyboard.")
    if not BACKENDS.exists():
        raise SystemExit("No existe uok_backends.")

    ACTIVATION.write_text(ACTIVATION_PY, encoding="utf-8")
    OVERRIDES.write_text(OVERRIDES_PY, encoding="utf-8")

    py_compile.compile(str(ACTIVATION), doraise=True)
    py_compile.compile(str(OVERRIDES), doraise=True)
    py_compile.compile(str(INDICATOR), doraise=True)

    print("OK: activación GNOME Wayland delegada a uok_backends/activation.py")
    print("OK: overrides.py ahora usa block_custom_profile_in_gnome_wayland().")
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
