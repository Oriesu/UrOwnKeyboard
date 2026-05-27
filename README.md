# UrOwnKeyboard

**UrOwnKeyboard** es un gestor de distribuciones de teclado personalizadas para Linux.

Permite importar, crear, activar y eliminar configuraciones basadas en **XKB** y, opcionalmente, asociarlas con archivos **keyd.conf** para remapeos físicos y atajos avanzados.

Incluye:

- un núcleo portable de terminal llamado `uok`;
- un indicador gráfico compatible con AppIndicator/Ayatana;
- un editor visual de distribuciones XKB;
- una integración específica para GNOME que oculta el menú nativo de fuentes de entrada.
  
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

Después de instalar, cierra sesión y vuelve a entrar para que GNOME con `Alt + F2`, estrbe `r` y pulsa `Enter`.

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
- Usar un menú gráfico en la barra superior.
- Abrir la configuración de teclado del sistema desde el menú gráfico.
- Ocultar el indicador nativo de teclado de GNOME.
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

Después de instalar, aparecerá un nuevo indicador en la barra superior.

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

El indicador gráfico usa AppIndicator/Ayatana, por lo que puede funcionar en GNOME y en otros escritorios compatibles con indicadores de aplicación.

El editor visual usa GTK 3 y herramientas XKB como `setxkbmap` y `xkbcomp`.

La extensión para ocultar el indicador nativo de teclado es específica de GNOME. En otros escritorios, ocultar el indicador nativo dependerá del propio entorno.

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

- Tras instalar, puede ser necesario cerrar sesión y volver a entrar para que GNOME detecte la extensión que oculta el indicador nativo de teclado.
- Ocultar el indicador nativo de teclado fuera de GNOME depende de cada entorno de escritorio.
- Algunas distribuciones XKB usan símbolos Unicode poco comunes. Si se ven cuadrados en el editor visual, instala fuentes adicionales como `fonts-noto-extra`.
