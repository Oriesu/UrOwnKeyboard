from pathlib import Path
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
        return (self.stdout + "\n" + self.stderr).strip()

def _run(cmd):
    return subprocess.run([str(x) for x in cmd],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)

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
    return KeydResult(fallback.returncode == 0,fallback.stdout + result.stdout,fallback.stderr + result.stderr,fallback.returncode)

def apply_conf(path):
    if not path:
        return off()
    keyd_path = Path(path).expanduser()
    if not keyd_path.exists():
        return KeydResult(False, stderr=f"keyd.conf no existe: {keyd_path}", returncode=1)
    result = _run(["sudo", "-n", str(HELPER), str(keyd_path)])
    return KeydResult(result.returncode == 0,result.stdout,result.stderr,result.returncode)

def is_service_active():
    result = _run(["systemctl", "is-active", "keyd"])
    return result.returncode == 0 and result.stdout.strip() == "active"

def stop_service():
    result = _run(["sudo", "systemctl", "stop", "keyd"])
    return KeydResult(result.returncode == 0,result.stdout,result.stderr,result.returncode)

def apply_profile_or_off(profile):
    keyd_conf = profile.get("keyd_conf") if profile else None
    if keyd_conf:
        return apply_conf(keyd_conf)
    return off()
