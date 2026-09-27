#!/usr/bin/env python3
"""
MIDI Bridge between Mixxx and Push 2.

Reads the SysEx protocol sent by push-mixxx's bridge-script.js
(functionprefix PUSH2BRIDGE, bound to a virtual MIDI port such as loopMIDI
"Mixxx Bridge" - see docs/mixxx-midi-setup.md) and renders a custom Push 2
display from it. This is NOT the same MIDI port as the Push 2 hardware
controller mapping (pusher.midi.xml) in the sibling push-mixxx repo.

Mixxx has never exposed track title/artist to controller scripting (see
github.com/mixxxdj/mixxx/issues/6898), so the SysEx protocol carries
duration+bpm instead, and artwork.TrackLookup identifies the loaded track
by matching those against Mixxx's own library database.

SysEx frame: F0 7D <type> <deck> <payload...> F7
  type 0x01 TRACK: deck(0/1) playing(0/1) bpmHi bpmLo posHi posLo durHi durLo
                   (bpm = 14-bit bpm*10, pos = 14-bit playposition 0.0-1.0,
                   dur = 14-bit duration in whole seconds)
  type 0x02 MIXER: crossfader(0-127)
  type 0x03 SCENE: sceneId (0=none 1=browse 2=device 3=mix 4=clip) - mirrors
                    push-mixxx's PUSH2T.scene
  type 0x04 FX: unit(0/1) mixKnob(0-127) eff1On eff2On eff3On (0/1 each) -
                only sent while scene == mix
"""

import colorsys
import importlib
import time

import mido
from PIL import Image, ImageDraw, ImageFont

from artwork import TrackLookup
from waveform import WaveformCache

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
TYPE_TRACK = 0x01
TYPE_MIXER = 0x02
TYPE_SCENE = 0x03
TYPE_FX = 0x04

SCENE_NAMES = {0: 'none', 1: 'browse', 2: 'device', 3: 'mix', 4: 'clip'}

# Push 2 screen deck colors: Deck A = green, Deck B = purple, everything else
# gray until active. (push-mixxx's own pad scheme uses blue/red per
# docs/color-palette.md Round 3, but the screen uses green/purple instead.)
COLOR_DECK_A = (60, 210, 100)
COLOR_DECK_B = (170, 80, 235)
COLOR_GRAY = (110, 110, 110)
COLOR_ORANGE = (255, 150, 0)   # cue / FX accent
COLOR_YELLOW = (255, 210, 0)   # BPM / warn
COLOR_GREEN = (0, 200, 90)     # active / on
COLOR_WHITE = (235, 235, 235)
COLOR_DIM = (150, 150, 150)


class MixxxState:
    """Track Mixxx state, populated from PUSH2BRIDGE SysEx frames."""

    def __init__(self):
        self.deck1 = {'playing': False, 'bpm': 0.0, 'duration': 0.0, 'position': 0.0,
                      'title': '', 'artist': '', 'art': None, 'path': None}
        self.deck2 = {'playing': False, 'bpm': 0.0, 'duration': 0.0, 'position': 0.0,
                      'title': '', 'artist': '', 'art': None, 'path': None}
        self.crossfader = 0.5
        self.scene = 'none'
        self.fx = {
            0: {'mix': 0.0, 'effects': [False, False, False]},
            1: {'mix': 0.0, 'effects': [False, False, False]},
        }


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
        self.track_lookup = TrackLookup(art_size=70)
        self.waveform_cache = WaveformCache()

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

        if frame_type == TYPE_TRACK and len(data) >= 10:
            deck = self.state.deck1 if data[2] == 0 else self.state.deck2
            deck['playing'] = bool(data[3])
            deck['bpm'] = _join14(data[4], data[5]) / 10.0
            deck['position'] = _join14(data[6], data[7]) / 16383.0
            deck['duration'] = float(_join14(data[8], data[9]))

            info = self.track_lookup.resolve(deck['duration'], deck['bpm'])
            deck['title'] = info['title']
            deck['artist'] = info['artist']
            deck['art'] = info['art']
            deck['path'] = info['path']

        elif frame_type == TYPE_MIXER and len(data) >= 3:
            self.state.crossfader = data[2] / 127.0

        elif frame_type == TYPE_SCENE and len(data) >= 3:
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
        """Render custom display for Push 2, laid out per the active push-mixxx scene"""
        img = Image.new('RGB', (960, 160), color=(0, 0, 0))
        draw = ImageDraw.Draw(img)

        font_large = _load_font(26)
        font_medium = _load_font(18)
        font_small = _load_font(13)

        if self.state.scene == 'mix':
            self.render_mix_scene(draw, font_large, font_medium, font_small)
        elif self.state.scene in ('device', 'clip'):
            draw.rectangle([(2, 2), (957, 157)], outline=COLOR_GRAY)
            draw.text((300, 70), f"{self.state.scene.upper()} SCENE", font=font_large, fill=COLOR_GRAY)
            draw.text((300, 105), "not yet implemented", font=font_small, fill=(60, 60, 60))
        else:
            self.render_track_scene(img, draw, font_large, font_medium, font_small)

        return img

    def render_track_scene(self, img, draw, font_large, font_medium, font_small):
        """Default / browse layout: per-deck artwork + track info + transport"""
        mid_x = 480
        self.draw_deck(img, draw, self.state.deck1, 0, 0, mid_x, 160,
                        font_large, font_medium, font_small, "DECK A", COLOR_DECK_A)
        self.draw_deck(img, draw, self.state.deck2, mid_x, 0, 960, 160,
                        font_large, font_medium, font_small, "DECK B", COLOR_DECK_B)

        cf_x = int(60 + (840 * self.state.crossfader))
        draw.line([(60, 155), (900, 155)], fill=COLOR_GRAY, width=1)
        draw.ellipse([(cf_x - 4, 151), (cf_x + 4, 159)], fill=COLOR_ORANGE)

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

    def draw_deck(self, img, draw, deck, x1, y1, x2, y2, font_large, font_medium, font_small, label, deck_color):
        """OP-1/Push2-style panel: compact header (artwork + track info) over a
        full-width colorful scrolling waveform, algoriddim-style."""
        dim_color = tuple(c // 3 for c in deck_color)
        draw.rectangle([(x1 + 1, y1 + 1), (x2 - 2, y2 - 2)], outline=dim_color)

        header_h = 62
        art_size = header_h - 8
        art_x, art_y = x1 + 6, y1 + 6
        draw.rectangle([(art_x - 1, art_y - 1), (art_x + art_size, art_y + art_size)], outline=deck_color)
        art = deck['art']
        if art is not None:
            thumb = art.resize((art_size, art_size)) if art.size != (art_size, art_size) else art
            img.paste(thumb, (art_x, art_y))
        else:
            draw.line([(art_x, art_y), (art_x + art_size, art_y + art_size)], fill=dim_color)
            draw.line([(art_x + art_size, art_y), (art_x, art_y + art_size)], fill=dim_color)

        text_x = art_x + art_size + 12

        draw.text((text_x, y1 + 4), label, font=font_small, fill=deck_color)

        # Play indicator: deck color when playing, gray when stopped
        if deck['playing']:
            draw.polygon([(x2 - 22, y1 + 6), (x2 - 10, y1 + 13), (x2 - 22, y1 + 20)], fill=deck_color)
        else:
            draw.rectangle([(x2 - 22, y1 + 6), (x2 - 12, y1 + 20)], fill=COLOR_GRAY)

        title = (deck['title'] or '(no track)')[:26]
        draw.text((text_x, y1 + 22), title, font=font_medium, fill=COLOR_WHITE if deck['title'] else COLOR_GRAY)
        if deck['artist']:
            draw.text((text_x, y1 + 44), deck['artist'][:26], font=font_small, fill=COLOR_DIM)
        if deck['bpm'] > 0:
            draw.text((x2 - 90, y1 + 44), f"{deck['bpm']:5.1f}", font=font_small, fill=COLOR_YELLOW)

        self.draw_waveform(img, draw, deck, x1 + 2, y1 + header_h + 4, x2 - 2, y2 - 2, deck_color)

    def draw_waveform(self, img, draw, deck, x1, y1, x2, y2, deck_color):
        """Full-height colorful scrolling waveform (algoriddim-style): fixed
        playhead at panel center, real audio scrolling underneath, red
        zero-amplitude line, deck-colored playhead needle."""
        mid_y = (y1 + y2) // 2

        envelope = self.waveform_cache.get(deck['path']) if deck['playing'] or deck['duration'] else None
        if envelope is None or deck['duration'] <= 0:
            draw.line([(x1, mid_y), (x2, mid_y)], fill=(120, 20, 20))
            draw.line([(x1, y1), (x2, y2)], fill=(30, 30, 30))
            draw.line([(x2, y1), (x1, y2)], fill=(30, 30, 30))
        else:
            width = x2 - x1
            half_h = (y2 - y1) // 2
            cols = envelope.shape[0]
            window_seconds = 6.0
            cols_per_sec = cols / deck['duration']
            half_window_cols = max(1, int((window_seconds / 2) * cols_per_sec))
            center_col = int(deck['position'] * cols)

            draw.line([(x1, mid_y), (x2, mid_y)], fill=(90, 15, 15))
            for px in range(width):
                col = center_col - half_window_cols + int(px * (2 * half_window_cols) / max(1, width))
                if col < 0 or col >= cols:
                    continue
                lo, hi = envelope[col]
                y_top = mid_y - int(hi * half_h)
                y_bot = mid_y - int(lo * half_h)
                if y_top == y_bot:
                    y_bot += 1
                hue = (col * 0.06180339887) % 1.0
                r, g, b = colorsys.hsv_to_rgb(hue, 0.65, 1.0)
                draw.line([(x1 + px, y_top), (x1 + px, y_bot)], fill=(int(r * 255), int(g * 255), int(b * 255)))

        needle_x = (x1 + x2) // 2
        draw.line([(needle_x, y1), (needle_x, y2)], fill=deck_color, width=2)

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
