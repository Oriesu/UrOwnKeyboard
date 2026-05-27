#!/usr/bin/env bash
set -euo pipefail

if [ ! -f "teclado-indicador.py" ] || [ ! -f "install.sh" ] || [ ! -f "uok" ]; then
  echo "Ejecuta este script desde la raíz del repositorio UrOwnKeyboard."
  exit 1
fi

cp -n teclado-indicador.py teclado-indicador.py.bak.$(date +%Y%m%d-%H%M%S)
cp -n install.sh install.sh.bak.$(date +%Y%m%d-%H%M%S)

cat > uok-layout-editor.py <<'PY'
#!/usr/bin/env python3
import json
import re
import shlex
import subprocess
import tempfile
import unicodedata
from pathlib import Path

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk

HOME = Path.home()
CONFIG = HOME / ".config" / "teclado-indicador"
DRAFTS = CONFIG / "generated-layouts"
DRAFTS.mkdir(parents=True, exist_ok=True)

BASE_INCLUDE = "es(basic)"

SPECIAL_KEYSYMS = [
    "NoSymbol", "Escape", "Tab", "ISO_Left_Tab", "BackSpace", "Return", "Delete", "Insert",
    "Home", "End", "Prior", "Next", "Up", "Down", "Left", "Right", "Pause", "Print",
    "Scroll_Lock", "Num_Lock", "Caps_Lock", "Menu", "Super_L", "Super_R", "Alt_L", "Alt_R",
    "Control_L", "Control_R", "Shift_L", "Shift_R", "ISO_Level3_Shift", "space",
]

CHAR_KEYSYMS = {
    " ": "space", "!": "exclam", '"': "quotedbl", "#": "numbersign", "$": "dollar",
    "%": "percent", "&": "ampersand", "'": "apostrophe", "(": "parenleft", ")": "parenright",
    "*": "asterisk", "+": "plus", ",": "comma", "-": "minus", ".": "period", "/": "slash",
    ":": "colon", ";": "semicolon", "<": "less", "=": "equal", ">": "greater", "?": "question",
    "@": "at", "[": "bracketleft", "\\": "backslash", "]": "bracketright", "^": "asciicircum",
    "_": "underscore", "`": "grave", "{": "braceleft", "|": "bar", "}": "braceright", "~": "asciitilde",
    "¡": "exclamdown", "¿": "questiondown", "ñ": "ntilde", "Ñ": "Ntilde", "ç": "ccedilla", "Ç": "Ccedilla",
    "á": "aacute", "é": "eacute", "í": "iacute", "ó": "oacute", "ú": "uacute", "ü": "udiaeresis",
    "Á": "Aacute", "É": "Eacute", "Í": "Iacute", "Ó": "Oacute", "Ú": "Uacute", "Ü": "Udiaeresis",
    "€": "EuroSign", "º": "masculine", "ª": "ordfeminine", "·": "periodcentered", "¬": "notsign",
}

ROWS = [
    [("TLDE", "º"), ("AE01", "1"), ("AE02", "2"), ("AE03", "3"), ("AE04", "4"), ("AE05", "5"), ("AE06", "6"), ("AE07", "7"), ("AE08", "8"), ("AE09", "9"), ("AE10", "0"), ("AE11", "'"), ("AE12", "¡"), ("BKSP", "BackSpace")],
    [("TAB", "Tab"), ("AD01", "Q"), ("AD02", "W"), ("AD03", "E"), ("AD04", "R"), ("AD05", "T"), ("AD06", "Y"), ("AD07", "U"), ("AD08", "I"), ("AD09", "O"), ("AD10", "P"), ("AD11", "`"), ("AD12", "+")],
    [("CAPS", "Caps Lock"), ("AC01", "A"), ("AC02", "S"), ("AC03", "D"), ("AC04", "F"), ("AC05", "G"), ("AC06", "H"), ("AC07", "J"), ("AC08", "K"), ("AC09", "L"), ("AC10", "Ñ"), ("AC11", "´"), ("RTRN", "Return")],
    [("LFSH", "Shift L"), ("LSGT", "<"), ("AB01", "Z"), ("AB02", "X"), ("AB03", "C"), ("AB04", "V"), ("AB05", "B"), ("AB06", "N"), ("AB07", "M"), ("AB08", ","), ("AB09", "."), ("AB10", "-"), ("RTSH", "Shift R")],
    [("LCTL", "Control L"), ("LWIN", "Super L"), ("LALT", "Alt L"), ("SPCE", "Space"), ("RALT", "Level3"), ("RWIN", "Super R"), ("MENU", "Menu"), ("RCTL", "Control R")],
]

NON_CHAR_DEFAULTS = {
    "ESC": ["Escape"], "TAB": ["Tab"], "BKSP": ["BackSpace"], "RTRN": ["Return"],
    "CAPS": ["Caps_Lock"], "LFSH": ["Shift_L"], "RTSH": ["Shift_R"], "LCTL": ["Control_L"],
    "RCTL": ["Control_R"], "LALT": ["Alt_L"], "RALT": ["ISO_Level3_Shift"], "LWIN": ["Super_L"],
    "RWIN": ["Super_R"], "MENU": ["Menu"], "SPCE": ["space"],
}

WIDTHS = {"BKSP": 2, "TAB": 1.5, "CAPS": 1.8, "RTRN": 2, "LFSH": 2.2, "RTSH": 2.2, "SPCE": 6}


def safe_id(name: str) -> str:
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()
    return name or "custom_layout"


def token_to_keysym(token: str) -> str:
    token = token.strip()
    if not token:
        return "NoSymbol"
    if token.startswith("XKB:"):
        return token[4:].strip() or "NoSymbol"
    if token in SPECIAL_KEYSYMS:
        return token
    if len(token) == 1:
        ch = token
        if "a" <= ch <= "z" or "A" <= ch <= "Z":
            return ch
        if "0" <= ch <= "9":
            return ch
        if ch in CHAR_KEYSYMS:
            return CHAR_KEYSYMS[ch]
        return "U%04X" % ord(ch)
    # Permite escribir directamente keysyms como Greek_OMEGA, dead_acute, XF86AudioMute, etc.
    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", token):
        return token
    raise ValueError(f"No sé convertir {token!r}. Usa un carácter, un keysym XKB o XKB:nombre_keysym.")


def key_line(code: str, values: list[str]) -> str:
    keysyms = [token_to_keysym(v) for v in values]
    while keysyms and keysyms[-1] == "NoSymbol":
        keysyms.pop()
    if not keysyms:
        keysyms = ["NoSymbol"]
    return f"    key <{code}> {{ [ {', '.join(keysyms)} ] }};"


def generate_xkb(layout_name: str, edits: dict[str, list[str]]) -> str:
    lines = [
        'default partial alphanumeric_keys modifier_keys',
        'xkb_symbols "basic" {',
        f'    include "{BASE_INCLUDE}"',
        f'    name[Group1] = "{layout_name}";',
        '',
    ]
    for code in sorted(edits):
        values = edits[code]
        if any(v.strip() for v in values):
            lines.append(key_line(code, values))
    lines.append('};')
    lines.append('')
    return "\n".join(lines)


class KeyDialog(Gtk.Dialog):
    def __init__(self, parent, code, label, values):
        super().__init__(title=f"Edit <{code}> {label}", transient_for=parent, flags=0)
        self.add_button("Cancel", Gtk.ResponseType.CANCEL)
        self.add_button("Save", Gtk.ResponseType.OK)
        self.set_default_size(420, 240)
        box = self.get_content_area()
        grid = Gtk.Grid(column_spacing=10, row_spacing=8, margin=12)
        box.add(grid)
        self.entries = []
        labels = ["Normal", "Shift", "AltGr / Level3", "AltGr + Shift"]
        for i, text in enumerate(labels):
            grid.attach(Gtk.Label(label=text, xalign=0), 0, i, 1, 1)
            entry = Gtk.Entry()
            entry.set_placeholder_text("carácter, keysym o XKB:keysym")
            if i < len(values):
                entry.set_text(values[i])
            grid.attach(entry, 1, i, 1, 1)
            self.entries.append(entry)
        combo = Gtk.ComboBoxText()
        combo.append_text("Insertar keysym especial…")
        for sym in SPECIAL_KEYSYMS:
            combo.append_text(sym)
        combo.set_active(0)
        combo.connect("changed", self.on_combo_changed)
        grid.attach(combo, 1, 4, 1, 1)
        help_text = Gtk.Label(label="Para keysyms avanzados escribe, por ejemplo: dead_acute, Greek_OMEGA o XKB:XF86AudioMute", xalign=0)
        help_text.set_line_wrap(True)
        grid.attach(help_text, 0, 5, 2, 1)
        self.show_all()

    def on_combo_changed(self, combo):
        text = combo.get_active_text()
        if text and text != "Insertar keysym especial…":
            self.entries[0].set_text(text)
            combo.set_active(0)

    def get_values(self):
        return [e.get_text() for e in self.entries]


class LayoutEditor(Gtk.Window):
    def __init__(self):
        super().__init__(title="UrOwnKeyboard layout editor")
        self.set_default_size(1180, 520)
        self.set_border_width(12)
        self.connect("destroy", Gtk.main_quit)
        self.edits = {}
        self.buttons = {}

        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(main)

        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        main.pack_start(top, False, False, 0)
        top.pack_start(Gtk.Label(label="Nombre:"), False, False, 0)
        self.name_entry = Gtk.Entry()
        self.name_entry.set_text("Mi teclado")
        top.pack_start(self.name_entry, True, True, 0)
        save_btn = Gtk.Button(label="Guardar e importar")
        save_btn.connect("clicked", self.on_save_import)
        top.pack_start(save_btn, False, False, 0)
        export_btn = Gtk.Button(label="Exportar XKB")
        export_btn.connect("clicked", self.on_export)
        top.pack_start(export_btn, False, False, 0)

        hint = Gtk.Label(label="Haz clic en una tecla para asignar hasta 4 niveles: normal, Shift, AltGr y AltGr+Shift. Deja campos vacíos para heredar la distribución española base.", xalign=0)
        hint.set_line_wrap(True)
        main.pack_start(hint, False, False, 0)

        grid = Gtk.Grid(column_spacing=4, row_spacing=4)
        main.pack_start(grid, True, True, 0)
        for r, row in enumerate(ROWS):
            c = 0
            for code, label in row:
                button = Gtk.Button(label=label)
                button.set_hexpand(True)
                button.set_vexpand(True)
                button.set_size_request(int(56 * WIDTHS.get(code, 1)), 52)
                button.connect("clicked", self.on_key_clicked, code, label)
                span = max(1, int(WIDTHS.get(code, 1)))
                grid.attach(button, c, r, span, 1)
                self.buttons[code] = button
                c += span

    def on_key_clicked(self, _button, code, label):
        defaults = self.edits.get(code, ["", "", "", ""])
        dialog = KeyDialog(self, code, label, defaults)
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            values = dialog.get_values()
            self.edits[code] = values
            visible = "/".join([v for v in values if v.strip()][:2]) or label
            self.buttons[code].set_label(f"{label}\n{visible}")
        dialog.destroy()

    def build_xkb(self):
        name = self.name_entry.get_text().strip() or "Mi teclado"
        return generate_xkb(name, self.edits), name

    def show_error(self, message):
        dialog = Gtk.MessageDialog(transient_for=self, flags=0, message_type=Gtk.MessageType.ERROR, buttons=Gtk.ButtonsType.CLOSE, text="UrOwnKeyboard")
        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()

    def show_info(self, message):
        dialog = Gtk.MessageDialog(transient_for=self, flags=0, message_type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.OK, text="UrOwnKeyboard")
        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()

    def on_export(self, _button):
        try:
            xkb, name = self.build_xkb()
            chooser = Gtk.FileChooserDialog(title="Exportar XKB", parent=self, action=Gtk.FileChooserAction.SAVE)
            chooser.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Save", Gtk.ResponseType.OK)
            chooser.set_current_name(safe_id(name))
            if chooser.run() == Gtk.ResponseType.OK:
                Path(chooser.get_filename()).write_text(xkb, encoding="utf-8")
                self.show_info("Archivo XKB exportado.")
            chooser.destroy()
        except Exception as exc:
            self.show_error(str(exc))

    def on_save_import(self, _button):
        try:
            xkb, name = self.build_xkb()
            draft = DRAFTS / safe_id(name)
            draft.write_text(xkb, encoding="utf-8")
            result = subprocess.run(["uok", "import", "--name", name, "--xkb", str(draft)], text=True, capture_output=True)
            if result.returncode != 0:
                self.show_error(result.stderr.strip() or result.stdout.strip() or "No se pudo importar el layout.")
                return
            self.show_info((result.stdout.strip() or "Layout importado.") + "\n\nActívalo desde el indicador o con uok activate.")
        except Exception as exc:
            self.show_error(str(exc))


if __name__ == "__main__":
    win = LayoutEditor()
    win.show_all()
    Gtk.main()
PY
chmod +x uok-layout-editor.py

python3 - <<'PY'
from pathlib import Path
p = Path('install.sh')
s = p.read_text()
if 'uok-layout-editor.py' not in s:
    marker = 'cp uok "$HOME/.local/bin/uok"'
    idx = s.find(marker)
    if idx == -1:
        raise SystemExit('No encuentro el punto para modificar install.sh')
    end = s.find('\n', idx)
    insert = '\ncp uok-layout-editor.py "$HOME/.local/bin/uok-layout-editor.py"\nchmod +x "$HOME/.local/bin/uok-layout-editor.py"'
    s = s[:end] + insert + s[end:]
    p.write_text(s)

p = Path('teclado-indicador.py')
s = p.read_text()
if 'crear_layout_visual' not in s:
    marker = 'def importar_configuracion(_)'
    idx = s.find(marker)
    if idx == -1:
        raise SystemExit('No encuentro importar_configuracion en teclado-indicador.py')
    func = '''def crear_layout_visual(_):\n    editor = HOME / ".local" / "bin" / "uok-layout-editor.py"\n    if not editor.exists():\n        editor = Path(__file__).resolve().parent / "uok-layout-editor.py"\n    run(f'{shlex.quote(str(editor))} || notify-send "Keyboard" "Could not open layout editor"')\n\n'''
    s = s[:idx] + func + s[idx:]

if 'Create layout visually' not in s:
    marker = 'item_import = Gtk.MenuItem(label="Import configuration…")'
    idx = s.find(marker)
    if idx == -1:
        raise SystemExit('No encuentro el menú de importación en teclado-indicador.py')
    insert = '''item_create = Gtk.MenuItem(label="Create layout visually…")\n    item_create.connect("activate", crear_layout_visual)\n    menu.append(item_create)\n    '''
    s = s[:idx] + insert + s[idx:]
    p.write_text(s)
PY

echo "Listo. Archivos modificados/creados:"
echo "  - uok-layout-editor.py"
echo "  - install.sh"
echo "  - teclado-indicador.py"
echo
echo "Prueba rápida:"
echo "  python3 -m py_compile uok-layout-editor.py teclado-indicador.py uok"
echo "  ./uok-layout-editor.py"
