#!/usr/bin/env python3
"""
Check if Push 2 is detected (doesn't require libusb driver)
Safe to run - only checks, doesn't modify anything
"""

import usb.core
import sys


def check_push2():
    """Check if Push 2 is connected"""
    VENDOR_ID = 0x2982
    PRODUCT_ID = 0x1967
    
    print("=" * 60)
    print("Push 2 Detection Check (Safe - No Modifications)")
    print("=" * 60)
    print()
    
    print("Searching for USB devices...")
    
    # List all USB devices
    devices = list(usb.core.find(find_all=True))
    print(f"Found {len(devices)} USB devices total")
    print()
    
    # Look for Push 2
    push2 = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
    
    if push2 is None:
        print("❌ Push 2 NOT detected")
        print()
        print("Possible reasons:")
        print("1. Push 2 is not connected")
        print("2. Push 2 is not powered on")
        print("3. USB cable issue")
        print()
        print("✓ This is safe - no driver needed for detection")
        return False
    
    print("✅ Push 2 DETECTED!")
    print()
    print("Device Information:")
    print(f"  Vendor ID:  0x{push2.idVendor:04x} (Ableton)")
    print(f"  Product ID: 0x{push2.idProduct:04x} (Push 2)")
    print(f"  Bus:        {push2.bus}")
    print(f"  Address:    {push2.address}")
    print()
    
    # Try to read configuration (doesn't require driver)
    try:
        config = push2.get_active_configuration()
        print(f"  Configuration: {config.bConfigurationValue}")
        print(f"  Interfaces: {config.bNumInterfaces}")
    except:
        print("  Configuration: Cannot read (driver not installed)")
    
    print()
    print("Next Steps:")
    print("-" * 60)
    
    # Check if we can access it
    try:
        # Try to claim interface (this will fail without driver)
        if push2.is_kernel_driver_active(0):
            print("✓ Kernel driver is active (default Windows driver)")
            print()
            print("To use Push 2 with this project, you need to:")
            print("1. Install libusb driver using Zadig")
            print("2. See INSTALL_LIBUSB_WINDOWS.md for instructions")
            print()
            print("⚠️  NOTE: This will temporarily disable Push 2 in Ableton Live")
            print("   (You can easily reverse it - see the guide)")
        else:
            print("✓ No kernel driver active")
            print("  Attempting to claim interface...")
            
            try:
                usb.util.claim_interface(push2, 0)
                print("✅ SUCCESS! Interface claimed - libusb driver is working!")
                print()
                print("You can now run:")
                print("  python test_push2.py")
                usb.util.release_interface(push2, 0)
                return True
            except usb.core.USBError as e:
                print(f"❌ Cannot claim interface: {e}")
                print()
                print("You need to install libusb driver using Zadig")
                print("See INSTALL_LIBUSB_WINDOWS.md")
    except Exception as e:
        print(f"Status check: {e}")
    
    return False


def main():
    try:
        check_push2()
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    print()
    print("=" * 60)
    print("Check complete - no changes made to your system")
    print("=" * 60)
    return 0


if __name__ == '__main__':
    sys.exit(main())
