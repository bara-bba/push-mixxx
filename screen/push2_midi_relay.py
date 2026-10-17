#!/usr/bin/env python3
"""Pi: relays MIDI between the Push 2 and a VirMIDI port that never goes away.

Mixxx 2.5 only opens MIDI ports at startup, so with the Push bound directly
an unplug kills the mapping until Mixxx restarts. Here Mixxx's Push mapping
is bound to VirMIDI 7-1 instead, and this relay copies bytes both ways
between that port's raw device (/dev/snd/midiC7D1) and the Push's Live Port
raw device, re-opening the Push whenever it is plugged back in. After a
reconnect it sends CC 127 on channel 16 so the mapping (PUSH2T.redraw) and
the screen app repaint the Push's LEDs.

Byte-level copy: the ALSA raw devices on both ends do their own MIDI parsing,
so split SysEx / running status pass through untouched.
"""
import argparse
import os
import re
import select
import time

REDRAW = bytes([0xBF, 0x7F, 0x7F])
RETRY_SECONDS = 0.5


def push_raw_device():
    """/dev/snd/midiC<card>D0 of the Push 2 (card id 'A2'), or None."""
    try:
        with open('/proc/asound/cards') as f:
            for line in f:
                m = re.match(r'\s*(\d+)\s+\[A2\s*\]', line)
                if m:
                    path = f'/dev/snd/midiC{m.group(1)}D0'
                    return path if os.path.exists(path) else None
    except OSError:
        pass
    return None


def write_all(fd, data):
    while data:
        n = os.write(fd, data)
        data = data[n:]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--virmidi', default='/dev/snd/midiC7D1', help='raw device of the VirMIDI port Mixxx uses')
    args = ap.parse_args()

    vfd = os.open(args.virmidi, os.O_RDWR | os.O_NONBLOCK)
    print(f'[relay] Mixxx side: {args.virmidi}', flush=True)
    pfd = None
    while True:
        if pfd is None:
            path = push_raw_device()
            if path:
                try:
                    pfd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
                    print(f'[relay] Push connected: {path}', flush=True)
                    time.sleep(0.3)  # Push firmware settles before it takes LED data
                    write_all(vfd, REDRAW)
                except OSError as e:
                    print(f'[relay] cannot open {path}: {e}', flush=True)
                    pfd = None
        fds = [vfd] + ([pfd] if pfd is not None else [])
        ready, _, _ = select.select(fds, [], [], RETRY_SECONDS)
        try:
            if pfd is not None and pfd in ready:
                data = os.read(pfd, 1024)
                if not data:
                    raise OSError('Push closed')
                write_all(vfd, data)
            if vfd in ready:
                data = os.read(vfd, 1024)
                if pfd is not None and data:
                    write_all(pfd, data)
                # Push unplugged: Mixxx's output is dropped; the redraw repaints later
        except BlockingIOError:
            pass
        except OSError as e:
            if pfd is not None:
                print(f'[relay] Push disconnected ({e})', flush=True)
                try:
                    os.close(pfd)
                except OSError:
                    pass
                pfd = None


if __name__ == '__main__':
    main()
