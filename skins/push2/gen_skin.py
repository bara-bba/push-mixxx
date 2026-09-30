"""Generates the Pusher160 skin's two pages + its whole stylesheet into this
folder's skin.xml (everything from the BROWSE PAGE marker to the end, and the
<Style> CDATA). Only the header comment and manifest are hand-written.
Install the skin by copying this folder to %LOCALAPPDATA%/Mixxx/skins/Pusher160.

Both decks come from the same template so they stay identical - Mixxx
templates don't work for user skins, so we generate instead.
"""
import pathlib

from PIL import Image

SKIN_DIR = pathlib.Path(__file__).resolve().parent
SKIN = SKIN_DIR / 'skin.xml'

DECKS = [
    {'g': '[Channel1]', 'n': 1, 's': 'A', 'color': '#3cd264', 'hi': '#8be6a4', 'lo': '#1c7a38',
     'cue': (60, 210, 100), 'loop': (26, 128, 60)},
    {'g': '[Channel2]', 'n': 2, 's': 'B', 'color': '#aa50eb', 'hi': '#cf9bf5', 'lo': '#5e2a85',
     'cue': (170, 80, 235), 'loop': (104, 44, 150)},
]
LOOP_SIZES = [('1/4', '0.25'), ('1/2', '0.5'), ('1', '1'), ('2', '2'), ('4', '4'), ('8', '8'), ('16', '16')]
ROW_H = 24
# ~70px-wide pads: 6px digit + 17 x 3px nbsp centers the digit ~7px from the left edge
HOTCUE_PAD = '&#160;' * 17
BROWSE_HEADER_H = 36
WAVE_H = (160 - BROWSE_HEADER_H) // 2
DEVICE_SCENE = 2  # [Skin],pusher_scene value for push-mixxx's Device scene


def hspace(w):
    return f'<WidgetGroup><Size>{w}f,1min</Size></WidgetGroup>'


def vspace(h):
    return f'<WidgetGroup><Size>1min,{h}f</Size></WidgetGroup>'


def states(text, n):
    return ''.join(f'<State><Number>{i}</Number><Text>{text}</Text></State>' for i in range(n))


def fixed_group(obj, layout, w, h, children, wpolicy='f'):
    maxw = 10000 if wpolicy == 'me' else w
    name = f'<ObjectName>{obj}</ObjectName>' if obj else ''
    return (f'<WidgetGroup>{name}<Layout>{layout}</Layout><SizePolicy>{wpolicy},f</SizePolicy>'
            f'<MinimumSize>{w},{h}</MinimumSize><MaximumSize>{maxw},{h}</MaximumSize>'
            f'<Children>{children}</Children></WidgetGroup>')


def scene_visibility(show_on_device):
    transform = f'<IsEqual>{DEVICE_SCENE}</IsEqual>' + ('' if show_on_device else '<Not/>')
    return (f'<Connection><ConfigKey>[Skin],pusher_scene</ConfigKey>'
            f'<Transform>{transform}</Transform><BindProperty>visible</BindProperty></Connection>')


# ---------------------------------------------------------------- widgets ----

def indicator(obj, g, key, text, w, n=2, expand=False, click=None):
    """Display-only button lit by a control; optional click connection."""
    policy = 'me,f' if expand else 'f,f'
    maxw = 10000 if expand else w
    click_conn = ''
    if click:
        click_conn = (f'<Connection><ConfigKey>{g},{click}</ConfigKey>'
                      '<ConnectValueToWidget>false</ConnectValueToWidget>'
                      '<ButtonState>LeftButton</ButtonState></Connection>')
    return (f'<PushButton><ObjectName>{obj}</ObjectName><SizePolicy>{policy}</SizePolicy>'
            f'<MinimumSize>{w},{ROW_H}</MinimumSize><MaximumSize>{maxw},{ROW_H}</MaximumSize>'
            f'<NumberStates>{n}</NumberStates>{states(text, n)}'
            f'<Connection><ConfigKey>{g},{key}</ConfigKey>'
            '<ConnectValueFromWidget>false</ConnectValueFromWidget></Connection>'
            f'{click_conn}</PushButton>')


def cover(d, size):
    return (f'<WidgetGroup><ObjectName>DkCover{d["s"]}</ObjectName><Layout>horizontal</Layout><Size>{size}f,{size}f</Size>'
            f'<Children><CoverArt><Group>{d["g"]}</Group><SizePolicy>me,me</SizePolicy></CoverArt></Children></WidgetGroup>')


def track_prop(obj, g, prop, h):
    return (f'<TrackProperty><ObjectName>{obj}</ObjectName><Group>{g}</Group><Property>{prop}</Property>'
            f'<SizePolicy>me,f</SizePolicy><MinimumSize>10,{h}</MinimumSize><MaximumSize>10000,{h}</MaximumSize>'
            '<Elide>right</Elide></TrackProperty>')


# NumberPos ignores its <Connection> and always follows the global
# [Controls],ShowDurationRemaining mode - set to 2 (elapsed AND remaining, one
# wrapped two-line string) in the manifest. Each widget is clipped to one of
# the two lines via fixed height + vertical alignment (see CSS).
def time_remaining(d):
    return (f'<NumberPos><ObjectName>DkTimeRemain</ObjectName><Group>{d["g"]}</Group><Channel>{d["n"]}</Channel>'
            '<SizePolicy>f,f</SizePolicy><MinimumSize>74,24</MinimumSize><MaximumSize>74,24</MaximumSize></NumberPos>')


def time_elapsed(d):
    # narrow enough (44px) that the 12px 'elapsed  -remaining' string wraps
    return fixed_group('', 'horizontal', 74, 16, hspace(30) + (
        f'<NumberPos><ObjectName>DkTimeElapsed</ObjectName><Group>{d["g"]}</Group><Channel>{d["n"]}</Channel>'
        '<SizePolicy>f,f</SizePolicy><MinimumSize>44,16</MinimumSize><MaximumSize>44,16</MaximumSize></NumberPos>'))


def bpm(d):
    return (f'<NumberBpm><ObjectName>DkBpm</ObjectName><Group>{d["g"]}</Group><SizePolicy>f,f</SizePolicy>'
            '<MinimumSize>62,20</MinimumSize><MaximumSize>62,20</MaximumSize><NumberOfDigits>2</NumberOfDigits>'
            f'<Connection><ConfigKey>{d["g"]},visual_bpm</ConfigKey></Connection></NumberBpm>')


def deck_letter(d, h):
    return (f'<Label><ObjectName>DkLetter{d["s"]}</ObjectName><Text>{d["s"]}</Text><SizePolicy>f,f</SizePolicy>'
            f'<MinimumSize>30,{h}</MinimumSize><MaximumSize>30,{h}</MaximumSize></Label>')


HOTCUE_MARK = ('<DefaultMark><Align>top</Align><Color>#1fb5e6</Color><TextColor>#000000</TextColor>'
               '<Text> %1 </Text></DefaultMark>')
LOOP_RANGE = ('<MarkRange><StartControl>loop_start_position</StartControl><EndControl>loop_end_position</EndControl>'
              '<EnabledControl>loop_enabled</EnabledControl><Color>#5aa832</Color><Opacity>0.6</Opacity>'
              '<DisabledColor>#ffffff</DisabledColor><DisabledOpacity>0.25</DisabledOpacity></MarkRange>')


# ------------------------------------------------------------ browse page ----

def browse_header(d):
    """Compact Traktor deck header: cover, title/artist, remaining, BPM, letter."""
    g, s, H = d['g'], d['s'], BROWSE_HEADER_H
    return (f'<WidgetGroup><ObjectName>DeckPanel{s}</ObjectName><Layout>horizontal</Layout><SizePolicy>me,f</SizePolicy>'
            f'<MinimumSize>100,{H}</MinimumSize><MaximumSize>10000,{H}</MaximumSize><Children>'
            + hspace(6)
            + fixed_group('', 'vertical', 32, H, vspace(2) + cover(d, 32))
            + hspace(8)
            + fixed_group('', 'vertical', 10, H, vspace(1) + track_prop('DkTitle', g, 'title', 18)
                          + track_prop('DkArtist', g, 'artist', 15), wpolicy='me')
            + hspace(6)
            + fixed_group('', 'vertical', 74, H, vspace(6) + time_remaining(d))
            + hspace(8)
            + fixed_group('', 'vertical', 62, H, vspace(8) + bpm(d))
            + hspace(4)
            + deck_letter(d, H)
            + hspace(2)
            + '</Children></WidgetGroup>')


def waveform(d, mark_align):
    """Full-width scrolling waveform. A marks on top, B on the bottom, so labels
    never collide on the shared seam used for beatmatching."""
    g, s = d['g'], d['s']
    visual = (f'<Visual><ObjectName>Wave{s}</ObjectName><Group>{g}</Group><SizePolicy>me,me</SizePolicy>'
              f'<SignalColor>{d["color"]}</SignalColor><SignalHighColor>{d["hi"]}</SignalHighColor>'
              f'<SignalMidColor>{d["color"]}</SignalMidColor><SignalLowColor>{d["lo"]}</SignalLowColor>'
              '<AxesColor></AxesColor><BeatColor>#777777</BeatColor><PlayPosColor>#ffffff</PlayPosColor>'
              '<BgColor>#111111</BgColor><EndOfTrackColor>#e8453c</EndOfTrackColor>'
              + HOTCUE_MARK.replace('<Align>top</Align>', f'<Align>{mark_align}</Align>')
              + f'<Mark><Control>cue_point</Control><Text> C </Text><Align>{mark_align}</Align>'
                '<Color>#e8a33a</Color><TextColor>#000000</TextColor></Mark>'
              + LOOP_RANGE
              + f'<Mark><Control>loop_start_position</Control><Text>IN</Text><Align>{mark_align}</Align>'
                '<Color>#5aa832</Color><TextColor>#ffffff</TextColor></Mark>'
              + f'<Mark><Control>loop_end_position</Control><Text>OUT</Text><Align>{mark_align}</Align>'
                '<Color>#5aa832</Color><TextColor>#ffffff</TextColor></Mark>'
              '</Visual>')
    # Wrapped + height-capped: <MaximumSize> on Visual itself isn't respected.
    return fixed_group(f'Wave{s}Box', 'horizontal', 960, WAVE_H, visual)


BROWSE = f'''    <!-- ===== BROWSE PAGE (shown for every push-mixxx scene except Device):
         Traktor-style deck headers, then the two waveforms stacked edge to
         edge so a beat line crossing the seam is visible for beatmatching.
         GENERATED by gen_skin.py. ===== -->
    <WidgetGroup>
      <ObjectName>BrowsePage</ObjectName>
      <Layout>vertical</Layout>
      <Size>960f,160f</Size>
      <MaximumSize>960,160</MaximumSize>
      {scene_visibility(show_on_device=False)}
      <Children>
{fixed_group('BrHeaderRow', 'horizontal', 960, BROWSE_HEADER_H, browse_header(DECKS[0]) + hspace(2) + browse_header(DECKS[1]))}
{waveform(DECKS[0], 'top')}
{waveform(DECKS[1], 'bottom')}
      </Children>
    </WidgetGroup>

'''


# ------------------------------------------------------------ device page ----

def device_deck(d):
    g, s, n = d['g'], d['s'], d['n']

    header = fixed_group('DkHeader', 'horizontal', 100, 48, ''.join([
        cover(d, 48),
        hspace(8),
        fixed_group('DkTextCol', 'vertical', 10, 48, track_prop('DkTitle', g, 'title', 18)
                    + track_prop('DkArtist', g, 'artist', 15) + track_prop('DkAlbum', g, 'album', 15), wpolicy='me'),
        hspace(6),
        fixed_group('DkTimeCol', 'vertical', 74, 48, time_remaining(d) + time_elapsed(d) + vspace(8)),
        hspace(8),
        fixed_group('DkBpmCol', 'vertical', 62, 48, bpm(d) + fixed_group('', 'horizontal', 62, 14,
            f'<NumberRate><ObjectName>DkRate</ObjectName><Channel>{n}</Channel><SizePolicy>f,f</SizePolicy>'
            '<MinimumSize>52,14</MinimumSize><MaximumSize>52,14</MaximumSize><NumberOfDigits>1</NumberOfDigits></NumberRate>'
            '<Label><ObjectName>DkRatePct</ObjectName><Text>%</Text><SizePolicy>f,f</SizePolicy>'
            '<MinimumSize>10,14</MinimumSize><MaximumSize>10,14</MaximumSize></Label>')
            + f'<NumberBpm><ObjectName>DkFileBpm</ObjectName><Group>{g}</Group><SizePolicy>f,f</SizePolicy>'
              '<MinimumSize>62,14</MinimumSize><MaximumSize>62,14</MaximumSize><NumberOfDigits>2</NumberOfDigits>'
              f'<Connection><ConfigKey>{g},file_bpm</ConfigKey></Connection></NumberBpm>'),
    ]), wpolicy='me')

    overview = fixed_group('DkOverviewBox', 'horizontal', 100, 38, (
        f'<Overview><Group>{g}</Group><SizePolicy>me,me</SizePolicy>'
        '<BgColor>#111111</BgColor>'
        f'<SignalColor>{d["color"]}</SignalColor>'
        '<PlayedOverlayColor>#000000a0</PlayedOverlayColor>'
        '<PlayPosColor>#ffffff</PlayPosColor>'
        '<EndOfTrackColor>#e8453c</EndOfTrackColor>'
        + HOTCUE_MARK
        + '<Mark><Control>cue_point</Control><Align>bottom</Align><Color>#e8a33a</Color><TextColor>#000000</TextColor><Text> C </Text></Mark>'
        + LOOP_RANGE
        + '</Overview>'), wpolicy='me')

    ctrl_parts = [
        indicator('DkPlay', g, 'play_indicator', '&#9654;', 34),
        hspace(2), indicator('DkCue', g, 'cue_indicator', 'CUE', 34),
        hspace(2), indicator('DkKey', g, 'keylock', 'KEY', 34),
        hspace(2), indicator('DkSync', g, 'sync_enabled', 'SYNC', 38, click='sync_enabled'),
        hspace(2), indicator('DkLead', g, 'sync_leader', 'MASTER', 48, n=3),
        hspace(8),
    ]
    for i, (label, val) in enumerate(LOOP_SIZES):
        if i:
            ctrl_parts.append(hspace(1))
        ctrl_parts.append(indicator(f'DkLoopSz{i}', g, 'beatloop_size', label, 22, n=64,
                                    expand=True, click=f'beatloop_{val}_activate'))
    ctrl_parts += [hspace(8), indicator('DkLoopAct', g, 'loop_enabled', 'ACTIVE', 50)]
    ctrl = fixed_group('DkCtrlRow', 'horizontal', 100, ROW_H, ''.join(ctrl_parts), wpolicy='me')

    cues = []
    for i in range(1, 7):
        if i > 1:
            cues.append(hspace(2))
        cue_states = ''.join(f'<State><Number>{k}</Number><Text>{i}{HOTCUE_PAD}</Text></State>' for k in range(3))
        cues.append(f'<HotcueButton><ObjectName>HotcueButton</ObjectName><Group>{g}</Group><Hotcue>{i}</Hotcue>'
                    f'<SizePolicy>me,f</SizePolicy><MinimumSize>30,{ROW_H}</MinimumSize><MaximumSize>10000,{ROW_H}</MaximumSize>'
                    f'<NumberStates>3</NumberStates>{cue_states}</HotcueButton>')
    hotcues = fixed_group('DkHotcueRow', 'horizontal', 100, ROW_H, ''.join(cues), wpolicy='me')

    main_col = ('<WidgetGroup><ObjectName>DkMain</ObjectName><Layout>vertical</Layout><SizePolicy>me,me</SizePolicy><Children>'
                + vspace(4) + header + vspace(4) + overview + vspace(4) + ctrl + vspace(4) + hotcues
                + '</Children></WidgetGroup>')

    side_col = fixed_group('DkSide', 'vertical', 30, 160, ''.join([
        vspace(2),
        deck_letter(d, 32),
        vspace(6),
        fixed_group('', 'horizontal', 30, 104, ''.join([
            hspace(6),
            f'<SliderComposed><ObjectName>DkPitch</ObjectName><TooltipId>rate</TooltipId><Size>18f,104f</Size>'
            f'<Slider scalemode="STRETCH">image/pitch-track-{s.lower()}.svg</Slider>'
            f'<Handle scalemode="STRETCH_ASPECT">image/pitch-handle-{s.lower()}.svg</Handle>'
            f'<Connection><ConfigKey>{g},rate</ConfigKey></Connection></SliderComposed>',
            hspace(6),
        ])),
    ]))

    return (f'<!-- DECK {s} -->'
            f'<WidgetGroup><ObjectName>DeckPanel{s}</ObjectName><Layout>horizontal</Layout><SizePolicy>me,me</SizePolicy><Children>'
            + hspace(6) + main_col + hspace(6) + side_col + hspace(2)
            + '</Children></WidgetGroup>')


EXPANDED = f'''    <!-- ===== DEVICE PAGE (ExpandedRow, shown while [Skin],pusher_scene is
         the Device scene): Traktor-style expanded decks. GENERATED by
         gen_skin.py. ===== -->
    <WidgetGroup>
      <ObjectName>ExpandedRow</ObjectName>
      <Layout>horizontal</Layout>
      <Size>960f,160f</Size>
      <MaximumSize>960,160</MaximumSize>
      {scene_visibility(show_on_device=True)}
      <Children>
{device_deck(DECKS[0])}
{hspace(2)}
{device_deck(DECKS[1])}
      </Children>
    </WidgetGroup>

  </Children>
</skin>
'''


# -------------------------------------------------------------------- CSS ----

BASE_BTNS = ['DkPlay', 'DkCue', 'DkKey', 'DkSync', 'DkLead', 'DkLoopAct'] + [f'DkLoopSz{i}' for i in range(len(LOOP_SIZES))]
loop_sel = ',\n'.join(f'#DkLoopSz{i}[value="{v}"]' for i, (_, v) in enumerate(LOOP_SIZES))

CSS = f'''
/* GENERATED by gen_skin.py - edit the generator, not this block. */
* {{ font-family: "Segoe UI", "Open Sans", "DejaVu Sans", "Ubuntu", sans-serif; }}

#Mixxx, WWidgetGroup {{ background-color: #000000; }}
WLabel, WTrackProperty, WNumberBpm, WNumberPos {{ color: #ffffff; }}

/* Deck panels (both pages): Traktor dark gray */
#DeckPanelA, #DeckPanelB, #DeckPanelA WWidgetGroup, #DeckPanelB WWidgetGroup {{ background-color: #1b1b1b; }}

#DkCoverA, #DkCoverB {{ border: 1px solid #000000; }}

#DkTitle {{ color: #dcdcdc; font-size: 14px; font-weight: bold; qproperty-alignment: 'AlignLeft|AlignVCenter'; }}
#DkArtist {{ color: #a0a0a0; font-size: 12px; qproperty-alignment: 'AlignLeft|AlignVCenter'; }}
#DkAlbum {{ color: #767676; font-size: 12px; qproperty-alignment: 'AlignLeft|AlignVCenter'; }}

#DkTimeRemain, #DkTimeElapsed {{ qproperty-wordWrap: true; padding: 0; }}
#DkTimeRemain {{ color: #e6e6e6; font-size: 17px; qproperty-alignment: 'AlignRight|AlignBottom'; }}
#DkTimeElapsed {{ color: #9a9a9a; font-size: 12px; qproperty-alignment: 'AlignRight|AlignTop'; }}

#DkBpm {{ color: #e6e6e6; font-size: 17px; qproperty-alignment: 'AlignRight|AlignVCenter'; }}
#DkRatePct {{ color: #9a9a9a; font-size: 12px; qproperty-alignment: 'AlignRight|AlignVCenter'; }}
#DkRate, #DkFileBpm {{ color: #9a9a9a; font-size: 12px; qproperty-alignment: 'AlignRight|AlignVCenter'; }}

#DkLetterA, #DkLetterB {{ font-size: 28px; font-weight: bold; qproperty-alignment: 'AlignCenter'; }}
#DkLetterA {{ color: #3cd264; }}
#DkLetterB {{ color: #aa50eb; }}

#DkOverviewBox {{ background-color: #111111; border: 1px solid #0a0a0a; }}

{', '.join('#' + b for b in BASE_BTNS)} {{
  font-size: 11px; font-weight: bold; color: #a8a8a8;
  background-color: #333333; border: none; border-radius: 0px;
}}
#DkPlay {{ font-size: 15px; }}
#DkPlay[displayValue="1"] {{ background-color: #b4ff1e; color: #0d0d0d; }}
#DkCue[displayValue="1"] {{ background-color: #e8a33a; color: #111111; }}
#DkSync {{ background-color: #1a2744; color: #6f95e8; }}
#DkSync[displayValue="1"] {{ background-color: #2f6bff; color: #ffffff; }}
#DkKey[displayValue="1"], #DkLead[displayValue="2"] {{ background-color: #1fb5e6; color: #0d0d0d; }}
#DkLead[displayValue="1"] {{ background-color: #155f78; color: #d0d0d0; }}
#DkLoopAct[displayValue="1"] {{ background-color: #5aa832; color: #ffffff; }}
{loop_sel} {{ background-color: #5c5c5c; color: #ffffff; }}

#HotcueButton {{
  font-size: 11px; font-weight: bold; border: none; border-radius: 0px;
  text-align: left; padding-left: 6px;
}}
#HotcueButton[displayValue="0"] {{ background-color: #2c2c2c; color: #7a7a7a; }}
#HotcueButton[light="true"] {{ color: #0d0d0d; }}
#HotcueButton[dark="true"] {{ color: #f0f0f0; }}
/* QSS image urls must use skin:/ - relative and skins:<name>/ paths silently fail */
#HotcueButton[type="loop"] {{
  image: url(skin:/image/hotcue-loop.svg);
  image-position: right center;
}}
'''


def hotcue_tint(d):
    # Mixxx paints each set hotcue in its stored cue color via a widget-level
    # stylesheet (wins over skin QSS for background-color), so paint the deck
    # color as a tiled solid background-image on top instead.
    p = f'#DeckPanel{d["s"]} #HotcueButton'
    lo = d["s"].lower()
    return f"""
/* deck {d["s"]} hotcues: deck color = cue point, darker + loop icon = saved loop */
{p}[displayValue="1"], {p}[displayValue="2"] {{
  background-image: url(skin:/image/hc-{lo}.png); background-repeat: repeat-xy; color: #0d0d0d;
}}
{p}[type="loop"][displayValue="1"], {p}[type="loop"][displayValue="2"] {{
  background-image: url(skin:/image/hc-{lo}-loop.png); color: #ffffff;
}}
"""


CSS += ''.join(hotcue_tint(d) for d in DECKS)


# ------------------------------------------------------------------ write ----

src = SKIN.read_text(encoding='utf-8')

src = src[:src.index('    <!-- ===== BROWSE PAGE')] + BROWSE + EXPANDED

css_open = '<Style><![CDATA['
css_start = src.index(css_open) + len(css_open)
src = src[:css_start] + CSS + src[src.index(']]></Style>'):]

SKIN.write_text(src, encoding='utf-8')

# --- image assets ---
ticks = ''.join(f'<line x1="1" y1="{y}" x2="5" y2="{y}"/><line x1="13" y1="{y}" x2="17" y2="{y}"/>'
                for y in (10, 20, 30, 40, 60, 70, 80, 90))
for d in DECKS:
    lo = d['s'].lower()
    (SKIN_DIR / 'image' / f'pitch-track-{lo}.svg').write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="100" viewBox="0 0 18 100">'
        '<rect x="7.5" y="1" width="3" height="98" fill="#050505" stroke="#3a3a3a" stroke-width="0.6"/>'
        f'<g stroke="#4a4a4a" stroke-width="0.8">{ticks}</g>'
        '<line x1="0" y1="50" x2="18" y2="50" stroke="#9a9a9a" stroke-width="1.2"/>'
        '</svg>', encoding='utf-8')
    (SKIN_DIR / 'image' / f'pitch-handle-{lo}.svg').write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="8" viewBox="0 0 18 8">'
        '<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#d8d8d8"/><stop offset="0.5" stop-color="#a8a8a8"/>'
        '<stop offset="1" stop-color="#6e6e6e"/></linearGradient></defs>'
        '<rect x="0.5" y="0.5" width="17" height="7" rx="1" fill="url(#g)" stroke="#111" stroke-width="0.8"/>'
        f'<rect x="2" y="3.3" width="14" height="1.4" fill="{d["color"]}"/>'
        '</svg>', encoding='utf-8')
    Image.new('RGB', (4, 4), d['cue']).save(SKIN_DIR / 'image' / f'hc-{lo}.png')
    Image.new('RGB', (4, 4), d['loop']).save(SKIN_DIR / 'image' / f'hc-{lo}-loop.png')
(SKIN_DIR / 'image' / 'hotcue-loop.svg').write_text(
    '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="10" viewBox="0 0 14 10">'
    '<path d="M3 2h7a2 2 0 0 1 2 2v2a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5" fill="none" stroke="#ffffff" stroke-width="1.4"/>'
    '<path d="M0 5.5l2-2.5 2 2.5z" fill="#ffffff"/></svg>', encoding='utf-8')
print('ok')
