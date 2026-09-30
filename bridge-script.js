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
//    type 0x01 TRACK: deck(0/1) playing(0/1) bpmHi bpmLo posHi posLo durHi durLo
//         bpm is bpm*10 as a 14-bit value (hi/lo 7-bit); pos is playposition
//         (0.0-1.0) scaled to 14-bit; dur is track duration in whole seconds
//         (14-bit, up to ~4.5h). NOTE: Mixxx does not expose track title/
//         artist to controller scripts at all (engine.getValue has no such
//         control - see github.com/mixxxdj/mixxx/issues/6898, open since
//         2013, unresolved). push-screen's mixxx-midi-bridge.py instead
//         identifies the loaded track by matching (duration, bpm) against
//         Mixxx's own library database and reads title/artist/art from there.
//    type 0x02 MIXER: crossfader(0-127)
//    type 0x03 SCENE: sceneId (0=none 1=browse 2=device 3=mix 4=clip) —
//         pusher-script.js's PUSH2T.scene. Each controller has its own JS
//         engine, so it's read from [Skin],pusher_scene, which
//         pusher-script.js publishes and the Pusher160 skin creates.
//    type 0x04 FX: unit(0/1) mixKnob(0-127) eff1On eff2On eff3On (0/1 each)
//
//  Device vs Browse page switching happens inside the Pusher160 skin itself
//  (same control); push-screen only needs SCENE for its Mix FX overlay.
// ─────────────────────────────────────────────────────────────────────────────

var PUSH2BRIDGE = {};

PUSH2BRIDGE.SYSEX_ID = 0x7D;
PUSH2BRIDGE.TYPE_TRACK = 0x01;
PUSH2BRIDGE.TYPE_MIXER = 0x02;
PUSH2BRIDGE.TYPE_SCENE = 0x03;
PUSH2BRIDGE.TYPE_FX = 0x04;
PUSH2BRIDGE.POLL_MS = 40; // 25Hz - smooth waveform/position scroll, cheap sysex payload
PUSH2BRIDGE.SCENE_NAMES = ['none', 'browse', 'device', 'mix', 'clip'];
PUSH2BRIDGE.sceneId = 0;
PUSH2BRIDGE.sceneConn = null;
PUSH2BRIDGE.sceneRetryTicks = 0;

PUSH2BRIDGE.split14 = function(value) {
    var v = Math.max(0, Math.min(16383, Math.round(value)));
    return [(v >> 7) & 0x7F, v & 0x7F];
};

PUSH2BRIDGE.sendTrack = function(deckIndex, group) {
    var playing = engine.getValue(group, "play") ? 1 : 0;
    var bpm = engine.getValue(group, "bpm") || 0;
    var pos = engine.getValue(group, "playposition") || 0;
    var duration = engine.getValue(group, "duration") || 0;

    var bpm14 = PUSH2BRIDGE.split14(bpm * 10);
    var pos14 = PUSH2BRIDGE.split14(pos * 16383);
    var dur14 = PUSH2BRIDGE.split14(duration);

    var msg = [0xF0, PUSH2BRIDGE.SYSEX_ID, PUSH2BRIDGE.TYPE_TRACK, deckIndex,
        playing, bpm14[0], bpm14[1], pos14[0], pos14[1], dur14[0], dur14[1], 0xF7];

    midi.sendSysexMsg(msg, msg.length);
};

PUSH2BRIDGE.sendMixer = function() {
    var cf = engine.getValue("[Master]", "crossfader"); // -1.0..1.0
    var cf127 = Math.max(0, Math.min(127, Math.round((cf + 1) * 63.5)));
    midi.sendSysexMsg([0xF0, PUSH2BRIDGE.SYSEX_ID, PUSH2BRIDGE.TYPE_MIXER, cf127, 0xF7], 5);
};

// [Skin],pusher_scene only exists once the skin has loaded, which is after
// this script's init - connect lazily, retrying every ~2s until it exists.
PUSH2BRIDGE.connectScene = function() {
    if (PUSH2BRIDGE.sceneConn || PUSH2BRIDGE.sceneRetryTicks-- > 0) { return; }
    PUSH2BRIDGE.sceneRetryTicks = 50;
    PUSH2BRIDGE.sceneConn = engine.makeConnection('[Skin]', 'pusher_scene', function(v) {
        PUSH2BRIDGE.sceneId = Math.round(v);
    });
    if (PUSH2BRIDGE.sceneConn) { PUSH2BRIDGE.sceneConn.trigger(); }
};

PUSH2BRIDGE.currentScene = function() {
    return PUSH2BRIDGE.SCENE_NAMES[PUSH2BRIDGE.sceneId] || 'none';
};

PUSH2BRIDGE.sendScene = function() {
    midi.sendSysexMsg([0xF0, PUSH2BRIDGE.SYSEX_ID, PUSH2BRIDGE.TYPE_SCENE, PUSH2BRIDGE.sceneId, 0xF7], 5);
};

PUSH2BRIDGE.sendFxUnit = function(unitIndex) {
    var unit = unitIndex + 1;
    var unitGroup = '[EffectRack1_EffectUnit' + unit + ']';
    var mix = engine.getValue(unitGroup, 'mix') || 0; // 0.0-1.0
    var mix127 = Math.max(0, Math.min(127, Math.round(mix * 127)));

    var effOn = [0, 0, 0];
    for (var n = 1; n <= 3; n++) {
        var effGroup = '[EffectRack1_EffectUnit' + unit + '_Effect' + n + ']';
        effOn[n - 1] = engine.getValue(effGroup, 'enabled') ? 1 : 0;
    }

    midi.sendSysexMsg([0xF0, PUSH2BRIDGE.SYSEX_ID, PUSH2BRIDGE.TYPE_FX, unitIndex,
        mix127, effOn[0], effOn[1], effOn[2], 0xF7], 9);
};

PUSH2BRIDGE.tick = function() {
    PUSH2BRIDGE.connectScene();
    PUSH2BRIDGE.sendTrack(0, "[Channel1]");
    PUSH2BRIDGE.sendTrack(1, "[Channel2]");
    PUSH2BRIDGE.sendMixer();
    PUSH2BRIDGE.sendScene();
    if (PUSH2BRIDGE.currentScene() === 'mix') {
        PUSH2BRIDGE.sendFxUnit(0);
        PUSH2BRIDGE.sendFxUnit(1);
    }
};

PUSH2BRIDGE.init = function() {
    engine.beginTimer(PUSH2BRIDGE.POLL_MS, PUSH2BRIDGE.tick, false);
};

PUSH2BRIDGE.shutdown = function() {};
