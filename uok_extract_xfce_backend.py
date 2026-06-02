#!/usr/bin/env python3
from pathlib import Path
import py_compile

IND = Path("teclado-indicador.py")
XFCE = Path("uok_backends/xfce.py")

START = "# UOK desktop compatibility overrides: XFCE input sources"
END = "# UOK desktop compatibility override: Add from settings"

REPLACEMENT = """# UOK XFCE backend delegation
try:
    from uok_backends.xfce import install as uok_install_xfce_backend
    uok_install_xfce_backend(__import__(__name__))
except Exception as exc:
    print(f'UOK XFCE backend disabled: {exc}')

"""

text = IND.read_text(encoding="utf-8")

if "uok_backends.xfce" in text:
    raise SystemExit("XFCE ya parece delegado; no modifico nada.")

start = text.find(START)
end = text.find(END, start)

if start == -1:
    raise SystemExit("No encontré inicio XFCE.")
if end == -1 or end <= start:
    raise SystemExit("No encontré final XFCE.")

block = text[start:end]

required = [
    "UOK desktop compatibility overrides: XFCE input sources",
    "UOK desktop compatibility overrides: XFCE input sources v2",
    "UOK desktop compatibility overrides: XFCE input sources v3",
    "UOK XFCE compatibility override v5",
    "UOK XFCE compatibility override v6",
    "def uok_is_xfce",
    "def uok_v5_is_xfce",
    "def uok_v6_is_xfce",
]

missing = [x for x in required if x not in block]
if missing:
    raise SystemExit("Bloque XFCE incompleto. Faltan: " + ", ".join(missing))

forbidden = [
    "uok_hide_kde_ibus_native_menu()",
    "ocultar_menu_xfce()",
    "sincronizar_estado_al_arrancar()",
    "uok_main_menu = crear_menu()",
]

bad = [x for x in forbidden if x in block]
if bad:
    raise SystemExit("El bloque XFCE capturaría arranque: " + ", ".join(bad))

Path("uok_backends").mkdir(exist_ok=True)

module = (
    "#!/usr/bin/env python3\n"
    '"""XFCE compatibility backend for UrOwnKeyboard."""\n\n'
    "_XFCE_CODE = " + repr(block) + "\n\n\n"
    "def install(app):\n"
    "    namespace = app.__dict__\n"
    "    exec(_XFCE_CODE, namespace, namespace)\n"
)

IND.with_suffix(".py.bak-xfce-backend").write_text(text, encoding="utf-8")
XFCE.write_text(module, encoding="utf-8")

new_text = text[:start] + REPLACEMENT + text[end:]
IND.write_text(new_text, encoding="utf-8")

py_compile.compile(str(IND), doraise=True)
py_compile.compile(str(XFCE), doraise=True)

print("OK: bloque XFCE extraído.")
print(f"teclado-indicador.py: {len(text.splitlines())} -> {len(new_text.splitlines())} líneas")
print(f"uok_backends/xfce.py: {len(module.splitlines())} líneas")
