#!/usr/bin/env python3
"""
MIDI Bridge between Mixxx and Push 2.

The display is a straight screen capture of the custom "Pusher160" Mixxx
skin (../skins/push2 in this repo), a display-only 960x160 skin that switches
itself between its expanded-deck (Device), waveform (Mix), library (Browse)
and FX (Clip) pages on the push-mixxx scene - so every frame is just
"capture whatever the skin shows".
The skin has direct access to track metadata and effect state that Mixxx
never exposes to controller scripts. See mixxx_capture.py.

The SCENE frames below come from push-mixxx's bridge-script.js
(functionprefix PUSH2BRIDGE, bound to a virtual MIDI port such as loopMIDI
"Mixxx Bridge" - see docs/mixxx-midi-setup.md).

SysEx frame: F0 7D <type> <deck> <payload...> F7
  type 0x03 SCENE: sceneId (0=none 1=browse 2=device 3=mix 4=clip) - mirrors
                    push-mixxx's PUSH2T.scene
"""

import importlib
import threading
import time

import mido
from PIL import Image, ImageDraw, ImageFont

from mixxx_capture import MixxxSkinCapture, close_mixxx_popups, focus_mixxx

Push2Display = importlib.import_module('mixxx-to-push2').Push2Display

MONO_FONT_CANDIDATES = ["consola.ttf", "cour.ttf", "arial.ttf"]


def _load_font(size):
    for name in MONO_FONT_CANDIDATES:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


# The Push 2 display refreshes at 60Hz; on Windows the screen capture (~23ms)
# is what actually limits the rate - see the [display] fps log.
TARGET_FPS = 60
FPS_LOG_SECONDS = 5

SYSEX_ID = 0x7D
TYPE_SCENE = 0x03

SCENE_NAMES = {0: 'none', 1: 'browse', 2: 'device', 3: 'mix', 4: 'clip'}

PUSH_PORT_MATCH = 'Push 2 Live Port'
CC_DELETE = 118  # push-mixxx's DELETE modifier; also closes Mixxx popups here

COLOR_GRAY = (110, 110, 110)


class MixxxState:
    """State populated from PUSH2BRIDGE SysEx frames (everything shown on the
    screen comes from the skin capture, not SysEx)."""

    def __init__(self):
        self.scene = 'none'


class MixxxMidiBridge:
    """Bridge between the Pusher160 skin capture / push-mixxx SysEx and the Push 2 display."""

    def __init__(self):
        self.push2 = Push2Display()
        self.state = MixxxState()
        self.running = False
        self.midi_in = None
        self.midi_out = None
        self.push_in = None
        self.skin_capture = MixxxSkinCapture()
        self._last_skin_frame = None
        self._frame_ready = threading.Condition()
        self._next_frame = None

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
            scene = SCENE_NAMES.get(data[2], 'none')
            # Browse navigation only works while Mixxx has focus (see focus_mixxx)
            if scene == 'browse' and self.state.scene != 'browse':
                ok = focus_mixxx()
                print(f"[focus] Browse: Mixxx {'in front' if ok else 'could NOT be focused'}")
            self.state.scene = scene

    def connect_push_buttons(self):
        """Listens to the Push alongside Mixxx so DELETE can close popups.
        ALSA lets both read the port; on Windows Mixxx holds it exclusively,
        so this just fails quietly there."""
        port = next((p for p in mido.get_input_names() if PUSH_PORT_MATCH in p), None)
        if not port:
            return
        try:
            self.push_in = mido.open_input(port, callback=self._on_push_message)
            print(f"[OK] Listening to Push buttons: {port}")
        except Exception as e:
            print(f"[!] Push buttons unavailable ({e}) - DELETE won't close popups")

    def _on_push_message(self, msg):
        if msg.type == 'control_change' and msg.control == CC_DELETE and msg.value > 0:
            closed = close_mixxx_popups()
            if closed:
                print(f"[popup] DELETE closed {closed} window(s)")

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
        """Render the Push 2 frame: the skin already shows the right page"""
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

    def _frame_producer(self):
        """Capture + convert frames, keeping only the newest for the sender."""
        frame_time = 1.0 / TARGET_FPS
        while self.running:
            start = time.perf_counter()
            data = self.push2.prepare_frame(self.render_display())
            with self._frame_ready:
                self._next_frame = data
                self._frame_ready.notify()
            sleep_time = frame_time - (time.perf_counter() - start)
            if sleep_time > 0:
                time.sleep(sleep_time)

    def display_loop(self):
        """Send frames to the Push while the producer thread captures the next
        one - capture (the slow part) overlaps the USB transfer."""
        threading.Thread(target=self._frame_producer, daemon=True).start()
        sent, window_start = 0, time.perf_counter()

        while self.running:
            with self._frame_ready:
                while self._next_frame is None and self.running:
                    self._frame_ready.wait(0.5)
                data, self._next_frame = self._next_frame, None
            if data is None:
                continue
            self.push2.send_prepared(data)

            sent += 1
            now = time.perf_counter()
            if now - window_start >= FPS_LOG_SECONDS:
                print(f"[display] {sent / (now - window_start):.1f} fps", flush=True)
                sent, window_start = 0, now

    def start(self):
        """Start the bridge"""
        print("Starting Mixxx MIDI Bridge...")

        if not self.push2.connect():
            print("Failed to connect to Push 2")
            return False

        self.running = True
        self.connect_push_buttons()

        if self.midi_in:
            midi_thread = threading.Thread(target=self.midi_listener, daemon=True)
            midi_thread.start()
        else:
            print("[!] No MIDI input connected - the display still works (the skin "
                  "switches pages itself); only the SCENE frames are skipped.")

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
        if self.push_in:
            self.push_in.close()
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
