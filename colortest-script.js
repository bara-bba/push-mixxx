// ─────────────────────────────────────────────────────────────────────────────
//  colortest-script.js  –  Push 2 palette tester for Mixxx
//  functionprefix: CTEST    |    companion: colortest.midi.xml
//
//  Lights all 64 pads with Push 2 color palette indices:
//    Page 1 (default)    : indices 0..63   (pad 0x24 = 0, 0x25 = 1, ... 0x63 = 63)
//    Page 2 (hold SHIFT) : indices 64..127 (pad 0x24 = 64, ... 0x63 = 127)
//
//  Pressing any pad prints its palette index to the controller debug log so
//  you can read off the exact number for a color you like:
//      mixxx.exe --controllerDebug
//      -> "[CTEST] pad 0x34 = palette index 80"
//
//  SHIFT = CC49 (0x31). Hold it to see page 2, release for page 1.
//
//  Pressing a pad ALSO mirrors that same index onto every CC button used by
//  the real "pusher" mapping, so you can compare a pad's color directly
//  against the button LEDs:
//    - Record (CC86) and Browse/Play (CC85) are full RGB — same 128-color
//      palette as the pads, so they should visually match the pad exactly.
//    - Shift, Delete, Load x6, Gain Reset x2 are monochrome white LEDs —
//      confirmed on hardware: on/off with dimming only, no color variation.
//      The mirrored index still gets sent (harmless), but only brightness
//      is meaningful for these; don't bother picking a "color" for them.
// ─────────────────────────────────────────────────────────────────────────────

var CTEST = {};

CTEST.PAD_STATIC = 0x90;   // NoteOn Ch1 = static pad color
CTEST.PAD_LOW    = 0x24;   // bottom-left pad note
CTEST.PAD_HIGH   = 0x63;   // top-right pad note (0x24 + 63)

// CC buttons used by the real "pusher" mapping, mirrored here for comparison.
CTEST.CC = {
    shift    : 0x31,  // 49  - monochrome
    del      : 0x76,  // 118 - monochrome
    record   : 0x56,  // 86  - RGB
    browse   : 0x55,  // 85  - RGB (Push 2 Play button)
    loadA    : 0x14,  // 20  - monochrome
    loadPrevA: 0x15,  // 21  - monochrome
    loadNextA: 0x16,  // 22  - monochrome
    loadB    : 0x18,  // 24  - monochrome
    loadPrevB: 0x19,  // 25  - monochrome
    loadNextB: 0x1A,  // 26  - monochrome
    gainRstA : 0x69,  // 105 - monochrome
    gainRstB : 0x6D   // 109 - monochrome
};
CTEST.CC_RGB  = [CTEST.CC.record, CTEST.CC.browse];
CTEST.CC_MONO = [
    CTEST.CC.shift, CTEST.CC.del,
    CTEST.CC.loadA, CTEST.CC.loadPrevA, CTEST.CC.loadNextA,
    CTEST.CC.loadB, CTEST.CC.loadPrevB, CTEST.CC.loadNextB,
    CTEST.CC.gainRstA, CTEST.CC.gainRstB
];

CTEST.shiftActive = false;

// ─── INIT / SHUTDOWN ─────────────────────────────────────────────────────────

CTEST.init = function (id, debugging) {
    CTEST.drawPage(0);   // page 1: indices 0..63
    // Start every CC button at index 0 (off) until a pad is pressed.
    CTEST.CC_RGB.concat(CTEST.CC_MONO).forEach(function (cc) {
        midi.sendShortMsg(0xB0, cc, 0);
    });
    print('[CTEST] Color test loaded. Page 1 = colors 0-63. Hold SHIFT (CC49) for 64-127.');
    print('[CTEST] Press any pad to print its color index and mirror it onto the CC buttons.');
};

CTEST.shutdown = function () {
    // Turn every pad off
    for (var n = CTEST.PAD_LOW; n <= CTEST.PAD_HIGH; n++) {
        midi.sendShortMsg(CTEST.PAD_STATIC, n, 0);
    }
    // Turn every mirrored CC button off
    CTEST.CC_RGB.concat(CTEST.CC_MONO).forEach(function (cc) {
        midi.sendShortMsg(0xB0, cc, 0);
    });
    print('[CTEST] Color test shut down.');
};

// ─── PAGE DRAWING ─────────────────────────────────────────────────────────────

// page 0 -> indices 0..63, page 1 -> indices 64..127
CTEST.drawPage = function (page) {
    var base = page * 64;
    for (var n = CTEST.PAD_LOW; n <= CTEST.PAD_HIGH; n++) {
        var colorIndex = base + (n - CTEST.PAD_LOW);
        midi.sendShortMsg(CTEST.PAD_STATIC, n, colorIndex);
    }
};

// ─── HANDLERS ─────────────────────────────────────────────────────────────────

// Any pad: print which palette index it's currently showing, and mirror
// that same index onto every CC button so it can be compared side by side.
CTEST.pad = function (channel, control, value, status) {
    if (value === 0) { return; }   // ignore release
    var base  = CTEST.shiftActive ? 64 : 0;
    var index = base + (control - CTEST.PAD_LOW);
    var row   = Math.floor((control - CTEST.PAD_LOW) / 8) + 1;
    var col   = ((control - CTEST.PAD_LOW) % 8) + 1;
    print('[CTEST] pad 0x' + control.toString(16) +
          ' (row ' + row + ', col ' + col + ') = palette index ' + index +
          ' -> mirrored onto Record/Browse (RGB) + Shift/Delete/Load/GainReset (mono)');

    CTEST.CC_RGB.forEach(function (cc)  { midi.sendShortMsg(0xB0, cc, index); });
    CTEST.CC_MONO.forEach(function (cc) { midi.sendShortMsg(0xB0, cc, index); });
};

// SHIFT (CC49): hold for page 2, release for page 1.
CTEST.shift = function (channel, control, value) {
    if (value > 0) {
        CTEST.shiftActive = true;
        CTEST.drawPage(1);    // indices 64..127
        print('[CTEST] Page 2: colors 64-127');
    } else {
        CTEST.shiftActive = false;
        CTEST.drawPage(0);    // indices 0..63
        print('[CTEST] Page 1: colors 0-63');
    }
};