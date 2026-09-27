# Mixxx Integration Guide

## Overview

Instead of just screen capture, you can integrate directly with Mixxx using:

1. **MIDI Communication** - Send/receive MIDI to control Mixxx
2. **JavaScript Controller Mapping** - Create a custom Push 2 controller script
3. **OSC (Open Sound Control)** - Network-based control (if enabled)
4. **Custom Rendering** - Draw custom visualizations based on Mixxx data

## Approach 1: MIDI Bridge (Recommended)

Create a Python bridge that:
- Reads Mixxx state via MIDI output
- Sends controls to Mixxx via MIDI input
- Renders custom displays on Push 2

### Benefits
- No screen capture needed
- Access to real-time track data
- Control Mixxx with Push 2 buttons/encoders
- Custom visualizations optimized for 960x160 display

## Approach 2: Create Mixxx Controller Script

Write a JavaScript controller mapping that:
- Communicates with your Python application
- Exposes Mixxx controls
- Sends track metadata

## Available Mixxx Controls

Mixxx exposes hundreds of controls you can read/write:

**Playback:**
- `[ChannelN],play` - Play/pause (1/0)
- `[ChannelN],cue_default` - Cue point
- `[ChannelN],sync_enabled` - Sync on/off

**Track Info:**
- `[ChannelN],track_loaded` - Track loaded (1/0)
- `[ChannelN],duration` - Track duration
- `[ChannelN],artist` - Artist name
- `[ChannelN],title` - Track title
- `[ChannelN],bpm` - BPM

**Mixing:**
- `[ChannelN],volume` - Volume fader (0.0-1.0)
- `[ChannelN],pfl` - Headphone cue
- `[ChannelN],rate` - Tempo slider
- `[Master],crossfader` - Crossfader position

**Waveform:**
- `[ChannelN],playposition` - Current play position (0.0-1.0)
- `[ChannelN],visual_playposition` - Visual position

**Effects:**
- `[EffectRackN_EffectUnitN],group_[ChannelN]_enable` - Effect enable
- `[EffectRackN_EffectUnitN_EffectN],enabled` - Effect on/off

## Implementation Options

### Option 1: MIDI Loopback

```
Mixxx MIDI Out → Python Script → Push 2 Display
Mixxx MIDI In  ← Python Script ← Push 2 Buttons
```

### Option 2: Custom Controller Mapping

Create a Mixxx controller XML/JS that treats Push 2 as a controller:

```javascript
// push2-mixxx-controller.js
var Push2 = {};

Push2.init = function() {
    // Initialize Push 2
    engine.connectControl("[Channel1]", "playposition", Push2.onPlayPositionChanged);
    engine.connectControl("[Channel1]", "bpm", Push2.onBPMChanged);
};

Push2.onPlayPositionChanged = function(value, group, control) {
    // Send position to Python via MIDI
    midi.sendSysexMsg([0xF0, 0x00, ...], value);
};
```

### Option 3: Hybrid Approach

- Screen capture for complex visualizations (waveforms)
- MIDI for track info overlay (text, BPM, time)
- MIDI for button controls (play, cue, effects)

## What You Can Display

Custom rendered displays could show:

1. **Track Info Display**
   - Current track name, artist
   - BPM, key, time remaining
   - Deck indicators

2. **Waveform Display**
   - Custom waveform rendering
   - Beat markers
   - Cue points
   - Loop markers

3. **Mixer Display**
   - VU meters
   - Crossfader position
   - EQ indicators

4. **Effect Display**
   - Active effects
   - Effect parameters
   - Wet/dry mix

## Example: Track Info Display

Instead of screen capture, render track info directly:

```python
import mido
from PIL import Image, ImageDraw, ImageFont

# Read MIDI from Mixxx
with mido.open_input('Mixxx:Output') as inport:
    for msg in inport:
        # Parse Mixxx control messages
        if msg.type == 'control_change':
            if msg.control == 1:  # BPM
                bpm = msg.value
            elif msg.control == 2:  # Playposition
                position = msg.value / 127.0
        
        # Render custom display
        img = render_track_display(bpm, position)
        push2.send_frame(img)
```

## Next Steps

Would you like me to create:

1. **MIDI Bridge** - Python script that reads Mixxx MIDI output and renders custom displays
2. **Controller Mapping** - JavaScript controller that exposes Mixxx data
3. **Hybrid Solution** - Screen capture + MIDI overlays
4. **Full Custom Renderer** - Draw waveforms, track info, etc. from scratch

Which approach interests you most?

## Resources

- Mixxx Controls List: https://manual.mixxx.org/2.3/en/chapters/appendix/mixxx_controls
- MIDI Scripting Wiki: https://github.com/mixxxdj/mixxx/wiki/midi-scripting
- Components JS: https://github.com/mixxxdj/mixxx/wiki/Components-JS
- Controller Mapping: https://mixxx.org/wiki/doku.php/midi_controller_mapping_file_format
