# Windows Setup Guide

## Prerequisites

1. **Python 3.7 or higher**
   - Download from: https://www.python.org/downloads/
   - During installation, check "Add Python to PATH"

2. **libusb**
   - Download Zadig: https://zadig.akeo.ie/
   - Run Zadig as Administrator
   - Options → List All Devices
   - Select "Ableton Push 2" from dropdown
   - Select "libusb-win32" or "libusbK" driver
   - Click "Replace Driver" or "Install Driver"

## Installation Steps

1. **Clone or download this repository**

2. **Open Command Prompt or PowerShell in the project directory**

3. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Connect your Push 2**
   - Connect USB cable
   - Power on Push 2 (external power recommended)

5. **Test the connection:**
   ```bash
   python test-push2.py
   ```

## Running the Application

1. **Start Mixxx DJ software**

2. **Position Mixxx window where you want to capture**

3. **Edit config.json to match your screen setup:**
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

4. **Run the streamer:**
   ```bash
   python mixxx-to-push2.py
   ```

## Troubleshooting

### "Push 2 not found"
- Ensure Push 2 is powered on
- Check USB connection
- Verify libusb driver is installed via Zadig
- Try a different USB port

### "Access Denied" or Permission Errors
- Run Command Prompt as Administrator
- Reinstall libusb driver via Zadig

### Low Frame Rate
- Close other applications
- Reduce capture region size
- Lower fps_target in config.json
- Ensure Push 2 has external power supply

### Display is Black
- Check that Mixxx is running in the capture region
- Verify capture coordinates in config.json
- Try running test-push2.py to verify Push 2 works

## Finding the Right Capture Region

1. Run Mixxx in windowed mode
2. Note the window position (top-left corner coordinates)
3. Measure window width and height
4. Update config.json with these values
5. You can also use command line:
   ```bash
   python mixxx-to-push2.py --x 100 --y 100 --width 1920 --height 320
   ```

## Performance Tips

- Use external power supply for Push 2 (brighter display, better performance)
- Close unnecessary applications
- Run Mixxx in windowed mode at a reasonable size
- Capture only the area you need (not full screen)
- Target 25-30 FPS is usually sufficient
