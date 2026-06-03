import re
import shlex
import subprocess
from pathlib import Path
from uok_backends.session import desktop_text

def _is_lxqt():
    return "lxqt" in desktop_text()

def _panel_conf_path():
    return Path.home() / ".config/lxqt/panel.conf"

def _rewrite_panel_conf(backup_suffix, rewrite):
    conf = _panel_conf_path()
    if not conf.exists():
        return
    try:
        text = conf.read_text(encoding="utf-8")
    except Exception:
        return
    new_text = rewrite(text)
    if new_text == text:
        return
    try:
        backup = conf.with_suffix(backup_suffix)
        if not backup.exists():
            backup.write_text(text, encoding="utf-8")
        conf.write_text(new_text, encoding="utf-8")
    except Exception:
        pass

def _hide_native_input_indicators(app):
    if not _is_lxqt():
        return
    # IBus: ocultar icono/nombre nativo.
    for cmd in [["gsettings", "set", "org.freedesktop.ibus.panel", "show-icon-on-systray", "false"],
        ["gsettings", "set", "org.freedesktop.ibus.panel", "show-im-name", "false"]]:
        try:
            app.run_menu_cmd(cmd)
        except Exception:
            pass

    # LXQt keyboard indicator plugin: kbindicator.
    # No se toca statusnotifier porque ahí puede vivir UOK.
    def rewrite(text):
        text = re.sub(r"(^plugins=.*)$",lambda m: re.sub(r",?kbindicator,?|kbindicator,?",lambda x: "," if "," in x.group(0) else "",m.group(1),
            ).replace(",,", ",").rstrip(","),text,flags=re.M)
        text = re.sub(r"\n?\[kbindicator\]\n.*?(?=\n\[[^\]]+\]|\Z)","\n",text,flags=re.S,)
        return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"
    _rewrite_panel_conf(".conf.uok-backup", rewrite)

def _remove_legacy_tray_keep_statusnotifier():
    if not _is_lxqt():
        return

    def rewrite(text):
        if "[tray]" not in text:
            return text
        new_text = re.sub(r"(?ms)^\[tray\]\n.*?(?=^\[[^\]]+\]\n|\Z)","",text)
        return re.sub(r"\n{3,}", "\n\n", new_text).strip() + "\n"
    _rewrite_panel_conf(".conf.uok-before-remove-tray", rewrite)

def _open_lxqt_keyboard_settings(app, base_open_keyboard_settings, _item=None):
    if not _is_lxqt():
        if base_open_keyboard_settings is not None:
            return base_open_keyboard_settings(_item)
        app.notify("UrOwnKeyboard","No se pudo abrir la configuración de teclado del sistema.")
        return
    for cmd in [["lxqt-config-input"],["lxqt-config"]]:
        try:
            check = app.run_menu_cmd(["bash","-lc","command -v " + shlex.quote(cmd[0])])
            if check.returncode != 0:
                continue
            shell_cmd = (" ".join(shlex.quote(x) for x in cmd) + "; " + "pkill -f teclado-indicador.py 2>/dev/null || true; "
                + "$HOME/.local/bin/teclado-indicador.py >/dev/null 2>&1 &")
            subprocess.Popen(["bash", "-lc", shell_cmd],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                start_new_session=True,env=app.menu_env())
            return
        except Exception:
            continue
    app.notify("UrOwnKeyboard","No se pudo abrir la configuración de teclado de LXQt.")

def install(app):
    base_open_keyboard_settings = getattr(app, "abrir_ajustes_teclado", None)

    def abrir_ajustes_teclado(_item=None):
        return _open_lxqt_keyboard_settings(app,base_open_keyboard_settings,_item)

    def uok_lxqt_append_system_sources_to_menu(_menu):
        # Las fuentes ya se leen desde get_sources()/uok_xkb_sources.py.
        # Aquí sólo ocultamos indicadores nativos de LXQt/IBus.
        _hide_native_input_indicators(app)

    app.uok_is_lxqt_desktop = _is_lxqt
    app.uok_lxqt_panel_conf_path = _panel_conf_path
    app.uok_lxqt_hide_native_input_indicators = lambda: _hide_native_input_indicators(app)
    app.uok_lxqt_remove_legacy_tray_keep_statusnotifier = _remove_legacy_tray_keep_statusnotifier
    app.uok_lxqt_append_system_sources_to_menu = uok_lxqt_append_system_sources_to_menu
    app.abrir_ajustes_teclado = abrir_ajustes_teclado
