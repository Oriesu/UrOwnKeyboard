import os
for _var in ("LD_LIBRARY_PATH","LD_PRELOAD","GTK_PATH","GIO_EXTRA_MODULES","GI_TYPELIB_PATH"):
    if "/snap/" in os.environ.get(_var, ""):
        os.environ.pop(_var, None)

def _sanitize_snap_gtk_environment():
    for name in ("LD_LIBRARY_PATH","LD_PRELOAD","GTK_PATH","GIO_EXTRA_MODULES","GI_TYPELIB_PATH"):
        value = os.environ.get(name, "")
        if "/snap/" in value:
            os.environ.pop(name, None)

_sanitize_snap_gtk_environment()
import re
import ctypes
import json
import subprocess
import tempfile
import sys
from pathlib import Path
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk
from uok_xkb_symbols import keysym_to_text, text_to_keysym, validate_keysym_text, SPECIAL_KEYSYMS
from uok_xkb_sources import load_xkb_sources, source_id_to_include, layout_label
from uok_backends.session import desktop_text

HOME = Path.home()
CONFIG = HOME / ".config" / "teclado-indicador"
CURRENT_PROFILE = CONFIG / "current-profile.json"
USER_XKB = HOME / ".xkb" / "symbols"
KEYD_DIR = CONFIG / "keyd"

def uok_editor_mate_layouts_from_gsettings():
    desktop = desktop_text()
    if "mate" not in desktop:
        return []
    try:
        result = subprocess.run(["gsettings","get","org.mate.peripherals-keyboard-xkb.kbd","layouts"],text=True,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    except Exception:
        return []
    if result.returncode != 0:
        return []
    raw_layouts = re.findall(r"'([^']+)'", result.stdout.strip())
    rows = []

    for raw in raw_layouts:
        raw = (raw or "").strip()
        if not raw:
            continue
        if "+" in raw:
            layout, variant = raw.split("+", 1)
        elif "(" in raw and raw.endswith(")"):
            layout, variant = raw[:-1].split("(", 1)
        else:
            layout, variant = raw, ""
        layout = layout.strip()
        variant = variant.strip()
        if not layout:
            continue
        include = layout if not variant else f"{layout}({variant})"
        source_id = layout if not variant else f"{layout}+{variant}"
        label = layout_label(layout, variant)
        rows.append({"section":"Añadidas del sistema","kind":"system-other","id":f"mate-gsettings:{source_id}","source_id":source_id,"include":include,
            "label":label,"description":"Distribución añadida en los ajustes de MATE","xkb_file":""})
    return rows

def uok_editor_merge_mate_gsettings_layouts(source_items):
    rows = uok_editor_mate_layouts_from_gsettings()
    if not rows:
        return source_items
    seen = set()
    merged = []
    for row in rows:
        key = row.get("source_id") or row.get("include") or row.get("id")
        if key in seen:
            continue
        seen.add(key)
        merged.append(row)
    for item in source_items:
        key = item.get("source_id") or item.get("include") or item.get("id")
        if key in seen and item.get("section") != "UOK":
            continue
        merged.append(item)
    return merged

LEVEL_NAMES = ["Normal","Shift","AltGr","AltGr + Shift"]

LAYOUT_ROWS = [[("ESC","Esc",1.0),("TLDE","º",1.0),("AE01","1",1.0),("AE02","2",1.0),("AE03","3",1.0),("AE04","4",1.0),("AE05","5",1.0),("AE06","6",1.0),
        ("AE07","7",1.0),("AE08","8",1.0),("AE09","9",1.0),("AE10","0",1.0),("AE11","'",1.0),("AE12","¡",1.0),("BKSP","⌫",1.6)],
    [("TAB","Tab",1.4),("AD01","Q",1.0),("AD02","W",1.0),("AD03","E",1.0),("AD04","R",1.0),("AD05","T",1.0),("AD06","Y",1.0),("AD07","U",1.0),
        ("AD08","I",1.0),("AD09","O",1.0),("AD10","P",1.0),("AD11","`",1.0),("AD12","+",1.0),("RTRN","Enter",1.5)],
    [("CAPS","Caps",1.7),("AC01","A",1.0),("AC02","S",1.0),("AC03","D",1.0),("AC04","F",1.0),("AC05","G",1.0),("AC06","H",1.0),("AC07","J",1.0),
        ("AC08","K",1.0),("AC09","L",1.0),("AC10","Ñ",1.0),("AC11","´",1.0),("BKSL", "Ç",1.0)],
    [("LFSH","Shift",1.25),("LSGT","<",1.0),("AB01","Z",1.0),("AB02","X",1.0),("AB03","C",1.0),("AB04","V",1.0),("AB05","B",1.0),("AB06","N",1.0),
        ("AB07","M",1.0),("AB08",",",1.0),("AB09",".",1.0),("AB10","-",1.0),("RTSH", "Shift", 1.8)],
    [("LCTL","Ctrl",1.25),("LWIN","Super",1.25),("LALT","Alt",1.25),("SPCE","Space",5.5),("RALT","AltGr",1.25),("RWIN","Super",1.25),("MENU","Menu",1.25),
        ("RCTL", "Ctrl", 1.25),],]
KEYD_SOURCE_MODIFIERS = [("Ctrl","control","C"),("Alt","alt","A"),("Shift","shift","S"),("Super","meta","M"),("AltGr","altgr","G")]

KEYD_MODIFIER_KEYCODES = {"LCTL","RCTL","LALT","RALT","LFSH","RTSH","LWIN","RWIN"}

KEYD_KEY_NAMES = {"ESC":"esc","TLDE":"grave","AE01":"1","AE02":"2","AE03":"3","AE04":"4","AE05":"5","AE06":"6","AE07":"7","AE08":"8","AE09":"9","AE10":"0",
    "AE11":"minus","AE12":"equal","BKSP":"backspace","TAB":"tab","AD01":"q","AD02":"w","AD03":"e","AD04":"r","AD05":"t","AD06":"y","AD07":"u","AD08":"i",
    "AD09":"o","AD10":"p","AD11":"leftbrace","AD12":"rightbrace","RTRN":"enter","CAPS":"capslock","AC01":"a","AC02":"s","AC03":"d","AC04":"f","AC05":"g",
    "AC06":"h","AC07":"j","AC08":"k","AC09":"l","AC10":"semicolon","AC11":"apostrophe","BKSL":"backslash","LSGT":"102nd","AB01":"z","AB02":"x","AB03":"c",
    "AB04":"v","AB05":"b","AB06":"n","AB07":"m","AB08":"comma","AB09":"dot","AB10":"slash","SPCE":"space","MENU":"compose","FK01":"f1","FK02":"f2","FK03":"f3",
    "FK04":"f4","FK05":"f5","FK06":"f6","FK07":"f7","FK08":"f8","FK09":"f9","FK10":"f10","FK11":"f11","FK12":"f12","FK13":"f13","FK14":"f14","FK15":"f15",
    "FK16":"f16","FK17":"f17","FK18":"f18","FK19":"f19","FK20":"f20","FK21":"f21","FK22":"f22","FK23":"f23","FK24":"f24"}

def uok_editor_is_mate_desktop():
    return "mate" in desktop_text()

def uok_editor_run_cmd(args):
    import subprocess
    return subprocess.run(args, text=True, capture_output=True)

def uok_editor_mate_system_sources():
    if not uok_editor_is_mate_desktop():
        return []
    out = []
    seen = set()
    # 1) XKB activo/configurado en la sesión.
    result = uok_editor_run_cmd(["setxkbmap", "-query"])
    if result.returncode == 0:
        layout_line = ""
        variant_line = ""
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.startswith("layout:"):
                layout_line = line.split(":", 1)[1].strip()
            elif line.startswith("variant:"):
                variant_line = line.split(":", 1)[1].strip()
        layouts = [x.strip() for x in layout_line.split(",") if x.strip()]
        variants = [x.strip() for x in variant_line.split(",")] if variant_line else []
        while len(variants) < len(layouts):
            variants.append("")
        for layout, variant in zip(layouts, variants):
            sid = layout if not variant else f"{layout}+{variant}"
            if sid in seen:
                continue
            seen.add(sid)
            out.append({"kind":"system-xkb","id":sid,"label":layout_label(layout, variant),"layout":layout,"variant":variant})
    # 2) IBus configurado, no todos los motores instalados.
    result = uok_editor_run_cmd(["gsettings","get","org.freedesktop.ibus.general","preload-engines"])
    if result.returncode == 0:
        engine_ids = re.findall(r"'([^']+)'", result.stdout.strip())
        for engine_id in engine_ids:
            if not engine_id.startswith("xkb:"):
                continue
            parts = engine_id.split(":")
            layout = parts[1] if len(parts) > 1 else ""
            variant = parts[2] if len(parts) > 2 else ""
            if not layout:
                continue
            sid = layout if not variant else f"{layout}+{variant}"
            if sid in seen:
                continue
            seen.add(sid)
            out.append({"kind":"system-ibus","id":engine_id,"label":layout_label(layout,variant),"layout":layout,"variant":variant})
    return out

def uok_editor_system_source_rows():
    return [{"id": source["id"],"label":source["label"],"display":f'{source["label"]} — sistema',"kind":source["kind"]}
        for source in uok_editor_mate_system_sources()]

def keyd_name_for_code(code):
    if code in KEYD_KEY_NAMES:
        return KEYD_KEY_NAMES[code]
    m = re.fullmatch(r"FK(\d{2})", code or "")
    if m:
        return f"f{int(m.group(1))}"
    return (code or "").lower()

def keyd_escape_comment_text(text):
    return (text or "").replace("\n", " ").strip()

KEY_BLOCK_RE = re.compile(r"key\s+<([^>]+)>\s*\{(.*?)\};", re.S)
KEY_SYMBOLS_RE = re.compile(r"\[([^\]]*)\]", re.S)
KEYCODE_RE = re.compile(r"<([^>]+)>\s*=\s*(\d+)\s*;")

def run(cmd):
    try:
        return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError as e:
        return subprocess.CompletedProcess(cmd, 127, "", str(e))

def load_current_profile():
    if not CURRENT_PROFILE.exists():
        return None
    try:
        return json.loads(CURRENT_PROFILE.read_text(encoding="utf-8"))
    except Exception:
        return None

def parse_include_name(include_name):
    include_name = (include_name or "").strip()
    m = re.fullmatch(r"([^()]+)\(([^()]+)\)", include_name)
    if m:
        return m.group(1), m.group(2)
    return include_name, ""

def x11_active_group_index():
    display_name = os.environ.get("DISPLAY")
    if not display_name:
        return None
    try:
        x11 = ctypes.CDLL("libX11.so.6")
    except Exception:
        return None

    class XkbStateRec(ctypes.Structure):
        _fields_ = [("group",ctypes.c_ubyte),("locked_group",ctypes.c_ubyte),("base_group",ctypes.c_ushort),("latched_group",ctypes.c_ushort),
            ("mods",ctypes.c_ubyte),("base_mods",ctypes.c_ubyte),("latched_mods",ctypes.c_ubyte),("locked_mods",ctypes.c_ubyte),("compat_state",ctypes.c_ubyte),
            ("grab_mods",ctypes.c_ubyte),("compat_grab_mods",ctypes.c_ubyte),("lookup_mods",ctypes.c_ubyte),("compat_lookup_mods",ctypes.c_ubyte),
            ("ptr_buttons",ctypes.c_ushort)]
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    x11.XkbGetState.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.POINTER(XkbStateRec)]
    x11.XkbGetState.restype = ctypes.c_int
    display = x11.XOpenDisplay(display_name.encode())
    if not display:
        return None
    try:
        state = XkbStateRec()
        XkbUseCoreKbd = 0x0100
        ok = x11.XkbGetState(display, XkbUseCoreKbd, ctypes.byref(state))
        if ok == 0:
            return int(state.group)
    finally:
        x11.XCloseDisplay(display)
    return None

def setxkbmap_query_groups():
    result = run(["setxkbmap", "-query"])
    layouts = []
    variants = []
    if result.returncode == 0:
        for line in result.stdout.splitlines():
            clean = line.strip()
            if clean.startswith("layout:"):
                raw = clean.split(":", 1)[1].strip()
                layouts = [x.strip() for x in raw.split(",")]
            elif clean.startswith("variant:"):
                raw = clean.split(":", 1)[1].strip()
                variants = [x.strip() for x in raw.split(",")]
    while len(variants) < len(layouts):
        variants.append("")
    return list(zip(layouts, variants))

def active_xkb_group_include():
    # Detecta el grupo/layout activo real usando X11/XKB.
    # Esto cubre el caso donde GNOME cambia el teclado, pero
    # org.gnome.desktop.input-sources current sigue en 0.
    group = x11_active_group_index()
    groups = setxkbmap_query_groups()
    if group is not None and groups and 0 <= group < len(groups):
        layout, variant = groups[group]
        if layout:
            return f"{layout}({variant})" if variant else layout
    # Fallback opcional si el usuario tiene alguna herramienta externa.
    for cmd in (["xkb-switch"],["xkblayout-state","print","%s"]):
        result = run(cmd)
        if result.returncode == 0:
            value = result.stdout.strip()
            if value:
                return source_id_to_include(value)
    return ""

def gnome_current_include():
    result = run(["gsettings", "get", "org.gnome.desktop.input-sources", "sources"])
    if result.returncode != 0:
        return ""
    sources_text = result.stdout.strip()
    result = run(["gsettings", "get", "org.gnome.desktop.input-sources", "current"])
    current_index = 0
    if result.returncode == 0:
        try:
            current_index = int(result.stdout.strip().replace("uint32", "").strip())
        except Exception:
            current_index = 0
    sources = re.findall(r"\('xkb',\s*'([^']+)'\)", sources_text)
    if not sources:
        return ""
    if current_index < 0 or current_index >= len(sources):
        current_index = 0
    return source_id_to_include(sources[current_index])

def setxkbmap_query_include():
    groups = setxkbmap_query_groups()
    if not groups:
        return ""
    layout, variant = groups[0]
    if not layout:
        return ""
    return f"{layout}({variant})" if variant else layout

def xkb_dump_from_include(include_name):
    layout, variant = parse_include_name(include_name)
    if not layout:
        return ""
    cmd = ["setxkbmap",f"-I{HOME / '.xkb'}","-layout",layout]
    if variant:
        cmd.extend(["-variant", variant])
    cmd.append("-print")
    printed = run(cmd)
    if printed.returncode != 0:
        return ""
    compiled = subprocess.run(["xkbcomp", f"-I{HOME / '.xkb'}", "-xkb", "-", "-"],input=printed.stdout,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if compiled.returncode == 0:
        return compiled.stdout
    return ""

def current_display_symbols_text():
    display = os.environ.get("DISPLAY")
    if not display:
        return ""
    for cmd in (["xkbcomp", "-xkb", display, "-"], ["xkbcomp", display, "-"]):
        result = run(cmd)
        if result.returncode == 0:
            return result.stdout
    return ""

def active_base_include():
    profile = load_current_profile()
    if profile:
        profile_type = profile.get("type")
        if profile_type == "imported-profile" and profile.get("id"):
            return profile["id"]
        if profile_type == "gnome-source":
            include = source_id_to_include(profile.get("source_id", ""))
            if include:
                return include
    xkb_group_include = active_xkb_group_include()
    if xkb_group_include:
        return xkb_group_include
    gnome_include = gnome_current_include()
    if gnome_include:
        return gnome_include
    query_include = setxkbmap_query_include()
    if query_include:
        return query_include
    return "es"

def xkb_include_from_current():
    return active_base_include()

def current_symbols_text():
    profile = load_current_profile()
    # 1. Perfil importado UOK activo: compilar el layout completo.
    # El archivo del perfil puede ser sólo un wrapper con include "...";
    # para editar necesitamos el mapa resuelto completo.
    if profile and profile.get("type") == "imported-profile":
        profile_id = profile.get("id", "")
        # En GNOME Wayland el perfil visible UOK se implementa como una fuente
        # técnica del sistema. Para mostrar la imagen/teclas reales, probar ese
        # ID primero; si no existe, caer al perfil y finalmente al archivo XKB.
        for include in (profile.get("system_xkb_id"), profile_id):
            if include:
                text = xkb_dump_from_include(include)
                if text:
                    return text
        xkb_file = profile.get("xkb_file")
        if xkb_file:
            path = Path(xkb_file).expanduser()
            if path.exists():
                return path.read_text(encoding="utf-8")
    # 2. Fuente GNOME seleccionada desde el menú de UrOwnKeyboard.
    # Esto es más fiable que XkbGetState en GNOME, porque el grupo XKB puede seguir
    # apareciendo como 0 aunque el teclado real haya cambiado.
    if profile and profile.get("type") == "gnome-source":
        include = source_id_to_include(profile.get("source_id", ""))
        text = xkb_dump_from_include(include)
        if text:
            return text
    # 3. Grupo XKB activo real, si se puede detectar.
    xkb_group_include = active_xkb_group_include()
    text = xkb_dump_from_include(xkb_group_include)
    if text:
        return text
    # 4. Fuente GNOME activa por gsettings.
    gnome_include = gnome_current_include()
    text = xkb_dump_from_include(gnome_include)
    if text:
        return text
    # 5. Fallback setxkbmap.
    query_include = setxkbmap_query_include()
    text = xkb_dump_from_include(query_include)
    if text:
        return text
    # 6. Último recurso: mapa cargado en DISPLAY.
    return current_display_symbols_text()

def parse_key_symbols(text):
    out = {}
    for code, body in KEY_BLOCK_RE.findall(text or ""):
        matches = KEY_SYMBOLS_RE.findall(body)
        if not matches:
            continue
        # En dumps reales de xkbcomp puede aparecer:
        # key <AC10> { [ ntilde, Ntilde ] };
        # o:
        # key <AC10> { symbols[Group1]= [ odiaeresis, Odiaeresis ] };
        symbols_body = matches[-1]
        parts = []
        for p in symbols_body.replace("\n", " ").split(","):
            p = p.strip()
            if not p:
                continue
            if "=" in p:
                p = p.split("=", 1)[-1].strip()
            if p:
                parts.append(p)
        if parts:
            out[code] = parts[:4]
    return out

def parse_keycodes(text):
    return {int(num): code for code, num in KEYCODE_RE.findall(text or "")}

def detected_function_key_row(base_symbols=None, keycode_to_name=None):
    found = set()
    if base_symbols:
        found.update(base_symbols.keys())
    if keycode_to_name:
        found.update(keycode_to_name.values())
    nums = []
    for code in found:
        m = re.fullmatch(r"FK(\d{2})", code)
        if m:
            nums.append(int(m.group(1)))
    max_detected = max(nums) if nums else 12
    # En XKB pueden existir FK01-FK12 aunque el teclado físico no tenga todas.
    # Mostramos F1-F12 como base normal y ampliamos si el mapa detecta más.
    count = max(12, max_detected)
    # Límite prudente: muchos mapas pueden definir teclas de función extendidas.
    count = min(count, 24)
    return [(f"FK{i:02d}", f"F{i}", 1.0)
        for i in range(1, count + 1)]

def keycap_symbol(symbols, fallback):
    if not symbols:
        return fallback
    normal = keysym_to_text(symbols[0]) if len(symbols) > 0 else ""
    shift = keysym_to_text(symbols[1]) if len(symbols) > 1 else ""
    if normal == "space":
        return "Space"
    if normal and shift and normal != shift:
        return f"{normal}/{shift}"
    if normal:
        return normal
    if shift:
        return shift
    text = keysym_to_text(fallback)
    return text if text else fallback

def normalized_symbols_for_values(values):
    syms = []
    for index, v in enumerate(values):
        raw = v or ""
        if not raw.strip():
            syms.append("NoSymbol")
            continue
        ok, message = validate_keysym_text(raw)
        if not ok:
            raise ValueError(message or f"Valor inválido en el nivel {index + 1}: {raw}")
        syms.append(text_to_keysym(raw) or "NoSymbol")
    while len(syms) < 4:
        syms.append("NoSymbol")
    return syms[:4]

class EditKeyDialog(Gtk.Dialog):
    def __init__(self, parent, code, current_values):
        super().__init__(title=f"Editar tecla <{code}>", transient_for=parent, flags=0)
        self.set_modal(True)
        self.add_button("Cancelar", Gtk.ResponseType.CANCEL)
        self.add_button("Guardar", Gtk.ResponseType.OK)
        self.set_default_size(560, 260)
        self.entries = []
        box = self.get_content_area()
        box.set_spacing(8)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(12)
        box.set_margin_end(12)
        info = Gtk.Label(label="Valores actuales de la tecla. Cambia sólo lo que quieras modificar.")
        info.set_xalign(0)
        box.pack_start(info, False, False, 0)
        grid = Gtk.Grid(column_spacing=8, row_spacing=8)
        grid.set_valign(Gtk.Align.START)
        box.pack_start(grid, False, False, 0)
        for i, name in enumerate(LEVEL_NAMES):
            lab = Gtk.Label(label=name)
            lab.set_xalign(0)
            grid.attach(lab, 0, i, 1, 1)
            entry = Gtk.Entry()
            entry.set_hexpand(True)
            entry.set_text(current_values[i])
            grid.attach(entry, 1, i, 1, 1)
            self.entries.append(entry)
            combo = Gtk.ComboBoxText()
            for s in SPECIAL_KEYSYMS:
                combo.append_text(s)
            combo.set_active(0)
            combo.connect("changed", self._special_selected, entry)
            grid.attach(combo, 2, i, 1, 1)
        self.show_all()

    def _special_selected(self, combo, entry):
        val = combo.get_active_text()
        if val:
            entry.set_text(val)

    def values(self):
        return [entry.get_text() for entry in self.entries]

class CaptureKeyDialog(Gtk.Dialog):
    def __init__(self, parent, keycode_to_name):
        super().__init__(title="Añadir tecla física", transient_for=parent, flags=0)
        self.keycode_to_name = keycode_to_name
        self.detected = None
        self.add_button("Cancelar", Gtk.ResponseType.CANCEL)
        self.set_modal(True)
        self.set_default_size(420, 140)
        label = Gtk.Label(label="Pulsa la tecla física que quieres añadir al editor.")
        label.set_margin_top(20)
        label.set_margin_bottom(20)
        label.set_margin_start(20)
        label.set_margin_end(20)
        self.get_content_area().pack_start(label, True, True, 0)
        self.connect("key-press-event", self.on_key_press)
        self.show_all()

    def on_key_press(self, _widget, event):
        code = self.keycode_to_name.get(event.hardware_keycode)
        if code:
            self.detected = code
            self.response(Gtk.ResponseType.OK)
        return True


class KeydShortcutCaptureDialog(Gtk.Dialog):
    MODIFIER_KEYVALS = {"Shift_L","Shift_R","Control_L","Control_R","Alt_L","Alt_R","Meta_L","Meta_R","Super_L","Super_R","Hyper_L","Hyper_R",
        "ISO_Level3_Shift","Mode_switch","Caps_Lock","Num_Lock"}
    KEYVAL_TO_KEYD = {"Escape":"esc","Tab":"tab","ISO_Left_Tab":"tab","Return":"enter","KP_Enter":"enter","BackSpace":"backspace","Delete":"delete",
        "Insert":"insert","Home":"home","End":"end","Page_Up":"pageup","Page_Down":"pagedown","Prior":"pageup","Next":"pagedown","Left":"left",
        "Right":"right","Up":"up","Down":"down","space":"space","minus":"minus","equal":"equal","slash":"slash","backslash":"backslash","comma":"comma",
        "period":"dot","semicolon":"semicolon","apostrophe":"apostrophe","grave":"grave","bracketleft":"leftbrace","bracketright":"rightbrace"}

    def __init__(self, parent, key_options):
        super().__init__(title="Detectar atajo", transient_for=parent, flags=0)
        self.key_options = list(key_options or [])
        self.detected_mods = []
        self.detected_key = ""
        self.add_button("Cancelar", Gtk.ResponseType.CANCEL)
        self.set_modal(True)
        self.set_default_size(420, 150)
        box = self.get_content_area()
        box.set_spacing(8)
        box.set_margin_top(14)
        box.set_margin_bottom(14)
        box.set_margin_start(14)
        box.set_margin_end(14)
        label = Gtk.Label(label="Pulsa el atajo completo que quieres detectar, por ejemplo Alt+Tab o Super+Space.")
        label.set_xalign(0)
        label.set_line_wrap(True)
        box.pack_start(label, True, True, 0)
        hint = Gtk.Label(label="Se guardan los modificadores y la tecla principal. Pulsa Esc para cancelar.")
        hint.get_style_context().add_class("uok-source-description")
        hint.set_xalign(0)
        hint.set_line_wrap(True)
        box.pack_start(hint, True, True, 0)
        self.connect("key-press-event", self.on_key_press)
        self.show_all()

    def key_option_names(self):
        return {key_name for _label, key_name, _code in self.key_options}

    def keyval_to_keyd(self, keyval):
        name = Gdk.keyval_name(keyval) or ""
        if name in self.MODIFIER_KEYVALS:
            return ""
        if name in self.KEYVAL_TO_KEYD:
            return self.KEYVAL_TO_KEYD[name]
        lower = name.lower()
        if re.fullmatch(r"[a-z0-9]", lower):
            return lower
        match = re.fullmatch(r"f([1-9]|1[0-9]|2[0-4])", lower)
        if match:
            return lower
        if lower.startswith("kp_"):
            value = lower[3:]
            if value in {"0","1","2","3","4","5","6","7","8","9"}:
                return value
        return self.KEYVAL_TO_KEYD.get(lower,lower)

    def source_mods_from_state(self, state):
        mods = []
        if state & Gdk.ModifierType.CONTROL_MASK:
            mods.append("control")
        if state & Gdk.ModifierType.MOD1_MASK:
            mods.append("alt")
        if state & Gdk.ModifierType.SHIFT_MASK:
            mods.append("shift")
        super_masks = (getattr(Gdk.ModifierType,"SUPER_MASK",0) | getattr(Gdk.ModifierType,"META_MASK",0) | getattr(Gdk.ModifierType,"HYPER_MASK",0)
            | getattr(Gdk.ModifierType,"MOD4_MASK",0))
        if state & super_masks:
            mods.append("meta")
        if state & Gdk.ModifierType.MOD5_MASK:
            mods.append("altgr")
        return mods

    def on_key_press(self, _widget, event):
        key_name = Gdk.keyval_name(event.keyval) or ""
        if key_name == "Escape":
            self.response(Gtk.ResponseType.CANCEL)
            return True
        keyd_key = self.keyval_to_keyd(event.keyval)
        if not keyd_key:
            return True
        valid_keys = self.key_option_names()
        if valid_keys and keyd_key not in valid_keys:
            # Algunos nombres de GDK coinciden con keyd tras normalizar,
            # pero si no existen en el mapa visible no los aceptamos.
            return True
        self.detected_mods = self.source_mods_from_state(event.state)
        self.detected_key = keyd_key
        self.response(Gtk.ResponseType.OK)
        return True

class KeydKeyPicker(Gtk.Box):

    def __init__(self, key_options, selected_key=""):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.key_options = list(key_options or [])
        self.selected_key = selected_key or (self.key_options[0][1] if self.key_options else "")
        self.button = Gtk.Button()
        self.button.set_hexpand(True)
        self.button.set_halign(Gtk.Align.FILL)
        self.button.connect("clicked", self.on_button_clicked)
        self.pack_start(self.button, True, True, 0)
        self.update_button_label()

    def option_text(self, option):
        label, key_name, _code = option
        return f"{label}  [{key_name}]"

    def update_button_label(self):
        text = self.selected_key or "Seleccionar tecla"
        for option in self.key_options:
            if option[1] == self.selected_key:
                text = self.option_text(option)
                break
        self.button.set_label(text)

    def on_button_clicked(self, _button):
        dialog = Gtk.Dialog(title="Seleccionar tecla",transient_for=self.get_toplevel() if isinstance(self.get_toplevel(),Gtk.Window) else None,
            flags=Gtk.DialogFlags.MODAL)
        dialog.add_button("Cancelar", Gtk.ResponseType.CANCEL)
        dialog.set_default_size(420, 420)
        dialog.set_resizable(True)
        area = dialog.get_content_area()
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        outer.set_margin_top(10)
        outer.set_margin_bottom(10)
        outer.set_margin_start(10)
        outer.set_margin_end(10)
        area.pack_start(outer, True, True, 0)
        search = Gtk.SearchEntry()
        search.set_placeholder_text("Buscar tecla…")
        outer.pack_start(search, False, False, 0)
        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_size_request(380, 300)
        scrolled.add(listbox)
        outer.pack_start(scrolled, True, True, 0)

        def rebuild():
            for row in list(listbox.get_children()):
                listbox.remove(row)
            query = search.get_text().strip().lower()
            for option in self.key_options:
                label, key_name, code = option
                haystack = " ".join([str(label), str(key_name), str(code)]).lower()
                if query and query not in haystack:
                    continue
                row = Gtk.ListBoxRow()
                row.uok_keyd_key = key_name
                row.set_selectable(True)
                row.set_activatable(True)
                text = Gtk.Label(label=self.option_text(option))
                text.set_xalign(0)
                text.set_margin_top(6)
                text.set_margin_bottom(6)
                text.set_margin_start(8)
                text.set_margin_end(8)
                text.set_ellipsize(3)
                row.add(text)
                listbox.add(row)
                if key_name == self.selected_key:
                    listbox.select_row(row)
            listbox.show_all()

        def choose(row):
            key = getattr(row, "uok_keyd_key", "")
            if key:
                self.selected_key = key
                self.update_button_label()
                dialog.response(Gtk.ResponseType.OK)

        def on_row_activated(_listbox, row):
            choose(row)

        def on_search_changed(_entry):
            rebuild()

        listbox.connect("row-activated", on_row_activated)
        search.connect("search-changed", on_search_changed)
        rebuild()
        dialog.show_all()
        search.grab_focus()
        dialog.run()
        dialog.destroy()

    def set_selected_key(self, key):
        self.selected_key = key or self.selected_key
        self.update_button_label()

    def get_selected_key(self):
        return self.selected_key

class KeydShortcutDialog(Gtk.Dialog):
    def __init__(self, parent, key_options, rule=None, block_all_shortcuts=False):
        super().__init__(title="Editar atajo keyd", transient_for=parent, flags=0)
        self.key_options = key_options
        self.block_all_shortcuts = block_all_shortcuts
        self.mod_checks = []
        self.target_mod_checks = []
        self.set_modal(True)
        self.add_button("Cancelar", Gtk.ResponseType.CANCEL)
        self.add_button("Guardar", Gtk.ResponseType.OK)
        self.set_default_size(620, 360)
        rule = rule or {"source_mods":[],"source_key":key_options[0][1] if key_options else "a","action":"replace" if block_all_shortcuts else "block",
            "target_mods":[],"target_key":key_options[0][1] if key_options else "a"}
        box = self.get_content_area()
        box.set_spacing(10)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(12)
        box.set_margin_end(12)
        if block_all_shortcuts:
            info_text = ("Bloqueo global activo: todos los atajos con modificadores quedan bloqueados. "
                "Aquí sólo añades excepciones o reemplazos concretos.")
        else:
            info_text = ("Define el atajo original y, si eliges reemplazar, el atajo destino. "
                "El destino se guarda como tecla lógica y UOK lo traduce a la posición física del layout.")
        info = Gtk.Label(label=info_text)
        info.set_xalign(0)
        info.set_line_wrap(True)
        box.pack_start(info, False, False, 0)
        grid = Gtk.Grid(column_spacing=10, row_spacing=10)
        box.pack_start(grid, False, False, 0)
        source_title = Gtk.Label(label="Atajo original")
        source_title.get_style_context().add_class("uok-keyd-section-title")
        source_title.set_xalign(0)
        grid.attach(source_title, 0, 0, 2, 1)
        grid.attach(Gtk.Label(label="Modificadores", xalign=0), 0, 1, 1, 1)
        source_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        source_row.set_hexpand(True)
        grid.attach(source_row, 1, 1, 1, 1)
        source_mod_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        source_row.pack_start(source_mod_box, False, False, 0)
        selected_source_mods = set(rule.get("source_mods", []))
        for label, layer, _prefix in KEYD_SOURCE_MODIFIERS:
            check = Gtk.CheckButton(label=label)
            check.uok_keyd_value = layer
            check.set_active(layer in selected_source_mods)
            source_mod_box.pack_start(check, False, False, 0)
            self.mod_checks.append(check)
        capture_btn = Gtk.Button(label="Detectar…")
        capture_btn.set_hexpand(True)
        capture_btn.set_halign(Gtk.Align.FILL)
        capture_btn.set_tooltip_text("Pulsar directamente el atajo original, por ejemplo Alt+Tab")
        capture_btn.connect("clicked", self.on_capture_source_shortcut)
        source_row.pack_start(capture_btn, True, True, 0)
        grid.attach(Gtk.Label(label="Tecla", xalign=0), 0, 2, 1, 1)
        self.source_key_combo = self.make_key_combo(rule.get("source_key", ""))
        grid.attach(self.source_key_combo, 1, 2, 1, 1)
        action_title = Gtk.Label(label="Acción")
        action_title.get_style_context().add_class("uok-keyd-section-title")
        action_title.set_xalign(0)
        grid.attach(action_title, 0, 3, 2, 1)
        if block_all_shortcuts:
            self.block_radio = None
            self.replace_radio = Gtk.RadioButton.new_with_label_from_widget(None,"Añadir atajo permitido / reemplazo")
            self.replace_radio.set_active(True)
            grid.attach(self.replace_radio, 0, 4, 2, 1)
            target_row_offset = 5
        else:
            self.block_radio = Gtk.RadioButton.new_with_label_from_widget(None, "Bloquear atajo")
            self.replace_radio = Gtk.RadioButton.new_with_label_from_widget(self.block_radio,"Reemplazar por otro atajo")
            grid.attach(self.block_radio, 0, 4, 2, 1)
            grid.attach(self.replace_radio, 0, 5, 2, 1)
            self.block_radio.set_active(rule.get("action") != "replace")
            self.replace_radio.set_active(rule.get("action") == "replace")
            self.block_radio.connect("toggled", self.on_action_toggled)
            target_row_offset = 6
        grid.attach(Gtk.Label(label="Modificadores destino", xalign=0), 0, target_row_offset, 1, 1)
        target_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        target_row.set_hexpand(True)
        grid.attach(target_row,1,target_row_offset,1,1)
        self.target_mod_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        target_row.pack_start(self.target_mod_box, False, False, 0)
        selected_target_mods = set(rule.get("target_mods", []))
        for label, _layer, prefix in KEYD_SOURCE_MODIFIERS:
            check = Gtk.CheckButton(label=label)
            check.uok_keyd_value = prefix
            check.set_active(prefix in selected_target_mods)
            self.target_mod_box.pack_start(check, False, False, 0)
            self.target_mod_checks.append(check)
        target_capture_btn = Gtk.Button(label="Detectar destino…")
        target_capture_btn.set_tooltip_text(
            "Pulsar directamente el atajo de destino. Se guardará como atajo lógico y UOK lo traducirá a la posición física del layout.")
        target_capture_btn.connect("clicked", self.on_capture_target_shortcut)
        target_row.pack_start(target_capture_btn, False, False, 0)
        grid.attach(Gtk.Label(label="Tecla destino", xalign=0), 0, target_row_offset + 1, 1, 1)
        self.target_key_combo = self.make_key_combo(rule.get("target_key", ""))
        grid.attach(self.target_key_combo, 1, target_row_offset + 1, 1, 1)
        self.update_target_controls()
        self.show_all()

    def set_source_mods(self, mods):
        selected = set(mods or [])
        for check in self.mod_checks:
            check.set_active(check.uok_keyd_value in selected)

    def set_source_key(self, key):
        if hasattr(self.source_key_combo, "set_selected_key"):
            self.source_key_combo.set_selected_key(key)
            return
        for idx, (_label, key_name, _code) in enumerate(self.key_options):
            if key_name == key:
                self.source_key_combo.set_active(idx)
                return

    def target_mods_from_source_mods(self, mods):
        source_to_target = {"control":"C","alt":"A","shift":"S","meta":"M","altgr":"G"}
        return [source_to_target[mod] for mod in mods if mod in source_to_target]

    def set_target_mods(self, mods):
        selected = set(mods or [])
        for check in self.target_mod_checks:
            check.set_active(check.uok_keyd_value in selected)

    def set_target_key(self, key):
        if hasattr(self.target_key_combo, "set_selected_key"):
            self.target_key_combo.set_selected_key(key)
            return
        for idx, (_label, key_name, _code) in enumerate(self.key_options):
            if key_name == key:
                self.target_key_combo.set_active(idx)
                return

    def on_capture_source_shortcut(self, _button):
        dialog = KeydShortcutCaptureDialog(self, self.key_options)
        response = dialog.run()
        if response == Gtk.ResponseType.OK and dialog.detected_key:
            self.set_source_mods(dialog.detected_mods)
            self.set_source_key(dialog.detected_key)
        dialog.destroy()

    def on_capture_target_shortcut(self, _button):
        if self.block_radio is not None and not self.replace_radio.get_active():
            self.replace_radio.set_active(True)
        dialog = KeydShortcutCaptureDialog(self, self.key_options)
        response = dialog.run()
        if response == Gtk.ResponseType.OK and dialog.detected_key:
            self.set_target_mods(self.target_mods_from_source_mods(dialog.detected_mods))
            self.set_target_key(dialog.detected_key)
            self.update_target_controls()
        dialog.destroy()

    def make_key_combo(self, selected_key):
        return KeydKeyPicker(self.key_options, selected_key)

    def selected_key(self, combo):
        if hasattr(combo, "get_selected_key"):
            return combo.get_selected_key()
        index = combo.get_active()
        if index < 0 or index >= len(self.key_options):
            return ""
        return self.key_options[index][1]

    def update_target_controls(self):
        sensitive = self.block_all_shortcuts or self.replace_radio.get_active()
        self.target_key_combo.set_sensitive(sensitive)
        for child in self.target_mod_box.get_children():
            child.set_sensitive(sensitive)

    def on_action_toggled(self, _button):
        self.update_target_controls()

    def values(self):
        source_mods = [check.uok_keyd_value for check in self.mod_checks if check.get_active()]
        target_mods = [check.uok_keyd_value for check in self.target_mod_checks if check.get_active()]
        return {"source_mods":source_mods,"source_key":self.selected_key(self.source_key_combo),"action":"replace" if self.block_all_shortcuts 
            or self.replace_radio.get_active() else "block","target_mods":target_mods,"target_key":self.selected_key(self.target_key_combo)}

def uok_editor_append_mate_system_sources(source_items):
    if not uok_editor_is_mate_desktop():
        return source_items
    if not isinstance(source_items, list):
        return source_items
    rows = uok_editor_system_source_rows()
    if not rows:
        return source_items
    added = []
    for row in rows:
        layout_id = row.get("id", "")
        label = row.get("label") or layout_id
        if not layout_id:
            continue
        added.append({
            "section":"Añadidas del sistema","kind":"system-other","id":f"mate-system:{layout_id}","source_id":layout_id,"include":layout_id,
            "label":label,"description":"Distribución del sistema añadida","xkb_file":""})
    # Quitar versiones anteriores de esta misma sección para no duplicar.
    cleaned = []
    for item in source_items:
        if isinstance(item, dict) and item.get("section") == "Añadidas del sistema":
            continue
        cleaned.append(item)
    return added + cleaned

class UokLayoutEditor(Gtk.Window):
    def __init__(self):
        super().__init__(title="UrOwnKeyboard - Editor visual")
        self.set_default_size(1180, 620)
        self.connect("destroy", Gtk.main_quit)
        text = current_symbols_text()
        self.base_symbols = parse_key_symbols(text)
        self.keycode_to_name = parse_keycodes(text)
        self.include_name = xkb_include_from_current()
        self.changes = {}
        self.buttons = {}
        self.keyd_shortcuts = []
        self.keyd_block_all_shortcuts = False
        self.keyd_rows = []
        self.extra_keys = []
        self.function_key_row = detected_function_key_row(self.base_symbols,self.keycode_to_name)
        # Separador redimensionable izquierda/derecha.
        root_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        root_paned.set_wide_handle(True)
        root_paned.set_hexpand(True)
        root_paned.set_vexpand(True)
        self.add(root_paned)
        self.root_paned = root_paned
        self.source_items = load_xkb_sources(CURRENT_PROFILE, CONFIG / "profiles")
        self.source_items = uok_editor_merge_mate_gsettings_layouts(self.source_items)
        self.source_items = uok_editor_append_mate_system_sources(self.source_items)
        sidebar = self.build_sources_sidebar()
        sidebar.set_hexpand(True)
        sidebar.set_vexpand(True)
        root_paned.pack1(sidebar, resize=True, shrink=False)
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        right.set_hexpand(True)
        right.set_vexpand(True)
        root_paned.pack2(right, resize=True, shrink=False)
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header.set_margin_top(8)
        header.set_margin_bottom(8)
        header.set_margin_start(8)
        header.set_margin_end(8)
        right.pack_start(header, False, False, 0)
        self.base_label = Gtk.Label(label=f"Base: {self.include_name}")
        self.base_label.set_xalign(0)
        header.pack_start(self.base_label, False, False, 0)
        name_label = Gtk.Label(label="Nombre:")
        header.pack_start(name_label, False, False, 0)
        self.name_entry = Gtk.Entry()
        self.name_entry.set_text("Mi teclado visual")
        self.name_entry.set_hexpand(True)
        header.pack_start(self.name_entry, True, True, 0)
        add_btn = Gtk.Button(label="Añadir tecla física…")
        add_btn.connect("clicked", self.on_add_physical_key)
        header.pack_start(add_btn, False, False, 0)
        export_btn = Gtk.Button(label="Exportar XKB…")
        export_btn.connect("clicked", self.on_export_xkb)
        header.pack_start(export_btn, False, False, 0)
        save_btn = Gtk.Button(label="Añadir configuración")
        save_btn.connect("clicked", self.on_save)
        header.pack_start(save_btn, False, False, 0)
        # Separador redimensionable teclado/atajos.
        right_paned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        right_paned.set_wide_handle(True)
        right_paned.set_hexpand(True)
        right_paned.set_vexpand(True)
        right.pack_start(right_paned, True, True, 0)
        self.right_paned = right_paned
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        self.keyboard_outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.keyboard_outer.set_hexpand(True)
        self.keyboard_outer.set_vexpand(True)
        self.keyboard_outer.set_halign(Gtk.Align.CENTER)
        self.keyboard_outer.set_valign(Gtk.Align.CENTER)
        self.keyboard_frame = Gtk.Frame()
        self.keyboard_frame.get_style_context().add_class("uok-keyboard-frame")
        self.keyboard_frame.set_shadow_type(Gtk.ShadowType.NONE)
        self.keyboard_frame.set_halign(Gtk.Align.CENTER)
        self.keyboard_frame.set_valign(Gtk.Align.CENTER)
        self.keyboard_frame.set_hexpand(False)
        self.keyboard_frame.set_vexpand(False)
        self.keyboard_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.keyboard_box.set_margin_top(14)
        self.keyboard_box.set_margin_bottom(14)
        self.keyboard_box.set_margin_start(14)
        self.keyboard_box.set_margin_end(14)
        self.keyboard_box.set_halign(Gtk.Align.START)
        self.keyboard_box.set_valign(Gtk.Align.START)
        self.keyboard_box.set_hexpand(False)
        self.keyboard_box.set_vexpand(False)
        self.keyboard_frame.add(self.keyboard_box)
        self.keyboard_outer.pack_start(self.keyboard_frame, False, False, 0)
        try:
            scrolled.add_with_viewport(self.keyboard_outer)
        except AttributeError:
            scrolled.add(self.keyboard_outer)
        self.keyd_editor = self.build_keyd_editor()
        self.keyd_editor.set_hexpand(True)
        self.keyd_editor.set_vexpand(True)
        right_paned.pack1(scrolled, resize=True, shrink=False)
        right_paned.pack2(self.keyd_editor, resize=True, shrink=False)
        # Posiciones iniciales tras mostrar la ventana. Si se ponen antes,
        # GTK puede ignorarlas porque todavía no conoce el tamaño real.
        def set_initial_paned_positions():
            root_paned.set_position(150)
            allocation = right_paned.get_allocation()
            if allocation.height > 0:
                right_paned.set_position(max(220, allocation.height - 175))
            else:
                right_paned.set_position(445)
            return False
        Gdk.threads_add_idle(0, set_initial_paned_positions)
        self.draw_keyboard()
        self.show_all()

    def build_sources_sidebar(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        outer.get_style_context().add_class("uok-sidebar")
        outer.set_size_request(140, -1)
        outer.set_hexpand(False)
        outer.set_vexpand(True)
        outer.set_margin_top(10)
        outer.set_margin_bottom(10)
        outer.set_margin_start(8)
        outer.set_margin_end(8)
        title = Gtk.Label(label="Fuentes de entrada")
        title.get_style_context().add_class("uok-sidebar-title")
        title.set_xalign(0)
        outer.pack_start(title, False, False, 0)
        self.sources_search = Gtk.SearchEntry()
        self.sources_search.set_placeholder_text("Buscar…")
        self.sources_search.connect("search-changed", self.on_sources_search_changed)
        outer.pack_start(self.sources_search, False, False, 0)
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        outer.pack_start(scrolled, True, True, 0)
        self.sources_list = Gtk.ListBox()
        self.sources_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.sources_list.connect("row-selected", self.on_source_row_selected)
        scrolled.add(self.sources_list)
        self.rebuild_sources_list()
        return outer

    def source_matches_filter(self, item, query):
        if not query:
            return True
        haystack = " ".join([item.get("section",""),item.get("label",""),item.get("description",""),item.get("source_id", ""),item.get("include","")]).lower()
        return query.lower() in haystack

    def make_section_row(self, title):
        row = Gtk.ListBoxRow()
        row.set_selectable(False)
        row.set_activatable(False)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_margin_top(10)
        box.set_margin_bottom(5)
        box.set_margin_start(6)
        box.set_margin_end(6)
        sep = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        sep.get_style_context().add_class("uok-source-separator")
        sep.set_size_request(-1, 2)
        box.pack_start(sep, False, False, 0)
        label_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        label_box.get_style_context().add_class("uok-source-section-box")
        label_box.set_margin_top(2)
        label = Gtk.Label(label=title)
        label.get_style_context().add_class("uok-source-section")
        label.set_xalign(0)
        label.set_margin_top(4)
        label.set_margin_bottom(4)
        label.set_margin_start(8)
        label.set_margin_end(8)
        label_box.pack_start(label, True, True, 0)
        box.pack_start(label_box, False, False, 0)
        row.add(box)
        return row

    def make_source_row(self, item):
        row = Gtk.ListBoxRow()
        row.uok_source_item = item
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_margin_top(6)
        box.set_margin_bottom(6)
        box.set_margin_start(10)
        box.set_margin_end(10)
        label = Gtk.Label(label=item.get("label", ""))
        label.set_xalign(0)
        label.set_ellipsize(3)
        box.pack_start(label, False, False, 0)
        description = item.get("description", "") or item.get("include", "")
        if description:
            sub = Gtk.Label(label=description)
            sub.get_style_context().add_class("uok-source-description")
            sub.set_xalign(0)
            sub.set_ellipsize(3)
            box.pack_start(sub, False, False, 0)
        row.add(box)
        return row

    def rebuild_sources_list(self):
        try:
            self.source_items = uok_editor_merge_mate_gsettings_layouts(self.source_items)
        except Exception:
            pass
        for child in list(self.sources_list.get_children()):
            self.sources_list.remove(child)
        query = self.sources_search.get_text().strip() if hasattr(self, "sources_search") else ""
        sections = ["UOK", "Añadidas del sistema", "Added to system", "Others"]
        for section in sections:
            items = [item
                for item in self.source_items
                if item.get("section") == section and self.source_matches_filter(item, query)]
            if not items:
                continue
            self.sources_list.add(self.make_section_row(section))
            for item in items:
                self.sources_list.add(self.make_source_row(item))
        self.sources_list.show_all()

    def on_sources_search_changed(self, _entry):
        self.rebuild_sources_list()

    def on_source_row_selected(self, _listbox, row):
        if row is None:
            return
        item = getattr(row, "uok_source_item", None)
        if not item:
            return
        self.load_source_item(item)

    def load_source_item(self, item):
        include = item.get("include", "") or item.get("source_id", "") or item.get("id", "")
        kind = item.get("kind", "")
        is_uok_item = item.get("section") == "UOK" or kind in {"uok","imported-profile","visual-profile"}
        text = ""
        # Para perfiles UOK/importados no basta con leer el archivo crudo:
        # suele ser un wrapper con include "...", y puede contener pocas o
        # ninguna tecla redefinida. Compilamos primero el layout completo.
        if is_uok_item and include:
            text = xkb_dump_from_include(include)
        if not text and is_uok_item:
            xkb_file = item.get("xkb_file", "")
            if xkb_file:
                path = Path(xkb_file).expanduser()
                if path.exists():
                    text = path.read_text(encoding="utf-8")
        if not text and include:
            text = xkb_dump_from_include(include)
        if not text:
            self.message("No se pudo cargar la fuente",item.get("label",include),Gtk.MessageType.ERROR)
            return
        parsed = parse_key_symbols(text)
        if not parsed:
            self.message("No se pudieron leer las teclas","La fuente se ha cargado, pero no se han encontrado símbolos XKB editables.",Gtk.MessageType.ERROR)
            return
        self.base_symbols = parsed
        self.include_name = include
        self.changes.clear()
        self.buttons.clear()
        self.base_label.set_text(f"Base: {self.include_name}")
        self.draw_keyboard()

    def base_for_code(self, code):
        base = list(self.base_symbols.get(code, []))[:4]
        while len(base) < 4:
            base.append("NoSymbol")
        return base

    def symbols_for_code(self, code):
        base = self.base_for_code(code)
        return self.changes.get(code, base)

    def entry_values_for_code(self, code):
        return [keysym_to_text(s) for s in self.symbols_for_code(code)]

    def key_pixel_width(self, width):
        return int(54 * width) + 12

    def row_pixel_width(self, row):
        if not row:
            return 0
        keys_width = sum(self.key_pixel_width(width) for _code, _fallback, width in row)
        spacing_width = 6 * (len(row) - 1)
        return keys_width + spacing_width

    def max_main_keyboard_width(self):
        if not LAYOUT_ROWS:
            return 0
        return max(self.row_pixel_width(row) for row in LAYOUT_ROWS)

    def wrap_key_items(self, items, max_width):
        rows = []
        current = []
        current_width = 0
        for item in items:
            item_width = self.key_pixel_width(item[2])
            if current:
                candidate_width = current_width + 6 + item_width
            else:
                candidate_width = item_width
            if current and candidate_width > max_width:
                rows.append(current)
                current = [item]
                current_width = item_width
            else:
                current.append(item)
                current_width = candidate_width
        if current:
            rows.append(current)
        return rows

    def make_row_box(self):
        h = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        h.set_halign(Gtk.Align.CENTER)
        h.set_valign(Gtk.Align.START)
        h.set_hexpand(False)
        h.set_vexpand(False)
        return h

    def build_keyd_editor(self):
        frame = Gtk.Frame(label="Atajos keyd")
        frame.get_style_context().add_class("uok-keyd-frame")
        frame.set_shadow_type(Gtk.ShadowType.NONE)
        frame.set_halign(Gtk.Align.FILL)
        frame.set_hexpand(True)
        frame.set_vexpand(True)
        frame.set_margin_top(6)
        frame.set_margin_bottom(6)
        frame.set_margin_start(8)
        frame.set_margin_end(8)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        outer.set_margin_top(5)
        outer.set_margin_bottom(5)
        outer.set_margin_start(8)
        outer.set_margin_end(8)
        outer.set_vexpand(True)
        outer.set_hexpand(True)
        frame.add(outer)
        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        top_row.set_vexpand(False)
        top_row.set_hexpand(True)
        outer.pack_start(top_row, False, False, 0)
        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        buttons.set_vexpand(False)
        buttons.set_valign(Gtk.Align.CENTER)
        buttons.set_halign(Gtk.Align.START)
        top_row.pack_start(buttons, False, False, 0)
        add_btn = Gtk.Button(label="Añadir atajo…")
        add_btn.set_tooltip_text("Añadir atajo")
        add_btn.connect("clicked", self.on_add_keyd_shortcut)
        buttons.pack_start(add_btn, False, False, 0)
        edit_btn = Gtk.Button(label="Editar seleccionado…")
        edit_btn.set_tooltip_text("Editar atajo seleccionado")
        edit_btn.connect("clicked", self.on_edit_keyd_shortcut)
        buttons.pack_start(edit_btn, False, False, 0)
        delete_btn = Gtk.Button(label="Eliminar seleccionado")
        delete_btn.set_tooltip_text("Eliminar atajo seleccionado")
        delete_btn.connect("clicked", self.on_delete_keyd_shortcut)
        buttons.pack_start(delete_btn, False, False, 0)
        preview_btn = Gtk.Button(label="Exportar keyd.conf…")
        preview_btn.set_tooltip_text("Exportar keyd.conf generado")
        preview_btn.connect("clicked", self.on_preview_keyd_conf)
        buttons.pack_start(preview_btn, False, False, 0)
        keyd_scroll = Gtk.ScrolledWindow()
        keyd_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        keyd_scroll.set_hexpand(True)
        keyd_scroll.set_vexpand(True)
        keyd_scroll.set_size_request(-1, 154)
        keyd_scroll.get_style_context().add_class("uok-keyd-scroll")
        self.keyd_list = Gtk.FlowBox()
        self.keyd_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.keyd_list.set_vexpand(False)
        self.keyd_list.set_hexpand(True)
        self.keyd_list.set_max_children_per_line(99)
        self.keyd_list.set_min_children_per_line(1)
        self.keyd_list.set_column_spacing(5)
        self.keyd_list.set_row_spacing(10)
        self.keyd_list.set_homogeneous(False)
        self.keyd_list.set_valign(Gtk.Align.START)
        keyd_scroll.add(self.keyd_list)
        outer.pack_start(keyd_scroll, True, True, 0)
        self.refresh_keyd_shortcuts()
        return frame

    def on_keyd_block_all_toggled(self, check):
        self.keyd_block_all_shortcuts = False
        if check is not None:
            try:
                check.set_active(False)
            except Exception:
                pass
        self.refresh_keyd_shortcuts()

    def keyd_key_options(self):
        items = []
        seen = set()

        def add(code, fallback):
            if code in KEYD_MODIFIER_KEYCODES:
                return
            key_name = keyd_name_for_code(code)
            if not key_name or key_name in seen:
                return
            seen.add(key_name)
            label = self.button_label(code, fallback) if hasattr(self, "base_symbols") else fallback
            label = label.replace("\n", " ").strip() or fallback or code
            items.append((label, key_name, code))
        for row in LAYOUT_ROWS:
            for code, fallback, _width in row:
                add(code, fallback)
        for code, fallback, _width in self.function_key_row:
            add(code, fallback)
        for code in self.extra_keys:
            add(code, code)
        return items

    def keyd_source_expr(self, rule):
        mods = list(rule.get("source_mods", []))
        key = rule.get("source_key", "")
        return "+".join(mods), key

    def keyd_target_expr(self, rule):
        if rule.get("action") != "replace":
            return "noop"
        mods = list(rule.get("target_mods", []))
        key = rule.get("target_key", "")
        if mods:
            return "-".join(mods + [key])
        return key

    def keyd_rule_label(self, rule):
        source_mods = [label for label, layer, _prefix in KEYD_SOURCE_MODIFIERS if layer in rule.get("source_mods", [])]
        source = "+".join(source_mods + [rule.get("source_key", "")])
        if rule.get("action") == "replace":
            target_mods = [label for label, _layer, prefix in KEYD_SOURCE_MODIFIERS if prefix in rule.get("target_mods", [])]
            target = "+".join(target_mods + [rule.get("target_key", "")])
            return f"{source}  →  {target}"
        return f"{source}  →  bloqueado"

    def refresh_keyd_shortcuts(self):
        if not hasattr(self, "keyd_list"):
            return
        for child in list(self.keyd_list.get_children()):
            self.keyd_list.remove(child)
        if not self.keyd_shortcuts:
            child = Gtk.FlowBoxChild()
            child.set_can_focus(False)
            label = Gtk.Label(label="Sin atajos keyd definidos para esta configuración.")
            label.set_xalign(0)
            label.set_margin_top(6)
            label.set_margin_bottom(6)
            label.set_margin_start(8)
            label.set_margin_end(8)
            child.add(label)
            self.keyd_list.add(child)
        else:
            for idx, rule in enumerate(self.keyd_shortcuts):
                child = Gtk.FlowBoxChild()
                child.uok_keyd_index = idx
                child.get_style_context().add_class("uok-keyd-chip")
                label = Gtk.Label(label=self.keyd_rule_label(rule))
                label.set_xalign(0)
                label.set_margin_top(1)
                label.set_margin_bottom(1)
                label.set_margin_start(6)
                label.set_margin_end(6)
                label.set_single_line_mode(True)
                label.set_ellipsize(3)
                child.add(label)
                self.keyd_list.add(child)
        self.keyd_list.show_all()

    def selected_keyd_index(self):
        if not hasattr(self, "keyd_list"):
            return None
        selected = self.keyd_list.get_selected_children()
        if not selected:
            return None
        child = selected[0]
        return getattr(child, "uok_keyd_index", None)

    def keyd_rule_signature(self, rule):
        return (self.keyd_normalized_mods(rule.get("source_mods", [])),rule.get("source_key", ""),rule.get("action", "block"),
            tuple(rule.get("target_mods", [])),rule.get("target_key", ""))

    def add_or_replace_keyd_shortcut(self, rule, skip_index=None):
        signature = self.keyd_rule_signature(rule)
        for idx, existing in enumerate(self.keyd_shortcuts):
            if skip_index is not None and idx == skip_index:
                continue
            if self.keyd_rule_signature(existing) == signature:
                self.keyd_shortcuts[idx] = rule
                return False
        if skip_index is None:
            self.keyd_shortcuts.append(rule)
        else:
            self.keyd_shortcuts[skip_index] = rule
        return True

    def on_add_keyd_shortcut(self, _button):
        options = self.keyd_key_options()
        if not options:
            self.message("No hay teclas disponibles", "No se han podido generar teclas compatibles con keyd.", Gtk.MessageType.ERROR)
            return
        dialog = KeydShortcutDialog(self, options, block_all_shortcuts=False)
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            self.add_or_replace_keyd_shortcut(dialog.values())
            self.refresh_keyd_shortcuts()
        dialog.destroy()

    def on_edit_keyd_shortcut(self, _button):
        index = self.selected_keyd_index()
        if index is None:
            self.message("Selecciona un atajo", "Elige primero un atajo keyd de la lista.")
            return
        options = self.keyd_key_options()
        dialog = KeydShortcutDialog(self, options, self.keyd_shortcuts[index], block_all_shortcuts=self.keyd_block_all_shortcuts)
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            self.add_or_replace_keyd_shortcut(dialog.values(), skip_index=index)
            self.refresh_keyd_shortcuts()
        dialog.destroy()

    def on_delete_keyd_shortcut(self, _button):
        index = self.selected_keyd_index()
        if index is None:
            self.message("Selecciona un atajo", "Elige primero un atajo keyd de la lista.")
            return
        del self.keyd_shortcuts[index]
        self.refresh_keyd_shortcuts()

    def keyd_modifier_specs(self):
        return [{"id":"control","short":"ctrl","layer":"ctrlq","target_prefix":"C","keys":["leftcontrol","rightcontrol"]},
            {"id":"alt","short":"alt","layer":"altq","target_prefix":"A","keys":["leftalt"]},
            {"id":"shift","short":"shift","layer":"shiftq","target_prefix":"S","keys":["leftshift","rightshift"]},
            {"id":"meta","short":"meta","layer":"metaq","target_prefix":"M","keys":["leftmeta","rightmeta"]},
            {"id":"altgr","short":"altgr","layer":"altgrq","target_prefix":"G","keys":["rightalt"]}]

    def keyd_modifier_order(self):
        return [spec["id"] for spec in self.keyd_modifier_specs()]

    def keyd_modifier_spec(self, mod):
        for spec in self.keyd_modifier_specs():
            if spec["id"] == mod:
                return spec
        return None

    def keyd_normalized_mods(self, mods):
        selected = set(mods or [])
        return tuple(mod
            for mod in self.keyd_modifier_order()
            if mod in selected)

    def keyd_layer_name_for_mods(self, mods):
        mods = self.keyd_normalized_mods(mods)
        if not mods:
            return "main"
        if len(mods) == 1:
            spec = self.keyd_modifier_spec(mods[0])
            return spec["layer"] if spec else f"{mods[0]}q"
        parts = []
        for mod in mods:
            spec = self.keyd_modifier_spec(mod)
            parts.append(spec["short"] if spec else mod)
        return "_".join(parts) + "q"

    def keyd_all_modifier_combinations(self):
        mods = self.keyd_modifier_order()
        out = []
        for mask in range(1, 1 << len(mods)):
            combo = tuple(mods[i]
                for i in range(len(mods))
                if mask & (1 << i))
            out.append(combo)
        return out

    def keyd_required_layer_sets(self, rules):
        required = set()
        for rule in rules:
            mods = self.keyd_normalized_mods(rule.get("source_mods", []))
            if mods:
                required.add(mods)
                # Añadimos también las capas intermedias para poder llegar a
                # combinaciones como Ctrl+Alt desde Ctrl o desde Alt.
                for i in range(1, len(mods)):
                    required.add(mods[:i])
        if self.keyd_block_all_shortcuts:
            required.update(self.keyd_all_modifier_combinations())
        return required

    def keyd_add_layer_transitions(self, groups, required_layers):
        # [main] activa las capas de modificadores.
        groups.setdefault("main", {})
        required_layers = {self.keyd_normalized_mods(layer)
            for layer in required_layers
            if layer}
        # Para llegar a Ctrl+Alt independientemente del orden:
        # [main] leftcontrol -> ctrlq
        # [main] leftalt     -> altq
        # [ctrlq] leftalt    -> ctrl_altq
        # [altq] leftcontrol -> ctrl_altq
        for current in [tuple()] + sorted(required_layers, key=lambda x: (len(x), x)):
            current_set = set(current)
            current_layer = self.keyd_layer_name_for_mods(current)
            groups.setdefault(current_layer, {})
            for spec in self.keyd_modifier_specs():
                mod = spec["id"]
                if mod in current_set:
                    continue
                next_mods = self.keyd_normalized_mods(tuple(current) + (mod,))
                if next_mods not in required_layers:
                    continue
                next_layer = self.keyd_layer_name_for_mods(next_mods)
                for key_name in spec["keys"]:
                    groups[current_layer][key_name] = (f"layer({next_layer})", None)

    def keyd_keysym_to_keyd_name(self, sym):
        raw = (sym or "").strip()
        if not raw or raw == "NoSymbol":
            return ""
        text = keysym_to_text(raw)
        if text:
            raw = text
        value = raw.strip()
        aliases = {" ":"space","space":"space","Space":"space",".":"dot","period":"dot","dot":"dot",",":"comma","comma":"comma",";":"semicolon",
            "semicolon":"semicolon",":":"colon","colon":"colon","/":"slash","slash":"slash","backslash":"backslash","'":"apostrophe","apostrophe":"apostrophe",
            "`":"grave","grave":"grave","-":"minus","minus":"minus","=":"equal","equal":"equal","[":"leftbrace","bracketleft":"leftbrace","leftbrace":"leftbrace",
            "]":"rightbrace","bracketright":"rightbrace","rightbrace":"rightbrace","<":"102nd","less":"102nd","Tab":"tab","tab":"tab","Return":"enter",
            "Enter":"enter","enter":"enter","BackSpace":"backspace","backspace":"backspace","Escape":"esc","Esc":"esc","esc":"esc"}
        aliases[chr(92)] = "backslash"
        if value in aliases:
            return aliases[value]
        low = value.lower()
        if re.fullmatch(r"[a-z0-9]", low):
            return low
        if re.fullmatch(r"f([1-9]|1[0-9]|2[0-4])", low):
            return low
        return aliases.get(low, low)

    def keyd_translation_symbols(self):
        include = getattr(self, "include_name", "") or active_base_include()
        text = ""
        try:
            text = xkb_dump_from_include(include)
        except Exception:
            text = ""
        symbols = parse_key_symbols(text) if text else {}
        if not symbols:
            symbols = dict(getattr(self, "base_symbols", {}) or {})
        for code, values in getattr(self, "changes", {}).items():
            symbols[code] = values
        return symbols

    def keyd_inverse_layout_map(self):
        out = {}
        symbols = self.keyd_translation_symbols()
        for code, values in symbols.items():
            if not values:
                continue
            physical = keyd_name_for_code(code)
            if not physical:
                continue
            logical = self.keyd_keysym_to_keyd_name(values[0])
            if logical and logical not in out:
                out[logical] = physical
        for key in ["esc","tab","enter","backspace","space","left","right","up","down","pageup","pagedown","home","end","insert","delete"]:
            out.setdefault(key, key)
        for i in range(1, 25):
            out.setdefault(f"f{i}", f"f{i}")
        return out

    def keyd_translate_target_key(self, key):
        key = (key or "").strip()
        if not key:
            return ""
        inverse = self.keyd_inverse_layout_map()
        return inverse.get(key, key)

    def keyd_target_expr_translated(self, rule):
        if rule.get("action") != "replace":
            return "noop"
        mods = list(rule.get("target_mods", []))
        key = self.keyd_translate_target_key(rule.get("target_key", ""))
        if not key:
            return ""
        if mods:
            return "-".join(mods + [key])
        return key

    def keyd_required_layers_for_rules(self, rules):
        required = set()
        for rule in rules:
            mods = self.keyd_normalized_mods(rule.get("source_mods", []))
            if not mods:
                continue
            required.add(mods)
            for i in range(1, len(mods)):
                required.add(mods[:i])
            if len(mods) > 1:
                for mod in mods:
                    parent = tuple(x for x in mods if x != mod)
                    if parent:
                        required.add(self.keyd_normalized_mods(parent))
        if getattr(self, "keyd_block_all_shortcuts", False):
            try:
                required.update(self.keyd_all_modifier_combinations())
            except Exception:
                pass
        return {self.keyd_normalized_mods(layer)
            for layer in required
            if layer}

    def build_keyd_conf(self):
        if not self.keyd_shortcuts:
            return ""
        rules = [rule for rule in self.keyd_shortcuts
            if rule.get("source_key", "")]
        if not rules:
            return ""
        required_layers = self.keyd_required_layers_for_rules(rules)
        groups = {}
        self.keyd_add_layer_transitions(groups, required_layers)
        used = set()
        def add_rule(section, left, right, comment=None):
            if not section or not left or not right:
                return
            key = (section, left)
            if key in used:
                return
            used.add(key)
            groups.setdefault(section, {})
            groups[section][left] = (right, comment)
        for rule in rules:
            source_key = rule.get("source_key", "")
            source_mods = self.keyd_normalized_mods(rule.get("source_mods", []))
            section = self.keyd_layer_name_for_mods(source_mods) if source_mods else "main"
            target = self.keyd_target_expr_translated(rule)
            if not source_key or not target:
                continue
            add_rule(section,source_key,target,self.keyd_rule_label(rule))
        lines = ["# Generated by UrOwnKeyboard visual editor","# Safe keyd mode: explicit shortcut layers only.","# Targets are translated through the active XKB layout.",
            "","[ids]","*",""]
        ordered_sections = ["main"] + [self.keyd_layer_name_for_mods(layer)
            for layer in sorted(required_layers, key=lambda x: (len(x), x))]
        emitted = set()
        for section in ordered_sections:
            if section in emitted:
                continue
            emitted.add(section)
            body = groups.get(section, {})
            if not body:
                continue
            lines.append(f"[{section}]")
            for left, value in body.items():
                right, comment = value
                if comment:
                    lines.append(f"# {keyd_escape_comment_text(comment)}")
                lines.append(f"{left} = {right}")
            lines.append("")
        if len(lines) <= 8:
            return ""
        return chr(10).join(lines)

    def on_preview_keyd_conf(self, _button):
        content = self.build_keyd_conf()
        if not content:
            self.message("No hay keyd.conf para exportar","Añade algún atajo keyd antes de exportar.",Gtk.MessageType.INFO)
            return
        chooser = Gtk.FileChooserDialog(title="Exportar keyd.conf",transient_for=self,action=Gtk.FileChooserAction.SAVE,)
        chooser.add_buttons("Cancelar",Gtk.ResponseType.CANCEL,"Exportar",Gtk.ResponseType.OK)
        chooser.set_do_overwrite_confirmation(True)
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", self.layout_name()).strip("_") or "uok"
        chooser.set_current_name(safe + ".keyd.conf")
        response = chooser.run()
        filename = chooser.get_filename()
        chooser.destroy()
        if response == Gtk.ResponseType.OK and filename:
            Path(filename).write_text(content, encoding="utf-8")
            self.message("keyd.conf exportado", filename)
    def draw_keyboard(self):
        for child in list(self.keyboard_box.get_children()):
            self.keyboard_box.remove(child)
        for row in LAYOUT_ROWS:
            h = self.make_row_box()
            self.keyboard_box.pack_start(h, False, False, 0)
            for code, fallback, width in row:
                self.add_key_button(h, code, fallback, width)
        additional_items = []
        if self.function_key_row:
            additional_items.extend(self.function_key_row)
        function_codes = {c for c, _, _ in self.function_key_row}
        additional_items.extend((code, code, 1.2)
            for code in self.extra_keys
            if code not in function_codes)
        if additional_items:
            sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
            self.keyboard_box.pack_start(sep, False, False, 4)
            label = Gtk.Label(label="Teclas adicionales")
            label.set_xalign(0)
            label.get_style_context().add_class("uok-additional-title")
            self.keyboard_box.pack_start(label, False, False, 0)
            max_width = self.max_main_keyboard_width()
            for row in self.wrap_key_items(additional_items, max_width):
                h = self.make_row_box()
                self.keyboard_box.pack_start(h, False, False, 0)
                for code, fallback, width in row:
                    self.add_key_button(h, code, fallback, width)
        self.keyboard_box.show_all()

    def add_key_button(self, row_box, code, fallback, width):
        btn = Gtk.Button()
        btn.get_style_context().add_class("uok-keycap")
        btn.set_size_request(self.key_pixel_width(width), 54)
        btn.set_vexpand(False)
        btn.set_hexpand(False)
        btn.set_label(self.button_label(code, fallback))
        btn.set_tooltip_text(" / ".join(self.symbols_for_code(code)))
        btn.connect("clicked", self.on_edit_key, code)
        row_box.pack_start(btn, False, False, 0)
        self.buttons[code] = (btn, fallback)

    def button_label(self, code, fallback):
        return keycap_symbol(self.symbols_for_code(code), fallback)

    def refresh_button(self, code):
        if code in self.buttons:
            btn, fallback = self.buttons[code]
            btn.set_label(self.button_label(code, fallback))
            btn.set_tooltip_text(" / ".join(self.symbols_for_code(code)))

    def on_edit_key(self, _button, code):
        dialog = EditKeyDialog(self, code, self.entry_values_for_code(code))
        try:
            while True:
                response = dialog.run()
                if response != Gtk.ResponseType.OK:
                    break
                try:
                    new_symbols = normalized_symbols_for_values(dialog.values())
                except ValueError as exc:
                    error_dialog = Gtk.MessageDialog(
                        transient_for=dialog,
                        flags=Gtk.DialogFlags.MODAL,
                        message_type=Gtk.MessageType.ERROR,
                        buttons=Gtk.ButtonsType.OK,
                        text="Valor de tecla no válido",
                    )
                    error_dialog.format_secondary_text(str(exc))
                    error_dialog.run()
                    error_dialog.destroy()
                    continue
                base = self.base_for_code(code)
                if new_symbols == base:
                    self.changes.pop(code, None)
                else:
                    self.changes[code] = new_symbols
                self.refresh_button(code)
                break
        finally:
            dialog.destroy()

    def on_add_physical_key(self, _button):
        dialog = CaptureKeyDialog(self, self.keycode_to_name)
        response = dialog.run()
        code = dialog.detected
        dialog.destroy()
        if response == Gtk.ResponseType.OK and code:
            known = {c for row in LAYOUT_ROWS for c, _, _ in row}
            known.update(c for c, _, _ in self.function_key_row)
            if code not in known and code not in self.extra_keys:
                self.extra_keys.append(code)
                self.draw_keyboard()
            elif code in self.buttons:
                self.refresh_button(code)

    def layout_name(self):
        return self.name_entry.get_text().strip() or "Mi teclado visual"

    def build_xkb(self, name):
        lines = ['default partial alphanumeric_keys modifier_keys','xkb_symbols "basic" {',f'    include "{self.include_name}"',
            f'    name[Group1] = "{name}";','',]
        for code in sorted(self.changes):
            symbols = self.symbols_for_code(code)
            lines.append(f'    key <{code}> {{ [ {", ".join(symbols[:4])} ] }};')
        lines.extend(['};', ''])
        return "\n".join(lines)

    def message(self, title, text, kind=Gtk.MessageType.INFO):
        dialog = Gtk.MessageDialog(transient_for=self,flags=0,message_type=kind,buttons=Gtk.ButtonsType.OK,text=title)
        dialog.format_secondary_text(text)
        dialog.run()
        dialog.destroy()

    def warn_if_no_changes(self):
        if self.changes or self.keyd_shortcuts or self.keyd_block_all_shortcuts:
            return True
        self.message("No hay cambios", "Edita alguna tecla o añade algún atajo keyd antes de guardar.")
        return False

    def on_export_xkb(self, _button):
        if not self.warn_if_no_changes():
            return
        name = self.layout_name()
        content = self.build_xkb(name)
        chooser = Gtk.FileChooserDialog(title="Exportar archivo XKB",transient_for=self,action=Gtk.FileChooserAction.SAVE)
        chooser.add_buttons("Cancelar", Gtk.ResponseType.CANCEL, "Exportar", Gtk.ResponseType.OK)
        chooser.set_do_overwrite_confirmation(True)
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_") or "uok-layout"
        chooser.set_current_name(safe + ".xkb")
        response = chooser.run()
        filename = chooser.get_filename()
        chooser.destroy()
        if response == Gtk.ResponseType.OK and filename:
            Path(filename).write_text(content, encoding="utf-8")
            self.message("XKB exportado", filename)

    def on_save(self, _button):
        if not self.warn_if_no_changes():
            return
        name = self.layout_name()
        content = self.build_xkb(name)
        temp_dir = Path(tempfile.mkdtemp(prefix="uok-visual-"))
        xkb_file = temp_dir / "symbols"
        xkb_file.write_text(content, encoding="utf-8")
        local_uok = Path(__file__).resolve().with_name("uok")
        if local_uok.exists():
            cmd = [sys.executable, str(local_uok), "import", "--name", name, "--xkb", str(xkb_file)]
        else:
            cmd = ["uok", "import", "--name", name, "--xkb", str(xkb_file)]
        keyd_content = self.build_keyd_conf()
        if keyd_content:
            keyd_file = temp_dir / "keyd.conf"
            keyd_file.write_text(keyd_content, encoding="utf-8")
            cmd.extend(["--keyd", str(keyd_file)])
        result = subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        raw_lines = []
        for part in (result.stdout, result.stderr):
            if part:
                raw_lines.extend(line.strip() for line in part.splitlines() if line.strip())
        wayland_notice = any(
            "GNOME Wayland" in line or "logging out" in line or "cerrar sesión" in line
            for line in raw_lines
        )
        # Avoid showing the same Wayland warning twice: uok import may print it,
        # and the editor also needs to present it as a localized dialog.
        filtered_lines = [
            line for line in raw_lines
            if not ("GNOME Wayland" in line and ("logging out" in line or "cerrar sesión" in line))
        ]
        combined = "\n".join(filtered_lines)
        if result.returncode != 0:
            self.message("No se pudo importar", combined or "Error desconocido", Gtk.MessageType.ERROR)
            return
        if wayland_notice:
            base = combined or "Configuración importada correctamente."
            self.message(
                "Layout importado - GNOME Wayland",
                base + "\n\nSi es la primera vez que usas esta distribución en GNOME Wayland, cierra sesión y vuelve a entrar antes de probarla.",
                Gtk.MessageType.WARNING,
            )
        else:
            self.message("Layout importado", combined or "Configuración importada correctamente.")

def main():
    css = b"""
    .uok-sidebar {background-color: @theme_base_color; border: 1px solid @borders; border-radius: 12px; padding: 8px;}
    .uok-sidebar-title {font-weight: bold; font-size: 115%;}
    .uok-source-section-box {background-color: alpha(@theme_fg_color, 0.06); border-radius: 6px;}
    .uok-source-section {font-weight: bold; opacity: 0.9;}
    .uok-source-separator {background-color: alpha(@theme_fg_color, 0.28); border-radius: 999px;}
    .uok-source-description {font-size: 85%; opacity: 0.65;}
    .uok-keyboard-frame {background-color: @theme_base_color; border: 1px solid @borders; border-radius: 12px; padding: 0px;}
    .uok-keyd-frame {background-color: @theme_base_color; border: 1px solid @borders; border-radius: 12px; padding: 0px;}
    .uok-keyd-help {opacity: 0.75;}
    .uok-keyd-scroll {border: 1px solid alpha(@theme_fg_color, 0.18); border-radius: 6px; background-color: alpha(@theme_base_color, 0.65); padding: 2px;}
    .uok-keyd-chip {border: 1px solid alpha(@theme_fg_color, 0.20); border-radius: 999px; background-color: alpha(@theme_fg_color, 0.06);}
    .uok-keyd-chip:selected {background-color: @theme_selected_bg_color; color: @theme_selected_fg_color;}
    .uok-keyd-section-title {font-weight: bold;}
    .uok-additional-title {margin-top: 4px; margin-bottom: 2px; font-weight: bold;}
    paned > separator {background-color: transparent; border: none; box-shadow: none;}
    paned.horizontal > separator {min-width: 6px;}
    paned.vertical > separator {min-height: 6px;}
    paned > separator:hover {background-color: transparent;}
    GtkPaned > separator,
    paned > separator {background-color: transparent; border: none; box-shadow: none;}
    GtkPaned.horizontal > separator,
    paned.horizontal > separator {min-width: 6px;}
    GtkPaned.vertical > separator,
    paned.vertical > separator {min-height: 6px;}
    GtkPaned > separator:hover,
    paned > separator:hover {background-color: transparent;}
    .uok-keycap {padding-top: 2px; padding-bottom: 2px; padding-left: 8px; padding-right: 8px;}
    """
    provider = Gtk.CssProvider()
    provider.load_from_data(css)
    screen = Gdk.Screen.get_default()
    if screen is not None:
        Gtk.StyleContext.add_provider_for_screen(screen,provider,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,)
    UokLayoutEditor()
    Gtk.main()

if __name__ == "__main__":
    main()