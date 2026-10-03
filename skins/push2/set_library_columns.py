"""Sets Mixxx's track table columns to the six the Pusher160 library page
labels on its top row - Title, Artist, Album, BPM, Key, Length - at the
widths below, so each sort label sits exactly above its own column (plus a
slim preview column under TITLE that marks the song playing in preview).

Mixxx keeps each library view's column layout in mixxxdb.sqlite (settings
table, '<view>.header_state_pb', a protobuf HeaderState), not in the skin, so
this rewrites those rows. Run with Mixxx closed (it saves layouts on exit;
on the Pi: sudo systemctl stop push2-screen mixxx);
the database is backed up next to itself first. Views opened for the first
time later (e.g. a playlist) start with Mixxx defaults: run this again.

    python set_library_columns.py [path/to/mixxxdb.sqlite]
"""
import base64
import os
import shutil
import sqlite3
import sys
import time

import psutil

if os.name == 'nt':
    DEFAULT_DB = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Mixxx', 'mixxxdb.sqlite')
else:
    DEFAULT_DB = os.path.expanduser('~/.mixxx/mixxxdb.sqlite')
# (column name, width) - also read by gen_skin.py, which sizes the sort-label
# row above the table from these so every label stays over its own column.
# Short columns (BPM/Key/Length) get just enough for their values so the text
# columns get the room; 'preview' marks the song playing in preview and sits
# under the TITLE label at Mixxx's minimum width (~39px).
COLUMNS = [('preview', 39), ('title', 199), ('artist', 150), ('album', 130), ('bpm', 56), ('key', 48),
           ('duration', 52)]
SCROLLBAR_W = 4  # the table's thin vertical scrollbar, right of the last column

# HeaderState { repeated HeaderSection sections = 1; sort fields 2-4 }
# HeaderSection { bool hidden = 1; int32 size = 2; int32 logical_index = 3;
#                 int32 visual_index = 4; string column_name = 5; }


def _varint(b, i):
    result = shift = 0
    while True:
        c = b[i]
        i += 1
        result |= (c & 0x7F) << shift
        shift += 7
        if c < 0x80:
            return result, i


def _fields(b):
    i, out = 0, []
    while i < len(b):
        key, i = _varint(b, i)
        field, wire = key >> 3, key & 7
        if wire == 0:
            value, i = _varint(b, i)
        elif wire == 2:
            n, i = _varint(b, i)
            value, i = b[i:i + n], i + n
        else:
            raise ValueError(f'unsupported wire type {wire}')
        out.append((field, wire, value))
    return out


def _enc_varint(v):
    out = bytearray()
    while True:
        byte = v & 0x7F
        v >>= 7
        out.append(byte | (0x80 if v else 0))
        if not v:
            return bytes(out)


def _enc_field(field, wire, value):
    head = _enc_varint((field << 3) | wire)
    if wire == 0:
        return head + _enc_varint(value)
    return head + _enc_varint(len(value)) + value


def rewrite(state_b64):
    fields = _fields(base64.b64decode(state_b64))
    sections = [dict((f, v) for f, _, v in _fields(v)) for f, _, v in fields if f == 1]
    names = [s.get(5, b'').decode() for s in sections]
    columns = COLUMNS
    if 'preview' not in names:  # e.g. Missing/Hidden: title takes the preview's width too
        columns = [('title', COLUMNS[0][1] + COLUMNS[1][1])] + COLUMNS[2:]
    if not all(name in names for name, _ in columns):
        return None  # not a track table (e.g. the folder browser)

    wanted = {name: (order, width) for order, (name, width) in enumerate(columns)}
    rest = iter(range(len(columns), len(sections)))
    placed = []
    for sec in sorted(sections, key=lambda s: s.get(4, 0)):
        name = sec.get(5, b'').decode()
        if name in wanted:
            visual, size, hidden = wanted[name][0], wanted[name][1], 0
        else:
            visual, size, hidden = next(rest), sec.get(2, 0), 1
        placed.append((visual, hidden, size, sec.get(3, 0), name))
    # Mixxx restores by moving each section to its visual index in the order
    # stored, so store them in final visual order or later moves shift
    # earlier ones (BPM and Key came out swapped otherwise).
    new = b''
    for visual, hidden, size, logical, name in sorted(placed):
        body = (_enc_field(1, 0, hidden) + _enc_field(2, 0, size) + _enc_field(3, 0, logical)
                + _enc_field(4, 0, visual) + _enc_field(5, 2, name.encode()))
        new += _enc_field(1, 2, body)
    for f, wire, v in fields:
        if f != 1:
            new += _enc_field(f, wire, v)
    return base64.b64encode(new).decode()


def main():
    db_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DB
    if any((p.info['name'] or '').lower() in ('mixxx.exe', 'mixxx') for p in psutil.process_iter(['name'])):
        sys.exit('Close Mixxx first - it would overwrite the layout on exit.')

    backup = f'{db_path}.{time.strftime("%Y%m%d-%H%M%S")}.bak'
    shutil.copy2(db_path, backup)
    print('backup:', backup)

    db = sqlite3.connect(db_path)
    rows = db.execute("select name, value from settings where name like '%header_state_pb'").fetchall()
    for name, value in rows:
        new = rewrite(value)
        if new is None:
            print('skipped (not a track table):', name)
            continue
        db.execute('update settings set value = ? where name = ?', (new, name))
        print('set:', name)
    db.commit()


if __name__ == '__main__':
    main()
