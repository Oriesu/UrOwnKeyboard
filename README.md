# UrOwnKeyboard

**UrOwnKeyboard** es un gestor de distribuciones de teclado personalizadas para Linux.

Permite importar, crear, activar y eliminar configuraciones basadas en **XKB** y, opcionalmente, asociarlas con archivos **keyd.conf** para remapeos físicos y atajos avanzados.

Incluye:

- un comando de terminal llamado `uok`;
- un indicador gráfico compatible con AppIndicator/Ayatana;
- un editor visual de distribuciones XKB;
- soporte para perfiles XKB propios;
- soporte opcional para `keyd`;
- Extensiónes específicas para ocultar el indicador nativo de fuentes de entrada.

---

## Estado actual

UrOwnKeyboard está orientado a escritorios Linux que usen XKB.

Estado de soporte:

| Escritorio | Estado |
|---|---|
| GNOME | Soportado (x11) |
| KDE Plasma | Soportado (x11) |
| XFCE | Soportado (x11)|
| MATE | Soportado (x11)|
| Cinnamon | Soportado (x11)|
| LXQt | Soportado (x11)|
| Otros | Puede funcionar si soportan XKB y AppIndicator/Ayatana/StatusNotifier (x11)|

En **GNOME**, UrOwnKeyboard usa las fuentes de entrada de `gsettings`.

En **XFCE**, UrOwnKeyboard puede leer distribuciones añadidas desde la configuración de teclado de XFCE, `setxkbmap` e IBus cuando está presente.

---

## Funciones

- Importar distribuciones XKB desde archivos.
- Crear distribuciones nuevas desde un editor visual.
- Usar como base una distribución del sistema, una fuente añadida desde la configuración del escritorio o una configuración propia de UrOwnKeyboard.
- Editar teclas visualmente, incluyendo niveles normal, Shift, AltGr y AltGr+Shift.
- Exportar una distribución editada como archivo XKB.
- Importar directamente una distribución editada en UrOwnKeyboard.
- Asociar opcionalmente un archivo `keyd.conf`.
- Aplicar automáticamente XKB + keyd.
- Volver a una distribución normal dejando `keyd` en modo neutral.
- Listar configuraciones importadas.
- Eliminar configuraciones importadas.
- Mostrar la configuración activa.
- Mostrar el `keyd.conf` asociado a la configuración activa.
- Mostrar una vista completa de la configuración activa.
- Usar un menú gráfico en la barra superior o panel.
- Abrir la configuración de teclado del sistema desde el menú gráfico.
- Ocultar el indicador nativo/IBus en cuando sea posible.
- Iniciarse automáticamente al iniciar sesión.

---

## Instalación rápida

En Ubuntu, Debian y derivadas:

```bash
sudo apt update
sudo apt install -y git build-essential python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1 zenity gkbd-capplet gnome-shell-extension-appindicator fonts-noto-core fonts-noto-extra x11-xkb-utils fonts-noto-core fonts-noto-extra

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
chmod +x install.sh uninstall.sh make-release.sh uok
chmod +x install.sh uninstall.sh uok
./install.sh
```

El instalador instala las dependencias necesarias, copia los archivos a `~/.local/bin`, instala el helper de `keyd`, crea la regla sudoers limitada y activa el autoinicio del indicador.

Después de instalar, se recomienda cerrar sesión y volver a entrar.

En GNOME, si el indicador nativo sigue apareciendo, ejecuta:

```bash
gnome-extensions enable hide-input-source@teclado-indicador
```

---

## Qué instala

El script `install.sh`:

- instala dependencias GTK, AppIndicator/Ayatana, XKB, Noto y herramientas de escritorio;
- instala o activa `keyd`;
- crea directorios de configuración en `~/.config/teclado-indicador/`;
- copia `uok` a `~/.local/bin/uok`;
- copia `teclado-indicador.py` a `~/.local/bin/`;
- copia `uok-layout-editor.py` a `~/.local/bin/`;
- copia los módulos `uok_xkb_symbols.py` y `uok_xkb_sources.py`;
- instala el helper `/usr/local/sbin/keyd-aplicar-conf`;
- crea la regla sudoers `/etc/sudoers.d/teclado-indicador-keyd`;
- crea el autoinicio `~/.config/autostart/teclado-indicador.desktop`;
- instala la extensión local de GNOME si detecta GNOME Shell;
- inicia el indicador gráfico.

La regla sudoers se limita al helper de keyd:

```text
/usr/local/sbin/keyd-aplicar-conf
```

Puedes comprobarla con:

```bash
sudo visudo -cf /etc/sudoers.d/teclado-indicador-keyd
```

---

## Uso gráfico

Después de instalar, aparecerá un indicador de UrOwnKeyboard en la barra superior o panel.

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

### New configuration…

Agrupa las formas de crear o añadir configuraciones:

- **Open visual editor…** abre el editor visual.
- **Import configuration…** importa un archivo XKB existente.
- **Add from settings…** abre la configuración de teclado del escritorio actual.

`Add from settings…` se adapta al escritorio:

- en GNOME abre la configuración de teclado/región de GNOME;
- en XFCE abre `xfce4-keyboard-settings`;
- en Cinnamon intenta abrir `cinnamon-settings keyboard`;
- en KDE intenta abrir el módulo de teclado de System Settings.

### Reload list

Recarga las distribuciones mostradas en el menú.

Útil si acabas de añadir una distribución desde los ajustes del sistema.

---

## Editor visual

El editor visual permite crear una distribución XKB desde una base existente.

Se puede iniciar desde el menú gráfico o desde terminal:

```bash
uok editor
```

También se puede abrir directamente:

```bash
~/.local/bin/uok-layout-editor.py
```

El editor permite:

- elegir una distribución base;
- modificar símbolos de teclas;
- editar niveles normal, Shift, AltGr y AltGr+Shift;
- guardar la distribución como archivo XKB;
- importar la distribución directamente en UrOwnKeyboard;
- añadir atajos concretos de keyd.

### keyd en el editor visual

El editor visual sólo debe generar reglas concretas de keyd.

La opción antigua de **bloqueo global de todos los atajos** fue eliminada porque generaba archivos `keyd.conf` enormes con muchas secciones y muchos `noop`. Ese formato podía hacer fallar `keyd` por superar su límite interno de secciones.

Formato recomendado:

```ini
[ids]
*

[main]
leftcontrol = layer(ctrlq)
rightcontrol = layer(ctrlq)
leftalt = layer(altq)

[ctrlq]
c = C-c
v = C-v

[altq]
tab = A-tab
```

No se recomienda generar secciones masivas como:

```ini
[ctrl_alt_shift_meta_altgrq]
a = noop
b = noop
c = noop
```

---

## Uso por terminal

### Ver ayuda

```bash
uok --help
```

### Listar configuraciones

```bash
uok list
```

### Importar una distribución XKB

```bash
uok import --name "Mi teclado" --xkb ./mi_teclado
```

### Importar una distribución XKB con keyd

```bash
uok import \
  --name "Mi teclado" \
  --xkb ./mi_teclado \
  --keyd ./mi_teclado.keyd.conf
```

### Activar una configuración

```bash
uok activate mi_teclado
```

### Ver la configuración activa

```bash
uok current
```

### Ver el keyd activo

```bash
uok current-keyd
```

### Ver la configuración completa

```bash
uok show
```

### Eliminar una configuración

```bash
uok delete mi_teclado
```

---

## Ejemplo: importar Dvorak para programación en español

Si tienes una carpeta con:

```text
Dvorak-para-programacion-en-espanol-main/
├── esprog
├── esprog.keyd.conf
└── README.md
```

puedes importarla con:

```bash
uok import \
  --name "Dvorak esprog" \
  --xkb "$HOME/Descargas/Dvorak-para-programacion-en-espanol-main/esprog" \
  --keyd "$HOME/Descargas/Dvorak-para-programacion-en-espanol-main/esprog.keyd.conf"
```

Luego activa el perfil:

```bash
uok list
uok activate dvorak_esprog
```

Si el ID generado es distinto, usa el ID exacto mostrado por `uok list`.

---

## Funcionamiento de keyd

UrOwnKeyboard trata XKB como la parte principal y `keyd` como una capa opcional.

Al activar una configuración importada:

1. intenta aplicar el `keyd.conf` asociado, si existe;
2. aplica la distribución XKB;
3. guarda el perfil como configuración activa.

Si `keyd` falla, UrOwnKeyboard puede mantener XKB activo y mostrar un aviso no bloqueante.

Al volver a una distribución normal del sistema, UrOwnKeyboard deja `/etc/keyd/default.conf` en modo neutral:

```ini
[ids]
*

[main]
```

Esto significa que el servicio `keyd` puede seguir activo, pero sin remapeos personalizados.

Comprobar estado:

```bash
sudo cat /etc/keyd/default.conf
systemctl is-active keyd
```

Es normal que `systemctl is-active keyd` muestre:

```text
active
```

Lo importante es que `/etc/keyd/default.conf` esté neutral cuando uses una distribución normal.

---

## GNOME

En GNOME, UrOwnKeyboard lee las fuentes de entrada desde:

```bash
gsettings get org.gnome.desktop.input-sources sources
```

También puede cambiar la fuente activa de GNOME y aplicar XKB.

Para ocultar el indicador nativo de GNOME, el instalador incluye una extensión local:

```text
gnome-extension/
├── extension.js
└── metadata.json
```

Activación manual:

```bash
gnome-extensions enable hide-input-source@teclado-indicador
```

---

## XFCE

En XFCE, UrOwnKeyboard puede leer fuentes desde:

- `xfconf-query`;
- `setxkbmap -query`;
- IBus, si está activo;
- configuraciones detectables del panel.

Para abrir la configuración de teclado de XFCE:

```bash
xfce4-keyboard-settings
```

Para comprobar la configuración actual:

```bash
xfconf-query -c keyboard-layout -l -v
setxkbmap -query
```

UrOwnKeyboard intenta ocultar indicadores nativos o de IBus en el panel de XFCE cuando interfieren con el menú propio.

---

## Estructura del proyecto

```text
.
├── gnome-extension
│   ├── extension.js
│   └── metadata.json
├── helpers
│   └── keyd-aplicar-conf
├── install.sh
├── make-release.sh
├── README.md
├── teclado-indicador.py
├── uninstall.sh
├── uok
├── uok-layout-editor.keyd.py
├── uok-layout-editor.py
├── uok_xkb_sources.py
└── uok_xkb_symbols.py
```

Archivos principales:

| Archivo | Función |
|---|---|
| `uok` | CLI principal |
| `teclado-indicador.py` | Indicador gráfico |
| `uok-layout-editor.py` | Editor visual XKB |
| `uok_xkb_sources.py` | Lectura de fuentes XKB del sistema/escritorio |
| `uok_xkb_symbols.py` | Utilidades para símbolos XKB |
| `helpers/keyd-aplicar-conf` | Helper con sudo para aplicar keyd |
| `install.sh` | Instalador |
| `uninstall.sh` | Desinstalador |
| `make-release.sh` | Generador de release |

---

## Crear una release

```bash
./make-release.sh
```

El script genera una carpeta `release/` con el paquete y el `.tar.gz`.

---

## Desinstalación

```bash
./uninstall.sh
```

Esto elimina los archivos instalados por UrOwnKeyboard.

Si quieres dejar keyd neutral manualmente:

```bash
sudo tee /etc/keyd/default.conf >/dev/null <<'EOF2'
[ids]
*

[main]
EOF2
sudo systemctl restart keyd
```

---

## Solución de problemas

### No aparece el indicador

Comprueba que el autoinicio existe:

```bash
ls ~/.config/autostart/teclado-indicador.desktop
```

Reinicia manualmente:

```bash
pkill -f teclado-indicador.py 2>/dev/null || true
pkill -f uok-indicator-start 2>/dev/null || true
rm -rf "/tmp/uok-indicator-$USER.lock"
~/.local/bin/uok-indicator-start &
```

### keyd no aplica una configuración

Comprueba el archivo asociado:

```bash
uok current-keyd
sudo journalctl -u keyd -n 120 --no-pager
```

Comprueba que el helper funciona:

```bash
sudo /usr/local/sbin/keyd-aplicar-conf ~/.config/teclado-indicador/keyd/ID_DEL_PERFIL.conf
```

### keyd está activo al volver a una distribución normal

Eso es correcto.

Comprueba que esté neutral:

```bash
sudo cat /etc/keyd/default.conf
```

Debe mostrar:

```ini
[ids]
*

[main]
```

### El editor genera un keyd.conf demasiado grande

No debería ocurrir en la versión actual.

Comprueba:

```bash
wc -l ~/.config/teclado-indicador/keyd/mi_teclado.conf
grep -n '^\[' ~/.config/teclado-indicador/keyd/mi_teclado.conf
```

Si aparecen muchas secciones de combinaciones de modificadores, elimina esa configuración y vuelve a generarla con la versión actual del editor.

---

## Notas sobre fuentes Unicode

Algunas distribuciones usan símbolos Unicode poco comunes. Para mejorar su visualización se recomienda tener instaladas las fuentes Noto.

El instalador intenta instalar:

```bash
fonts-noto-core fonts-noto-extra
```

Instalación manual:

```bash
sudo apt install -y fonts-noto-core fonts-noto-extra
```

---

## Licencia

Indica aquí la licencia del proyecto.
