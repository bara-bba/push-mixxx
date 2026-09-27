"""
Cover-art lookup for the Push 2 display.

mixxx-midi-bridge.py's SysEx protocol only carries title/artist/bpm/position -
Mixxx has no MIDI-side way to send image data. So cover art is fetched
directly from Mixxx's own library database (mixxxdb.sqlite) by matching
title+artist, then either used as-is (coverart_type FILE, e.g. folder.jpg)
or extracted from the audio file's embedded tags via mutagen.

Opened read-only so it never contends with Mixxx's own connection to the
same file, and every lookup is cached (including misses) since deck state
only changes a few times a minute.
"""

import os
import sqlite3

from PIL import Image

try:
    import mutagen
except ImportError:
    mutagen = None

DEFAULT_DB_PATH = os.path.expandvars(r"%LOCALAPPDATA%\Mixxx\mixxxdb.sqlite")

# Mixxx library.coverart_type values
COVERART_NONE = 0
COVERART_FILE = 1
COVERART_EMBEDDED = 2


class ArtworkCache:
    """Looks up + resizes cover art, caching by (artist, title)."""

    def __init__(self, db_path=None, size=120):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.size = size
        self._cache = {}  # (artist, title) -> PIL.Image or None

    def get(self, artist, title):
        key = (artist.strip().lower(), title.strip().lower())
        if not key[1]:
            return None
        if key in self._cache:
            return self._cache[key]

        img = self._lookup(artist, title)
        if img is not None:
            img = self._fit_square(img)
        self._cache[key] = img
        return img

    def _connect(self):
        uri = f"file:{self.db_path}?mode=ro"
        return sqlite3.connect(uri, uri=True, timeout=1.0)

    def _lookup(self, artist, title):
        if not os.path.exists(self.db_path):
            return None
        try:
            con = self._connect()
        except sqlite3.OperationalError:
            return None

        try:
            cur = con.cursor()
            cur.execute(
                """
                SELECT l.coverart_type, l.coverart_location, tl.location, tl.directory
                FROM library l
                JOIN track_locations tl ON l.location = tl.id
                WHERE l.title = ? COLLATE NOCASE AND l.artist = ? COLLATE NOCASE
                LIMIT 1
                """,
                (title, artist),
            )
            row = cur.fetchone()
        except sqlite3.Error:
            return None
        finally:
            con.close()

        if not row:
            return None

        coverart_type, coverart_location, file_location, directory = row
        return self._load_image(coverart_type, coverart_location, file_location, directory)

    def _load_image(self, coverart_type, coverart_location, file_location, directory):
        if coverart_type == COVERART_FILE and coverart_location:
            path = coverart_location
            if not os.path.isabs(path):
                path = os.path.join(directory or '', path)
            if os.path.exists(path):
                try:
                    return Image.open(path).convert('RGB')
                except Exception:
                    pass

        # Embedded (or FILE type with no usable location) - pull tag art
        if mutagen and file_location and os.path.exists(file_location):
            try:
                data = self._extract_embedded(file_location)
                if data:
                    from io import BytesIO
                    return Image.open(BytesIO(data)).convert('RGB')
            except Exception:
                pass

        return None

    def _extract_embedded(self, path):
        f = mutagen.File(path)
        if f is None:
            return None

        # ID3 (mp3, aiff, wav): APIC frames
        if hasattr(f, 'tags') and f.tags:
            for key in f.tags.keys():
                if key.startswith('APIC'):
                    return f.tags[key].data

        # FLAC / OGG: .pictures
        pictures = getattr(f, 'pictures', None)
        if pictures:
            return pictures[0].data

        # MP4/M4A: 'covr' atom
        if hasattr(f, 'tags') and f.tags and 'covr' in f.tags:
            covr = f.tags['covr']
            if covr:
                return bytes(covr[0])

        return None

    def _fit_square(self, img):
        w, h = img.size
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        img = img.crop((left, top, left + side, top + side))
        return img.resize((self.size, self.size), Image.LANCZOS)
