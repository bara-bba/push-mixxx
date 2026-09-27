# Quick Start Guide

Get up and running with Mixxx on your Push 2 display in 5 minutes!

## Step 1: Install Dependencies

### Windows
```bash
pip install -r requirements.txt
```
Then install libusb driver using [Zadig](https://zadig.akeo.ie/) - see [setup-windows.md](setup-windows.md)

### Linux/Raspbian
```bash
sudo apt-get install python3-pip libusb-1.0-0 python3-pil
pip3 install -r requirements.txt
sudo cp 99-push2.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
```

## Step 2: Test Push 2 Connection

```bash
python test-push2.py
```

You should see a test pattern with moving elements on your Push 2 display.

## Step 3: Find Your Capture Region

Run Mixxx, then:

```bash
python find-window.py
```

Follow the interactive prompts to determine your capture region coordinates.

## Step 4: Update Configuration

Edit `config.json` with your capture region:

```json
{
  "capture_region": {
    "x": 0,
    "y": 0,
    "width": 1920,
    "height": 320
  },
  "fps_target": 30
}
```

## Step 5: Run the Streamer

```bash
python mixxx-to-push2.py
```

That's it! You should now see Mixxx on your Push 2 display.

## Troubleshooting

### "Push 2 not found"
- Power on Push 2
- Check USB connection
- Windows: Install libusb driver via Zadig
- Linux: Install udev rules

### Display is black
- Verify Mixxx is running
- Check capture region coordinates
- Run `find-window.py` to verify region

### Low FPS
- Reduce capture region size
- Lower `fps_target` in config.json
- Close other applications

## Next Steps

- Read [setup-windows.md](setup-windows.md) for detailed Windows setup
- Read [setup-raspbian.md](setup-raspbian.md) for Raspberry Pi setup
- Customize capture region for your Mixxx layout
- Adjust FPS for your system performance

## Command Line Options

```bash
# Custom capture region
python mixxx-to-push2.py --x 100 --y 100 --width 1920 --height 320

# Custom FPS
python mixxx-to-push2.py --fps 25

# Custom config file
python mixxx-to-push2.py --config my_config.json
```

## Tips for Best Results

1. **Use external power** for Push 2 (brighter display, better performance)
2. **Capture only what you need** - smaller regions = better FPS
3. **Run Mixxx in windowed mode** for easier positioning
4. **Target 25-30 FPS** is usually sufficient for DJ displays
5. **Position Mixxx UI** to show the most important elements in the capture region

## Getting Help

- Check the detailed setup guides for your platform
- Run test scripts to isolate issues
- Verify USB connection with `lsusb` (Linux) or Device Manager (Windows)
