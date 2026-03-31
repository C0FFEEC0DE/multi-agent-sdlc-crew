#!/bin/bash

set -euo pipefail

# Claude Code Config Installer
# Installs config from repo

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_DIR="${SCRIPT_DIR}/claudecfg"
BACKUP_DIR="$HOME/.claude.backup.$(date +%Y%m%d_%H%M%S)"

echo "=== Claude Code Config Installer ==="

if [ ! -d "$CONFIG_DIR" ]; then
    echo "ERROR: expected config directory at $CONFIG_DIR"
    exit 1
fi

# Backup current directory
if [ -d "$HOME/.claude" ]; then
    echo "[1/3] Creating backup: $BACKUP_DIR"
    cp -r "$HOME/.claude" "$BACKUP_DIR"
    echo "      Backup created!"
else
    echo "[1/3] No existing .claude directory, skipping backup"
fi

# Install new config
echo "[2/3] Installing new config..."
mkdir -p "$HOME/.claude"
cp -r "$CONFIG_DIR"/* "$HOME/.claude/"
find "$HOME/.claude/hooks" -type f -name "*.sh" -exec chmod +x {} \;
echo "      Done!"

# Verify
echo "[3/3] Verifying installation..."
if [ -f "$HOME/.claude/settings.json" ]; then
    echo "      settings.json OK"
else
    echo "      ERROR: settings.json not found!"
    exit 1
fi

echo ""
echo "=== Installation complete! ==="
echo "Restart Claude Code to use new config."
echo ""
echo "To restore backup: cp -r $BACKUP_DIR/* $HOME/.claude/"
