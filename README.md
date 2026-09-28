---
type: snapshot
status: active
area: dj
tags: [dj, mixxx, push2, midi-mapping]
created: 2026-06-15
updated: 2026-09-26
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
- **Beatloop anchor (Start vs. End)** — `PUSH2T.init` now force-sets `loop_anchor` to `0` (Start) on both `[Channel1]`/`[Channel2]` every time the mapping loads. Root cause of loops setting the cursor as the loop's END instead of its START: not a script bug — Mixxx persists a per-deck `loop_anchor` control (`0` = Start/forward, `1` = End/backward) in `mixxx.cfg`, and the two decks driven by the Push 2 had it saved as `1` (likely flipped via the skin's own loop-anchor toggle at some point), while the unused decks 3/4 sat at the real default of `0`. Forcing it at init makes `beatloop_activate` deterministically forward regardless of what the GUI last left it at. Fixed 2026-09-26.
- **Beatloop size ± while a loop is ACTIVE** — uses `loop_scale` (0.5 / 2.0) exclusively, keeping the loop START fixed and moving only the end. (Earlier version double-applied `beatloop_size` + `loop_scale`, which shifted both points on the first press — fixed by only touching `beatloop_size` when no loop is running.)
- **Beatjump (row 7, C6/D6 and E6/F#6)** — same size as current beatloop size.
- **Loop In/Out (row 6)** — respects the deck's own QNT toggle for beat-snapping; script never forces or clears quantize. Sent as a pulse (1 then 0): leaving `loop_in`/`loop_out` at 1 makes Mixxx treat it as held and the point follows the playhead. With no active loop a press sets the point; with an active loop a press does NOT move it — instead, **hold the pad and turn that deck's jog encoder to fine-tune** the point (5 ms per tick, `PUSH2T.LOOP_TUNE_MS`); needs the XML Note Off (0x80) bindings.
- **Beatgrid pad (row 7 middle)** — only fires with SHIFT held (dim until then) to avoid accidentally moving the grid.
- **Beatjump pads** — flash white while pressed; XML binds Note Off (0x80) too so they return to color on release.
- **VU meters** — columns 4 and 8, 8 segments bottom→top: 5 deck-color (blue for A, red for B), 1 yellow, 1 orange, 1 red (`PUSH2T.vuColorsFor`).

## Modifiers (CC buttons, not pads)

- **SHIFT = CC49 (0x31)** — dim(64) idle / bright(127) held. Held: browse encoder (CC14) navigates library sidebar instead of scrolling tracks. SHIFT + Sync → resets that deck's tempo slider to 0.
- **DELETE = CC118 (0x76)** — dim(64) idle / bright(127) held. Held + hotcue press → clears that hotcue. Held + Loop In/Out → releases the active loop.
- **RECORD = CC86 (0x56)** — toggles Mixxx recording. Static white idle, static red while recording (no blink/heartbeat — removed per preference for plain colors).
- Double-tap-to-reset-sync was removed; sync toggles instantly now that SHIFT+Sync handles the reset.

## DJ colors — Traktor-style scheme, user-tuned on hardware (2026-09-26)

Every pad / LED button has an ON and an OFF color, stored as "slots" (`PUSH2T.slots`,
keys `P<note>` for pads and `C<cc>` for CC buttons). Defaults are built in
`PUSH2T.buildSlots`; hardware-tuned values live in `PUSH2T.SAVED` (baked from the Mixxx
log). Highlights: Play = green (pale green when stopped), Cue = orange (brighter while
held, pale white with no cue), Sync = blue (mid blue when off), Slip/Keylock/Quantize =
purple tints, hotcues 1-6 = Traktor-style red/orange/yellow/green/teal/blue, VU = green
with yellow/orange/red top segments. Right deck's Play/Sync/Cue and all OFF colors mirror
the left deck. Palette notes: `docs/color-palette.md`. Pale/inactive index guesses
(`paleWhite`, `paleBlue`, `paleGreen`) were tuned by eye; `C.gray` (1) reads pink, avoid.

### Color-edit mode (SELECT, CC48)

SELECT toggles it. All pads/buttons (incl. VU segments) show their ON colors; hold SHIFT
to show/edit OFF colors. Press a pad/button to select it (nothing else fires), turn the
tempo encoder (CC14) to step its palette index. Every change prints
`[PUSH2T] COLORS {...}` to the Mixxx log; scripts can't write files, so copy the values
into `PUSH2T.SAVED` to keep them. Handlers are wrapped at script load (end of file) so
color mode can intercept them; Load buttons and VU pads have script bindings in the XML
for that reason.

## Library mode, deck select, tap tempo, pitch strip

- **Arrows (CC44-47)** — Up/Down walk the focused list (tracks or sidebar folders/playlists/crates). Left/Right move focus sidebar <-> tracks; SHIFT+Right opens the selected sidebar item. While the preview deck plays, Left/Right seek the preview instead (`PREVIEW_SEEK_SEC` = 10).
- **Top row (CC102-109), library mode only** (library maximized via the Play/browse button): button 1 = preview play/pause (resumes if the selection didn't move, else loads the selected track), 2 = empty, 3-8 = sort by Title, Artist, Album, BPM, Key, Duration (`sort_column_toggle`, press again flips order; ids in `PUSH2T.SORT_COLUMNS`, written against Mixxx 2.5.6). Outside library mode CC105/CC109 are the Gain Reset buttons, colored green -> red by gain (`GAIN_RAMP`, white at 0 dB).
- **Deck select (CC23 = A, CC27 = B)** — SHIFT+press selects that deck (orange, exclusive); a plain press releases all. Default none. `PUSH2T.selectedDeck` / `selectedGroup()` expose it.
- **Tap tempo (CC3)** — with a deck selected, taps set that deck's `bpm` (average of last 8 intervals, 2 s reset), playing or stopped.
- **Metronome (CC9)** — with a deck selected, cycles its `rateRange` (6/8/10/16/24/50/90%).
- **Touch strip** — while touched (note 12) and a deck is selected, sets `rate` from the finger position across the current range. Exact-center pitch-bend (the spring-back on release) is ignored so the pitch stays put.
- **Color-edit mode (SELECT CC48)** — Duplicate (CC88) copies one slot's color to others (press Duplicate, press source, press destinations).

## Scenes (Device CC110 / Browse CC111 / Mix CC112 / Clip CC113)

A scene decides what the top row (CC102-109) and the touch strip do (`PUSH2T.scene`, `setScene`).
- **Browse** (also toggled by the Play/browse button CC85; = library maximized): top row = preview play/pause (red stopped, green playing) + sort buttons; strip = seek the preview song, and its LEDs show a dim fill up to a bright cursor at the preview position. Entering it focuses the track table and places a cursor (`focusTrackTable`; uses `[Library] focused_widget`, falls back to MoveFocusForward).
- **Device / Mix / Clip**: reserved (enter/leave only, LED lit while active). Pressing any scene button leaves Browse and un-maximizes the library.
- **No scene**: strip = pitch of the selected deck; strip LEDs show a single dot (deck pitch, or center with no deck selected). Strip LEDs are always host-drawn via SysEx (`midi.sendSysexMsg`; config byte 0x67), never Push's own display.
- Arrows only navigate the library (no preview seeking); the strip does the seeking.
- **Device scene is the default/resting scene** (`PUSH2T.scene` starts as `'device'`; toggling any scene off returns to it, not to a scene-less state).
- **CUP fix (2026-09-28)**: stopped + a cue already set now ALWAYS jumps/previews from it, regardless of playhead position — fixes a freshly-loaded stopped track (playhead at 0 by default) silently overwriting its real cue on the first press. Relocating the cue while stopped now needs SHIFT+CUP explicitly, replacing the old "off-cue = relocate" auto-detection.
- **Lower row (CC20-27)**: Load A/B (CC20/CC24) load the selected track; Prev/Next (CC21/22, CC25/26) no longer load tracks — in every scene they toggle FX unit 1 / 2 on that deck's channel (`EffectRack1_EffectUnitN` `group_[ChannelX]_enable`; idle = your color, on = `FX_ON_COLOR`); CC23/CC27 = deck select.
- **Mix scene**: encoders CC71-74 / buttons CC102-105 = FX unit 1, CC75-78 / CC106-109 = FX unit 2. Knobs 1-3 = the effects' knob (`meta`), buttons 1-3 = effect on/off, knob 4 = unit `mix` (master), button 4 = reset the 3 knobs to `FX_KNOB_DEFAULT`. Jog/gain encoders and the top-row sort/gain-reset buttons are taken over while in this scene.

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
