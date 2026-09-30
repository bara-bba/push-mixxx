// ─────────────────────────────────────────────────────────────────────────────
//  pusher-script.js  –  Ableton Push 2 / Mixxx  (functionprefix: PUSH2T)
//  Companion to: pusher.midi.xml
//
//  MIDI convention: Traktor C-1=0  →  C2=36=0x24  (Push 2 bottom-left pad)
//  0x90 = Note On Ch1 (pads, static LED)
//  0xB0 = CC Ch1 (encoders & buttons)
//
//  All state indicators use static color changes only (no blinking/heartbeat
//  animation) — simpler and less confusing to read at a glance.
//
//  LAYOUT  col→  1      2      3    [4=VU]  5      6      7   [8=VU]
//  row↓
//   8    G#6   A6    A#6   [B6]   C7    C#7    D7   [D#7]
//        BL÷   BEAT  BL×   VUA   BL÷   BEAT   BL×   VUB
//   7    C6   C#6    D6   [D#6]   E6    F6    F#6   [G6]
//        L-IN BGRID L-OUT  VUA  L-IN  BGRID  L-OUT   VUB
//   6    E5    F5   F#5   [G5]   G#5   A5    A#5   [B5]
//        ---   ---   ---   VUA   ---   ---    ---    VUB
//   5    G#4   A4   A#4   [B4]   C5   C#5    D5   [D#5]
//        HC1   HC2  HC3    VUA   HC1   HC2   HC3    VUB
//   4    C4   C#4    D4   [D#4]   E4    F4   F#4   [G4]
//        HC4   HC5  HC6    VUA   HC4   HC5   HC6    VUB
//   3    E3    F3   F#3   [G3]   G#3   A3   A#3   [B3]
//        ---   ---   ---   VUA   ---   ---   ---    VUB
//   2    G#2   A2   A#2   [B2]   C3   C#3    D3   [D#3]
//        SLP  KEY   QNT   VUA   SLP  KEY    QNT    VUB
//   1    C2   C#2    D2   [D#2]   E2    F2   F#2   [G2]
//        PLY  CUP   SYN   VUA   PLY  CUP   SYN    VUB
// ─────────────────────────────────────────────────────────────────────────────

var PUSH2T = {};

// ─── MIDI STATUS BYTES ────────────────────────────────────────────────────────
PUSH2T.PAD_STATIC  = 0x90;   // Note On Ch1   → static pad color
PUSH2T.BTN_STATIC  = 0xB0;   // CC Ch1        → button static (not used for LEDs here)

// ─── PUSH 2 COLOR PALETTE (6-bit index) ──────────────────────────────────────
// Verified 2026-09-08 against photos of the full palette (docs/color-palette.md).
// orange/yellow/darkgreen/lime/purple were re-pointed to photo-verified indices
// in the correct color family (purple moved off the pale row 48-63 range onto a
// saturated one so it reads as a real rainbow-hotcue color, not pale lavender);
// gray/teal were left alone (photo mismatch there traced to camera pink-bias
// and/or the currently-unused pale rows — see docs/color-palette.md).
PUSH2T.C = {
    off        : 0,
    gray       : 1,    // reads as pale PINK on hardware, not neutral gray — do
                        // not use this for "inactive"; see `paleWhite` below.
    red        : 127,  // photo-verified red    (colortest shift D#7)
    orange     : 69,   // photo-verified orange  (colortest shift F2)
    yellow     : 9,    // photo-verified yellow  (colortest A2)
    lime       : 88,   // photo-verified lime    (colortest shift C4)
    green      : 126,  // photo-verified green   (colortest shift D7)
    darkgreen  : 86,   // photo-verified dark green (colortest shift A#3)
    teal       : 92,   // saturated teal (page 2, row 4, col 5); old 50 was pale lavender
    blue       : 125,  // photo-verified blue    (colortest shift C#7)
    purple     : 107,  // photo-verified purple  (colortest shift G5)
    white      : 122,  // photo-verified white   (colortest shift A#6)
    paleWhite  : 121,  // CANDIDATE pale white (118-124 ramp); 119 and 120 read bluish
                        // brightness ramp seen in the colortest photos — not
                        // independently verified on hardware yet (see
                        // docs/color-palette.md); adjust if this reads wrong.
    paleBlue   : 99,   // mid blue (page 2, row 5, col 4) — sync idle, distinct from active 125
    paleGreen  : 86,   // dark green (page 2, row 3, col 7) — play idle, same hue family as active
    pink       : 57
};

// ─── DJ CONFIG COLORS — Traktor-style scheme ──────────────────────────────────
// Cue = orange (dim while just "set", brighter while actively held), sync =
// pale blue idle / blue active — Traktor hardware (Kontrol S/D series) uses
// the same orange/blue convention. Hot cues 1-6 = the first six swatches of
// Traktor's own 8-color hotcue picker (red, orange, yellow, green, mint,
// blue, purple, pink), in order. `C.teal` stands in for "mint".
PUSH2T.DJ = {
    noteGreen  : PUSH2T.C.green,
    noteRed    : PUSH2T.C.red,
    // Row 2 (Slip / Keylock / Quantize) active colors: three tints of purple
    row2       : [21, 111, 48],   // slip 108 was too dim; 21 = page-1 purple (paler = brighter)
    cue        : 3,                // cue set, idle — dim orange (colortest D#2)
    cuePressed : PUSH2T.C.orange,  // CUP actively held — brighter orange
    syncOn     : PUSH2T.C.blue,    // sync active
    syncOff    : PUSH2T.C.paleBlue, // sync not active — pale/light blue
    hc         : [PUSH2T.C.red, PUSH2T.C.orange, PUSH2T.C.yellow,
                  PUSH2T.C.green, PUSH2T.C.teal, PUSH2T.C.blue]  // Cue 1..6
};

// ─── PER-DECK IDENTITY COLOR — Traktor's classic Deck A/B color coding ────────
// Traktor has colored Deck A blue and Deck B red since its multi-deck color
// coding was introduced, independent of any state. We reuse that here for
// indicators that are otherwise just "on/off" for a given deck (play state,
// loop-active, and the VU meter's normal range) so a glance at color alone
// tells you which deck you're looking at, not just its play state.
PUSH2T.DECK = {
    A: PUSH2T.C.blue,
    B: PUSH2T.C.red
};

// ─── BROWSE BUTTON (CC85) COLORS ──────────────────────────────────────────────
// CC85 is Push 2's Play button (RGB). Change these to recolor the browse
// button. Use any value from PUSH2T.C above (e.g. PUSH2T.C.blue), or a raw
// 0-127 Push 2 palette index.
PUSH2T.BROWSE_COLOR_OPEN   = PUSH2T.C.green;   // library maximized -> bright green
PUSH2T.BROWSE_COLOR_CLOSED = PUSH2T.C.white;   // library normal    -> bright white

// ─── PAD NOTE ADDRESSES (0x90 status) ────────────────────────────────────────
PUSH2T.PAD = {
    // Row 1
    playA : 0x24,  cueA  : 0x26,  syncA : 0x25,  // col 1-3 Deck A (cue/sync swapped)
    playB : 0x28,  cueB  : 0x2A,  syncB : 0x29,  // col 5-7 Deck B (cue/sync swapped)
    // Row 2
    slipA : 0x2C,  keyA  : 0x2D,  qntA  : 0x2E,  // col 1-3 Deck A
    slipB : 0x30,  keyB  : 0x31,  qntB  : 0x32,  // col 5-7 Deck B
    // Row 3 – all pads empty (SHIFT/DELETE are now CC buttons, see CC_BTN).
    // Row 4
    hc4A  : 0x3C,  hc5A  : 0x3D,  hc6A  : 0x3E,  // col 1-3 Deck A
    hc4B  : 0x40,  hc5B  : 0x41,  hc6B  : 0x42,  // col 5-7 Deck B
    // Row 5  (G#4 used for HC1-A; G4=0x43 is VU-B, avoided)
    hc1A  : 0x44,  hc2A  : 0x45,  hc3A  : 0x46,  // col 1-3 Deck A
    hc1B  : 0x48,  hc2B  : 0x49,  hc3B  : 0x4A,  // col 5-7 Deck B
    // Row 6 – Loop In / Loop Out  (F5=0x4D and A5=0x51 stay empty)
    linA  : 0x4C,  loutA : 0x4E,                  // E5, F#5  Deck A
    linB  : 0x50,  loutB : 0x52,                  // G#5, A#5 Deck B
    // Row 7 – Beatjump Back / Beatgrid / Beatjump Forward
    bjbA  : 0x54,  bgrA  : 0x55,  bjfA  : 0x56,  // C6, C#6, D6  Deck A
    bjbB  : 0x58,  bgrB  : 0x59,  bjfB  : 0x5A,  // E6, F6,  F#6 Deck B
    // Row 8
    bldA  : 0x5C,  blsA  : 0x5D,  bluA  : 0x5E,  // col 1-3 Deck A
    bldB  : 0x60,  blsB  : 0x61,  bluB  : 0x62   // col 5-7 Deck B
};

// ─── VU METER COLUMNS ────────────────────────────────────────────────────────
// col 4: D#2(0x27) B2(0x2F) G3(0x37) D#4(0x3F) B4(0x47) G5(0x4F) D#6(0x57) B6(0x5F)
PUSH2T.VU_A = [0x27, 0x2F, 0x37, 0x3F, 0x47, 0x4F, 0x57, 0x5F];
// col 8: G2(0x2B) D#3(0x33) B3(0x3B) G4(0x43) D#5(0x4B) B5(0x53) G6(0x5B) D#7(0x63)
PUSH2T.VU_B = [0x2B, 0x33, 0x3B, 0x43, 0x4B, 0x53, 0x5B, 0x63];

// ─── CC BUTTON NUMBERS (status 0xB0, LED set by sending CC back) ──────────────
PUSH2T.CC_BTN = {
    shift  : 0x31,   // CC49  – SHIFT modifier
    del    : 0x76,   // CC118 – DELETE modifier
    record : 0x56    // CC86  – Record toggle
};

// ─── ENCODER SENSITIVITY ─────────────────────────────────────────────────────
PUSH2T.GAIN_STEP = 0.025;
PUSH2T.RATE_STEP = 0.004;
PUSH2T.VOL_STEP  = 0.015;

// ─── SHIFT STATE ─────────────────────────────────────────────────────────────
PUSH2T.shiftActive = false;

// ─── DELETE STATE ────────────────────────────────────────────────────────────
PUSH2T.deleteActive = false;

// Max sidebar-navigation steps per encoder message while SHIFT is held,
// to avoid runaway scrolling on a fast spin.
PUSH2T.SHIFT_NAV_MAX_STEPS = 8;

// ─── BEATLOOP STATE (per deck, persistent across calls) ──────────────────────
// Valid sizes: 2^n for n = -2..6  →  0.25, 0.5, 1, 2, 4, 8, 16, 32, 64
PUSH2T.BL_SIZES = [0.25, 0.5, 1, 2, 4, 8, 16, 32, 64];
PUSH2T.blIdxA   = 3;   // default index → 2 beats
PUSH2T.blIdxB   = 3;

// ─── COLOR SLOTS (every pad / LED button has an ON and an OFF color) ─────────
// Key 'P<note>' = pad (Note On 0x90), 'C<cc>' = CC button (0xB0). Values are
// Push 2 palette indices (for the white-only CC buttons: brightness 0-127).
// SELECT (CC48) toggles COLOR-EDIT MODE (see bottom of file): press a pad/
// button, turn the tempo encoder (CC14) to change its color. Hold SHIFT to
// show/edit the OFF ("not used") colors instead of the ON colors.
// Edited values are printed to the Mixxx log as "[PUSH2T] COLORS ..." so they
// can be baked into PUSH2T.SAVED below (scripts can't write files).
PUSH2T.SAVED = {"P36":{"on":126,"off":86},"P38":{"on":3,"off":121},"P37":{"on":125,"off":99},"P44":{"on":10,"off":121},"P45":{"on":11,"off":121},"P46":{"on":32,"off":121},"P68":{"on":11,"off":0},"P69":{"on":32,"off":0},"P70":{"on":89,"off":0},"P60":{"on":89,"off":0},"P61":{"on":13,"off":0},"P62":{"on":11,"off":0},"P76":{"on":120,"off":121},"P78":{"on":120,"off":121},"P93":{"on":122,"off":121},"P85":{"on":122,"off":121},"P92":{"on":89,"off":0},"P94":{"on":11,"off":0},"P84":{"on":92,"off":0},"P86":{"on":69,"off":0},"P39":{"on":10,"off":0},"P47":{"on":10,"off":0},"P55":{"on":10,"off":0},"P63":{"on":10,"off":0},"P71":{"on":10,"off":0},"P79":{"on":8,"off":0},"P87":{"on":3,"off":0},"P95":{"on":2,"off":0},"P40":{"on":126,"off":86},"P42":{"on":3,"off":121},"P41":{"on":125,"off":99},"P48":{"on":24,"off":121},"P49":{"on":23,"off":121},"P50":{"on":22,"off":121},"P72":{"on":107,"off":0},"P73":{"on":21,"off":0},"P74":{"on":22,"off":0},"P64":{"on":23,"off":0},"P65":{"on":35,"off":0},"P66":{"on":115,"off":0},"P80":{"on":120,"off":121},"P82":{"on":120,"off":121},"P97":{"on":122,"off":121},"P89":{"on":122,"off":121},"P96":{"on":115,"off":0},"P98":{"on":109,"off":0},"P88":{"on":92,"off":0},"P90":{"on":69,"off":0},"P43":{"on":10,"off":0},"P51":{"on":10,"off":0},"P59":{"on":10,"off":0},"P67":{"on":10,"off":0},"P75":{"on":10,"off":0},"P83":{"on":8,"off":0},"P91":{"on":3,"off":0},"P99":{"on":2,"off":0},"C85":{"on":126,"off":122},"C86":{"on":127,"off":122},"C118":{"on":127,"off":64},"C20":{"on":64,"off":1},"C21":{"on":13,"off":0},"C22":{"on":12,"off":0},"C24":{"on":64,"off":1},"C25":{"on":115,"off":0},"C26":{"on":107,"off":0},"C105":{"on":64,"off":1},"C109":{"on":64,"off":1}};   // baked from log 

PUSH2T.slots = {};
PUSH2T.colorMode = false;
PUSH2T.selSlot = null;      // currently selected slot key in color mode
PUSH2T.dupSource = null;    // {value} copied by the Duplicate button, or null
PUSH2T.dupArmed = false;    // Duplicate active: next pad = source, then pads = destinations
PUSH2T.selState = 'on';

PUSH2T.buildSlots = function () {
    var P = PUSH2T.PAD, C = PUSH2T.C, DJ = PUSH2T.DJ;
    function def(key, on, off) {
        PUSH2T.slots[key] = { on: on, off: (off === undefined ? C.off : off) };
    }
    ['A', 'B'].forEach(function (s) {
        def('P' + P['play' + s], C.green,  C.paleGreen);
        def('P' + P['cue' + s],  DJ.cue,   C.paleWhite);
        def('P' + P['sync' + s], DJ.syncOn, DJ.syncOff);
        def('P' + P['slip' + s], DJ.row2[0], C.paleWhite);
        def('P' + P['key' + s],  DJ.row2[1], C.paleWhite);
        def('P' + P['qnt' + s],  DJ.row2[2], C.paleWhite);
        for (var n = 1; n <= 6; n++) { def('P' + P['hc' + n + s], DJ.hc[n - 1], C.off); }
        def('P' + P['lin' + s],  PUSH2T.DECK[s], C.paleWhite);
        def('P' + P['lout' + s], PUSH2T.DECK[s], C.paleWhite);
        def('P' + P['bls' + s],  C.lime, C.paleWhite);
        def('P' + P['bgr' + s],  C.orange, C.paleWhite);   // ON only while SHIFT held
        def('P' + P['bld' + s],  C.red, C.off);
        def('P' + P['blu' + s],  C.red, C.off);
        def('P' + P['bjb' + s],  C.teal, C.off);
        def('P' + P['bjf' + s],  C.orange, C.off);
        var vu = PUSH2T.vuColorsFor(s), cols = (s === 'A') ? PUSH2T.VU_A : PUSH2T.VU_B;
        for (var i = 0; i < cols.length; i++) { def('P' + cols[i], vu[i], C.off); }
    });
    // CC buttons: RGB ones (browse 85, record 86) take palette indices; the
    // rest are white-only (value = brightness).
    def('C85', PUSH2T.BROWSE_COLOR_OPEN, PUSH2T.BROWSE_COLOR_CLOSED);
    def('C86', C.red, C.white);        // record: on = recording
    def('C118', 127, 64);              // delete: on = held
    def('C20', 64, 1);  def('C21', 1, 0);  def('C22', 1, 0);   // load / prev / next A
    def('C24', 64, 1);  def('C25', 1, 0);  def('C26', 1, 0);   // load / prev / next B
    def('C110', 127, 32); def('C111', 127, 32); def('C112', 127, 32); def('C113', 127, 32);   // scene buttons
    def('C23', C.orange, C.paleWhite); def('C27', C.orange, C.paleWhite);   // deck-select A / B
    def('C105', 64, 1); def('C109', 64, 1);                    // gain reset A / B
    for (var k in PUSH2T.SAVED) {
        if (PUSH2T.slots[k]) {
            if (PUSH2T.SAVED[k].on  !== undefined) { PUSH2T.slots[k].on  = PUSH2T.SAVED[k].on; }
            if (PUSH2T.SAVED[k].off !== undefined) { PUSH2T.slots[k].off = PUSH2T.SAVED[k].off; }
        }
    }
};

// Color lookup for a pad note / CC number.
PUSH2T.padOn  = function (note) { return PUSH2T.slots['P' + note].on; };
PUSH2T.padOff = function (note) { return PUSH2T.slots['P' + note].off; };

// LED writers used by all normal-mode feedback. Suppressed in color-edit mode
// so live engine updates don't overwrite the color-edit display.
PUSH2T.setPad = function (note, color) {
    if (PUSH2T.colorMode) { return; }
    midi.sendShortMsg(PUSH2T.PAD_STATIC, note, color);
};
PUSH2T.setCC = function (cc, value) {
    if (PUSH2T.colorMode) { return; }
    midi.sendShortMsg(0xB0, cc, value);
};

PUSH2T._rawSlot = function (key, color) {
    midi.sendShortMsg(key.charAt(0) === 'P' ? 0x90 : 0xB0,
                      parseInt(key.slice(1), 10), color);
};

// Draw every slot in its ON (or, with SHIFT held, OFF) color.
PUSH2T.renderColorMode = function () {
    var st = PUSH2T.shiftActive ? 'off' : 'on';
    for (var key in PUSH2T.slots) { PUSH2T._rawSlot(key, PUSH2T.slots[key][st]); }
};

PUSH2T.dumpColors = function () {
    var out = {};
    for (var key in PUSH2T.slots) { out[key] = PUSH2T.slots[key]; }
    print('[PUSH2T] COLORS ' + JSON.stringify(out));
};

// ─── INIT / SHUTDOWN ─────────────────────────────────────────────────────────

PUSH2T.init = function (id, debugging) {
    try {
        PUSH2T.buildSlots();
        PUSH2T.clearAllPads();
        PUSH2T.stripRelease();
        // Force Start-anchored beatloops on both decks (LoopAnchorPoint::Start = 0).
        // Root cause of "loop sets the cursor as the END instead of the START":
        // this isn't a script bug — Mixxx persists a per-deck loop_anchor flag
        // (0 = Start/forward, 1 = End/backward), and mixxx.cfg had it saved as 1
        // for Channel1/Channel2 (likely flipped via the skin's own loop-anchor
        // toggle), while unused Channel3/4 sat at the real default of 0. Forcing
        // it here every init makes beatloop_activate deterministically forward
        // (current position = start) regardless of what the GUI last left it at.
        engine.setValue('[Channel1]', 'loop_anchor', 0);
        engine.setValue('[Channel2]', 'loop_anchor', 0);
        PUSH2T.connectDeck('[Channel1]', 'A');
        PUSH2T.connectDeck('[Channel2]', 'B');
        PUSH2T.connectRecording();
        PUSH2T.drawStaticButtons();
        print('[PUSH2T] Push 2 Pusher mapping initialized.');
    } catch (e) {
        print('[PUSH2T] ERROR during init: ' + e);
    }
};

PUSH2T.shutdown = function () {
    // Release any active scratch so decks don't get stuck
    if (engine.isScratching(1)) { engine.scratchDisable(1); }
    if (engine.isScratching(2)) { engine.scratchDisable(2); }
    PUSH2T.clearAllPads();
    // Clear CC button LEDs (incl. SHIFT 0x31, DELETE 0x76, RECORD 0x56)
    [0x14,0x15,0x16,0x18,0x19,0x1A,0x03,0x09,0x17,0x1B,0x2C,0x6E,0x6F,0x70,0x71,0x2D,0x2E,0x2F,0x30,0x31,0x55,0x56,0x58,0x69,0x6D,0x76].forEach(function(cc) {
        midi.sendShortMsg(0xB0, cc, 0);
    });
    PUSH2T.stripConfig(PUSH2T.STRIP_CFG_HOST);
    PUSH2T.stripLedsSet(-1, false);
    PUSH2T.stripConfig(PUSH2T.STRIP_CFG_PUSH);
    print('[PUSH2T] Push 2 Pusher mapping shut down.');
};

// ─── SAFE CONNECTION HELPER ───────────────────────────────────────────────────
// engine.makeConnection() returns null if the (group, control) pair doesn't
// exist on this Mixxx version/skin. Calling .trigger() on null throws an
// uncaught error, which can abort init() and disable the ENTIRE controller.
// Always go through this helper instead of calling makeConnection directly.
PUSH2T.conns = [];
PUSH2T.safeConnect = function (group, key, callback) {
    var conn = engine.makeConnection(group, key, callback);
    if (conn) {
        PUSH2T.conns.push(conn);
        conn.trigger();
    } else {
        print('[PUSH2T] WARNING: could not connect ' + group + ' ' + key + ' (control not found)');
    }
    return conn;
};

// ─── DECK CONNECTIONS (LED feedback via engine.makeConnection) ────────────────

PUSH2T.connectDeck = function (group, side) {
    var P = PUSH2T.PAD;
    function pd(name) { return P[name + side]; }   // pad note for this deck

    // ── Play indicator (ON = playing, OFF = stopped) ──
    PUSH2T.safeConnect(group, 'play_indicator', function (v) {
        PUSH2T.setPad(pd('play'), v ? PUSH2T.padOn(pd('play')) : PUSH2T.padOff(pd('play')));
    });

    // ── CUP – ON when a cue is set, OFF when not, DJ.cuePressed while held.
    // cue_point = -1 when no cue is set; track_loaded guards empty decks.
    // The held state is tracked separately (see cupA/cupB).
    PUSH2T.safeConnect(group, 'cue_point', function (v) {
        PUSH2T.setPad(pd('cue'), PUSH2T._cueColor(group, side));
    });

    // ── Sync ──
    PUSH2T.safeConnect(group, 'sync_enabled', function (v) {
        PUSH2T.setPad(pd('sync'), v ? PUSH2T.padOn(pd('sync')) : PUSH2T.padOff(pd('sync')));
    });

    // ── Slip mode ──
    PUSH2T.safeConnect(group, 'slip_enabled', function (v) {
        PUSH2T.setPad(pd('slip'), v ? PUSH2T.padOn(pd('slip')) : PUSH2T.padOff(pd('slip')));
    });

    // ── Keylock ──
    PUSH2T.safeConnect(group, 'keylock', function (v) {
        PUSH2T.setPad(pd('key'), v ? PUSH2T.padOn(pd('key')) : PUSH2T.padOff(pd('key')));
    });

    // ── Quantize ──
    PUSH2T.safeConnect(group, 'quantize', function (v) {
        PUSH2T.setPad(pd('qnt'), v ? PUSH2T.padOn(pd('qnt')) : PUSH2T.padOff(pd('qnt')));
    });

    // ── Hotcues 1-6 (ON = cue set, OFF = empty) ──
    for (var n = 1; n <= 6; n++) {
        (function (num) {
            var pad = P['hc' + num + side];
            PUSH2T.safeConnect(group, 'hotcue_' + num + '_enabled', function (v) {
                PUSH2T.setPad(pad, v ? PUSH2T.padOn(pad) : PUSH2T.padOff(pad));
            });
        })(n);
    }

    // ── Loop active → Loop In/Out and loop-size pads (ON = loop active) ──
    PUSH2T.safeConnect(group, 'loop_enabled', function (v) {
        ['lin', 'lout', 'bls'].forEach(function (name) {
            var pad = pd(name);
            PUSH2T.setPad(pad, v ? PUSH2T.padOn(pad) : PUSH2T.padOff(pad));
        });
    });

    // ── VU meter ──
    PUSH2T.safeConnect(group, 'VuMeter', function (v) {
        PUSH2T.drawVu(side, v);
    });

    // Push our default beatloop size into Mixxx so the GUI highlights it
    // from the start, and keep the script's index in sync if the size is
    // changed elsewhere (e.g. clicking a size in the GUI).
    var idxRef = (side === 'A') ? 'blIdxA' : 'blIdxB';
    engine.setValue(group, 'beatloop_size', PUSH2T.BL_SIZES[PUSH2T[idxRef]]);
    PUSH2T.safeConnect(group, 'beatloop_size', function (v) {
        var i = PUSH2T.BL_SIZES.indexOf(v);
        if (i !== -1) { PUSH2T[idxRef] = i; }
    });
};

// ─── VU METER ────────────────────────────────────────────────────────────────

// VU segment colors, bottom (0) to top (7): 5 deck-color, 1 yellow, 1 orange,
// 1 red. The bottom 5 use each deck's Traktor identity color (blue/red)
// instead of a shared green, so the meter reads as "this deck" at a glance;
// the top 3 stay universal yellow/orange/red clip warnings regardless of deck.
PUSH2T.vuColorsFor = function (side) {
    var deckColor = PUSH2T.C.green;   // shared green (deck-colored bottoms looked wrong)
    return [
        deckColor, deckColor, deckColor, deckColor, deckColor,
        PUSH2T.C.yellow,
        PUSH2T.C.orange,
        PUSH2T.C.red
    ];
};

PUSH2T.drawVu = function (side, value) {
    var col = (side === 'A') ? PUSH2T.VU_A : PUSH2T.VU_B;
    var lit = Math.round(value * col.length);
    for (var i = 0; i < col.length; i++) {
        PUSH2T.setPad(col[i], (i < lit) ? PUSH2T.padOn(col[i]) : PUSH2T.padOff(col[i]));
    }
};

// ─── STATIC LIGHTS (action buttons that don't track state) ───────────────────

// Push 2 CC button LED:  midi.sendShortMsg(0xB0, ccNum, value)
//   0 = off  |  1 = dim (quarter)  |  64 = medium  |  127 = full bright

// Always-on pads and idle CC button LEDs. Safe to call repeatedly (used again
// when leaving color-edit mode).
// Beatgrid pads only do anything with SHIFT held, so they sit at their low
// (OFF) color normally and light to their ON color while SHIFT is down.
PUSH2T.drawBeatgrid = function () {
    var P = PUSH2T.PAD;
    ['A', 'B'].forEach(function (s) {
        var pad = P['bgr' + s];
        PUSH2T.setPad(pad, PUSH2T.shiftActive ? PUSH2T.padOn(pad) : PUSH2T.padOff(pad));
    });
};

// ─── DECK SELECT (CC23 = Deck A, CC27 = Deck B; the spare 4th button of each
// Load bank). SHIFT + press selects that deck (orange) and deselects the
// other (exclusive). A press WITHOUT shift on either releases everything.
// Default: none selected. PUSH2T.selectedDeck is 'A', 'B' or null, and
// PUSH2T.selectedGroup() gives '[Channel1]' / '[Channel2]' / null, for
// single-deck functions to build on.
PUSH2T.selectedDeck = null;
PUSH2T.selectedGroup = function () {
    return PUSH2T.selectedDeck === 'A' ? '[Channel1]'
         : PUSH2T.selectedDeck === 'B' ? '[Channel2]' : null;
};
PUSH2T.drawDeckSelect = function () {
    PUSH2T.setCC(0x17, PUSH2T.selectedDeck === 'A' ? PUSH2T.slots['C23'].on : PUSH2T.slots['C23'].off);
    PUSH2T.setCC(0x1B, PUSH2T.selectedDeck === 'B' ? PUSH2T.slots['C27'].on : PUSH2T.slots['C27'].off);
};
PUSH2T._deckSelect = function (side, v) {
    if (v <= 0) { return; }
    PUSH2T.selectedDeck = PUSH2T.shiftActive ? side : null;
    PUSH2T.drawDeckSelect();
    PUSH2T.drawStrip();
    print('[PUSH2T] selected deck: ' + (PUSH2T.selectedDeck || 'none'));
};
PUSH2T.deckSelA = function (c, t, v) { PUSH2T._deckSelect('A', v); };
PUSH2T.deckSelB = function (c, t, v) { PUSH2T._deckSelect('B', v); };

// ─── TAP TEMPO (Push 2 Tap Tempo button, CC3, top-left) ──────────────────────
// Only acts when a deck is selected (see deck select above). Tap in time: the
// deck's BPM is set to the tapped tempo (averaged over the last taps) via the
// deck's `bpm` control, whether or not the deck is playing. A pause longer
// than TAP_RESET_MS starts a new tap sequence.
PUSH2T.TAP_RESET_MS = 2000;
PUSH2T.TAP_MAX_INTERVALS = 8;
PUSH2T._taps = [];

PUSH2T.tapTempo = function (c, t, v) {
    if (v <= 0 || PUSH2T.colorMode) { return; }
    var group = PUSH2T.selectedGroup();
    print('[PUSH2T] tap pressed, selected deck: ' + (PUSH2T.selectedDeck || 'none'));
    if (group === null) { return; }                    // no deck selected
    var now = Date.now();
    var taps = PUSH2T._taps;
    if (taps.length && now - taps[taps.length - 1] > PUSH2T.TAP_RESET_MS) { taps.length = 0; }
    taps.push(now);
    if (taps.length > PUSH2T.TAP_MAX_INTERVALS + 1) { taps.shift(); }
    if (taps.length < 2) { return; }
    var avgMs = (taps[taps.length - 1] - taps[0]) / (taps.length - 1);
    var bpm = 60000 / avgMs;
    engine.setValue(group, 'bpm', bpm);
    print('[PUSH2T] tap tempo (bpm control now ' + engine.getValue(group, 'bpm').toFixed(1) + ') ' + bpm.toFixed(1) + ' BPM -> ' + group);
};

// ─── PITCH STRIP + METRONOME (selected deck only) ────────────────────────────
// METRONOME (CC9): cycles the selected deck's pitch range (`rateRange`).
// TOUCH STRIP: while touched, its absolute position sets the selected deck's
// `rate` across the current range (top = faster, bottom = slower, middle =
// 0%). The strip springs back to center on release; those return messages are
// ignored, so the pitch stays where you left it.
PUSH2T.RATE_RANGES = [0.06, 0.08, 0.10, 0.16, 0.24, 0.50, 0.90];
PUSH2T.stripTouching = false;

PUSH2T.metronomeBtn = function (c, t, v) {
    if (v <= 0 || PUSH2T.colorMode) { return; }
    var group = PUSH2T.selectedGroup();
    if (group === null) { return; }
    var cur = engine.getValue(group, 'rateRange');
    var idx = 0, best = 1e9;
    for (var i = 0; i < PUSH2T.RATE_RANGES.length; i++) {     // nearest current
        var d = Math.abs(PUSH2T.RATE_RANGES[i] - cur);
        if (d < best) { best = d; idx = i; }
    }
    var next = PUSH2T.RATE_RANGES[(idx + 1) % PUSH2T.RATE_RANGES.length];
    engine.setValue(group, 'rateRange', next);
    print('[PUSH2T] pitch range ' + group + ' = +/-' + Math.round(next * 100) + '%');
};

PUSH2T.stripTouch = function (c, t, v, status) {
    PUSH2T.stripTouching = ((status & 0xF0) === 0x90) && v > 0;
    print('[PUSH2T] strip touch ' + (PUSH2T.stripTouching ? 'on' : 'off'));
};

PUSH2T.stripPitch = function (c, t, v, status) {
    if ((status & 0xF0) === 0xB0) {     // mod-wheel CC1 (0-127) -> pitch-bend scale
        v = (v === 64) ? 8192 : Math.round(v / 127 * 16383);
        t = v & 0x7F; v = v >> 7;
    }
    print('[PUSH2T] strip raw t=' + t + ' v=' + v + ' touching=' + PUSH2T.stripTouching);
    if (PUSH2T.colorMode || !PUSH2T.stripTouching) { return; }
    // Browse scene: strip position = position in the preview song.
    if (PUSH2T.inLibraryMode()) {
        var w14 = (v > 127) ? v : ((v << 7) | (t & 0x7F));
        if (w14 === 8192) { return; }                        // spring-back on release
        if (engine.getValue('[PreviewDeck1]', 'track_loaded')) {
            engine.setValue('[PreviewDeck1]', 'playposition', Math.max(0, Math.min(1, w14 / 16383)));
        }
        return;
    }
    var group = PUSH2T.selectedGroup();
    if (group === null) { return; }
    // Pitch bend arrives as (LSB, MSB); some Mixxx paths pass it pre-combined.
    var v14 = (v > 127) ? v : ((v << 7) | (t & 0x7F));
    // The strip springs back to exactly center (8192) on release, and that
    // message can arrive before the touch-off note. Ignore exact center so the
    // pitch stays where you left it (cost: you can't pick exactly 0% by hand).
    if (v14 === 8192) { return; }
    print('[PUSH2T] strip ' + v14);
    var pos = (v14 - 8192) / 8192;               // -1 .. +1
    engine.setValue(group, 'rate', Math.max(-1, Math.min(1, pos)));
};

// ─── SCENES (Device CC110, Browse CC111, Mix CC112, Clip CC113) ──────────────
// A scene decides what the top-row buttons (CC102-109) and the touch strip do.
//   Browse scene = library mode (library maximized): top row = preview play/
//     pause + sort buttons, strip = quick-seek the preview song. Toggled by
//     the Browse scene button OR the Play/browse button (CC85), same action.
//   Device / Mix / Clip: not defined yet (buttons reserved, LEDs dim).
//   No scene (default): top row = normal functions, strip = pitch of the
//     selected deck.
PUSH2T.sceneBrowse = function (c, t, v) { PUSH2T.toggleBrowser(c, t, v); };
// Device / Mix / Clip: reserved. Pressing one enters it (leaving Browse); pressing
// it again returns to no scene.
PUSH2T._sceneToggle = function (name, v) {
    if (v > 0) { PUSH2T.setScene(PUSH2T.scene === name ? 'device' : name); }
};
PUSH2T.sceneDevice = function (c, t, v) { PUSH2T._sceneToggle('device', v); };
PUSH2T.sceneMix    = function (c, t, v) { PUSH2T._sceneToggle('mix', v); };
PUSH2T.sceneClip   = function (c, t, v) { PUSH2T._sceneToggle('clip', v); };

// Entering the Browse scene: put keyboard focus on the track table and make
// sure a row is selected, so Up/Down and the browse encoder work right away.
// (Delayed a moment so the maximized-library layout exists first.)
// focused_widget: 0 none, 1 search bar, 2 sidebar, 3 track table.
// Down-then-Up leaves the selection unchanged if a row was already selected,
// and selects the first row if there was none.
PUSH2T.focusTrackTable = function () {
    engine.beginTimer(250, function () {
        var lib = '[Library]';
        var before = engine.getValue(lib, 'focused_widget');
        engine.setValue(lib, 'focused_widget', 3);
        var after = engine.getValue(lib, 'focused_widget');
        print('[PUSH2T] focus: focused_widget ' + before + ' -> ' + after);
        if (after !== 3) {
            // Setting it had no effect on this Mixxx: step focus forward instead.
            for (var n = 0; n < PUSH2T.LIBRARY_FOCUS_STEPS; n++) {
                engine.setValue(lib, 'MoveFocusForward', 1);
            }
        }
        engine.beginTimer(120, function () {
            engine.setValue(lib, 'MoveVertical', 1);
            engine.setValue(lib, 'MoveVertical', -1);
            print('[PUSH2T] focus: cursor placed, focused_widget = ' + engine.getValue(lib, 'focused_widget'));
        }, true);
    }, true);
};

// ─── TOUCH STRIP LEDs (Browse scene: preview song cursor) ────────────────────
// Push 2 SysEx: 0x17 = touch strip configuration flags, 0x19 = 31 LED
// brightnesses (0-7, two per byte). Flags used: bit0 host controls LEDs, bit1
// host sends via SysEx, bit2 pitch-bend mode, bit5+6 auto-return to center
// (same behavior as the default). With bit0 = 0 the strip goes back to Push's
// own LED display.
PUSH2T.STRIP_LEDS = 31;
PUSH2T.STRIP_CFG_HOST  = 0x67;
PUSH2T.STRIP_CFG_PUSH  = 0x64;
PUSH2T._stripLed = -1;

// Mixxx's API is midi.sendSysexMsg(byteArray, length) (there is no sendSysEx).
PUSH2T._sendSysex = function (bytes) {
    try { midi.sendSysexMsg(bytes, bytes.length); }
    catch (e) { print('[PUSH2T] sysex failed: ' + e); }
};

PUSH2T._sysexHead = [0xF0, 0x00, 0x21, 0x1D, 0x01, 0x01];
PUSH2T.stripConfig = function (flags) {
    PUSH2T._sendSysex(PUSH2T._sysexHead.concat([0x17, flags, 0xF7]));
};
// litIndex -1 = all off. bar = true: dim fill up to the cursor; false: one dot.
PUSH2T.stripLedsSet = function (litIndex, bar) {
    var data = [];
    function lvl(k) {
        if (litIndex < 0) { return 0; }
        if (k === litIndex) { return 7; }
        return (bar && k < litIndex) ? 2 : 0;
    }
    for (var i = 0; i < PUSH2T.STRIP_LEDS; i += 2) {
        data.push(lvl(i) | (lvl(i + 1) << 4));
    }
    PUSH2T._sendSysex(PUSH2T._sysexHead.concat([0x19], data, [0xF7]));
};

// The strip's LEDs are ALWAYS host-drawn (Push's own display showed unwanted
// extra dots): Browse = bar following the preview song, everything else = a
// single dot at the selected deck's pitch (center when no deck is selected).
PUSH2T._stripKey = null;
PUSH2T.drawStrip = function () {
    var idx, bar, key;
    if (PUSH2T.inLibraryMode()) {
        if (!engine.getValue('[PreviewDeck1]', 'track_loaded')) { idx = -1; }
        else { idx = Math.round(engine.getValue('[PreviewDeck1]', 'playposition') * (PUSH2T.STRIP_LEDS - 1)); }
        bar = true;
    } else {
        var g = PUSH2T.selectedGroup();
        var pos = (g === null) ? 0 : engine.getValue(g, 'rate');   // -1..1, 0 = center
        idx = Math.round((pos + 1) / 2 * (PUSH2T.STRIP_LEDS - 1));
        bar = false;
    }
    if (idx >= 0) { idx = Math.max(0, Math.min(PUSH2T.STRIP_LEDS - 1, idx)); }
    key = idx + (bar ? 'b' : 'd');
    if (key === PUSH2T._stripKey) { return; }
    PUSH2T._stripKey = key;
    PUSH2T.stripLedsSet(idx, bar);
};
PUSH2T.drawStripCursor = PUSH2T.drawStrip;      // (old name still used below)

// Take over the strip LEDs and redraw for the current scene.
PUSH2T.stripRelease = function () {
    PUSH2T.stripConfig(PUSH2T.STRIP_CFG_HOST);
    PUSH2T._stripKey = null;
    PUSH2T.drawStrip();
};

// ─── LOWER ROW: Prev / Next buttons are FX1 / FX2 for that channel (all scenes) ──
// In every scene the Prev (CC21 / CC25) and Next (CC22 / CC26) buttons toggle
// effect unit 1 / 2 on the deck's channel. Idle keeps the color you set in the
// color editor (slot ON value); an active effect shows FX_ON_COLOR.
PUSH2T.FX_ON_COLOR = PUSH2T.C.orange;
PUSH2T.FX_BUTTONS = {
    0x15: { ch: '[Channel1]', unit: 1 },   // Deck A Prev -> FX1
    0x16: { ch: '[Channel1]', unit: 2 },   // Deck A Next -> FX2
    0x19: { ch: '[Channel2]', unit: 1 },   // Deck B Prev -> FX1
    0x1A: { ch: '[Channel2]', unit: 2 }    // Deck B Next -> FX2
};
PUSH2T._fxGroup = function (b) { return '[EffectRack1_EffectUnit' + b.unit + ']'; };
PUSH2T._fxKey   = function (b) { return 'group_' + b.ch + '_enable'; };

PUSH2T.fxToggle = function (cc) {
    var b = PUSH2T.FX_BUTTONS[cc];
    var cur = engine.getValue(PUSH2T._fxGroup(b), PUSH2T._fxKey(b));
    engine.setValue(PUSH2T._fxGroup(b), PUSH2T._fxKey(b), cur ? 0 : 1);
};

PUSH2T.drawLoadNav = function () {
    [0x15, 0x16, 0x19, 0x1A].forEach(function (cc) {
        var color = PUSH2T.slots['C' + cc].on;
        var b = PUSH2T.FX_BUTTONS[cc];
        if (engine.getValue(PUSH2T._fxGroup(b), PUSH2T._fxKey(b))) { color = PUSH2T.FX_ON_COLOR; }
        PUSH2T.setCC(cc, color);
    });
};

PUSH2T.drawScenes = function () {
    PUSH2T.drawLoadNav();
    var map = [[0x6E, 'C110', 'device'], [0x6F, 'C111', 'browse'],
               [0x70, 'C112', 'mix'],    [0x71, 'C113', 'clip']];
    map.forEach(function (m) {
        PUSH2T.setCC(m[0], PUSH2T.scene === m[2] ? PUSH2T.slots[m[1]].on : PUSH2T.slots[m[1]].off);
    });
};

PUSH2T.drawStaticColors = function () {
    var P = PUSH2T.PAD;
    // SHIFT has no color slot: dim white idle (64), full (127) when held.
    PUSH2T.setCC(PUSH2T.CC_BTN.shift, 64);
    PUSH2T.setCC(0x30, 64);                                   // SELECT idle
    PUSH2T.setCC(PUSH2T.CC_BTN.del, PUSH2T.slots['C118'].off);
    PUSH2T.setCC(PUSH2T.CC_BTN.record, PUSH2T.slots['C86'].off);
    ['A', 'B'].forEach(function (s) {
        ['bld', 'blu', 'bjb', 'bjf'].forEach(function (name) {
            PUSH2T.setPad(P[name + s], PUSH2T.padOn(P[name + s]));
        });
        PUSH2T.drawBeatgrid();

    });
    // Arrow buttons (browser navigation) – dim idle level
    [0x2C, 0x2D, 0x2E, 0x2F].forEach(function (cc) { PUSH2T.setCC(cc, 64); });
    PUSH2T.drawScenes();
    PUSH2T.setCC(0x03, 64);
    PUSH2T.setCC(0x09, 64);                                   // METRONOME idle                                   // TAP TEMPO idle
    PUSH2T.drawDeckSelect();
    // Load / prev / next (static, always mapped)
    [0x14, 0x18].forEach(function (cc) {
        PUSH2T.setCC(cc, PUSH2T.slots['C' + cc].on);
    });
    PUSH2T.drawLoadNav();
};

// Gain Reset button color from the deck's pregain (1.0 = 0 dB): white at unity,
// greener the further BELOW 0 dB, redder the further ABOVE. (If these buttons
// turn out to be white-only LEDs on your unit this just shows as brightness.)
PUSH2T.GAIN_RAMP = [    // palette indices, dark green -> green -> yellow -> orange -> red
    86, 87, 85, 84, 82, 81, 9, 79, 69, 75, 68, 127
];
PUSH2T.GAIN_DB_MIN = -12;   // dB mapped to the first ramp entry
PUSH2T.GAIN_DB_MAX = 12;    // dB mapped to the last ramp entry
PUSH2T.GAIN_UNITY_DB = 0.15;    // within this of 0 dB the button shows white
PUSH2T.gainColor = function (gain) {
    var db = (gain > 0.0001) ? 20 * Math.log(gain) / Math.LN10 : PUSH2T.GAIN_DB_MIN;
    if (Math.abs(db) < PUSH2T.GAIN_UNITY_DB) { return PUSH2T.C.white; }
    var t = (db - PUSH2T.GAIN_DB_MIN) / (PUSH2T.GAIN_DB_MAX - PUSH2T.GAIN_DB_MIN);
    t = Math.max(0, Math.min(1, t));
    return PUSH2T.GAIN_RAMP[Math.round(t * (PUSH2T.GAIN_RAMP.length - 1))];
};

// Top row LEDs: library mode -> all 8 sort buttons lit; otherwise the Gain
// Reset ones show gain color and the rest are off.
// ─── CLIP SCENE: 8 encoders + 8 buttons = 2 effect units ────────────────────
// Encoders CC71-74 / buttons CC102-105 = FX unit 1; encoders CC75-78 / buttons
// CC106-109 = FX unit 2. Per unit: knobs 1-3 = the 3 effects' knob (`meta`),
// buttons 1-3 = those effects' on/off; knob 4 = unit master (`mix`); button 4
// resets the 3 effect knobs to their default (like double-clicking them).
// (In this scene the jog/gain encoders CC71/74/75/78 are re-used for FX.)
PUSH2T.FX_KNOB_STEP = 0.01;      // per encoder tick
PUSH2T.FX_KNOB_DEFAULT = 0;      // value the reset button restores
PUSH2T._fxUnitGroup = function (u) { return '[EffectRack1_EffectUnit' + u + ']'; };
PUSH2T._fxEffGroup  = function (u, n) { return '[EffectRack1_EffectUnit' + u + '_Effect' + n + ']'; };

PUSH2T.fxEncoder = function (cc, v) {
    var u = (cc < 75) ? 1 : 2, idx = cc - (71 + (u - 1) * 4);
    var d = PUSH2T._decodeRelative(v) * PUSH2T.FX_KNOB_STEP;
    if (d === 0) { return; }
    // idx 3 (4th knob) = the unit's Super Knob (super1): moves all 3 effects'
    // own metaknobs together, NOT the dry/wet mix (which sounds like a plain
    // volume control on the effect and isn't what 'master' means here).
    var g = (idx < 3) ? PUSH2T._fxEffGroup(u, idx + 1) : PUSH2T._fxUnitGroup(u);
    var key = (idx < 3) ? 'meta' : 'super1';
    engine.setValue(g, key, Math.max(0, Math.min(1, engine.getValue(g, key) + d)));
};

PUSH2T.fxButton = function (cc, v) {
    if (v <= 0) { return; }
    var u = (cc < 106) ? 1 : 2, idx = cc - (102 + (u - 1) * 4);
    if (idx < 3) {
        var g = PUSH2T._fxEffGroup(u, idx + 1);
        engine.setValue(g, 'enabled', engine.getValue(g, 'enabled') ? 0 : 1);
    } else {
        for (var n = 1; n <= 3; n++) {
            engine.setValue(PUSH2T._fxEffGroup(u, n), 'meta', PUSH2T.FX_KNOB_DEFAULT);
        }
        engine.setValue(PUSH2T._fxUnitGroup(u), 'super1', PUSH2T.FX_KNOB_DEFAULT);
    }
};

PUSH2T.drawMixButtons = function () {  // renders the Clip scene's FX layout
    [1, 2].forEach(function (u) {
        for (var idx = 0; idx < 4; idx++) {
            var cc = 102 + (u - 1) * 4 + idx, color;
            if (idx < 3) {
                color = engine.getValue(PUSH2T._fxEffGroup(u, idx + 1), 'enabled')
                    ? PUSH2T.C.green : PUSH2T.C.paleWhite;
            } else { color = PUSH2T.C.white; }          // reset button
            PUSH2T.setCC(cc, color);
        }
    });
};

PUSH2T.drawTopRow = function () {
    if (PUSH2T.scene === 'clip') {
        PUSH2T.drawMixButtons();
    } else if (PUSH2T.inLibraryMode()) {
        [104, 105, 106, 107, 108, 109].forEach(function (cc) {
            PUSH2T.setCC(cc, PUSH2T.C.white);
        });
        PUSH2T.setCC(103, 0);
        PUSH2T.setCC(102, PUSH2T.previewPlaying() ? PUSH2T.C.green : PUSH2T.C.red);
    } else {
        [102, 103, 104, 106, 107, 108].forEach(function (cc) { PUSH2T.setCC(cc, 0); });
        PUSH2T.setCC(0x69, PUSH2T.gainColor(engine.getValue('[Channel1]', 'pregain')));
        PUSH2T.setCC(0x6D, PUSH2T.gainColor(engine.getValue('[Channel2]', 'pregain')));
    }
};

PUSH2T.drawStaticButtons = function () {
    PUSH2T.drawStaticColors();

    // ── Browser toggle CC85 – reflects [Skin] show_maximized_library state ──
    // CC85 is Push 2's Play button (RGB): value = palette index.
    PUSH2T.safeConnect('[Skin]', 'show_maximized_library', function (v) {
        PUSH2T.setCC(0x55, v ? PUSH2T.slots['C85'].on : PUSH2T.slots['C85'].off);
        if (v) { PUSH2T.scene = 'browse'; }
        else if (PUSH2T.scene === 'browse') { PUSH2T.scene = 'device'; }
        PUSH2T.drawTopRow();
        PUSH2T.drawScenes();
        if (v) { PUSH2T.focusTrackTable(); }
        PUSH2T.stripRelease();
    });
    PUSH2T.safeConnect('[PreviewDeck1]', 'playposition', function () { PUSH2T.drawStripCursor(); });
    PUSH2T.safeConnect('[PreviewDeck1]', 'track_loaded', function () { PUSH2T.drawStripCursor(); });
    PUSH2T.safeConnect('[Channel1]', 'rate', function () { PUSH2T.drawStrip(); });
    PUSH2T.safeConnect('[Channel2]', 'rate', function () { PUSH2T.drawStrip(); });

    // ── Preview play state -> CC102 LED (library mode only) ──
    PUSH2T.safeConnect('[PreviewDeck1]', 'play', function (v) {
        if (PUSH2T.inLibraryMode()) {
            PUSH2T.setCC(102, v ? PUSH2T.C.green : PUSH2T.C.red);
        }
    });

    // ── Effect on/off -> Mix scene button LEDs ──
    [1, 2].forEach(function (u) {
        for (var n = 1; n <= 3; n++) {
            PUSH2T.safeConnect(PUSH2T._fxEffGroup(u, n), 'enabled', function () {
                if (PUSH2T.scene === 'clip') { PUSH2T.drawTopRow(); }
            });
        }
    });

    // ── FX unit enable per channel -> Prev/Next button LEDs (Mix scene) ──
    [0x15, 0x16, 0x19, 0x1A].forEach(function (cc) {
        var b = PUSH2T.FX_BUTTONS[cc];
        PUSH2T.safeConnect(PUSH2T._fxGroup(b), PUSH2T._fxKey(b), function () { PUSH2T.drawLoadNav(); });
    });

    // ── Gain Reset CC105 / CC109 – ON when gain != 0 dB, OFF at unity ──
    PUSH2T.safeConnect('[Channel1]', 'pregain', function (v) {
        if (PUSH2T.scene !== 'browse' && PUSH2T.scene !== 'clip') { PUSH2T.setCC(0x69, PUSH2T.gainColor(v)); }
    });
    PUSH2T.safeConnect('[Channel2]', 'pregain', function (v) {
        if (PUSH2T.scene !== 'browse' && PUSH2T.scene !== 'clip') { PUSH2T.setCC(0x6D, PUSH2T.gainColor(v)); }
    });
};

// ─── HELPERS ─────────────────────────────────────────────────────────────────

PUSH2T._relDelta = function (val) { return (val === 1) ? 1 : -1; };

PUSH2T.clearAllPads = function () {
    for (var n = 0x24; n <= 0x63; n++) {
        midi.sendShortMsg(PUSH2T.PAD_STATIC, n, PUSH2T.C.off);
    }
};

// ─── INPUT CALLBACKS ─────────────────────────────────────────────────────────

// ──── ROW 1: Transport ────────────────────────────────────────────────────────

PUSH2T.playA = function (ch, ctrl, val) {
    if (val > 0) {
        if (PUSH2T.cupPreviewA) {
            // CUE is being held and previewing -> PLAY "locks in" playback.
            // Track is already playing from the preview; just cancel the
            // rollback so releasing CUE afterward does nothing.
            PUSH2T.cupPreviewA = false;
        } else {
            engine.setValue('[Channel1]', 'play', !engine.getValue('[Channel1]', 'play'));
        }
    }
};
PUSH2T.playB = function (ch, ctrl, val) {
    if (val > 0) {
        if (PUSH2T.cupPreviewB) {
            PUSH2T.cupPreviewB = false;
        } else {
            engine.setValue('[Channel2]', 'play', !engine.getValue('[Channel2]', 'play'));
        }
    }
};

// State flags: true while a CUP press is "previewing" from a stopped deck
// (i.e. release should roll back to cue). False if the press was a
// stop-and-jump from a playing deck (release does nothing).
PUSH2T.cupPreviewA = false;
PUSH2T.cupPreviewB = false;

// State flags: true while CUP is physically held down. Drives the
// dim-orange (idle) vs brighter-orange (held) LED distinction — this isn't
// something any engine control reports on its own, so we track it here and
// push the LED directly on press/release (see cupA/cupB).
PUSH2T.cupHeldA = false;
PUSH2T.cupHeldB = false;

// Tolerance (normalized 0..1 playposition) for "playhead is AT the cue point".
// Tight enough that a deliberate jog nudge counts as "moved" (so CUP re-sets
// the cue), but loose enough to reliably register a real cue hit after a
// gotoandstop. ~0.0001 of a track ≈ tens of ms on a typical track.
PUSH2T.CUE_AT_TOLERANCE = 0.0001;

// Returns true if the playhead is currently sitting on the cue point.
PUSH2T._playheadAtCue = function (group) {
    var totalSamples = engine.getValue(group, 'track_samples');
    if (!totalSamples) { return false; }           // no track loaded
    var cueSamples = engine.getValue(group, 'cue_point');
    if (cueSamples < 0) { return false; }           // no cue set yet
    // cue_point and track_samples are reported on the same scale here, so
    // cueSamples / track_samples gives the cue's normalized 0..1 position.
    var cuePos  = cueSamples / totalSamples;
    var playPos = engine.getValue(group, 'playposition');
    return Math.abs(playPos - cuePos) <= PUSH2T.CUE_AT_TOLERANCE;
};

// CUP LED color for the given deck: brighter orange while held, dim orange
// once a cue is set (idle), pale white if no cue is set at all.
PUSH2T._cueColor = function (group, side) {
    var held = (side === 'A') ? PUSH2T.cupHeldA : PUSH2T.cupHeldB;
    var pad = (side === 'A') ? PUSH2T.PAD.cueA : PUSH2T.PAD.cueB;
    if (held) { return PUSH2T.DJ.cuePressed; }
    var loaded = engine.getValue(group, 'track_loaded');
    var cuePoint = engine.getValue(group, 'cue_point');
    return (loaded && cuePoint >= 0) ? PUSH2T.padOn(pad) : PUSH2T.padOff(pad);
};

// Shared stopped-deck decision for CUP: returns 'preview' (jump to/preview
// the existing cue) or 'set' (set a new cue / relocate it to the cursor).
//   No cue yet                       -> 'set'
//   Playhead already at the cue      -> 'preview'
//   SHIFT held                       -> 'set' (explicit relocate, always)
//   Playhead sitting at the native
//     start (~sample 0) and NOT the
//     cue -> 'preview'. This is the freshly-loaded-track default position,
//     not a deliberate scrub, so treat it the same as being at the cue
//     instead of silently overwriting a real cue on the very first press.
//   Otherwise (deliberately scrubbed/jogged somewhere else) -> 'set', so
//     scrub-then-press-CUP still relocates the cue like before.
PUSH2T.CUE_FRESH_TOLERANCE = 0.0005;
PUSH2T._cupStoppedAction = function (group) {
    var cuePt = engine.getValue(group, 'cue_point');
    if (cuePt < 0) { return 'set'; }
    var atCue = PUSH2T._playheadAtCue(group);
    if (atCue) { return 'preview'; }
    if (PUSH2T.shiftActive) { return 'set'; }
    var pos = engine.getValue(group, 'playposition');
    if (pos < PUSH2T.CUE_FRESH_TOLERANCE) { return 'preview'; }
    return 'set';
};

PUSH2T.cupA = function (ch, ctrl, val) {
    // CUP behavior, independent of Preferences > Decks > Cue mode.
    //   Playing -> jump to cue and stop (release = no-op)
    //   Stopped -> see PUSH2T._cupStoppedAction
    PUSH2T.cupHeldA = val > 0;
    PUSH2T.setPad(PUSH2T.PAD.cueA, PUSH2T._cueColor('[Channel1]', 'A'));
    if (val > 0) {
        if (engine.getValue('[Channel1]', 'play')) {
            engine.setValue('[Channel1]', 'cue_gotoandstop', 1);
            PUSH2T.cupPreviewA = false;
        } else if (PUSH2T._cupStoppedAction('[Channel1]') === 'set') {
            engine.setValue('[Channel1]', 'cue_set', 1);
            PUSH2T.cupPreviewA = false;
        } else {
            engine.setValue('[Channel1]', 'cue_gotoandplay', 1);
            PUSH2T.cupPreviewA = true;
        }
    } else {
        if (PUSH2T.cupPreviewA) {
            engine.setValue('[Channel1]', 'cue_gotoandstop', 1);
            PUSH2T.cupPreviewA = false;
        }
    }
};
PUSH2T.cupB = function (ch, ctrl, val) {
    PUSH2T.cupHeldB = val > 0;
    PUSH2T.setPad(PUSH2T.PAD.cueB, PUSH2T._cueColor('[Channel2]', 'B'));
    if (val > 0) {
        if (engine.getValue('[Channel2]', 'play')) {
            engine.setValue('[Channel2]', 'cue_gotoandstop', 1);
            PUSH2T.cupPreviewB = false;
        } else if (PUSH2T._cupStoppedAction('[Channel2]') === 'set') {
            engine.setValue('[Channel2]', 'cue_set', 1);
            PUSH2T.cupPreviewB = false;
        } else {
            engine.setValue('[Channel2]', 'cue_gotoandplay', 1);
            PUSH2T.cupPreviewB = true;
        }
    } else {
        if (PUSH2T.cupPreviewB) {
            engine.setValue('[Channel2]', 'cue_gotoandstop', 1);
            PUSH2T.cupPreviewB = false;
        }
    }
};

// Sync button: single tap toggles sync instantly.
// SHIFT + Sync resets the tempo slider to 0 (center / 0%).
PUSH2T.syncA = function (ch, ctrl, val) {
    if (val > 0) {
        if (PUSH2T.shiftActive) {
            // SHIFT + Sync: reset tempo slider to center (0).
            engine.setValue('[Channel1]', 'rate', 0);
        } else {
            engine.setValue('[Channel1]', 'sync_enabled',
                !engine.getValue('[Channel1]', 'sync_enabled'));
        }
    }
};
PUSH2T.syncB = function (ch, ctrl, val) {
    if (val > 0) {
        if (PUSH2T.shiftActive) {
            engine.setValue('[Channel2]', 'rate', 0);
        } else {
            engine.setValue('[Channel2]', 'sync_enabled',
                !engine.getValue('[Channel2]', 'sync_enabled'));
        }
    }
};

// ──── ROW 2: Slip / Keylock / Quantize ───────────────────────────────────────

PUSH2T.slipA = function (ch, ctrl, val) {
    if (val > 0) engine.setValue('[Channel1]', 'slip_enabled', !engine.getValue('[Channel1]', 'slip_enabled'));
};
PUSH2T.slipB = function (ch, ctrl, val) {
    if (val > 0) engine.setValue('[Channel2]', 'slip_enabled', !engine.getValue('[Channel2]', 'slip_enabled'));
};

PUSH2T.keylockA = function (ch, ctrl, val) {
    if (val > 0) engine.setValue('[Channel1]', 'keylock', !engine.getValue('[Channel1]', 'keylock'));
};
PUSH2T.keylockB = function (ch, ctrl, val) {
    if (val > 0) engine.setValue('[Channel2]', 'keylock', !engine.getValue('[Channel2]', 'keylock'));
};

PUSH2T.quantizeA = function (ch, ctrl, val) {
    if (val > 0) engine.setValue('[Channel1]', 'quantize', !engine.getValue('[Channel1]', 'quantize'));
};
PUSH2T.quantizeB = function (ch, ctrl, val) {
    if (val > 0) engine.setValue('[Channel2]', 'quantize', !engine.getValue('[Channel2]', 'quantize'));
};

// ──── ROWS 4-5: Hotcues ───────────────────────────────────────────────────────

PUSH2T._hotcue = function (group, num, val) {
    if (val > 0) {
        if (PUSH2T.deleteActive) {
            // DELETE held: clear this hotcue instead of activating it.
            engine.setValue(group, 'hotcue_' + num + '_clear', 1);
        } else {
            engine.setValue(group, 'hotcue_' + num + '_activate', 1);
        }
    }
};

PUSH2T.hc1A = function (c, t, v) { PUSH2T._hotcue('[Channel1]', 1, v); };
PUSH2T.hc2A = function (c, t, v) { PUSH2T._hotcue('[Channel1]', 2, v); };
PUSH2T.hc3A = function (c, t, v) { PUSH2T._hotcue('[Channel1]', 3, v); };
PUSH2T.hc4A = function (c, t, v) { PUSH2T._hotcue('[Channel1]', 4, v); };
PUSH2T.hc5A = function (c, t, v) { PUSH2T._hotcue('[Channel1]', 5, v); };
PUSH2T.hc6A = function (c, t, v) { PUSH2T._hotcue('[Channel1]', 6, v); };

PUSH2T.hc1B = function (c, t, v) { PUSH2T._hotcue('[Channel2]', 1, v); };
PUSH2T.hc2B = function (c, t, v) { PUSH2T._hotcue('[Channel2]', 2, v); };
PUSH2T.hc3B = function (c, t, v) { PUSH2T._hotcue('[Channel2]', 3, v); };
PUSH2T.hc4B = function (c, t, v) { PUSH2T._hotcue('[Channel2]', 4, v); };
PUSH2T.hc5B = function (c, t, v) { PUSH2T._hotcue('[Channel2]', 5, v); };
PUSH2T.hc6B = function (c, t, v) { PUSH2T._hotcue('[Channel2]', 6, v); };

// ──── ROW 7: Loop controls ────────────────────────────────────────────────────

// Loop In/Out: normal press sets the loop point. DELETE held: release
// (disable) the loop on either pad.
PUSH2T._releaseLoop = function (group) {
    // Only toggle off if a loop is currently active, so we don't
    // accidentally re-enable one that's already off.
    if (engine.getValue(group, 'loop_enabled')) {
        engine.setValue(group, 'reloop_toggle', 1);
    }
};
// Fine-tune: while a Loop In / Loop Out pad is HELD, turning that deck's jog
// encoder nudges the loop point (In or Out) instead of scratching/bending.
// Each encoder tick moves it LOOP_TUNE_MS milliseconds. Release to finish.
PUSH2T.LOOP_TUNE_MS = 5;
PUSH2T._loopHeld = { '[Channel1]': null, '[Channel2]': null };   // 'in' | 'out' | null

PUSH2T._loopTune = function (group, ticks) {
    var which = PUSH2T._loopHeld[group];
    var st = engine.getValue(group, 'loop_start_position');
    var en = engine.getValue(group, 'loop_end_position');
    if (st < 0 || en < 0) { return; }                  // no loop to tune
    var dur = engine.getValue(group, 'duration');
    var spm = dur > 0 ? engine.getValue(group, 'track_samples') / dur / 1000 : 88.2;
    var mag = Math.max(2, Math.round(Math.abs(ticks) * PUSH2T.LOOP_TUNE_MS * spm / 2) * 2);
    var step = (ticks < 0) ? -mag : mag;
    var minLen = 2048;
    if (which === 'in') {
        var ns = st + step;
        if (ns >= 0 && ns < en - minLen) { engine.setValue(group, 'loop_start_position', ns); }
    } else {
        var ne = en + step;
        if (ne > st + minLen) { engine.setValue(group, 'loop_end_position', ne); }
    }
};

PUSH2T._loopIn = function (group, v) {
    if (v > 0) {
        if (PUSH2T.deleteActive) { PUSH2T._releaseLoop(group); }
        // Pulse (1 then 0) so Mixxx sees a tap, not a held button: while loop_in/
        // loop_out stay 'pressed' on an active loop, the point follows the playhead.
        // loop_in respects the deck's quantize toggle: QNT on -> snaps to
        // the beat grid (no timing roll-back); QNT off -> lands exactly here.
        else {
            // Active loop: a press must NOT move the point (that resized the
            // loop) — it only arms fine-tuning. No active loop: set the IN.
            if (!engine.getValue(group, 'loop_enabled')) {
                engine.setValue(group, 'loop_in', 1); engine.setValue(group, 'loop_in', 0);
            }
            PUSH2T._loopHeld[group] = 'in';
        }
    } else if (PUSH2T._loopHeld[group] === 'in') {
        PUSH2T._loopHeld[group] = null;
    }
};
PUSH2T._loopOut = function (group, v) {
    if (v > 0) {
        if (PUSH2T.deleteActive) { PUSH2T._releaseLoop(group); }
        else {
            if (!engine.getValue(group, 'loop_enabled')) {
                engine.setValue(group, 'loop_out', 1); engine.setValue(group, 'loop_out', 0);
            }
            PUSH2T._loopHeld[group] = 'out';
        }
    } else if (PUSH2T._loopHeld[group] === 'out') {
        PUSH2T._loopHeld[group] = null;
    }
};

PUSH2T.loopInA  = function (c, t, v) { PUSH2T._loopIn('[Channel1]', v); };
PUSH2T.loopOutA = function (c, t, v) { PUSH2T._loopOut('[Channel1]', v); };
PUSH2T.loopInB  = function (c, t, v) { PUSH2T._loopIn('[Channel2]', v); };
PUSH2T.loopOutB = function (c, t, v) { PUSH2T._loopOut('[Channel2]', v); };

// Beatgrid (move grid to playhead) only fires with SHIFT held, to avoid
// accidental presses wrecking the grid.
PUSH2T.beatgridA = function (c, t, v) {
    if (v > 0 && PUSH2T.shiftActive) engine.setValue('[Channel1]', 'beats_translate_curpos', 1);
};
PUSH2T.beatgridB = function (c, t, v) {
    if (v > 0 && PUSH2T.shiftActive) engine.setValue('[Channel2]', 'beats_translate_curpos', 1);
};

// ──── ROW 8: Beatloop size +/– and Set Beatloop ──────────────────────────────

// If a loop is ACTIVE, resize it with loop_scale ALONE (keeps the start
// fixed, moves only the end). Do NOT also write beatloop_size while active —
// that separately moves the loop and fights loop_scale, shifting both points.
// When no loop is active, just update beatloop_size for the GUI + next loop.
PUSH2T._applyBeatloopSize = function (group, idx, dir) {
    if (engine.getValue(group, 'loop_enabled')) {
        engine.setValue(group, 'loop_scale', (dir < 0) ? 0.5 : 2.0);
    } else {
        engine.setValue(group, 'beatloop_size', PUSH2T.BL_SIZES[idx]);
    }
};

PUSH2T.beatloopDecA = function (c, t, v) {
    if (v > 0 && PUSH2T.blIdxA > 0) {
        PUSH2T.blIdxA--;
        PUSH2T._applyBeatloopSize('[Channel1]', PUSH2T.blIdxA, -1);
    }
};
PUSH2T.beatloopIncA = function (c, t, v) {
    if (v > 0 && PUSH2T.blIdxA < PUSH2T.BL_SIZES.length - 1) {
        PUSH2T.blIdxA++;
        PUSH2T._applyBeatloopSize('[Channel1]', PUSH2T.blIdxA, 1);
    }
};
// Toggle beatloop:
//   - Loop currently active -> remove it entirely (loop_remove, not
//     reloop_toggle). reloop_toggle only DISABLES the loop but leaves its
//     points cached, and Mixxx's beatloop_X_activate re-enables those same
//     cached points instead of recomputing when the size matches -- so the
//     next loop would silently reuse the OLD position instead of starting
//     fresh at the playhead. loop_remove clears the points so the next
//     activate is forced to compute a brand new loop at the current position.
//   - Loop off -> always create a fresh beatloop of the current size at the
//     current playhead position.
//     IMPORTANT: use beatloop_size + the GENERIC beatloop_activate, not the
//     fixed-size beatloop_<N>_activate. The fixed-size control anchors the
//     loop BACKWARD (current position becomes the loop's END, so playback
//     immediately jumps back to a point before where you pressed); the
//     generic one anchors FORWARD (current position becomes the loop's
//     START, matching the intended "loop from here" behavior).
PUSH2T.beatloopSetA = function (c, t, v) {
    if (v > 0) {
        if (engine.getValue('[Channel1]', 'loop_enabled')) {
            engine.setValue('[Channel1]', 'loop_remove', 1);   // clear loop
        } else {
            engine.setValue('[Channel1]', 'beatloop_size', PUSH2T.BL_SIZES[PUSH2T.blIdxA]);
            engine.setValue('[Channel1]', 'beatloop_activate', 1);
        }
    }
};

PUSH2T.beatloopDecB = function (c, t, v) {
    if (v > 0 && PUSH2T.blIdxB > 0) {
        PUSH2T.blIdxB--;
        PUSH2T._applyBeatloopSize('[Channel2]', PUSH2T.blIdxB, -1);
    }
};
PUSH2T.beatloopIncB = function (c, t, v) {
    if (v > 0 && PUSH2T.blIdxB < PUSH2T.BL_SIZES.length - 1) {
        PUSH2T.blIdxB++;
        PUSH2T._applyBeatloopSize('[Channel2]', PUSH2T.blIdxB, 1);
    }
};
PUSH2T.beatloopSetB = function (c, t, v) {
    if (v > 0) {
        if (engine.getValue('[Channel2]', 'loop_enabled')) {
            engine.setValue('[Channel2]', 'loop_remove', 1);   // clear loop
        } else {
            engine.setValue('[Channel2]', 'beatloop_size', PUSH2T.BL_SIZES[PUSH2T.blIdxB]);
            engine.setValue('[Channel2]', 'beatloop_activate', 1);
        }
    }
};

// ──── ROW 7: Beatjump (size = same as current beatloop size) ──────────────────
// Flash white on press, return to static color on release.

PUSH2T.beatjumpBackA = function (c, t, v) {
    if (v > 0) {
        engine.setValue('[Channel1]', 'beatjump_size', PUSH2T.BL_SIZES[PUSH2T.blIdxA]);
        engine.setValue('[Channel1]', 'beatjump_backward', 1);
        PUSH2T.setPad(PUSH2T.PAD.bjbA, PUSH2T.C.white);
    } else {
        PUSH2T.setPad(PUSH2T.PAD.bjbA, PUSH2T.padOn(PUSH2T.PAD.bjbA));
    }
};
PUSH2T.beatjumpFwdA = function (c, t, v) {
    if (v > 0) {
        engine.setValue('[Channel1]', 'beatjump_size', PUSH2T.BL_SIZES[PUSH2T.blIdxA]);
        engine.setValue('[Channel1]', 'beatjump_forward', 1);
        PUSH2T.setPad(PUSH2T.PAD.bjfA, PUSH2T.C.white);
    } else {
        PUSH2T.setPad(PUSH2T.PAD.bjfA, PUSH2T.padOn(PUSH2T.PAD.bjfA));
    }
};
PUSH2T.beatjumpBackB = function (c, t, v) {
    if (v > 0) {
        engine.setValue('[Channel2]', 'beatjump_size', PUSH2T.BL_SIZES[PUSH2T.blIdxB]);
        engine.setValue('[Channel2]', 'beatjump_backward', 1);
        PUSH2T.setPad(PUSH2T.PAD.bjbB, PUSH2T.C.white);
    } else {
        PUSH2T.setPad(PUSH2T.PAD.bjbB, PUSH2T.padOn(PUSH2T.PAD.bjbB));
    }
};
PUSH2T.beatjumpFwdB = function (c, t, v) {
    if (v > 0) {
        engine.setValue('[Channel2]', 'beatjump_size', PUSH2T.BL_SIZES[PUSH2T.blIdxB]);
        engine.setValue('[Channel2]', 'beatjump_forward', 1);
        PUSH2T.setPad(PUSH2T.PAD.bjfB, PUSH2T.C.white);
    } else {
        PUSH2T.setPad(PUSH2T.PAD.bjfB, PUSH2T.padOn(PUSH2T.PAD.bjfB));
    }
};

// ──── CC: Load track / prev / next ───────────────────────────────────────────

PUSH2T.loadA = function (c, t, v) {
    if (v > 0) { engine.setValue('[Channel1]', 'LoadSelectedTrack', 1); }
};
PUSH2T.loadB = function (c, t, v) {
    if (v > 0) { engine.setValue('[Channel2]', 'LoadSelectedTrack', 1); }
};
PUSH2T.loadPrevA = function (c, t, v) {
    // Prev/Next track loading was removed; these buttons are FX1/FX2 toggles in every scene.
    if (v > 0) { PUSH2T.fxToggle(0x15); }
};
PUSH2T.loadNextA = function (c, t, v) {
    // Prev/Next track loading was removed; these buttons are FX1/FX2 toggles in every scene.
    if (v > 0) { PUSH2T.fxToggle(0x16); }
};
PUSH2T.loadPrevB = function (c, t, v) {
    // Prev/Next track loading was removed; these buttons are FX1/FX2 toggles in every scene.
    if (v > 0) { PUSH2T.fxToggle(0x19); }
};
PUSH2T.loadNextB = function (c, t, v) {
    // Prev/Next track loading was removed; these buttons are FX1/FX2 toggles in every scene.
    if (v > 0) { PUSH2T.fxToggle(0x1A); }
};

// ──── CC: Jog encoders (CC71 Deck A / CC75 Deck B) ───────────────────────────
//
// "Real" jog behavior:
//   • Encoder TOUCHED (capacitive, Note On 0x00/0x04) -> enable scratch.
//     Rotation feeds engine.scratchTick() so you can scratch/cue like a platter.
//   • Encoder NOT touched -> rotation TEMPO-BENDS the track: speeds it up
//     (turn away/CW) or slows it down (turn toward/CCW) to nudge two tracks
//     into sync, then snaps back to the set rate. Uses rate_temp_*_small.
//
// Relative value: 1..63 = forward (CW), 65..127 = back (CCW), step magnitude
// scales with spin speed (Push 2 sends larger values on faster turns).

PUSH2T.JOG_ALPHA      = 1.0 / 8;   // scratch filter responsiveness
PUSH2T.JOG_BETA       = (1.0 / 8) / 32;

// Scratch velocity multiplier (stopped deck). Push 2 sends larger deltas on
// faster spins; this amplifies that so quick flicks throw the platter more.
PUSH2T.JOG_SCRATCH_VEL = 2.0;      // raise for more velocity sensitivity

// Tempo-bend amount PER TICK while turning the jog on a PLAYING deck, as a
// fraction of the deck's normalized rate range (-1..+1). Accumulates while
// you turn and scales with spin speed; resets to the set rate when you LIFT
// your finger off the encoder (Traktor-style).
PUSH2T.JOG_BEND_STEP  = 0.012;     // per encoder tick (raise for stronger bend)
PUSH2T.JOG_BEND_MAX   = 0.5;       // cap total bend at ±50% of range

PUSH2T._jogDelta = function (value) {
    // Two's-complement relative decode, preserving magnitude (acceleration)
    if (value < 64)  return value;
    if (value > 64)  return value - 128;
    return 0;
};

PUSH2T._jogScratchActive = { '[Channel1]': false, '[Channel2]': false };
PUSH2T._jogTouched       = { '[Channel1]': false, '[Channel2]': false };
PUSH2T._jogBendBase      = { '[Channel1]': null,  '[Channel2]': null };

// Touch handlers (bound to encoder touch Note On/Off in the XML).
//   Deck STOPPED + touched -> scratch the platter (velocity-sensitive).
//   Deck PLAYING + touched -> tempo-bend on turn; resets on release.
PUSH2T.jogTouchA = function (c, t, v) { PUSH2T._jogTouch('[Channel1]', 1, v); };
PUSH2T.jogTouchB = function (c, t, v) { PUSH2T._jogTouch('[Channel2]', 2, v); };

PUSH2T._jogTouch = function (group, deckNum, v) {
    if (v > 0) {
        PUSH2T._jogTouched[group] = true;
        if (!engine.getValue(group, 'play')) {
            // Stopped: grab platter for scratching.
            engine.scratchEnable(deckNum, 768, 33 + 1/3,
                                 PUSH2T.JOG_ALPHA, PUSH2T.JOG_BETA);
            PUSH2T._jogScratchActive[group] = true;
        } else {
            // Playing: capture the set rate so we can snap back on release.
            PUSH2T._jogBendBase[group] = engine.getValue(group, 'rate');
        }
    } else {
        PUSH2T._jogTouched[group] = false;
        if (PUSH2T._jogScratchActive[group]) {
            engine.scratchDisable(deckNum);
            PUSH2T._jogScratchActive[group] = false;
        }
        // Release any tempo bend: snap back to the captured set rate.
        if (PUSH2T._jogBendBase[group] !== null) {
            engine.setValue(group, 'rate', PUSH2T._jogBendBase[group]);
            PUSH2T._jogBendBase[group] = null;
        }
    }
};

PUSH2T._jogTurn = function (group, deckNum, value) {
    var delta = PUSH2T._jogDelta(value);
    if (delta === 0) return;

    // Loop In/Out pad held: this turn fine-tunes the loop point instead.
    if (PUSH2T._loopHeld[group]) {
        PUSH2T._loopTune(group, delta);
        return;
    }

    if (PUSH2T._jogScratchActive[group] && engine.isScratching(deckNum)) {
        // Deck stopped + touched: velocity-sensitive scratch.
        engine.scratchTick(deckNum, delta * PUSH2T.JOG_SCRATCH_VEL);
    } else if (PUSH2T._jogTouched[group]) {
        // Deck playing + touched: tempo bend that accumulates while turning
        // and resets when you lift your finger (handled in _jogTouch).
        if (PUSH2T._jogBendBase[group] === null) {
            PUSH2T._jogBendBase[group] = engine.getValue(group, 'rate');
        }
        // Direction: turn forward/CW = faster, back/CCW = slower.
        // Negated to correct encoder direction.
        var bend = engine.getValue(group, 'rate') - PUSH2T._jogBendBase[group];
        bend += (-delta) * PUSH2T.JOG_BEND_STEP;
        if (bend >  PUSH2T.JOG_BEND_MAX) bend =  PUSH2T.JOG_BEND_MAX;
        if (bend < -PUSH2T.JOG_BEND_MAX) bend = -PUSH2T.JOG_BEND_MAX;

        var next = PUSH2T._jogBendBase[group] + bend;
        if (next > 1)  next = 1;
        if (next < -1) next = -1;
        engine.setValue(group, 'rate', next);
    }
    // If playing and NOT touched, turning does nothing (bend needs touch).
};

PUSH2T.rateA = function (c, t, v) { PUSH2T._jogTurn('[Channel1]', 1, v); };
PUSH2T.rateB = function (c, t, v) { PUSH2T._jogTurn('[Channel2]', 2, v); };

PUSH2T.gainA = function (c, t, v) {
    var d = PUSH2T._relDelta(v) * PUSH2T.GAIN_STEP;
    engine.setValue('[Channel1]', 'pregain',
        Math.max(0, Math.min(4, engine.getValue('[Channel1]', 'pregain') + d)));
};
PUSH2T.gainB = function (c, t, v) {
    var d = PUSH2T._relDelta(v) * PUSH2T.GAIN_STEP;
    engine.setValue('[Channel2]', 'pregain',
        Math.max(0, Math.min(4, engine.getValue('[Channel2]', 'pregain') + d)));
};

PUSH2T.masterVol = function (c, t, v) {
    var d = PUSH2T._relDelta(v) * PUSH2T.VOL_STEP;
    engine.setValue('[Master]', 'volume',
        Math.max(0, Math.min(5, engine.getValue('[Master]', 'volume') + d)));
};

// ──── TOP ROW (CC102-109): library SORT in library mode, else normal ─────────
// In library mode (library maximized via the Play/browse button, CC85) each
// top-row button sorts the track table by a column; pressing the same one
// again flips ascending/descending (Mixxx's sort_column_toggle). Outside
// library mode CC105/CC109 are the Gain Reset buttons and the rest do nothing.
// Values are Mixxx's TrackModel::SortColumnId (verified against Mixxx main;
// this mapping was written for Mixxx 2.5.6 — tell me if a column looks off).
PUSH2T.SORT_COLUMNS = {
    104: 2,    // Title
    105: 1,    // Artist
    106: 3,    // Album
    107: 15,   // BPM
    108: 20,   // Key
    109: 13    // Duration
};
PUSH2T.SORT_NAMES = { 104: 'Title', 105: 'Artist', 106: 'Album', 107: 'BPM',
                      108: 'Key', 109: 'Duration' };
// CC102 = preview play/pause, CC103 unused (see below).

// Current scene: 'device' (default/resting) | 'browse' | 'mix' (reserved) | 'clip' (FX). Browse is
// tied to the library being maximized (kept in sync from the skin control);
// pressing any other scene button leaves Browse and un-maximizes the library.
PUSH2T.scene = 'device';   // resting/default scene
PUSH2T.inLibraryMode = function () { return PUSH2T.scene === 'browse'; };

PUSH2T.setScene = function (name) {
    var wasBrowse = (PUSH2T.scene === 'browse');
    PUSH2T.scene = name;
    if (wasBrowse && name !== 'browse') {
        engine.setValue('[Skin]', 'show_maximized_library', 0);   // leave library view
    }
    PUSH2T.drawTopRow();
    PUSH2T.drawScenes();
    PUSH2T.drawStripCursor();
    PUSH2T.stripRelease();
    print('[PUSH2T] scene: ' + name);
};

PUSH2T._sortBy = function (cc) {
    engine.setValue('[Library]', 'sort_column_toggle', PUSH2T.SORT_COLUMNS[cc]);
    print('[PUSH2T] library sort by ' + PUSH2T.SORT_NAMES[cc]);
};

// ── Preview deck (CC102 in library mode) ──
// Play/pause of [PreviewDeck1]. If the library selection moved since the
// preview was last started, a new press loads the selected track and plays it
// from the start; otherwise a press on a paused preview just resumes.
// While the preview is PLAYING, the Left/Right arrows seek it back/forward
// PREVIEW_SEEK_SEC seconds instead of navigating the library.
PUSH2T.PREVIEW_SEEK_SEC = 10;
PUSH2T.previewDirty = true;      // selection moved since the preview was loaded

PUSH2T.previewPlaying = function () {
    return engine.getValue('[PreviewDeck1]', 'play') ? true : false;
};

PUSH2T.previewToggle = function () {
    var pv = '[PreviewDeck1]';
    if (PUSH2T.previewPlaying()) {
        engine.setValue(pv, 'play', 0);                    // pause
    } else if (engine.getValue(pv, 'track_loaded') && !PUSH2T.previewDirty) {
        engine.setValue(pv, 'play', 1);                    // resume
    } else {
        engine.setValue(pv, 'LoadSelectedTrackAndPlay', 1);  // new track
        PUSH2T.previewDirty = false;
    }
};

PUSH2T.previewSeek = function (dir) {
    var pv = '[PreviewDeck1]';
    var dur = engine.getValue(pv, 'duration');
    if (dur <= 0) { return; }
    var pos = engine.getValue(pv, 'playposition') + dir * PUSH2T.PREVIEW_SEEK_SEC / dur;
    engine.setValue(pv, 'playposition', Math.max(0, Math.min(1, pos)));
};

PUSH2T.top102 = function (c, t, v) {
    if (v > 0 && PUSH2T.inLibraryMode()) { PUSH2T.previewToggle(); }
};
PUSH2T.top103 = function () {};       // free (kept bound so color mode can catch it)

[104, 106, 107, 108].forEach(function (cc) {
    PUSH2T['top' + cc] = function (c, t, v) {
        if (v > 0 && PUSH2T.inLibraryMode()) { PUSH2T._sortBy(cc); }
    };
});

PUSH2T.gainResetA = function (c, t, v) {
    if (v <= 0) { return; }
    if (PUSH2T.inLibraryMode()) { PUSH2T._sortBy(105); }
    else { engine.setValue('[Channel1]', 'pregain', 1.0); }
};
PUSH2T.gainResetB = function (c, t, v) {
    if (v <= 0) { return; }
    if (PUSH2T.inLibraryMode()) { PUSH2T._sortBy(109); }
    else { engine.setValue('[Channel2]', 'pregain', 1.0); }
};

// Number of MoveFocusForward steps to reach the track table from wherever
// focus currently is. Depends on skin's widget order (search box, sidebar
// tree, track table, ...). If the encoder still scrolls the wrong thing
// after pressing the browser button, try changing this to 1, 2, or 3.
PUSH2T.LIBRARY_FOCUS_STEPS = 1;

PUSH2T.toggleBrowser = function (c, t, v) {
    // [Skin] show_maximized_library toggles the library panel between
    // normal and maximized/full view. (Previous version used
    // [Library] show_track_menu, which opens the right-click context
    // menu on the selected track instead.)
    //
    // MoveFocusForward additionally shifts keyboard focus to the track
    // table so the browse encoder (CC14 -> MoveVertical) scrolls track
    // selection immediately, without first clicking a song.
    if (v > 0) {
        var cur = engine.getValue('[Skin]', 'show_maximized_library');
        engine.setValue('[Skin]', 'show_maximized_library', cur ? 0 : 1);

        for (var i = 0; i < PUSH2T.LIBRARY_FOCUS_STEPS; i++) {
            engine.setValue('[Library]', 'MoveFocusForward', 1);
        }
    }
};

// ──── SHIFT (global modifier, hold) ──────────────────────────────────────────

PUSH2T.shiftBtn = function (c, t, v) {
    if (v > 0) {
        PUSH2T.shiftActive = true;
        // Bright white while held
        midi.sendShortMsg(0xB0, PUSH2T.CC_BTN.shift, 127);
    } else {
        PUSH2T.shiftActive = false;
        // Visible idle level
        midi.sendShortMsg(0xB0, PUSH2T.CC_BTN.shift, 64);
    }
    // Color-edit mode: SHIFT swaps the display between ON and OFF colors.
    if (PUSH2T.colorMode) { PUSH2T.renderColorMode(); }
    else { PUSH2T.drawBeatgrid(); }
};

// ──── DELETE (global modifier, hold) ─────────────────────────────────────────
// Held while pressing a hotcue -> clears that hotcue.
// Held while pressing Loop In or Loop Out -> disables (releases) the loop.

PUSH2T.deleteBtn = function (c, t, v) {
    if (v > 0) {
        PUSH2T.deleteActive = true;
        PUSH2T.setCC(PUSH2T.CC_BTN.del, PUSH2T.slots['C118'].on);   // held
    } else {
        PUSH2T.deleteActive = false;
        PUSH2T.setCC(PUSH2T.CC_BTN.del, PUSH2T.slots['C118'].off);    // idle
    }
};

// ──── RECORD (CC86) ──────────────────────────────────────────────────────────
// Toggles Mixxx mix recording. LED: static white when idle, static red
// while recording — driven by the [Recording] status connection below.

PUSH2T.recordToggle = function (c, t, v) {
    if (v > 0) {
        engine.setValue('[Recording]', 'toggle_recording', 1);
    }
};

PUSH2T.connectRecording = function () {
    PUSH2T.safeConnect('[Recording]', 'status', function (v) {
        // Plain static color: bright red while recording, white when idle.
        PUSH2T.setCC(PUSH2T.CC_BTN.record,
            v ? PUSH2T.slots['C86'].on : PUSH2T.slots['C86'].off);
    });
};

// ──── ARROW BUTTONS (CC44 Left, CC45 Right, CC46 Up, CC47 Down) ────────────────
// Up/Down move within whichever list has focus (tracks or sidebar folders/
// playlists/crates). Left/Right switch focus sidebar <-> tracks;
// SHIFT+Right opens the selected sidebar item. (Preview seeking is done only
// with the touch strip, never the arrows.)
PUSH2T._arrow = function (key, v) {
    if (v <= 0 || PUSH2T.colorMode) { return; }
    if (key === 'MoveUp' || key === 'MoveDown') {
        PUSH2T.previewDirty = true;
        // Normal (non-browse) view: if nothing in the library has keyboard
        // focus, give it to the track table so Up/Down actually move.
        if (engine.getValue('[Library]', 'focused_widget') === 0) {
            engine.setValue('[Library]', 'focused_widget', 3);
        }
    }
    // Left/Right move keyboard FOCUS between the sidebar (folders/playlists/
    // crates) and the track table, so Up/Down can then walk either list.
    // SHIFT + Right opens/expands the selected sidebar item (GoToItem).
    if (key === 'MoveLeft')  { engine.setValue('[Library]', 'MoveFocusBackward', 1); return; }
    if (key === 'MoveRight') {
        if (PUSH2T.shiftActive) { engine.setValue('[Library]', 'GoToItem', 1); }
        else { engine.setValue('[Library]', 'MoveFocusForward', 1); }
        return;
    }
    engine.setValue('[Library]', key, 1);
};
PUSH2T.arrowUp    = function (c, t, v) { PUSH2T._arrow('MoveUp', v); };
PUSH2T.arrowDown  = function (c, t, v) { PUSH2T._arrow('MoveDown', v); };
PUSH2T.arrowLeft  = function (c, t, v) { PUSH2T._arrow('MoveLeft', v); };
PUSH2T.arrowRight = function (c, t, v) { PUSH2T._arrow('MoveRight', v); };

// ──── BROWSE ENCODER (CC14) ───────────────────────────────────────────────────
//
// Push 2 sends this CC using "two's complement" relative encoding:
//   1..63   -> positive steps  (CW),  value = step size (acceleration)
//   65..127 -> negative steps  (CCW), step size = 128 - value
//   64      -> no movement
//
// Normal: scroll the track table  -> [Library] MoveVertical
// SHIFT held: navigate sidebar sections (Tracks/Auto DJ/Playlists/Crates/...)
//   -> [Library] MoveFocusForward / MoveFocusBackward, once per step
//      (capped at SHIFT_NAV_MAX_STEPS to avoid runaway on a fast spin)

PUSH2T._decodeRelative = function (value) {
    if (value < 64)  return value;        // positive steps
    if (value > 64)  return value - 128;  // negative steps
    return 0;
};

PUSH2T.browseEncoder = function (c, t, v) {
    var amount = PUSH2T._decodeRelative(v);
    if (amount === 0) return;
    PUSH2T.previewDirty = true;

    if (PUSH2T.shiftActive) {
        var steps = Math.min(Math.abs(amount), PUSH2T.SHIFT_NAV_MAX_STEPS);
        var key   = (amount > 0) ? 'MoveFocusForward' : 'MoveFocusBackward';
        for (var i = 0; i < steps; i++) {
            engine.setValue('[Library]', key, 1);
        }
    } else {
        engine.setValue('[Library]', 'MoveVertical', amount);
    }
};

// ─────────────────────────────────────────────────────────────────────────────
//  TUNING GUIDE
//  ─────────────────────────────────────────────────────────────────────────────
//  PUSH2T.GAIN_STEP   = 0.025  →  gain change per encoder tick
//  PUSH2T.RATE_STEP   = 0.004  →  rate change per encoder tick
//  PUSH2T.VOL_STEP    = 0.015  →  master volume change per tick
//  PUSH2T.blIdxA/B    = 3      →  default beatloop size (2 beats)
//  PUSH2T.BL_SIZES    array    →  available beatloop sizes
//
//  CUP behavior follows the Mixxx cue mode set in Preferences → Decks.
//  Hotcue activate: empty pad = set cue, set pad = jump to cue.
//  Loop In / Loop Out: press sets bracket; loop activates after Out is set.
//  Set Beatloop: creates a loop of current size (shown by ÷2/×2 buttons).
//  Load Prev/Next: moves library selection then immediately loads to deck.
// ─────────────────────────────────────────────────────────────────────────────

// ──── COLOR-EDIT MODE (SELECT CC48) ──────────────────────────────────────────
// SELECT toggles the mode. Inside it:
//   • every pad / LED button shows its ON color (SHIFT held: its OFF color)
//   • pressing a pad/button selects it (nothing else fires)
//   • turning the tempo encoder (CC14) steps that slot's palette index
//     (SHIFT held at selection time edits the OFF color, otherwise ON)
//   • each change prints "[PUSH2T] COLORS {...}" to the Mixxx log
// Leaving the mode restores normal LED feedback.

PUSH2T.selectBtn = function (c, t, v) {
    if (v <= 0) { return; }
    if (!PUSH2T.colorMode) {
        PUSH2T.colorMode = true;
        PUSH2T.selSlot = null;
        PUSH2T.dupArmed = false; PUSH2T.dupSource = null;
        midi.sendShortMsg(0xB0, 0x58, 64);
        PUSH2T.clearAllPads();
        PUSH2T.renderColorMode();
        midi.sendShortMsg(0xB0, 0x30, 127);
        print('[PUSH2T] Color-edit mode ON');
    } else {
        PUSH2T.colorMode = false;
        PUSH2T.selSlot = null;
        PUSH2T.dupArmed = false; PUSH2T.dupSource = null;
        midi.sendShortMsg(0xB0, 0x58, 0);
        PUSH2T.clearAllPads();
        PUSH2T.drawStaticColors();
        PUSH2T.conns.forEach(function (conn) { conn.trigger(); });
        PUSH2T.dumpColors();
        print('[PUSH2T] Color-edit mode OFF');
    }
};

// DUPLICATE (CC88): in color-edit mode, press it, press a pad/button to copy
// its color, then press other pads/buttons to give them the same color (ON or
// OFF according to whether SHIFT is held). Press Duplicate again to finish.
PUSH2T.duplicateBtn = function (c, t, v) {
    if (v <= 0 || !PUSH2T.colorMode) { return; }
    PUSH2T.dupArmed = !PUSH2T.dupArmed;
    PUSH2T.dupSource = null;
    midi.sendShortMsg(0xB0, 0x58, PUSH2T.dupArmed ? 127 : 64);
    print('[PUSH2T] Duplicate ' + (PUSH2T.dupArmed ? 'armed: press the source pad' : 'off'));
};

// Called instead of the normal handler while in color-edit mode.
PUSH2T._colorPress = function (status, ctrl, val) {
    var type = status & 0xF0;
    if (val <= 0 || type === 0x80) { return; }           // ignore releases
    var key = ((type === 0x90) ? 'P' : 'C') + ctrl;
    if (!PUSH2T.slots[key]) { return; }
    PUSH2T.selState = PUSH2T.shiftActive ? 'off' : 'on';
    if (PUSH2T.dupArmed) {
        if (PUSH2T.dupSource === null) {
            // First press while Duplicate is armed: copy this color.
            PUSH2T.dupSource = PUSH2T.slots[key][PUSH2T.selState];
            print('[PUSH2T] duplicate: copied ' + PUSH2T.dupSource + ' from ' + key);
        } else {
            // Following presses: paste the copied color here.
            PUSH2T.slots[key][PUSH2T.selState] = PUSH2T.dupSource;
            PUSH2T._rawSlot(key, PUSH2T.dupSource);
            print('[PUSH2T] duplicate: ' + key + ' ' + PUSH2T.selState + ' = ' + PUSH2T.dupSource);
            PUSH2T.dumpColors();
        }
        PUSH2T.selSlot = key;
        return;
    }
    PUSH2T.selSlot = key;
    print('[PUSH2T] selected ' + key + ' (' + PUSH2T.selState + ') = ' +
          PUSH2T.slots[key][PUSH2T.selState]);
};

PUSH2T._colorTurn = function (amount) {
    if (PUSH2T.selSlot === null) { return; }
    var slot = PUSH2T.slots[PUSH2T.selSlot];
    var v = slot[PUSH2T.selState] + (amount > 0 ? 1 : -1);
    if (v < 0) { v = 0; }
    if (v > 127) { v = 127; }
    slot[PUSH2T.selState] = v;
    // Show the change live if the selected state is what's on screen.
    if ((PUSH2T.selState === 'off') === PUSH2T.shiftActive) {
        PUSH2T._rawSlot(PUSH2T.selSlot, v);
    }
    print('[PUSH2T] ' + PUSH2T.selSlot + ' ' + PUSH2T.selState + ' = ' + v);
    PUSH2T.dumpColors();
};

// VU pads have no normal-mode action; the binding exists only so color-edit
// mode can select them.
PUSH2T.vuPad = function () {};

// Clip scene routing: encoders and top-row buttons act on effects instead.
PUSH2T.fxEnc72 = function (c, t, v) { if (PUSH2T.scene === 'clip') { PUSH2T.fxEncoder(72, v); } };
PUSH2T.fxEnc73 = function (c, t, v) { if (PUSH2T.scene === 'clip') { PUSH2T.fxEncoder(73, v); } };
PUSH2T.fxEnc76 = function (c, t, v) { if (PUSH2T.scene === 'clip') { PUSH2T.fxEncoder(76, v); } };
PUSH2T.fxEnc77 = function (c, t, v) { if (PUSH2T.scene === 'clip') { PUSH2T.fxEncoder(77, v); } };
[['rateA', 71], ['gainA', 74], ['rateB', 75], ['gainB', 78]].forEach(function (e) {
    var orig = PUSH2T[e[0]];
    PUSH2T[e[0]] = function (c, t, v, st, g) {
        if (PUSH2T.scene === 'clip') { PUSH2T.fxEncoder(e[1], v); return; }
        return orig.call(PUSH2T, c, t, v, st, g);
    };
});
[['top102', 102], ['top103', 103], ['top104', 104], ['top106', 106], ['top107', 107],
 ['top108', 108], ['gainResetA', 105], ['gainResetB', 109]].forEach(function (e) {
    var orig = PUSH2T[e[0]];
    PUSH2T[e[0]] = function (c, t, v, st, g) {
        if (PUSH2T.scene === 'clip') { PUSH2T.fxButton(e[1], v); return; }
        return orig.call(PUSH2T, c, t, v, st, g);
    };
});

// Wrap every button/pad handler so color-edit mode can intercept it. Done at
// script load (not init) so the wrapped versions are what the XML resolves.
(function () {
    var names = ['sceneBrowse', 'sceneDevice', 'sceneMix', 'sceneClip', 'metronomeBtn', 'tapTempo', 'deckSelA', 'deckSelB', 'top102', 'top103', 'top104', 'top106', 'top107', 'top108', 'vuPad', 'deleteBtn', 'toggleBrowser', 'recordToggle', 'loadA', 'loadB',
                 'loadPrevA', 'loadNextA', 'loadPrevB', 'loadNextB',
                 'gainResetA', 'gainResetB'];
    ['A', 'B'].forEach(function (s) {
        ['play', 'cup', 'sync', 'slip', 'keylock', 'quantize', 'loopIn', 'loopOut',
         'beatjumpBack', 'beatgrid', 'beatjumpFwd', 'beatloopDec', 'beatloopSet',
         'beatloopInc'].forEach(function (n) { names.push(n + s); });
        for (var i = 1; i <= 6; i++) { names.push('hc' + i + s); }
    });
    names.forEach(function (name) {
        var orig = PUSH2T[name];
        if (typeof orig !== 'function') { return; }
        PUSH2T[name] = function (ch, ctrl, val, status, group) {
            if (PUSH2T.colorMode) { PUSH2T._colorPress(status, ctrl, val); return; }
            return orig.call(PUSH2T, ch, ctrl, val, status, group);
        };
    });
    var origBrowse = PUSH2T.browseEncoder;
    PUSH2T.browseEncoder = function (ch, ctrl, val, status, group) {
        if (PUSH2T.colorMode) {
            var amt = PUSH2T._decodeRelative(val);
            if (amt !== 0) { PUSH2T._colorTurn(amt); }
            return;
        }
        return origBrowse.call(PUSH2T, ch, ctrl, val, status, group);
    };
})();
