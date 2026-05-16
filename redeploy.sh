#!/usr/bin/env bash
set -e

APP_DIR="/opt/dimmer"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "[RE-INSTALL] Stopping dimmer service..."
sudo systemctl stop dimmer.service

echo "[RE-INSTALL] Deploying updated files..."
sudo cp "$SCRIPT_DIR/src/"* "$APP_DIR/"
sudo chmod +x "$APP_DIR/"*.py

echo "[RE-INSTALL] Reloading and restarting service..."
sudo systemctl daemon-reload
sudo systemctl restart dimmer.service

echo
echo "[DONE] Dimmer service re-deployed."
echo
echo "Check service status with:"
echo "  sudo systemctl status dimmer.service"
echo
echo "View logs with:"
echo "  journalctl -u dimmer.service -f"
