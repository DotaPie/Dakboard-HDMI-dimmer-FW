# Dakboard HDMI Dimmer — Firmware

Firmware for Raspberry Pi Zero 2W that controls HDMI display brightness based on ambient light and motion detection.

Using a [Dakboard-HDMI-dimmer-HW](https://github.com/DotaPie/Dakboard-HDMI-dimmer-HW) with a BH1750 light sensor (I2C) and a PIR motion sensor.

## How it works

- PIR sensor detects motion and wakes the display
- BH1750 light sensor reads ambient light and adjusts brightness accordingly
- Display dims to idle brightness after a configurable timeout
- Runs as a systemd service that starts early on boot

## Quick start

```bash
git clone https://github.com/DotaPie/Dakboard-HDMI-dimmer-FW.git && cd Dakboard-HDMI-dimmer-FW && chmod +x install.sh && sudo ./install.sh
```

The installer enables I2C, deploys the script, creates a systemd service, and reboots.

## Redeploy

After pulling updates, run:

```bash
chmod +x redeploy.sh && sudo ./redeploy.sh
```

This stops the service, copies updated files from `src/`, and restarts it — no reboot needed.

## Useful commands

```bash
sudo systemctl status dimmer.service
journalctl -u dimmer.service -f
```
