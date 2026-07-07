import re
import subprocess
from pathlib import Path

KEYBOARD_PLUGINS = {
    "org.kde.plasma.keyboardlayout",
    "org.kde.plasma.manage-inputmethod",
    "org.kde.plasma.inputmethod",
    "org.kde.plasma.ibus",
}

def run(cmd, env=None):
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env, check=False)
    except Exception:
        pass

def hide_ibus(app):
    env = app.menu_env() if hasattr(app, "menu_env") else None
    run(["gsettings", "set", "org.freedesktop.ibus.panel", "show-icon-on-systray", "false"], env)
    run(["gsettings", "set", "org.freedesktop.ibus.panel", "show-im-name", "false"], env)

def hide_kde(app):
    env = app.menu_env() if hasattr(app, "menu_env") else None
    for tool in ("kwriteconfig6", "kwriteconfig5"):
        run([tool, "--file", "kxkbrc", "--group", "Layout", "--key", "ShowLayoutIndicator", "false"], env)
        run([tool, "--file", "kxkbrc", "--group", "Layout", "--key", "ShowSingle", "false"], env)

    path = Path.home() / ".config" / "plasma-org.kde.plasma.desktop-appletsrc"
    if not path.exists():
        return
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return
    m = re.search(r"SystrayContainmentId=(\d+)", text)
    if not m:
        return

    tray_group = f"Containments][{m.group(1)}][General"
    lines = text.splitlines()
    out = []
    in_tray = False

    def split(v):
        return [x.strip() for x in v.split(",") if x.strip()]

    def join(xs):
        seen, out2 = set(), []
        for x in xs:
            if x and x not in seen:
                out2.append(x)
                seen.add(x)
        return ",".join(out2)

    for line in lines:
        gm = re.match(r"^\[(.+)\]\s*$", line)
        if gm:
            in_tray = gm.group(1) == tray_group
            out.append(line)
            continue
        if in_tray and "=" in line:
            k, v = line.split("=", 1)
            if k == "hiddenItems":
                line = "hiddenItems=" + join(split(v) + sorted(KEYBOARD_PLUGINS))
            elif k in {"shownItems", "extraItems"}:
                line = k + "=" + join([x for x in split(v) if x not in KEYBOARD_PLUGINS])
        out.append(line)

    fixed = "\n".join(out) + "\n"
    if fixed != text:
        backup = path.with_suffix(path.suffix + ".before-uok-hide-native")
        if not backup.exists():
            backup.write_text(text, encoding="utf-8")
        path.write_text(fixed, encoding="utf-8")

def xfconf(args):
    try:
        return subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    except Exception:
        return None

def hide_xfce():
    r = xfconf(["xfconf-query", "-c", "xfce4-panel", "-l"])
    if not r or r.returncode != 0:
        return
    ids = []
    for prop in r.stdout.splitlines():
        m = re.fullmatch(r"/plugins/plugin-(\d+)", prop.strip())
        if not m:
            continue
        g = xfconf(["xfconf-query", "-c", "xfce4-panel", "-p", prop.strip()])
        name = (g.stdout if g else "").strip().lower()
        if "xkb" in name or "keyboard" in name:
            ids.append(int(m.group(1)))
    if not ids:
        return
    remove = set(ids)
    for prop in ("/panels/panel-0/plugin-ids", "/panels/panel-1/plugin-ids"):
        g = xfconf(["xfconf-query", "-c", "xfce4-panel", "-p", prop])
        if not g or g.returncode != 0:
            continue
        vals = []
        for line in g.stdout.splitlines():
            m = re.search(r"(-?\d+)\s*$", line.strip())
            if m:
                vals.append(int(m.group(1)))
        vals2 = [x for x in vals if x not in remove]
        if vals and vals2 != vals:
            cmd = ["xfconf-query", "-c", "xfce4-panel", "-p", prop, "--force-array"]
            for v in vals2:
                cmd += ["-t", "int", "-s", str(v)]
            xfconf(cmd)

def hide_lxqt():
    path = Path.home() / ".config" / "lxqt" / "panel.conf"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8", errors="ignore")
    fixed = re.sub(r",?kbindicator,?|kbindicator,?", lambda m: "," if "," in m.group(0) else "", text)
    fixed = fixed.replace(",,", ",")
    fixed = re.sub(r"\n?\[kbindicator\]\n.*?(?=\n\[[^\]]+\]|\Z)", "\n", fixed, flags=re.S)
    if fixed != text:
        backup = path.with_suffix(path.suffix + ".before-uok-hide-native")
        if not backup.exists():
            backup.write_text(text, encoding="utf-8")
        path.write_text(fixed, encoding="utf-8")

def hide_all_native_indicators(app):
    hide_ibus(app)
    hide_kde(app)
    hide_xfce()
    hide_lxqt()

def install(app):
    app.uok_hide_all_native_indicators = lambda: hide_all_native_indicators(app) or True
    hide_all_native_indicators(app)
