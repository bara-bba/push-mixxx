// ─────────────────────────────────────────────────────────────────────────────
//  pusher-script.js  –  Ableton Push 2 / Mixxx  (functionprefix: PUSH2T)
//  Companion to: pusher.midi.xml
//
//  MIDI convention: Traktor C-1=0  →  C2=36=0x24  (Push 2 bottom-left pad)
//  0x90 = Note On Ch1 (pads, static LED)
//  0x9A = Note On Ch11 (pads, blinking animation on Push 2)
//  0xB0 = CC Ch1 (encoders & buttons)
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
PUSH2T.PAD_BLINK   = 0x9A;   // Note On Ch11  → blinking pad (Push 2 animation)
PUSH2T.BTN_STATIC  = 0xB0;   // CC Ch1        → button static (not used for LEDs here)

// ─── PUSH 2 COLOR PALETTE (6-bit index) ──────────────────────────────────────
PUSH2T.C = {
    off        : 0,
    gray       : 1,
    red        : 2,
    orange     : 7,
    yellow     : 8,
    lime       : 18,   // hotcue set
    green      : 10,
    darkgreen  : 12,
    teal       : 50,
    blue       : 125,
    purple     : 48,
    white      : 122,
    pink       : 57
};

// ─── PAD NOTE ADDRESSES (0x90 status) ────────────────────────────────────────
PUSH2T.PAD = {
    // Row 1
    playA : 0x24,  cueA  : 0x25,  syncA : 0x26,  // col 1-3 Deck A
    playB : 0x28,  cueB  : 0x29,  syncB : 0x2A,  // col 5-7 Deck B
    // Row 2
    slipA : 0x2C,  keyA  : 0x2D,  qntA  : 0x2E,  // col 1-3 Deck A
    slipB : 0x30,  keyB  : 0x31,  qntB  : 0x32,  // col 5-7 Deck B
    // Row 3 – empty (no input)
    // Row 3 – empty (no input)
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

// ─── ENCODER SENSITIVITY ─────────────────────────────────────────────────────
PUSH2T.GAIN_STEP = 0.025;
PUSH2T.RATE_STEP = 0.004;
PUSH2T.VOL_STEP  = 0.015;

// ─── BEATLOOP STATE (per deck, persistent across calls) ──────────────────────
// Valid sizes: 2^n for n = -2..6  →  0.25, 0.5, 1, 2, 4, 8, 16, 32, 64
PUSH2T.BL_SIZES = [0.25, 0.5, 1, 2, 4, 8, 16, 32, 64];
PUSH2T.blIdxA   = 3;   // default index → 2 beats
PUSH2T.blIdxB   = 3;

// ─── INIT / SHUTDOWN ─────────────────────────────────────────────────────────

PUSH2T.init = function (id, debugging) {
    try {
        PUSH2T.clearAllPads();
        PUSH2T.connectDeck('[Channel1]', 'A');
        PUSH2T.connectDeck('[Channel2]', 'B');
        PUSH2T.drawStaticButtons();
        print('[PUSH2T] Push 2 Pusher mapping initialized.');
    } catch (e) {
        print('[PUSH2T] ERROR during init: ' + e);
    }
};

PUSH2T.shutdown = function () {
    PUSH2T.clearAllPads();
    // Clear CC button LEDs
    [0x14,0x15,0x16,0x18,0x19,0x1A,0x55,0x69,0x6D].forEach(function(cc) {
        midi.sendShortMsg(0xB0, cc, 0);
    });
    print('[PUSH2T] Push 2 Pusher mapping shut down.');
};

// ─── SAFE CONNECTION HELPER ───────────────────────────────────────────────────
// engine.makeConnection() returns null if the (group, control) pair doesn't
// exist on this Mixxx version/skin. Calling .trigger() on null throws an
// uncaught error, which can abort init() and disable the ENTIRE controller.
// Always go through this helper instead of calling makeConnection directly.
PUSH2T.safeConnect = function (group, key, callback) {
    var conn = engine.makeConnection(group, key, callback);
    if (conn) {
        conn.trigger();
    } else {
        print('[PUSH2T] WARNING: could not connect ' + group + ' ' + key + ' (control not found)');
    }
    return conn;
};

// ─── DECK CONNECTIONS (LED feedback via engine.makeConnection) ────────────────

PUSH2T.connectDeck = function (group, side) {
    var P = PUSH2T.PAD;

    // ── Play indicator (blinking when playing) ──
    PUSH2T.safeConnect(group, 'play_indicator', function (v) {
        var pad = (side === 'A') ? P.playA : P.playB;
        if (v > 0) {
            midi.sendShortMsg(PUSH2T.PAD_BLINK, pad, PUSH2T.C.green);
        } else {
            midi.sendShortMsg(PUSH2T.PAD_STATIC, pad, PUSH2T.C.darkgreen);
        }
    });

    // ── CUP – lit orange when cue is set, gray when not ──
    // cue_point = -1 when no cue is set, >= 0 (sample position) when set.
    // track_loaded guards against false positives on empty decks.
    PUSH2T.safeConnect(group, 'cue_point', function (v) {
        var pad = (side === 'A') ? P.cueA : P.cueB;
        var loaded = engine.getValue(group, 'track_loaded');
        midi.sendShortMsg(PUSH2T.PAD_STATIC, pad,
            (loaded && v >= 0) ? PUSH2T.C.orange : PUSH2T.C.gray);
    });

    // ── Sync ──
    PUSH2T.safeConnect(group, 'sync_enabled', function (v) {
        var pad = (side === 'A') ? P.syncA : P.syncB;
        midi.sendShortMsg(PUSH2T.PAD_STATIC, pad,
            v ? PUSH2T.C.blue : PUSH2T.C.gray);
    });

    // ── Slip mode ──
    PUSH2T.safeConnect(group, 'slip_enabled', function (v) {
        var pad = (side === 'A') ? P.slipA : P.slipB;
        midi.sendShortMsg(PUSH2T.PAD_STATIC, pad,
            v ? PUSH2T.C.purple : PUSH2T.C.gray);
    });

    // ── Keylock ──
    PUSH2T.safeConnect(group, 'keylock', function (v) {
        var pad = (side === 'A') ? P.keyA : P.keyB;
        midi.sendShortMsg(PUSH2T.PAD_STATIC, pad,
            v ? PUSH2T.C.yellow : PUSH2T.C.gray);
    });

    // ── Quantize ──
    PUSH2T.safeConnect(group, 'quantize', function (v) {
        var pad = (side === 'A') ? P.qntA : P.qntB;
        midi.sendShortMsg(PUSH2T.PAD_STATIC, pad,
            v ? PUSH2T.C.teal : PUSH2T.C.gray);
    });

    // ── Hotcues 1-6 ──
    var hcPads = (side === 'A')
        ? [P.hc1A, P.hc2A, P.hc3A, P.hc4A, P.hc5A, P.hc6A]
        : [P.hc1B, P.hc2B, P.hc3B, P.hc4B, P.hc5B, P.hc6B];
    for (var n = 1; n <= 6; n++) {
        (function (num, pad) {
            PUSH2T.safeConnect(group, 'hotcue_' + num + '_enabled', function (v) {
                midi.sendShortMsg(PUSH2T.PAD_STATIC, pad,
                    v ? PUSH2T.C.lime : PUSH2T.C.off);
            });
        })(n, hcPads[n - 1]);
    }

    // ── Loop active → lights Loop In/Out pads; beatjump pads stay static ──
    PUSH2T.safeConnect(group, 'loop_enabled', function (v) {
        var lin  = (side === 'A') ? P.linA  : P.linB;
        var lout = (side === 'A') ? P.loutA : P.loutB;
        var bls  = (side === 'A') ? P.blsA  : P.blsB;
        var color = v ? PUSH2T.C.green : PUSH2T.C.darkgreen;
        midi.sendShortMsg(PUSH2T.PAD_STATIC, lin,  color);
        midi.sendShortMsg(PUSH2T.PAD_STATIC, lout, color);
        if (v > 0) {
            midi.sendShortMsg(PUSH2T.PAD_BLINK, bls, PUSH2T.C.lime);
        } else {
            midi.sendShortMsg(PUSH2T.PAD_STATIC, bls, PUSH2T.C.gray);
        }
    });

    // ── VU meter ──
    PUSH2T.safeConnect(group, 'VuMeter', function (v) {
        PUSH2T.drawVu(side, v);
    });
};

// ─── VU METER ────────────────────────────────────────────────────────────────

PUSH2T.drawVu = function (side, value) {
    var col = (side === 'A') ? PUSH2T.VU_A : PUSH2T.VU_B;
    var lit = Math.round(value * col.length);
    for (var i = 0; i < col.length; i++) {
        var c;
        if (i < lit) {
            c = (i < 5) ? PUSH2T.C.green
              : (i < 7) ? PUSH2T.C.yellow
              :            PUSH2T.C.red;
        } else {
            c = PUSH2T.C.off;
        }
        midi.sendShortMsg(PUSH2T.PAD_STATIC, col[i], c);
    }
};

// ─── STATIC LIGHTS (action buttons that don't track state) ───────────────────

// Push 2 CC button LED:  midi.sendShortMsg(0xB0, ccNum, value)
//   0 = off  |  1 = dim (quarter)  |  64 = medium  |  127 = full bright

PUSH2T.drawStaticButtons = function () {
    // Beatgrid (action – static orange, always on)
    midi.sendShortMsg(PUSH2T.PAD_STATIC, PUSH2T.PAD.bgrA, PUSH2T.C.orange);
    midi.sendShortMsg(PUSH2T.PAD_STATIC, PUSH2T.PAD.bgrB, PUSH2T.C.orange);
    // Beatloop size ÷2 (dim red – action button)
    midi.sendShortMsg(PUSH2T.PAD_STATIC, PUSH2T.PAD.bldA, PUSH2T.C.red);
    midi.sendShortMsg(PUSH2T.PAD_STATIC, PUSH2T.PAD.bldB, PUSH2T.C.red);
    // Beatloop size ×2 (dim red – action button)
    midi.sendShortMsg(PUSH2T.PAD_STATIC, PUSH2T.PAD.bluA, PUSH2T.C.red);
    midi.sendShortMsg(PUSH2T.PAD_STATIC, PUSH2T.PAD.bluB, PUSH2T.C.red);
    // Beatjump back (teal ◀) and forward (orange ▶)
    midi.sendShortMsg(PUSH2T.PAD_STATIC, PUSH2T.PAD.bjbA, PUSH2T.C.teal);
    midi.sendShortMsg(PUSH2T.PAD_STATIC, PUSH2T.PAD.bjfA, PUSH2T.C.orange);
    midi.sendShortMsg(PUSH2T.PAD_STATIC, PUSH2T.PAD.bjbB, PUSH2T.C.teal);
    midi.sendShortMsg(PUSH2T.PAD_STATIC, PUSH2T.PAD.bjfB, PUSH2T.C.orange);

    // ── CC buttons: load / nav (static dim – always mapped) ──
    // Deck A: CC20 Load  CC21 Prev  CC22 Next
    midi.sendShortMsg(0xB0, 0x14, 64);   // Load A – medium
    midi.sendShortMsg(0xB0, 0x15, 1);    // Load Prev A – dim
    midi.sendShortMsg(0xB0, 0x16, 1);    // Load Next A – dim
    // Deck B: CC24 Load  CC25 Prev  CC26 Next
    midi.sendShortMsg(0xB0, 0x18, 64);   // Load B – medium
    midi.sendShortMsg(0xB0, 0x19, 1);    // Load Prev B – dim
    midi.sendShortMsg(0xB0, 0x1A, 1);    // Load Next B – dim

    // ── Browser toggle CC85 – reflects [Skin] show_maximized_library state ──
    // (falls back gracefully if this control doesn't exist in your skin)
    PUSH2T.safeConnect('[Skin]', 'show_maximized_library', function (v) {
        midi.sendShortMsg(0xB0, 0x55, v ? 127 : 1);
    });

    // ── Gain Reset CC105 / CC109 – bright when gain ≠ 0 dB, dim at unity ──
    PUSH2T.safeConnect('[Channel1]', 'pregain', function (v) {
        midi.sendShortMsg(0xB0, 0x69, Math.abs(v - 1.0) > 0.01 ? 64 : 1);
    });
    PUSH2T.safeConnect('[Channel2]', 'pregain', function (v) {
        midi.sendShortMsg(0xB0, 0x6D, Math.abs(v - 1.0) > 0.01 ? 64 : 1);
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

PUSH2T.cupA = function (ch, ctrl, val) {
    // CUP = CDJ-style cue preview, independent of Preferences > Decks > Cue mode.
    //   Press while playing -> jump to cue and stop (no preview, release = no-op)
    //   Press while stopped -> play from cue (preview)
    //   Release after a preview -> jump back to cue and stop
    if (val > 0) {
        if (engine.getValue('[Channel1]', 'play')) {
            engine.setValue('[Channel1]', 'cue_gotoandstop', 1);
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
    if (val > 0) {
        if (engine.getValue('[Channel2]', 'play')) {
            engine.setValue('[Channel2]', 'cue_gotoandstop', 1);
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

PUSH2T.syncA = function (ch, ctrl, val) {
    if (val > 0) engine.setValue('[Channel1]', 'sync_enabled', !engine.getValue('[Channel1]', 'sync_enabled'));
};
PUSH2T.syncB = function (ch, ctrl, val) {
    if (val > 0) engine.setValue('[Channel2]', 'sync_enabled', !engine.getValue('[Channel2]', 'sync_enabled'));
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
    if (val > 0) engine.setValue(group, 'hotcue_' + num + '_activate', 1);
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

PUSH2T.loopInA  = function (c, t, v) { if (v > 0) engine.setValue('[Channel1]', 'loop_in',  1); };
PUSH2T.loopOutA = function (c, t, v) { if (v > 0) engine.setValue('[Channel1]', 'loop_out', 1); };
PUSH2T.loopInB  = function (c, t, v) { if (v > 0) engine.setValue('[Channel2]', 'loop_in',  1); };
PUSH2T.loopOutB = function (c, t, v) { if (v > 0) engine.setValue('[Channel2]', 'loop_out', 1); };

PUSH2T.beatgridA = function (c, t, v) {
    if (v > 0) engine.setValue('[Channel1]', 'beats_translate_curpos', 1);
};
PUSH2T.beatgridB = function (c, t, v) {
    if (v > 0) engine.setValue('[Channel2]', 'beats_translate_curpos', 1);
};

// ──── ROW 8: Beatloop size +/– and Set Beatloop ──────────────────────────────

PUSH2T.beatloopDecA = function (c, t, v) {
    if (v > 0 && PUSH2T.blIdxA > 0) {
        PUSH2T.blIdxA--;
        midi.sendShortMsg(PUSH2T.PAD_BLINK, PUSH2T.PAD.bldA, PUSH2T.C.orange);
    }
};
PUSH2T.beatloopIncA = function (c, t, v) {
    if (v > 0 && PUSH2T.blIdxA < PUSH2T.BL_SIZES.length - 1) {
        PUSH2T.blIdxA++;
        midi.sendShortMsg(PUSH2T.PAD_BLINK, PUSH2T.PAD.bluA, PUSH2T.C.orange);
    }
};
// Toggle: activates beatloop if off, deactivates (reloop_toggle) if already on
PUSH2T.beatloopSetA = function (c, t, v) {
    if (v > 0) {
        if (engine.getValue('[Channel1]', 'loop_enabled')) {
            engine.setValue('[Channel1]', 'reloop_toggle', 1);
        } else {
            var sz = PUSH2T.BL_SIZES[PUSH2T.blIdxA];
            engine.setValue('[Channel1]', 'beatloop_' + sz + '_activate', 1);
        }
    }
};

PUSH2T.beatloopDecB = function (c, t, v) {
    if (v > 0 && PUSH2T.blIdxB > 0) {
        PUSH2T.blIdxB--;
        midi.sendShortMsg(PUSH2T.PAD_BLINK, PUSH2T.PAD.bldB, PUSH2T.C.orange);
    }
};
PUSH2T.beatloopIncB = function (c, t, v) {
    if (v > 0 && PUSH2T.blIdxB < PUSH2T.BL_SIZES.length - 1) {
        PUSH2T.blIdxB++;
        midi.sendShortMsg(PUSH2T.PAD_BLINK, PUSH2T.PAD.bluB, PUSH2T.C.orange);
    }
};
PUSH2T.beatloopSetB = function (c, t, v) {
    if (v > 0) {
        if (engine.getValue('[Channel2]', 'loop_enabled')) {
            engine.setValue('[Channel2]', 'reloop_toggle', 1);
        } else {
            var sz = PUSH2T.BL_SIZES[PUSH2T.blIdxB];
            engine.setValue('[Channel2]', 'beatloop_' + sz + '_activate', 1);
        }
    }
};

// ──── ROW 7: Beatjump (size = same as current beatloop size) ──────────────────
// Flash white on press, return to static color on release.

PUSH2T.beatjumpBackA = function (c, t, v) {
    if (v > 0) {
        engine.setValue('[Channel1]', 'beatjump_size', PUSH2T.BL_SIZES[PUSH2T.blIdxA]);
        engine.setValue('[Channel1]', 'beatjump_backward', 1);
        midi.sendShortMsg(PUSH2T.PAD_STATIC, PUSH2T.PAD.bjbA, PUSH2T.C.white);
    } else {
        midi.sendShortMsg(PUSH2T.PAD_STATIC, PUSH2T.PAD.bjbA, PUSH2T.C.teal);
    }
};
PUSH2T.beatjumpFwdA = function (c, t, v) {
    if (v > 0) {
        engine.setValue('[Channel1]', 'beatjump_size', PUSH2T.BL_SIZES[PUSH2T.blIdxA]);
        engine.setValue('[Channel1]', 'beatjump_forward', 1);
        midi.sendShortMsg(PUSH2T.PAD_STATIC, PUSH2T.PAD.bjfA, PUSH2T.C.white);
    } else {
        midi.sendShortMsg(PUSH2T.PAD_STATIC, PUSH2T.PAD.bjfA, PUSH2T.C.orange);
    }
};
PUSH2T.beatjumpBackB = function (c, t, v) {
    if (v > 0) {
        engine.setValue('[Channel2]', 'beatjump_size', PUSH2T.BL_SIZES[PUSH2T.blIdxB]);
        engine.setValue('[Channel2]', 'beatjump_backward', 1);
        midi.sendShortMsg(PUSH2T.PAD_STATIC, PUSH2T.PAD.bjbB, PUSH2T.C.white);
    } else {
        midi.sendShortMsg(PUSH2T.PAD_STATIC, PUSH2T.PAD.bjbB, PUSH2T.C.teal);
    }
};
PUSH2T.beatjumpFwdB = function (c, t, v) {
    if (v > 0) {
        engine.setValue('[Channel2]', 'beatjump_size', PUSH2T.BL_SIZES[PUSH2T.blIdxB]);
        engine.setValue('[Channel2]', 'beatjump_forward', 1);
        midi.sendShortMsg(PUSH2T.PAD_STATIC, PUSH2T.PAD.bjfB, PUSH2T.C.white);
    } else {
        midi.sendShortMsg(PUSH2T.PAD_STATIC, PUSH2T.PAD.bjfB, PUSH2T.C.orange);
    }
};

// ──── CC: Load track / prev / next ───────────────────────────────────────────

PUSH2T.loadPrevA = function (c, t, v) {
    if (v > 0) {
        engine.setValue('[Library]', 'MoveUp', 1);
        engine.setValue('[Channel1]', 'LoadSelectedTrack', 1);
    }
};
PUSH2T.loadNextA = function (c, t, v) {
    if (v > 0) {
        engine.setValue('[Library]', 'MoveDown', 1);
        engine.setValue('[Channel1]', 'LoadSelectedTrack', 1);
    }
};
PUSH2T.loadPrevB = function (c, t, v) {
    if (v > 0) {
        engine.setValue('[Library]', 'MoveUp', 1);
        engine.setValue('[Channel2]', 'LoadSelectedTrack', 1);
    }
};
PUSH2T.loadNextB = function (c, t, v) {
    if (v > 0) {
        engine.setValue('[Library]', 'MoveDown', 1);
        engine.setValue('[Channel2]', 'LoadSelectedTrack', 1);
    }
};

// ──── CC: Encoders (relative: 1=CW, 127=CCW) ─────────────────────────────────

PUSH2T.rateA = function (c, t, v) {
    var d   = PUSH2T._relDelta(v) * PUSH2T.RATE_STEP;
    var max = engine.getValue('[Channel1]', 'rateRange') || 0.08;
    engine.setValue('[Channel1]', 'rate',
        Math.max(-max, Math.min(max, engine.getValue('[Channel1]', 'rate') + d)));
};
PUSH2T.rateB = function (c, t, v) {
    var d   = PUSH2T._relDelta(v) * PUSH2T.RATE_STEP;
    var max = engine.getValue('[Channel2]', 'rateRange') || 0.08;
    engine.setValue('[Channel2]', 'rate',
        Math.max(-max, Math.min(max, engine.getValue('[Channel2]', 'rate') + d)));
};

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

PUSH2T.gainResetA = function (c, t, v) { if (v > 0) engine.setValue('[Channel1]', 'pregain', 1.0); };
PUSH2T.gainResetB = function (c, t, v) { if (v > 0) engine.setValue('[Channel2]', 'pregain', 1.0); };

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