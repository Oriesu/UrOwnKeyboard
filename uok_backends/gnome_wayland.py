import subprocess
from pathlib import Path
import time

CONFIG = Path.home() / ".config" / "teclado-indicador"

def run(cmd):
    return subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)

def current_index():
    result = run(["gsettings","get","org.gnome.desktop.input-sources","current"])
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
    (CONFIG / "gnome-wayland-source-request").write_text(f"{index} {token}\n",encoding="utf-8",)
    result = run(["gsettings","set","org.gnome.desktop.input-sources","current",str(index)])
    return result.returncode == 0

def verify_index(index):
    return current_index() == int(index)