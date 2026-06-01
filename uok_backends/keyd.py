from pathlib import Path
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
        return (self.stdout + "\n" + self.stderr).strip()


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
