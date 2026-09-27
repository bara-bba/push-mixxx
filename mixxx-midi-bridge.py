#!/usr/bin/env python3
"""
MIDI Bridge between Mixxx and Push 2
Reads Mixxx MIDI output and renders custom displays on Push 2
Also sends Push 2 button presses back to Mixxx
"""

import mido
from PIL import Image, ImageDraw, ImageFont
import threading
import time
from mixxx_to_push2 import Push2Display


class MixxxState:
    """Track Mixxx state"""
    def __init__(self):
        self.deck1 = {
            'playing': False,
            'bpm': 0,
            'title': '',
            'artist': '',
            'position': 0.0,
            'duration': 0,
            'volume': 0.5
        }
        self.deck2 = {
            'playing': False,
            'bpm': 0,
            'title': '',
            'artist': '',
            'position': 0.0,
            'duration': 0,
            'volume': 0.5
        }
        self.crossfader = 0.5


class MixxxMidiBridge:
    """Bridge between Mixxx MIDI and Push 2"""
    
    def __init__(self):
        self.push2 = Push2Display()
        self.state = MixxxState()
        self.running = False
        self.midi_in = None
        self.midi_out = None
        
    def list_midi_ports(self):
        """List available MIDI ports"""
        print("Available MIDI Input Ports:")
        for port in mido.get_input_names():
            print(f"  - {port}")
        print()
        print("Available MIDI Output Ports:")
        for port in mido.get_output_names():
            print(f"  - {port}")
        print()
    
    def connect_midi(self, input_port=None, output_port=None):
        """Connect to Mixxx MIDI ports"""
        try:
            # Find Mixxx ports if not specified
            if input_port is None:
                for port in mido.get_input_names():
                    if 'Mixxx' in port or 'MIDI' in port:
                        input_port = port
                        break
            
            if output_port is None:
                for port in mido.get_output_names():
                    if 'Mixxx' in port or 'MIDI' in port:
                        output_port = port
                        break
            
            if input_port:
                self.midi_in = mido.open_input(input_port)
                print(f"✓ Connected to MIDI input: {input_port}")
            
            if output_port:
                self.midi_out = mido.open_output(output_port)
                print(f"✓ Connected to MIDI output: {output_port}")
            
            return True
            
        except Exception as e:
            print(f"✗ MIDI connection failed: {e}")
            return False
    
    def process_midi_message(self, msg):
        """Process incoming MIDI from Mixxx"""
        if msg.type == 'note_on':
            # Button presses (play, cue, etc.)
            if msg.note == 0x00:  # Deck 1 play
                self.state.deck1['playing'] = msg.velocity > 0
            elif msg.note == 0x10:  # Deck 2 play
                self.state.deck2['playing'] = msg.velocity > 0
                
        elif msg.type == 'control_change':
            # Continuous controls (volume, position, etc.)
            if msg.control == 0x07:  # Deck 1 volume
                self.state.deck1['volume'] = msg.value / 127.0
            elif msg.control == 0x08:  # Deck 2 volume
                self.state.deck2['volume'] = msg.value / 127.0
            elif msg.control == 0x0F:  # Crossfader
                self.state.crossfader = msg.value / 127.0
    
    def midi_listener(self):
        """Listen for MIDI messages from Mixxx"""
        if not self.midi_in:
            return
        
        print("Listening for MIDI from Mixxx...")
        for msg in self.midi_in:
            if not self.running:
                break
            self.process_midi_message(msg)
    
    def render_display(self):
        """Render custom display for Push 2"""
        # Create image
        img = Image.new('RGB', (960, 160), color=(0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        try:
            font_large = ImageFont.truetype("arial.ttf", 30)
            font_medium = ImageFont.truetype("arial.ttf", 20)
            font_small = ImageFont.truetype("arial.ttf", 16)
        except:
            font_large = ImageFont.load_default()
            font_medium = ImageFont.load_default()
            font_small = ImageFont.load_default()
        
        # Split display: Deck 1 on left, Deck 2 on right
        mid_x = 480
        
        # Deck 1
        self.draw_deck(draw, self.state.deck1, 0, 0, mid_x, 160, 
                      font_large, font_medium, font_small, "DECK 1")
        
        # Deck 2
        self.draw_deck(draw, self.state.deck2, mid_x, 0, 960, 160,
                      font_large, font_medium, font_small, "DECK 2")
        
        # Crossfader indicator at bottom
        cf_x = int(60 + (840 * self.state.crossfader))
        draw.line([(60, 155), (900, 155)], fill=(100, 100, 100), width=2)
        draw.ellipse([(cf_x-10, 150), (cf_x+10, 160)], fill=(255, 0, 0))
        
        return img
    
    def draw_deck(self, draw, deck, x1, y1, x2, y2, font_large, font_medium, font_small, label):
        """Draw a single deck display"""
        # Deck label
        draw.text((x1 + 10, y1 + 5), label, font=font_small, fill=(100, 100, 100))
        
        # Play indicator
        if deck['playing']:
            draw.polygon([(x2-30, y1+10), (x2-10, y1+20), (x2-30, y1+30)], fill=(0, 255, 0))
        else:
            draw.rectangle([(x2-30, y1+10), (x2-10, y1+30)], fill=(255, 0, 0))
        
        # BPM
        if deck['bpm'] > 0:
            bpm_text = f"{deck['bpm']:.1f} BPM"
            draw.text((x1 + 10, y1 + 30), bpm_text, font=font_large, fill=(255, 255, 0))
        
        # Track info
        if deck['title']:
            draw.text((x1 + 10, y1 + 70), deck['title'][:20], font=font_medium, fill=(255, 255, 255))
        if deck['artist']:
            draw.text((x1 + 10, y1 + 95), deck['artist'][:20], font=font_small, fill=(180, 180, 180))
        
        # Position bar
        bar_width = (x2 - x1 - 20)
        bar_fill = int(bar_width * deck['position'])
        draw.rectangle([(x1+10, y2-15), (x1+10+bar_width, y2-5)], outline=(100, 100, 100))
        draw.rectangle([(x1+10, y2-15), (x1+10+bar_fill, y2-5)], fill=(0, 150, 255))
        
        # Volume meter
        vol_height = int(60 * deck['volume'])
        draw.rectangle([(x1+5, y1+40), (x1+8, y1+100)], outline=(100, 100, 100))
        draw.rectangle([(x1+5, y1+100-vol_height), (x1+8, y1+100)], fill=(0, 255, 0))
    
    def display_loop(self):
        """Continuously render display"""
        fps = 30
        frame_time = 1.0 / fps
        
        while self.running:
            start = time.time()
            
            # Render and send frame
            img = self.render_display()
            self.push2.send_frame(img)
            
            # Maintain frame rate
            elapsed = time.time() - start
            sleep_time = frame_time - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
    
    def start(self):
        """Start the bridge"""
        print("Starting Mixxx MIDI Bridge...")
        
        # Connect to Push 2
        if not self.push2.connect():
            print("Failed to connect to Push 2")
            return False
        
        self.running = True
        
        # Start MIDI listener thread
        if self.midi_in:
            midi_thread = threading.Thread(target=self.midi_listener, daemon=True)
            midi_thread.start()
        
        # Start display loop
        try:
            self.display_loop()
        except KeyboardInterrupt:
            print("\nStopping...")
        finally:
            self.stop()
        
        return True
    
    def stop(self):
        """Stop the bridge"""
        self.running = False
        if self.midi_in:
            self.midi_in.close()
        if self.midi_out:
            self.midi_out.close()
        self.push2.disconnect()
        print("Bridge stopped")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Mixxx MIDI Bridge for Push 2')
    parser.add_argument('--list-ports', action='store_true', help='List MIDI ports')
    parser.add_argument('--input', help='MIDI input port name')
    parser.add_argument('--output', help='MIDI output port name')
    
    args = parser.parse_args()
    
    bridge = MixxxMidiBridge()
    
    if args.list_ports:
        bridge.list_midi_ports()
        return
    
    # Connect MIDI
    if args.input or args.output:
        bridge.connect_midi(args.input, args.output)
    
    # Start bridge
    bridge.start()


if __name__ == '__main__':
    main()
