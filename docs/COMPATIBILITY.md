# Compatibilidad y sesiones gráficas

## Alcance

UrOwnKeyboard utiliza **XKB** para definir caracteres y, cuando se configura, **keyd** para remapeos físicos. No todos los servidores gráficos ni los escritorios gestionan el cambio de fuente de entrada del mismo modo.

La matriz describe **rutas implementadas en el código**, no una batería de pruebas completada en todas las distribuciones/versiones:

| Sesión | Ruta de integración | Precaución |
| --- | --- | --- |
| GNOME X11 | `gsettings`, XKB, indicador, extensión local | El indicador depende del entorno de panel/extensiones; comprobar cada versión de GNOME |
| GNOME Wayland | Fuente `gsettings` + registro XKB de sistema + extensión GNOME Shell | **Experimental**; cambios privilegiados y posible cierre de sesión para cargar el layout nuevo |
| KDE Plasma X11 | Fuentes de `kxkbrc` y XKB; adaptación de preferencias y bandeja | El panel y el soporte de indicador varían; puede modificar archivos del usuario |
| XFCE X11 | `xfconf`, XKB y ajustes de teclado | Puede intentar retirar componentes nativos del panel |
| MATE X11 | Fuentes XKB/GNOME/IBus y ajustes de teclado | Ocultación de indicadores según configuración |
| Cinnamon X11 | Ajustes Cinnamon y fuentes XKB/GNOME | Integración del panel dependiente del entorno |
| LXQt X11 | Configuración LXQt, XKB e integración de panel | Puede reescribir `panel.conf` y crear copias de seguridad |
| Otros Wayland | Ninguna ruta nativa equivalente a GNOME garantizada | No asumas compatibilidad porque exista `DISPLAY`/Xwayland |

La extensión local declara compatibilidad con GNOME Shell **42–49**, pero esa declaración no sustituye pruebas funcionales en cada versión.

## Por qué GNOME Wayland necesita tratamiento especial

En X11, UOK puede aplicar una distribución XKB usando `setxkbmap` y `xkbcomp`. En GNOME Wayland el compositor administra las fuentes de entrada; aplicar XKB sobre Xwayland no basta para el teclado de aplicaciones Wayland nativas.

Ruta implementada para un perfil UOK:

1. Importación: copia y valida el archivo XKB; guarda un perfil JSON de UOK.
2. Registro: copia los símbolos a `/usr/share/X11/xkb/symbols/<id>` y registra la disposición en las reglas XKB, incluyendo `evdev.xml` y `evdev` cuando corresponde.
3. GNOME: añade una fuente `('xkb', '<id>')` a `org.gnome.desktop.input-sources`.
4. Activación: solicita a GNOME Shell/GSettings el cambio de fuente; sincroniza Xwayland como mejor esfuerzo y aplica la configuración opcional `keyd`.
5. Presentación: el indicador muestra un único perfil UOK y oculta su fuente técnica duplicada de la lista.

Las operaciones de registro XKB del sistema necesitan privilegios, generalmente mediante `pkexec` o `sudo`; **una activación inmediata puede parecer correcta en el estado guardado, pero no estar cargada en GNOME Shell hasta cerrar sesión**.

## Fuentes del sistema y perfiles propios

- **Fuente de sistema:** distribución que ya figura en la configuración del escritorio; no pertenece a UOK y no debe borrarse mediante `uok delete`.
- **Perfil UOK:** entrada JSON bajo `~/.config/teclado-indicador/profiles/` con referencia a un archivo XKB y, opcionalmente, un archivo `keyd.conf`.
- **Registro técnico en GNOME Wayland:** representación de sistema creada por UOK para que GNOME reconozca el perfil; normalmente no se muestra como segundo elemento en el menú.

`uok list` permite distinguir entre **System sources** y **UOK profiles**. El marcador `+ wayland` indica metadatos de registro; no certifica que todas las aplicaciones hayan recargado el mapa.

## Indicadores nativos

Los módulos de integración intentan ocultar componentes nativos (GNOME, IBus, Plasma, XFCE o LXQt) para evitar indicadores duplicados. Pueden alterar configuraciones del panel del usuario y el resultado depende de versiones y extensiones instaladas. Consulta [operaciones y copias de seguridad](OPERATIONS.md) antes de instalar o actualizar.

## Límites conocidos

- No hay soporte Wayland genérico para KDE, Sway, Hyprland u otros compositores mediante la ruta GNOME.
- Las fuentes IBus **no XKB** no se pueden activar desde la CLI, y el adaptador GNOME Wayland del indicador las bloquea.
- La activación en Xwayland es un intento de sincronización, no una prueba de que un cliente haya adoptado la disposición.
- La limpieza de registros antiguos debe inspeccionarse con `--dry-run` antes de ejecutarse.
