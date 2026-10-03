"""Raspberry Pi health page for the Push 2 screen (toggled with the USER button).

Samples once a second in the background and draws a 960x160 frame in the
Pusher160 palette: temperature/clock/throttling, CPU, memory, and the
Mixxx + screen-bridge processes. Throttling is the thing to watch on the Pi 3:
past ~80 C the firmware caps the clock and Mixxx starts dropping audio.
"""

import os
import socket
import subprocess
import threading
import time

import psutil
from PIL import Image, ImageDraw, ImageFont

# Pusher160 palette (skins/push2/gen_skin.py)
INK = (0x0B, 0x0B, 0x0B)
LINE = (0xE8, 0xE8, 0xE2)
DIM = (0x8C, 0x8C, 0x86)
FAINT = (0x5A, 0x5A, 0x55)
EDGE = (0x3A, 0x3A, 0x36)
HAIR = (0x2A, 0x2A, 0x28)
LIME = (0xC8, 0xF5, 0x3C)
ORANGE = (0xE8, 0xA3, 0x3A)
RED = (0xFF, 0x2B, 0x1C)

W, H = 960, 160
COL_W = W // 4

DISPLAY_FONTS = [os.path.expanduser('~/.local/share/fonts/TAN-SPRING.otf'),
                 os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Microsoft', 'Windows', 'Fonts', 'TAN-SPRING.otf')]
BODY_FONTS = ['/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf', 'arial.ttf']
BODY_BOLD_FONTS = ['/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf', 'arialbd.ttf']

# vcgencmd get_throttled bits: (now, has-occurred) pairs
THROTTLE_FLAGS = [(0x1, 'UNDERVOLT'), (0x2, 'CLOCK CAPPED'), (0x4, 'THROTTLED'), (0x8, 'TEMP LIMIT')]


def _font(candidates, size):
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _read(path, default=None):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return default


def _lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))  # no packet is sent; just picks the outbound interface
        return s.getsockname()[0]
    except OSError:
        return '-'
    finally:
        s.close()


def _level_color(value, warn, alarm):
    if value >= alarm:
        return RED
    if value >= warn:
        return ORANGE
    return LIME


class PiStats:
    def __init__(self, fps_source=None):
        self._fps_source = fps_source or (lambda: 0.0)
        self._data = {}
        self._lock = threading.Lock()
        self._thread = None
        self.f_big = _font(DISPLAY_FONTS, 40)
        self.f_mid = _font(DISPLAY_FONTS, 20)
        self.f_label = _font(BODY_BOLD_FONTS, 11)
        self.f_body = _font(BODY_FONTS, 12)
        self.hostname = socket.gethostname()

    def start(self):
        if self._thread is None:
            psutil.cpu_percent(percpu=True)  # prime the counters
            self._thread = threading.Thread(target=self._sample_loop, daemon=True)
            self._thread.start()

    def _sample_loop(self):
        procs = {}
        while True:
            self._sample(procs)
            time.sleep(1.0)

    def _sample(self, procs):
        d = {'cores': psutil.cpu_percent(percpu=True)}
        d['cpu'] = sum(d['cores']) / max(len(d['cores']), 1)
        d['load'] = os.getloadavg() if hasattr(os, 'getloadavg') else (0, 0, 0)

        temp = _read('/sys/class/thermal/thermal_zone0/temp')
        d['temp'] = int(temp) / 1000 if temp else None
        freq = _read('/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq')
        d['mhz'] = int(freq) // 1000 if freq else None
        try:
            out = subprocess.run(['vcgencmd', 'get_throttled'], capture_output=True, text=True, timeout=1).stdout
            d['throttled'] = int(out.strip().split('=')[1], 16)
        except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
            d['throttled'] = None

        vm, sw = psutil.virtual_memory(), psutil.swap_memory()
        d['mem'] = (vm.total - vm.available, vm.total)
        d['swap'] = (sw.used, sw.total)
        d['disk'] = psutil.disk_usage('/').percent

        for name in ('mixxx', 'python'):
            p = procs.get(name)
            if p is None or not p.is_running():
                p = self._find_proc(name)
                procs[name] = p
                if p:
                    p.cpu_percent()
            try:
                d[name] = (p.cpu_percent(), p.memory_info().rss) if p else None
            except psutil.Error:
                procs[name], d[name] = None, None

        d['uptime'] = time.time() - psutil.boot_time()
        d['ip'] = _lan_ip()
        with self._lock:
            self._data = d

    @staticmethod
    def _find_proc(name):
        me = os.getpid()
        for p in psutil.process_iter(['name', 'pid']):
            pname = (p.info['name'] or '').lower()
            if name == 'python' and p.info['pid'] == me:
                return p
            if name == 'mixxx' and pname in ('mixxx', 'mixxx.exe'):
                return p
        return None

    # ---- drawing -------------------------------------------------------

    def _panel(self, draw, col, label):
        x = col * COL_W
        if col:
            draw.line([(x, 8), (x, H - 8)], fill=HAIR)
        draw.text((x + 12, 8), label, font=self.f_label, fill=DIM)
        return x + 12

    def _bar(self, draw, x, y, w, h, frac, color):
        draw.rectangle([x, y, x + w, y + h], outline=EDGE)
        fill_w = int((w - 2) * max(0.0, min(frac, 1.0)))
        if fill_w > 0:
            draw.rectangle([x + 1, y + 1, x + fill_w, y + h - 1], fill=color)

    def render(self):
        with self._lock:
            d = dict(self._data)
        img = Image.new('RGB', (W, H), INK)
        draw = ImageDraw.Draw(img)
        if not d:
            draw.text((12, 70), 'READING PI STATS...', font=self.f_label, fill=DIM)
            return img
        bar_w = COL_W - 24

        # TEMPERATURE / CLOCK / THROTTLING
        x = self._panel(draw, 0, 'TEMPERATURE')
        temp = d.get('temp')
        tcol = _level_color(temp, 70, 80) if temp is not None else DIM
        draw.text((x, 24), f"{temp:.1f}°" if temp is not None else '--', font=self.f_big, fill=tcol)
        if temp is not None:
            self._bar(draw, x, 76, bar_w, 8, (temp - 30) / 55, tcol)
        draw.text((x, 92), f"CLOCK  {d['mhz']} MHz" if d.get('mhz') else 'CLOCK  -', font=self.f_body, fill=LINE)
        thr = d.get('throttled')
        if thr is None:
            status, scol = 'THROTTLE  n/a', DIM
        else:
            now = [n for bit, n in THROTTLE_FLAGS if thr & bit]
            past = [n for bit, n in THROTTLE_FLAGS if thr & (bit << 16)]
            if now:
                status, scol = ' + '.join(now), RED
            elif past:
                status, scol = 'OK  (was: ' + ', '.join(past).lower() + ')', ORANGE
            else:
                status, scol = 'OK', LIME
        draw.text((x, 110), status, font=self.f_label, fill=scol)

        # CPU
        x = self._panel(draw, 1, 'CPU')
        cpu = d['cpu']
        ccol = _level_color(cpu, 70, 90)
        draw.text((x, 24), f"{cpu:.0f}%", font=self.f_big, fill=ccol)
        cores = d['cores']
        core_w = (bar_w - (len(cores) - 1) * 4) // max(len(cores), 1)
        for i, c in enumerate(cores):
            cx = x + i * (core_w + 4)
            self._bar(draw, cx, 76, core_w, 8, c / 100, _level_color(c, 70, 90))
        l1, l5, l15 = d['load']
        draw.text((x, 92), f"LOAD  {l1:.2f}  {l5:.2f}  {l15:.2f}", font=self.f_body, fill=LINE)
        draw.text((x, 110), f"DISK  {d['disk']:.0f}% used", font=self.f_body, fill=DIM)

        # MEMORY
        x = self._panel(draw, 2, 'MEMORY')
        used, total = d['mem']
        mfrac = used / total if total else 0
        mcol = _level_color(mfrac * 100, 75, 90)
        draw.text((x, 24), f"{mfrac * 100:.0f}%", font=self.f_big, fill=mcol)
        self._bar(draw, x, 76, bar_w, 8, mfrac, mcol)
        draw.text((x, 92), f"RAM  {used >> 20} / {total >> 20} MB", font=self.f_body, fill=LINE)
        su, st = d['swap']
        draw.text((x, 110), f"SWAP  {su >> 20} / {st >> 20} MB", font=self.f_body, fill=DIM)

        # PROCESSES / SYSTEM
        x = self._panel(draw, 3, 'SYSTEM')
        y = 26
        for label, key in (('MIXXX', 'mixxx'), ('SCREEN', 'python')):
            val = d.get(key)
            text = f"{val[0]:.0f}% cpu  {val[1] >> 20} MB" if val else 'not running'
            draw.text((x, y), label, font=self.f_label, fill=DIM)
            draw.text((x + 62, y - 2), text, font=self.f_body, fill=LINE if val else RED)
            y += 18
        draw.text((x, y), 'FPS', font=self.f_label, fill=DIM)
        draw.text((x + 62, y - 2), f"{self._fps_source():.1f}", font=self.f_body, fill=LINE)
        up = int(d['uptime'])
        draw.text((x, 92), f"UP  {up // 86400}d {up % 86400 // 3600}h {up % 3600 // 60}m", font=self.f_body, fill=LINE)
        draw.text((x, 110), f"{self.hostname}  {d['ip']}", font=self.f_body, fill=DIM)

        draw.text((12, H - 22), 'USER: back to Mixxx', font=self.f_label, fill=FAINT)
        return img
