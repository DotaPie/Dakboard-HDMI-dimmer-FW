#!/usr/bin/env python3

import os
import signal
import subprocess
import sys
import time
from threading import Lock

from smbus2 import SMBus
from gpiozero import MotionSensor


# =========================
# Config
# =========================

DISPLAY = ":0"
XRANDR_OUTPUT = "HDMI-1"

# Optional.
# If service runs as root and xrandr has auth problems, set this to the real user's Xauthority.
# Common values:
#   /home/pi/.Xauthority
#   /home/dakboard/.Xauthority
# Leave as None if not needed.
XAUTHORITY = None

# Brightness limits
BRIGHTNESS_IDLE = 0.2
BRIGHTNESS_MIN = 0.2
BRIGHTNESS_MAX = 1.5

# What brightness to set when service stops/restarts/reboots.
# You said you changed this to max brightness.
BRIGHTNESS_ON_EXIT = BRIGHTNESS_MAX

# Light sensor scaling
# Sensor values below LIGHT_LUX_MIN map to BRIGHTNESS_MIN.
# Sensor values above LIGHT_LUX_MAX map to BRIGHTNESS_MAX.
LIGHT_LUX_MIN = 0
LIGHT_LUX_MAX = 20

# Brightness transition
BRIGHTNESS_STEP = 0.06

# Time behavior
DISPLAY_ON_SECONDS = 30
LOOP_SLEEP_SECONDS = 0.025
LIGHT_READ_SECONDS = 0.25

# Ignore PIR immediately after startup.
# PIR sensors often need a moment to stabilize.
PIR_STARTUP_IGNORE_SECONDS = 5

# PIR false-trigger filtering
# After PIR says "motion", confirm it is still active several times.
PIR_CONFIRM_SAMPLES = 3
PIR_CONFIRM_SAMPLE_DELAY = 0.02

# Hardware
I2C_BUS = 1
BH1750_ADDR = 0x23
PIR_GPIO = 24

# Wait for X/xrandr to become usable
XRANDR_STARTUP_RETRY_SECONDS = 0.5


# =========================
# BH1750 constants
# =========================

BH1750_POWER_ON = 0x01
BH1750_RESET = 0x07
BH1750_CONTINUOUS_HIGH_RES_MODE = 0x10


# =========================
# Global state
# =========================

target_brightness = BRIGHTNESS_IDLE
current_brightness = BRIGHTNESS_IDLE
last_motion_time = 0.0
script_start_time = time.monotonic()
running = True

pir = None
state_lock = Lock()


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def scale_lux_to_brightness(lux):
    if LIGHT_LUX_MAX <= LIGHT_LUX_MIN:
        print("[ERROR] LIGHT_LUX_MAX must be higher than LIGHT_LUX_MIN")
        return BRIGHTNESS_IDLE

    lux = clamp(lux, LIGHT_LUX_MIN, LIGHT_LUX_MAX)

    ratio = (lux - LIGHT_LUX_MIN) / (LIGHT_LUX_MAX - LIGHT_LUX_MIN)
    brightness = BRIGHTNESS_MIN + ratio * (BRIGHTNESS_MAX - BRIGHTNESS_MIN)

    return clamp(brightness, BRIGHTNESS_MIN, BRIGHTNESS_MAX)


def get_xrandr_env():
    env = os.environ.copy()
    env["DISPLAY"] = DISPLAY

    if XAUTHORITY:
        env["XAUTHORITY"] = XAUTHORITY

    return env


def set_display_brightness(value, log_errors=True):
    value = clamp(value, BRIGHTNESS_MIN, BRIGHTNESS_MAX)

    cmd = [
        "xrandr",
        "--output",
        XRANDR_OUTPUT,
        "--brightness",
        f"{value:.2f}",
    ]

    try:
        subprocess.run(
            cmd,
            env=get_xrandr_env(),
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        return True

    except subprocess.CalledProcessError as e:
        if log_errors:
            error_text = e.stderr.strip() if e.stderr else str(e)
            print(f"[ERROR] xrandr failed for brightness {value:.2f}: {error_text}")
        return False


def wait_for_display_ready():
    print("[START] Waiting for display/xrandr to become ready...")

    while running:
        if set_display_brightness(BRIGHTNESS_IDLE, log_errors=False):
            print(f"[START] Display ready, brightness set to idle {BRIGHTNESS_IDLE:.2f}")
            return True

        time.sleep(XRANDR_STARTUP_RETRY_SECONDS)

    return False


def read_bh1750_lux(bus):
    # BH1750 returns 2 bytes.
    data = bus.read_i2c_block_data(BH1750_ADDR, BH1750_CONTINUOUS_HIGH_RES_MODE, 2)
    raw = (data[0] << 8) | data[1]

    # Per BH1750 datasheet: lux = raw / 1.2
    return raw / 1.2


def step_brightness_towards_target():
    global current_brightness

    with state_lock:
        target = clamp(target_brightness, BRIGHTNESS_MIN, BRIGHTNESS_MAX)
        current = clamp(current_brightness, BRIGHTNESS_MIN, BRIGHTNESS_MAX)

    if abs(current - target) < 0.001:
        return

    if current < target:
        new_value = min(current + BRIGHTNESS_STEP, target)
    else:
        new_value = max(current - BRIGHTNESS_STEP, target)

    new_value = clamp(new_value, BRIGHTNESS_MIN, BRIGHTNESS_MAX)

    if set_display_brightness(new_value):
        with state_lock:
            current_brightness = new_value

        print(f"[BRIGHTNESS] {new_value:.2f}")
    else:
        print("[BRIGHTNESS] Not updated because xrandr failed")


def motion_detected():
    global last_motion_time

    now = time.monotonic()

    if now - script_start_time < PIR_STARTUP_IGNORE_SECONDS:
        print("[MOTION] Ignored during PIR startup stabilization")
        return

    if pir is None:
        print("[MOTION] Ignored, PIR not initialized yet")
        return

    # Confirm PIR signal with quick repeated samples.
    # This helps ignore very short false triggers.
    for sample in range(PIR_CONFIRM_SAMPLES):
        if not pir.motion_detected:
            print(f"[MOTION] Ignored false trigger, sample {sample + 1} was low")
            return

        time.sleep(PIR_CONFIRM_SAMPLE_DELAY)

    with state_lock:
        last_motion_time = time.monotonic()

    print("[MOTION] Confirmed, timer reset")


def handle_shutdown_signal(signum, frame):
    global running
    print(f"[STOP] Received signal {signum}, shutting down")
    running = False


def main():
    global target_brightness
    global current_brightness
    global pir

    print("[START] Starting display brightness controller")

    with state_lock:
        current_brightness = BRIGHTNESS_IDLE
        target_brightness = BRIGHTNESS_IDLE

    if not wait_for_display_ready():
        return

    pir = MotionSensor(PIR_GPIO)
    pir.when_motion = motion_detected

    last_light_read = 0.0
    scaled_light_brightness = BRIGHTNESS_IDLE

    with SMBus(I2C_BUS) as bus:
        bus.write_byte(BH1750_ADDR, BH1750_POWER_ON)
        time.sleep(0.05)
        bus.write_byte(BH1750_ADDR, BH1750_RESET)
        time.sleep(0.05)

        print("[READY] Sensors initialized")
        print(f"[CONFIG] Brightness idle: {BRIGHTNESS_IDLE:.2f}")
        print(f"[CONFIG] Brightness max: {BRIGHTNESS_MAX:.2f}")
        print(f"[CONFIG] Brightness on exit: {BRIGHTNESS_ON_EXIT:.2f}")
        print(f"[CONFIG] Brightness step: {BRIGHTNESS_STEP:.2f}")
        print(f"[CONFIG] Light read interval: {LIGHT_READ_SECONDS:.2f}s")
        print(
            f"[CONFIG] PIR confirm: {PIR_CONFIRM_SAMPLES} samples, "
            f"{PIR_CONFIRM_SAMPLE_DELAY:.3f}s apart"
        )
        print(f"[CONFIG] PIR startup ignore: {PIR_STARTUP_IGNORE_SECONDS}s")

        while running:
            now = time.monotonic()

            # Read light sensor periodically.
            if now - last_light_read >= LIGHT_READ_SECONDS:
                last_light_read = now

                try:
                    lux = read_bh1750_lux(bus)
                    scaled_light_brightness = scale_lux_to_brightness(lux)

                    print(
                        f"[LIGHT] {lux:.1f} lux -> "
                        f"brightness {scaled_light_brightness:.2f}"
                    )

                except OSError as e:
                    print(f"[ERROR] Could not read BH1750: {e}")

            with state_lock:
                seconds_since_motion = now - last_motion_time

                if last_motion_time > 0 and seconds_since_motion <= DISPLAY_ON_SECONDS:
                    target_brightness = scaled_light_brightness
                else:
                    target_brightness = BRIGHTNESS_IDLE

                target_brightness = clamp(target_brightness, BRIGHTNESS_MIN, BRIGHTNESS_MAX)

            step_brightness_towards_target()

            time.sleep(LOOP_SLEEP_SECONDS)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, handle_shutdown_signal)
    signal.signal(signal.SIGINT, handle_shutdown_signal)

    try:
        main()
    finally:
        print(f"[STOP] Exiting, setting display brightness to {BRIGHTNESS_ON_EXIT:.2f}")
        set_display_brightness(BRIGHTNESS_ON_EXIT)
        sys.exit(0)