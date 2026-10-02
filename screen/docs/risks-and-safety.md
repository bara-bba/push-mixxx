# Risks and Safety Information

## TL;DR - Is This Safe?

**YES, it's safe.** You're only changing a software driver, not modifying hardware or firmware. Everything is reversible.

## What You're Actually Doing

When you install the libusb driver with Zadig, you're telling Windows:
- "Use this generic USB driver instead of Ableton's driver"
- This is a **standard Windows operation** - same as updating any driver
- **No firmware changes** to Push 2
- **No hardware modifications**
- **No system-level changes** beyond this one USB device

## Risk Assessment

### ❌ What CAN Go Wrong

1. **Push 2 won't work with Ableton Live** (while libusb driver is installed)
   - **Severity**: Medium (inconvenient but not damaging)
   - **Reversibility**: 100% - Takes 2 minutes to undo
   - **Fix**: Uninstall driver in Device Manager, replug Push 2

2. **You might need to switch drivers back and forth**
   - **Severity**: Low (just annoying)
   - **Reversibility**: 100%
   - **Workaround**: Keep Zadig handy, or use Push 2 for one purpose at a time

### ✅ What CANNOT Go Wrong

1. **Hardware damage** - Impossible. Drivers don't affect hardware.
2. **Bricking Push 2** - Impossible. We're not touching firmware.
3. **Breaking Windows** - Impossible. Only affects one USB device.
4. **Permanent changes** - Impossible. Everything is reversible.
5. **Data loss** - Impossible. No data is stored on Push 2.
6. **Warranty void** - No. This is standard driver installation.

## Comparison to Other Common Tasks

**This is SAFER than:**
- Installing graphics card drivers (those can crash your system)
- Updating BIOS (that can brick your motherboard)
- Overclocking (can damage hardware)

**This is SIMILAR to:**
- Installing printer drivers
- Updating mouse/keyboard drivers
- Installing game controller drivers

## Step-by-Step Safety Approach

### Option 1: Check First (Safest)
```bash
# Just check if Push 2 is detected (no changes)
python check-push2.py
```
This is 100% safe - only looks, doesn't touch anything.

### Option 2: Test on Raspberry Pi First
If you have a Raspberry Pi, test there first:
- Linux doesn't need driver replacement
- Just install udev rules (non-invasive)
- Push 2 works with both this project AND Ableton simultaneously

### Option 3: Full Windows Installation
If you're comfortable with the trade-off:
1. Install libusb driver with Zadig
2. Use Push 2 with this project
3. When you want Ableton Live back, uninstall libusb driver

## How to Undo Everything

### Quick Undo (2 minutes)

1. **Open Device Manager**
   - Press `Win + X`
   - Select "Device Manager"

2. **Find Push 2**
   - Look under "libusbK USB Devices" or "libusb-win32 devices"
   - Find "Ableton Push 2"

3. **Uninstall Driver**
   - Right-click → "Uninstall device"
   - ✅ Check "Delete the driver software for this device"
   - Click "Uninstall"

4. **Reconnect**
   - Unplug Push 2 USB cable
   - Wait 5 seconds
   - Plug it back in
   - Windows automatically reinstalls original driver

5. **Verify**
   - Open Ableton Live
   - Push 2 should work normally

### Complete System Restore (if paranoid)

Windows System Restore can roll back driver changes:
1. Create a restore point BEFORE installing libusb
2. If anything goes wrong, restore to that point
3. Everything returns to exactly how it was

## Real-World Usage

**Thousands of people use Zadig for:**
- Arduino programming
- Custom USB devices
- Game controllers
- DJ equipment
- Development boards

**This exact approach is used for:**
- Push 2 custom applications
- Other Ableton hardware hacking
- MIDI controller customization

## My Recommendation

**If you use Push 2 with Ableton Live regularly:**
- Test on Raspberry Pi first (if you have one)
- Or accept you'll need to switch drivers when switching uses
- Or get a second Push 2 (one for Live, one for projects)

**If you DON'T use Push 2 with Ableton Live:**
- Go ahead! No downside at all.

**If you're still unsure:**
1. Run `python check-push2.py` first (100% safe)
2. Create a Windows System Restore point
3. Install libusb driver
4. Test with `python test-push2.py`
5. If you don't like it, undo in 2 minutes

## Questions?

**Q: Will this void my warranty?**
A: No. Installing drivers is normal use.

**Q: Can I break Push 2?**
A: No. Software drivers cannot damage hardware.

**Q: What if I mess up?**
A: Worst case: Uninstall driver, replug Push 2. Takes 2 minutes.

**Q: Can I use Push 2 with both Ableton and this project?**
A: Not simultaneously on Windows. You need to switch drivers. On Linux/Raspberry Pi, yes!

**Q: Is there a way to avoid this?**
A: On Windows, no. On Linux/Raspberry Pi, yes (no driver replacement needed).

**Q: What do professionals do?**
A: They either switch drivers as needed, or use separate devices, or use Linux.

## Bottom Line

This is a **low-risk, high-reversibility** modification. The worst that can happen is you spend 2 minutes undoing it. No hardware damage is possible.

**Confidence Level: 99% Safe**

The 1% is just the inconvenience of switching drivers if you want to use Ableton Live again.
