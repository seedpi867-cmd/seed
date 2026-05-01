#!/bin/bash
# Scan and test GPIO pins
# Usage: bash tools/gpio-scan.sh [blink PIN]

MODE="${1:-scan}"
PIN="${2:-18}"

if [ "$MODE" = "scan" ]; then
  echo "═══ GPIO Scan ═══"
  echo ""

  # Check available interfaces
  echo "── Available GPIO chips ──"
  ls /dev/gpiochip* 2>/dev/null || echo "No gpiochip devices"
  echo ""

  echo "── Exported GPIOs ──"
  ls /sys/class/gpio/gpio* 2>/dev/null || echo "None exported"
  echo ""

  echo "── Pin functions (device tree) ──"
  if command -v raspi-gpio &>/dev/null; then
    raspi-gpio get 2>/dev/null | head -30
  elif command -v pinctrl &>/dev/null; then
    pinctrl 2>/dev/null | head -30
  else
    echo "No pin inspection tool — try: sudo apt install raspi-gpio"
  fi
  echo ""

  # Python GPIO test
  python3 -c "
try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    print('RPi.GPIO: available (BCM mode)')
    GPIO.cleanup()
except Exception as e:
    print(f'RPi.GPIO: {e}')
try:
    from gpiozero import Device
    print(f'gpiozero: available (factory: {Device._default_pin_factory})')
except Exception as e:
    print(f'gpiozero: {e}')
" 2>/dev/null

elif [ "$MODE" = "blink" ]; then
  echo "Blinking GPIO $PIN for 5 seconds..."
  python3 -c "
import RPi.GPIO as GPIO
import time
GPIO.setmode(GPIO.BCM)
GPIO.setup($PIN, GPIO.OUT)
for i in range(10):
    GPIO.output($PIN, GPIO.HIGH)
    time.sleep(0.25)
    GPIO.output($PIN, GPIO.LOW)
    time.sleep(0.25)
GPIO.cleanup()
print('Done blinking pin $PIN')
" 2>/dev/null
fi
