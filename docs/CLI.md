# Referencia de comandos (CLI)

La utilidad instalada es `uok` (también puedes ejecutar `python3 ./uok` desde el repositorio). Usa `uok --help` o `uok <comando> -h` para consultar la sintaxis exacta de tu versión.

## Comandos disponibles

| Comando | Efecto |
| --- | --- |
| `uok list` | Lista las fuentes de sistema detectadas y los perfiles propios; marca el perfil registrado como actual. |
| `uok import --name N --xkb R [--keyd K]` | Copia un archivo XKB a `~/.xkb/symbols/`, valida su compilación, guarda el perfil y opcionalmente copia una configuración keyd. |
| `uok activate ID` | Activa el perfil indicado o una fuente de sistema XKB detectada. Admite ID/nombre; para fuentes del sistema también puede admitir índice o etiqueta. |
| `uok delete ID` | Elimina un perfil UOK y sus archivos gestionados; intenta retirar su registro de sistema en GNOME Wayland. **No elimina fuentes normales del sistema.** |
| `uok current` | Muestra el JSON del perfil o fuente registrados como activos por UOK. |
| `uok show-keyd` | Muestra el contenido del `keyd.conf` asociado al perfil registrado, si existe. |
| `uok restore` | Vuelve a aplicar el perfil UOK guardado; sin perfil propio, intenta desactivar los remapeos keyd. **No reconstruye automáticamente los ajustes previos del escritorio.** |
| `uok editor` | Abre el editor visual GTK en una sesión gráfica. |
| `uok cleanup-wayland [--dry-run] [-y]` | Localiza y, con confirmación, elimina registros XKB UOK huérfanos/antiguos de GNOME Wayland. |
| `uok doctor [--system-only] [--no-fail] [--repair] [-y]` | Diagnostica el registro XKB, compilación, sesión, GNOME, IBus y keyd. |

Alias implementados: `cleanup-orphans` para `cleanup-wayland`, y `open-editor`, `visual-editor`, `layout-editor` para `editor`.

**Comandos ya no disponibles:** `current-keyd` (usa `show-keyd`) y `show` (usa `current` y `show-keyd`).

## Crear y activar un perfil

```bash
uok import --name "Mi teclado" --xkb ./mi_teclado.xkb
uok list
uok activate mi_teclado
uok current
```

Si el nombre ya corresponde a otro archivo, UOK puede generar un ID con sufijo numérico. Si detecta una configuración idéntica, informa de que ya existe sin importarla otra vez. **Utiliza el ID devuelto por `uok list`**; no asumas que el nombre visible y el ID son iguales.

Para remapeos físicos opcionales:

```bash
uok import --name "Mi teclado" --xkb ./mi_teclado.xkb --keyd ./atajos.keyd.conf
uok activate mi_teclado
uok show-keyd
```

El archivo XKB debe compilar; si falla la validación, la importación se cancela. Si falla `keyd` durante la activación, XKB puede quedar aplicado **sin** los remapeos deseados, y el comando emite una advertencia.

## Fuentes normales del sistema

```bash
uok list
uok activate es
```

Solo se pueden activar fuentes **XKB** desde la CLI; las fuentes IBus no XKB pueden mostrarse pero su activación no está implementada en esta ruta. Al activar una fuente normal, UOK intenta neutralizar `keyd`.

## GNOME Wayland

Cuando se importa un perfil personalizado en GNOME Wayland, UOK intenta registrarlo como fuente de GNOME y disposición XKB del sistema. Este paso puede requerir contraseña de administrador. La fuente técnica se filtra del listado visible para evitar duplicar el perfil UOK.

```bash
uok list
uok activate mi_teclado
uok cleanup-wayland --dry-run
```

Si es la primera instalación de ese layout, puede ser necesario **cerrar sesión y volver a entrar**. Los intentos de sincronizar Xwayland son de mejor esfuerzo y no garantizan que todas las aplicaciones adopten inmediatamente la nueva distribución.

## Limpieza de duplicados y perfiles antiguos

```bash
uok cleanup-wayland --dry-run
uok cleanup-wayland
```

Revisa las rutas/IDs propuestos antes de confirmar. `-y` omite la pregunta; no lo uses sin comprobar primero el resultado de `--dry-run`.

## Diagnóstico

```bash
uok doctor
uok doctor --system-only
```

- `--system-only`: examina el registro y la compilación XKB sin el diagnóstico de sesión.
- `--no-fail`: imprime los problemas detectados sin devolver un código de error.
- `--repair`: **intenta reinstalar el paquete XKB de la distribución**; es una acción con efectos sobre el sistema.
- `--yes`: permite continuar con `--repair` sin solicitar confirmación.

Antes de cualquier reparación automática, realiza una copia de tus modificaciones del registro XKB y consulta [operaciones](OPERATIONS.md).
