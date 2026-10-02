# Raspbian/Linux Setup Guide

## Prerequisites

- Raspberry Pi 3 or newer (Pi 4 recommended for better performance)
- Raspbian Buster or newer
- Ableton Push 2
- USB 2.0 port
- External power supply for Push 2 (recommended)

## Installation Steps

### 1. Update System

```bash
sudo apt-get update
sudo apt-get upgrade
```

### 2. Install System Dependencies

```bash
sudo apt-get install -y \
    python3-pip \
    python3-dev \
    libusb-1.0-0 \
    libusb-1.0-0-dev \
    python3-pil \
    python3-numpy
```

### 3. Install Python Dependencies

```bash
pip3 install -r requirements.txt
```

### 4. Set Up USB Permissions

```bash
# Copy udev rules
sudo cp 99-push2.rules /etc/udev/rules.d/

# Reload udev rules
sudo udevadm control --reload-rules
sudo udevadm trigger

# Add your user to plugdev group
sudo usermod -a -G plugdev $USER

# Log out and back in for group changes to take effect
```

### 5. Connect Push 2

- Connect USB cable to Raspberry Pi
- Power on Push 2
- Verify connection:
  ```bash
  lsusb | grep 2982:1967
  ```
  You should see: `Bus XXX Device XXX: ID 2982:1967 Ableton AG`

### 6. Test Connection

```bash
python3 test-push2.py
```

## Running with Mixxx

### 1. Install Mixxx

```bash
sudo apt-get install mixxx
```

### 2. Configure Display

If running headless (no monitor), you'll need a virtual display:

```bash
sudo apt-get install xvfb

# Start virtual display
Xvfb :1 -screen 0 1920x1080x24 &
export DISPLAY=:1

# Run Mixxx
mixxx &
```

### 3. Run the Streamer

```bash
python3 mixxx-to-push2.py
```

## Auto-Start on Boot

Create a systemd service:

```bash
sudo nano /etc/systemd/system/mixxx-push2.service
```

Add:

```ini
[Unit]
Description=Mixxx to Push 2 Display
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/mixxx-to-push2
ExecStart=/usr/bin/python3 /home/pi/mixxx-to-push2/mixxx-to-push2.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable mixxx-push2.service
sudo systemctl start mixxx-push2.service
sudo systemctl status mixxx-push2.service
```

## Performance Optimization

### 1. Overclock (Pi 4)

Edit `/boot/config.txt`:

```bash
sudo nano /boot/config.txt
```

Add:

```
over_voltage=6
arm_freq=2000
gpu_freq=750
```

Reboot:

```bash
sudo reboot
```

### 2. Reduce Capture Region

Edit `config.json` to capture only what you need:

```json
{
  "capture_region": {
    "x": 0,
    "y": 0,
    "width": 960,
    "height": 160
  },
  "fps_target": 25
}
```

### 3. Disable Desktop Environment (Headless)

```bash
sudo systemctl set-default multi-user.target
sudo reboot
```

To re-enable:

```bash
sudo systemctl set-default graphical.target
sudo reboot
```

## Troubleshooting

### Permission Denied

```bash
# Check udev rules
ls -l /etc/udev/rules.d/99-push2.rules

# Verify group membership
groups $USER

# Should include 'plugdev'
```

### Low Frame Rate on Raspberry Pi

- Use Pi 4 for better performance
- Reduce capture region size
- Lower fps_target to 20-25
- Ensure external power for Push 2
- Close unnecessary services
- Consider overclocking

### USB Device Not Found

```bash
# Check USB devices
lsusb

# Check dmesg for errors
dmesg | grep -i usb

# Try different USB port
```

### Display Timeout

The Push 2 display turns off after 2 seconds without frames. The script continuously sends frames to prevent this.

## Remote Access

To control from another machine:

```bash
# On Raspberry Pi
sudo apt-get install openssh-server

# From another machine
ssh pi@raspberrypi.local
```

## Monitoring

View logs:

```bash
# If running as service
sudo journalctl -u mixxx-push2.service -f

# If running manually
python3 mixxx-to-push2.py 2>&1 | tee output.log
```
