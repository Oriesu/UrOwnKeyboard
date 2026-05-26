# UrOwnKeyboard

**UrOwnKeyboard** es un gestor de distribuciones de teclado personalizadas para Linux.

Permite importar, activar y eliminar configuraciones basadas en **XKB** y, opcionalmente, asociarlas con archivos **keyd.conf** para remapeos físicos y atajos avanzados.

Incluye:

- un núcleo portable de terminal llamado `uok`;
- un indicador gráfico compatible con AppIndicator/Ayatana;
- una integración específica para GNOME que oculta el menú nativo de fuentes de entrada.

## Funciones

- Importar distribuciones XKB desde archivos.
- Asociar opcionalmente un archivo `keyd.conf`.
- Aplicar automáticamente XKB + keyd.
- Listar configuraciones importadas.
- Eliminar configuraciones importadas.
- Mostrar la configuración activa.
- Mostrar el `keyd.conf` activo.
- Mostrar una vista completa de la configuración activa.
- Usar un menú gráfico en la barra superior.
- Ocultar el indicador nativo de teclado de GNOME.
- Iniciarse automáticamente al iniciar sesión.

## Instalación rápida

Copia y pega esto en una terminal:

```bash
sudo apt update
sudo apt install -y git build-essential python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1 zenity gkbd-capplet gnome-shell-extension-appindicator

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

Después de instalar, cierra sesión y vuelve a entrar para que GNOME detecte la extensión que oculta el indicador nativo.

Si el indicador nativo de GNOME sigue apareciendo, ejecuta:

```bash
gnome-extensions enable hide-input-source@teclado-indicador
```

## Uso gráfico

Después de instalar, aparecerá un nuevo indicador en la barra superior.

Desde el menú puedes usar:

```text
Show full configuration
Import configuration…
Delete configuration…
Reload list
```

La interfaz del programa está en inglés para facilitar su uso en sistemas internacionales, pero este README está en español.

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
Import configuration…
```

El programa pedirá:

```text
1. Configuration name
2. XKB / symbols file
3. Optional keyd.conf file
```

Selecciona sólo el archivo XKB si únicamente quieres cambiar la distribución de teclado.

Selecciona también un archivo `keyd.conf` si quieres aplicar remapeos físicos o atajos personalizados.

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

## Compatibilidad

El núcleo `uok` puede funcionar en cualquier entorno Linux compatible con XKB y keyd.

El indicador gráfico usa AppIndicator/Ayatana, por lo que puede funcionar en GNOME y en otros escritorios compatibles con indicadores de aplicación.

La extensión para ocultar el indicador nativo de teclado es específica de GNOME. En otros escritorios, ocultar el indicador nativo dependerá del propio entorno.

## Estructura del proyecto

```text
UrOwnKeyboard/
├── teclado-indicador.py
├── uok
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
