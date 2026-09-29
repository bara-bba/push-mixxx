"""Regenerates the Pusher160 skin's Device page (ExpandedRow) + its CSS,
Traktor-deck style, in this folder's skin.xml. Install the skin by copying
this folder to %LOCALAPPDATA%/Mixxx/skins/Pusher160.
Both decks come from the same template so they stay identical (Mixxx templates
don't work for user skins, so we generate instead)."""
import pathlib
import re

SKIN_DIR = pathlib.Path(__file__).resolve().parent
SKIN = SKIN_DIR / 'skin.xml'

DECKS = [
    {'g': '[Channel1]', 'n': 1, 's': 'A', 'color': '#3cd264', 'cue': (60, 210, 100), 'loop': (26, 128, 60)},
    {'g': '[Channel2]', 'n': 2, 's': 'B', 'color': '#aa50eb', 'cue': (170, 80, 235), 'loop': (104, 44, 150)},
]
LOOP_SIZES = [('1/4', '0.25'), ('1/2', '0.5'), ('1', '1'), ('2', '2'), ('4', '4'), ('8', '8'), ('16', '16')]
ROW_H = 24
# ~70px-wide pads: 6px digit + 17 x 3px nbsp centers the digit ~7px from the left edge
HOTCUE_PAD = '&#160;' * 17


def hspace(w):
    return f'<WidgetGroup><Size>{w}f,1min</Size></WidgetGroup>'


def vspace(h):
    return f'<WidgetGroup><Size>1min,{h}f</Size></WidgetGroup>'


def states(text, n):
    return ''.join(f'<State><Number>{i}</Number><Text>{text}</Text></State>' for i in range(n))


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


def fixed_group(obj, layout, w, h, children, wpolicy='f'):
    maxw = 10000 if wpolicy == 'me' else w
    name = f'<ObjectName>{obj}</ObjectName>' if obj else ''
    return (f'<WidgetGroup>{name}<Layout>{layout}</Layout><SizePolicy>{wpolicy},f</SizePolicy>'
            f'<MinimumSize>{w},{h}</MinimumSize><MaximumSize>{maxw},{h}</MaximumSize>'
            f'<Children>{children}</Children></WidgetGroup>')


def deck(d):
    g, s, n = d['g'], d['s'], d['n']

    header = fixed_group('DkHeader', 'horizontal', 100, 48, ''.join([
        f'<WidgetGroup><ObjectName>DkCover{s}</ObjectName><Layout>horizontal</Layout><Size>48f,48f</Size>'
        f'<Children><CoverArt><Group>{g}</Group><SizePolicy>me,me</SizePolicy></CoverArt></Children></WidgetGroup>',
        hspace(8),
        '<WidgetGroup><ObjectName>DkTextCol</ObjectName><Layout>vertical</Layout><SizePolicy>me,me</SizePolicy><Children>',
        f'<TrackProperty><ObjectName>DkTitle</ObjectName><Group>{g}</Group><Property>title</Property><SizePolicy>me,f</SizePolicy><MinimumSize>10,18</MinimumSize><MaximumSize>10000,18</MaximumSize><Elide>right</Elide></TrackProperty>',
        f'<TrackProperty><ObjectName>DkArtist</ObjectName><Group>{g}</Group><Property>artist</Property><SizePolicy>me,f</SizePolicy><MinimumSize>10,15</MinimumSize><MaximumSize>10000,15</MaximumSize><Elide>right</Elide></TrackProperty>',
        f'<TrackProperty><ObjectName>DkAlbum</ObjectName><Group>{g}</Group><Property>album</Property><SizePolicy>me,f</SizePolicy><MinimumSize>10,15</MinimumSize><MaximumSize>10000,15</MaximumSize><Elide>right</Elide></TrackProperty>',
        '</Children></WidgetGroup>',
        hspace(6),
        # Time column. NumberPos ignores its <Connection> and always follows the
        # global [Controls],ShowDurationRemaining mode - set to 2 (elapsed AND
        # remaining, one wrapped two-line string) in the manifest. Each widget
        # is clipped to one of the two lines via fixed height + vertical align.
        '<WidgetGroup><ObjectName>DkTimeCol</ObjectName><Layout>vertical</Layout><SizePolicy>f,f</SizePolicy><MinimumSize>74,48</MinimumSize><MaximumSize>74,48</MaximumSize><Children>',
        f'<NumberPos><ObjectName>DkTimeRemain</ObjectName><Group>{g}</Group><Channel>{n}</Channel><SizePolicy>f,f</SizePolicy><MinimumSize>74,24</MinimumSize><MaximumSize>74,24</MaximumSize></NumberPos>',
        # narrow enough (44px) that the 12px 'elapsed  -remaining' string wraps
        fixed_group('', 'horizontal', 74, 16, hspace(30) + f'<NumberPos><ObjectName>DkTimeElapsed</ObjectName><Group>{g}</Group><Channel>{n}</Channel><SizePolicy>f,f</SizePolicy><MinimumSize>44,16</MinimumSize><MaximumSize>44,16</MaximumSize></NumberPos>'),
        vspace(8),
        '</Children></WidgetGroup>',
        hspace(8),
        '<WidgetGroup><ObjectName>DkBpmCol</ObjectName><Layout>vertical</Layout><SizePolicy>f,f</SizePolicy><MinimumSize>62,48</MinimumSize><MaximumSize>62,48</MaximumSize><Children>',
        f'<NumberBpm><ObjectName>DkBpm</ObjectName><Group>{g}</Group><SizePolicy>f,f</SizePolicy><MinimumSize>62,20</MinimumSize><MaximumSize>62,20</MaximumSize><NumberOfDigits>2</NumberOfDigits><Connection><ConfigKey>{g},visual_bpm</ConfigKey></Connection></NumberBpm>',
        fixed_group('', 'horizontal', 62, 14,
                    f'<NumberRate><ObjectName>DkRate</ObjectName><Channel>{n}</Channel><SizePolicy>f,f</SizePolicy><MinimumSize>52,14</MinimumSize><MaximumSize>52,14</MaximumSize><NumberOfDigits>1</NumberOfDigits></NumberRate>'
                    '<Label><ObjectName>DkRatePct</ObjectName><Text>%</Text><SizePolicy>f,f</SizePolicy><MinimumSize>10,14</MinimumSize><MaximumSize>10,14</MaximumSize></Label>'),
        f'<NumberBpm><ObjectName>DkFileBpm</ObjectName><Group>{g}</Group><SizePolicy>f,f</SizePolicy><MinimumSize>62,14</MinimumSize><MaximumSize>62,14</MaximumSize><NumberOfDigits>2</NumberOfDigits><Connection><ConfigKey>{g},file_bpm</ConfigKey></Connection></NumberBpm>',
        '</Children></WidgetGroup>',
    ]), wpolicy='me')

    overview = fixed_group('DkOverviewBox', 'horizontal', 100, 38, (
        f'<Overview><Group>{g}</Group><SizePolicy>me,me</SizePolicy>'
        '<BgColor>#111111</BgColor>'
        f'<SignalColor>{d["color"]}</SignalColor>'
        '<PlayedOverlayColor>#000000a0</PlayedOverlayColor>'
        '<PlayPosColor>#ffffff</PlayPosColor>'
        '<EndOfTrackColor>#e8453c</EndOfTrackColor>'
        '<DefaultMark><Align>top</Align><Color>#1fb5e6</Color><TextColor>#000000</TextColor><Text> %1 </Text></DefaultMark>'
        '<Mark><Control>cue_point</Control><Align>bottom</Align><Color>#e8a33a</Color><TextColor>#000000</TextColor><Text> C </Text></Mark>'
        '<MarkRange><StartControl>loop_start_position</StartControl><EndControl>loop_end_position</EndControl>'
        '<EnabledControl>loop_enabled</EnabledControl><Color>#5aa832</Color><Opacity>0.6</Opacity>'
        '<DisabledColor>#ffffff</DisabledColor><DisabledOpacity>0.25</DisabledOpacity></MarkRange>'
        '</Overview>'), wpolicy='me')

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
        cue_states = ''.join(f'<State><Number>{k}</Number><Text>{i}{HOTCUE_PAD}</Text></State>'
                             for k in range(3))
        cues.append(f'<HotcueButton><ObjectName>HotcueButton</ObjectName><Group>{g}</Group><Hotcue>{i}</Hotcue>'
                    f'<SizePolicy>me,f</SizePolicy><MinimumSize>30,{ROW_H}</MinimumSize><MaximumSize>10000,{ROW_H}</MaximumSize>'
                    f'<NumberStates>3</NumberStates>{cue_states}</HotcueButton>')
    hotcues = fixed_group('DkHotcueRow', 'horizontal', 100, ROW_H, ''.join(cues), wpolicy='me')

    main_col = ('<WidgetGroup><ObjectName>DkMain</ObjectName><Layout>vertical</Layout><SizePolicy>me,me</SizePolicy><Children>'
                + vspace(4) + header + vspace(4) + overview + vspace(4) + ctrl + vspace(4) + hotcues
                + '</Children></WidgetGroup>')

    side_col = fixed_group('DkSide', 'vertical', 30, 160, ''.join([
        vspace(2),
        f'<Label><ObjectName>DkLetter{s}</ObjectName><Text>{s}</Text><SizePolicy>f,f</SizePolicy>'
        '<MinimumSize>30,32</MinimumSize><MaximumSize>30,32</MaximumSize></Label>',
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


EXPANDED = f'''    <!-- ===== EXPANDED "DEVICE" SCENE (second 960x160 page, captured
         separately by push-screen when that scene is active). Traktor-deck
         style; GENERATED by gen_device.py - both decks from one template. ===== -->
    <WidgetGroup>
      <ObjectName>ExpandedRow</ObjectName>
      <Layout>horizontal</Layout>
      <Size>960f,160f</Size>
      <MaximumSize>960,160</MaximumSize>
      <Children>
{deck(DECKS[0])}
{hspace(2)}
{deck(DECKS[1])}
      </Children>
    </WidgetGroup>

  </Children>
</skin>
'''

BASE_BTNS = ['DkPlay', 'DkCue', 'DkKey', 'DkSync', 'DkLead', 'DkLoopAct'] + [f'DkLoopSz{i}' for i in range(len(LOOP_SIZES))]
loop_sel = ',\n'.join(f'#DkLoopSz{i}[value="{v}"]' for i, (_, v) in enumerate(LOOP_SIZES))

CSS = f'''/* ===== Expanded "Device" scene - Traktor-deck style (generated by gen_device.py) ===== */
#ExpandedRow {{ background-color: #000000; }}
#DeckPanelA, #DeckPanelB, #DeckPanelA WWidgetGroup, #DeckPanelB WWidgetGroup {{ background-color: #1b1b1b; }}
#DeckPanelA, #DeckPanelB, #DeckPanelA *, #DeckPanelB * {{ font-family: "Segoe UI", "Open Sans", "DejaVu Sans", "Ubuntu", sans-serif; }}

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
#HotcueButton[type="loop"] {{
  image: url(skin:/image/hotcue-loop.svg);
  image-position: right center;
}}
'''


def tint(d):
    # Mixxx paints each set hotcue in its stored cue color via a widget-level
    # stylesheet (wins over skin QSS for background-color), so paint the deck
    # color as a tiled solid background-image on top instead.
    p = f'#DeckPanel{d["s"]} #HotcueButton'
    lo = d["s"].lower()
    return f"""
/* ---- deck {d["s"]} hotcues: deck color = cue point, darker + loop icon = saved loop ---- */
{p}[displayValue="1"], {p}[displayValue="2"] {{
  background-image: url(skin:/image/hc-{lo}.png); background-repeat: repeat-xy; color: #0d0d0d;
}}
{p}[type="loop"][displayValue="1"], {p}[type="loop"][displayValue="2"] {{
  background-image: url(skin:/image/hc-{lo}-loop.png); color: #ffffff;
}}
"""

CSS += ''.join(tint(d) for d in DECKS)

src = SKIN.read_text(encoding='utf-8')

start = src.index('    <!-- ===== EXPANDED "DEVICE" SCENE')
src = src[:start] + EXPANDED

css_start = src.index('/* ===== Expanded "Device" scene')
css_end = src.index(']]></Style>')
src = src[:css_start] + CSS + src[css_end:]

attr_block = '<attribute config_key="[App],num_decks">2</attribute>'
if 'ShowDurationRemaining' not in src:
    src = src.replace(attr_block, attr_block + '''
      <!-- elapsed + remaining in one NumberPos string (Device page splits it
           into two clipped widgets); coarse mm:ss like Traktor -->
      <attribute config_key="[Controls],ShowDurationRemaining">2</attribute>
      <attribute config_key="[Controls],TimeFormat">1</attribute>''')

SKIN.write_text(src, encoding='utf-8')

# --- image assets ---
ticks = ''.join(f'<line x1="1" y1="{y}" x2="5" y2="{y}"/><line x1="13" y1="{y}" x2="17" y2="{y}"/>'
                for y in (10, 20, 30, 40, 60, 70, 80, 90))
for d in DECKS:
    (SKIN_DIR / 'image' / f'pitch-track-{d["s"].lower()}.svg').write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="100" viewBox="0 0 18 100">'
        f'<rect x="7.5" y="1" width="3" height="98" fill="#050505" stroke="#3a3a3a" stroke-width="0.6"/>'
        f'<g stroke="#4a4a4a" stroke-width="0.8">{ticks}</g>'
        f'<line x1="0" y1="50" x2="18" y2="50" stroke="#9a9a9a" stroke-width="1.2"/>'
        '</svg>', encoding='utf-8')
for d in DECKS:
    (SKIN_DIR / 'image' / f'pitch-handle-{d["s"].lower()}.svg').write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="8" viewBox="0 0 18 8">'
        '<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#d8d8d8"/><stop offset="0.5" stop-color="#a8a8a8"/>'
        '<stop offset="1" stop-color="#6e6e6e"/></linearGradient></defs>'
        '<rect x="0.5" y="0.5" width="17" height="7" rx="1" fill="url(#g)" stroke="#111" stroke-width="0.8"/>'
        f'<rect x="2" y="3.3" width="14" height="1.4" fill="{d["color"]}"/>'
        '</svg>', encoding='utf-8')
(SKIN_DIR / 'image' / 'hotcue-loop.svg').write_text(
    '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="10" viewBox="0 0 14 10">'
    '<path d="M3 2h7a2 2 0 0 1 2 2v2a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5" fill="none" stroke="#0d0d0d" stroke-width="1.4"/>'
    '<path d="M0 5.5l2-2.5 2 2.5z" fill="#0d0d0d"/></svg>', encoding='utf-8')

from PIL import Image
for d in DECKS:
    lo = d['s'].lower()
    Image.new('RGB', (4, 4), d['cue']).save(SKIN_DIR / 'image' / f'hc-{lo}.png')
    Image.new('RGB', (4, 4), d['loop']).save(SKIN_DIR / 'image' / f'hc-{lo}-loop.png')
(SKIN_DIR / 'image' / 'hotcue-loop.svg').write_text(
    '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="10" viewBox="0 0 14 10">'
    '<path d="M3 2h7a2 2 0 0 1 2 2v2a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5" fill="none" stroke="#ffffff" stroke-width="1.4"/>'
    '<path d="M0 5.5l2-2.5 2 2.5z" fill="#ffffff"/></svg>', encoding='utf-8')
print('ok')
