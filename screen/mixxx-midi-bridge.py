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
import signal
import subprocess
import threading
import time

import mido
import psutil
from PIL import Image, ImageDraw, ImageFont

from mixxx_capture import MixxxSkinCapture, _x11_focus_main, close_mixxx_popups, focus_mixxx
import playlist_analysis
from playlist_analysis import AnalysisProgress
from library_pages import AutoDJPage, RecordingsPage
from playlist_page import NAV_NAMES, NAV_TREE_OPEN, PlaylistPage
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
TYPE_PLAYLIST = 0x06  # hi lo of [Skin],pusher_playlist (playlist_page.py)

# Pi: raw device of the VirMIDI port Mixxx's Push mapping reads (the relay's
# Mixxx side); bytes written here reach the mapping like Push input.
MIXXX_RAWMIDI = '/dev/snd/midiC7D1'
PLAYLISTS_CC = bytes([0xBF, 0x7E])  # + count: pusher-script.js PUSH2T.plPage
DEPTH_CC = bytes([0xBF, 0x7D])  # + 1 top-level / 2 deeper: PUSH2T.navDepth
ANALYSED_CC = bytes([0xBF, 0x7C])  # + 1 queued / 2 failed: PUSH2T.plAnalysed
RESYNC_CC = bytes([0xBF, 0x7B, 0x01])  # PUSH2T.navResync
RECORDINGS_CC = bytes([0xBF, 0x7A])  # + number of recordings: PUSH2T.recPage
REQ_DELETE_KEY = 1  # [Skin],pusher_req kind: press Delete in Mixxx (remove from the Auto DJ queue)
CC_RECORD = 86  # push-mixxx starts/stops recording on a REC_HOLD_SECONDS hold
REC_HOLD_SECONDS = 0.8  # = pusher-script.js PUSH2T.REC_HOLD_MS
PL_ANALYSE = 256  # pusher_playlist >= this: Convert asked to analyse playlist (value - 256)
ANALYSE_SETTLE_SECONDS = 0.4  # the script's sidebar steps, before the right-click
FREEZE_AFTER_SECONDS = 0.4  # the Push image stays still this long after a request
RESYNC_AFTER_SECONDS = 1.0  # Playlists page under another nav entry this long = drifted
RESYNC_EVERY_SECONDS = 3.0
PLAYLISTS_RESEND_SECONDS = 2.0
PLAYLISTS_GONE_SECONDS = 0.8
FRAME_DUMP = '/tmp/push2-frame.png'  # written on SIGUSR1 (debugging)

SCENE_NAMES = {0: 'none', 1: 'browse', 2: 'device', 3: 'mix', 4: 'clip'}

PUSH_PORT_MATCH = 'Push 2 Live Port'  # Pi: --push-port "VirMIDI 7-1" (push2_midi_relay.py)
REDRAW_CC = 127  # on channel 16: the relay's "Push reconnected" signal
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
        self.playlist = 0         # pusher_playlist: 0 off, 1..127 cursor + 1, 128 + cursor = open, 256 + cursor = analyse it
        self.nav = 0              # pusher_nav: painted nav cursor + 1 (0 = not set yet), 100 = tree open
        self.rec = 0              # pusher_rec: recordings list (library_pages.py)
        self.rec_status = 0       # [Recording],status: 0 off, 1 waiting for audio, 2 recording
        self.autodj = 0           # [AutoDJ],enabled
        self.req = None           # pusher_req: last one-shot request seen


class MixxxMidiBridge:
    """Bridge between the Pusher160 skin capture / push-mixxx SysEx and the Push 2 display."""

    def __init__(self, music_drive=None, push_port=PUSH_PORT_MATCH):
        self.push_port = push_port  # MIDI port the Push buttons/LEDs are reached through
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
        self.playlist_page = PlaylistPage(music_drive)  # names over Mixxx's Playlists text page
        self._pl_sent = (None, 0.0)  # (count, monotonic) last reported to the mapping
        self._depth_sent = None
        self._pl_gone_since = None
        self.analysis = AnalysisProgress(music_drive)  # Convert on a playlist
        self._raw_frame = None      # newest capture without overlays
        self._freeze_until = 0.0    # hold the Push image still until then (monotonic)
        self._drift_since = None    # Playlists page shown under another nav entry since
        self._resync_at = 0.0
        self.recordings = RecordingsPage()
        self.autodj_page = AutoDJPage(music_drive)
        self._rec_sent = (None, 0.0)
        self._rec_pressed_at = None  # REC held since (monotonic), for the countdown
        self._dump_frame = False
        if hasattr(signal, 'SIGUSR1'):
            signal.signal(signal.SIGUSR1, lambda *_: setattr(self, '_dump_frame', True))
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
        elif frame_type == TYPE_PLAYLIST and len(data) >= 4:
            playlist = (data[2] << 7) | data[3]
            if playlist >= PL_ANALYSE and self.state.playlist < PL_ANALYSE:
                threading.Thread(target=self._analyse_playlist, args=(playlist - PL_ANALYSE,),
                                 daemon=True).start()
            self.state.playlist = playlist
            if len(data) >= 5:
                self.state.nav = data[4]
            if len(data) >= 11:
                self._library_state(data)
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
        port = next((p for p in mido.get_input_names() if self.push_port in p), None)
        if not port:
            return
        try:
            self.push_in = mido.open_input(port, callback=self._on_push_message)
            print(f"[OK] Listening to Push buttons: {port}")
        except Exception as e:
            print(f"[!] Push buttons unavailable ({e}) - DELETE won't close popups")
            return
        out_port = next((p for p in mido.get_output_names() if self.push_port in p), None)
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
        if msg.channel == 15 and msg.control == REDRAW_CC:
            self._led(CC_SETUP, LED_DIM)
            self._led(CC_USER, LED_BRIGHT if self.show_stats else LED_DIM)
            return
        if msg.control == CC_DELETE and msg.value > 0:
            closed = close_mixxx_popups()
            if closed:
                print(f"[popup] DELETE closed {closed} window(s)")
        elif msg.control == CC_SHIFT:
            self._shift = msg.value > 0
        elif msg.control == CC_RECORD and msg.channel != 15:
            self._rec_pressed_at = time.monotonic() if msg.value > 0 else None
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
        elif self._rec_pressed_at is not None:
            frame = self._rec_overlay(frame.copy())
        if self._dump_frame:  # kill -USR1: save exactly what the Push shows
            self._dump_frame = False
            frame.save(FRAME_DUMP)
            print(f'[display] frame saved to {FRAME_DUMP}', flush=True)
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
            self._raw_frame = frame
            if self._frozen() and self._last_skin_frame is not None:
                return self._last_skin_frame   # Mixxx's sidebar is being worked behind it
            frame = self._playlists_overlay(frame.copy())
        if frame is not None:
            self._last_skin_frame = frame
            return frame
        if self._last_skin_frame is not None:
            return self._last_skin_frame
        return self._not_found_frame()

    def _playlists_overlay(self, frame):
        """Library nav + playlist list over the Browse page (playlist_page.py)."""
        if self.state.scene != 'browse':
            return frame
        pl, nav = self.state.playlist, self.state.nav
        shown = PlaylistPage.shown(frame)
        self._report_playlists(self.playlist_page.count if shown else 0)
        depth = PlaylistPage.depth(frame)
        if depth and depth != self._depth_sent:
            self._depth_sent = depth
            self._send_mixxx(DEPTH_CC + bytes([depth]))
            print(f'[library] sidebar highlight depth {depth}', flush=True)
        if shown:
            rows = 7 if self.analysis.showing else 8   # the analysis bar takes the 8th
            frame = self.playlist_page.draw(frame, pl - 1 if 0 < pl < 128 else -1, rows)
        page = NAV_NAMES[min(nav - 1, len(NAV_NAMES) - 1)] if 0 < nav != NAV_TREE_OPEN else None
        self._report_recordings()
        if page == 'Recordings':
            frame = self.recordings.draw(frame, self.state.rec, self.state.rec_status)
        elif page == 'Auto DJ':
            frame = self.autodj_page.draw(frame, self.state.autodj)
        if nav != NAV_TREE_OPEN:
            nav_rows = 4 if self.analysis.showing else 5   # the analysis bar takes the 5th
            frame = self.playlist_page.draw_nav(frame, max(nav - 1, 0), nav_rows)
        self._check_drift(shown, pl, nav)
        return self.analysis.draw(frame)

    def _library_state(self, data):
        """Recordings / Auto DJ part of the 0x06 frame (bridge-script.js)."""
        st = self.state
        rec = (data[5] << 7) | data[6]
        if data[7] != st.rec_status:
            print(f'[recording] status {st.rec_status} -> {data[7]}', flush=True)
        st.rec_status, st.autodj = data[7], data[8]
        req = (data[9] << 7) | data[10]
        if rec != st.rec:
            st.rec = rec
            self.recordings.request(rec, st.rec_status)
        if st.req is None:
            st.req = req          # whatever was pending before this app started
        elif req != st.req:
            st.req = req
            if req >> 7 == REQ_DELETE_KEY:
                threading.Thread(target=self._press_delete, daemon=True).start()

    def _press_delete(self):
        """Remove the selected song from Mixxx's Auto DJ queue: its Delete key,
        then OK in the "Confirm track removal" box it asks with (DELETE on the
        Push already was the confirmation). The Push image holds still meanwhile."""
        self._freeze_until = time.monotonic() + 2.0
        try:
            _x11_focus_main()
            xdo = lambda *a: subprocess.run(['xdotool', *a], capture_output=True, text=True, timeout=2).stdout
            xdo('key', 'Delete')
            deadline = time.monotonic() + 1.5
            wid = ''
            while not wid and time.monotonic() < deadline:
                time.sleep(0.05)
                wid = xdo('search', '--onlyvisible', '--name', '^Confirm track removal$').split()[:1]
                wid = wid[0] if wid else ''
            if wid:
                geo = dict(l.split('=', 1) for l in xdo('getwindowgeometry', '--shell', wid).split() if '=' in l)
                x, y, w, h = (int(geo[k]) for k in ('X', 'Y', 'WIDTH', 'HEIGHT'))
                # OK sits left of Cancel at the bottom right (measured on the Pi: 480x113 box)
                xdo('mousemove', str(x + w - 135), str(y + h - 24), 'click', '1')
                xdo('mousemove', '959', '0')
                time.sleep(0.2)
                if xdo('search', '--onlyvisible', '--name', '^Confirm track removal$').strip():
                    xdo('key', '--window', wid, 'Escape')   # missed OK: don't leave it blocking Mixxx
                    print('[autodj] removal box not confirmed, closed it', flush=True)
                else:
                    print('[autodj] song removed from the queue', flush=True)
            _x11_focus_main()
        finally:
            self._freeze_until = time.monotonic() + 0.3

    def _report_recordings(self):
        """Number of recordings to the Push mapping (on change, and every few s)."""
        count = min(self.recordings.count, 127)
        last, at = self._rec_sent
        now = time.monotonic()
        if count == last and now - at < PLAYLISTS_RESEND_SECONDS:
            return
        self._rec_sent = (count, now)
        self._send_mixxx(RECORDINGS_CC + bytes([count]))

    def _frozen(self):
        if self.state.playlist >= PL_ANALYSE:
            self._freeze_until = time.monotonic() + FREEZE_AFTER_SECONDS
        return time.monotonic() < self._freeze_until

    def _analyse_playlist(self, cursor):
        """Convert on a playlist (pusher-script.js PUSH2T.plAnalyse): the
        script has selected it in Mixxx's sidebar; queue it for analysis."""
        ok = False
        try:
            time.sleep(ANALYSE_SETTLE_SECONDS)
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:   # until the highlight is on a playlist
                frame = self._raw_frame
                if frame is not None and PlaylistPage.depth(frame) == 2:
                    break
                time.sleep(0.05)
            target = self.playlist_page.playlist_at(cursor)
            if frame is not None and target and PlaylistPage.depth(frame) == 2:
                ok = playlist_analysis.queue(frame)
                if ok:
                    self.analysis.add(*target)
            else:
                print('[analyse] the sidebar never reached the playlist', flush=True)
        except Exception as e:
            print(f'[analyse] failed: {e}', flush=True)
        finally:
            self._send_mixxx(ANALYSED_CC + bytes([1 if ok else 2]))

    def _check_drift(self, shown, pl, nav):
        """Mixxx's Playlists page under another painted nav entry: the real
        sidebar drifted from the nav - ask the script to re-home it."""
        drifted = (shown and pl == 0 and 0 < nav != NAV_TREE_OPEN
                   and NAV_NAMES[min(nav - 1, len(NAV_NAMES) - 1)] != 'Playlists')
        now = time.monotonic()
        if not drifted:
            self._drift_since = None
            return
        if self._drift_since is None:
            self._drift_since = now
        if now - self._drift_since >= RESYNC_AFTER_SECONDS and now - self._resync_at >= RESYNC_EVERY_SECONDS:
            self._resync_at = now
            print(f'[library] sidebar drifted from the nav ({NAV_NAMES[min(nav - 1, len(NAV_NAMES) - 1)]}), resync',
                  flush=True)
            self._send_mixxx(RESYNC_CC)

    def _report_playlists(self, count):
        """Tell the Push mapping whether the Playlists page shows (on change,
        and again every couple of seconds in case Mixxx restarted)."""
        count = min(count, 127)
        last, at = self._pl_sent
        now = time.monotonic()
        # "gone" only once it stayed gone a moment: the sidebar passing
        # through other rows (opening / analysing a playlist) mustn't drop
        # the list's cursor
        if count == 0 and last:
            if self._pl_gone_since is None:
                self._pl_gone_since = now
            if now - self._pl_gone_since < PLAYLISTS_GONE_SECONDS:
                return
        self._pl_gone_since = None
        if count == last and (count == 0 or now - at < PLAYLISTS_RESEND_SECONDS):
            return
        if count != last:
            print(f'[library] playlists page: {count}', flush=True)
        self._pl_sent = (count, now)
        self._send_mixxx(PLAYLISTS_CC + bytes([count]))

    def _send_mixxx(self, data):
        """Bytes to the Push mapping, as if they came from the Push (Pi only)."""
        if not os.path.exists(MIXXX_RAWMIDI):
            return
        try:
            fd = os.open(MIXXX_RAWMIDI, os.O_WRONLY | os.O_NONBLOCK)
            try:
                os.write(fd, data)
            finally:
                os.close(fd)
        except OSError as e:
            print(f'[library] cannot reach the mapping: {e}', flush=True)

    def _rec_overlay(self, img):
        """Countdown while REC is held (push-mixxx toggles recording at the end)."""
        held = time.monotonic() - (self._rec_pressed_at or time.monotonic())
        if held > REC_HOLD_SECONDS + 1.0:
            return img
        stopping = self.state.rec_status != 0
        if held < REC_HOLD_SECONDS:
            title = 'STOP RECORDING' if stopping else 'START RECORDING'
            return self._box(img, title, 'keep holding REC', held / REC_HOLD_SECONDS)
        return self._box(img, 'RECORDING' if stopping else 'RECORDING STOPPED', 'release REC', 1.0)

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
            if not self.push2.send_prepared(data):
                self._reconnect_display()
                continue

            sent += 1
            now = time.perf_counter()
            if now - window_start >= FPS_LOG_SECONDS:
                self.fps = sent / (now - window_start)
                print(f"[display] {self.fps:.1f} fps", flush=True)
                sent, window_start = 0, now

    def _reconnect_display(self):
        """Push unplugged (or never found): retry the USB display once a second."""
        print("[display] Push 2 display lost - waiting for it to come back", flush=True)
        self.push2.disconnect()
        while self.running and not self.push2.connect():
            time.sleep(1.0)

    def start(self, rawmidi_path=None):
        """Start the bridge"""
        print("Starting Mixxx MIDI Bridge...")

        if not self.push2.connect():
            print("Push 2 not found - waiting for it")
            self.running = True
            self._reconnect_display()

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
    parser.add_argument('--push-port', default=PUSH_PORT_MATCH,
                        help='MIDI port name (substring) for the Push buttons/LEDs - Pi: "VirMIDI 7-1"')
    parser.add_argument('--music-drive', help='Pi: mount point of the USB music drive - enables '
                                              'the drive status screens and SHIFT+SETUP eject')

    args = parser.parse_args()

    bridge = MixxxMidiBridge(args.music_drive, args.push_port)

    if args.list_ports:
        bridge.list_midi_ports()
        return

    if not args.rawmidi:
        bridge.connect_midi(args.input, args.output)
    bridge.start(args.rawmidi)


if __name__ == '__main__':
    main()
