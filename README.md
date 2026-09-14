---
type: snapshot
status: active
area: dj
tags: [dj, mixxx, push2, midi-mapping]
created: 2026-06-15
updated: 2026-09-08
---

# Push 2 → Mixxx Mapping (Pusher) — Snapshot

Custom Ableton Push 2 controller mapping for Mixxx, converted from a Traktor TSI and heavily extended through iterative testing on hardware. Two core files: `pusher.midi.xml` (input/output bindings) + `pusher-script.js` (logic, LED feedback), functionprefix `PUSH2T`.

## Files

- `pusher.midi.xml` — controller preset (deck A = Ch1, deck B = Ch2)
- `pusher-script.js` — all mapping logic
- `colortest.midi.xml` + `colortest-script.js` — standalone Push 2 palette tester (SHIFT switches page 0–63 / 64–127, prints index of pressed pad to log)
- `old/` — previous version of the mapping (June 15, pre palette/CUP rework), kept for reference

Install path (Windows): `C:\Users\loren\AppData\Local\Mixxx\controllers\`

## Pad grid (current)

```
Row 8  BL÷   BEAT  BL×   VUA   BL÷   BEAT   BL×   VUB
Row 7  BJB  BGRID  BJF   VUA   BJB  BGRID   BJF   VUB
Row 6  L-IN  ...  L-OUT  VUA  L-IN   ...  L-OUT   VUB
Row 5  HC1   HC2  HC3    VUA   HC1   HC2   HC3    VUB
Row 4  HC4   HC5  HC6    VUA   HC4   HC5   HC6    VUB
Row 3  (empty — SHIFT/DELETE moved to dedicated CC buttons)
Row 2  SLP  KEY   QNT   VUA   SLP  KEY    QNT    VUB
Row 1  PLY  SYNC  CUP   VUA   PLY  SYNC   CUP    VUB
```

Cue and Sync pads were swapped on both decks: SYNC now sits inboard (closer to Play), CUP outboard.

## Key behaviors

- **CUP** — CDJ-style: playing → jump to cue + stop; stopped at cue → hold-to-preview, release rolls back; stopped off-cue → sets a NEW cue at the cursor (replaces old one). Push 2 sends release as `0x80` (Note Off) — both `0x90`/`0x80` bound for CUP.
- **CUE + PLAY combo** — hold CUE (preview), tap PLAY to lock playback in without rolling back on release (Traktor-style stutter-start).
- **Jog encoders (CC71 Deck A / CC75 Deck B)** — touch-sensitive (touch note 0x00 / 0x04).
  - Deck **stopped** + touched → velocity-sensitive scratch (`JOG_SCRATCH_VEL = 2.0`).
  - Deck **playing** + touched → tempo bend, accumulates while turning, resets to set rate the instant you lift your finger (not on a timer).
  - Deck playing, NOT touched → no effect (bend requires touch).
- **Beatloop set** — toggle: loop active → fully clears the loop (`loop_remove`, not `reloop_toggle`); loop off → always creates a fresh loop of current size at the playhead. (`reloop_toggle` only disables the loop but leaves its points cached — pressing `beatloop_X_activate` again with a matching size then just re-enables those stale points instead of computing a new one at the current playhead. `loop_remove` clears the cache so the next press is forced to start fresh. Fixed 2026-09-08 after observing the loop "stay" at its old position on re-press.)
- **Beatloop size ± while a loop is ACTIVE** — uses `loop_scale` (0.5 / 2.0) exclusively, keeping the loop START fixed and moving only the end. (Earlier version double-applied `beatloop_size` + `loop_scale`, which shifted both points on the first press — fixed by only touching `beatloop_size` when no loop is running.)
- **Beatjump (row 7, C6/D6 and E6/F#6)** — same size as current beatloop size.
- **Loop In/Out (row 6)** — respects the deck's own QNT toggle for beat-snapping; script never forces or clears quantize.
- **VU meters** — columns 4 and 8, 8 segments bottom→top: 5 green, 1 yellow, 1 orange, 1 red (`PUSH2T.VU_COLORS`).

## Modifiers (CC buttons, not pads)

- **SHIFT = CC49 (0x31)** — dim(64) idle / bright(127) held. Held: browse encoder (CC14) navigates library sidebar instead of scrolling tracks. SHIFT + Sync → resets that deck's tempo slider to 0.
- **DELETE = CC118 (0x76)** — dim(64) idle / bright(127) held. Held + hotcue press → clears that hotcue. Held + Loop In/Out → releases the active loop.
- **RECORD = CC86 (0x56)** — toggles Mixxx recording. Static white idle, static red while recording (no blink/heartbeat — removed per preference for plain colors).
- Double-tap-to-reset-sync was removed; sync toggles instantly now that SHIFT+Sync handles the reset.

## DJ colors — Pioneer CDJ/DJM-style scheme (photo-verified 2026-09-08)

Held in `PUSH2T.DJ`, all pointing at named `PUSH2T.C.*` palette entries (see
`docs/color-palette.md` for how each index was verified against real photos of the
hardware palette):
- `noteGreen`/`noteRed` = `C.green`/`C.red` — play pad, loop pads, VU top segment, and
  beatloop-size buttons all use these.
- `cue = 3` (orange, CUP lit) — matches the industry-standard CDJ/rekordbox cue color.
- `syncOn = C.blue` (matches CDJ/DJM sync-engaged convention), `syncOff = 49` (dim).
  Deliberately NOT yellow, so it doesn't double up with keylock's color.
- `hc = [C.red, C.orange, C.yellow, C.green, C.blue, C.purple]` — fixed rainbow order
  for Cue 1–6 (NOT the track's own stored cue color), matching rekordbox's default
  multi-color hot cue palette. Six clearly distinct colors, replacing the old scheme's
  near-duplicate pairs.

Browse button (CC85, Push 2 Play button, RGB) — `BROWSE_COLOR_OPEN` = `C.green`
(library maximized), `BROWSE_COLOR_CLOSED` = `C.white` (bright white, normal/idle).
Record (CC86) unchanged: white idle, red while recording.

## Known issues / open items

- White-only CC buttons (Shift/Delete) needed brightness bumped from 1→64 to be visible; confirm they're actually lighting on hardware (last known: unconfirmed after the fix).
- `CUE_AT_TOLERANCE` (0.0001) governs "is the playhead at the cue" vs "cursor moved, set new cue" — tune if CUP misfires near the cue point.
- Encountered a Mixxx JS parse error at load time once ("Expected token `,`" at line 2) — suspected UTF-8 box-drawing characters in header comments choking Mixxx's JS engine; not fully confirmed/resolved, worth ASCII-only header comments if it recurs. **Confirmed present**: the header comment block in `pusher-script.js` does contain UTF-8 box-drawing/em-dash characters — worth converting to ASCII if the parse error recurs.
- Loop resize logic has been revised twice fighting Mixxx's anchor behavior (`beatloop_size` vs `beatloop_X_activate` vs `loop_scale`) — current version (loop_scale-only while active) fixed the "first press extends both ends" bug; re-verify still correct after any further Mixxx updates.

## Debugging

Launch with `mixxx.exe --controllerDebug` from the Mixxx install folder (not `C:\Users\loren`). Watch for `incoming:` MIDI lines and `[PUSH2T]` prints in console/`mixxx.log`.

## Tunables (top of pusher-script.js)

`GAIN_STEP`, `RATE_STEP`, `VOL_STEP`, `BL_SIZES`, `JOG_SCRATCH_VEL`, `JOG_BEND_STEP`, `JOG_BEND_MAX`, `PUSH2T.DJ.*` colors, `BROWSE_COLOR_*`, `VU_COLORS`, `LIBRARY_FOCUS_STEPS`, `CUE_AT_TOLERANCE`.

## Related

- [[mixxx]]
- [[ableton-push-2]]
