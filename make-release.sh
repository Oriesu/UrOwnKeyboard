#!/usr/bin/env bash
set -euo pipefail
APP_NAME="UrOwnKeyboard"
VERSION="${1:-dev}"
RELEASE_DIR="release"
PKG_DIR="$RELEASE_DIR/UrOwnKeyboard-$VERSION"
ARCHIVE="$RELEASE_DIR/UrOwnKeyboard-$VERSION.tar.gz"
rm -rf "$PKG_DIR"
mkdir -p "$PKG_DIR"
copy_file() {
    local src="$1"
    if [ -f "$src" ]; then
        cp "$src" "$PKG_DIR/"
    else
        echo "ERROR: missing required file: $src" >&2
        exit 1
    fi
}
copy_dir() {
    local src="$1"
    if [ -d "$src" ]; then
        cp -r "$src" "$PKG_DIR/"
    fi
}
copy_file README.md
copy_file install.sh
copy_file uninstall.sh
copy_file uok
copy_file teclado-indicador.py
copy_file uok-layout-editor.py
copy_file uok_xkb_symbols.py
copy_file uok_xkb_sources.py
copy_dir helpers
copy_dir uok_backends
copy_dir gnome-extension
if [ -f aplicar-editor-visual-uok.sh ]; then
    cp aplicar-editor-visual-uok.sh "$PKG_DIR/"
fi
find "$PKG_DIR" -type f -name "*.py" -exec python3 -m py_compile {} \;
bash -n "$PKG_DIR/install.sh"
bash -n "$PKG_DIR/uninstall.sh"
if [ -f "$PKG_DIR/helpers/keyd-aplicar-conf" ]; then
    bash -n "$PKG_DIR/helpers/keyd-aplicar-conf"
    chmod +x "$PKG_DIR/helpers/keyd-aplicar-conf"
fi
chmod +x "$PKG_DIR/install.sh"
chmod +x "$PKG_DIR/uninstall.sh"
chmod +x "$PKG_DIR/uok"
chmod +x "$PKG_DIR/teclado-indicador.py"
chmod +x "$PKG_DIR/uok-layout-editor.py"
rm -f "$ARCHIVE"
tar -C "$RELEASE_DIR" -czf "$ARCHIVE" "UrOwnKeyboard-$VERSION"
echo
echo "Release creada:"
echo "$ARCHIVE"
echo
echo "Para probarla:"
echo "mkdir -p /tmp/uok-test"
echo "tar -xzf $ARCHIVE -C /tmp/uok-test"
echo "cd /tmp/uok-test/UrOwnKeyboard-$VERSION"
echo "./install.sh"