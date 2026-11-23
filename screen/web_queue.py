"""Pushy: a phone page to search the drive's library and add songs to Auto DJ (Pi).

Runs inside the screen app (mixxx-midi-bridge.py) on port 8080:
http://pushy.local:8080 (the Pi, renamed pushy on 2026-11-21, answers to pushy.local).
Meant for the DJ's own phone on the same network: no login. (Ejecting the
drive stays on the Push: SHIFT + hold SETUP.)

Search reads the drive's Mixxx library read-only, in all songs or inside one
playlist (the picker; with an empty search it lists the playlist's songs).
On a computer (wide window, mouse) search and queue sit side by side and each
queue row has a remove (×) button. Swiping a queue row to the left removes that song from the queue (the row in
the database; Mixxx re-reads the queue when Auto DJ takes the next song).
Titles use the Push screen's display font (TAN-SPRING, served from the Pi). Adding appends the song to
the Auto DJ queue (the hidden "Auto DJ" playlist) in the database, after
Mixxx's own last entry; the Push's Auto DJ page reads the queue from there,
and Mixxx picks the new rows up the next time it re-reads the queue (when
Auto DJ takes a song, or on its Auto DJ view).
"""

import json
import os
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

PORT = 8080
MAX_RESULTS = 60
MAX_PLAYLIST = 400
TITLE_FONT = os.path.expanduser('~/.local/share/fonts/TAN-SPRING.otf')
# icons + manifest (screen/web, made by screen/web/make_icons.py)
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web')
STATIC_TYPES = {'.png': 'image/png', '.svg': 'image/svg+xml', '.ico': 'image/x-icon',
                '.webmanifest': 'application/manifest+json'}

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0b0b0b">
<meta name="apple-mobile-web-app-capable" content="yes">
<title>Pushy</title>
<link rel="icon" href="/favicon.ico" sizes="48x48">
<link rel="icon" href="/static/icon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/static/apple-touch-icon.png">
<link rel="manifest" href="/static/manifest.webmanifest">
<style>
@font-face { font-family: 'Tan Spring'; src: url('/font/tan-spring.otf') format('opentype'); font-display: swap; }
:root { --ink:#0b0b0b; --panel:#151514; --edge:#2a2a28; --line:#e8e8e2; --dim:#8a8a84; --lime:#c8f53c; }
* { box-sizing: border-box; }
body { margin:0; background:var(--ink); color:var(--line); font:16px/1.35 -apple-system, system-ui, sans-serif; }
header { position:sticky; top:0; background:var(--ink); padding:12px 16px 10px; border-bottom:1px solid var(--edge); z-index:1; }
h1 { font:28px/1 'Tan Spring', system-ui, sans-serif; color:var(--lime); margin:2px 0 10px; }
.bar { display:flex; gap:8px; margin-top:8px; }
select { flex:1; min-width:0; padding:10px 12px; border-radius:10px; border:1px solid var(--edge); background:var(--panel); color:var(--line); font-size:15px; }
input { width:100%; padding:12px 14px; border-radius:10px; border:1px solid var(--edge); background:var(--panel); color:var(--line); font-size:17px; }
input:focus { outline:2px solid var(--lime); border-color:transparent; }
section { padding:6px 16px 24px; }
h2 { font:18px/1.1 'Tan Spring', system-ui, sans-serif; color:var(--line); margin:18px 0 6px; }
.row { display:flex; align-items:center; gap:10px; padding:10px 0; border-bottom:1px solid var(--edge); }
.t { flex:1; min-width:0; }
.t b { display:block; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.t span { display:block; color:var(--dim); font-size:13px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.m { color:var(--dim); font-size:12px; text-align:right; white-space:nowrap; }
button { min-width:44px; height:44px; border-radius:22px; border:1px solid var(--lime); background:transparent; color:var(--lime); font-size:22px; }
button.done { background:var(--lime); color:var(--ink); font-size:16px; }
.n { color:var(--dim); width:22px; font-size:12px; }
#msg { color:var(--dim); font-size:13px; padding:8px 0; }
.sw { position:relative; overflow:hidden; border-bottom:1px solid var(--edge); }
.sw .bg { position:absolute; inset:0; background:#ff5a4a; color:var(--ink); font-weight:700; font-size:13px;
          letter-spacing:.06em; display:flex; align-items:center; justify-content:flex-end; padding-right:18px; }
.sw .row { position:relative; background:var(--ink); border-bottom:0; touch-action:pan-y; transition:transform .2s; }
.sw.dragging .row { transition:none; }
.sw.gone { transition:height .2s, opacity .2s; opacity:0; }
.hint { color:var(--dim); font-size:12px; margin:-2px 0 6px; }
.rm { display:none; min-width:36px; height:36px; border-color:var(--edge); color:var(--dim); font-size:20px; }
.rm:hover { border-color:#ff5a4a; color:#ff5a4a; }
.hint .mouse { display:none; }
/* computer: mouse -> remove buttons instead of swiping */
@media (hover: hover) and (pointer: fine) {
  .rm { display:inline-block; }
  .hint .touch { display:none; }
  .hint .mouse { display:inline; }
  button { cursor:pointer; }
}
/* wide window: search on the left, queue on the right */
@media (min-width: 900px) {
  header { padding:16px 32px 12px; }
  header > * { max-width:1180px; margin-left:auto; margin-right:auto; }
  header .bar, header input { max-width:1180px; }
  h1 { font-size:34px; }
  section { display:grid; grid-template-columns:minmax(0, 1fr) minmax(0, 1fr); gap:40px;
            max-width:1180px; margin:0 auto; padding:8px 32px 40px; }
  #right { position:sticky; top:150px; align-self:start; max-height:calc(100vh - 170px); overflow-y:auto; }
  #right h2 { margin-top:12px; }
}
</style></head><body>
<header><h1>Pushy</h1>
<input id="q" type="search" placeholder="Search title, artist, album" autocomplete="off" autocapitalize="off">
<div class="bar"><select id="pl"><option value="">All songs</option></select></div></header>
<section><div id="left"><h2 id="rh" hidden></h2><div id="msg"></div><div id="results"></div></div>
<div id="right"><h2 id="qh">Queue</h2><div class="hint"><span class="touch">swipe a song left to remove it</span><span class="mouse">× removes a song</span></div>
<div id="queue"></div></div></section>
<script>
const $ = s => document.querySelector(s);
const esc = s => (s || '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const dur = s => { s = Math.round(s || 0); return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0'); };
const meta = t => [t.bpm ? t.bpm.toFixed(0) : '', t.key || '', dur(t.duration)].filter(Boolean).join(' · ');
let timer = 0;
async function search() {
  const q = $('#q').value.trim(), pl = $('#pl').value;
  $('#rh').hidden = !pl; $('#rh').textContent = pl ? $('#pl').selectedOptions[0].dataset.name : '';
  if (q.length < 2 && !pl) { $('#results').innerHTML = ''; $('#msg').textContent = ''; return; }
  const r = await (await fetch('/api/search?q=' + encodeURIComponent(q) + '&playlist=' + pl)).json();
  $('#msg').textContent = r.length ? '' : 'Nothing found';
  $('#results').innerHTML = r.map(t => `<div class="row"><div class="t"><b>${esc(t.title)}</b><span>${esc(t.artist)}${t.album ? ' — ' + esc(t.album) : ''}</span></div>
    <div class="m">${meta(t)}</div><button data-id="${t.id}">+</button></div>`).join('');
}
async function queue() {
  const r = await (await fetch('/api/queue')).json();
  $('#qh').textContent = 'Queue · ' + r.length + ' song' + (r.length === 1 ? '' : 's');
  if (drag) return;   // don't redraw under a finger
  $('#queue').innerHTML = r.map((t, i) => `<div class="sw" data-pt="${t.pt}"><div class="bg">REMOVE</div>
    <div class="row"><div class="n">${i + 1}</div><div class="t"><b>${esc(t.title)}</b><span>${esc(t.artist)}</span></div>
    <div class="m">${meta(t)}</div><button class="rm" title="Remove from the queue">×</button></div></div>`).join('');
}
// computer: the × button
$('#queue').addEventListener('click', e => {
  const b = e.target.closest('.rm'); if (!b) return;
  removeRow(b.closest('.sw'), b.closest('.row'));
});
async function removeRow(sw, row) {
  if (sw === $('#queue .sw')) {   // the next song: Mixxx has it lined up already
    row.style.transform = '';
    $('#msg').textContent = "The next song can't be removed here: use SKIP NEXT on the Push";
    return;
  }
  row.style.transform = 'translateX(-100%)';
  sw.style.height = sw.offsetHeight + 'px';
  const r = await (await fetch('/api/remove', {method: 'POST', body: 'pt=' + sw.dataset.pt})).json();
  if (r.ok) { sw.classList.add('gone'); sw.style.height = '0px'; setTimeout(queue, 250); }
  else { row.style.transform = ''; $('#msg').textContent = r.error || 'Could not remove'; }
}
// swipe left past a third of the width = remove
let drag = null;
$('#queue').addEventListener('touchstart', e => {
  const sw = e.target.closest('.sw'); if (!sw) return;
  drag = {sw, row: sw.querySelector('.row'), x: e.touches[0].clientX, y: e.touches[0].clientY, dx: 0, lock: null};
}, {passive: true});
$('#queue').addEventListener('touchmove', e => {
  if (!drag) return;
  const dx = e.touches[0].clientX - drag.x, dy = e.touches[0].clientY - drag.y;
  if (drag.lock === null && (Math.abs(dx) > 8 || Math.abs(dy) > 8)) drag.lock = Math.abs(dx) > Math.abs(dy) ? 'x' : 'y';
  if (drag.lock !== 'x') return;
  drag.dx = Math.min(0, dx);
  drag.sw.classList.add('dragging');
  drag.row.style.transform = `translateX(${drag.dx}px)`;
}, {passive: true});
$('#queue').addEventListener('touchend', async () => {
  if (!drag) return;
  const d = drag; drag = null;
  d.sw.classList.remove('dragging');
  if (d.lock === 'x' && -d.dx > d.sw.offsetWidth / 3) {
    removeRow(d.sw, d.row);
  } else {
    d.row.style.transform = '';
  }
});
$('#q').addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(search, 250); });
$('#pl').addEventListener('change', search);
fetch('/api/playlists').then(r => r.json()).then(r => {
  $('#pl').insertAdjacentHTML('beforeend', r.map(p =>
    `<option value="${p.id}" data-name="${esc(p.name)}">${esc(p.name)} (${p.count})</option>`).join(''));
});
$('#results').addEventListener('click', async e => {
  const b = e.target.closest('button'); if (!b || b.disabled) return;
  b.disabled = true;
  const r = await (await fetch('/api/add', {method: 'POST', body: 'id=' + b.dataset.id})).json();
  if (r.ok) { b.textContent = '#' + r.position; b.classList.add('done'); queue(); }
  else { b.disabled = false; $('#msg').textContent = r.error || 'Could not add'; }
});
queue(); setInterval(queue, 5000);
</script></body></html>
"""


class WebQueue:
    def __init__(self, music_drive, on_added=None):
        self.db_path = os.path.join(music_drive, '.mixxx', 'mixxxdb.sqlite') if music_drive else None
        self.drive = music_drive
        self.on_added = on_added
        self._lock = threading.Lock()

    def start(self):
        if not self.db_path:
            return
        handler = self._handler()
        try:
            server = ThreadingHTTPServer(('', PORT), handler)
        except OSError as e:
            print(f'[web] port {PORT} unavailable: {e}', flush=True)
            return
        threading.Thread(target=server.serve_forever, daemon=True, name='web-queue').start()
        print(f'[web] Pushy page on http://pushy.local:{PORT}', flush=True)

    # ── library ──
    def _db(self, write=False):
        uri = f'file:{self.db_path}' + ('' if write else '?mode=ro')
        return sqlite3.connect(uri, uri=True, timeout=5)

    def search(self, q):
        like = f'%{q}%'
        db = self._db()
        try:
            rows = db.execute(
                'select l.id, l.title, l.artist, l.album, l.bpm, l.key, l.duration from library l '
                'join track_locations tl on tl.id = l.location '
                'where l.mixxx_deleted = 0 and coalesce(tl.fs_deleted, 0) = 0 and tl.location like ? '
                'and (l.title like ? or l.artist like ? or l.album like ?) '
                'order by l.artist, l.album, l.tracknumber, l.title limit ?',
                (self.drive + '/%', like, like, like, MAX_RESULTS)).fetchall()
        finally:
            db.close()
        return [dict(zip(('id', 'title', 'artist', 'album', 'bpm', 'key', 'duration'), r)) for r in rows]

    def playlists(self):
        db = self._db()
        try:
            rows = db.execute(
                'select p.id, p.name, count(pt.id) from Playlists p '
                'left join PlaylistTracks pt on pt.playlist_id = p.id '
                'where p.hidden = 0 group by p.id order by p.name collate nocase').fetchall()
        finally:
            db.close()
        return [{'id': i, 'name': n, 'count': c} for i, n, c in rows]

    def playlist_search(self, playlist_id, q):
        """A playlist's songs in its order, filtered by q (all of them with q empty)."""
        like = f'%{q}%'
        db = self._db()
        try:
            rows = db.execute(
                'select l.id, l.title, l.artist, l.album, l.bpm, l.key, l.duration from PlaylistTracks pt '
                'join library l on l.id = pt.track_id and l.mixxx_deleted = 0 '
                'where pt.playlist_id = ? and (l.title like ? or l.artist like ? or l.album like ?) '
                'order by pt.position limit ?',
                (playlist_id, like, like, like, MAX_PLAYLIST)).fetchall()
        finally:
            db.close()
        return [dict(zip(('id', 'title', 'artist', 'album', 'bpm', 'key', 'duration'), r)) for r in rows]

    def queue(self):
        db = self._db()
        try:
            rows = db.execute(
                'select l.id, l.title, l.artist, l.album, l.bpm, l.key, l.duration, pt.id from PlaylistTracks pt '
                'join Playlists p on p.id = pt.playlist_id and p.hidden = 1 '
                'join library l on l.id = pt.track_id and l.mixxx_deleted = 0 '
                'order by pt.position').fetchall()
        finally:
            db.close()
        return [dict(zip(('id', 'title', 'artist', 'album', 'bpm', 'key', 'duration', 'pt'), r)) for r in rows]

    def remove(self, pt_id):
        """Take one row off the Auto DJ queue and close the gap in the positions."""
        with self._lock:
            db = self._db(write=True)
            try:
                row = db.execute('select pt.playlist_id, pt.position from PlaylistTracks pt '
                                 'join Playlists p on p.id = pt.playlist_id and p.hidden = 1 '
                                 'where pt.id = ?', (pt_id,)).fetchone()
                if not row:
                    return {'ok': False, 'error': 'Already gone from the queue'}
                if row[1] <= 1:
                    # Mixxx loads the next song from its own copy of the queue and then
                    # drops position 1: removing #1 here would lose the song after it
                    return {'ok': False, 'error': "The next song can't be removed here: use SKIP NEXT on the Push"}
                db.execute('delete from PlaylistTracks where id = ?', (pt_id,))
                db.execute('update PlaylistTracks set position = position - 1 '
                           'where playlist_id = ? and position > ?', row)
                db.commit()
            finally:
                db.close()
        print(f'[web] removed queue row {pt_id} (was #{row[1]})', flush=True)
        if self.on_added:
            self.on_added(removed=True)
        return {'ok': True}

    def add(self, track_id):
        with self._lock:
            db = self._db(write=True)
            try:
                ok = db.execute('select 1 from library where id = ? and mixxx_deleted = 0', (track_id,)).fetchone()
                if not ok:
                    return {'ok': False, 'error': 'Song not in the library'}
                pl = db.execute('select id from Playlists where hidden = 1 order by id limit 1').fetchone()
                if not pl:
                    return {'ok': False, 'error': 'No Auto DJ queue in this library'}
                pos = (db.execute('select max(position) from PlaylistTracks where playlist_id = ?',
                                  (pl[0],)).fetchone()[0] or 0) + 1
                # Mixxx stores the time added in UTC
                now = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())
                db.execute('insert into PlaylistTracks (playlist_id, track_id, position, pl_datetime_added) '
                           'values (?, ?, ?, ?)', (pl[0], track_id, pos, now))
                db.commit()
            finally:
                db.close()
        print(f'[web] added track {track_id} to Auto DJ (#{pos})', flush=True)
        if self.on_added:
            self.on_added()
        return {'ok': True, 'position': pos}

    # ── HTTP ──
    def _handler(self):
        app = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, body, ctype='application/json'):
                data = body.encode('utf-8') if isinstance(body, str) else body
                self.send_response(code)
                self.send_header('Content-Type', ctype + '; charset=utf-8')
                self.send_header('Content-Length', str(len(data)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                u = urlparse(self.path)
                try:
                    if u.path == '/':
                        self._send(200, PAGE, 'text/html')
                    elif u.path == '/api/search':
                        args = parse_qs(u.query)
                        q = (args.get('q') or [''])[0].strip()
                        pl = (args.get('playlist') or [''])[0]
                        if pl.isdigit():
                            self._send(200, json.dumps(app.playlist_search(int(pl), q)))
                        else:
                            self._send(200, json.dumps(app.search(q) if len(q) >= 2 else []))
                    elif u.path == '/api/playlists':
                        self._send(200, json.dumps(app.playlists()))
                    elif u.path == '/favicon.ico' or u.path.startswith('/static/'):
                        name = 'favicon.ico' if u.path == '/favicon.ico' else os.path.basename(u.path)
                        path = os.path.join(WEB_DIR, name)
                        ext = os.path.splitext(name)[1]
                        if ext not in STATIC_TYPES or not os.path.isfile(path):
                            self._send(404, '{}')
                            return
                        with open(path, 'rb') as f:
                            data = f.read()
                        self.send_response(200)
                        self.send_header('Content-Type', STATIC_TYPES[ext])
                        self.send_header('Content-Length', str(len(data)))
                        self.send_header('Cache-Control', 'max-age=86400')
                        self.end_headers()
                        self.wfile.write(data)
                    elif u.path == '/font/tan-spring.otf':
                        try:
                            with open(TITLE_FONT, 'rb') as f:
                                data = f.read()
                        except OSError:
                            self._send(404, '{}')
                            return
                        self.send_response(200)
                        self.send_header('Content-Type', 'font/otf')
                        self.send_header('Content-Length', str(len(data)))
                        self.send_header('Cache-Control', 'max-age=86400')
                        self.end_headers()
                        self.wfile.write(data)
                    elif u.path == '/api/queue':
                        self._send(200, json.dumps(app.queue()))
                    else:
                        self._send(404, '{}')
                except sqlite3.Error as e:
                    self._send(503, json.dumps({'error': str(e)}))

            def do_POST(self):
                if urlparse(self.path).path == '/api/remove':
                    n = int(self.headers.get('Content-Length') or 0)
                    form = parse_qs(self.rfile.read(n).decode('utf-8', 'replace'))
                    try:
                        self._send(200, json.dumps(app.remove(int((form.get('pt') or ['0'])[0]))))
                    except (ValueError, sqlite3.Error) as e:
                        self._send(200, json.dumps({'ok': False, 'error': str(e)}))
                    return
                if urlparse(self.path).path != '/api/add':
                    self._send(404, '{}')
                    return
                n = int(self.headers.get('Content-Length') or 0)
                form = parse_qs(self.rfile.read(n).decode('utf-8', 'replace'))
                try:
                    track_id = int((form.get('id') or ['0'])[0])
                    self._send(200, json.dumps(app.add(track_id)))
                except (ValueError, sqlite3.Error) as e:
                    self._send(200, json.dumps({'ok': False, 'error': str(e)}))

        return Handler
