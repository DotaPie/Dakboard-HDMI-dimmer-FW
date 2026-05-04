#!/usr/bin/env bash
set -e

APP_DIR="/opt/dimmer"
SERVICE_FILE="/etc/systemd/system/dimmer.service"

echo "[INSTALL] Enabling I2C..."
sudo sed -i '/^#*dtparam=i2c_arm=/d' /boot/firmware/config.txt
echo 'dtparam=i2c_arm=on' | sudo tee -a /boot/firmware/config.txt

echo "[INSTALL] Installing dimmer script..."
sudo mkdir -p "$APP_DIR"
sudo cp ./src/dimmer.py "$APP_DIR/dimmer.py"
sudo chmod +x "$APP_DIR/dimmer.py"

echo "[INSTALL] Creating systemd service..."
sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=HDMI Display Dimmer
DefaultDependencies=no
After=local-fs.target systemd-udev-settle.service
Before=display-manager.service graphical.target multi-user.target

[Service]
Type=simple
ExecStartPre=/bin/sleep 1
ExecStart=/usr/bin/python3.11 $APP_DIR/dimmer.py
WorkingDirectory=$APP_DIR
Restart=always
RestartSec=3
User=root

[Install]
WantedBy=sysinit.target
EOF

echo "[INSTALL] Enabling and starting service..."
sudo systemctl daemon-reload

# Disable old enable target if it was previously installed differently.
sudo systemctl disable dimmer.service 2>/dev/null || true

sudo systemctl enable dimmer.service
sudo systemctl restart dimmer.service

echo
echo "[DONE] Dimmer installed."
echo "[INFO] Service is configured to start early during boot."
echo "[INFO] I2C was enabled, reboot is needed."
echo
echo "Check service status later with:"
echo "  sudo systemctl status dimmer.service"
echo
echo "View logs later with:"
echo "  journalctl -u dimmer.service -f"
echo
read -r -p "Press Enter to reboot in 3 seconds..."

sleep 3
sudo reboot