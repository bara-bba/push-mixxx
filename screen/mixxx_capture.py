"""
Captures the custom "Pusher160" Mixxx skin (../skins/push2 in this repo, installed
at %LOCALAPPDATA%/Mixxx/skins/Pusher160) and sends it straight to the Push 2.

Everything is done IN THE SKIN - this module does a straight screen capture
+ resize to 960x160, nothing more. No cropping, rotating, or reassembling
pieces in Python. That matters for the real deployment target: a headless
Pi3 running Mixxx on a virtual display with the Push 2 as the only screen,
so whatever's wrong with the layout has to be fixed in the skin itself
(Pusher160/skin.xml), not patched around here.

Why capture the skin at all instead of decoding audio/drawing our own
overlay: the skin has direct access to track metadata/cover art (unlike
Mixxx's controller scripting API, which has never exposed title/artist -
github.com/mixxxdj/mixxx/issues/6898) and renders waveforms, cue points and
loop markers natively - no reason to reinvent any of that.

Pusher160 is display-only - no transport buttons/library, since Push 2's
own hardware buttons already control playback via push-mixxx's
pusher-script.js.

Self-calibrating (Windows only): finds the live Mixxx window via Win32 and
reads its actual client-area bounds every time, rather than trusting a
hardcoded screen position - the window moves/resizes across restarts (e.g.
after a forced taskkill, which doesn't let Mixxx save its geometry) and
this dev machine isn't always in a state where it can be repositioned. The
native title bar + menu bar sit inside the client rect (Win32 doesn't
separate them out), so MENU_BAR_HEIGHT below crops those off to leave just
the skin's own content. On the real Pi3 deployment (headless, virtual
display, no window chrome at all) this self-calibration is moot - swap in
a fixed region matching that display.
"""

import ctypes
import subprocess
from ctypes import wintypes

import mss
from PIL import Image

MENU_BAR_HEIGHT = 21  # File/Library/View/Options/Help row, inside the client rect -
# measured directly (client origin y=131, content top y=152).

# Fallback if the window can't be found (Mixxx not running / not on Windows) -
# last-known-good position, in case a plain grab is still better than nothing.
FALLBACK_REGION = {"left": 108, "top": 152, "width": 960, "height": 160}

# Pi: Mixxx runs fullscreen on a 960x160 Xvfb display, so the skin is the whole screen.
HEADLESS_REGION = {"left": 0, "top": 0, "width": 960, "height": 160}

TARGET_SIZE = (960, 160)

user32 = ctypes.windll.user32 if hasattr(ctypes, 'windll') else None


class RECT(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                ("right", wintypes.LONG), ("bottom", wintypes.LONG)]


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


def _find_mixxx_hwnd():
    """Finds the Mixxx main window by walking top-level windows and matching
    the process image name - title-based lookup breaks once a track is
    loaded (title becomes "Artist - Title | Mixxx")."""
    if user32 is None:
        return None

    result = []

    def callback(hwnd, lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        try:
            import psutil
            proc = psutil.Process(pid.value)
            if proc.name().lower() == 'mixxx.exe':
                result.append(hwnd)
                return False
        except Exception:
            pass
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows(WNDENUMPROC(callback), 0)
    return result[0] if result else None


def focus_mixxx():
    """Brings the Mixxx window to the foreground (Windows only). Mixxx ignores
    the [Library] navigation controls the Push arrows / browse encoder use
    ("No Mixxx window, popup or menu has focus. Don't send key events")
    unless one of its windows has focus, which on a desktop with other apps
    open it usually doesn't. Windows refuses SetForegroundWindow from a
    background process, so attach to the foreground thread's input first.
    Returns True if Mixxx is in front afterwards."""
    if user32 is None:
        return _x11_focus_main()
    hwnd = _find_mixxx_hwnd()
    if not hwnd:
        return False
    fg = user32.GetForegroundWindow()
    if fg == hwnd:
        return True
    kernel32 = ctypes.windll.kernel32
    me = kernel32.GetCurrentThreadId()
    fg_thread = user32.GetWindowThreadProcessId(fg, None) if fg else 0
    attached = bool(fg_thread and fg_thread != me and user32.AttachThreadInput(me, fg_thread, True))
    try:
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(me, fg_thread, False)
    return user32.GetForegroundWindow() == hwnd


def _xdo(*args):
    try:
        return subprocess.run(['xdotool', *args], capture_output=True, text=True, timeout=2).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ''


def _x11_windows():
    """(window id, title) of every visible X window (Pi: no window manager)."""
    out = []
    for wid in _xdo('search', '--onlyvisible', '--name', '').split():
        name = _xdo('getwindowname', wid).strip()
        if name:
            out.append((wid, name))
    return out


def _is_main_title(name):
    # "Mixxx", or "Artist - Title | Mixxx" once a track is loaded
    return name == 'Mixxx' or name.endswith('| Mixxx')


def _x11_focus_main():
    for wid, name in _x11_windows():
        if _is_main_title(name):
            _xdo('windowfocus', '--sync', wid)
            return True
    return False


def close_mixxx_popups():
    """Linux only: sends Escape to every visible window except the main Mixxx
    window (file pickers, message boxes - e.g. the iTunes picker Browse opens
    when the sidebar lands on iTunes), then gives focus back to Mixxx so
    library navigation keeps working. Returns how many were closed."""
    if user32 is not None:
        return 0
    closed = 0
    for wid, name in _x11_windows():
        if _is_main_title(name):
            continue
        _xdo('windowfocus', '--sync', wid, 'key', '--window', wid, 'Escape')
        closed += 1
    if closed:
        _x11_focus_main()
    return closed


# Pusher160 shows one 960x160 page at a time (Browse or Device, switched
# inside the skin on the push-mixxx scene), so the capture is always just
# the top-left 960x160 of the content area.
def _live_content_region():
    hwnd = _find_mixxx_hwnd()
    if not hwnd:
        return None

    client = RECT()
    if not user32.GetClientRect(hwnd, ctypes.byref(client)):
        return None

    origin = POINT(0, 0)
    if not user32.ClientToScreen(hwnd, ctypes.byref(origin)):
        return None

    # The skin's pages are fixed 960 wide; anything past that is empty window
    # background, and including it would squish the frame on resize.
    width = min(client.right - client.left, TARGET_SIZE[0])
    height = min(client.bottom - client.top - MENU_BAR_HEIGHT, TARGET_SIZE[1])
    if width <= 0 or height <= 0:
        return None

    return {"left": origin.x, "top": origin.y + MENU_BAR_HEIGHT, "width": width, "height": height}


class MixxxSkinCapture:
    def __init__(self, region=None):
        self._fixed_region = region  # if given, skip self-calibration
        self._sct = None

    def _ensure_sct(self):
        if self._sct is None:
            self._sct = mss.mss()
        return self._sct

    def capture(self):
        """Grabs the skin's visible page (self-calibrated each call unless a
        fixed region was passed to __init__) and resizes to exactly
        960x160. Returns None on any capture failure (window not found/
        closed/minimized) rather than raising - callers should keep showing
        the last good frame."""
        if self._fixed_region:
            region = self._fixed_region
        elif user32 is None:
            region = HEADLESS_REGION
        else:
            region = _live_content_region() or FALLBACK_REGION

        try:
            sct = self._ensure_sct()
            shot = sct.grab(region)
            img = Image.frombytes('RGB', shot.size, shot.bgra, 'raw', 'BGRX')
        except Exception:
            self._sct = None  # force reconnect next time
            return None

        if img.size == TARGET_SIZE:
            return img
        return img.resize(TARGET_SIZE, Image.BILINEAR)

    def close(self):
        if self._sct is not None:
            self._sct.close()
            self._sct = None
