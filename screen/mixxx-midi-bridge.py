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
import os
import subprocess
import threading
import time

import mido
import psutil
from PIL import Image, ImageDraw, ImageFont

from mixxx_capture import MixxxSkinCapture, close_mixxx_popups, focus_mixxx
from pi_stats import BODY_BOLD_FONTS, DISPLAY_FONTS, EDGE, INK, LIME, LINE, DIM, PiStats, _font

Push2Display = importlib.import_module('mixxx-to-push2').Push2Display

MONO_FONT_CANDIDATES = ["consola.ttf", "cour.ttf", "arial.ttf"]


def _load_font(size):
    for name in MONO_FONT_CANDIDATES:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


# Capped well below the Push's 60Hz: on the Pi 3 capture + conversion costs
# real CPU that Mixxx's audio and track analysis need. Mix shows moving
# waveforms, so it gets more.
TARGET_FPS = 20
MIX_FPS = 30
FPS_LOG_SECONDS = 5

SYSEX_ID = 0x7D
TYPE_SCENE = 0x03
TYPE_AUDIO = 0x05  # dropoutsHi dropoutsLo enginePct (bridge-script.js)

SCENE_NAMES = {0: 'none', 1: 'browse', 2: 'device', 3: 'mix', 4: 'clip'}

PUSH_PORT_MATCH = 'Push 2 Live Port'
CC_DELETE = 118  # push-mixxx's DELETE modifier; also closes Mixxx popups here
CC_SETUP = 30  # unused by push-mixxx; hold to restart Mixxx
SETUP_HOLD_SECONDS = 3
# Needs a sudoers rule on the Pi: admin ALL=(root) NOPASSWD: /usr/bin/systemctl restart mixxx.service
RESTART_MIXXX_CMD = ['sudo', '-n', '/usr/bin/systemctl', 'restart', 'mixxx.service']
CC_SHIFT = 49  # push-mixxx's SHIFT; SHIFT + hold SETUP ejects the music drive
# Needs a sudoers rule on the Pi: admin ALL=(root) NOPASSWD: /usr/local/bin/usb-library-eject
EJECT_CMD = ['sudo', '-n', '/usr/local/bin/usb-library-eject']
CC_USER = 59  # unused by push-mixxx; toggles the Pi stats page
# White-only Push buttons: same brightness levels push-mixxx uses for SHIFT/DELETE
LED_DIM = 64
LED_BRIGHT = 127

COLOR_GRAY = (110, 110, 110)


class MixxxState:
    """State populated from PUSH2BRIDGE SysEx frames (everything shown on the
    screen comes from the skin capture, not SysEx)."""

    def __init__(self):
        self.scene = 'none'
        self.dropouts = None      # audio underruns since Mixxx started
        self.engine_pct = None    # Mixxx audio engine load, % of the buffer time
        self.dropout_times = []   # monotonic times of dropouts seen by this bridge


class MixxxMidiBridge:
    """Bridge between the Pusher160 skin capture / push-mixxx SysEx and the Push 2 display."""

    def __init__(self, music_drive=None):
        self.music_drive = music_drive  # Pi: mount point of the USB music drive
        self._shift = False
        self._setup_action = 'restart'
        self._ejecting = False
        self._ejected = False
        self._mixxx_up = (0.0, True)  # (checked at, running)
        self.push2 = Push2Display()
        self.state = MixxxState()
        self.running = False
        self.midi_in = None
        self.midi_out = None
        self.push_in = None
        self.push_out = None
        self._setup_timer = None
        self._setup_pressed_at = None
        self._restarting = False
        self._f_countdown = _font(DISPLAY_FONTS, 30)
        self._f_note = _font(BODY_BOLD_FONTS, 11)
        self.show_stats = False
        self.fps = 0.0
        self.pi_stats = PiStats(lambda: self.fps, self._audio_stats)
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
        elif frame_type == TYPE_AUDIO and len(data) >= 5:
            count, pct = (data[2] << 7) | data[3], data[4]
            st = self.state
            if st.dropouts is not None and count > st.dropouts:
                now = time.monotonic()
                st.dropout_times += [now] * (count - st.dropouts)
                print(f"[audio] DROPOUT #{count} (engine load {pct}%)", flush=True)
            st.dropouts, st.engine_pct = count, pct

    def _audio_stats(self):
        """(dropouts total, dropouts in the last minute, engine load %) or None."""
        st = self.state
        if st.dropouts is None:
            return None
        cutoff = time.monotonic() - 60
        st.dropout_times = [t for t in st.dropout_times if t > cutoff]
        return st.dropouts, len(st.dropout_times), st.engine_pct

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
            return
        out_port = next((p for p in mido.get_output_names() if PUSH_PORT_MATCH in p), None)
        try:
            self.push_out = mido.open_output(out_port) if out_port else None
        except Exception as e:
            print(f"[!] Push LEDs unavailable ({e})")
        self._led(CC_SETUP, LED_DIM)
        self._led(CC_USER, LED_DIM)

    def _led(self, cc, value):
        if self.push_out:
            self.push_out.send(mido.Message('control_change', control=cc, value=value))

    def _on_push_message(self, msg):
        if msg.type != 'control_change':
            return
        if msg.control == CC_DELETE and msg.value > 0:
            closed = close_mixxx_popups()
            if closed:
                print(f"[popup] DELETE closed {closed} window(s)")
        elif msg.control == CC_SHIFT:
            self._shift = msg.value > 0
        elif msg.control == CC_SETUP:
            if self._setup_timer:
                self._setup_timer.cancel()
                self._setup_timer = None
            self._led(CC_SETUP, LED_BRIGHT if msg.value > 0 else LED_DIM)
            self._setup_pressed_at = time.monotonic() if msg.value > 0 else None
            if msg.value > 0:
                eject = self._shift and self.music_drive and os.path.ismount(self.music_drive)
                self._setup_action = 'eject' if eject else 'restart'
                action = self._eject_drive if eject else self._restart_mixxx
                self._setup_timer = threading.Timer(SETUP_HOLD_SECONDS, action)
                self._setup_timer.daemon = True
                self._setup_timer.start()
        elif msg.control == CC_USER and msg.value > 0:
            self.show_stats = not self.show_stats
            if self.show_stats:
                self.pi_stats.start()
            self._led(CC_USER, LED_BRIGHT if self.show_stats else LED_DIM)

    def _restart_mixxx(self):
        print("[setup] SETUP held - restarting Mixxx", flush=True)
        self._setup_pressed_at = None
        self._restarting = True
        result = subprocess.run(RESTART_MIXXX_CMD, capture_output=True, text=True)
        self._restarting = False
        if result.returncode != 0:
            print(f"[setup] restart failed: {result.stderr.strip()}", flush=True)

    def _eject_drive(self):
        print("[setup] SHIFT+SETUP held - ejecting the music drive", flush=True)
        self._setup_pressed_at = None
        self._ejecting = True
        result = subprocess.run(EJECT_CMD, capture_output=True, text=True)
        self._ejecting = False
        self._ejected = result.returncode == 0
        if result.returncode != 0:
            print(f"[setup] eject failed: {result.stderr.strip()}", flush=True)

    def _mixxx_running(self):
        checked, up = self._mixxx_up
        now = time.monotonic()
        if now - checked > 1.0:
            up = any((p.info['name'] or '') == 'mixxx' for p in psutil.process_iter(['name']))
            self._mixxx_up = (now, up)
        return up

    def rawmidi_listener(self, path):
        """Linux: reads the Mixxx Bridge SysEx straight from an ALSA raw MIDI
        device. With snd-virmidi, what Mixxx writes to the 'VirMIDI 7-0'
        sequencer port comes out of /dev/snd/midiC7D0, not out of the
        sequencer port, so a normal mido input never sees it."""
        print(f"Listening for Mixxx Bridge SysEx on {path}...")
        buf = None
        with open(path, 'rb', buffering=0) as dev:
            while self.running:
                for byte in dev.read(256):
                    if byte == 0xF0:
                        buf = []
                    elif byte == 0xF7:
                        if buf is not None:
                            self.process_midi_message(mido.Message('sysex', data=buf))
                        buf = None
                    elif buf is not None:
                        if byte < 0x80:
                            buf.append(byte)
                        else:
                            buf = None

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
        frame = self._base_frame()
        if self._setup_pressed_at is not None:
            frame = self._setup_overlay(frame.copy())
        return frame

    def _status(self):
        """(title, note) when the Pi isn't showing Mixxx, else None."""
        if self._ejecting:
            return 'EJECTING USB', 'saving the library - do not unplug'
        if self._restarting:
            return 'RESTARTING MIXXX', 'back in about a minute'
        if not self.music_drive:
            return None
        if not os.path.ismount(self.music_drive):
            if self._ejected:
                return 'SAFE TO REMOVE', 'insert a USB drive to start Mixxx'
            return 'INSERT USB DRIVE', 'Mixxx starts when a music drive is plugged in'
        self._ejected = False
        if not self._mixxx_running():
            return 'STARTING MIXXX', 'loading the library from the USB drive'
        return None

    def _base_frame(self):
        if self.show_stats:
            return self.pi_stats.render()
        status = self._status()
        if status:
            return self._box(Image.new('RGB', (960, 160), INK), *status)
        frame = self.skin_capture.capture()
        if frame is not None:
            self._last_skin_frame = frame
            return frame
        if self._last_skin_frame is not None:
            return self._last_skin_frame
        return self._not_found_frame()

    def _setup_overlay(self, img):
        """Countdown box while SETUP is held (release cancels)."""
        held = time.monotonic() - (self._setup_pressed_at or time.monotonic())
        left = max(SETUP_HOLD_SECONDS - held, 0)
        what = 'EJECT USB' if self._setup_action == 'eject' else 'RESTART MIXXX'
        title = f'{what} IN {int(left) + 1}' if left > 0 else what
        return self._box(img, title, 'release SETUP to cancel', min(held / SETUP_HOLD_SECONDS, 1.0))

    def _box(self, img, title, note, frac=None):
        """Centred message box in the skin palette, optional progress bar."""
        draw = ImageDraw.Draw(img)
        x0, y0, x1, y1 = 250, 30, 710, 130
        draw.rectangle([x0, y0, x1, y1], fill=INK, outline=LIME, width=2)
        tw = draw.textlength(title, font=self._f_countdown)
        draw.text(((x0 + x1 - tw) / 2, y0 + 12), title, font=self._f_countdown, fill=LINE)
        nw = draw.textlength(note, font=self._f_note)
        draw.text(((x0 + x1 - nw) / 2, y0 + 56), note, font=self._f_note, fill=DIM)
        if frac is None:
            return img
        bx0, by0, bx1, by1 = x0 + 20, y1 - 22, x1 - 20, y1 - 12
        draw.rectangle([bx0, by0, bx1, by1], outline=EDGE)
        fill_x = bx0 + 1 + int((bx1 - bx0 - 2) * frac)
        if fill_x > bx0 + 1:
            draw.rectangle([bx0 + 1, by0 + 1, fill_x, by1 - 1], fill=LIME)
        return img

    def _not_found_frame(self):
        img = Image.new('RGB', (960, 160), color=(0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.text((320, 70), "Mixxx window not found", font=_load_font(20), fill=COLOR_GRAY)
        return img

    def _frame_producer(self):
        """Capture + convert frames, keeping only the newest for the sender."""
        while self.running:
            mix = self.state.scene == 'mix' and not self.show_stats
            frame_time = 1.0 / (MIX_FPS if mix else TARGET_FPS)
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
                self.fps = sent / (now - window_start)
                print(f"[display] {self.fps:.1f} fps", flush=True)
                sent, window_start = 0, now

    def start(self, rawmidi_path=None):
        """Start the bridge"""
        print("Starting Mixxx MIDI Bridge...")

        if not self.push2.connect():
            print("Failed to connect to Push 2")
            return False

        self.running = True
        self.connect_push_buttons()

        if rawmidi_path:
            threading.Thread(target=self.rawmidi_listener, args=(rawmidi_path,), daemon=True).start()
        elif self.midi_in:
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
        if self.push_out:
            self.push_out.close()
        self.skin_capture.close()
        self.push2.disconnect()
        print("Bridge stopped")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Mixxx MIDI Bridge for Push 2')
    parser.add_argument('--list-ports', action='store_true', help='List MIDI ports')
    parser.add_argument('--input', help='MIDI input port name (the "Mixxx Bridge" virtual port)')
    parser.add_argument('--output', help='MIDI output port name')
    parser.add_argument('--rawmidi', help='Linux: read the bridge SysEx from this ALSA raw MIDI '
                                          'device instead (Pi: /dev/snd/midiC7D0)')
    parser.add_argument('--music-drive', help='Pi: mount point of the USB music drive - enables '
                                              'the drive status screens and SHIFT+SETUP eject')

    args = parser.parse_args()

    bridge = MixxxMidiBridge(args.music_drive)

    if args.list_ports:
        bridge.list_midi_ports()
        return

    if not args.rawmidi:
        bridge.connect_midi(args.input, args.output)
    bridge.start(args.rawmidi)


if __name__ == '__main__':
    main()
