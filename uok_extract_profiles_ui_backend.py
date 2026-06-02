#!/usr/bin/env python3
from pathlib import Path
import py_compile

IND = Path("teclado-indicador.py")
PROFILES = Path("uok_backends/profiles.py")

START = "\ndef load_profiles():"
END = "\ndef get_raw_setxkbmap_spec():"

REPLACEMENT = """# UOK profile UI backend delegation
try:
    from uok_backends.profiles import install as uok_install_profiles_backend
    uok_install_profiles_backend(__import__(__name__))
except Exception as exc:
    print(f'UOK profile UI backend disabled: {exc}')

"""

text = IND.read_text(encoding="utf-8")
profiles_text = PROFILES.read_text(encoding="utf-8")

if "uok_install_profiles_backend" in text:
    raise SystemExit("Parece que profile UI ya está delegado; no modifico nada.")

if "\ndef install(app):" in profiles_text:
    raise SystemExit("uok_backends/profiles.py ya tiene install(app). Revisa antes de modificar.")

start_pos = text.find(START)
end_pos = text.find(END, start_pos)

if start_pos == -1:
    raise SystemExit("No encontré inicio del bloque de perfiles.")
if end_pos == -1 or end_pos <= start_pos:
    raise SystemExit("No encontré final del bloque de perfiles.")

# No comerse el salto de línea anterior; conservar el bloque desde def load_profiles.
start = start_pos + 1
block = text[start:end_pos]

required = [
    "def load_profiles",
    "def crear_layout_visual",
    "def importar_configuracion",
    "def borrar_si_seguro",
    "def uok_profile_is_current",
    "def uok_safe_before_delete_profile",
    "def eliminar_configuracion",
    "def get_current_profile",
    "def mostrar_distribucion_actual",
    "def mostrar_configuracion_completa",
    "def abrir_editor_visual",
]

missing = [x for x in required if x not in block]
if missing:
    raise SystemExit("Bloque de perfiles incompleto. Faltan: " + ", ".join(missing))

forbidden = [
    "uok_hide_kde_ibus_native_menu()",
    "ocultar_menu_xfce()",
    "sincronizar_estado_al_arrancar()",
    "uok_main_menu = crear_menu()",
    "def crear_menu",
]

bad = [x for x in forbidden if x in block]
if bad:
    raise SystemExit("El bloque capturaría código de arranque/menú: " + ", ".join(bad))

IND.with_suffix(".py.bak-profiles-ui-backend").write_text(text, encoding="utf-8")
PROFILES.with_suffix(".py.bak-profiles-ui-backend").write_text(profiles_text, encoding="utf-8")

append = (
    "\n\n"
    "# --------------------------------------------------------------------\n"
    "# Profile UI compatibility block extracted from teclado-indicador.py\n"
    "# --------------------------------------------------------------------\n"
    "_PROFILE_UI_CODE = " + repr(block) + "\n\n\n"
    "def install(app):\n"
    "    namespace = app.__dict__\n"
    "    exec(_PROFILE_UI_CODE, namespace, namespace)\n"
)

PROFILES.write_text(profiles_text.rstrip() + append + "\n", encoding="utf-8")

new_text = text[:start] + REPLACEMENT + text[end_pos:]
IND.write_text(new_text, encoding="utf-8")

py_compile.compile(str(IND), doraise=True)
py_compile.compile(str(PROFILES), doraise=True)

print("OK: bloque de perfiles/UI extraído.")
print(f"teclado-indicador.py: {len(text.splitlines())} -> {len(new_text.splitlines())} líneas")
print(f"uok_backends/profiles.py: {len(profiles_text.splitlines())} -> {len(PROFILES.read_text(encoding='utf-8').splitlines())} líneas")
print("Backups:")
print("  teclado-indicador.py.bak-profiles-ui-backend")
print("  uok_backends/profiles.py.bak-profiles-ui-backend")
