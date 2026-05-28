# UrOwnKeyboard

**UrOwnKeyboard** es un gestor de distribuciones de teclado personalizadas para Linux.

Permite importar, crear, activar y eliminar configuraciones basadas en **XKB** y, opcionalmente, asociarlas con archivos **keyd.conf** para remapeos físicos y atajos avanzados.

Incluye:

- un núcleo portable de terminal llamado `uok`;
- un indicador gráfico compatible con AppIndicator/Ayatana;
- un editor visual de distribuciones XKB;
- integración con GNOME, KDE Plasma, XFCE y Cinnamon en sesiones X11;
- ocultación de menús nativos de teclado en escritorios soportados;
- soporte opcional para `keyd`.

## Estado actual

UrOwnKeyboard está orientado principalmente a escritorios Linux que usen **XKB en sesión X11**.

| Escritorio | Estado | Integración |
|---|---|---|
| GNOME | Soportado | `gsettings` y extensión GNOME para ocultar el selector nativo |
| KDE Plasma | Soportado en X11 | `kxkbrc`, `setxkbmap`, IBus y ocultación de menús nativos |
| XFCE | Soportado | `xfconf-query`, `setxkbmap` e IBus cuando está presente |
| Cinnamon | Soportado en X11 | IBus, `setxkbmap` y fallback de icono en bandeja |
| MATE | En desarrollo | previsto para X11 |
| LXQt | En desarrollo | previsto para X11 |
| Wayland | En desarrollo | no garantizado todavía |
| Otros | Experimental | puede funcionar si soportan XKB y AppIndicator/Ayatana |

### Notas por escritorio

En **GNOME**, UrOwnKeyboard usa las fuentes de entrada de `gsettings` y puede ocultar el indicador nativo mediante la extensión GNOME incluida.

En **KDE Plasma**, UrOwnKeyboard lee distribuciones desde `~/.config/kxkbrc`, `setxkbmap -query` e IBus. También puede ocultar los menús nativos de Plasma relacionados con teclado e input method para dejar visible sólo el menú de UrOwnKeyboard.

En **XFCE**, UrOwnKeyboard puede leer distribuciones añadidas desde la configuración de teclado de XFCE, `setxkbmap` e IBus cuando está presente.

En **Cinnamon**, UrOwnKeyboard lee fuentes desde IBus y `setxkbmap`. También incluye un fallback para que el indicador sea visible en la bandeja de Cinnamon cuando AppIndicator no se muestra correctamente.

En **Wayland**, el soporte todavía está en desarrollo. `keyd` puede seguir siendo útil porque trabaja a nivel de dispositivo, pero el cambio de distribución mediante `setxkbmap` no es fiable en Wayland. El soporte Wayland necesitará integración específica por escritorio o compositor.

## Instalación rápida

Copia y pega esto en una terminal:

```bash
sudo apt update
sudo apt install -y git build-essential python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1 zenity gkbd-capplet gnome-shell-extension-appindicator x11-xkb-utils fonts-noto-core fonts-noto-extra

if ! command -v keyd >/dev/null 2>&1; then
    cd /tmp
    rm -rf keyd
    git clone https://github.com/rvaiya/keyd.git
    cd keyd
    make
    sudo make install
    sudo systemctl enable --now keyd
fi

cd "$HOME"
rm -rf UrOwnKeyboard
git clone https://github.com/Oriesu/UrOwnKeyboard.git
cd UrOwnKeyboard
chmod +x install.sh uninstall.sh uok
./install.sh
```

Después de instalar, se recomienda cerrar sesión y volver a entrar. En GNOME también puedes recargar la sesión con `Alt + F2`, escribir `r` y pulsar `Enter` cuando estés en X11.

Si el indicador nativo de GNOME sigue apareciendo, ejecuta:

```bash
gnome-extensions enable hide-input-source@teclado-indicador
```

## Funciones

- Importar distribuciones XKB desde archivos.
- Crear distribuciones nuevas desde un editor visual.
- Usar como base cualquier distribución del sistema, una fuente añadida en la configuración del sistema o una configuración propia de UrOwnKeyboard.
- Editar teclas visualmente, incluyendo niveles normal, Shift, AltGr y AltGr+Shift.
- Exportar la distribución editada como archivo XKB.
- Importar directamente la distribución editada en UrOwnKeyboard.
- Asociar opcionalmente un archivo `keyd.conf`.
- Aplicar automáticamente XKB + keyd.
- Listar configuraciones importadas.
- Eliminar configuraciones importadas.
- Mostrar la configuración activa.
- Mostrar el `keyd.conf` activo.
- Mostrar una vista completa de la configuración activa.
- Usar un menú gráfico en la barra superior o panel.
- Abrir la configuración de teclado del sistema desde el menú gráfico.
- Ocultar indicadores nativos de teclado en GNOME, KDE Plasma y Cinnamon cuando corresponde.
- Iniciarse automáticamente al iniciar sesión.

## Qué hace el instalador

El script `install.sh`:

- instala las dependencias necesarias;
- copia `teclado-indicador.py` a `~/.local/bin/`;
- copia `uok` a `~/.local/bin/`;
- copia `uok-layout-editor.py` a `~/.local/bin/`;
- copia los módulos del editor visual `uok_xkb_symbols.py` y `uok_xkb_sources.py` a `~/.local/bin/`;
- instala el helper de keyd en `/usr/local/sbin/keyd-aplicar-conf`;
- crea una regla sudoers limitada para aplicar configuraciones keyd;
- crea la entrada de autoinicio en `~/.config/autostart/teclado-indicador.desktop`;
- instala la extensión local de GNOME si detecta GNOME Shell;
- inicia el indicador gráfico al terminar.

Si la instalación se detiene durante la configuración de sudoers, comprueba que no haya archivos antiguos con permisos incorrectos en `/etc/sudoers.d/`.

Puedes verificarlo con:

```bash
sudo visudo -c
```

La regla propia de UrOwnKeyboard se comprueba con:

```bash
sudo visudo -cf /etc/sudoers.d/teclado-indicador-keyd
```

## Uso gráfico

Después de instalar, aparecerá un nuevo indicador en la barra superior o panel.

Desde el menú puedes usar:

```text
Show full configuration
New configuration…
  ├─ Open visual editor…
  ├─ Import configuration…
  └─ Add from settings…
Delete configuration…
Reload list
```

La opción **New configuration…** agrupa las formas de añadir o crear configuraciones nuevas:

- **Open visual editor…** abre el editor visual de distribuciones.
- **Import configuration…** importa un archivo XKB existente.
- **Add from settings…** abre directamente el apartado de teclado de la configuración del sistema para añadir distribuciones del sistema.

`Add from settings…` se adapta al escritorio:

- en GNOME abre la configuración de teclado/región de GNOME;
- en XFCE abre `xfce4-keyboard-settings`;
- en Cinnamon intenta abrir `cinnamon-settings keyboard`;
- en KDE intenta abrir el módulo de teclado de System Settings.

La interfaz del programa está en inglés para facilitar su uso en sistemas internacionales, pero este README está en español.

## Editor visual

El editor visual permite crear una distribución nueva partiendo de otra ya existente.

Puede abrirse desde el menú gráfico:

```text
New configuration… → Open visual editor…
```

También puede abrirse desde terminal:

```bash
uok editor
```

Alias disponibles:

```bash
uok open-editor
uok visual-editor
uok layout-editor
```

En la barra lateral del editor aparecen tres secciones:

```text
UOK
Added to system
Others
```

- **UOK** muestra configuraciones propias de UrOwnKeyboard.
- **Added to system** muestra distribuciones añadidas en la configuración del sistema.
- **Others** muestra distribuciones disponibles en XKB.

La sección **Added to system** puede leer distribuciones desde:

- GNOME `org.gnome.desktop.input-sources`;
- XFCE `xfconf-query`;
- KDE Plasma `~/.config/kxkbrc`;
- IBus `preload-engines` y `engines-order`;
- `setxkbmap -query`.

Esto permite que el editor visual use como base teclados añadidos desde la configuración del sistema en GNOME, KDE Plasma, XFCE y Cinnamon.

El editor permite:

```text
- buscar distribuciones;
- elegir una distribución base;
- editar teclas visualmente;
- añadir teclas físicas adicionales;
- exportar la distribución como archivo XKB;
- importarla directamente en UrOwnKeyboard.
```

Algunas distribuciones usan símbolos Unicode poco comunes. Para mejorar su visualización se recomienda tener instaladas las fuentes Noto:

```bash
sudo apt install -y fonts-noto-core fonts-noto-extra
```

## Uso por terminal

UrOwnKeyboard instala el comando `uok`.

Ver ayuda general:

```bash
uok --help
```

Ver ayuda de un comando concreto:

```bash
uok import --help
uok activate --help
uok delete --help
uok editor --help
```

Listar configuraciones:

```bash
uok list
```

Importar una configuración sólo con XKB:

```bash
uok import --name "Mi teclado" --xkb ./mi_teclado
```

Importar una configuración con XKB + keyd:

```bash
uok import --name "Mi teclado" --xkb ./mi_teclado --keyd ./mi_teclado.keyd.conf
```

Abrir el editor visual:

```bash
uok editor
```

Activar una configuración:

```bash
uok activate mi_teclado
```

Eliminar una configuración:

```bash
uok delete mi_teclado
```

Ver la configuración activa:

```bash
uok current
```

Ver el `keyd.conf` asociado a la configuración activa:

```bash
uok show-keyd
```

## Importar una configuración desde el menú

Selecciona:

```text
New configuration… → Import configuration…
```

El programa pedirá:

```text
1. Configuration name
2. XKB / symbols file
3. Optional keyd.conf file
```

Selecciona sólo el archivo XKB si únicamente quieres cambiar la distribución de teclado.

Selecciona también un archivo `keyd.conf` si quieres aplicar remapeos físicos o atajos personalizados.

## Crear una configuración visualmente

Selecciona:

```text
New configuration… → Open visual editor…
```

Después:

```text
1. Elige una distribución base en la barra lateral.
2. Edita las teclas que quieras cambiar.
3. Ponle un nombre a la configuración.
4. Usa "Export XKB…" si sólo quieres guardar el archivo.
5. Usa "Import into UOK…" si quieres añadirla directamente a UrOwnKeyboard.
```

Las configuraciones importadas aparecerán después en el menú del indicador.

Si el menú ya estaba abierto o no se actualiza automáticamente, usa:

```text
Reload list
```

## Añadir distribuciones desde la configuración del sistema

Selecciona:

```text
New configuration… → Add from settings…
```

Esto abre el apartado de teclado de la configuración del sistema.

Desde ahí puedes añadir distribuciones del sistema. Después aparecerán en el editor visual dentro de:

```text
Added to system
```

## Mostrar configuración completa

La opción:

```text
Show full configuration
```

abre el visor gráfico XKB y muestra información del perfil activo, incluyendo su archivo `keyd.conf` asociado si existe.

Esto permite ver en una sola acción:

```text
- la distribución XKB activa;
- el perfil activo de UrOwnKeyboard;
- el archivo XKB usado;
- el archivo keyd.conf asociado;
- el contenido del keyd.conf activo.
```

## Recarga automática de la interfaz gráfica

Cuando se usa `uok import` o `uok delete`, el indicador gráfico se recarga automáticamente si está abierto.

Esto permite que las configuraciones nuevas o eliminadas aparezcan en el menú sin tener que reiniciar manualmente el indicador.

También puedes forzar la recarga desde el menú:

```text
Reload list
```

## Compatibilidad

El núcleo `uok` puede funcionar en cualquier entorno Linux compatible con XKB y keyd.

El indicador gráfico usa AppIndicator/Ayatana. En Cinnamon se incluye un fallback de bandeja para evitar problemas de visibilidad del indicador.

El editor visual usa GTK 3 y herramientas XKB como `setxkbmap` y `xkbcomp`.

UrOwnKeyboard está probado principalmente en sesiones **X11**. En Wayland, cada escritorio o compositor gestiona el teclado de forma distinta, por lo que el soporte todavía está en desarrollo.

### X11 y Wayland

En X11, UrOwnKeyboard puede usar `setxkbmap`, XKB clásico y los mecanismos gráficos de cada escritorio para detectar y activar distribuciones.

En Wayland:

- `setxkbmap` no debe considerarse fiable;
- `keyd` puede seguir siendo útil como capa inferior;
- GNOME Wayland, KDE Wayland, Sway, Hyprland y otros necesitarán tratamiento específico;
- el soporte está marcado como **en desarrollo**.

Para el estado actual del proyecto, se recomienda usar una sesión **X11**.


## Estructura del proyecto

```text
UrOwnKeyboard/
├── teclado-indicador.py
├── uok
├── uok-layout-editor.py
├── uok_xkb_sources.py
├── uok_xkb_symbols.py
├── install.sh
├── uninstall.sh
├── helpers/
│   └── keyd-aplicar-conf
├── gnome-extension/
│   ├── metadata.json
│   └── extension.js
└── README.md
```

## Desinstalación

```bash
cd "$HOME/UrOwnKeyboard"
./uninstall.sh
```

Esto elimina:

```text
- el indicador instalado;
- el comando uok instalado;
- el editor visual instalado;
- la entrada de autoinicio;
- la extensión local de GNOME;
- el helper de keyd;
- la regla sudoers.
```

No borra tus configuraciones importadas en:

```text
~/.config/teclado-indicador/
~/.xkb/symbols/
```

## Seguridad

UrOwnKeyboard no ejecuta scripts importados.

Sólo gestiona:

```text
- archivos XKB / symbols;
- archivos keyd.conf.
```

Para aplicar configuraciones keyd sin pedir contraseña cada vez, el instalador crea una regla sudoers limitada al helper:

```text
/usr/local/sbin/keyd-aplicar-conf
```

Ese helper sólo acepta archivos situados dentro de la carpeta de configuración del usuario.

## Limitaciones

- Tras instalar, puede ser necesario cerrar sesión y volver a entrar para que el escritorio detecte correctamente el indicador y las integraciones.
- UrOwnKeyboard está orientado actualmente a sesiones X11.
- Wayland está en desarrollo y no está garantizado todavía.
- MATE y LXQt están en desarrollo.
- Algunas distribuciones XKB usan símbolos Unicode poco comunes. Si se ven cuadrados en el editor visual, instala fuentes adicionales como `fonts-noto-extra`.

## Hoja de ruta

Próximos objetivos:

- limpiar internamente la detección de distribuciones para evitar duplicar lógica por escritorio;
- completar soporte para MATE;
- completar soporte para LXQt;
- diseñar soporte Wayland separado del flujo X11;
- mejorar la documentación por escritorio;
- añadir pruebas de instalación y release.