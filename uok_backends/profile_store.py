import hashlib
import json
import re
import unicodedata
from pathlib import Path

HOME = Path.home()
CONFIG = HOME / ".config" / "teclado-indicador"
PROFILES = CONFIG / "profiles"
KEYD_DIR = CONFIG / "keyd"
XKB_DIR = CONFIG / "xkb"
USER_XKB = HOME / ".xkb" / "symbols"
CURRENT_PROFILE = CONFIG / "current-profile.json"


def ensure_dirs():
    for directory in (CONFIG, PROFILES, KEYD_DIR, XKB_DIR, USER_XKB):
        directory.mkdir(parents=True, exist_ok=True)


def safe_id(name):
    name = unicodedata.normalize("NFKD", str(name or ""))
    name = name.encode("ascii", "ignore").decode("ascii")
    name = name.lower()
    name = re.sub(r"[^a-z0-9]+", "_", name)
    name = name.strip("_")
    return name or "configuracion"


def file_hash(path):
    path = Path(path).expanduser()
    hasher = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def same_file(a, b):
    if not a and not b:
        return True
    if not a or not b:
        return False
    a = Path(a).expanduser()
    b = Path(b).expanduser()
    if not a.exists() or not b.exists():
        return False
    return file_hash(a) == file_hash(b)


def load_profiles(profiles_dir=PROFILES):
    profiles = []
    for file in sorted(Path(profiles_dir).expanduser().glob("*.json")):
        try:
            profile = json.loads(file.read_text(encoding="utf-8"))
            profile["_profile_file"] = str(file)
            profiles.append(profile)
        except Exception:
            pass
    return profiles


def find_profile(name_or_id, profiles_dir=PROFILES):
    for profile in load_profiles(profiles_dir):
        if profile.get("id") == name_or_id or profile.get("name") == name_or_id:
            return profile
    return None


def find_duplicate(xkb_file, keyd_file, profiles_dir=PROFILES):
    for profile in load_profiles(profiles_dir):
        if same_file(xkb_file, profile.get("xkb_file")) and same_file(keyd_file, profile.get("keyd_conf")):
            return profile
    return None


def unique_layout_id(base_id, profiles_dir=PROFILES, user_xkb_dir=USER_XKB, keyd_dir=KEYD_DIR):
    candidate = base_id
    counter = 2
    profiles_dir = Path(profiles_dir).expanduser()
    user_xkb_dir = Path(user_xkb_dir).expanduser()
    keyd_dir = Path(keyd_dir).expanduser()
    while True:
        profile_file = profiles_dir / f"{candidate}.json"
        xkb_file = user_xkb_dir / candidate
        keyd_file = keyd_dir / f"{candidate}.conf"
        if not profile_file.exists() and not xkb_file.exists() and not keyd_file.exists():
            return candidate
        candidate = f"{base_id}_{counter}"
        counter += 1


def delete_file_if_safe(path_str, extra_allowed_dirs=()):
    if not path_str:
        return
    path = Path(path_str).expanduser().resolve()
    allowed_dirs = [USER_XKB.resolve(), KEYD_DIR.resolve(), XKB_DIR.resolve(), PROFILES.resolve()]
    allowed_dirs.extend(Path(p).expanduser().resolve() for p in extra_allowed_dirs)
    allowed = any(str(path).startswith(str(directory) + "/") or path == directory for directory in allowed_dirs)
    if allowed and path.exists() and path.is_file():
        path.unlink()
