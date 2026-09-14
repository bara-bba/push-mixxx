# Push 2 Color Palette — Field Reference

Source photos: `colortest-page1-indices-0-63.jpg`, `colortest-page2-indices-64-127.jpg`
(taken 2026-09-08, using the "Push 2 Color Test" mapping — `colortest.midi.xml` / `colortest-script.js`)

Grid position is **exact** — it comes from the deterministic layout the script draws
(`index = page·64 + (row-1)·8 + (col-1)`, row 1 = bottom, col 1 = left). Color **names**
below are my best-effort read of the photos under unknown indoor white balance — treat
them as approximate, not calibrated. Page 1 (0–63) genuinely renders as pale/pastel,
low-saturation colors on this hardware (confirmed by hardware owner, not a photo
exposure artifact) — likely the white-LED-dominant half of the palette. Page 2 (64–127)
is the rich/saturated RGB half.

## ⚠️ Flagged for hardware double-check

These are indices the mapping **already uses** where the photo doesn't obviously match
what the code's constant name implies. Worth looking at directly on the unit (no camera)
before changing anything:

| Constant | Index | Code assumes | Photo shows | Used for |
|---|---|---|---|---|
| `C.gray` | 1 | neutral gray | **pale pink** | cue-unset, slip/keylock/quantize-off, loop-inactive |
| `C.darkgreen` | 12 | dim green | **yellow** | play-stopped, loop-inactive dim state |
| `C.lime` | 18 | lime / yellow-green | **blue** | loop-active bright indicator |
| `C.orange` | 7 | orange | **tan** | beatgrid, beatjump-forward, beatloop ±, browse |
| `C.teal` | 50 | teal | **pale lavender** (whole row 7 reads pastel-blue in the photo, low confidence) | keylock-related / beatjump-back idle |
| `C.purple` | 48 | purple | **pale lavender** (paler than expected, same family) | slip-mode-on |
| `DJ.syncOn` / `C.yellow` | 8 | yellow | **orange** | sync-active, keylock-on (shared index, so functionally consistent even if the name's off) |

Confirmed matching:

| Constant | Index | Photo shows |
|---|---|---|
| `C.off` | 0 | off / unlit ✅ |
| `C.white` | 122 | white ✅ |
| `C.green` / `DJ.noteGreen` | 126 | green ✅ |
| `C.red` / `DJ.noteRed` | 127 | red ✅ |

Hotcue slot colors (`DJ.hc = [21,22,23,13,14,15]`, Cue 1–6) read as: purple, purple,
magenta, mint, teal, teal — slots 1↔2 and 5↔6 look like near-duplicates rather than 6
distinct colors. Worth deciding if that's fine or if the 6 slots should be more visually
distinct.

## Full palette read (best effort)

### Page 1 — indices 0–63 (pale/pastel range)

| Row\Col | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| 8 (idx 56–63) | pale rose | pale rose | pale rose | pale rose | pale rose | pale rose | pale rose | pale rose |
| 7 (idx 48–55) | pale lavender | pale lavender | pale lavender | pale lavender | pale pink-lavender | pale lavender | pale lavender | pale lavender |
| 6 (idx 40–47) | tan | tan | tan | pale mint | pale mint | pale mint | pale blue | pale blue |
| 5 (idx 32–39) | green | blue | purple | pink | pink | pink | peach | peach |
| 4 (idx 24–31) | magenta | crimson | magenta | red-orange | peach | gold | tan | yellow-green |
| 3 (idx 16–23) | cyan | blue | blue | indigo | blue | purple | purple | magenta |
| 2 (idx 8–15) | orange | yellow | yellow-green | green | yellow | mint | teal | teal |
| 1 (idx 0–7) | **off/black** | pale pink | red | orange | red-orange | peach | dark orange | tan |

### Page 2 — indices 64–127 (saturated range)

| Row\Col | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| 8 (idx 120–127) | white | white | white | white | white | blue | green | red |
| 7 (idx 112–119) | purple/magenta | crimson | crimson | pink | pink | dark navy (~off) | white | white |
| 6 (idx 104–111) | blue | blue | blue | purple | purple | pink/magenta | purple | pink/magenta |
| 5 (idx 96–103) | cyan | blue | blue | blue | blue | blue | blue | blue |
| 4 (idx 88–95) | lime | mint green | mint green | teal | teal | teal | teal | blue |
| 3 (idx 80–87) | amber | yellow-green | yellow-green | green | green | bright green | dark green | medium green |
| 2 (idx 72–79) | rust | salmon | salmon | orange-red | dark brown-orange | cream | cream | gold-tan |
| 1 (idx 64–71) | pale lavender-white | pink | pink | red | red | orange | orange | red-orange |

## Resolution (2026-09-08)

Hardware owner confirmed the camera skews slightly pink, which explains the `gray`(1),
`purple`(48), and `teal`(50) mismatches — left unchanged. `purple`/`teal` also sit in
the pale rows 7-8 (idx 48-63), which aren't in active use right now anyway.

The other four flagged mismatches weren't camera-bias-shaped (tan/orange/yellow/blue
aren't pink-adjacent) and sit in the actively-used rows 1-4, so `pusher-script.js` was
updated to point them at photo-verified indices instead:

| Constant | Old index | New index | New color (photo-verified) |
|---|---|---|---|
| `C.orange` | 7 (read as tan) | **69** | orange (page 2, row 1, col 6) |
| `C.yellow` / `DJ.syncOn` | 8 (read as orange) | **9** | yellow (page 1, row 2, col 2) |
| `C.darkgreen` | 12 (read as yellow) | **86** | dark green (page 2, row 3, col 7) |
| `C.lime` | 18 (read as blue) | **88** | lime (page 2, row 4, col 1) |

`DJ.syncOn` now references `PUSH2T.C.yellow` directly instead of duplicating the index,
so the two stay in sync automatically going forward.

Still open / deferred:
- Hotcue slot colors (1-6 = indices 21,22,23,13,14,15) read as only 4 distinct hues
  (purple, purple, magenta, mint, teal, teal) rather than 6 — not fixed, just noted.
- `gray`/`purple`/`teal` weren't re-verified on hardware directly (camera-bias
  explanation accepted as-is) — worth a real glance next time the unit's out.

Also confirmed on hardware: **Shift, Delete, Load x6, and Gain Reset x2 CC buttons are
on/off-with-dimming only — no color variation, monochrome white LEDs.** Only Record
(CC86) and Play/Browse (CC85) are real RGB, sharing the pad palette. No "color mapping"
work is needed for the monochrome buttons beyond brightness levels.

## Round 2 (2026-09-08): Pioneer CDJ/DJM-style redesign

A photo of the live "pusher" mapping in action (device rotated 90°, not the color test
tool) showed the scheme looked messy overall. Rebuilt the DJ-facing colors around
Pioneer CDJ/DJM convention instead of ad hoc picks:

- **Cue = orange** (already was — kept, it's the one color everyone agreed looked right).
- **Sync = blue** (`C.blue` = 125), moved off `C.yellow` so it doesn't double up with
  keylock's color — each accent now means exactly one thing.
- **Hot cues 1–6 = fixed rainbow** — red, orange, yellow, green, blue, purple
  (`DJ.hc` now references the named `C.*` constants directly instead of separate
  literal indices), matching rekordbox's default multi-color hot cue palette. Replaces
  the old scheme's near-duplicate pairs (purple/purple, teal/teal).
- **`C.purple` re-pointed 48 → 107** — the old value sat in the pale/deprioritized row
  48-63 (photographs as washed lavender); 107 is in the saturated page-2 range,
  confirmed alongside the same row as the already-verified blue/purple/pink neighbors.
- **Browse button (CC85)**: bright white when idle/library-closed (`C.white` = 122,
  was dim gray = 1), green when library is open (`C.green`, was raw index 10). Record
  (CC86) left untouched — already correct (white idle / red recording).

`DJ.noteGreen`/`noteRed` also switched from separate literal `126`/`127` to direct
`C.green`/`C.red` references, so there's one source of truth for those two.
