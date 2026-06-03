_APP = None

def _restart_indicator():
    if _APP is not None and hasattr(_APP, "reiniciar_indicador"):
        return _APP.reiniciar_indicador()

def profile_name(profile):
    return profile.get("name") or profile.get("id") or "perfil UOK"

def profile_is_custom_xkb(profile):
    return profile.get("type") != "gnome-source"

def unsupported_gnome_wayland_message(profile):
    name = profile_name(profile)
    return ("Este perfil UOK usa una distribución XKB propia.\n\n""En GNOME Wayland UOK todavía no puede aplicar perfiles XKB personalizados "
        "con setxkbmap/xkbcomp, porque no cambian el layout real del compositor.\n\n"f"Perfil no aplicado: {name}\n\n"
        "Usa GNOME X11 para perfiles propios, o instala esta distribución como ""fuente XKB del sistema/GNOME.")

def load_profiles():
    profiles = []
    for file in sorted(PROFILES.glob("*.json")):
        try:
            profile = json.loads(file.read_text())
            profile["_profile_file"] = str(file)
            profiles.append(profile)
        except Exception:
            pass
    return profiles

def crear_layout_visual(_):
    editor = HOME / ".local" / "bin" / "uok-layout-editor.py"
    if not editor.exists():
        editor = Path(__file__).resolve().parent / "uok-layout-editor.py"
    run(f'{shlex.quote(str(editor))} || notify-send "Keyboard" "Could not open layout editor"')

def importar_configuracion(_):
    name = sh('zenity --entry ''--title="Import keyboard" ''--text="Configuration name:" ''|| true')
    if not name:
        return
    base_id = safe_id(name)
    layout_id = unique_layout_id(base_id)
    xkb_file = sh('zenity --file-selection ''--title="Select XKB / symbols file" ''|| true')
    if not xkb_file:
        return
    keyd_file = sh('zenity --file-selection ''--title="Selecciona keyd.conf opcional" ''--filename="$HOME/" ''|| true')
    dest_xkb = USER_XKB / layout_id
    shutil.copyfile(xkb_file, dest_xkb)
    profile = {"id":layout_id,"name":name,"xkb_file":str(dest_xkb)}
    if keyd_file:
        dest_keyd = KEYD_DIR / f"{layout_id}.conf"
        shutil.copyfile(keyd_file, dest_keyd)
        profile["keyd_conf"] = str(dest_keyd)
    (PROFILES / f"{layout_id}.json").write_text(json.dumps(profile, indent=2, ensure_ascii=False))
    if layout_id != base_id:
        notify("Keyboard", f"Configuration {name} imported as {layout_id}")
    else:
        notify("Keyboard", f"Configuration {name} imported")
    _restart_indicator()

def borrar_si_seguro(path_str):
    if not path_str:
        return
    path = Path(path_str).expanduser().resolve()
    zonas_permitidas = [USER_XKB.resolve(),KEYD_DIR.resolve(),XKB_DIR.resolve()]
    permitido = any(str(path).startswith(str(zona) + "/") or path == zona
        for zona in zonas_permitidas)
    if permitido and path.exists() and path.is_file():
        path.unlink()

def uok_profile_is_current(profile):
    if not profile or not CURRENT_PROFILE.exists():
        return False
    try:
        current = json.loads(CURRENT_PROFILE.read_text(encoding="utf-8"))
    except Exception:
        return False
    return (current.get("type") == "imported-profile"
        and current.get("id")
        and current.get("id") == profile.get("id"))

def uok_safe_before_delete_profile(profile):
    if not uok_profile_is_current(profile):
        return True
    # Primero apagar keyd si el perfil activo tenía keyd asociado.
    if profile.get("keyd_conf"):
        if not aplicar_keyd_off_sync():
            return False
    # Luego cambiar a un XKB seguro.
    run_menu_cmd(["setxkbmap", "es"])
    # Y eliminar el marcador de perfil activo para que el arranque no intente reactivarlo.
    try:
        if CURRENT_PROFILE.exists():
            CURRENT_PROFILE.unlink()
    except Exception:
        pass
    return True

def eliminar_configuracion(_):
    profiles = load_profiles()
    if not profiles:
        notify("Keyboard", "There are no imported configurations to delete")
        return
    opciones = []
    for profile in profiles:
        opciones.append(profile["id"])
        opciones.append(profile["name"])
    quoted_options = " ".join(shlex.quote(x) for x in opciones)
    cmd = ('zenity --list ''--title="Delete configuration" ''--text="Select the configuration you want to delete:" ''--column="ID" ''--column="Name" '
        '--hide-column=1 ''--print-column=1 'f'{quoted_options} ''|| true')
    selected_id = sh(cmd)
    if not selected_id:
        return
    profile = next((p for p in profiles if p["id"] == selected_id), None)
    if not profile:
        return
    confirm = sh('zenity --question ''--title="Delete configuration" 'f'--text={shlex.quote("Delete configuration “" + profile["name"] + "”?")} '
        '&& echo yes || true')
    if confirm != "yes":
        return
    if not uok_safe_before_delete_profile(profile):
        return
    borrar_si_seguro(profile.get("xkb_file"))
    borrar_si_seguro(profile.get("keyd_conf"))
    profile_file = Path(profile["_profile_file"]).resolve()
    if str(profile_file).startswith(str(PROFILES.resolve()) + "/") and profile_file.exists():
        profile_file.unlink()
    notify("Keyboard", f"Configuration {profile['name']} deleted")
    _restart_indicator()

def get_current_profile():
    if CURRENT_PROFILE.exists():
        try:
            return json.loads(CURRENT_PROFILE.read_text())
        except Exception:
            return None
    return None

def get_xkb_spec_actual():
    profile = get_current_profile()
    if profile and profile.get("type") == "imported-profile" and profile.get("id"):
        return profile["id"]
    query = sh("setxkbmap -query")
    layout = ""
    variant = ""
    for line in query.splitlines():
        if line.startswith("layout:"):
            layout = line.split(":", 1)[1].strip().split(",")[0]
        elif line.startswith("variant:"):
            variant = line.split(":", 1)[1].strip().split(",")[0]
    if not layout:
        return ""
    if variant:
        return f"{layout}({variant})"
    return layout

def mostrar_distribucion_actual(_):
    try:
        spec = get_xkb_spec_actual()
        if not spec:
            notify("Keyboard", "Could not detect the current layout")
            return
        run(f'gkbd-keyboard-display -l {shlex.quote(spec)} 'f'|| notify-send "Keyboard" "No se pudo abrir el visor para {spec}"')
    except Exception:
        notify("Keyboard", "Could not open the current layout viewer")

def mostrar_texto(title, content):
    try:
        proc = subprocess.Popen(["zenity","--text-info",f"--title={title}","--width=900","--height=700","--font=monospace"],stdin=subprocess.PIPE,
            text=True)
        if proc.stdin:
            proc.stdin.write(content)
            proc.stdin.close()
    except Exception:
        notify("Keyboard", "Could not open the information window")

def mostrar_configuracion_completa(_):
    try:
        spec = get_xkb_spec_actual()
        if spec:
            run(f'gkbd-keyboard-display -l {shlex.quote(spec)} 'f'|| notify-send "Keyboard" "No se pudo abrir el visor para {spec}"')
        info = []
        info.append("CURRENT CONFIGURATION")
        info.append("=" * 80)
        info.append("")
        if spec:
            info.append(f"Active XKB layout: {spec}")
        else:
            info.append("Active XKB layout: no detectado")
        info.append("")
        info.append("setxkbmap -query")
        info.append("-" * 80)
        try:
            info.append(sh("setxkbmap -query"))
        except Exception:
            info.append("No se pudo leer setxkbmap -query")
        info.append("")
        info.append("UR OWN KEYBOARD PROFILE")
        info.append("=" * 80)
        info.append("")
        profile = get_current_profile()
        if profile:
            info.append(f"Name: {profile.get('name', 'unnamed')}")
            info.append(f"Type: {profile.get('type', 'unknown')}")
            if profile.get("id"):
                info.append(f"ID: {profile.get('id')}")
            if profile.get("source_id"):
                info.append(f"GNOME source: {profile.get('source_id')}")
            if profile.get("xkb_file"):
                info.append(f"XKB file: {profile.get('xkb_file')}")
                info.append("")
                info.append("XKB FILE CONTENT")
                info.append("=" * 80)
                info.append("")
                try:
                    info.append(Path(profile.get("xkb_file")).read_text())
                except Exception:
                    info.append("Could not read the associated XKB file.")
            keyd_conf = profile.get("keyd_conf")
            info.append("")
            if keyd_conf:
                info.append("ACTIVE KEYD")
                info.append("=" * 80)
                info.append("")
                info.append(f"keyd file: {keyd_conf}")
                info.append("")
                info.append("-" * 80)
                try:
                    info.append(Path(keyd_conf).read_text())
                except Exception:
                    info.append("Could not read the associated keyd file.")
            else:
                info.append("ACTIVE KEYD")
                info.append("=" * 80)
                info.append("")
                info.append("This configuration has no associated keyd.conf.")
                info.append("If this is a regular GNOME input source, keyd is used in normal mode.")
        else:
            info.append("No active profile registered by UrOwnKeyboard.")
            info.append("")
            info.append("This can happen if the current keyboard was changed outside the indicator.")
        mostrar_texto("Full configuration", "\n".join(info))
    except Exception:
        notify("Keyboard", "Could not show the full configuration")

def abrir_editor_visual(_item=None):
    import sys
    candidates = [Path(__file__).resolve().parent / "uok-layout-editor.py",HOME / ".local" / "bin" / "uok-layout-editor.py",
        Path.cwd() / "uok-layout-editor.py"]
    editor = next((path for path in candidates if path.exists()), None)
    if editor is None:
        notify("UrOwnKeyboard", "No se encontró el editor visual.")
        return
    subprocess.Popen([sys.executable, str(editor)],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)

_PROFILE_FUNCTIONS = ['load_profiles', 'crear_layout_visual', 'importar_configuracion', 'borrar_si_seguro', 'uok_profile_is_current',
    'uok_safe_before_delete_profile', 'eliminar_configuracion', 'get_current_profile', 'get_xkb_spec_actual', 'mostrar_distribucion_actual',
    'mostrar_texto', 'mostrar_configuracion_completa', 'abrir_editor_visual']

def _bind_app_globals(app):
    module_globals = globals()
    for name, value in app.__dict__.items():
        if not name.startswith("__"):
            module_globals[name] = value
    # Mantener el comportamiento anterior del exec(..., app.__dict__):
    # las funciones veían el __file__ de teclado-indicador.py.
    module_globals["__file__"] = app.__dict__.get("__file__", __file__)

def install(app):
    global _APP
    _APP = app
    _bind_app_globals(app)
    for name in _PROFILE_FUNCTIONS:
        setattr(app, name, globals()[name])