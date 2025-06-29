#!/bin/bash
# ============================================================================
# Translation Update Script
#
# This script scans the Python source code for translatable strings
# and updates the .ts translation files in the i18n/ directory.
#
# Requirements:
# - PyQt6 development tools must be installed (`pyqt6-dev-tools` on Debian/Ubuntu)
#   sudo apt-get install pyqt6-dev-tools
#
# Usage:
#   cd OpenVPN-Py-main
#   ./scripts/update_translations.sh
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
I18N_DIR="$PROJECT_DIR/i18n"

echo "Updating translation source files (*.ts)..."

# Check if pylupdate6 is installed
if ! command -v pylupdate6 &> /dev/null; then
    echo "Error: pylupdate6 could not be found."
    echo "Please install PyQt6 development tools (e.g., 'sudo apt-get install pyqt6-dev-tools')."
    exit 1
fi

# Find all python files
PY_FILES=$(find "$PROJECT_DIR" -name "*.py")

# Update the .ts files
pylupdate6 -verbose $PY_FILES -ts "$I18N_DIR/de.ts"
pylupdate6 -verbose $PY_FILES -ts "$I18N_DIR/en.ts"

echo "Update complete."
echo "You can now edit the .ts files (e.g., with Qt Linguist) and compile them to .qm files for use in the application."
echo "Compile with: lrelease i18n/de.ts"