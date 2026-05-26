#!/bin/bash
set -e

APP_NAME="teclado-indicador"
EXT_UUID="hide-input-source@teclado-indicador"

echo "Installing dependencias..."
sudo apt update
sudo apt install -y python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1 zenity gkbd-capplet gnome-shell-extension-appindicator

if ! command -v keyd >/dev/null 2>&1; then
    echo
    echo "WARNING: keyd is not installed."
    echo "UrOwnKeyboard will work with XKB layouts, but profiles with keyd.conf will require keyd."
    echo "Puedes instalar keyd desde: https://github.com/rvaiya/keyd"
    echo
fi

echo "Creating directories..."
mkdir -p "$HOME/.local/bin"
mkdir -p "$HOME/.config/teclado-indicador/profiles"
mkdir -p "$HOME/.config/teclado-indicador/keyd"
mkdir -p "$HOME/.config/teclado-indicador/xkb"
mkdir -p "$HOME/.xkb/symbols"
mkdir -p "$HOME/.config/autostart"

echo "Installing indicator..."
cp teclado-indicador.py "$HOME/.local/bin/teclado-indicador.py"
chmod +x "$HOME/.local/bin/teclado-indicador.py"
cp uok "$HOME/.local/bin/uok"
chmod +x "$HOME/.local/bin/uok"

echo "Installing helper..."
sudo cp helpers/keyd-aplicar-conf /usr/local/sbin/keyd-aplicar-conf
sudo chmod 755 /usr/local/sbin/keyd-aplicar-conf

echo "Configurando sudoers..."
CURRENT_USER="$(whoami)"
echo "$CURRENT_USER ALL=(root) NOPASSWD: /usr/local/sbin/keyd-aplicar-conf" | sudo tee /etc/sudoers.d/teclado-indicador-keyd > /dev/null
sudo chmod 440 /etc/sudoers.d/teclado-indicador-keyd
sudo visudo -cf /etc/sudoers.d/teclado-indicador-keyd

echo "Installing autoinicio..."
cat > "$HOME/.config/autostart/teclado-indicador.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Custom keyboard indicator
Comment=Custom menu for input sources, XKB layouts and keyd
Exec=$HOME/.local/bin/teclado-indicador.py
Icon=input-keyboard
Terminal=false
X-GNOME-Autostart-enabled=true
DESKTOP

echo "Checking GNOME integration..."
if command -v gnome-shell >/dev/null 2>&1; then
    echo "Installing local GNOME extension..."
    EXT_DIR="$HOME/.local/share/gnome-shell/extensions/$EXT_UUID"
    mkdir -p "$EXT_DIR"
    cp gnome-extension/metadata.json "$EXT_DIR/metadata.json"
    cp gnome-extension/extension.js "$EXT_DIR/extension.js"

    gsettings set org.gnome.shell disable-user-extensions false 2>/dev/null || true
else
    echo "GNOME Shell not detected. Skipping the GNOME-specific extension."
fi

echo "Starting indicator..."
pkill -f "$HOME/.local/bin/teclado-indicador.py" 2>/dev/null || true
pkill -f "teclado-indicador.py" 2>/dev/null || true

nohup "$HOME/.local/bin/teclado-indicador.py" >/tmp/teclado-indicador.log 2>&1 &
sleep 1

if pgrep -af "teclado-indicador.py" >/dev/null; then
    echo "Indicator started successfully."
else
    echo "Could not confirm that the indicator is still running."
    echo "Manual test:"
    echo "  $HOME/.local/bin/teclado-indicador.py"
    echo "Log:"
    echo "  cat /tmp/teclado-indicador.log"
fi

echo "Installation complete."
echo "Log out and log back in so GNOME can detect the extension."
echo "Then run:"
echo "  gnome-extensions enable $EXT_UUID"
