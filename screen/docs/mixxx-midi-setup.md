# Mixxx MIDI Integration Setup

## Overview

Instead of screen capture, you can use MIDI to:
- Read real-time data from Mixxx (BPM, track info, playback state)
- Send controls to Mixxx from Push 2 buttons
- Render custom displays optimized for Push 2's screen

## Installation

### 1. Install MIDI Dependencies

```bash
pip install mido python-rtmidi
```

### 2. Configure Mixxx MIDI Output

1. Open Mixxx
2. Go to **Options → Preferences → Controllers**
3. Enable a MIDI output device (or create a virtual MIDI port)

### Windows: Create Virtual MIDI Port

Download and install **loopMIDI**:
- https://www.tobias-erichsen.de/software/loopmidi.html
- Create a virtual MIDI port named "Mixxx Bridge"

### Linux: Use ALSA Virtual Port

```bash
# ALSA creates virtual ports automatically
# Just configure Mixxx to use them
```

### 3. Enable MIDI in Mixxx

In Mixxx Preferences → Controllers:
- **Output**: Select your MIDI device or virtual port
- **Enable**: Check the box to enable MIDI output
- **Configure**: Map controls you want to monitor

## Usage

### Option 1: MIDI Bridge (Custom Display)

Uses MIDI to read Mixxx state and render custom displays:

```bash
# List available MIDI ports
python mixxx-midi-bridge.py --list-ports

# Run bridge with auto-detection
python mixxx-midi-bridge.py

# Specify MIDI ports
python mixxx-midi-bridge.py --input "Mixxx Output" --output "Mixxx Input"
```

**What it shows:**
- Deck 1 and Deck 2 side-by-side
- BPM display
- Track title and artist (if available via MIDI)
- Play/pause indicators
- Position bars
- Volume meters
- Crossfader position

### Option 2: Screen Capture (Original Method)

Uses screen capture (already working):

```bash
python mixxx-to-push2.py
```

### Option 3: Hybrid Approach

Combine both! Screen capture for waveforms + MIDI overlays for text:

```bash
# TODO: Create hybrid script
python mixxx_hybrid.py
```

## Mixxx MIDI Configuration

To send data from Mixxx via MIDI, you need to map controls:

### 1. Create MIDI Mapping

In Mixxx, go to Options → Preferences → Controllers → [Your Device]

Map these controls to MIDI CC messages:

**Deck 1:**
- Play: Note 0
- Volume: CC 7
- BPM: CC 20
- Position: CC 21

**Deck 2:**
- Play: Note 16
- Volume: CC 8
- BPM: CC 22
- Position: CC 23

**Master:**
- Crossfader: CC 15

### 2. Or Use JavaScript Controller

Create a custom controller script that sends data automatically.

## Receiving Button Presses from Push 2

The bridge can also send MIDI back to Mixxx when you press Push 2 buttons:

```python
# In mixxx-midi-bridge.py
# Press pad → Send MIDI to Mixxx → Control playback
```

This turns Push 2 into a full Mixxx controller!

## Custom Visualizations

You can customize what's displayed by editing `render_display()` in `mixxx-midi-bridge.py`:

**Ideas:**
- Waveform display (draw from position data)
- Beat counter
- Key detection display
- Effect indicators
- BPM sync status
- Loop markers
- Hot cues

## Advantages Over Screen Capture

✅ **Lower latency** - Direct MIDI is faster than screen capture
✅ **Lower CPU usage** - No constant screen grabbing
✅ **Custom layouts** - Design displays optimized for 960x160
✅ **Better text** - Crisp text rendering instead of scaled capture
✅ **Bi-directional** - Control Mixxx with Push 2 buttons
✅ **Track metadata** - Access track info not visible on screen

## Limitations

⚠️ **Waveforms** - MIDI doesn't include waveform data (use screen capture for that)
⚠️ **Setup required** - Need to configure MIDI mappings in Mixxx
⚠️ **Limited data** - Only get what you explicitly map

## Best Approach: Hybrid

Combine both methods:
1. **MIDI** for track info, BPM, time, controls
2. **Screen capture** for waveforms and complex visualizations

This gives you the best of both worlds!

## Troubleshooting

### No MIDI ports found

**Windows:**
- Install loopMIDI to create virtual ports
- Configure Mixxx to use the virtual port

**Linux:**
- ALSA creates ports automatically
- Use `aconnect -l` to see ALSA ports

### MIDI not working

- Check Mixxx preferences → Controllers
- Ensure MIDI output is enabled
- Verify port names with `--list-ports`
- Try a different MIDI device

### Display shows zeros

- MIDI data might not be mapped in Mixxx
- Create a controller mapping (see above)
- Or use the JavaScript controller approach

## Next Steps

Would you like me to create:

1. **JavaScript controller** for Mixxx that auto-sends all data?
2. **Hybrid script** combining screen capture + MIDI overlays?
3. **Interactive setup** to help configure MIDI mappings?
4. **Full Push 2 controller** with button/encoder support?
