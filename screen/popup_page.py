"""Mixxx popups (message boxes, questions, file pickers) on the Push screen.

Mixxx sometimes opens a window of its own - "One deck must be stopped to
enable Auto DJ mode", a question with Yes/No... On the Pi it lands on the
Xvfb display behind the Push image, unreadable. MixxxPopups watches Mixxx's
windows over the accessibility bus (mixxx_tree.Atspi) and reads the popup's
title, text and buttons; draw() paints it as a box over the Push image and
the arrows answer it (mixxx-midi-bridge.py routes them here, and tells the
Push script to leave them alone meanwhile):

  ◄ ►  choose a button     ▲  press it     ▼  Cancel / No (else Esc)
  DELETE  Esc (closes it as Escape would)
"""

import re
import subprocess
import threading
import time

from PIL import ImageDraw

from mixxx_capture import _x11_focus_main
from mixxx_tree import Atspi
from pi_stats import BODY_BOLD_FONTS, BODY_FONTS, DIM, EDGE, FAINT, INK, LIME, LINE, _font

POLL_SECONDS = 0.25
RETRY_SECONDS = 5.0
STATE_ACTIVE, STATE_FOCUSED, STATE_SHOWING, STATE_DEFAULT = 1, 12, 25, 39
REFOCUS_AFTER = 2          # polls with Mixxx's window inactive (and no popup) before refocusing
REFOCUS_EVERY_SECONDS = 3.0
TEXT_ROLES = {'label', 'text', 'static', 'paragraph', 'heading'}
BUTTON_ROLES = {'push button'}
CANCEL_NAMES = ('cancel', 'no', 'close', 'abort', 'discard', "don't save")
MAX_NODES = 200            # a file picker has a lot inside; enough to find its buttons
BOX = (40, 2, 920, 157)    # x0, y0, x1, y1 on the 960x160 Push screen


def _clean(name):
    return name.replace('&', '').strip()


def _refocus_after_close(timeout=1.5):
    """Once the popup's window is gone, give Mixxx's main window the focus
    again: Qt otherwise has no active window and drops the library keys the
    Push sends ("No Mixxx window, popup or menu has focus")."""
    from mixxx_capture import _is_main_title, _x11_windows
    end = time.monotonic() + timeout
    while time.monotonic() < end and any(not _is_main_title(n) for _, n in _x11_windows()):
        time.sleep(0.05)
    # X focus alone isn't enough after a modal box: Qt has no active window
    # until it sees the focus leave and come back
    info = subprocess.run(['xwininfo', '-root'], capture_output=True, text=True, timeout=2).stdout
    root = re.search(r'Window id: (0x[0-9a-f]+)', info)
    if root:
        subprocess.run(['xdotool', 'windowfocus', root.group(1)], capture_output=True, timeout=2)
        time.sleep(0.1)
    _x11_focus_main()


class Popup:
    def __init__(self, path, title, texts, buttons, selected):
        self.path, self.title, self.texts = path, title, texts
        self.buttons = buttons          # [(name, (dest, path), (x, y, w, h))]
        self.selected = selected


class MixxxPopups(Atspi):
    """Background watcher; current() = the open Popup or None."""

    def __init__(self):
        super().__init__()
        self._popup = None
        self._failed_at = 0.0
        self._inactive = 0
        self._refocused_at = 0.0
        self._lock = threading.Lock()
        threading.Thread(target=self._run, daemon=True, name='mixxx-popups').start()

    def current(self):
        with self._lock:
            return self._popup

    # ── reading ──
    def _read(self, dest, path):
        title = _clean(self._prop(dest, path, 'Name') or '')
        texts, buttons, stack, seen = [], [], [(dest, path)], 0
        selected = None
        while stack and seen < MAX_NODES:
            d, p = stack.pop(0)
            seen += 1
            role = self._call(d, p, 'GetRoleName')[0]
            if role in BUTTON_ROLES:
                name = _clean(self._prop(d, p, 'Name') or '')
                if name:
                    bits = self._states(d, p)
                    if selected is None and (bits >> STATE_FOCUSED & 1 or bits >> STATE_DEFAULT & 1):
                        selected = len(buttons)
                    buttons.append((name, (d, p), self._extents(d, p)))
                continue
            if role in TEXT_ROLES and (d, p) != (dest, path):
                name = (self._prop(d, p, 'Name') or '').strip()
                if name and name != title:
                    texts.append(name)
            if role in ('table', 'tree table', 'list', 'tree'):
                continue   # file lists: their rows aren't needed
            stack.extend(self._call(d, p, 'GetChildren')[0])
        # dialog buttons only (a file picker's toolbar buttons have icon names
        # like "Back"): keep the ones on the dialog's bottom row
        if buttons:
            bottom = max(b[2][1] for b in buttons)
            buttons = [b for b in buttons if b[2][1] >= bottom - 8]
            buttons.sort(key=lambda b: b[2][0])
        if selected is None or selected >= len(buttons):
            selected = 0
        return Popup(path, title, texts, buttons, selected)

    def _run(self):
        while True:
            time.sleep(POLL_SECONDS)
            if self._failed_at and time.monotonic() - self._failed_at < RETRY_SECONDS:
                continue
            try:
                if self._conn is None:
                    self._connect()
                app = self._mixxx_app()
                popup = None
                main_active = True
                if app:
                    for d, p in self._call(*app, 'GetChildren')[0]:
                        role = self._call(d, p, 'GetRoleName')[0]
                        if role == 'frame' and (self._prop(d, p, 'Name') or '').endswith('Mixxx'):
                            main_active = bool(self._states(d, p) >> STATE_ACTIVE & 1)
                            continue   # the main window
                        if not self._states(d, p) >> STATE_SHOWING & 1:
                            continue   # a closed window Mixxx keeps (e.g. the startup Library Scanner)
                        old = self.current()
                        if old and old.path == p:
                            popup = old   # still open: keep the reading and the choice
                        else:
                            popup = self._read(d, p)
                            print(f'[popup] {popup.title!r}: {" / ".join(popup.texts)[:120]!r} '
                                  f'buttons {[b[0] for b in popup.buttons]}', flush=True)
                        break
                with self._lock:
                    if self._popup and not popup:
                        print('[popup] closed', flush=True)
                    self._popup = popup
                self._failed_at = 0.0
                # no popup but Mixxx's window isn't the active one: Qt then drops
                # the library keys the Push sends - give it the focus back
                self._inactive = 0 if (popup or main_active) else self._inactive + 1
                if self._inactive >= REFOCUS_AFTER and time.monotonic() - self._refocused_at >= REFOCUS_EVERY_SECONDS:
                    self._refocused_at = time.monotonic()
                    print('[popup] Mixxx window lost the focus, giving it back', flush=True)
                    _refocus_after_close(timeout=0)
            except Exception as e:
                if not self._failed_at:
                    print(f'[popup] not readable: {e!r}', flush=True)
                with self._lock:
                    self._popup = None
                self._close()
                self._failed_at = time.monotonic()

    # ── answering (called from the Push input thread) ──
    def move(self, delta):
        pop = self.current()
        if pop and pop.buttons:
            pop.selected = max(0, min(len(pop.buttons) - 1, pop.selected + delta))

    def press(self):
        pop = self.current()
        if not pop:
            return
        if not pop.buttons:
            self.escape()
            return
        self._click(pop.buttons[pop.selected])

    def cancel(self):
        pop = self.current()
        if not pop:
            return
        for b in pop.buttons:
            if b[0].lower() in CANCEL_NAMES:
                self._click(b)
                return
        self.escape()

    def escape(self):
        from mixxx_capture import close_mixxx_popups
        close_mixxx_popups()
        _refocus_after_close()
        self._forget()

    def _click(self, button):
        name, _, (x, y, w, h) = button
        print(f'[popup] pressing {name!r}', flush=True)
        xdo = lambda *a: subprocess.run(['xdotool', *a], capture_output=True, timeout=2)
        xdo('mousemove', str(x + w // 2), str(y + h // 2), 'click', '1')
        xdo('mousemove', '959', '0')
        _refocus_after_close()
        self._forget()

    def _forget(self):
        with self._lock:
            self._popup = None   # re-read on the next poll if it's still there


class PopupPage:
    def __init__(self):
        self._f_title = _font(BODY_BOLD_FONTS, 13)
        self._f = _font(BODY_FONTS, 13)
        self._f_btn = _font(BODY_BOLD_FONTS, 12)
        self._f_hint = _font(BODY_FONTS, 10)
        self._f_key = _font(BODY_BOLD_FONTS, 10)

    def _wrap(self, draw, text, width):
        lines = []
        for para in text.splitlines() or ['']:
            line = ''
            for word in para.split():
                test = f'{line} {word}'.strip()
                if draw.textlength(test, font=self._f) <= width:
                    line = test
                else:
                    if line:
                        lines.append(line)
                    line = word
            lines.append(line)
        return lines

    def draw(self, frame, pop):
        draw = ImageDraw.Draw(frame)
        x0, y0, x1, y1 = BOX
        draw.rectangle([x0 - 4, 0, x1 + 4, 159], fill=INK)   # also hides Mixxx's own box (y 0..)
        draw.rectangle([x0, y0, x1, y1], fill=INK, outline=LIME, width=2)
        draw.text((x0 + 14, y0 + 8), (pop.title or 'Mixxx').upper(), font=self._f_title, fill=LIME)
        # message
        y = y0 + 30
        lines = []
        for t in pop.texts:
            lines += self._wrap(draw, t, x1 - x0 - 28)
        max_lines = 4
        for line in lines[:max_lines]:
            draw.text((x0 + 14, y), line, font=self._f, fill=LINE)
            y += 17
        if len(lines) > max_lines:
            draw.text((x1 - 30, y - 17), '…', font=self._f, fill=DIM)
        # buttons, right-aligned at the bottom
        by0, by1 = y1 - 34, y1 - 14
        bx = x1 - 14
        for i in reversed(range(len(pop.buttons))):
            name = pop.buttons[i][0]
            w = draw.textlength(name, font=self._f_btn) + 28
            on = i == pop.selected
            draw.rectangle([bx - w, by0, bx, by1], fill=LIME if on else INK, outline=LIME if on else EDGE)
            draw.text((bx - w + 14, by0 + 3), name, font=self._f_btn, fill=INK if on else LINE)
            bx -= w + 10
        # hints, bottom left
        x, hy = x0 + 14, y1 - 30
        for key, what in (('◄ ►', 'choose'), ('▲', 'press'), ('▼', 'cancel'), ('DELETE', 'esc')):
            draw.text((x, hy), key, font=self._f_key, fill=LINE)
            x += draw.textlength(key, font=self._f_key) + 4
            draw.text((x, hy), what, font=self._f_hint, fill=FAINT)
            x += draw.textlength(what, font=self._f_hint) + 12
        return frame
