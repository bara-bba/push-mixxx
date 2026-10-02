#!/usr/bin/env python3
"""
Helper script to find window positions and sizes
Useful for determining the correct capture region for Mixxx
"""

import sys

try:
    import mss
    from PIL import Image
    import time
except ImportError:
    print("Error: Required packages not installed")
    print("Run: pip install mss Pillow")
    sys.exit(1)


def list_monitors():
    """List all available monitors"""
    with mss.mss() as sct:
        print("Available Monitors:")
        print("=" * 60)
        
        for i, monitor in enumerate(sct.monitors):
            if i == 0:
                print(f"Monitor {i}: All Monitors Combined")
            else:
                print(f"Monitor {i}: Display {i}")
            
            print(f"  Position: ({monitor['left']}, {monitor['top']})")
            print(f"  Size: {monitor['width']} x {monitor['height']}")
            print()


def capture_preview(x, y, width, height, output_file="preview.png"):
    """Capture a region and save as preview"""
    region = {
        "top": y,
        "left": x,
        "width": width,
        "height": height
    }
    
    print(f"Capturing region: x={x}, y={y}, width={width}, height={height}")
    
    with mss.mss() as sct:
        screenshot = sct.grab(region)
        img = Image.frombytes('RGB', screenshot.size, screenshot.bgra, 'raw', 'BGRX')
        
        # Resize to Push 2 dimensions for preview
        img_resized = img.resize((960, 160), Image.LANCZOS)
        
        # Save both original and resized
        img.save(output_file)
        img_resized.save(output_file.replace('.png', '_push2.png'))
        
        print(f"[OK] Saved preview to {output_file}")
        print(f"[OK] Saved Push 2 preview to {output_file.replace('.png', '_push2.png')}")


def interactive_mode():
    """Interactive mode to help find the right region"""
    print("=" * 60)
    print("Interactive Window Finder")
    print("=" * 60)
    print()
    print("This tool helps you find the correct capture region for Mixxx")
    print()
    
    list_monitors()
    
    print("Tips:")
    print("1. Run Mixxx in windowed mode")
    print("2. Note the window position (top-left corner)")
    print("3. Measure the window size")
    print("4. Enter the values below")
    print()
    
    try:
        x = int(input("Enter X coordinate (left edge): "))
        y = int(input("Enter Y coordinate (top edge): "))
        width = int(input("Enter width: "))
        height = int(input("Enter height: "))
        
        print()
        capture_preview(x, y, width, height)
        
        print()
        print("Config for config.json:")
        print("-" * 60)
        print('{')
        print('  "capture_region": {')
        print(f'    "x": {x},')
        print(f'    "y": {y},')
        print(f'    "width": {width},')
        print(f'    "height": {height}')
        print('  },')
        print('  "fps_target": 30')
        print('}')
        print("-" * 60)
        
    except ValueError:
        print("Error: Please enter valid numbers")
    except KeyboardInterrupt:
        print("\nCancelled")


def continuous_capture(x, y, width, height, interval=1):
    """Continuously capture and display info"""
    region = {
        "top": y,
        "left": x,
        "width": width,
        "height": height
    }
    
    print(f"Capturing region: x={x}, y={y}, width={width}, height={height}")
    print("Press Ctrl+C to stop")
    print()
    
    try:
        with mss.mss() as sct:
            frame_count = 0
            start_time = time.time()
            
            while True:
                screenshot = sct.grab(region)
                frame_count += 1
                
                elapsed = time.time() - start_time
                if elapsed >= 1.0:
                    fps = frame_count / elapsed
                    print(f"Capture FPS: {fps:.1f}", end='\r')
                    frame_count = 0
                    start_time = time.time()
                
                time.sleep(interval)
    
    except KeyboardInterrupt:
        print("\nStopped")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Find window positions for Mixxx capture',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode
  python find_window.py
  
  # List monitors
  python find_window.py --list
  
  # Capture preview
  python find_window.py --x 0 --y 0 --width 1920 --height 320
  
  # Test continuous capture
  python find_window.py --x 0 --y 0 --width 1920 --height 320 --continuous
        """
    )
    
    parser.add_argument('--list', action='store_true', help='List all monitors')
    parser.add_argument('--x', type=int, help='X coordinate')
    parser.add_argument('--y', type=int, help='Y coordinate')
    parser.add_argument('--width', type=int, help='Width')
    parser.add_argument('--height', type=int, help='Height')
    parser.add_argument('--continuous', action='store_true', help='Continuous capture test')
    parser.add_argument('--output', default='preview.png', help='Output file for preview')
    
    args = parser.parse_args()
    
    if args.list:
        list_monitors()
    elif args.x is not None and args.y is not None and args.width and args.height:
        if args.continuous:
            continuous_capture(args.x, args.y, args.width, args.height)
        else:
            capture_preview(args.x, args.y, args.width, args.height, args.output)
    else:
        interactive_mode()


if __name__ == '__main__':
    main()
