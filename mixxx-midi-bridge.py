#!/usr/bin/env python3
"""
MIDI Bridge between Mixxx and Push 2.

Reads the SysEx protocol sent by push-mixxx's bridge-script.js
(functionprefix PUSH2BRIDGE, bound to a virtual MIDI port such as loopMIDI
"Mixxx Bridge" - see docs/mixxx-midi-setup.md) and renders a custom Push 2
display from it. This is NOT the same MIDI port as the Push 2 hardware
controller mapping (pusher.midi.xml) in the sibling push-mixxx repo.

SysEx frame: F0 7D <type> <deck> <payload...> F7
  type 0x01 TRACK: deck(0/1) playing(0/1) bpmHi bpmLo posHi posLo
                   title-bytes 0x00 artist-bytes   (bpm = 14-bit bpm*10,
                   pos = 14-bit playposition 0.0-1.0)
  type 0x02 MIXER: crossfader(0-127)
"""

import importlib
import time

import mido
from PIL import Image, ImageDraw, ImageFont

Push2Display = importlib.import_module('mixxx-to-push2').Push2Display

SYSEX_ID = 0x7D
TYPE_TRACK = 0x01
TYPE_MIXER = 0x02


class MixxxState:
    """Track Mixxx state, populated from PUSH2BRIDGE SysEx frames."""

    def __init__(self):
        self.deck1 = {'playing': False, 'bpm': 0.0, 'title': '', 'artist': '', 'position': 0.0}
        self.deck2 = {'playing': False, 'bpm': 0.0, 'title': '', 'artist': '', 'position': 0.0}
        self.crossfader = 0.5


def _join14(hi, lo):
    return (hi << 7) | lo


class MixxxMidiBridge:
    """Bridge between the push-mixxx SysEx bridge and the Push 2 display."""

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
        """Connect to the Mixxx Bridge virtual MIDI port"""
        try:
            if input_port is None:
                for port in mido.get_input_names():
                    if 'Mixxx Bridge' in port or 'loopMIDI' in port:
                        input_port = port
                        break

            if output_port is None:
                for port in mido.get_output_names():
                    if 'Mixxx Bridge' in port or 'loopMIDI' in port:
                        output_port = port
                        break

            if input_port:
                self.midi_in = mido.open_input(input_port)
                print(f"[OK] Connected to MIDI input: {input_port}")
            else:
                print("[X] No 'Mixxx Bridge' MIDI input found - pass --input explicitly")

            if output_port:
                self.midi_out = mido.open_output(output_port)
                print(f"[OK] Connected to MIDI output: {output_port}")

            return self.midi_in is not None

        except Exception as e:
            print(f"[X] MIDI connection failed: {e}")
            return False

    def process_midi_message(self, msg):
        """Process an incoming SysEx frame from push-mixxx's bridge-script.js"""
        if msg.type != 'sysex':
            return

        data = msg.data
        if len(data) < 2 or data[0] != SYSEX_ID:
            return

        frame_type = data[1]

        if frame_type == TYPE_TRACK and len(data) >= 9:
            deck = self.state.deck1 if data[2] == 0 else self.state.deck2
            deck['playing'] = bool(data[3])
            deck['bpm'] = _join14(data[4], data[5]) / 10.0
            deck['position'] = _join14(data[6], data[7]) / 16383.0

            rest = data[8:]
            if 0x00 in rest:
                sep = rest.index(0x00)
                title_bytes, artist_bytes = rest[:sep], rest[sep + 1:]
            else:
                title_bytes, artist_bytes = rest, ()
            deck['title'] = ''.join(chr(b) for b in title_bytes)
            deck['artist'] = ''.join(chr(b) for b in artist_bytes)

        elif frame_type == TYPE_MIXER and len(data) >= 3:
            self.state.crossfader = data[2] / 127.0

    def midi_listener(self):
        """Listen for MIDI messages from Mixxx"""
        if not self.midi_in:
            return

        print("Listening for Mixxx Bridge SysEx...")
        for msg in self.midi_in:
            if not self.running:
                break
            self.process_midi_message(msg)

    def render_display(self):
        """Render custom display for Push 2"""
        img = Image.new('RGB', (960, 160), color=(0, 0, 0))
        draw = ImageDraw.Draw(img)

        try:
            font_large = ImageFont.truetype("arial.ttf", 30)
            font_medium = ImageFont.truetype("arial.ttf", 20)
            font_small = ImageFont.truetype("arial.ttf", 16)
        except Exception:
            font_large = ImageFont.load_default()
            font_medium = ImageFont.load_default()
            font_small = ImageFont.load_default()

        mid_x = 480
        self.draw_deck(draw, self.state.deck1, 0, 0, mid_x, 160,
                        font_large, font_medium, font_small, "DECK A")
        self.draw_deck(draw, self.state.deck2, mid_x, 0, 960, 160,
                        font_large, font_medium, font_small, "DECK B")

        cf_x = int(60 + (840 * self.state.crossfader))
        draw.line([(60, 155), (900, 155)], fill=(100, 100, 100), width=2)
        draw.ellipse([(cf_x - 10, 150), (cf_x + 10, 160)], fill=(255, 0, 0))

        return img

    def draw_deck(self, draw, deck, x1, y1, x2, y2, font_large, font_medium, font_small, label):
        """Draw a single deck display"""
        draw.text((x1 + 10, y1 + 5), label, font=font_small, fill=(100, 100, 100))

        if deck['playing']:
            draw.polygon([(x2 - 30, y1 + 10), (x2 - 10, y1 + 20), (x2 - 30, y1 + 30)], fill=(0, 255, 0))
        else:
            draw.rectangle([(x2 - 30, y1 + 10), (x2 - 10, y1 + 30)], fill=(255, 0, 0))

        if deck['bpm'] > 0:
            draw.text((x1 + 10, y1 + 30), f"{deck['bpm']:.1f} BPM", font=font_large, fill=(255, 255, 0))

        if deck['title']:
            draw.text((x1 + 10, y1 + 70), deck['title'][:24], font=font_medium, fill=(255, 255, 255))
        if deck['artist']:
            draw.text((x1 + 10, y1 + 95), deck['artist'][:24], font=font_small, fill=(180, 180, 180))

        bar_width = x2 - x1 - 20
        bar_fill = int(bar_width * deck['position'])
        draw.rectangle([(x1 + 10, y2 - 15), (x1 + 10 + bar_width, y2 - 5)], outline=(100, 100, 100))
        draw.rectangle([(x1 + 10, y2 - 15), (x1 + 10 + bar_fill, y2 - 5)], fill=(0, 150, 255))

    def display_loop(self):
        """Continuously render display"""
        fps = 30
        frame_time = 1.0 / fps

        while self.running:
            start = time.time()

            img = self.render_display()
            self.push2.send_frame(img)

            elapsed = time.time() - start
            sleep_time = frame_time - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def start(self):
        """Start the bridge"""
        print("Starting Mixxx MIDI Bridge...")

        if not self.push2.connect():
            print("Failed to connect to Push 2")
            return False

        self.running = True

        if self.midi_in:
            import threading
            midi_thread = threading.Thread(target=self.midi_listener, daemon=True)
            midi_thread.start()
        else:
            print("[!] No MIDI input connected - display will show no data. "
                  "Run with --list-ports and --input to connect the Mixxx Bridge port.")

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
    parser.add_argument('--input', help='MIDI input port name (the "Mixxx Bridge" virtual port)')
    parser.add_argument('--output', help='MIDI output port name')

    args = parser.parse_args()

    bridge = MixxxMidiBridge()

    if args.list_ports:
        bridge.list_midi_ports()
        return

    bridge.connect_midi(args.input, args.output)
    bridge.start()


if __name__ == '__main__':
    main()
