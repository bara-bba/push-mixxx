"""Recordings and Auto DJ pages of the Browse screen, painted over Mixxx (Pi).

Recordings (nav on Recordings): the right pane shows the recording in progress
on top - or how to start one - and the recordings folder below as a list
(name, date, length, size), newest first. pusher-script.js (PUSH2T.rec) keeps
the list cursor and the two-press DELETE; this module reports the number of
files (CC 122 on channel 16, from mixxx-midi-bridge.py) and deletes the file
when asked ([Skin],pusher_rec = 2000 + cursor, armed first with 1000 + cursor).

Auto DJ (nav on Auto DJ): Mixxx's own queue table stays; its control row,
whose buttons have no labels in Pusher160, is covered by a summary of the
queue (from the drive's library), and the sort labels above the table by the
labels of the Push buttons that drive Auto DJ on this page (PUSH2T.autoDJButton).
"""

import configparser
import os
import shutil
import sqlite3
import struct
import time

from PIL import ImageDraw

from pi_stats import BODY_BOLD_FONTS, BODY_FONTS, DIM, EDGE, FAINT, INK, LIME, LINE, _font

PANE_X = 282
HEAD_H = 20
SIDEBAR_FOCUS_Y = 68
RED = (230, 50, 40)
REC_ARMED = 1000
REC_DELETE = 2000

AUDIO_EXT = {'.wav', '.flac', '.mp3', '.ogg', '.opus', '.aiff', '.aif', '.m4a'}
MIXXX_CFG = os.path.expanduser('~/.mixxx/mixxx.cfg')
DEFAULT_REC_DIR = os.path.expanduser('~/Music/Mixxx/Recordings')
LIST_REFRESH_SECONDS = 1.0
LIVE_SECONDS = 15   # a file written to this recently is the recording in progress

# Push 2 top display buttons: CC 102 + i sits above x 120 * i .. 120 * (i + 1)
AUTODJ_LABELS = {104: 'AUTO DJ', 105: 'FADE NOW', 106: 'SKIP NEXT', 107: 'SHUFFLE', 108: '+ RANDOM'}
# shown on the button's label for a moment after a press (one-shot actions)
AUTODJ_DONE = {105: 'FADING…', 106: 'SKIPPED', 107: 'SHUFFLED', 108: '+1 SONG'}
AUTODJ_FLASH_SECONDS = 0.9
AUTODJ_NEWS_SECONDS = 4.0   # the summary line tells what + RANDOM added / that SHUFFLE shuffled


def _fmt_dur(seconds):
    if seconds is None:
        return '—'
    seconds = int(seconds)
    h, m, s = seconds // 3600, seconds // 60 % 60, seconds % 60
    return f'{h}:{m:02d}:{s:02d}' if h else f'{m}:{s:02d}'


def _fmt_size(n):
    for unit in ('B', 'KB', 'MB', 'GB'):
        if n < 1024 or unit == 'GB':
            return f'{n:.0f} {unit}' if unit in ('B', 'KB') else f'{n:.1f} {unit}'
        n /= 1024


def _wav_seconds(path, size):
    """Length of a WAV from its header's byte rate and the file size (the
    header's own sizes are only filled in when the recording stops)."""
    try:
        with open(path, 'rb') as f:
            head = f.read(36)
        if head[:4] != b'RIFF' or head[8:12] != b'WAVE':
            return None
        byte_rate = struct.unpack('<I', head[28:32])[0]
        return max(size - 44, 0) / byte_rate if byte_rate else None
    except (OSError, struct.error):
        return None


def _fit(draw, text, font, room):
    if draw.textlength(text, font=font) <= room:
        return text
    while text and draw.textlength(text + '…', font=font) > room:
        text = text[:-1]
    return text + '…'


def recordings_dir():
    """Mixxx's [Recording] Directory (mixxx.cfg: "Key value" lines under [Group])."""
    try:
        with open(MIXXX_CFG, encoding='utf-8', errors='replace') as f:
            group = None
            for line in f:
                line = line.strip()
                if line.startswith('['):
                    group = line
                elif group == '[Recording]' and line.startswith('Directory '):
                    return line[len('Directory '):].strip() or DEFAULT_REC_DIR
    except OSError:
        pass
    return DEFAULT_REC_DIR


class RecordingsPage:
    def __init__(self):
        self.files = []        # newest first: dicts name, path, size, mtime, seconds
        self._read_at = 0.0
        self._armed = None     # path armed for deletion
        self.dir = DEFAULT_REC_DIR
        self._f_head = _font(BODY_BOLD_FONTS, 11)
        self._f_big = _font(BODY_BOLD_FONTS, 16)
        self._f = _font(BODY_FONTS, 12)
        self._f_meta = _font(BODY_FONTS, 10)

    @property
    def count(self):
        self._load()
        return len(self.files)

    def _load(self, force=False):
        now = time.monotonic()
        if not force and now - self._read_at < LIST_REFRESH_SECONDS:
            return
        self._read_at = now
        self.dir = recordings_dir()
        files = []
        try:
            entries = list(os.scandir(self.dir))
        except OSError:
            entries = []
        for e in entries:
            ext = os.path.splitext(e.name)[1].lower()
            if ext not in AUDIO_EXT or not e.is_file():
                continue
            st = e.stat()
            files.append({'name': os.path.splitext(e.name)[0], 'ext': ext[1:].upper(), 'path': e.path,
                          'size': st.st_size, 'mtime': st.st_mtime,
                          'seconds': _wav_seconds(e.path, st.st_size) if ext == '.wav' else None})
        files.sort(key=lambda f: f['mtime'], reverse=True)
        self.files = files

    def _live(self, rec_status):
        """The file being recorded, or None."""
        if not rec_status or not self.files:
            return None
        f = self.files[0]
        return f if time.time() - f['mtime'] < LIVE_SECONDS else None

    def request(self, value, rec_status):
        """[Skin],pusher_rec changed: remember the armed file / delete it."""
        self._load(force=True)
        if REC_ARMED <= value < REC_DELETE:
            i = value - REC_ARMED
            live = self._live(rec_status)
            f = self.files[i] if i < len(self.files) else None
            self._armed = f['path'] if f and f is not live else None
        elif value >= REC_DELETE:
            i = value - REC_DELETE
            f = self.files[i] if i < len(self.files) else None
            if f and f['path'] == self._armed:
                self._delete(f['path'])
            self._armed = None
            self._load(force=True)
        else:
            self._armed = None

    @staticmethod
    def _delete(path):
        stem = os.path.splitext(path)[0]
        for p in (path, stem + '.cue'):
            try:
                os.remove(p)
                print(f'[recordings] deleted {p}', flush=True)
            except FileNotFoundError:
                pass
            except OSError as e:
                print(f'[recordings] cannot delete {p}: {e}', flush=True)

    def draw(self, frame, value, rec_status):
        """Paint the right pane; value = [Skin],pusher_rec."""
        self._load()
        draw = ImageDraw.Draw(frame)
        draw.rectangle([PANE_X, 0, 959, 159], fill=INK)
        cursor = -1
        armed = False
        if 0 < value < REC_ARMED:
            cursor = value - 1
        elif REC_ARMED <= value < REC_DELETE:
            cursor, armed = value - REC_ARMED, True
        n = len(self.files)
        draw.text((PANE_X + 8, 4), f'RECORDINGS · {n}', font=self._f_head, fill=LINE)
        hint = 'HOLD REC: START / STOP     DELETE ×2: REMOVE'
        draw.text((959 - 8 - draw.textlength(hint, font=self._f_head), 4), hint, font=self._f_head, fill=DIM)
        if cursor >= 0:
            draw.rectangle([PANE_X, HEAD_H, 959, HEAD_H + 1], fill=LIME)
            draw.rectangle([0, SIDEBAR_FOCUS_Y, PANE_X - 3, SIDEBAR_FOCUS_Y + 1], fill=INK)
        else:
            draw.line([PANE_X, HEAD_H, 959, HEAD_H], fill=EDGE)

        # now: the recording in progress, or how to start one
        live = self._live(rec_status)
        x, y = PANE_X + 10, HEAD_H + 6
        try:
            free = shutil.disk_usage(self.dir if os.path.isdir(self.dir) else os.path.expanduser('~')).free
        except OSError:
            free = None
        free_txt = f'{_fmt_size(free)} free' if free is not None else ''
        if rec_status == 2 or live:
            draw.ellipse([x, y + 3, x + 12, y + 15], fill=RED)
            draw.text((x + 20, y), 'RECORDING', font=self._f_big, fill=LINE)
            tx = x + 20 + draw.textlength('RECORDING', font=self._f_big) + 16
            if live:
                draw.text((tx, y), _fmt_dur(live['seconds']), font=self._f_big, fill=LIME)
                tx += draw.textlength(_fmt_dur(live['seconds']), font=self._f_big) + 16
                draw.text((tx, y + 4), _fmt_size(live['size']), font=self._f, fill=DIM)
                draw.text((x + 20, y + 19), _fit(draw, f"{live['name']}.{live['ext'].lower()}", self._f_meta, 420),
                          font=self._f_meta, fill=FAINT)
            else:
                draw.text((x + 20, y + 19), 'waiting for the first audio…', font=self._f_meta, fill=FAINT)
        elif rec_status == 1:
            draw.ellipse([x, y + 3, x + 12, y + 15], outline=RED, width=2)
            draw.text((x + 20, y), 'WAITING FOR AUDIO', font=self._f_big, fill=LINE)
            draw.text((x + 20, y + 19), 'Mixxx is ready to record but gets no audio to record',
                      font=self._f_meta, fill=FAINT)
        else:
            draw.ellipse([x, y + 3, x + 12, y + 15], outline=DIM, width=2)
            draw.text((x + 20, y), 'NOT RECORDING', font=self._f_big, fill=DIM)
            draw.text((x + 20, y + 19), 'hold REC to start', font=self._f_meta, fill=FAINT)
        draw.text((959 - 10 - draw.textlength(free_txt, font=self._f), y + 2), free_txt, font=self._f, fill=DIM)

        # the folder
        top = 62
        draw.line([PANE_X, top - 2, 959, top - 2], fill=EDGE)
        cols = [('NAME', PANE_X + 10), ('DATE', 700), ('LENGTH', 820), ('SIZE', 890)]
        for label, cx in cols:
            draw.text((cx, top), label, font=self._f_meta, fill=FAINT)
        row_h, y0, rows = 16, top + 14, 5
        if not self.files:
            draw.text((PANE_X + 10, y0 + 4), 'No recordings yet', font=self._f, fill=DIM)
            return frame
        first = max(0, min(cursor - rows // 2, n - rows)) if cursor >= 0 else 0
        for i, f in enumerate(self.files[first:first + rows]):
            idx = first + i
            yy = y0 + i * row_h
            on = idx == cursor
            fill, fg, meta = None, LINE, DIM
            if on:
                fill, fg, meta = (RED if armed else LIME), INK, INK
            if fill:
                draw.rectangle([PANE_X + 2, yy - 1, 957, yy + row_h - 2], fill=fill)
            is_live = f is live
            name = ('● ' if is_live else '') + f['name']
            draw.text((PANE_X + 10, yy), _fit(draw, name, self._f, 700 - PANE_X - 24), font=self._f,
                      fill=RED if is_live and not on else fg)
            if on and armed:
                msg = 'DELETE AGAIN TO REMOVE'
                draw.text((700, yy + 1), msg, font=self._f_head, fill=INK)
                continue
            date = time.strftime('%d %b %H:%M', time.localtime(f['mtime']))
            draw.text((700, yy + 1), date, font=self._f_meta, fill=meta)
            draw.text((820, yy + 1), _fmt_dur(f['seconds']), font=self._f_meta, fill=meta)
            draw.text((890, yy + 1), _fmt_size(f['size']), font=self._f_meta, fill=meta)
        return frame


class AutoDJPage:
    def __init__(self, music_drive):
        self.db_path = os.path.join(music_drive, '.mixxx', 'mixxxdb.sqlite') if music_drive else None
        self._queue = []      # (artist, title, duration) in play order
        self.shuffle_on = False   # latching SHUFFLE (state from pusher-script.js)
        self._read_at = 0.0
        self._f_head = _font(BODY_BOLD_FONTS, 11)
        self._f = _font(BODY_FONTS, 12)
        self._f_meta = _font(BODY_FONTS, 10)

    def _load(self):
        now = time.monotonic()
        if now - self._read_at < 2.0 or not self.db_path:
            return
        self._read_at = now
        try:
            db = sqlite3.connect(f'file:{self.db_path}?mode=ro', uri=True, timeout=0.2)
            try:
                # hidden 1 = the Auto DJ queue
                self._queue = db.execute(
                    'select l.artist, l.title, l.duration, l.album, l.bpm, l.key from PlaylistTracks pt '
                    'join Playlists p on p.id = pt.playlist_id and p.hidden = 1 '
                    'join library l on l.id = pt.track_id and l.mixxx_deleted = 0 '
                    'order by pt.position').fetchall()
                # the song added last (+ RANDOM appends it at the end, out of sight)
                self._newest = db.execute(
                    'select pt.id, l.title, l.artist, pt.position from PlaylistTracks pt '
                    'join Playlists p on p.id = pt.playlist_id and p.hidden = 1 '
                    'join library l on l.id = pt.track_id '
                    'order by pt.pl_datetime_added desc, pt.id desc limit 1').fetchone()
            finally:
                db.close()
        except sqlite3.Error as e:
            print(f'[autodj] library read failed: {e}', flush=True)

    def draw_queue(self, frame):
        """The queue as a table, in the skin's columns - shown while Mixxx is
        still switching to its own Auto DJ table (it takes about half a second)."""
        self._load()
        draw = ImageDraw.Draw(frame)
        draw.rectangle([PANE_X, 46, 959, 159], fill=INK)
        cols = [(PANE_X + 72, 236), (524, 144), (674, 124), (806, 46), (860, 42), (908, 48)]
        for i, (artist, title, dur, album, bpm, key) in enumerate(self._queue[:5]):
            y = 50 + i * 20
            vals = [title or '', artist or '', album or '', f'{bpm:.1f}' if bpm else '-', key or '',
                    _fmt_dur(dur)]
            for (x, w), v in zip(cols, vals):
                draw.text((x, y), _fit(draw, v, self._f, w - 6), font=self._f, fill=LINE)
        return frame

    @property
    def queue(self):
        return self._queue

    def refresh(self):
        self._load()

    def refresh_soon(self):
        self._read_at = 0.0   # re-read the queue on the next draw

    def pressed(self, cc):
        """A top button was pressed (mixxx-midi-bridge.py hears the Push):
        confirm it on its label, and re-read the queue shortly after."""
        if cc in AUTODJ_DONE:
            self._flash = (cc, time.monotonic())
            if cc == 108:
                self._before = getattr(self, '_newest', None)
            self._read_at = time.monotonic() - 1.6   # reload in ~0.4 s, once Mixxx has it

    def draw(self, frame, enabled):
        self._load()
        flash_cc, flash_at = getattr(self, '_flash', (None, 0.0))
        if time.monotonic() - flash_at > AUTODJ_FLASH_SECONDS:
            flash_cc = None
        draw = ImageDraw.Draw(frame)
        # button labels over the sort labels, one per Push button column
        draw.rectangle([PANE_X, 0, 959, HEAD_H - 1], fill=INK)
        for cc, label in AUTODJ_LABELS.items():
            x0 = max(120 * (cc - 102), PANE_X) + 3
            x1 = 120 * (cc - 101) - 4
            on = (cc == 104 and enabled) or (cc == 107 and self.shuffle_on) or cc == flash_cc
            if on:
                draw.rectangle([x0, 2, x1, HEAD_H - 3], fill=LIME)
            else:
                draw.rectangle([x0, 2, x1, HEAD_H - 3], outline=EDGE)
            text = AUTODJ_DONE[cc] if cc == flash_cc else (
                ('AUTO DJ ON' if cc == 104 else 'SHUFFLE ON') if on else label)
            tw = draw.textlength(text, font=self._f_head)
            draw.text(((x0 + x1 - tw) / 2, 4), text, font=self._f_head, fill=INK if on else LINE)
        # queue summary over Mixxx's control row
        y0, y1 = HEAD_H + 2, 45
        draw.rectangle([PANE_X, y0, 959, y1], fill=INK)
        draw.line([PANE_X, y1, 959, y1], fill=EDGE)
        x = PANE_X + 10
        n = len(self._queue)
        if not n:
            draw.text((x, y0 + 5), 'Queue empty', font=self._f_head, fill=LINE)
            hint = 'add songs from Tracks / Playlists with the 2nd top button (SHIFT: to the top)'
            draw.text((x + 90, y0 + 6), hint, font=self._f_meta, fill=DIM)
            return frame
        total = sum(q[2] or 0 for q in self._queue)
        summary = f'{n} song{"s" if n != 1 else ""} · {_fmt_dur(total)}'
        draw.text((x, y0 + 5), summary, font=self._f_head, fill=LINE)
        x += draw.textlength(summary, font=self._f_head) + 20
        artist, title = self._queue[0][:2]
        tag, nxt = 'NEXT', ' — '.join(t for t in (title, artist) if t)
        news_cc, news_at = getattr(self, '_flash', (None, 0.0))
        if time.monotonic() - news_at < AUTODJ_NEWS_SECONDS:
            newest = getattr(self, '_newest', None)
            if news_cc == 108:
                if newest and newest != getattr(self, '_before', None):
                    tag = 'ADDED'
                    nxt = ' — '.join(t for t in newest[1:3] if t) + f'  (#{newest[3]}, at the end)'
                else:
                    tag, nxt = 'ADDING', 'a random song…'
            elif news_cc == 107:
                tag = 'SHUFFLED · NEXT'
        draw.text((x, y0 + 6), tag, font=self._f_meta, fill=LIME if tag != 'NEXT' else FAINT)
        x += draw.textlength(tag, font=self._f_meta) + 10
        draw.text((x, y0 + 4), _fit(draw, nxt, self._f, 959 - 10 - x - 130), font=self._f, fill=LINE)
        hint = 'DELETE: remove song'
        draw.text((959 - 10 - draw.textlength(hint, font=self._f_meta), y0 + 6), hint, font=self._f_meta, fill=DIM)
        return frame
