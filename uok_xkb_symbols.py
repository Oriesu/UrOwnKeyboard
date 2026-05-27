#!/usr/bin/env python3
import re

import gi
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk


COMBINING_DOTTED_CIRCLE = "\u25cc"


KEYSYM_TO_DISPLAY = {
    "NoSymbol": "",
    "VoidSymbol": "",
    "space": "Space",

    # Alias XKB frecuentes.
    "ordmasculine": "º",
    "masculine": "º",
    "ordfeminine": "ª",
    "feminine": "ª",

    # Comillas angulares: se ven con varias grafías según layout/parser.
    "guillemetleft": "«",
    "guillemetright": "»",
    "gillemetleft": "«",
    "gillemetright": "»",

    # Teclas muertas comunes.
    "dead_acute": "´",
    "dead_grave": "`",
    "dead_circumflex": "^",
    "dead_diaeresis": "¨",
    "dead_tilde": "~",
    "dead_macron": "¯",
    "dead_breve": "˘",
    "dead_abovedot": "˙",
    "dead_abovering": "˚",
    "dead_doubleacute": "˝",
    "dead_caron": "ˇ",
    "dead_cedilla": "¸",
    "dead_ogonek": "˛",
    "dead_iota": "ͅ",
    "dead_voiced_sound": "゛",
    "dead_semivoiced_sound": "゜",
    # Dead keys usadas en layouts como Amharic/Ethiopic.
    # Se muestran como tecla muerta visible, no como nombre largo.
    "dead_a": "◌a",
    "dead_A": "◌A",
    "dead_e": "◌e",
    "dead_E": "◌E",
    "dead_i": "◌i",
    "dead_I": "◌I",
    "dead_o": "◌o",
    "dead_O": "◌O",
    "dead_u": "◌u",
    "dead_U": "◌U",
    "dead_schwa": "◌ə",
    "dead_SCHWA": "◌Ə",
    "dead_belowdot": "◌̣",
    "dead_belowcomma": "◌̦",

    # Signos con nombres XKB que GDK no siempre convierte como esperamos.
    "guillemotleft": "«",
    "guillemotright": "»",
    "leftdoublequotemark": "“",
    "rightdoublequotemark": "”",
    "singlelowquotemark": "‚",
    "doublelowquotemark": "„",

    # Combinantes. Se muestran con círculo punteado para que sean visibles.
    "combining_tilde": COMBINING_DOTTED_CIRCLE + "\u0303",
    "combining_belowdot": COMBINING_DOTTED_CIRCLE + "\u0323",
    "combining_acute": COMBINING_DOTTED_CIRCLE + "\u0301",
    "combining_grave": COMBINING_DOTTED_CIRCLE + "\u0300",
    "combining_hook": COMBINING_DOTTED_CIRCLE + "\u0309",
    "combining_abovedot": COMBINING_DOTTED_CIRCLE + "\u0307",
    "combining_diaeresis": COMBINING_DOTTED_CIRCLE + "\u0308",
    "combining_macron": COMBINING_DOTTED_CIRCLE + "\u0304",
    "combining_circumflex": COMBINING_DOTTED_CIRCLE + "\u0302",
    "combining_caron": COMBINING_DOTTED_CIRCLE + "\u030c",
    "combining_breve": COMBINING_DOTTED_CIRCLE + "\u0306",
    "combining_ringabove": COMBINING_DOTTED_CIRCLE + "\u030a",
    "combining_cedilla": COMBINING_DOTTED_CIRCLE + "\u0327",
    "combining_ogonek": COMBINING_DOTTED_CIRCLE + "\u0328",

    # Teclas especiales.
    "Tab": "Tab",
    "ISO_Left_Tab": "⇤",
    "BackSpace": "⌫",
    "Return": "Enter",
    "Escape": "Esc",
    "Delete": "Del",
    "Insert": "Ins",
    "Home": "Home",
    "End": "End",
    "Prior": "PgUp",
    "Next": "PgDn",
    "Left": "←",
    "Right": "→",
    "Up": "↑",
    "Down": "↓",
    "Caps_Lock": "Caps",
    "Shift_L": "Shift",
    "Shift_R": "Shift",
    "Control_L": "Ctrl",
    "Control_R": "Ctrl",
    "Alt_L": "Alt",
    "Alt_R": "Alt",
    "Super_L": "Super",
    "Super_R": "Super",
    "Menu": "Menu",
    "ISO_Level3_Shift": "AltGr",
    "Multi_key": "Compose",
}


DISPLAY_TO_KEYSYM = {
    value: key
    for key, value in KEYSYM_TO_DISPLAY.items()
    if value
}

DISPLAY_TO_KEYSYM.update({
    "º": "ordmasculine",
    "ª": "ordfeminine",
    "«": "guillemotleft",
    "»": "guillemotright",

    "◌a": "dead_a",
    "◌A": "dead_A",
    "◌e": "dead_e",
    "◌E": "dead_E",
    "◌i": "dead_i",
    "◌I": "dead_I",
    "◌o": "dead_o",
    "◌O": "dead_O",
    "◌u": "dead_u",
    "◌U": "dead_U",
    "◌ə": "dead_schwa",
    "◌Ə": "dead_SCHWA",
    "◌̣": "dead_belowdot",
    "◌̦": "dead_belowcomma",

    "´": "dead_acute",
    "`": "dead_grave",
    "^": "dead_circumflex",
    "¨": "dead_diaeresis",
    "~": "dead_tilde",
    "¯": "dead_macron",
    "˘": "dead_breve",
    "˙": "dead_abovedot",
    "˚": "dead_abovering",
    "˝": "dead_doubleacute",
    "ˇ": "dead_caron",
    "¸": "dead_cedilla",
    "˛": "dead_ogonek",

    "«": "guillemotleft",
    "»": "guillemotright",

    COMBINING_DOTTED_CIRCLE + "\u0303": "combining_tilde",
    COMBINING_DOTTED_CIRCLE + "\u0323": "combining_belowdot",
    COMBINING_DOTTED_CIRCLE + "\u0301": "combining_acute",
    COMBINING_DOTTED_CIRCLE + "\u0300": "combining_grave",
    COMBINING_DOTTED_CIRCLE + "\u0309": "combining_hook",
    COMBINING_DOTTED_CIRCLE + "\u0307": "combining_abovedot",
    COMBINING_DOTTED_CIRCLE + "\u0308": "combining_diaeresis",
    COMBINING_DOTTED_CIRCLE + "\u0304": "combining_macron",
    COMBINING_DOTTED_CIRCLE + "\u0302": "combining_circumflex",
    COMBINING_DOTTED_CIRCLE + "\u030c": "combining_caron",
    COMBINING_DOTTED_CIRCLE + "\u0306": "combining_breve",
    COMBINING_DOTTED_CIRCLE + "\u030a": "combining_ringabove",
    COMBINING_DOTTED_CIRCLE + "\u0327": "combining_cedilla",
    COMBINING_DOTTED_CIRCLE + "\u0328": "combining_ogonek",
})


def unicode_keysym_to_char(sym):
    # XKB puede usar U10578, U010578 o U00010578.
    # Aceptamos ceros a la izquierda y hasta 8 dígitos.
    if not re.fullmatch(r"U[0-9A-Fa-f]{4,8}", sym or ""):
        return None

    try:
        codepoint = int(sym[1:], 16)
    except Exception:
        return None

    if codepoint <= 0 or codepoint > 0x10FFFF:
        return None

    try:
        return chr(codepoint)
    except Exception:
        return None


def maybe_visible_combining_char(ch):
    if not ch:
        return ch

    codepoint = ord(ch)

    # Rangos principales de marcas combinantes Unicode.
    is_combining = (
        0x0300 <= codepoint <= 0x036F or
        0x1AB0 <= codepoint <= 0x1AFF or
        0x1DC0 <= codepoint <= 0x1DFF or
        0x20D0 <= codepoint <= 0x20FF or
        0xFE20 <= codepoint <= 0xFE2F
    )

    if is_combining:
        return COMBINING_DOTTED_CIRCLE + ch

    return ch


def keysym_to_text(sym):
    sym = (sym or "").strip()

    if sym in KEYSYM_TO_DISPLAY:
        return KEYSYM_TO_DISPLAY[sym]

    if not sym:
        return ""

    ch = unicode_keysym_to_char(sym)
    if ch is not None:
        return maybe_visible_combining_char(ch)

    keyval = Gdk.keyval_from_name(sym)

    if keyval:
        codepoint = Gdk.keyval_to_unicode(keyval)
        if codepoint:
            try:
                return maybe_visible_combining_char(chr(codepoint))
            except Exception:
                pass

    if len(sym) == 1:
        return sym

    return sym


def text_to_keysym(value):
    value = (value or "").strip()

    if not value:
        return None

    if value == " ":
        return "space"

    if value in DISPLAY_TO_KEYSYM:
        return DISPLAY_TO_KEYSYM[value]

    # Si el usuario pega un combinante visible como ◌̃, quitamos el círculo.
    if value.startswith(COMBINING_DOTTED_CIRCLE) and len(value) == 2:
        value = value[1]

    # Si escribe directamente un keysym válido, se respeta.
    direct_keyval = Gdk.keyval_from_name(value)
    if direct_keyval:
        return value

    if len(value) == 1:
        keyval = Gdk.unicode_to_keyval(ord(value))
        name = Gdk.keyval_name(keyval)

        if name:
            return name

        return f"U{ord(value):04X}"

    return value


# --- UOK generic keysym fixes ---

try:
    COMBINING_DOTTED_CIRCLE
except NameError:
    COMBINING_DOTTED_CIRCLE = "\u25cc"


# Alias y keysyms especiales que no siempre resuelve GDK.
KEYSYM_TO_DISPLAY.update({
    "NoSymbol": "",
    "VoidSymbol": "",
    "space": "Space",

    # Ordinales / alias frecuentes.
    "ordmasculine": "º",
    "masculine": "º",
    "ordfeminine": "ª",
    "feminine": "ª",

    # Guillemets con grafías distintas.
    "guillemotleft": "«",
    "guillemotright": "»",
    "guillemetleft": "«",
    "guillemetright": "»",
    "gillemetleft": "«",
    "gillemetright": "»",

    # Modificadores XKB compactos.
    "ISO_Level3_Shift": "AltGr",
    "ISO_Level3_Latch": "AltGr⇧",
    "ISO_Level3_Lock": "AltGr⇩",
    "ISO_Level5_Shift": "Lvl5",
    "ISO_Level5_Latch": "Lvl5⇧",
    "ISO_Level5_Lock": "Lvl5⇩",

    # Dead keys usadas por layouts etiópicos/amárico.
    "dead_a": "◌a",
    "dead_A": "◌A",
    "dead_e": "◌e",
    "dead_E": "◌E",
    "dead_i": "◌i",
    "dead_I": "◌I",
    "dead_o": "◌o",
    "dead_O": "◌O",
    "dead_u": "◌u",
    "dead_U": "◌U",
    "dead_schwa": "◌ə",
    "dead_SCHWA": "◌Ə",
    "dead_belowdot": "◌̣",
    "dead_belowcomma": "◌̦",
})

DISPLAY_TO_KEYSYM.update({
    "º": "ordmasculine",
    "ª": "ordfeminine",
    "«": "guillemotleft",
    "»": "guillemotright",

    "AltGr⇧": "ISO_Level3_Latch",
    "AltGr⇩": "ISO_Level3_Lock",
    "Lvl5": "ISO_Level5_Shift",
    "Lvl5⇧": "ISO_Level5_Latch",
    "Lvl5⇩": "ISO_Level5_Lock",

    "◌a": "dead_a",
    "◌A": "dead_A",
    "◌e": "dead_e",
    "◌E": "dead_E",
    "◌i": "dead_i",
    "◌I": "dead_I",
    "◌o": "dead_o",
    "◌O": "dead_O",
    "◌u": "dead_u",
    "◌U": "dead_U",
    "◌ə": "dead_schwa",
    "◌Ə": "dead_SCHWA",
    "◌̣": "dead_belowdot",
    "◌̦": "dead_belowcomma",
})


_BRAILLE_DOT_DISPLAY = {
    1: "⠁",
    2: "⠂",
    3: "⠄",
    4: "⡀",
    5: "⠈",
    6: "⠐",
    7: "⠠",
    8: "⢀",
    9: "B9",
    10: "B10",
}

for _dot, _display in _BRAILLE_DOT_DISPLAY.items():
    KEYSYM_TO_DISPLAY[f"braille_dot_{_dot}"] = _display
    DISPLAY_TO_KEYSYM[_display] = f"braille_dot_{_dot}"


def unicode_keysym_to_char(sym):
    sym = (sym or "").strip()

    # Formato XKB tipo U10578, U010578, U00010578.
    if re.fullmatch(r"U[0-9A-Fa-f]{4,8}", sym):
        try:
            codepoint = int(sym[1:], 16)
        except Exception:
            return None

        if 0 < codepoint <= 0x10FFFF:
            try:
                return chr(codepoint)
            except Exception:
                return None

    # Formato XKB/GDK tipo 0x1000029, 0x1000b85.
    # En X11, los keysyms Unicode suelen ser 0x01000000 | codepoint.
    if re.fullmatch(r"0x[0-9A-Fa-f]+", sym):
        try:
            value = int(sym, 16)
        except Exception:
            return None

        if 0x01000000 <= value <= 0x0110FFFF:
            codepoint = value & 0x00FFFFFF
        else:
            codepoint = value

        if 0 < codepoint <= 0x10FFFF:
            try:
                return chr(codepoint)
            except Exception:
                return None

    return None


def maybe_visible_combining_char(ch):
    if not ch:
        return ch

    if len(ch) != 1:
        return ch

    codepoint = ord(ch)

    is_combining = (
        0x0300 <= codepoint <= 0x036F or
        0x1AB0 <= codepoint <= 0x1AFF or
        0x1DC0 <= codepoint <= 0x1DFF or
        0x20D0 <= codepoint <= 0x20FF or
        0xFE20 <= codepoint <= 0xFE2F
    )

    if is_combining:
        return COMBINING_DOTTED_CIRCLE + ch

    return ch


def keysym_to_text(sym):
    sym = (sym or "").strip()

    if sym in KEYSYM_TO_DISPLAY:
        return KEYSYM_TO_DISPLAY[sym]

    if not sym:
        return ""

    ch = unicode_keysym_to_char(sym)
    if ch is not None:
        return maybe_visible_combining_char(ch)

    keyval = Gdk.keyval_from_name(sym)

    if keyval:
        codepoint = Gdk.keyval_to_unicode(keyval)
        if codepoint:
            try:
                return maybe_visible_combining_char(chr(codepoint))
            except Exception:
                pass

    if len(sym) == 1:
        return sym

    return sym


def text_to_keysym(value):
    value = (value or "").strip()

    if not value:
        return None

    if value == " ":
        return "space"

    if value in DISPLAY_TO_KEYSYM:
        return DISPLAY_TO_KEYSYM[value]

    # Si el usuario pega un combinante visible como ◌̃, quitamos el círculo.
    if value.startswith(COMBINING_DOTTED_CIRCLE) and len(value) == 2:
        value = value[1]

    # Si escribe directamente un keysym válido, se respeta.
    direct_keyval = Gdk.keyval_from_name(value)
    if direct_keyval:
        return value

    if len(value) == 1:
        keyval = Gdk.unicode_to_keyval(ord(value))
        name = Gdk.keyval_name(keyval)

        if name:
            return name

        return f"U{ord(value):04X}"

    return value


# --- UOK unicode display final override ---

def unicode_keysym_to_char(sym):
    sym = (sym or "").strip()

    # Formato XKB tipo U10578, U010578, U00010578.
    if re.fullmatch(r"U[0-9A-Fa-f]{4,8}", sym):
        try:
            codepoint = int(sym[1:], 16)
        except Exception:
            return None

        if 0 < codepoint <= 0x10FFFF:
            try:
                return chr(codepoint)
            except Exception:
                return None

    # Formato XKB/GDK tipo 0x1000029, 0x1000b85.
    # Unicode keysym = 0x01000000 | codepoint.
    if re.fullmatch(r"0x[0-9A-Fa-f]+", sym):
        try:
            value = int(sym, 16)
        except Exception:
            return None

        if 0x01000000 <= value <= 0x0110FFFF:
            codepoint = value & 0x00FFFFFF
        else:
            return None

        if 0 < codepoint <= 0x10FFFF:
            try:
                return chr(codepoint)
            except Exception:
                return None

    return None


def maybe_visible_combining_char(ch):
    if not ch:
        return ch

    if len(ch) != 1:
        return ch

    codepoint = ord(ch)

    is_combining = (
        0x0300 <= codepoint <= 0x036F or
        0x1AB0 <= codepoint <= 0x1AFF or
        0x1DC0 <= codepoint <= 0x1DFF or
        0x20D0 <= codepoint <= 0x20FF or
        0xFE20 <= codepoint <= 0xFE2F
    )

    if is_combining:
        return COMBINING_DOTTED_CIRCLE + ch

    return ch


def keysym_to_text(sym):
    sym = (sym or "").strip()

    if sym in KEYSYM_TO_DISPLAY:
        return KEYSYM_TO_DISPLAY[sym]

    if not sym:
        return ""

    ch = unicode_keysym_to_char(sym)
    if ch is not None:
        return maybe_visible_combining_char(ch)

    keyval = Gdk.keyval_from_name(sym)

    if keyval:
        codepoint = Gdk.keyval_to_unicode(keyval)
        if codepoint:
            try:
                return maybe_visible_combining_char(chr(codepoint))
            except Exception:
                pass

    if len(sym) == 1:
        return sym

    return sym


def text_to_keysym(value):
    value = (value or "").strip()

    if not value:
        return None

    if value == " ":
        return "space"

    if value in DISPLAY_TO_KEYSYM:
        return DISPLAY_TO_KEYSYM[value]

    if value.startswith(COMBINING_DOTTED_CIRCLE) and len(value) == 2:
        value = value[1]

    direct_keyval = Gdk.keyval_from_name(value)
    if direct_keyval:
        return value

    if len(value) == 1:
        keyval = Gdk.unicode_to_keyval(ord(value))
        name = Gdk.keyval_name(keyval)

        if name:
            return name

        return f"U{ord(value):04X}"

    return value
