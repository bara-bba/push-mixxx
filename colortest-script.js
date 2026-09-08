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
// ─────────────────────────────────────────────────────────────────────────────

var CTEST = {};

CTEST.PAD_STATIC = 0x90;   // NoteOn Ch1 = static pad color
CTEST.PAD_LOW    = 0x24;   // bottom-left pad note
CTEST.PAD_HIGH   = 0x63;   // top-right pad note (0x24 + 63)

CTEST.shiftActive = false;

// ─── INIT / SHUTDOWN ─────────────────────────────────────────────────────────

CTEST.init = function (id, debugging) {
    CTEST.drawPage(0);   // page 1: indices 0..63
    print('[CTEST] Color test loaded. Page 1 = colors 0-63. Hold SHIFT (CC49) for 64-127.');
    print('[CTEST] Press any pad to print its color index.');
};

CTEST.shutdown = function () {
    // Turn every pad off
    for (var n = CTEST.PAD_LOW; n <= CTEST.PAD_HIGH; n++) {
        midi.sendShortMsg(CTEST.PAD_STATIC, n, 0);
    }
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

// Any pad: print which palette index it's currently showing.
CTEST.pad = function (channel, control, value, status) {
    if (value === 0) { return; }   // ignore release
    var base  = CTEST.shiftActive ? 64 : 0;
    var index = base + (control - CTEST.PAD_LOW);
    var row   = Math.floor((control - CTEST.PAD_LOW) / 8) + 1;
    var col   = ((control - CTEST.PAD_LOW) % 8) + 1;
    print('[CTEST] pad 0x' + control.toString(16) +
          ' (row ' + row + ', col ' + col + ') = palette index ' + index);
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