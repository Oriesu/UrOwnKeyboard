#!/usr/bin/env bash
set -u
echo "== Parando UOK y keyd =="
pkill -f teclado-indicador.py 2>/dev/null || true
sudo systemctl stop keyd 2>/dev/null || true
echo "== Quitando layout experimental UOK registrado en sistema =="
sudo rm -f /usr/share/X11/xkb/symbols/uok_mi_teclado_visual 2>/dev/null || true
echo "== Reinstalando xkb-data =="
sudo apt install --reinstall -y xkb-data
echo "== Restaurando GNOME sources =="
gsettings set org.gnome.desktop.input-sources sources "[('xkb', 'es'), ('xkb', 'de')]"
gsettings set org.gnome.desktop.input-sources mru-sources "[('xkb', 'es'), ('xkb', 'de')]"
gsettings set org.gnome.desktop.input-sources current 0
gsettings set org.gnome.desktop.input-sources xkb-options "[]"
echo "== Restaurando IBus =="
gsettings set org.freedesktop.ibus.general preload-engines "['xkb:es::spa', 'xkb:de::ger']"
gsettings set org.freedesktop.ibus.general engines-order "['xkb:es::spa', 'xkb:de::ger']"
gsettings set org.freedesktop.ibus.general use-xmodmap false
ibus restart 2>/dev/null || true
sleep 2
ibus engine xkb:es::spa 2>/dev/null || true
echo "== Limpiando estado UOK =="
rm -f "$HOME/.config/teclado-indicador/current-profile.json"
rm -f "$HOME/.config/teclado-indicador/gnome-wayland-source-request"
echo "== Estado =="
gsettings get org.gnome.desktop.input-sources sources
gsettings get org.gnome.desktop.input-sources current
ibus engine 2>/dev/null || true