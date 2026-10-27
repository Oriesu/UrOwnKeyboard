# Instalación, mantenimiento y recuperación

## Antes de instalar

`install.sh` está pensado para Debian/Ubuntu y derivadas con `apt` y `systemd`, y **modifica el sistema**. Entre otras operaciones:

- Instala dependencias GTK, Ayatana/AppIndicator, XKB y herramientas de escritorio mediante `apt`.
- Instala `keyd` si no existe (intenta `apt` y, como alternativa, compilarlo desde GitHub), e inicia/habilita el servicio.
- Copia el helper privilegiado a `/usr/local/sbin/keyd-aplicar-conf` y crea `/etc/sudoers.d/teclado-indicador-keyd`, que permite a tu usuario ejecutar **ese helper concreto sin contraseña**.
- Copia ejecutables Python a `~/.local/bin/`, crea autoinicio y, si detecta GNOME Shell, instala una extensión del usuario.
- Puede ocultar indicadores nativos o modificar preferencias de panel al iniciar el indicador.

**Revisa el código del instalador y haz una copia de seguridad de la configuración de teclado**. No uses el proyecto en una sesión crítica sin tener otro método para recuperar la entrada.

## Instalación y comprobaciones

```bash
git clone https://github.com/Oriesu/UrOwnKeyboard.git
cd UrOwnKeyboard
./install.sh
```

El instalador ya ejecuta comprobaciones de compilación Python y `uok doctor --system-only`. Después de instalar:

```bash
uok --help
uok list
uok doctor
sudo visudo -cf /etc/sudoers.d/teclado-indicador-keyd
systemctl is-active keyd
```

En GNOME puedes comprobar el estado de la extensión con:

```bash
gnome-extensions list --enabled
gnome-extensions enable hide-input-source@urownkeyboard
```

Si la extensión acaba de instalarse, cierra sesión y entra de nuevo.

## Dónde se guardan los datos

| Ruta | Uso |
| --- | --- |
| `~/.config/teclado-indicador/profiles/*.json` | Metadatos de perfiles UOK |
| `~/.xkb/symbols/<id>` | Símbolos XKB importados |
| `~/.config/teclado-indicador/keyd/*.conf` | Archivos keyd asociados |
| `~/.config/teclado-indicador/current-profile.json` | Última configuración registrada |
| `~/.config/autostart/teclado-indicador.desktop` | Autoinicio del indicador |
| `~/.cache/urownkeyboard/indicator.log` | Salida y errores del iniciador |
| `/etc/keyd/default.conf` | Configuración activa de keyd, modificada por el helper |
| `/usr/share/X11/xkb/symbols/<id>` y reglas `evdev*` | Archivos de sistema registrados para GNOME Wayland |

Si vas a probar cambios, respalda tus perfiles, `~/.xkb/`, las preferencias del panel y, en GNOME Wayland, el registro XKB de sistema **antes** de modificarlo.

## Qué hacer si algo no funciona

### El indicador no aparece

```bash
ls -l ~/.config/autostart/teclado-indicador.desktop
cat ~/.cache/urownkeyboard/indicator.log
uok doctor
```

El instalador crea `~/.local/bin/uok-indicator-start`. Inícialo manualmente desde tu sesión gráfica para obtener diagnósticos si el autoinicio falla.

### No funciona la distribución creada en GNOME Wayland

1. Inspecciona las fuentes: `gsettings get org.gnome.desktop.input-sources sources`.
2. Comprueba si el perfil figura en `uok list` y ejecuta `uok doctor`.
3. Si acabas de importar una disposición XKB nueva, **cierra sesión y vuelve a entrar**.
4. Si hay duplicados técnicos tras migraciones, usa primero `uok cleanup-wayland --dry-run`; confirma la lista antes de ejecutarlo.

Evita borrar a mano entradas arbitrarias de `/usr/share/X11/xkb`; puedes inutilizar el registro usado por otras distribuciones.

### `keyd` no aplica o deja remapeos

```bash
uok show-keyd
systemctl is-active keyd
sudo journalctl -u keyd -n 80 --no-pager
sudo cat /etc/keyd/default.conf
```

Al activar una fuente XKB normal, UOK intenta dejar una configuración keyd **neutral**; el servicio puede seguir activo. Si el archivo no es neutral, revisa las advertencias de `uok activate` y el helper.

### El registro XKB está dañado

```bash
uok doctor --system-only
```

El comando `uok doctor --repair` puede reinstalar el paquete XKB del sistema y sobrescribir cambios; inspecciona las copias de seguridad y las consecuencias antes de usarlo.

**No ejecutes indiscriminadamente** `uok_recover_gnome_wayland.sh`: ese script de recuperación experimental restablece fuentes GNOME concretas (`es` y `de`) y podría sobrescribir tus preferencias actuales.

## Desinstalación

Desde la carpeta del repositorio:

```bash
./uninstall.sh
```

El desinstalador retira los binarios instalados, autoinicio, extensión GNOME local, helper y regla sudoers. **No borra las configuraciones importadas** de `~/.config/teclado-indicador/`. **No garantiza revertir** modificaciones de indicadores del escritorio, la configuración global de keyd ni los layouts XKB de sistema previamente registrados para GNOME Wayland.

Antes de desinstalar, revisa `uok cleanup-wayland --dry-run` y elimina los perfiles propios que ya no quieras mientras UOK todavía pueda gestionar sus registros. Conserva tus datos si prevés reinstalar.

## Resumen de comprobaciones sin efectos destructivos

```bash
uok list
uok current
uok show-keyd
uok doctor --system-only
uok cleanup-wayland --dry-run
```

Consulta también la [referencia CLI](CLI.md) y las [limitaciones de compatibilidad](COMPATIBILITY.md).
