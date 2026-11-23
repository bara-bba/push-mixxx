"""Mixxx's library sidebar tree, read through AT-SPI (Linux accessibility).

While Mixxx's own tree is open (Computer, History...) the screen app paints
it in the nav's style (playlist_page.draw_tree). The rows - name, depth,
open/openable, selected - come from Mixxx itself over the accessibility bus,
so they always match what Mixxx has, including rows scrolled out of its
5-row view.

Needs, on the Pi: Mixxx started with QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1 and
the user session bus (mixxx.service.d/accessibility.conf, linger for admin),
and jeepney in the screen app's venv. Without them rows() returns None and
the screen shows Mixxx's own tree as before.
"""

import os
import threading
import time

from jeepney import DBusAddress, Properties, new_method_call
from jeepney.io.blocking import open_dbus_connection

ACC = 'org.a11y.atspi.Accessible'
ROOT = '/org/a11y/atspi/accessible/root'
REGISTRY = DBusAddress(ROOT, bus_name='org.a11y.atspi.Registry', interface=ACC)
STATE_EXPANDABLE, STATE_EXPANDED, STATE_SELECTED = 9, 10, 23
SKIP_ROLES = {'table', 'tree table', 'list', 'menu bar', 'popup menu', 'combo box'}
TIMEOUT = 2.0
RETRY_SECONDS = 5.0
POLL_SECONDS = 0.15


class Row:
    __slots__ = ('name', 'depth', 'expandable', 'expanded', 'selected')

    def __init__(self, name, depth, expandable, expanded, selected):
        self.name, self.depth = name, depth
        self.expandable, self.expanded, self.selected = expandable, expanded, selected

    def __repr__(self):
        return f'Row({self.name!r}, d{self.depth}{" +" if self.expandable else ""}{" open" if self.expanded else ""}{" SEL" if self.selected else ""})'


class Atspi:
    """A connection to the accessibility bus (one per thread: jeepney's
    blocking connection isn't shared)."""

    def __init__(self):
        self._conn = None

    def _call(self, dest, path, method, sig=None, body=(), iface=ACC):
        msg = new_method_call(DBusAddress(path, bus_name=dest, interface=iface), method, sig, body)
        return self._conn.send_and_get_reply(msg, timeout=TIMEOUT).body

    def _prop(self, dest, path, name):
        msg = Properties(DBusAddress(path, bus_name=dest, interface=ACC)).get(name)
        return self._conn.send_and_get_reply(msg, timeout=TIMEOUT).body[0][1]

    def _connect(self):
        # push2-screen.service has no session-bus variable: the user's bus (linger)
        session = os.environ.get('DBUS_SESSION_BUS_ADDRESS') or f'unix:path=/run/user/{os.getuid()}/bus'
        with open_dbus_connection(bus=session) as sess:
            msg = new_method_call(DBusAddress('/org/a11y/bus', bus_name='org.a11y.Bus',
                                              interface='org.a11y.Bus'), 'GetAddress')
            addr = sess.send_and_get_reply(msg, timeout=TIMEOUT).body[0]
        self._conn = open_dbus_connection(bus=addr)

    def _close(self):
        try:
            if self._conn is not None:
                self._conn.close()
        except Exception:
            pass
        self._conn = None

    def _mixxx_app(self):
        """(bus name, path) of Mixxx's application root, or None."""
        apps = self._conn.send_and_get_reply(new_method_call(REGISTRY, 'GetChildren'), timeout=TIMEOUT).body[0]
        for dest, path in apps:
            if self._prop(dest, path, 'Name') == 'Mixxx':
                return dest, path
        return None

    def _states(self, dest, path):
        lo, hi = self._call(dest, path, 'GetState')[0]
        return lo | (hi << 32)

    def _extents(self, dest, path):
        """(x, y, w, h) on the screen."""
        return tuple(self._call(dest, path, 'GetExtents', 'u', (0,), iface='org.a11y.atspi.Component')[0])


_button_cache = {}


def press_mixxx_button(description):
    """Press the Mixxx button whose tooltip starts with description (e.g. the
    Auto DJ view's Shuffle, which has no controller control). True if found.
    One-off connection; the path is cached for next time."""
    a = Atspi()
    try:
        a._connect()
        path = _button_cache.get(description)
        if path:
            try:
                if (a._prop(*path, 'Description') or '').startswith(description):
                    a._call(*path, 'DoAction', 'i', (_press_index(a, path),), iface='org.a11y.atspi.Action')
                    return True
            except Exception:
                pass
        app = a._mixxx_app()
        stack = [app] if app else []
        while stack:
            d, p = stack.pop(0)
            role = a._call(d, p, 'GetRoleName')[0]
            if role in ('table', 'tree', 'tree table', 'list', 'menu bar'):
                continue
            if role in ('push button', 'check box', 'toggle button'):
                if (a._prop(d, p, 'Description') or '').startswith(description):
                    _button_cache[description] = (d, p)
                    a._call(d, p, 'DoAction', 'i', (_press_index(a, (d, p)),), iface='org.a11y.atspi.Action')
                    return True
                continue
            stack.extend(a._call(d, p, 'GetChildren')[0])
        return False
    finally:
        a._close()


def _press_index(a, path):
    acts = [x[0] for x in a._call(*path, 'GetActions', iface='org.a11y.atspi.Action')[0]]
    return acts.index('Press') if 'Press' in acts else 0


class MixxxTree(Atspi):
    """Polls the sidebar while wanted (active = True) in a background thread;
    rows() gives the latest list, or None when it can't be read."""

    def __init__(self):
        super().__init__()
        self.active = False
        self._rows = None
        self._tree = None         # (bus name, object path) of the sidebar tree
        self._failed_at = 0.0
        self._lock = threading.Lock()
        threading.Thread(target=self._run, daemon=True, name='mixxx-tree').start()

    def rows(self):
        with self._lock:
            return self._rows

    def _find_tree(self):
        """The sidebar: a 'tree' whose first item is Tracks, in the Mixxx app."""
        app = self._mixxx_app()
        for dest, path in [app] if app else []:
            stack = [(dest, path)]
            while stack:
                d, p = stack.pop()
                role = self._call(d, p, 'GetRoleName')[0]
                if role in SKIP_ROLES:
                    continue
                kids = self._call(d, p, 'GetChildren')[0]
                if role == 'tree':
                    names = [self._prop(kd, kp, 'Name') for kd, kp in kids[:3]]
                    if 'Tracks' in names:
                        return (d, p)
                    continue
                stack.extend(kids)
        return None

    def _read(self):
        d, p = self._tree
        rows, xs = [], []
        for kd, kp in self._call(d, p, 'GetChildren')[0]:
            if self._call(kd, kp, 'GetRoleName')[0] != 'tree item':
                continue
            bits = self._states(kd, kp)
            x, _, w, h = self._extents(kd, kp)
            if w <= 0 or h <= 0:
                # no place in the view = a row Qt's accessibility cache kept
                # from before a collapse (seen after closing a playlist): the
                # whole list can't be trusted until Qt refreshes it
                return None
            xs.append(x)
            rows.append(Row(self._prop(kd, kp, 'Name'), x,
                            bool(bits >> STATE_EXPANDABLE & 1), bool(bits >> STATE_EXPANDED & 1),
                            bool(bits >> STATE_SELECTED & 1)))
        if not rows:
            raise LookupError('empty tree')
        # depth from the indent: top-level rows sit furthest left, 20px per level
        base = min(xs)
        steps = sorted({x - base for x in xs if x > base})
        step = steps[0] if steps else 20
        for r in rows:
            r.depth = 1 + round((r.depth - base) / step)
        return rows

    def _run(self):
        while True:
            if not self.active:
                time.sleep(POLL_SECONDS)
                continue
            if self._failed_at and time.monotonic() - self._failed_at < RETRY_SECONDS:
                time.sleep(POLL_SECONDS)
                continue
            try:
                if self._conn is None:
                    self._connect()
                if self._tree is None:
                    self._tree = self._find_tree()
                    if self._tree is None:
                        raise LookupError('Mixxx sidebar not on the accessibility bus')
                    print(f'[tree] Mixxx sidebar found: {self._tree[1]}', flush=True)
                rows = self._read()   # None = stale, see _read
                with self._lock:
                    self._rows = rows
                self._failed_at = 0.0
            except Exception as e:   # Mixxx restarted, bus gone...: start over
                if not self._failed_at:
                    print(f'[tree] not readable: {e!r}', flush=True)
                with self._lock:
                    self._rows = None
                self._tree = None
                self._close()
                self._failed_at = time.monotonic()
            time.sleep(POLL_SECONDS)


if __name__ == '__main__':   # on the Pi: print the tree once
    t = MixxxTree()
    t.active = True
    for _ in range(100):
        time.sleep(0.2)
        if t.rows():
            break
    t0 = time.monotonic()
    rows = t._read() if t._tree else None
    print(f'read in {time.monotonic() - t0:.3f}s')
    for r in rows or []:
        print('  ' * r.depth, r)
