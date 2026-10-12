"""Mirrors <drive>/Playlists/*.m3u8 / *.m3u into the drive's Mixxx library (Pi).

Run by mixxx-prestart before Mixxx opens the database. Each playlist file
becomes a Mixxx playlist of the same name, in the file's order, locked (edits
in Mixxx would be overwritten on the next start). Playlists this script made
whose file is gone are deleted; the names it manages are kept in
<drive>/.mixxx/managed-playlists.txt so playlists made in Mixxx are left alone.

Songs that are on the drive but not in the library yet (new drive / newly
exported songs) can't be added before Mixxx's startup scan; they're listed in
~/.cache/mixxx-playlists-pending and usb/playlist-watch.sh restarts Mixxx once
after the scan so this script runs again and adds them.
"""
import glob
import os
import sqlite3
import sys
import time
from urllib.parse import unquote, urlparse

DRIVE = '/home/admin/Music/usb'
DB = os.path.join(DRIVE, '.mixxx', 'mixxxdb.sqlite')
MANAGED = os.path.join(DRIVE, '.mixxx', 'managed-playlists.txt')
PENDING = os.path.expanduser('~/.cache/mixxx-playlists-pending')
PENDING_DONE = PENDING + '.done'  # missing songs already given their one restart
NAME_MAX = 48  # Playlists.name is varchar(48)


def read_lines(path):
    with open(path, 'rb') as f:
        raw = f.read()
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = raw.decode('latin-1')
    return text.splitlines()


def entries(path):
    base = os.path.dirname(path)
    for line in read_lines(path):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('file://'):
            line = unquote(urlparse(line).path)
        line = line.replace('\\', '/')
        yield os.path.normpath(line if os.path.isabs(line) else os.path.join(base, line))


def read_set(path):
    try:
        with open(path, encoding='utf-8') as f:
            return {l.rstrip('\n') for l in f if l.strip()}
    except OSError:
        return set()


def write_set(path, items):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(''.join(i + '\n' for i in sorted(items)))


def main():
    files = sorted(glob.glob(os.path.join(DRIVE, 'Playlists', '*.m3u8'))
                   + glob.glob(os.path.join(DRIVE, 'Playlists', '*.m3u')))
    managed_before = read_set(MANAGED)
    if not files and not managed_before:
        return
    now = time.strftime('%Y-%m-%d %H:%M:%S')
    db = sqlite3.connect(DB, timeout=10)
    track_id = dict(db.execute(
        'select tl.location, l.id from library l join track_locations tl on tl.id = l.location '
        'where l.mixxx_deleted = 0 and coalesce(tl.fs_deleted, 0) = 0'))
    existing = dict(db.execute('select name, id from Playlists where hidden = 0'))
    next_pos = (db.execute('select max(position) from Playlists').fetchone()[0] or 0) + 1

    managed, waiting, absent = set(), set(), 0
    for path in files:
        name = os.path.splitext(os.path.basename(path))[0][:NAME_MAX]
        if name in managed:
            continue  # a .m3u and .m3u8 of the same name: first one wins
        ids = []
        for song in entries(path):
            if song in track_id:
                ids.append(track_id[song])
            elif os.path.isfile(song):
                waiting.add(song)
            else:
                absent += 1
        pid = existing.get(name)
        if pid is None:
            pid = db.execute('insert into Playlists (name, position, hidden, date_created, date_modified, locked) '
                             'values (?, ?, 0, ?, ?, 1)', (name, next_pos, now, now)).lastrowid
            next_pos += 1
        else:
            db.execute('update Playlists set locked = 1, date_modified = ? where id = ?', (now, pid))
        db.execute('delete from PlaylistTracks where playlist_id = ?', (pid,))
        db.executemany('insert into PlaylistTracks (playlist_id, track_id, position, pl_datetime_added) '
                       'values (?, ?, ?, ?)', [(pid, t, i + 1, now) for i, t in enumerate(ids)])
        managed.add(name)
        print(f'playlist {name}: {len(ids)} songs')

    for name in managed_before - managed:
        pid = existing.get(name)
        if pid is not None:
            db.execute('delete from PlaylistTracks where playlist_id = ?', (pid,))
            db.execute('delete from Playlists where id = ?', (pid,))
            print(f'playlist {name}: removed (file gone)')
    db.commit()
    db.close()
    write_set(MANAGED, managed)

    # One restart per batch of new songs; songs Mixxx still can't import
    # (unsupported files) don't trigger restart loops.
    new = waiting - read_set(PENDING_DONE)
    if new:
        write_set(PENDING, waiting)
    elif os.path.exists(PENDING):
        os.remove(PENDING)
    if waiting:
        print(f'{len(waiting)} songs not in the library yet - added after the scan')
    if absent:
        print(f'{absent} playlist entries point at files that are not on the drive', file=sys.stderr)


if __name__ == '__main__':
    main()
