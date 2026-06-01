#!/usr/bin/env python3
from pathlib import Path
import py_compile

ROOT = Path.cwd()
INDICATOR = ROOT / "teclado-indicador.py"
BACKENDS = ROOT / "uok_backends"
KEYD = BACKENDS / "keyd.py"

KEYD_PY = '''from pathlib import Path
import subprocess


HELPER = Path("/usr/local/sbin/keyd-aplicar-conf")


class KeydResult:
    def __init__(self, ok, stdout="", stderr="", returncode=0):
        self.ok = bool(ok)
        self.stdout = stdout or ""
        self.stderr = stderr or ""
        self.returncode = int(returncode or 0)

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


def helper_exists():
    return HELPER.exists()


def off():
    if not HELPER.exists():
        return KeydResult(True)

    # El helper de UOK acepta --off en versiones recientes.
    result = _run(["sudo", "-n", str(HELPER), "--off"])

    if result.returncode == 0:
        return KeydResult(True, result.stdout, result.stderr, result.returncode)

    # Compatibilidad con helpers antiguos que usaban argumento vacío.
    fallback = _run(["sudo", "-n", str(HELPER), ""])
    return KeydResult(
        fallback.returncode == 0,
        fallback.stdout + result.stdout,
        fallback.stderr + result.stderr,
        fallback.returncode,
    )


def apply_conf(path):
    if not path:
        return off()

    keyd_path = Path(path).expanduser()

    if not keyd_path.exists():
        return KeydResult(False, stderr=f"keyd.conf no existe: {keyd_path}", returncode=1)

    result = _run(["sudo", "-n", str(HELPER), str(keyd_path)])

    return KeydResult(
        result.returncode == 0,
        result.stdout,
        result.stderr,
        result.returncode,
    )


def is_service_active():
    result = _run(["systemctl", "is-active", "keyd"])
    return result.returncode == 0 and result.stdout.strip() == "active"


def stop_service():
    result = _run(["sudo", "systemctl", "stop", "keyd"])
    return KeydResult(
        result.returncode == 0,
        result.stdout,
        result.stderr,
        result.returncode,
    )


def apply_profile_or_off(profile):
    keyd_conf = profile.get("keyd_conf") if profile else None
    if keyd_conf:
        return apply_conf(keyd_conf)
    return off()
'''

KEYD_OVERRIDE_BLOCK = '''
# UOK keyd backend delegation
# This block must stay late in the file, after older keyd helper definitions.
try:
    from uok_backends import keyd as uok_keyd_backend

    def aplicar_keyd_off_sync():
        result = uok_keyd_backend.off()
        if not result.ok:
            try:
                show_error(
                    "UrOwnKeyboard - keyd",
                    "No se pudo desactivar keyd. Se continuará si el backend lo permite.\\n\\n"
                    + result.combined,
                )
            except Exception:
                pass
        return result.ok

    def aplicar_keyd_de_profile_o_apagar(profile):
        result = uok_keyd_backend.apply_profile_or_off(profile)
        if not result.ok:
            try:
                show_error(
                    "UrOwnKeyboard - keyd",
                    "No se pudo aplicar keyd para este perfil.\\n\\n" + result.combined,
                )
            except Exception:
                pass
        return result.ok

    def keyd_is_active():
        return uok_keyd_backend.is_service_active()

except Exception as exc:
    print(f"UOK keyd backend delegation disabled: {exc}")

'''


def remove_existing_block(text):
    marker = "# UOK keyd backend delegation"
    while marker in text:
        start = text.find(marker)
        # End before the next known late marker, otherwise after double newline.
        candidates = [
            text.find("# UOK backend overrides", start),
            text.find("uok_hide_kde_ibus_native_menu()", start),
        ]
        candidates = [x for x in candidates if x != -1]
        if candidates:
            end = min(candidates)
            text = text[:start] + text[end:]
            continue

        end = text.find("\n\n", start)
        if end == -1:
            text = text[:start]
        else:
            text = text[:start] + text[end + 2:]
    return text


def insert_late(text):
    marker = "# UOK backend overrides"
    if marker in text:
        return text.replace(marker, KEYD_OVERRIDE_BLOCK + marker, 1)

    call = "\nuok_hide_kde_ibus_native_menu()\n"
    if call in text:
        return text.replace(call, "\n" + KEYD_OVERRIDE_BLOCK + "uok_hide_kde_ibus_native_menu()\n", 1)

    raise SystemExit("No encontré punto de inserción tardío para el backend keyd.")


def main():
    if not INDICATOR.exists():
        raise SystemExit("Ejecuta este script en la raíz de UrOwnKeyboard.")
    if not BACKENDS.exists():
        raise SystemExit("No existe uok_backends. Ejecuta antes el esqueleto de backends.")

    KEYD.write_text(KEYD_PY, encoding="utf-8")
    py_compile.compile(str(KEYD), doraise=True)

    text = INDICATOR.read_text(encoding="utf-8")
    text = remove_existing_block(text)
    text = insert_late(text)
    INDICATOR.write_text(text, encoding="utf-8")

    py_compile.compile(str(INDICATOR), doraise=True)

    print("OK: keyd migrado como delegación tardía a uok_backends/keyd.py")
    print()
    print("Instala con:")
    print("  cp teclado-indicador.py ~/.local/bin/teclado-indicador.py")
    print("  mkdir -p ~/.local/bin/uok_backends")
    print("  cp uok_backends/*.py ~/.local/bin/uok_backends/")
    print("  chmod +x ~/.local/bin/teclado-indicador.py")
    print()
    print("Prueba:")
    print("  pkill -f teclado-indicador.py 2>/dev/null || true")
    print("  ~/.local/bin/teclado-indicador.py &")


if __name__ == "__main__":
    main()
