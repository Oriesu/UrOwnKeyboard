#!/bin/bash
set -e

EXT_UUID="hide-input-source@teclado-indicador"

pkill -f teclado-indicador.py || true

gnome-extensions disable "$EXT_UUID" 2>/dev/null || true

rm -f "$HOME/.local/bin/teclado-indicador.py"
rm -f "$HOME/.config/autostart/teclado-indicador.desktop"
rm -rf "$HOME/.local/share/gnome-shell/extensions/$EXT_UUID"

sudo rm -f /usr/local/sbin/keyd-aplicar-conf
sudo rm -f /etc/sudoers.d/teclado-indicador-keyd

echo "Desinstalado. Las configuraciones importadas en ~/.config/teclado-indicador no se han borrado."
