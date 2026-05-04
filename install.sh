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
After=multi-user.target

[Service]
Type=simple
ExecStart=/usr/bin/python3.11 $APP_DIR/dimmer.py
WorkingDirectory=$APP_DIR
Restart=always
RestartSec=3
User=root

[Install]
WantedBy=multi-user.target
EOF

echo "[INSTALL] Enabling and starting service..."
sudo systemctl daemon-reload
sudo systemctl enable dimmer.service
sudo systemctl restart dimmer.service

echo
echo "[DONE] Dimmer installed."
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