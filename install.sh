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

echo "Installing autostart launcher..."
cat > "$HOME/.local/bin/uok-indicator-start" <<'LAUNCHER'
#!/bin/bash

sleep 10

LOG="$HOME/.cache/urownkeyboard/indicator.log"
INDICATOR="$HOME/.local/bin/teclado-indicador.py"
LOCKDIR="/tmp/uok-indicator-$USER.lock"

mkdir -p "$HOME/.cache/urownkeyboard"

{
    echo "---- UrOwnKeyboard indicator start: $(date) ----"

    if [ ! -f "$INDICATOR" ]; then
        echo "Indicator not found: $INDICATOR"
        exit 1
    fi

    rm -rf "$LOCKDIR"

    if mkdir "$LOCKDIR" 2>/dev/null; then
        trap 'rmdir "$LOCKDIR" 2>/dev/null || true' EXIT

        echo "Starting indicator with clean environment..."

        exec env -i \
            HOME="$HOME" \
            USER="$USER" \
            LOGNAME="$USER" \
            SHELL="/bin/bash" \
            DISPLAY="${DISPLAY:-}" \
            WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-}" \
            XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}" \
            DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-}" \
            XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-}" \
            XDG_CURRENT_DESKTOP="${XDG_CURRENT_DESKTOP:-}" \
            DESKTOP_SESSION="${DESKTOP_SESSION:-}" \
            PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$HOME/.local/bin" \
            /usr/bin/python3 "$INDICATOR"
    else
        echo "Could not create lock directory: $LOCKDIR"
        exit 1
    fi
} >> "$LOG" 2>&1
LAUNCHER

chmod +x "$HOME/.local/bin/uok-indicator-start"


echo "Installing autostart entry..."
cat > "$HOME/.config/autostart/teclado-indicador.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=UrOwnKeyboard
Comment=Custom keyboard layout indicator
Exec=$HOME/.local/bin/uok-indicator-start
Icon=input-keyboard
Terminal=false
X-GNOME-Autostart-enabled=true
Hidden=false
NoDisplay=false
StartupNotify=false
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
pkill -f teclado-indicador.py 2>/dev/null || true
pkill -f uok-indicator-start 2>/dev/null || true
rm -rf "/tmp/uok-indicator-$USER.lock"

"$HOME/.local/bin/uok-indicator-start" &

sleep 12

if pgrep -af "teclado-indicador.py" >/dev/null; then
    echo "Indicator started successfully."
else
    echo "Could not confirm that the indicator is still running."
    echo "Manual test:"
    echo "  $HOME/.local/bin/uok-indicator-start"
    echo "Log:"
    echo "  cat $HOME/.cache/urownkeyboard/indicator.log"
firm that the indicator is still running."
    echo "Manual test:"
    echo "  $HOME/.local/bin/uok-indicator-start"
    echo "Log:"
    echo "  cat $HOME/.cache/urownkeyboard/indicator.log"
firm that the indicator is still running."
    echo "Manual test:"
    echo "  $HOME/.local/bin/teclado-indicador.py"
    echo "Log:"
    echo "  cat /tmp/teclado-indicador.log"
fi

echo "Installation complete."
echo "Log out and log back in so GNOME can detect the extension."
echo "Then run:"
echo "  gnome-extensions enable $EXT_UUID"
