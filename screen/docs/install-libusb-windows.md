# Installing libusb Driver on Windows (Required!)

## Why You Need This

Windows doesn't have a generic USB driver for the Push 2 display interface. You need to install libusb driver using Zadig.

## Step-by-Step Instructions

### 1. Download Zadig

Go to: https://zadig.akeo.ie/

Download the latest version (zadig-2.8.exe or newer)

### 2. Connect and Power On Push 2

- Connect Push 2 via USB
- Power on Push 2 (use external power supply if available)

### 3. Run Zadig as Administrator

- Right-click on zadig.exe
- Select "Run as administrator"

### 4. Configure Zadig

1. In Zadig, go to **Options** → **List All Devices**
2. From the dropdown, select **"Ableton Push 2"**
3. In the driver selection (green arrow area):
   - Target driver should show **"libusbK"** or **"libusb-win32"**
   - If it shows something else, use the up/down arrows to select one of these
4. Click **"Replace Driver"** or **"Install Driver"**

### 5. Wait for Installation

The installation takes 1-2 minutes. You'll see a progress bar.

### 6. Verify Installation

After installation completes, you should see:
- "The driver was installed successfully" message
- Push 2 should still be powered on

### 7. Test the Connection

```bash
python test-push2.py
```

You should see:
```
✓ Found Push 2: ...
✓ Claimed USB interface
✓ Push 2 connected successfully!
```

## Troubleshooting

### "Ableton Push 2" not in the list

- Make sure Push 2 is powered on
- Try a different USB port
- Unplug and replug the USB cable
- In Zadig: Options → List All Devices (make sure it's checked)

### "Access Denied" or "Cannot install driver"

- Close Zadig
- Right-click and "Run as administrator"
- Try again

### Driver installation fails

- Disable antivirus temporarily
- Try using "libusb-win32" instead of "libusbK"
- Restart computer and try again

### Push 2 stops working with Ableton Live

The libusb driver replaces the default driver. To use Push 2 with Ableton Live again:

1. Open Device Manager (Win + X → Device Manager)
2. Find "Ableton Push 2" under "libusbK USB Devices" or "libusb-win32 devices"
3. Right-click → "Uninstall device"
4. Check "Delete the driver software for this device"
5. Unplug and replug Push 2
6. Windows will reinstall the default driver

To switch back to this project, run Zadig again.

## Alternative: Use Both

If you want to use Push 2 with both Ableton Live and this project:

1. Use Push 2 with Live normally
2. When you want to use this project:
   - Close Ableton Live
   - Run Zadig and install libusb driver
   - Use this project
3. To switch back:
   - Uninstall libusb driver in Device Manager
   - Restart Push 2
   - Use with Ableton Live

## Next Steps

Once libusb driver is installed:

1. Test connection: `python test-push2.py`
2. Find your Mixxx window: `python find-window.py`
3. Run the streamer: `python mixxx-to-push2.py`
