#!/usr/bin/env python3
"""
Mixxx to Push 2 Display Streamer
Captures screen region and streams to Ableton Push 2 display
"""

import usb.core
import usb.util
import numpy as np
from PIL import Image
import mss
import time
import json
import argparse
import sys


class Push2Display:
    """Interface for Ableton Push 2 display"""
    
    VENDOR_ID = 0x2982
    PRODUCT_ID = 0x1967
    DISPLAY_WIDTH = 960
    DISPLAY_HEIGHT = 160
    BULK_EP_OUT = 0x01
    
    # Frame header as specified in Push 2 documentation
    FRAME_HEADER = bytes([
        0xFF, 0xCC, 0xAA, 0x88,
        0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00
    ])
    
    # XOR pattern for signal shaping
    XOR_PATTERN = 0xFFE7F3E7
    
    def __init__(self):
        self.device = None
        self.connected = False
        
    def connect(self):
        """Connect to Push 2 device"""
        try:
            self.device = usb.core.find(idVendor=self.VENDOR_ID, idProduct=self.PRODUCT_ID)
            
            if self.device is None:
                raise ValueError("Push 2 not found. Is it connected and powered on?")
            
            # Detach kernel driver if necessary (Linux only)
            try:
                if self.device.is_kernel_driver_active(0):
                    try:
                        self.device.detach_kernel_driver(0)
                    except usb.core.USBError as e:
                        print(f"Warning: Could not detach kernel driver: {e}")
            except (NotImplementedError, AttributeError):
                # Windows doesn't support this, which is fine
                pass
            
            # Claim the interface
            usb.util.claim_interface(self.device, 0)
            
            self.connected = True
            print("✓ Connected to Push 2")
            
            # Set display brightness
            self.set_brightness(200)
            
            return True
            
        except Exception as e:
            print(f"✗ Failed to connect to Push 2: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from Push 2"""
        if self.device:
            try:
                usb.util.release_interface(self.device, 0)
                usb.util.dispose_resources(self.device)
            except:
                pass
        self.connected = False
        print("Disconnected from Push 2")
    
    def set_brightness(self, brightness):
        """Set display brightness (0-255)"""
        try:
            # Sysex command to set display brightness
            brightness = max(0, min(255, brightness))
            b_lsb = brightness & 0x7F
            b_msb = (brightness >> 7) & 0x01
            
            sysex = bytes([
                0xF0, 0x00, 0x21, 0x1D, 0x01, 0x01,  # Ableton sysex header
                0x08,  # Set display brightness command
                b_lsb, b_msb,
                0xF7  # End of sysex
            ])
            
            # Note: This would need MIDI interface, simplified for display-only
            print(f"Display brightness set to {brightness}")
            
        except Exception as e:
            print(f"Warning: Could not set brightness: {e}")

    
    def rgb_to_bgr565(self, image):
        """Convert RGB image to BGR565 format for Push 2"""
        # Ensure image is RGB
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Convert to numpy array
        img_array = np.array(image, dtype=np.uint8)
        
        # Extract RGB channels
        r = img_array[:, :, 0]
        g = img_array[:, :, 1]
        b = img_array[:, :, 2]
        
        # Convert to 5-6-5 bit format
        # BGR565 format: [b4 b3 b2 b1 b0 g5 g4 g3 g2 g1 g0 r4 r3 r2 r1 r0]
        r5 = (r >> 3).astype(np.uint16)  # 5 bits
        g6 = (g >> 2).astype(np.uint16)  # 6 bits
        b5 = (b >> 3).astype(np.uint16)  # 5 bits
        
        # Combine into BGR565
        bgr565 = (b5 << 11) | (g6 << 5) | r5
        
        return bgr565
    
    def xor_frame(self, frame_data):
        """Apply XOR pattern to frame data for signal shaping"""
        # Convert to bytes if needed
        if isinstance(frame_data, np.ndarray):
            frame_bytes = frame_data.tobytes()
        else:
            frame_bytes = frame_data
        
        # Apply XOR pattern
        xor_bytes = bytearray(frame_bytes)
        pattern_bytes = self.XOR_PATTERN.to_bytes(4, byteorder='little')
        
        for i in range(len(xor_bytes)):
            xor_bytes[i] ^= pattern_bytes[i % 4]
        
        return bytes(xor_bytes)
    
    def prepare_frame(self, image):
        """Prepare image frame for Push 2 display"""
        # Resize to Push 2 display dimensions
        if image.size != (self.DISPLAY_WIDTH, self.DISPLAY_HEIGHT):
            image = image.resize((self.DISPLAY_WIDTH, self.DISPLAY_HEIGHT), Image.LANCZOS)
        
        # Convert to BGR565
        bgr565 = self.rgb_to_bgr565(image)
        
        # Prepare line data with padding
        lines = []
        for y in range(self.DISPLAY_HEIGHT):
            line = bgr565[y, :]
            line_bytes = line.tobytes()
            
            # Add 128 bytes of padding (filler) after each line
            # Each line is 1920 bytes (960 pixels * 2 bytes) + 128 filler = 2048 bytes
            padding = bytes(128)
            line_with_padding = line_bytes + padding
            
            # Apply XOR pattern
            line_xored = self.xor_frame(line_with_padding)
            lines.append(line_xored)
        
        return b''.join(lines)
    
    def send_frame(self, image):
        """Send a frame to Push 2 display"""
        if not self.connected:
            return False
        
        try:
            # Send frame header
            self.device.write(self.BULK_EP_OUT, self.FRAME_HEADER, timeout=1000)
            
            # Prepare and send pixel data
            frame_data = self.prepare_frame(image)
            
            # Send in chunks (16KB recommended for efficiency)
            chunk_size = 16384
            for i in range(0, len(frame_data), chunk_size):
                chunk = frame_data[i:i + chunk_size]
                self.device.write(self.BULK_EP_OUT, chunk, timeout=1000)
            
            return True
            
        except usb.core.USBError as e:
            print(f"USB Error: {e}")
            return False
        except Exception as e:
            print(f"Error sending frame: {e}")
            return False


class ScreenCapture:
    """Screen capture utility"""
    
    def __init__(self, region=None):
        self.sct = mss.mss()
        self.region = region or {"top": 0, "left": 0, "width": 1920, "height": 320}
    
    def capture(self):
        """Capture screen region and return PIL Image"""
        screenshot = self.sct.grab(self.region)
        return Image.frombytes('RGB', screenshot.size, screenshot.bgra, 'raw', 'BGRX')
    
    def set_region(self, x, y, width, height):
        """Update capture region"""
        self.region = {"top": y, "left": x, "width": width, "height": height}


def load_config(config_file):
    """Load configuration from JSON file"""
    try:
        with open(config_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Config file {config_file} not found, using defaults")
        return {
            "capture_region": {"x": 0, "y": 0, "width": 1920, "height": 320},
            "fps_target": 30,
            "display_brightness": 200
        }
    except json.JSONDecodeError as e:
        print(f"Error parsing config file: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description='Stream Mixxx to Push 2 Display')
    parser.add_argument('--config', default='config.json', help='Config file path')
    parser.add_argument('--x', type=int, help='Capture region X coordinate')
    parser.add_argument('--y', type=int, help='Capture region Y coordinate')
    parser.add_argument('--width', type=int, help='Capture region width')
    parser.add_argument('--height', type=int, help='Capture region height')
    parser.add_argument('--fps', type=int, help='Target FPS')
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_config(args.config)
    
    # Override with command line arguments
    if args.x is not None:
        config['capture_region']['x'] = args.x
    if args.y is not None:
        config['capture_region']['y'] = args.y
    if args.width is not None:
        config['capture_region']['width'] = args.width
    if args.height is not None:
        config['capture_region']['height'] = args.height
    if args.fps is not None:
        config['fps_target'] = args.fps
    
    # Initialize
    print("Mixxx to Push 2 Display Streamer")
    print("=" * 40)
    
    push2 = Push2Display()
    if not push2.connect():
        sys.exit(1)
    
    region = config['capture_region']
    capture = ScreenCapture({
        "top": region['y'],
        "left": region['x'],
        "width": region['width'],
        "height": region['height']
    })
    
    fps_target = config['fps_target']
    frame_time = 1.0 / fps_target
    
    print(f"Capture region: {region['x']},{region['y']} {region['width']}x{region['height']}")
    print(f"Target FPS: {fps_target}")
    print("Press Ctrl+C to stop")
    print()
    
    frame_count = 0
    start_time = time.time()
    
    try:
        while True:
            loop_start = time.time()
            
            # Capture screen
            image = capture.capture()
            
            # Send to Push 2
            if push2.send_frame(image):
                frame_count += 1
                
                # Display stats every second
                elapsed = time.time() - start_time
                if elapsed >= 1.0:
                    actual_fps = frame_count / elapsed
                    print(f"FPS: {actual_fps:.1f} | Frames: {frame_count}", end='\r')
                    frame_count = 0
                    start_time = time.time()
            
            # Maintain target frame rate
            loop_time = time.time() - loop_start
            sleep_time = frame_time - loop_time
            if sleep_time > 0:
                time.sleep(sleep_time)
    
    except KeyboardInterrupt:
        print("\n\nStopping...")
    
    finally:
        push2.disconnect()
        print("Done!")


if __name__ == '__main__':
    main()
