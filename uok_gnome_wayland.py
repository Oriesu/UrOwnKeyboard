import time
from pathlib import Path
import subprocess

CONFIG = Path.home() / ".config" / "teclado-indicador"

def request_input_source(index):
    CONFIG.mkdir(parents=True, exist_ok=True)

    req = CONFIG / "gnome-wayland-source-request"
    token = int(time.time() * 1000)
    req.write_text(f"{index} {token}\n", encoding="utf-8")

    subprocess.run([
        "gsettings",
        "set",
        "org.gnome.desktop.input-sources",
        "current",
        str(index),
    ], check=False)

    return True
