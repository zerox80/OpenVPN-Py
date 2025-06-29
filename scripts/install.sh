#!/bin/bash

# Stellt sicher, dass das Skript bei Fehlern abbricht
set -euo pipefail

# Installationsverzeichnis in ~/.config/openvpn-py
TARGET_DIR="$HOME/.config/openvpn-py"
SOURCE_DIR=$(dirname "$(dirname "$(realpath "$0")")")
TARGET_USER=$(whoami)

echo "Starting installation for OpenVPN-Py..."

# Verzeichnisse erstellen
echo "Creating directories in $TARGET_DIR..."
mkdir -p "$TARGET_DIR/scripts"
mkdir -p "$TARGET_DIR/configs"
mkdir -p "$TARGET_DIR/ui"
mkdir -p "$TARGET_DIR/i18n"

# Kopieren der Projektdateien
echo "Copying application files..."
rsync -a --delete \
    --exclude 'scripts/' \
    --exclude '.git/' \
    --exclude '.idea/' \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude '*.md' \
    "$SOURCE_DIR/" "$TARGET_DIR/"

# Kopieren der Skripte
cp "$SOURCE_DIR/scripts/openvpn-gui-helper.sh" "$TARGET_DIR/scripts/"
chmod +x "$TARGET_DIR/scripts/openvpn-gui-helper.sh"
echo "Scripts copied and made executable."

# Übersetzungen kompilieren
echo "Compiling translations..."
"$SOURCE_DIR/scripts/update_translations.sh"
lrelease "$TARGET_DIR/i18n/de.ts" -qm "$TARGET_DIR/i18n/de.qm"
lrelease "$TARGET_DIR/i18n/en.ts" -qm "$TARGET_DIR/i18n/en.qm"
echo "Translations compiled."


# Erstellen der .desktop-Datei für das Anwendungsmenü
DESKTOP_ENTRY_DIR="$HOME/.local/share/applications"
mkdir -p "$DESKTOP_ENTRY_DIR"
DESKTOP_FILE="$DESKTOP_ENTRY_DIR/openvpn-py.desktop"

echo "Creating .desktop file at $DESKTOP_FILE..."

cat > "$DESKTOP_FILE" << EOL
[Desktop Entry]
Name=OpenVPN-Py
Comment=A simple OpenVPN GUI Client
Exec=python3 $TARGET_DIR/main.py
Icon=$SOURCE_DIR/icon.svg
Terminal=false
Type=Application
Categories=Network;
EOL

echo ".desktop file created."

# Einrichten der sudo-Rechte für das Helper-Skript
HELPER_SCRIPT_PATH="$TARGET_DIR/scripts/openvpn-gui-helper.sh"
SUDOERS_FILE="/etc/sudoers.d/openvpn-py-helper"

echo "Setting up sudo permissions..."
echo "This requires sudo privileges."

# Die Regel erlaubt dem Benutzer, das Skript ohne Passwort auszuführen.
# Die Parameter werden durch das Python-Programm validiert.
# WICHTIG: Die neue Regel für `stop` akzeptiert nun einen Pfad als Argument.
SUDOERS_CONTENT="$TARGET_USER ALL=(root) NOPASSWD: $HELPER_SCRIPT_PATH start *, $HELPER_SCRIPT_PATH stop *"

if command -v pkexec >/dev/null; then
    pkexec bash -c "echo '$SUDOERS_CONTENT' > $SUDOERS_FILE && chmod 0440 $SUDOERS_FILE"
else
    sudo bash -c "echo '$SUDOERS_CONTENT' > $SUDOERS_FILE && chmod 0440 $SUDOERS_FILE"
fi


echo ""
echo "----------------------------------------"
echo "Installation complete!"
echo "You can now start OpenVPN-Py from your application menu."
echo "----------------------------------------"