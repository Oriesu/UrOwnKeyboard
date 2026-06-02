#!/usr/bin/env python3
from pathlib import Path
import ast

ROOT = Path.cwd()
PATH = ROOT / "teclado-indicador.py"

TARGETS = {
    "get_sources",
    "raw_xkb_layout",
    "get_raw_setxkbmap_spec",
    "gnome_source_to_setxkbmap_cmd",
    "verify_gnome_source_applied",
    "expected_source_spec",
    "aplicar_keyd_off_sync",
    "keyd_is_active",
    "activar_gnome_source",
    "activar_profile",
    "aplicar_gnome_source_sync",
    "aplicar_xkb_source_sync",
    "get_gnome_current_source",
    "uok_unique_sources",
    "uok_parse_setxkbmap_sources",
    "uok_parse_xfce_keyboard_sources",
    "uok_parse_gnome_sources",
    "uok_xfconf_get",
    "uok_xfconf_list",
    "uok_source_id_from_layout_variant",
    "uok_split_csv_keep_empty",
    "uok_split_csv_nonempty",
    "uok_desktop_name",
    "uok_is_xfce",
    "uok_is_gnome",
    "uok_is_cinnamon_desktop",
    "uok_mate_settings_is_mate",
    "uok_xfce_panel_array",
    "uok_xfce_set_panel_array",
    "menu_env",
    "run_checked_for_menu",
    "show_error",
    # Importante: solo se recorta si hay una definición conservada ANTES del arranque.
    "ocultar_menu_xfce",
    "abrir_ajustes_teclado",
}

STARTUP_ANCHOR = "uok_hide_kde_ibus_native_menu()"


def find_startup_line(lines):
    for i, line in enumerate(lines, start=1):
        if line.strip() == STARTUP_ANCHOR:
            return i
    raise SystemExit(f"No encontré {STARTUP_ANCHOR!r}; no recorto para no romper el arranque.")


def find_defs(text):
    tree = ast.parse(text)
    defs = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in TARGETS:
            defs.setdefault(node.name, []).append((node.lineno, node.end_lineno))
    return defs


def choose_spans_to_remove(defs, startup_line):
    remove = []
    report = []

    for name, spans in sorted(defs.items()):
        before = [span for span in spans if span[0] < startup_line]

        # Regla segura:
        # - Nunca eliminamos TODAS las definiciones anteriores al arranque.
        # - Conservamos la última definición disponible antes de las llamadas de arranque.
        # - No tocamos definiciones posteriores al arranque, porque pueden formar parte de overrides
        #   que se ejecutan antes de crear el menú.
        if len(before) <= 1:
            continue

        keep = before[-1]
        old = before[:-1]
        for start, end in old:
            remove.append((start, end, name))
        report.append((name, keep, old))

    return remove, report


def remove_spans(lines, spans):
    for start, end, name in sorted(spans, reverse=True):
        a = start - 1
        b = end

        # Borra como mucho una línea en blanco justo anterior.
        if a - 1 >= 0 and lines[a - 1].strip() == "":
            a -= 1

        del lines[a:b]
    return lines


def main():
    if not PATH.exists():
        raise SystemExit("Ejecuta esto en la raíz de UrOwnKeyboard.")

    text = PATH.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    startup_line = find_startup_line(lines)

    defs = find_defs(text)
    remove, report = choose_spans_to_remove(defs, startup_line)

    if not remove:
        print("No hay duplicados seguros anteriores al arranque que borrar.")
        return

    new_lines = remove_spans(lines[:], remove)
    new_text = "".join(new_lines)

    # Validación sintáctica antes de escribir.
    ast.parse(new_text)

    before = len(lines)
    after = len(new_text.splitlines())

    backup = PATH.with_suffix(PATH.suffix + ".bak-trim-step1-safe")
    backup.write_text(text, encoding="utf-8")
    PATH.write_text(new_text, encoding="utf-8")

    print(f"OK: teclado-indicador.py reducido de {before} a {after} líneas.")
    print(f"Eliminadas {before - after} líneas.")
    print(f"Backup: {backup}")
    print()
    print("Definiciones conservadas antes del arranque:")
    for name, keep, old in report:
        old_txt = ", ".join(f"{s}-{e}" for s, e in old)
        print(f"  {name}: queda {keep[0]}-{keep[1]} ; borradas {old_txt}")
    print()
    print("Comprueba con:")
    print("  python3 -m py_compile teclado-indicador.py uok uok_backends/*.py")
    print("  python3 - <<'PY'")
    print("import runpy")
    print("# No ejecuta el indicador completo; solo validación sintáctica ya cubierta por py_compile.")
    print("PY")
    print("  wc -l teclado-indicador.py")


if __name__ == "__main__":
    main()
