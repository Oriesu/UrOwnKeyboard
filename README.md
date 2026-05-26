# UrOwnKeyboard

**UrOwnKeyboard** es un indicador gráfico para GNOME que permite importar, activar y gestionar distribuciones de teclado personalizadas.

Permite usar archivos **XKB** para definir distribuciones de teclado y, opcionalmente, archivos **keyd.conf** para aplicar remapeos físicos o atajos personalizados.

Está pensado para sustituir el menú básico de fuentes de entrada de GNOME por un menú más completo.

## Funciones

- Gestiona las fuentes de entrada configuradas en GNOME.
- Importa distribuciones XKB desde archivos.
- Permite asociar un archivo `keyd.conf` a cada distribución.
- Aplica automáticamente XKB + keyd al seleccionar una configuración.
- Permite eliminar configuraciones importadas.
- Permite mostrar la configuración completa activa: visor XKB, perfil seleccionado y keyd.conf asociado.
- Oculta el indicador nativo de teclado de GNOME.
- Se inicia automáticamente al iniciar sesión.

## Compatibilidad

UrOwnKeyboard usa XKB y keyd como base, por lo que el sistema de perfiles puede adaptarse a otros entornos Linux compatibles.

La interfaz gráfica incluida actualmente está orientada a GNOME y escritorios compatibles con AppIndicator/Ayatana.

La integración que oculta el indicador nativo de teclado es específica de GNOME.

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
chmod +x install.sh uninstall.sh
./install.sh
```

Después de instalar, cierra sesión y vuelve a entrar.

Si el indicador nativo de GNOME sigue apareciendo, ejecuta:

```bash
gnome-extensions enable hide-input-source@teclado-indicador
```

## Uso

Después de instalar, aparecerá un nuevo indicador en la barra superior de GNOME.

Desde ese menú puedes usar:

```text
Mostrar distribución actual
Importar configuración…
Eliminar configuración…
Recargar lista
```

## Importar una configuración

Selecciona:

```text
Importar configuración…
```

El programa pedirá:

```text
1. Nombre de la configuración
2. Archivo XKB / symbols
3. Archivo keyd.conf opcional
```

Si sólo quieres cambiar la distribución de teclado, selecciona únicamente el archivo XKB.

Si también quieres remapear atajos físicos, selecciona además un archivo `keyd.conf`.

## Activar una configuración

Una configuración importada aparecerá directamente en el menú.

Al seleccionarla:

```text
- se aplica el layout XKB
- si tiene keyd.conf asociado, se aplica también la configuración keyd
```

## Eliminar una configuración

Selecciona:

```text
Eliminar configuración…
```

Esto elimina sólo configuraciones importadas desde UrOwnKeyboard.

No elimina las distribuciones normales de GNOME.

## Mostrar distribución actual

La opción:

```text
Mostrar distribución actual
```

abre el visor gráfico de GNOME con la distribución XKB activa.

Nota: este visor muestra la distribución XKB, pero no puede mostrar remapeos hechos por keyd.

## Desinstalación

Copia y pega:

```bash
cd "$HOME/UrOwnKeyboard"
./uninstall.sh
```

Esto elimina:

```text
- el indicador instalado
- el autoinicio
- la extensión local de GNOME
- el helper keyd
- la regla sudoers
```

No borra tus configuraciones importadas en:

```text
~/.config/teclado-indicador/
~/.xkb/symbols/
```

## Estructura del proyecto

```text
UrOwnKeyboard/
├── teclado-indicador.py
├── install.sh
├── uninstall.sh
├── helpers/
│   └── keyd-aplicar-conf
├── gnome-extension/
│   ├── metadata.json
│   └── extension.js
└── README.md
```

## Seguridad

UrOwnKeyboard no ejecuta scripts importados.

Sólo gestiona:

```text
- archivos XKB / symbols
- archivos keyd.conf
```

Para aplicar configuraciones keyd sin pedir contraseña cada vez, el instalador crea una regla sudoers limitada al helper:

```text
/usr/local/sbin/keyd-aplicar-conf
```

Ese helper sólo acepta archivos situados dentro de la carpeta de configuración del usuario.

## Limitaciones

- Tras instalar, puede ser necesario cerrar sesión y volver a entrar para que GNOME detecte la extensión que oculta el indicador nativo de teclado.
- La extensión para ocultar el indicador nativo es específica de GNOME. En otros escritorios puede ser necesario ocultar manualmente su propio indicador de teclado.
