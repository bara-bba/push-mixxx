# Installing libusb Backend on Windows

## The Problem

You're seeing: `Error: No backend available`

This means `pyusb` (Python package) is installed, but it needs a system-level USB library to actually communicate with USB devices.

## Solution: Install libusb System Library

### Option 1: Quick Install with libusb DLL (Recommended)

1. **Download libusb**
   - Go to: https://github.com/libusb/libusb/releases
   - Download the latest `libusb-1.0.XX.7z` (e.g., libusb-1.0.27.7z)
   - Or direct link: https://github.com/libusb/libusb/releases/download/v1.0.27/libusb-1.0.27.7z

2. **Extract the archive**
   - Use 7-Zip or Windows built-in extractor
   - Extract to a temporary folder

3. **Copy the DLL to your project**
   
   For 64-bit Python (most common):
   ```
   Copy: libusb-1.0.27\VS2019\MS64\dll\libusb-1.0.dll
   To: C:\Users\loren\OneDrive\Desktop\01-Projects\Push2Screen\
   ```
   
   For 32-bit Python (rare):
   ```
   Copy: libusb-1.0.27\VS2019\MS32\dll\libusb-1.0.dll
   To: C:\Users\loren\OneDrive\Desktop\01-Projects\Push2Screen\
   ```

4. **Test it**
   ```bash
   python check-push2.py
   ```

### Option 2: Install to System Directory

Copy `libusb-1.0.dll` to one of these locations:
- `C:\Windows\System32\` (for 64-bit)
- `C:\Windows\SysWOW64\` (for 32-bit on 64-bit Windows)

**Note**: Requires administrator privileges

### Option 3: Use Zadig (Installs Both Driver and Backend)

If you're going to use Zadig anyway for the driver:

1. Download Zadig: https://zadig.akeo.ie/
2. Run Zadig (it includes libusb)
3. This installs both the driver AND the backend

After Zadig is installed, the backend will be available system-wide.

## How to Check Your Python Architecture

Not sure if you have 32-bit or 64-bit Python?

```bash
python -c "import struct; print(struct.calcsize('P') * 8, 'bit')"
```

This will print either `32 bit` or `64 bit`.

## Verification

After installing libusb, run:

```bash
python check-push2.py
```

You should see:
- "Found X USB devices total" (instead of "No backend available")
- Either "Push 2 DETECTED" or "Push 2 NOT detected" (depending on if it's connected)

## Troubleshooting

### Still getting "No backend available"

1. Make sure `libusb-1.0.dll` is in the same folder as your Python script
2. Or make sure it's in `C:\Windows\System32\`
3. Restart your terminal/PowerShell
4. Try running as Administrator

### "DLL load failed"

- You might have the wrong architecture (32-bit vs 64-bit)
- Check your Python architecture (see above)
- Download the matching libusb version

### Can't extract .7z files

- Download 7-Zip: https://www.7-zip.org/
- Or use an online extractor
- Or I can provide direct DLL download links

## Next Steps

Once you see USB devices listed:
1. Connect and power on Push 2
2. Run `python check-push2.py` again
3. You should see "Push 2 DETECTED"
4. Then proceed with Zadig driver installation (if needed)
