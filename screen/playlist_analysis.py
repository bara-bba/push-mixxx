"""Convert on a playlist: Mixxx analyses it in the background (Pi).

Mixxx's playlist right-click menu has "Analyse entire Playlist", which queues
the playlist's tracks in Mixxx's background analyser (the Analyze view's): no
track loads and browsing goes on. Controller scripts can't reach that menu, so
pusher-script.js (PUSH2T.plAnalyse) selects the playlist in Mixxx's sidebar
and asks for it ([Skin],pusher_playlist = 256 + cursor); queue() right-clicks
the highlighted sidebar row in the Xvfb display and clicks the entry.

AnalysisProgress follows the queued playlists in the drive's library: a track
counts as done once it has a stored waveform (the analyser writes it with the
beats and key), and draw() puts a progress bar at the bottom of the Browse page.
"""

import os
import sqlite3
import subprocess
import time

from PIL import ImageDraw

from mixxx_capture import _x11_focus_main
from pi_stats import BODY_BOLD_FONTS, BODY_FONTS, DIM, EDGE, INK, LIME, LINE, _font

# Pusher160 sidebar rows (playlist_page.py SIDEBAR_BOX), the highlight is lime
SIDEBAR_BOX = (0, 70, 280, 160)
RIGHT_CLICK_X = 100
# The menu Mixxx 2.5 opens on a playlist in a 960x160 window: two columns,
# always this size; "Analyse entire Playlist" is the right column's 3rd entry
# (measured on the Pi: menu at (80, 0) -> item text at (294, 54)).
MENU_SIZE = (412, 154)
MENU_ITEM = (260, 54)   # click point relative to the menu's top-left
MENU_WAIT_SECONDS = 1.5

ANALYSIS_DIR = os.path.expanduser('~/.mixxx/analysis')
REFRESH_SECONDS = 2.0
DONE_SHOW_SECONDS = 5.0
STALL_SECONDS = 240.0   # no track finished for this long: stop following it

BAR_Y = 146   # bottom strip of the Browse page, right pane
PANE_X = 282


def _xdo(*args):
    try:
        return subprocess.run(['xdotool', *args], capture_output=True, text=True, timeout=2).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ''


def highlighted_row(frame):
    """Middle y of Mixxx's highlighted sidebar row in a raw capture, or None."""
    x0, y0, x1, y1 = SIDEBAR_BOX
    rows = [y for y in range(y0, min(y1, frame.height)) if frame.getpixel((2, y)) == LIME]
    return rows[len(rows) // 2] if rows else None


def _menus():
    """{window id: (x, y, w, h)} of Mixxx's visible windows other than its main one."""
    out = {}
    for wid in _xdo('search', '--onlyvisible', '--class', 'mixxx').split():
        geo = _xdo('getwindowgeometry', '--shell', wid)
        vals = dict(line.split('=', 1) for line in geo.split() if '=' in line)
        try:
            box = tuple(int(vals[k]) for k in ('X', 'Y', 'WIDTH', 'HEIGHT'))
        except (KeyError, ValueError):
            continue
        if box[2:] != (960, 160):
            out[wid] = box
    return out


def queue(frame):
    """Right-click the highlighted sidebar row and pick "Analyse entire
    Playlist". True when the click went to a menu of the expected shape."""
    y = highlighted_row(frame)
    if y is None:
        print('[analyse] no highlighted sidebar row', flush=True)
        return False
    before = set(_menus())
    _xdo('mousemove', str(RIGHT_CLICK_X), str(y), 'click', '3')
    deadline = time.monotonic() + MENU_WAIT_SECONDS
    menu = None
    while time.monotonic() < deadline and menu is None:
        time.sleep(0.05)
        menu = next((box for wid, box in _menus().items() if wid not in before), None)
    if menu is None:
        print('[analyse] no context menu opened', flush=True)
        _refocus()
        return False
    mx, my, mw, mh = menu
    if (mw, mh) != MENU_SIZE:
        print(f'[analyse] unexpected menu {mw}x{mh}, closing it', flush=True)
        _xdo('key', 'Escape')
        _refocus()
        return False
    _xdo('mousemove', str(mx + MENU_ITEM[0]), str(my + MENU_ITEM[1]), 'click', '1')
    _xdo('mousemove', '959', '0')   # park the pointer off the library
    _refocus()
    return True


def _refocus():
    """With no window manager, the closed menu leaves no window focused and
    Mixxx then drops the script's library keys: focus its main window again."""
    deadline = time.monotonic() + MENU_WAIT_SECONDS
    while _menus() and time.monotonic() < deadline:
        time.sleep(0.05)
    _x11_focus_main()


class AnalysisProgress:
    """Playlists queued for analysis and how far Mixxx got with them."""

    def __init__(self, music_drive):
        self.db_path = os.path.join(music_drive, '.mixxx', 'mixxxdb.sqlite') if music_drive else None
        self.jobs = []        # [{'name', 'tracks': set of ids}]
        self._done = set()    # finished track ids among the jobs'
        self._read_at = 0.0
        self._changed_at = 0.0
        self._finished = None  # (text, monotonic) shown for a while after the last job
        self._f_bold = _font(BODY_BOLD_FONTS, 11)
        self._f = _font(BODY_FONTS, 11)

    def _db(self):
        return sqlite3.connect(f'file:{self.db_path}?mode=ro', uri=True, timeout=0.2)

    def add(self, playlist_id, name):
        if not self.db_path:
            return
        try:
            db = self._db()
            try:
                ids = {r[0] for r in db.execute(
                    'select pt.track_id from PlaylistTracks pt join library l on l.id = pt.track_id '
                    'where pt.playlist_id = ? and l.mixxx_deleted = 0', (playlist_id,))}
            finally:
                db.close()
        except sqlite3.Error as e:
            print(f'[analyse] library read failed: {e}', flush=True)
            return
        print(f'[analyse] following "{name}": {len(ids)} tracks', flush=True)
        self.jobs.append({'name': name, 'tracks': ids})
        self._finished = None
        self._read_at = 0.0
        self._changed_at = time.monotonic()

    def _refresh(self):
        now = time.monotonic()
        if not self.jobs or now - self._read_at < REFRESH_SECONDS:
            return
        self._read_at = now
        wanted = set().union(*(j['tracks'] for j in self.jobs))
        try:
            db = self._db()
            try:
                rows = db.execute(
                    "select track_id, id from track_analysis where type = '1' and track_id in (%s)"
                    % ','.join('?' * len(wanted)), tuple(wanted)).fetchall() if wanted else []
            finally:
                db.close()
        except sqlite3.Error as e:
            print(f'[analyse] library read failed: {e}', flush=True)
            return
        # a waveform row whose file is gone (the cache is cleared each boot) isn't done
        done = {t for t, aid in rows if os.path.exists(os.path.join(ANALYSIS_DIR, str(aid)))}
        if done != self._done:
            self._done = done
            self._changed_at = now
        if all(j['tracks'] <= done for j in self.jobs):
            names = ', '.join(j['name'] for j in self.jobs)
            self._finished = (f'ANALYSED  {names}  ·  {len(wanted)} TRACKS', now)
            print(f'[analyse] done: {names}', flush=True)
            self.jobs = []
        elif now - self._changed_at > STALL_SECONDS:
            print(f'[analyse] no progress for {STALL_SECONDS:.0f}s, stopped following', flush=True)
            self.jobs = []

    @property
    def showing(self):
        """True while the bar is on screen (a job, or the done note)."""
        return bool(self.jobs) or (self._finished is not None
                                    and time.monotonic() - self._finished[1] < DONE_SHOW_SECONDS)

    def draw(self, frame):
        """Progress strip at the bottom of the Browse page's right pane."""
        self._refresh()
        now = time.monotonic()
        if self.jobs:
            wanted = set().union(*(j['tracks'] for j in self.jobs))
            n_done, total = len(wanted & self._done), len(wanted)
            names = ', '.join(j['name'] for j in self.jobs)
            label, frac = f'ANALYSING  {names}', (n_done / total if total else 1.0)
            count = f'{n_done} / {total}'
        elif self._finished and now - self._finished[1] < DONE_SHOW_SECONDS:
            label, frac, count = self._finished[0], 1.0, ''
        else:
            self._finished = None
            return frame
        draw = ImageDraw.Draw(frame)
        x0, y0, x1, y1 = PANE_X, BAR_Y, 959, 159
        draw.rectangle([x0, y0, x1, y1], fill=INK)
        draw.line([x0, y0, x1, y0], fill=EDGE)
        bar_x0, bar_x1 = 760, x1 - 8
        cw = draw.textlength(count, font=self._f)
        room = bar_x0 - 12 - cw - 10 - (x0 + 8)
        if draw.textlength(label, font=self._f_bold) > room:
            while label and draw.textlength(label + '…', font=self._f_bold) > room:
                label = label[:-1]
            label += '…'
        draw.text((x0 + 8, y0 + 1), label, font=self._f_bold, fill=LINE)
        draw.text((bar_x0 - 10 - cw, y0 + 1), count, font=self._f, fill=DIM)
        by0, by1 = y0 + 4, y1 - 3
        draw.rectangle([bar_x0, by0, bar_x1, by1], outline=EDGE)
        fill_x = bar_x0 + 1 + int((bar_x1 - bar_x0 - 2) * frac)
        if fill_x > bar_x0 + 1:
            draw.rectangle([bar_x0 + 1, by0 + 1, fill_x, by1 - 1], fill=LIME)
        return frame
