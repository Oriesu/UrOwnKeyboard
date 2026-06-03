import ast
import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import textwrap
from pathlib import Path

from .result import ActivationResult
from .profile_store import safe_id

GNOME_SCHEMA = "org.gnome.desktop.input-sources"
GNOME_KEY = "sources"
SYSTEM_SYMBOLS_DIR = Path("/usr/share/X11/xkb/symbols")
EVDEV_XML = Path("/usr/share/X11/xkb/rules/evdev.xml")
CONFIG = Path.home() / ".config" / "teclado-indicador"
PROFILES = CONFIG / "profiles"
CURRENT_PROFILE = CONFIG / "current-profile.json"


def run(cmd, **kwargs):
    return subprocess.run([str(x) for x in cmd], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, **kwargs)


def profile_system_xkb_id(profile):
    """Return the technical GNOME/XKB layout id for a UOK profile.

    Use the profile id itself as the system layout id. This mirrors the case
    that worked in testing (uok_test_wayland): GNOME's technical source and
    the UOK profile have the same id, while UOK hides the technical source from
    its own UI. Older patches prefixed non-uok profiles as uok_<id>; those
    sources are still cleaned up/hidden, but new and reactivated profiles use
    the profile id directly.
    """
    profile_id = (profile or {}).get("id") or (profile or {}).get("name") or "profile"
    return safe_id(str(profile_id))


def legacy_profile_system_xkb_ids(profile):
    ids = []
    existing = (profile or {}).get("system_xkb_id")
    if existing:
        ids.append(str(existing))
    try:
        canonical = profile_system_xkb_id(profile)
    except Exception:
        canonical = None
    if canonical:
        ids.append(canonical)
        if not canonical.startswith("uok_"):
            ids.append("uok_" + canonical)
    out = []
    seen = set()
    for value in ids:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def _profile_file(profile):
    path = (profile or {}).get("_profile_file")
    if path:
        return Path(path).expanduser()
    profile_id = (profile or {}).get("id")
    if profile_id:
        return PROFILES / f"{profile_id}.json"
    return None


def update_profile_wayland_metadata(profile, system_id):
    profile = dict(profile or {})
    profile["system_xkb_id"] = system_id
    profile["wayland_ready"] = True
    path = _profile_file(profile)
    if path is not None:
        try:
            data = dict(profile)
            data.pop("_profile_file", None)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass
    return profile


def system_layout_file(system_id):
    return SYSTEM_SYMBOLS_DIR / system_id


def is_system_layout_installed(system_id):
    if not system_layout_file(system_id).exists():
        return False
    try:
        text = EVDEV_XML.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False
    return f"<name>{system_id}</name>" in text


def system_layout_matches_profile(profile, system_id):
    """Return True only when the installed symbols file matches the profile file.

    GNOME Wayland uses /usr/share/X11/xkb/symbols/<system_id>, not the
    profile copy in ~/.xkb. If the user edits/recreates a profile with the same
    ID, the system file can be stale even though Show full configuration reads
    the new profile file correctly. In that case activating the hidden GNOME
    source applies the old layout.
    """
    try:
        src = Path((profile or {}).get("xkb_file", "")).expanduser()
        dst = system_layout_file(system_id)
        if not src.exists() or not dst.exists():
            return False
        return src.read_bytes() == dst.read_bytes()
    except Exception:
        return False


def _literal_gsettings_sources(raw):
    try:
        value = ast.literal_eval((raw or "").strip())
    except Exception:
        return []
    out = []
    if not isinstance(value, (list, tuple)):
        return out
    for item in value:
        try:
            source_type, source_id = item[0], item[1]
        except Exception:
            continue
        if source_type and source_id:
            out.append((str(source_type), str(source_id)))
    return out


def gnome_sources():
    result = run(["gsettings", "get", GNOME_SCHEMA, GNOME_KEY])
    if result.returncode != 0:
        return []
    return _literal_gsettings_sources(result.stdout)


def _sources_literal(sources):
    return "[" + ", ".join(f"({source_type!r}, {source_id!r})" for source_type, source_id in sources) + "]"


def ensure_gnome_source(source_id):
    sources = gnome_sources()
    target = ("xkb", source_id)
    if target not in sources:
        sources.append(target)
        value = _sources_literal(sources)
        result = run(["gsettings", "set", GNOME_SCHEMA, GNOME_KEY, value])
        if result.returncode != 0:
            return ActivationResult.fail("No se pudo añadir la fuente a GNOME.", result.stderr or result.stdout)
    return ActivationResult.ok_result("Fuente GNOME disponible.")


def _set_gsettings_current(index):
    return run(["gsettings", "set", GNOME_SCHEMA, "current", str(index)])


def _set_gsettings_mru_first(source_id):
    sources = gnome_sources()
    target = ("xkb", source_id)
    ordered = [target] + [item for item in sources if item != target]
    return run(["gsettings", "set", GNOME_SCHEMA, "mru-sources", _sources_literal(ordered)])


def _gnome_shell_eval(expr):
    return run([
        "gdbus", "call", "--session",
        "--dest", "org.gnome.Shell",
        "--object-path", "/org/gnome/Shell",
        "--method", "org.gnome.Shell.Eval",
        expr,
    ])


def _gnome_shell_activate_source(source_type, source_id):
    # In GNOME, changing org.gnome.desktop.input-sources current with
    # gsettings may update dconf without asking GNOME Shell/Mutter to switch
    # the actual input source. Activate through the Shell manager when possible.
    #
    # Do not address inputSources only by numeric index: on several GNOME
    # versions it is an object/map, not a plain JS array, so inputSources[2]
    # can evaluate to undefined and org.gnome.Shell.Eval just returns
    # (false, ''). Find the source by type+id instead.
    import json as _json
    st = _json.dumps(str(source_type))
    sid = _json.dumps(str(source_id))
    expr = (
        "(() => { "
        "const mgr = imports.ui.status.keyboard.getInputSourceManager(); "
        "const values = Object.values(mgr.inputSources || {}); "
        f"const src = values.find(s => s && s.type === {st} && s.id === {sid}); "
        "if (!src) return 'not-found:' + values.map(s => s.type + ':' + s.id).join(','); "
        "src.activate(); "
        "return 'activated'; "
        "})()"
    )
    result = _gnome_shell_eval(expr)
    if result.returncode == 0 and "activated" in (result.stdout or ""):
        return result

    # Some GNOME builds only allow Eval while unsafe_mode is enabled. Try to
    # enable it just for this activation and restore the previous value. If
    # the shell rejects Eval entirely, this still fails harmlessly and callers
    # can fall back to gsettings/log-out.
    expr_unsafe = (
        "(() => { "
        "const old = global.context.unsafe_mode; "
        "global.context.unsafe_mode = true; "
        "try { "
        "const mgr = imports.ui.status.keyboard.getInputSourceManager(); "
        "const values = Object.values(mgr.inputSources || {}); "
        f"const src = values.find(s => s && s.type === {st} && s.id === {sid}); "
        "if (!src) return 'not-found:' + values.map(s => s.type + ':' + s.id).join(','); "
        "src.activate(); return 'activated'; "
        "} finally { global.context.unsafe_mode = old; } "
        "})()"
    )
    return _gnome_shell_eval(expr_unsafe)


def _sync_xwayland_best_effort(source_id):
    # The GNOME Wayland compositor uses gsettings/input-sources, but Xwayland
    # clients can still keep the old XKB map. The UOK indicator already syncs
    # those clients when activating a GNOME system source; do the same from the
    # CLI and from UOK profile activation so a profile behaves like its hidden
    # system-source implementation. This is best-effort and never decides
    # success/failure of the GNOME activation.
    layout = (source_id or "").split("+", 1)[0].split(":", 1)[0]
    if not layout:
        return
    env = os.environ.copy()
    for cmd in (["setxkbmap", layout], ["bash", "-lc", "sleep 0.35; setxkbmap " + shlex.quote(layout)]):
        try:
            if cmd[0] == "bash":
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env, start_new_session=True)
            else:
                run(cmd, env=env)
        except Exception:
            pass

def activate_gnome_source_id(source_id):
    sources = gnome_sources()
    try:
        index = sources.index(("xkb", source_id))
    except ValueError:
        return ActivationResult.fail("La fuente XKB no está añadida en GNOME.", source_id)

    # Keep MRU/current coherent first; GNOME uses MRU when cycling sources and
    # current lets UOK/current reflect the intended state even if Shell needs a
    # logout to load a newly registered layout.
    _set_gsettings_mru_first(source_id)
    current = _set_gsettings_current(index)
    shell = _gnome_shell_activate_source("xkb", source_id)
    _sync_xwayland_best_effort(source_id)

    shell_text = ((shell.stdout or "") + (shell.stderr or "")).strip()
    if shell.returncode == 0 and "activated" in shell_text:
        return ActivationResult.ok_result("Fuente GNOME activada.")
    if current.returncode != 0:
        details = (shell_text or current.stderr or current.stdout or "").strip()
        return ActivationResult.fail("No se pudo activar la fuente GNOME.", details)

    # gsettings succeeded but Shell did not confirm actual activation. This is
    # common right after adding a new XKB layout to evdev.xml in the same
    # Wayland session. Tell callers the intended state is set, but the user may
    # need to log out once.
    details = shell_text or "GNOME Shell no confirmó la activación; puede requerir cerrar sesión tras instalar un layout nuevo."
    return ActivationResult.ok_result("Fuente GNOME marcada como actual; puede requerir cerrar sesión.", details)


def _xml_escape(text):
    return (str(text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;"))


def _root_installer_script():
    return r"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

source = Path(sys.argv[1]).expanduser().resolve()
system_id = sys.argv[2]
visible_name = sys.argv[3]

symbols_dir = Path('/usr/share/X11/xkb/symbols')
rules = Path('/usr/share/X11/xkb/rules/evdev.xml')
rules_plain = Path('/usr/share/X11/xkb/rules/evdev')
backup = rules.with_suffix(rules.suffix + '.uok-backup')
backup_plain = rules_plain.with_suffix(rules_plain.suffix + '.uok-backup')

if not source.exists():
    print(f'XKB source file does not exist: {source}', file=sys.stderr)
    sys.exit(2)
if not re.fullmatch(r'[A-Za-z0-9_.-]+', system_id):
    print(f'Invalid system layout id: {system_id}', file=sys.stderr)
    sys.exit(2)
if not rules.exists():
    print(f'XKB registry not found: {rules}', file=sys.stderr)
    sys.exit(2)

symbols_dir.mkdir(parents=True, exist_ok=True)
shutil.copyfile(source, symbols_dir / system_id)

text = rules.read_text(encoding='utf-8', errors='ignore')
if not backup.exists():
    backup.write_text(text, encoding='utf-8')

# Keep the plain evdev rules file in sync too. GNOME lists layouts from
# evdev.xml, but Mutter/libxkbcommon ultimately compiles against evdev rules;
# adding an explicit rule is harmless for full custom layout files and helps
# on installations that are stricter about rule resolution.
if rules_plain.exists():
    plain = rules_plain.read_text(encoding='utf-8', errors='ignore')
    if not backup_plain.exists():
        backup_plain.write_text(plain, encoding='utf-8')
    line = f'{system_id} = {system_id}'
    if line not in plain:
        marker = '! layout = symbols'
        if marker in plain:
            plain = plain.replace(marker, marker + '\n  ' + line, 1)
            rules_plain.write_text(plain, encoding='utf-8')

start = f'<!-- UOK layout: {system_id} -->'
end = f'<!-- /UOK layout: {system_id} -->'
block_re = re.compile(re.escape(start) + r'.*?' + re.escape(end) + r'\s*', re.S)
text = block_re.sub('', text)

if f'<name>{system_id}</name>' not in text:
    def esc(value):
        return (str(value or '')
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&apos;'))
    entry = f'''{start}
    <layout>
      <configItem>
        <name>{esc(system_id)}</name>
        <shortDescription>uok</shortDescription>
        <description>{esc(visible_name)}</description>
        <languageList>
          <iso639Id>spa</iso639Id>
        </languageList>
      </configItem>
    </layout>
{end}
'''
    marker = '</layoutList>'
    if marker not in text:
        print('Could not find </layoutList> in evdev.xml', file=sys.stderr)
        sys.exit(2)
    text = text.replace(marker, entry + marker, 1)
    rules.write_text(text, encoding='utf-8')

# Best-effort validation. Do not use setxkbmap here: in GNOME Wayland it can
# try to open an X display even with -print and fail with
# 'Cannot open display'. xkbcli compiles from the registry without DISPLAY.
if shutil.which('xmllint') and Path('/usr/share/X11/xkb/rules/xkb.dtd').exists():
    result = subprocess.run(['xmllint', '--noout', '--dtdvalid', '/usr/share/X11/xkb/rules/xkb.dtd', str(rules)], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        print(result.stderr or result.stdout, file=sys.stderr)
        sys.exit(result.returncode)

if shutil.which('xkbcli'):
    result = subprocess.run(['xkbcli', 'compile-keymap', '--layout', system_id], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        print(result.stderr or result.stdout, file=sys.stderr)
        sys.exit(result.returncode)

print(system_id)
"""


def _privileged_runner():
    if os.geteuid() == 0:
        return []
    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        if shutil.which("pkexec"):
            return ["pkexec"]
    if shutil.which("sudo"):
        return ["sudo"]
    return []


def install_profile_as_system_layout(profile):
    if not profile:
        return ActivationResult.fail("Perfil vacío.")
    xkb_file = Path(profile.get("xkb_file", "")).expanduser()
    if not xkb_file.exists():
        return ActivationResult.fail("El perfil no tiene un archivo XKB válido.", str(xkb_file))
    system_id = profile_system_xkb_id(profile)
    visible_name = "UOK - " + str(profile.get("name") or profile.get("id") or system_id)

    # Migrate older experimental metadata that used uok_<profile_id>. The
    # working behaviour in GNOME Wayland is to add a technical source whose id
    # matches the profile id, then hide that source in UOK's UI. Keep old
    # gsettings entries from shadowing/confusing activation.
    previous_system_id = str((profile or {}).get("system_xkb_id") or "")
    if previous_system_id and previous_system_id != system_id:
        try:
            remove_gnome_source(previous_system_id)
        except Exception:
            pass

    # If the layout is already installed and matches the profile file, no sudo
    # is needed. If it exists but differs, reinstall it: otherwise GNOME applies
    # the stale system layout while UOK's viewer shows the fresh ~/.xkb profile.
    if is_system_layout_installed(system_id) and system_layout_matches_profile(profile, system_id):
        update_profile_wayland_metadata(profile, system_id)
        return ActivationResult.ok_result(system_id)

    with tempfile.NamedTemporaryFile("w", prefix="uok-install-system-xkb-", suffix=".py", delete=False, encoding="utf-8") as fh:
        fh.write(_root_installer_script())
        script = Path(fh.name)
    try:
        runner = _privileged_runner()
        cmd = runner + ["python3", str(script), str(xkb_file), system_id, visible_name]
        result = run(cmd, timeout=90)
    except subprocess.TimeoutExpired as exc:
        return ActivationResult.fail("La instalación del layout de sistema ha tardado demasiado.", str(exc))
    finally:
        try:
            script.unlink()
        except Exception:
            pass
    if result.returncode != 0:
        details = (result.stderr or result.stdout or "").strip()
        return ActivationResult.fail("No se pudo instalar el perfil como layout de sistema para GNOME Wayland.", details)
    update_profile_wayland_metadata(profile, system_id)
    return ActivationResult.ok_result(system_id)


def ensure_profile_available_in_gnome(profile):
    install = install_profile_as_system_layout(profile)
    if not install.ok:
        return install
    system_id = install.message
    added = ensure_gnome_source(system_id)
    if not added.ok:
        return added
    return ActivationResult.ok_result(system_id)


def activate_profile_gnome_wayland(profile):
    available = ensure_profile_available_in_gnome(profile)
    if not available.ok:
        return available
    system_id = available.message
    activated = activate_gnome_source_id(system_id)
    if not activated.ok:
        return activated
    return ActivationResult.ok_result(system_id)



def _root_remover_script():
    return r"""
import re
import sys
from pathlib import Path

system_ids = sys.argv[1:]
rules = Path('/usr/share/X11/xkb/rules/evdev.xml')
rules_plain = Path('/usr/share/X11/xkb/rules/evdev')

if not system_ids:
    sys.exit(0)

for system_id in system_ids:
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', system_id):
        print(f'Invalid system layout id: {system_id}', file=sys.stderr)
        sys.exit(2)

for system_id in system_ids:
    symbols = Path('/usr/share/X11/xkb/symbols') / system_id
    try:
        if symbols.exists():
            symbols.unlink()
    except Exception as exc:
        print(f'Could not remove {symbols}: {exc}', file=sys.stderr)
        sys.exit(2)

if rules.exists():
    text = rules.read_text(encoding='utf-8', errors='ignore')
    text2 = text
    for system_id in system_ids:
        start = f'<!-- UOK layout: {system_id} -->'
        end = f'<!-- /UOK layout: {system_id} -->'
        text2 = re.sub(re.escape(start) + r'.*?' + re.escape(end) + r'\s*', '', text2, flags=re.S)
    if text2 != text:
        rules.write_text(text2, encoding='utf-8')

if rules_plain.exists():
    plain = rules_plain.read_text(encoding='utf-8', errors='ignore')
    plain2 = plain
    for system_id in system_ids:
        line_re = re.compile(r'^\s*' + re.escape(system_id) + r'\s*=\s*' + re.escape(system_id) + r'\s*$', re.M)
        plain2 = line_re.sub('', plain2)
    if plain2 != plain:
        rules_plain.write_text(plain2, encoding='utf-8')

print(','.join(system_ids))
"""


def remove_gnome_source(source_id):
    sources = gnome_sources()
    target = ("xkb", source_id)
    if target not in sources:
        return ActivationResult.ok_result("Fuente GNOME no estaba añadida.")
    current_index = 0
    try:
        cur = run(["gsettings", "get", GNOME_SCHEMA, "current"])
        m = re.search(r"(\d+)", cur.stdout or "")
        if m:
            current_index = int(m.group(1))
    except Exception:
        current_index = 0
    removed_index = sources.index(target)
    new_sources = [item for item in sources if item != target]
    result = run(["gsettings", "set", GNOME_SCHEMA, GNOME_KEY, _sources_literal(new_sources)])
    if result.returncode != 0:
        return ActivationResult.fail("No se pudo quitar la fuente de GNOME.", result.stderr or result.stdout)
    if new_sources:
        new_current = min(current_index, len(new_sources) - 1)
        if removed_index <= current_index:
            new_current = max(0, current_index - 1)
        run(["gsettings", "set", GNOME_SCHEMA, "current", str(new_current)])
    return ActivationResult.ok_result("Fuente GNOME eliminada.")


def remove_system_layout(system_id):
    return remove_system_layouts([system_id])


def remove_system_layouts(system_ids):
    ids = []
    seen = set()
    for value in system_ids or []:
        value = str(value or "").strip()
        if value and value not in seen:
            seen.add(value)
            ids.append(value)
    if not ids:
        return ActivationResult.ok_result("Sin layout de sistema.")

    # Avoid asking for the administrator password once per legacy id.  Remove
    # all technical UOK layouts in a single privileged helper invocation.
    with tempfile.NamedTemporaryFile("w", prefix="uok-remove-system-xkb-", suffix=".py", delete=False, encoding="utf-8") as fh:
        fh.write(_root_remover_script())
        script = Path(fh.name)
    try:
        runner = _privileged_runner()
        result = run(runner + ["python3", str(script)] + ids, timeout=90)
    except subprocess.TimeoutExpired as exc:
        return ActivationResult.fail("La eliminación del layout de sistema ha tardado demasiado.", str(exc))
    finally:
        try:
            script.unlink()
        except Exception:
            pass
    if result.returncode != 0:
        return ActivationResult.fail("No se pudo eliminar el layout de sistema UOK.", result.stderr or result.stdout)
    return ActivationResult.ok_result(",".join(ids))


def remove_profile_system_layout(profile):
    ids = legacy_profile_system_xkb_ids(profile)
    if not ids:
        return ActivationResult.ok_result("Sin layout de sistema.")
    for system_id in ids:
        try:
            remove_gnome_source(str(system_id))
        except Exception:
            pass
    return remove_system_layouts(ids)
