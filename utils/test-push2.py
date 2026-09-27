#!/usr/bin/env python3
"""
Test script for Push 2 connection and display
Shows a test pattern on the Push 2 display
"""

import usb.core
import usb.util
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import time
import sys


def find_push2():
    """Find and connect to Push 2"""
    VENDOR_ID = 0x2982
    PRODUCT_ID = 0x1967
    
    print("Searching for Push 2...")
    device = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
    
    if device is None:
        print("✗ Push 2 not found!")
        print("\nTroubleshooting:")
        print("1. Is Push 2 powered on?")
        print("2. Is USB cable connected?")
        print("3. On Windows: Is libusb driver installed? (Use Zadig)")
        print("4. On Linux: Are udev rules installed?")
        return None
    
    print(f"✓ Found Push 2: {device}")
    
    # Detach kernel driver if necessary (Linux only)
    try:
        if device.is_kernel_driver_active(0):
            try:
                device.detach_kernel_driver(0)
                print("✓ Detached kernel driver")
            except usb.core.USBError as e:
                print(f"Warning: Could not detach kernel driver: {e}")
    except NotImplementedError:
        # Windows doesn't support this, which is fine
        pass
    
    # Claim the interface
    try:
        usb.util.claim_interface(device, 0)
        print("✓ Claimed USB interface")
    except usb.core.USBError as e:
        print(f"✗ Could not claim interface: {e}")
        return None
    
    return device


def create_test_pattern(frame_num):
    """Create a test pattern image"""
    width, height = 960, 160
    
    # Create image
    img = Image.new('RGB', (width, height), color='black')
    draw = ImageDraw.Draw(img)
    
    # Draw gradient background
    for y in range(height):
        color_val = int((y / height) * 255)
        draw.rectangle([(0, y), (width, y+1)], fill=(color_val, 0, 255-color_val))
    
    # Draw moving bar
    bar_x = (frame_num * 10) % width
    draw.rectangle([(bar_x, 0), (bar_x + 50, height)], fill=(255, 255, 0))
    
    # Draw text
    try:
        font = ImageFont.truetype("arial.ttf", 40)
    except:
        font = ImageFont.load_default()
    
    text = f"Push 2 Test - Frame {frame_num}"
    
    # Get text bounding box for centering
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    text_x = (width - text_width) // 2
    text_y = (height - text_height) // 2
    
    # Draw text with outline
    for offset_x in [-2, 0, 2]:
        for offset_y in [-2, 0, 2]:
            draw.text((text_x + offset_x, text_y + offset_y), text, font=font, fill=(0, 0, 0))
    draw.text((text_x, text_y), text, font=font, fill=(255, 255, 255))
    
    return img


def rgb_to_bgr565(image):
    """Convert RGB image to BGR565 format"""
    img_array = np.array(image, dtype=np.uint8)
    
    r = img_array[:, :, 0]
    g = img_array[:, :, 1]
    b = img_array[:, :, 2]
    
    r5 = (r >> 3).astype(np.uint16)
    g6 = (g >> 2).astype(np.uint16)
    b5 = (b >> 3).astype(np.uint16)
    
    bgr565 = (b5 << 11) | (g6 << 5) | r5
    
    return bgr565


def xor_frame(frame_bytes):
    """Apply XOR pattern for signal shaping"""
    XOR_PATTERN = 0xFFE7F3E7
    xor_bytes = bytearray(frame_bytes)
    pattern_bytes = XOR_PATTERN.to_bytes(4, byteorder='little')
    
    for i in range(len(xor_bytes)):
        xor_bytes[i] ^= pattern_bytes[i % 4]
    
    return bytes(xor_bytes)


def prepare_frame(image):
    """Prepare frame for Push 2"""
    bgr565 = rgb_to_bgr565(image)
    
    lines = []
    for y in range(160):
        line = bgr565[y, :]
        line_bytes = line.tobytes()
        padding = bytes(128)
        line_with_padding = line_bytes + padding
        line_xored = xor_frame(line_with_padding)
        lines.append(line_xored)
    
    return b''.join(lines)


def send_frame(device, image):
    """Send frame to Push 2"""
    FRAME_HEADER = bytes([
        0xFF, 0xCC, 0xAA, 0x88,
        0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00
    ])
    
    BULK_EP_OUT = 0x01
    
    try:
        # Send header
        device.write(BULK_EP_OUT, FRAME_HEADER, timeout=1000)
        
        # Prepare and send pixel data
        frame_data = prepare_frame(image)
        
        # Send in 16KB chunks
        chunk_size = 16384
        for i in range(0, len(frame_data), chunk_size):
            chunk = frame_data[i:i + chunk_size]
            device.write(BULK_EP_OUT, chunk, timeout=1000)
        
        return True
    except Exception as e:
        print(f"Error sending frame: {e}")
        return False


def main():
    print("=" * 50)
    print("Push 2 Display Test")
    print("=" * 50)
    print()
    
    device = find_push2()
    if device is None:
        sys.exit(1)
    
    print()
    print("✓ Push 2 connected successfully!")
    print()
    print("Sending test pattern...")
    print("Press Ctrl+C to stop")
    print()
    
    frame_num = 0
    start_time = time.time()
    
    try:
        while True:
            # Create test pattern
            image = create_test_pattern(frame_num)
            
            # Send to Push 2
            if send_frame(device, image):
                frame_num += 1
                
                # Show FPS every second
                elapsed = time.time() - start_time
                if elapsed >= 1.0:
                    fps = frame_num / elapsed
                    print(f"FPS: {fps:.1f} | Frames: {frame_num}", end='\r')
                    frame_num = 0
                    start_time = time.time()
            
            time.sleep(1/30)  # 30 FPS
    
    except KeyboardInterrupt:
        print("\n\nStopping...")
    
    finally:
        # Cleanup
        try:
            usb.util.release_interface(device, 0)
            usb.util.dispose_resources(device)
        except:
            pass
        print("✓ Test complete!")


if __name__ == '__main__':
    main()
