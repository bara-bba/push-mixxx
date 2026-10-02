"""
Real waveform rendering for the Push 2 display.

Decodes the actual audio file (via a bundled ffmpeg binary - imageio_ffmpeg,
so any format ffmpeg reads: mp3/m4a/aiff/wav/flac/...) into a low-res min/max
envelope, once per track, then mixxx-midi-bridge.py scrolls through it live
using the real-time playposition already streamed over SysEx. This is our
own rendering, not a copy of Mixxx's own waveform widget - no screen capture
involved, so latency is just however fast playposition updates arrive.

Decoding a whole track takes real time (sub-second for a typical track at
an 8kHz mono decode rate, but never block the render/MIDI threads on it) -
callers should treat get() as "may return None for a track or two while it
decodes in the background" and keep rendering with the previous state.
"""

import os
import queue
import subprocess
import threading

import numpy as np

try:
    import imageio_ffmpeg
    FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG_EXE = None

ENVELOPE_COLUMNS = 2000   # resolution of the cached min/max envelope
DECODE_SAMPLE_RATE = 8000  # plenty for a visual envelope, keeps decode fast


class WaveformCache:
    """Decodes audio files to a min/max envelope in a background thread, cached by path."""

    def __init__(self):
        self._cache = {}  # path -> np.ndarray (ENVELOPE_COLUMNS, 2) float32 in [-1, 1], or 'pending', or 'failed'
        self._lock = threading.Lock()
        self._queue = queue.Queue()
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    def get(self, path):
        """Returns the cached envelope for `path`, or None if not ready yet (queues a decode)."""
        if not path or FFMPEG_EXE is None:
            return None

        with self._lock:
            cached = self._cache.get(path)

        if cached is None:
            with self._lock:
                if path not in self._cache:
                    self._cache[path] = 'pending'
                    self._queue.put(path)
            return None

        return cached if isinstance(cached, np.ndarray) else None

    def _run(self):
        while True:
            path = self._queue.get()
            envelope = self._decode(path)
            with self._lock:
                self._cache[path] = envelope if envelope is not None else 'failed'

    def _decode(self, path):
        if not os.path.exists(path):
            return None
        try:
            cmd = [FFMPEG_EXE, '-i', path, '-f', 's16le', '-ac', '1',
                   '-ar', str(DECODE_SAMPLE_RATE), '-']
            proc = subprocess.run(cmd, capture_output=True, timeout=60)
            if proc.returncode != 0 or not proc.stdout:
                return None
            samples = np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32) / 32768.0
        except Exception:
            return None

        if samples.size < ENVELOPE_COLUMNS:
            return None

        chunk = samples.size // ENVELOPE_COLUMNS
        trimmed = samples[:chunk * ENVELOPE_COLUMNS].reshape(ENVELOPE_COLUMNS, chunk)
        env = np.stack([trimmed.min(axis=1), trimmed.max(axis=1)], axis=1)
        return env
