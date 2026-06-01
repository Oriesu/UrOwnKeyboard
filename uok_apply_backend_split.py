#!/usr/bin/env python3
from pathlib import Path
import py_compile
import shutil
import sys

ROOT = Path.cwd()
INDICATOR = ROOT / "teclado-indicador.py"
BACKUP = ROOT / "teclado-indicador.py.bak-gnome-wayland-switch"
BACKENDS = ROOT / "uok_backends"

SESSION_PY = r'import os\n\n\ndef session_type():\n    return os.environ.get("XDG_SESSION_TYPE", "").lower()\n\n\ndef desktop_text():\n    return " ".join([\n        os.environ.get("XDG_CURRENT_DESKTOP", ""),\n        os.environ.get("DESKTOP_SESSION", ""),\n        os.environ.get("XDG_SESSION_DESKTOP", ""),\n    ]).lower()\n\n\ndef is_wayland():\n    return session_type() == "wayland"\n\n\ndef is_gnome():\n    return "gnome" in desktop_text()\n\n\ndef is_gnome_wayland():\n    return is_gnome() and is_wayland()\n'

GNOME_WAYLAND_PY = r'import subprocess\nfrom pathlib import Path\nimport time\n\n\nCONFIG = Path.home() / ".config" / "teclado-indicador"\n\n\ndef run(cmd):\n    return subprocess.run(\n        cmd,\n        text=True,\n        stdout=subprocess.PIPE,\n        stderr=subprocess.PIPE,\n        check=False,\n    )\n\n\ndef current_index():\n    result = run([\n        "gsettings",\n        "get",\n        "org.gnome.desktop.input-sources",\n        "current",\n    ])\n\n    text = result.stdout.strip()\n\n    if text.startswith("uint32 "):\n        text = text.split(None, 1)[1]\n\n    try:\n        return int(text)\n    except Exception:\n        return None\n\n\ndef set_current_index(index):\n    CONFIG.mkdir(parents=True, exist_ok=True)\n\n    token = int(time.time() * 1000)\n    (CONFIG / "gnome-wayland-source-request").write_text(\n        f"{index} {token}\\n",\n        encoding="utf-8",\n    )\n\n    result = run([\n        "gsettings",\n        "set",\n        "org.gnome.desktop.input-sources",\n        "current",\n        str(index),\n    ])\n\n    return result.returncode == 0\n\n\ndef verify_index(index):\n    return current_index() == int(index)\n'

PROFILES_PY = r'def profile_name(profile):\n    return profile.get("name") or profile.get("id") or "perfil UOK"\n\n\ndef profile_is_custom_xkb(profile):\n    return profile.get("type") != "gnome-source"\n\n\ndef unsupported_gnome_wayland_message(profile):\n    name = profile_name(profile)\n\n    return (\n        "Este perfil UOK usa una distribución XKB propia.\\n\\n"\n        "En GNOME Wayland UOK todavía no puede aplicar perfiles XKB personalizados "\n        "con setxkbmap/xkbcomp, porque no cambian el layout real del compositor.\\n\\n"\n        f"Perfil no aplicado: {name}\\n\\n"\n        "Usa GNOME X11 para perfiles propios, o instala esta distribución como "\n        "fuente XKB del sistema/GNOME."\n    )\n'

OVERRIDES_PY = r'from .session import is_gnome_wayland\nfrom . import gnome_wayland\nfrom .profiles import profile_is_custom_xkb, unsupported_gnome_wayland_message\n\n\ndef _is_setxkbmap_cmd(cmd):\n    if isinstance(cmd, (list, tuple)):\n        return len(cmd) > 0 and cmd[0] == "setxkbmap"\n    if isinstance(cmd, str):\n        return "setxkbmap" in cmd\n    return False\n\n\ndef install(app):\n    base_run_menu_cmd = app.run_menu_cmd\n    base_sh = getattr(app, "sh", None)\n    base_activar_gnome_source = app.activar_gnome_source\n    base_activar_profile = app.activar_profile\n\n    def run_menu_cmd(cmd, *args, **kwargs):\n        if is_gnome_wayland() and _is_setxkbmap_cmd(cmd):\n            return app.subprocess.CompletedProcess(cmd, 1, stdout="", stderr="")\n        return base_run_menu_cmd(cmd, *args, **kwargs)\n\n    def sh(cmd, *args, **kwargs):\n        if is_gnome_wayland() and _is_setxkbmap_cmd(cmd):\n            return ""\n        if base_sh is None:\n            return ""\n        return base_sh(cmd, *args, **kwargs)\n\n    def activar_gnome_source(index, source_type, source_id):\n        if not is_gnome_wayland():\n            return base_activar_gnome_source(index, source_type, source_id)\n\n        label = app.source_label(source_type, source_id)\n\n        if source_type != "xkb":\n            app.show_error(\n                "UrOwnKeyboard - GNOME Wayland",\n                "Esta fuente no es XKB y todavía no está soportada en GNOME Wayland.",\n            )\n            return\n\n        app.aplicar_keyd_off_sync()\n\n        if not gnome_wayland.set_current_index(index):\n            app.show_error(\n                "UrOwnKeyboard - GNOME Wayland",\n                "No se pudo cambiar la fuente de entrada de GNOME.",\n            )\n            return\n\n        if not gnome_wayland.verify_index(index):\n            app.show_error(\n                "UrOwnKeyboard - verificación",\n                f"GNOME no cambió al índice esperado. Esperado: {index}. Actual: {gnome_wayland.current_index()}",\n            )\n            return\n\n        current = {\n            "type": "gnome-source",\n            "name": label,\n            "source_type": source_type,\n            "source_id": source_id,\n            "desktop": "gnome-wayland",\n            "keyd_conf": None,\n        }\n\n        app.CURRENT_PROFILE.write_text(\n            app.json.dumps(current, indent=2, ensure_ascii=False)\n        )\n\n        app.notify("Keyboard", label + " activated")\n\n    def activar_profile(profile):\n        if is_gnome_wayland() and profile_is_custom_xkb(profile):\n            app.show_error(\n                "UrOwnKeyboard - GNOME Wayland",\n                unsupported_gnome_wayland_message(profile),\n            )\n            return\n\n        return base_activar_profile(profile)\n\n    app.run_menu_cmd = run_menu_cmd\n    if base_sh is not None:\n        app.sh = sh\n    app.activar_gnome_source = activar_gnome_source\n    app.activar_profile = activar_profile\n'

INSERT = """# UOK backend overrides
try:
    from uok_backends.overrides import install as uok_install_backend_overrides
    uok_install_backend_overrides(__import__(__name__))
except Exception as exc:
    print(f'UOK backend overrides disabled: {exc}')

"""


def compile_one(path: Path):
    py_compile.compile(str(path), doraise=True)


def main():
    if not INDICATOR.exists():
        raise SystemExit("No existe teclado-indicador.py en este directorio.")

    if BACKUP.exists():
        print("Restaurando teclado-indicador.py desde backup estable...")
        shutil.copy2(BACKUP, INDICATOR)
    else:
        print("AVISO: no existe teclado-indicador.py.bak-gnome-wayland-switch; parcheando el archivo actual.")

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

    # Quitar inserciones anteriores completas, si existen.
    while "# UOK backend overrides" in s:
        start = s.find("# UOK backend overrides")
        end = s.find("\n\n", start)
        if end == -1:
            break
        s = s[:start] + s[end + 2:]

    marker = "uok_hide_kde_ibus_native_menu()"
    if marker not in s:
        raise SystemExit("No encontré uok_hide_kde_ibus_native_menu().")

    # Importante: se instala antes de sincronizar_estado_al_arrancar().
    s = s.replace(marker, INSERT + marker, 1)

    INDICATOR.write_text(s, encoding="utf-8")
    compile_one(INDICATOR)

    print("OK: división GNOME Wayland aplicada y teclado-indicador.py compila.")
    print()
    print("Siguientes comandos:")
    print("  cp teclado-indicador.py ~/.local/bin/teclado-indicador.py")
    print("  mkdir -p ~/.local/bin/uok_backends")
    print("  cp uok_backends/*.py ~/.local/bin/uok_backends/")
    print("  chmod +x ~/.local/bin/teclado-indicador.py")
    print("  pkill -f teclado-indicador.py 2>/dev/null || true")
    print("  ~/.local/bin/teclado-indicador.py &")


if __name__ == "__main__":
    main()
