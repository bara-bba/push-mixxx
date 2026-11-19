"""The Browse screen's library nav and playlist list, painted over Mixxx.

Nav: Mixxx's sidebar can't be reordered or have sections hidden, so the left
column's nav is painted here (NAV_NAMES, no Crates) from the cursor
pusher-script.js keeps (PUSH2T.nav, [Skin],pusher_nav via bridge-script.js);
the script steers Mixxx's real sidebar to the same entry behind it. While
Mixxx's own folder tree is open (Computer/History) the real sidebar shows.
depth() tells the script whether the real highlight is on a top-level row.

Playlists: 
With the sidebar highlight on the Playlists root, Mixxx's right pane shows a
fixed help text instead of a list. The Pusher160 skin paints that text page a
one-off near-black (TEXT_PAGE_MARK, WLibraryTextBrowser in gen_skin.py), so
when the capture shows it this draws the drive's playlists there instead -
name, track count and length - read from the drive's Mixxx library.

The list is browsed with a cursor (pusher-script.js PUSH2T.pl): this module
reports the page to the script (CC 126 on channel 16, value = number of
playlists) and gets the cursor back through bridge-script.js ([Skin],
pusher_playlist). Opening a playlist has to select it in Mixxx's sidebar tree;
the painted nav hides that tree.
The list order must match the sidebar's (the script steps down to the cursor).
"""

import os
import sqlite3
import time

from PIL import Image, ImageDraw

from pi_stats import BODY_BOLD_FONTS, BODY_FONTS, DIM, EDGE, FAINT, INK, LIME, LINE, _font

TEXT_PAGE_MARK = (0x0B, 0x0B, 0x0D)  # gen_skin.py: WLibraryTextBrowser background

# Pusher160 library page geometry (gen_skin.py: LIB_LEFT_W = 280, a 2px rule,
# then the 678px right pane: 20px sort-label row, 2px focus bar, the table)
PANE_X = 282
PANE_TOP = 22
# pixels sampled for the marker: inside the text page, clear of its text
MARK_PROBES = [(300, 23), (900, 23), (900, 40), (600, 40)]
# Crates and Computer have text pages too; their bold heading tells them
# apart. Right end of the heading's ink (x, measured on the Pi): Playlists 358,
# Crates 340, Computer 370.
HEADING_BAND = (24, 48)
PLAYLISTS_HEADING_END = (353, 364)

# left column: preview, its 2px focus bar (lit while the sidebar has focus), the sidebar
SIDEBAR_FOCUS_Y = 68
SIDEBAR_BOX = (0, 70, 280, 160)
# Same order as pusher-script.js PUSH2T.NAV_REAL
NAV_NAMES = ['Tracks', 'Playlists', 'Auto DJ', 'Computer', 'Recordings', 'History', 'Analyze']
NAV_TREE_OPEN = 100   # [Skin],pusher_nav while Mixxx's own tree shows
NAV_ROWS = 5
NAV_ROW_H = 18
# Mixxx's highlighted sidebar row: the first non-lime pixel is the expand arrow
# or icon - x 8 / 23-24 on a top-level row, 28+ deeper (measured on the Pi)
DEPTH_X = 26
# Mixxx's own sidebar icons (cropped from its sidebar on the Pi), one 13x12
# alpha mask per NAV_NAMES entry, in that order; drawn in Mixxx's orange
NAV_ICONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'nav_icons.png')
NAV_ICON_W = 13
NAV_ICON_COLOR = (238, 95, 0)

HEAD_H = 20
ROWS = 8
ROW_H = 17
COLS = 3
DB_REFRESH_SECONDS = 3.0


def _fmt_len(seconds):
    seconds = int(seconds or 0)
    h, m = seconds // 3600, seconds // 60 % 60
    return f'{h}h{m:02d}' if h else f'{m}m'


class PlaylistPage:
    def __init__(self, music_drive):
        self.db_path = os.path.join(music_drive, '.mixxx', 'mixxxdb.sqlite') if music_drive else None
        self._playlists = []
        self._read_at = 0.0
        self._f_head = _font(BODY_BOLD_FONTS, 11)
        self._f_name = _font(BODY_FONTS, 12)
        self._f_meta = _font(BODY_FONTS, 10)
        self._f_nav = _font(BODY_FONTS, 13)
        try:
            strip = Image.open(NAV_ICONS).convert('L')
            self._icons = [strip.crop((i * NAV_ICON_W, 0, (i + 1) * NAV_ICON_W, strip.height))
                           for i in range(strip.width // NAV_ICON_W)]
        except OSError:
            self._icons = []

    @property
    def count(self):
        self._load()
        return len(self._playlists)

    @staticmethod
    def depth(frame):
        """1 = Mixxx's sidebar highlight is on a top-level row, 2 = deeper, 0 = none seen."""
        x0, y0, x1, y1 = SIDEBAR_BOX
        rows = [y for y in range(y0, y1) if frame.getpixel((2, y)) == LIME]
        if not rows:
            return 0
        y = rows[len(rows) // 2]
        first = next((x for x in range(0, 200) if frame.getpixel((x, y)) != LIME), 200)
        return 1 if first < DEPTH_X else 2

    def draw_nav(self, frame, cursor, rows=NAV_ROWS):
        """Paint the nav over Mixxx's sidebar, the cursor's entry highlighted;
        rows shown (fewer leaves the bottom free for the analysis bar)."""
        x0, y0, x1, y1 = SIDEBAR_BOX
        draw = ImageDraw.Draw(frame)
        draw.rectangle([x0, y0, x1 - 1, y0 + rows * NAV_ROW_H - 1], fill=INK)
        first = max(0, min(cursor - rows // 2, len(NAV_NAMES) - rows))
        for row, i in enumerate(range(first, min(first + rows, len(NAV_NAMES)))):
            y = y0 + row * NAV_ROW_H
            on = i == cursor
            if on:
                draw.rectangle([x0, y, x1 - 1, y + NAV_ROW_H - 2], fill=LIME)
            if i < len(self._icons):
                frame.paste(INK if on else NAV_ICON_COLOR, (x0 + 10, y + 3), self._icons[i])
            draw.text((x0 + 30, y + 1), NAV_NAMES[i], font=self._f_nav, fill=INK if on else LINE)
            if NAV_NAMES[i] == 'Playlists':
                n = str(self.count)
                draw.text((x1 - 10 - draw.textlength(n, font=self._f_meta), y + 3), n,
                          font=self._f_meta, fill=INK if on else FAINT)
        return frame

    @staticmethod
    def shown(frame):
        """True while the right pane shows Mixxx's Playlists text page."""
        if not all(frame.getpixel(p) == TEXT_PAGE_MARK for p in MARK_PROBES):
            return False
        y0, y1 = HEADING_BAND
        band = frame.crop((PANE_X, y0, 420, y1))
        w, h = band.size
        px = band.load()
        end = max((x for x in range(w) for y in range(h) if px[x, y] != TEXT_PAGE_MARK), default=-1)
        return PLAYLISTS_HEADING_END[0] <= PANE_X + end <= PLAYLISTS_HEADING_END[1]

    def playlist_at(self, i):
        """(id, name) of the i-th listed playlist, or None."""
        self._load()
        if 0 <= i < len(self._playlists):
            name, _, _, pid = self._playlists[i]
            return pid, name
        return None

    def _load(self):
        now = time.monotonic()
        if now - self._read_at < DB_REFRESH_SECONDS or not self.db_path:
            return
        self._read_at = now
        try:
            db = sqlite3.connect(f'file:{self.db_path}?mode=ro', uri=True, timeout=0.2)
            try:
                # hidden 0 = ordinary playlists (1 = Auto DJ, 2 = history sets)
                self._playlists = db.execute(
                    'select p.name, count(l.id), coalesce(sum(l.duration), 0), p.id from Playlists p '
                    'left join PlaylistTracks pt on pt.playlist_id = p.id '
                    'left join library l on l.id = pt.track_id and l.mixxx_deleted = 0 '
                    'where p.hidden = 0 group by p.id order by lower(p.name)').fetchall()
            finally:
                db.close()
        except sqlite3.Error as e:
            print(f'[playlists] library read failed: {e}', flush=True)

    def draw(self, frame, cursor=-1, rows=ROWS):
        """Draw the playlist list over the right pane (frame is modified);
        cursor >= 0 = list mode, that row highlighted and the pane focused;
        rows per column (fewer leaves the bottom free for the analysis bar)."""
        self._load()
        draw = ImageDraw.Draw(frame)
        draw.rectangle([PANE_X, 0, 959, 159], fill=INK)
        n = len(self._playlists)
        draw.text((PANE_X + 8, 4), f'PLAYLISTS · {n}', font=self._f_head, fill=LINE)
        hint = 'RIGHT ► OPEN'  # U+25B6 isn't in Liberation Sans, U+25BA is
        draw.text((959 - 8 - draw.textlength(hint, font=self._f_head), 4), hint, font=self._f_head, fill=DIM)
        if cursor >= 0:   # focus moved from the sidebar to this list
            draw.rectangle([PANE_X, HEAD_H, 959, HEAD_H + 1], fill=LIME)
            draw.rectangle([0, SIDEBAR_FOCUS_Y, PANE_X - 3, SIDEBAR_FOCUS_Y + 1], fill=INK)
        else:
            draw.line([PANE_X, HEAD_H, 959, HEAD_H], fill=EDGE)

        col_w = (960 - PANE_X) // COLS
        per_page = rows * COLS
        first = (max(cursor, 0) // per_page) * per_page
        for i, (name, count, length, _) in enumerate(self._playlists[first:first + per_page]):
            col, row = divmod(i, rows)
            x0 = PANE_X + col * col_w
            x = x0 + 8
            y = HEAD_H + 3 + row * ROW_H
            on = first + i == cursor
            if on:
                draw.rectangle([x0 + 2, y - 1, x0 + col_w - 3, y + ROW_H - 2], fill=LIME)
            meta = f'{count} · {_fmt_len(length)}'
            meta_w = draw.textlength(meta, font=self._f_meta)
            room = col_w - 16 - meta_w - 6
            if draw.textlength(name, font=self._f_name) > room:
                while name and draw.textlength(name + '…', font=self._f_name) > room:
                    name = name[:-1]
                name += '…'
            draw.text((x, y), name, font=self._f_name, fill=INK if on else LINE)
            draw.text((x + col_w - 16 - meta_w, y + 2), meta, font=self._f_meta, fill=INK if on else FAINT)
        if n > first + per_page:
            more = f'+{n - first - per_page} more'
            draw.text((959 - 8 - draw.textlength(more, font=self._f_meta), 160 - 13), more, font=self._f_meta, fill=DIM)
        return frame
