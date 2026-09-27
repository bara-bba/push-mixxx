#!/usr/bin/env python3
"""
Download and install libusb DLL for Windows
"""

import urllib.request
import zipfile
import os
import sys
import shutil

LIBUSB_URL = "https://github.com/libusb/libusb/releases/download/v1.0.27/libusb-1.0.27.7z"
LIBUSB_DIRECT_DLL = "https://github.com/libusb/libusb/releases/download/v1.0.27/libusb-1.0.27-binaries.7z"

def download_file(url, filename):
    """Download a file with progress"""
    print(f"Downloading {filename}...")
    try:
        urllib.request.urlretrieve(url, filename)
        print(f"[OK] Downloaded {filename}")
        return True
    except Exception as e:
        print(f"[X] Failed to download: {e}")
        return False

def main():
    print("=" * 60)
    print("libusb DLL Installer for Windows")
    print("=" * 60)
    print()
    print("You have 64-bit Python")
    print()
    
    # Check if libusb-1.0.dll already exists
    if os.path.exists("libusb-1.0.dll"):
        print("[OK] libusb-1.0.dll already exists in current directory")
        print()
        response = input("Re-download? (y/n): ")
        if response.lower() != 'y':
            print("Skipping download")
            return 0
    
    print("Option 1: Manual Download (Recommended)")
    print("-" * 60)
    print("1. Go to: https://github.com/libusb/libusb/releases")
    print("2. Download: libusb-1.0.27.7z (or latest version)")
    print("3. Extract the archive")
    print("4. Copy this file to your project folder:")
    print("   libusb-1.0.27\\VS2019\\MS64\\dll\\libusb-1.0.dll")
    print()
    print("   To: C:\\Users\\loren\\OneDrive\\Desktop\\01-Projects\\Push2Screen\\")
    print()
    
    print("Option 2: Use Zadig (Easiest)")
    print("-" * 60)
    print("Zadig includes libusb and installs it system-wide")
    print("1. Download: https://zadig.akeo.ie/")
    print("2. Run Zadig")
    print("3. This installs libusb automatically")
    print()
    
    print("Option 3: Direct DLL Download")
    print("-" * 60)
    print("I can try to download a pre-extracted DLL")
    print("(This might not work due to GitHub's file format)")
    print()
    
    response = input("Try automatic download? (y/n): ")
    if response.lower() == 'y':
        print()
        print("Attempting to download libusb DLL...")
        print("Note: This requires 7-Zip to extract .7z files")
        print()
        
        # Try to download
        if download_file(LIBUSB_URL, "libusb-1.0.27.7z"):
            print()
            print("[OK] Downloaded libusb-1.0.27.7z")
            print()
            print("Next steps:")
            print("1. Extract libusb-1.0.27.7z (use 7-Zip)")
            print("2. Copy: libusb-1.0.27\\VS2019\\MS64\\dll\\libusb-1.0.dll")
            print("3. To: " + os.getcwd())
            print()
            print("Or just use Zadig - it's easier!")
    
    print()
    print("=" * 60)
    print("After installing libusb, run: python check_push2.py")
    print("=" * 60)
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
