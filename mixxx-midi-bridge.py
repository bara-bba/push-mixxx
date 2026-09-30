#!/usr/bin/env python3
"""
MIDI Bridge between Mixxx and Push 2.

The display is a straight screen capture of the custom "Pusher160" Mixxx
skin (push-mixxx/skins/push2), a display-only 960x160 skin that switches
itself between its Browse page (parallel waveforms) and its Device page
(Traktor-style expanded decks) on the push-mixxx scene - so every scene
except Mix is just "capture whatever the skin shows". The skin has direct
access to track metadata Mixxx never exposes to controller scripts. See
mixxx_capture.py.

The Mix-scene FX overlay still needs live data from push-mixxx's
bridge-script.js (functionprefix PUSH2BRIDGE, bound to a virtual MIDI port
such as loopMIDI "Mixxx Bridge" - see docs/mixxx-midi-setup.md), since FX
unit state isn't visible in the skin.

SysEx frame: F0 7D <type> <deck> <payload...> F7
  type 0x03 SCENE: sceneId (0=none 1=browse 2=device 3=mix 4=clip) - mirrors
                    push-mixxx's PUSH2T.scene
  type 0x04 FX: unit(0/1) mixKnob(0-127) eff1On eff2On eff3On (0/1 each) -
                only sent while scene == mix
"""

import importlib
import time

import mido
from PIL import Image, ImageDraw, ImageFont

from mixxx_capture import MixxxSkinCapture

Push2Display = importlib.import_module('mixxx-to-push2').Push2Display

MONO_FONT_CANDIDATES = ["consola.ttf", "cour.ttf", "arial.ttf"]


def _load_font(size):
    for name in MONO_FONT_CANDIDATES:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


SYSEX_ID = 0x7D
TYPE_SCENE = 0x03
TYPE_FX = 0x04

SCENE_NAMES = {0: 'none', 1: 'browse', 2: 'device', 3: 'mix', 4: 'clip'}

COLOR_GRAY = (110, 110, 110)
COLOR_ORANGE = (255, 150, 0)
COLOR_GREEN = (0, 200, 90)
COLOR_DIM = (150, 150, 150)


class MixxxState:
    """State populated from PUSH2BRIDGE SysEx frames (scene + FX only -
    track/deck info comes from the skin capture, not SysEx)."""

    def __init__(self):
        self.scene = 'none'
        self.fx = {
            0: {'mix': 0.0, 'effects': [False, False, False]},
            1: {'mix': 0.0, 'effects': [False, False, False]},
        }


class MixxxMidiBridge:
    """Bridge between the Pusher160 skin capture / push-mixxx SysEx and the Push 2 display."""

    def __init__(self):
        self.push2 = Push2Display()
        self.state = MixxxState()
        self.running = False
        self.midi_in = None
        self.midi_out = None
        self.skin_capture = MixxxSkinCapture()
        self._last_skin_frame = None

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
            if input_port is None or input_port not in mido.get_input_names():
                wanted = input_port or 'Mixxx Bridge'
                for port in mido.get_input_names():
                    if wanted in port or 'loopMIDI' in port:
                        input_port = port
                        break
                else:
                    input_port = None

            if output_port is None or output_port not in mido.get_output_names():
                wanted = output_port or 'Mixxx Bridge'
                for port in mido.get_output_names():
                    if wanted in port or 'loopMIDI' in port:
                        output_port = port
                        break
                else:
                    output_port = None

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

        if frame_type == TYPE_SCENE and len(data) >= 3:
            self.state.scene = SCENE_NAMES.get(data[2], 'none')

        elif frame_type == TYPE_FX and len(data) >= 7:
            unit = self.state.fx.get(data[2])
            if unit is not None:
                unit['mix'] = data[3] / 127.0
                unit['effects'] = [bool(data[4]), bool(data[5]), bool(data[6])]

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
        """Render the Push 2 frame for whatever push-mixxx scene is active"""
        if self.state.scene == 'mix':
            img = Image.new('RGB', (960, 160), color=(0, 0, 0))
            draw = ImageDraw.Draw(img)
            font_large = _load_font(26)
            font_medium = _load_font(18)
            font_small = _load_font(13)
            self.render_mix_scene(draw, font_large, font_medium, font_small)
            return img

        # Every other scene: the skin already shows the right page
        frame = self.skin_capture.capture()
        if frame is not None:
            self._last_skin_frame = frame
            return frame
        if self._last_skin_frame is not None:
            return self._last_skin_frame
        return self._not_found_frame()

    def _not_found_frame(self):
        img = Image.new('RGB', (960, 160), color=(0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.text((320, 70), "Mixxx window not found", font=_load_font(20), fill=COLOR_GRAY)
        return img

    def render_mix_scene(self, draw, font_large, font_medium, font_small):
        """Mix scene layout: FX unit 1/2 mix level + which effects are on"""
        mid_x = 480
        self.draw_fx_unit(draw, self.state.fx[0], 0, 0, mid_x, 160,
                           font_large, font_medium, font_small, "FX UNIT 1")
        self.draw_fx_unit(draw, self.state.fx[1], mid_x, 0, 960, 160,
                           font_large, font_medium, font_small, "FX UNIT 2")

    def draw_fx_unit(self, draw, fx, x1, y1, x2, y2, font_large, font_medium, font_small, label):
        draw.text((x1 + 10, y1 + 5), label, font=font_small, fill=COLOR_GRAY)

        mix_pct = int(fx['mix'] * 100)
        draw.text((x1 + 10, y1 + 30), f"MIX {mix_pct}%", font=font_large, fill=COLOR_ORANGE)

        bar_width = x2 - x1 - 20
        bar_fill = int(bar_width * fx['mix'])
        draw.rectangle([(x1 + 10, y1 + 70), (x1 + 10 + bar_width, y1 + 85)], outline=COLOR_GRAY)
        draw.rectangle([(x1 + 10, y1 + 70), (x1 + 10 + bar_fill, y1 + 85)], fill=COLOR_ORANGE)

        for i, on in enumerate(fx['effects']):
            ex = x1 + 10 + i * 70
            color = COLOR_GREEN if on else (60, 60, 60)
            draw.rectangle([(ex, y1 + 105), (ex + 55, y1 + 135)], fill=color)
            draw.text((ex + 15, y1 + 112), f"E{i + 1}", font=font_medium, fill=(0, 0, 0) if on else COLOR_DIM)

    def display_loop(self):
        """Continuously render display"""
        fps = 36  # push-mixxx docs: Push 2 display supports up to 36 FPS over USB
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
            print("[!] No MIDI input connected - scene switching (Mix FX view) won't work, "
                  "but the default skin-capture view still will. "
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
        self.skin_capture.close()
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
