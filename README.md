---
type: snapshot
status: active
area: dj
tags: [dj, mixxx, push2, display]
created: 2026-09-27
updated: 2026-09-27
---

# Mixxx → Push 2 Display

Streams Mixxx DJ software to an Ableton Push 2's screen — either by mirroring a
screen-capture region, or by rendering custom visuals from Mixxx's MIDI state.
Works on Windows (dev/testing) and Raspbian/Linux (production).

Controller mapping (Push 2 → Mixxx buttons/pads) lives in the sibling
[push-mixxx](../push-mixxx) repo, not here — see [Related](#related).

## Modes

- **Screen capture** (`mixxx-to-push2.py`) — grabs a screen region, scales to
  960x160, streams to Push 2. Easiest to get running; ~30 FPS.
- **MIDI bridge** (`mixxx-midi-bridge.py`) — reads Mixxx state via MIDI and
  renders custom displays (track info, BPM, playback state) directly. Lower
  latency/CPU than screen capture; no control-back-to-Mixxx yet.

## Files

```
readme.md                    # this file
license                      # MIT
requirements.txt             # Python deps
config.json                  # capture region / FPS config

mixxx-to-push2.py            # screen-capture mode
mixxx-midi-bridge.py         # MIDI bridge mode

docs/
  quickstart.md               # 5-minute quick start
  setup-windows.md             # Windows setup
  setup-raspbian.md            # Raspberry Pi / Linux setup
  install-libusb-windows.md    # libusb driver via Zadig
  install-libusb-backend.md    # libusb backend details
  mixxx-integration.md         # MIDI bridge design notes / control list
  mixxx-midi-setup.md          # Mixxx MIDI preferences setup
  risks-and-safety.md          # safety info

utils/
  test-push2.py                # test connection (animated pattern)
  check-push2.py                # detect Push 2 (safe, no display writes)
  find-window.py                # interactive capture-region finder
  download-libusb.py            # libusb DLL download helper (Windows)

examples/                     # sample capture/output images
scripts/99-push2.rules        # Linux udev rules for USB permissions
```

## Requirements

- Ableton Push 2, USB 2.0+, external power recommended for full brightness
- Python 3.7+, libusb (system library)

## Quick start

```bash
pip install -r requirements.txt
python utils/test-push2.py          # verify connection — animated test pattern
python mixxx-to-push2.py            # screen capture mode
# or
python mixxx-midi-bridge.py         # MIDI bridge mode
```

**Windows**: also install the libusb driver — see
[`docs/install-libusb-windows.md`](docs/install-libusb-windows.md).

**Linux/Raspbian**:
```bash
sudo cp scripts/99-push2.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
```

Full walkthrough: [`docs/quickstart.md`](docs/quickstart.md).

## Configuration

`config.json` controls the screen-capture region and target FPS:

```json
{
  "capture_region": { "x": 0, "y": 0, "width": 1000, "height": 150 },
  "fps_target": 30
}
```

Use `python utils/find-window.py` to find the right coordinates.

## Technical details

- Display: 960x160 px, BGR565 (16-bit color)
- USB: bulk transfer endpoint 0x01, vendor 0x2982 (Ableton), product 0x1967 (Push 2)
- Frame rate: up to 36 FPS (30 recommended)

## Open items

- MIDI bridge does not yet send controls back to Mixxx (display-only for now).
- Custom-render layouts (waveform, VU, effects) in
  [`docs/mixxx-integration.md`](docs/mixxx-integration.md) are design notes,
  not yet implemented.

## Troubleshooting

See [`docs/risks-and-safety.md`](docs/risks-and-safety.md) and the
per-platform setup docs. Quick checks:

```bash
python utils/check-push2.py     # is Push 2 detected?
python utils/test-push2.py      # does the display actually draw?
```

## Credits

Based on [push2-python](https://github.com/ffont/push2-python) by Frederic Font
and the [Ableton Push 2 MIDI/Display Interface Manual](https://github.com/Ableton/push-interface).

## Related

- [[push-mixxx]] — the Push 2 controller mapping (MIDI in/out, pads, LEDs)
- [[mixxx]]
- [[ableton-push-2]]

## License

MIT — see [`license`](license).
