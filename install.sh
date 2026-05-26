#!/bin/bash
set -e

APP_NAME="teclado-indicador"
EXT_UUID="hide-input-source@teclado-indicador"

echo "Instalando dependencias..."
sudo apt update
sudo apt install -y python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1 zenity gkbd-capplet gnome-shell-extension-appindicator

echo "Creando carpetas..."
mkdir -p "$HOME/.local/bin"
mkdir -p "$HOME/.config/teclado-indicador/profiles"
mkdir -p "$HOME/.config/teclado-indicador/keyd"
mkdir -p "$HOME/.config/teclado-indicador/xkb"
mkdir -p "$HOME/.xkb/symbols"
mkdir -p "$HOME/.config/autostart"

echo "Instalando indicador..."
cp teclado-indicador.py "$HOME/.local/bin/teclado-indicador.py"
chmod +x "$HOME/.local/bin/teclado-indicador.py"

echo "Instalando helper..."
sudo cp helpers/keyd-aplicar-conf /usr/local/sbin/keyd-aplicar-conf
sudo chmod 755 /usr/local/sbin/keyd-aplicar-conf

echo "Configurando sudoers..."
CURRENT_USER="$(whoami)"
echo "$CURRENT_USER ALL=(root) NOPASSWD: /usr/local/sbin/keyd-aplicar-conf" | sudo tee /etc/sudoers.d/teclado-indicador-keyd > /dev/null
sudo chmod 440 /etc/sudoers.d/teclado-indicador-keyd
sudo visudo -c

echo "Instalando autoinicio..."
cat > "$HOME/.config/autostart/teclado-indicador.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Indicador de teclado personalizado
Comment=Menú personalizado para fuentes de entrada, layouts XKB y
Exec=$HOME/.local/bin/teclado-indicador.py
Icon=input-keyboard
Terminal=false
X-GNOME-Autostart-enabled=true
DESKTOP

echo "Instalando extensión local de GNOME..."
EXT_DIR="$HOME/.local/share/gnome-shell/extensions/$EXT_UUID"
mkdir -p "$EXT_DIR"
cp gnome-extension/metadata.json "$EXT_DIR/metadata.json"
cp gnome-extension/extension.js "$EXT_DIR/extension.js"

echo "Iniciando indicador..."
pkill -f "$HOME/.local/bin/teclado-indicador.py" 2>/dev/null || true
pkill -f "teclado-indicador.py" 2>/dev/null || true

nohup "$HOME/.local/bin/teclado-indicador.py" >/tmp/teclado-indicador.log 2>&1 &
sleep 1

if pgrep -af "teclado-indicador.py" >/dev/null; then
    echo "Indicador iniciado correctamente."
else
    echo "No se pudo confirmar que el indicador siga abierto."
    echo "Prueba manual:"
    echo "  $HOME/.local/bin/teclado-indicador.py"
    echo "Log:"
    echo "  cat /tmp/teclado-indicador.log"
fi

echo "Instalación terminada."
echo "Cierra sesión y vuelve a entrar para que GNOME detecte la extensión."
echo "Después ejecuta:"
echo "  gnome-extensions enable $EXT_UUID"
