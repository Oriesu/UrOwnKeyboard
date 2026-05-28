# UrOwnKeyboard

**UrOwnKeyboard** es un gestor de distribuciones de teclado personalizadas para Linux.

Permite importar, crear, activar y eliminar configuraciones basadas en **XKB** y, opcionalmente, asociarlas con archivos **keyd.conf** para remapeos físicos y atajos avanzados.

Incluye:

- un comando de terminal llamado `uok`;
- un indicador gráfico compatible con AppIndicator/Ayatana;
- un editor visual de distribuciones XKB;
- soporte para perfiles XKB propios;
- soporte opcional para `keyd`;

---

## Estado actual

UrOwnKeyboard está orientado a escritorios Linux que usen XKB.

Estado de soporte:

| Escritorio | Estado |
|---|---|
| GNOME | Soportado |
| XFCE | Soportado |
| Cinnamon | Parcial / experimental |
| KDE Plasma | Parcial / experimental |
| Otros | Puede funcionar si soportan XKB y AppIndicator/Ayatana |

En **GNOME**, UrOwnKeyboard usa las fuentes de entrada de `gsettings`.

En **XFCE**, UrOwnKeyboard puede leer distribuciones añadidas desde la configuración de teclado de XFCE, `setxkbmap` e IBus cuando está presente.

---

## Instalación

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
chmod +x install.sh uninstall.sh uok
./install.sh
```

El instalador instala las dependencias necesarias, copia los archivos a `~/.local/bin`, instala el helper de `keyd`, crea la regla sudoers limitada y activa el autoinicio del indicador.

Después de instalar, se recomienda cerrar sesión y volver a entrar.

---

## Funciones

- Importar distribuciones XKB desde archivos.
- Crear distribuciones nuevas desde un editor visual usando como base una distribución del sistema, o una configuración propia de UrOwnKeyboard.
- Editar teclas visualmente, incluyendo niveles normal, Shift, AltGr y AltGr+Shift.
- Exportar una distribución editada como archivo XKB.
- Asociar opcionalmente un archivo `keyd.conf`.
- Aplicar automáticamente XKB + keyd.
- Cambiar entre distribuciones.
- Listar configuraciones importadas.
- Eliminar configuraciones importadas.
- Mostrar la configuración activa.
- Menú gráfico en la barra superior o panel.
- Ocultar el indicadores nativos de teclado.
- Iniciarse automáticamente al iniciar sesión.

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
~/
├── keyboard 
└── shotcuts.keyd.conf
```

puedes importarla con:

```bash
uok import \
  --name "Configuration 1" \
  --xkb "$HOME/keyboard" \
  --keyd "$HOME/shotcuts.keyd.conf"
```

Luego activa el perfil:

```bash
uok list
uok activate configuration_1
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
