// ─────────────────────────────────────────────────────────────────────────────
//  bridge-script.js  –  Mixxx -> push-screen display bridge (functionprefix: PUSH2BRIDGE)
//  Companion to: bridge.midi.xml
//  Not part of the Push 2 hardware mapping (pusher.midi.xml/pusher-script.js) —
//  this is a second, output-only Mixxx controller bound to a virtual MIDI port
//  (loopMIDI "Mixxx Bridge", see push-screen/docs/mixxx-midi-setup.md). It polls
//  deck/mixer state and pushes it as SysEx to whatever reads that port —
//  push-screen's mixxx-midi-bridge.py renders it on the Push 2 screen.
//
//  SysEx frame: F0 7D <type> <deck> <payload...> F7
//    manufacturer id 0x7D = non-commercial/educational (MIDI spec reserved)
//    type 0x01 TRACK: deck(0/1) playing(0/1) bpmHi bpmLo posHi posLo
//                      title-bytes(7-bit, <=24) 0x00 artist-bytes(7-bit, <=24)
//         bpm is bpm*10 as a 14-bit value (hi/lo 7-bit); pos is playposition
//         (0.0-1.0) scaled to 14-bit.
//    type 0x02 MIXER: crossfader(0-127)
// ─────────────────────────────────────────────────────────────────────────────

var PUSH2BRIDGE = {};

PUSH2BRIDGE.SYSEX_ID = 0x7D;
PUSH2BRIDGE.TYPE_TRACK = 0x01;
PUSH2BRIDGE.TYPE_MIXER = 0x02;
PUSH2BRIDGE.POLL_MS = 200;
PUSH2BRIDGE.MAX_TEXT = 24;

PUSH2BRIDGE.encodeText = function(str) {
    var out = [];
    if (!str) return out;
    for (var i = 0; i < str.length && out.length < PUSH2BRIDGE.MAX_TEXT; i++) {
        var code = str.charCodeAt(i);
        out.push(code < 128 ? code : 0x3F); // '?' for non-ASCII
    }
    return out;
};

PUSH2BRIDGE.split14 = function(value) {
    var v = Math.max(0, Math.min(16383, Math.round(value)));
    return [(v >> 7) & 0x7F, v & 0x7F];
};

PUSH2BRIDGE.sendTrack = function(deckIndex, group) {
    var playing = engine.getValue(group, "play") ? 1 : 0;
    var bpm = engine.getValue(group, "bpm") || 0;
    var pos = engine.getValue(group, "playposition") || 0;
    var title = engine.getValue(group, "title") || "";
    var artist = engine.getValue(group, "artist") || "";

    var bpm14 = PUSH2BRIDGE.split14(bpm * 10);
    var pos14 = PUSH2BRIDGE.split14(pos * 16383);

    var msg = [0xF0, PUSH2BRIDGE.SYSEX_ID, PUSH2BRIDGE.TYPE_TRACK, deckIndex,
        playing, bpm14[0], bpm14[1], pos14[0], pos14[1]];
    msg = msg.concat(PUSH2BRIDGE.encodeText(title));
    msg.push(0x00);
    msg = msg.concat(PUSH2BRIDGE.encodeText(artist));
    msg.push(0xF7);

    midi.sendSysexMsg(msg, msg.length);
};

PUSH2BRIDGE.sendMixer = function() {
    var cf = engine.getValue("[Master]", "crossfader"); // -1.0..1.0
    var cf127 = Math.max(0, Math.min(127, Math.round((cf + 1) * 63.5)));
    midi.sendSysexMsg([0xF0, PUSH2BRIDGE.SYSEX_ID, PUSH2BRIDGE.TYPE_MIXER, cf127, 0xF7], 5);
};

PUSH2BRIDGE.tick = function() {
    PUSH2BRIDGE.sendTrack(0, "[Channel1]");
    PUSH2BRIDGE.sendTrack(1, "[Channel2]");
    PUSH2BRIDGE.sendMixer();
};

PUSH2BRIDGE.init = function() {
    engine.beginTimer(PUSH2BRIDGE.POLL_MS, PUSH2BRIDGE.tick, false);
};

PUSH2BRIDGE.shutdown = function() {};
