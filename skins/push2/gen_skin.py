"""Generates the Pusher160 skin's two pages + its whole stylesheet into this
folder's skin.xml (everything from the BROWSE PAGE marker to the end, and the
<Style> CDATA). Only the header comment and manifest are hand-written.
Install the skin by copying this folder to %LOCALAPPDATA%/Mixxx/skins/Pusher160.

Both decks come from the same template so they stay identical - Mixxx
templates don't work for user skins, so we generate instead.
"""
import pathlib

from PIL import Image

from set_library_columns import COLUMNS as LIB_COLUMNS, SCROLLBAR_W as LIB_SCROLLBAR_W

SKIN_DIR = pathlib.Path(__file__).resolve().parent
SKIN = SKIN_DIR / 'skin.xml'

DECKS = [
    {'g': '[Channel1]', 'n': 1, 's': 'A', 'color': '#3cd264', 'hi': '#8be6a4', 'lo': '#1c7a38',
     'cue': (60, 210, 100), 'loop': (26, 128, 60)},
    {'g': '[Channel2]', 'n': 2, 's': 'B', 'color': '#aa50eb', 'hi': '#cf9bf5', 'lo': '#5e2a85',
     'cue': (170, 80, 235), 'loop': (104, 44, 150)},
]
# Design scheme, "Scan" register (github.com/bara-bba/la-pagina-barbara,
# STYLE.md): ink ground, off-white line/type, one accent (acid lime), scan red
# only as a signal, electric blue from the palette for SYNC; 0 radius, no
# gradients/shadows, outlined components. Deck colours (A green / B purple)
# are kept as the deck identity. Highlighted text uses TAN - SPRING (display),
# everything else Arial.
INK = '#0B0B0B'
LINE = '#E8E8E2'
DIM = '#8C8C86'      # secondary text
FAINT = '#5A5A55'    # tertiary text, beat lines
EDGE = '#3A3A36'     # idle outlines
HAIR = '#2A2A28'     # hairline rules
LIME = '#C8F53C'     # the accent
RED = '#FF2B1C'      # signal (end of track)
ORANGE = '#E8A33A'   # cue (button + cue-point markers) - kept from the earlier look
BLUE = '#1F4BFF'     # SYNC
FONT = '"Arial", "Liberation Sans", "DejaVu Sans", sans-serif'
DISPLAY = '"TAN - SPRING", "Arial", sans-serif'

LOOP_SIZES = [('1/4', '0.25'), ('1/2', '0.5'), ('1', '1'), ('2', '2'), ('4', '4'), ('8', '8'), ('16', '16')]
ROW_H = 24
# ~70px-wide pads: 6px digit + 17 x 3px nbsp centers the digit ~7px from the left edge
HOTCUE_PAD = '&#160;' * 17
# Each deck half is fixed at 479px (+ the 2px rule = 960): with expanding halves
# Qt splits the width by content (a long title widens its deck), which would
# also make the two pages' headers differ.
HALF_W = (960 - 2) // 2
HEADER_TOP = 4     # space above the deck header on every deck page
HEADER_H = 48      # the deck header itself (deck_header)
BROWSE_HEADER_H = HEADER_TOP + HEADER_H
WAVE_H = (160 - BROWSE_HEADER_H) // 2
# [Skin],pusher_scene values (push-mixxx scenes) with their own page; every
# other scene shows the browse/waveform page.
LIBRARY_SCENE = 1   # Browse: library + preview deck
EXPANDED_SCENE = 2  # Device (the resting scene): expanded decks
FX_SCENE = 4        # Clip: FX units (where the Push FX controls live)


def hspace(w):
    return f'<WidgetGroup><Size>{w}f,1min</Size></WidgetGroup>'


def vspace(h):
    return f'<WidgetGroup><Size>1min,{h}f</Size></WidgetGroup>'


def states(text, n):
    return ''.join(f'<State><Number>{i}</Number><Text>{text}</Text></State>' for i in range(n))


# Loop sizes the last loop pad grows into when the loop is doubled past it
LOOP_TAIL_SIZES = (32, 64, 128, 256, 512)  # 512 = Mixxx's largest beatloop


def loop_size_tail(obj, g, label, val):
    """Last loop-size pad: shows '16' until the loop size goes past it, then
    the actual size (32, 64, ... 512) in the same cell, lit. A PushButton's
    text comes from state int(value) % NumberStates, so one state per size up
    to 512, all '16' except the larger sizes."""
    n = LOOP_TAIL_SIZES[-1] + 1
    texts = {size: str(size) for size in LOOP_TAIL_SIZES}
    state_xml = ''.join(f'<State><Number>{i}</Number><Text>{texts.get(i, label)}</Text></State>' for i in range(n))
    return (f'<PushButton><ObjectName>{obj}</ObjectName><SizePolicy>me,f</SizePolicy>'
            f'<MinimumSize>22,{ROW_H}</MinimumSize><MaximumSize>10000,{ROW_H}</MaximumSize>'
            f'<NumberStates>{n}</NumberStates>{state_xml}'
            f'<Connection><ConfigKey>{g},beatloop_size</ConfigKey>'
            '<ConnectValueFromWidget>false</ConnectValueFromWidget></Connection>'
            f'<Connection><ConfigKey>{g},beatloop_{val}_activate</ConfigKey>'
            '<ConnectValueToWidget>false</ConnectValueToWidget><ButtonState>LeftButton</ButtonState></Connection>'
            '</PushButton>')


def fixed_group(obj, layout, w, h, children, wpolicy='f'):
    maxw = 10000 if wpolicy == 'me' else w
    name = f'<ObjectName>{obj}</ObjectName>' if obj else ''
    return (f'<WidgetGroup>{name}<Layout>{layout}</Layout><SizePolicy>{wpolicy},f</SizePolicy>'
            f'<MinimumSize>{w},{h}</MinimumSize><MaximumSize>{maxw},{h}</MaximumSize>'
            f'<Children>{children}</Children></WidgetGroup>')


def scene_visibility(scene, shown):
    """Visible while [Skin],pusher_scene == scene (shown) or != scene (not shown)."""
    transform = f'<IsEqual>{scene}</IsEqual>' + ('' if shown else '<Not/>')
    return (f'<Connection><ConfigKey>[Skin],pusher_scene</ConfigKey>'
            f'<Transform>{transform}</Transform><BindProperty>visible</BindProperty></Connection>')


def vrule(w=2):
    """Vertical hairline rule (the scheme's visible grid lines)."""
    return (f'<Label><ObjectName>Rule</ObjectName><SizePolicy>f,me</SizePolicy>'
            f'<MinimumSize>{w},1</MinimumSize><MaximumSize>{w},10000</MaximumSize></Label>')


def hidden_on(scenes, page):
    """Wraps page in one group per scene, each hidden on that scene; a visible
    wrapper whose child is hidden collapses to zero height (SizePolicy max)."""
    for scene in scenes:
        page = ('<WidgetGroup><Layout>vertical</Layout><SizePolicy>me,max</SizePolicy>'
                f'{scene_visibility(scene, shown=False)}<Children>{page}</Children></WidgetGroup>')
    return page


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
    # one 11px line tall (13px): any taller and the hidden second line peeks in
    return fixed_group('', 'horizontal', 74, 13, hspace(30) + (
        f'<NumberPos><ObjectName>DkTimeElapsed</ObjectName><Group>{d["g"]}</Group><Channel>{d["n"]}</Channel>'
        '<SizePolicy>f,f</SizePolicy><MinimumSize>44,13</MinimumSize><MaximumSize>44,13</MaximumSize></NumberPos>'))


def bpm(d):
    return (f'<NumberBpm><ObjectName>DkBpm</ObjectName><Group>{d["g"]}</Group><SizePolicy>f,f</SizePolicy>'
            '<MinimumSize>62,24</MinimumSize><MaximumSize>62,24</MaximumSize><NumberOfDigits>2</NumberOfDigits>'
            f'<Connection><ConfigKey>{d["g"]},visual_bpm</ConfigKey></Connection></NumberBpm>')


def deck_letter(d, h):
    return (f'<Label><ObjectName>DkLetter{d["s"]}</ObjectName><Text>{d["s"]}</Text><SizePolicy>f,f</SizePolicy>'
            f'<MinimumSize>30,{h}</MinimumSize><MaximumSize>30,{h}</MaximumSize></Label>')


def hotcue_mark(d, align='top'):
    return (f'<DefaultMark><Align>{align}</Align><Color>{d["color"]}</Color><TextColor>{INK}</TextColor>'
            '<Text> %1 </Text></DefaultMark>')


def cue_mark(align):
    return (f'<Mark><Control>cue_point</Control><Text> C </Text><Align>{align}</Align>'
            f'<Color>{ORANGE}</Color><TextColor>{INK}</TextColor></Mark>')


LOOP_RANGE = ('<MarkRange><StartControl>loop_start_position</StartControl><EndControl>loop_end_position</EndControl>'
              f'<EnabledControl>loop_enabled</EnabledControl><Color>{LIME}</Color><Opacity>0.5</Opacity>'
              f'<DisabledColor>{LINE}</DisabledColor><DisabledOpacity>0.2</DisabledOpacity></MarkRange>')


# ------------------------------------------------------------- deck header ----

def deck_header(d):
    """The deck header used identically on the expanded (Device) and waveform
    (Mix) pages: cover, title/artist/album, remaining/elapsed, BPM/pitch/
    file BPM. The deck letter sits right of it (deck_letter_column)."""
    g, s, n = d['g'], d['s'], d['n']
    return fixed_group('DkHeader', 'horizontal', 100, HEADER_H, ''.join([
        cover(d, 48),
        hspace(8),
        # same rows as the time / BPM columns: title on the 24px bottom-aligned
        # line of remaining time + BPM, artist and album on the two 12px lines
        # of elapsed / pitch % / file BPM
        fixed_group('DkTextCol', 'vertical', 10, 48, track_prop('DkTitle', g, 'title', 24)
                    + track_prop('DkArtist', g, 'artist', 12) + track_prop('DkAlbum', g, 'album', 12), wpolicy='me'),
        hspace(6),
        fixed_group('DkTimeCol', 'vertical', 74, 48, time_remaining(d) + time_elapsed(d) + vspace(48 - 24 - 13)),
        hspace(8),
        # BPM shares the remaining time's 24px bottom-aligned line; the two
        # small rows below start where the elapsed time does (24px down)
        fixed_group('DkBpmCol', 'vertical', 62, 48, bpm(d) + fixed_group('', 'horizontal', 62, 12,
            f'<NumberRate><ObjectName>DkRate</ObjectName><Channel>{n}</Channel><SizePolicy>f,f</SizePolicy>'
            '<MinimumSize>52,12</MinimumSize><MaximumSize>52,12</MaximumSize><NumberOfDigits>1</NumberOfDigits></NumberRate>'
            '<Label><ObjectName>DkRatePct</ObjectName><Text>%</Text><SizePolicy>f,f</SizePolicy>'
            '<MinimumSize>10,12</MinimumSize><MaximumSize>10,12</MaximumSize></Label>')
            + f'<NumberBpm><ObjectName>DkFileBpm</ObjectName><Group>{g}</Group><SizePolicy>f,f</SizePolicy>'
              '<MinimumSize>62,12</MinimumSize><MaximumSize>62,12</MaximumSize><NumberOfDigits>2</NumberOfDigits>'
              f'<Connection><ConfigKey>{g},file_bpm</ConfigKey></Connection></NumberBpm>'),
    ]), wpolicy='me')


def deck_letter_column(d, h, below=''):
    """Right-hand column of a deck half: the big deck letter on top, then
    whatever the page puts below it (the Device page's pitch fader)."""
    return fixed_group('DkSide', 'vertical', 30, h, vspace(2) + deck_letter(d, 32) + below)


# ------------------------------------------------------------ browse page ----

def browse_header(d):
    """The waveform page's deck header: exactly the Device page's header and
    letter, with the same margins and top offset as device_deck."""
    H = BROWSE_HEADER_H
    return (f'<WidgetGroup><ObjectName>DeckPanel{d["s"]}</ObjectName><Layout>horizontal</Layout><SizePolicy>f,f</SizePolicy>'
            f'<MinimumSize>{HALF_W},{H}</MinimumSize><MaximumSize>{HALF_W},{H}</MaximumSize><Children>'
            + hspace(6)
            + fixed_group('', 'vertical', 10, H, vspace(HEADER_TOP) + deck_header(d), wpolicy='me')
            + hspace(6)
            + deck_letter_column(d, H, vspace(H - 2 - 32))
            + hspace(2)
            + '</Children></WidgetGroup>')


def waveform(d, mark_align):
    """Full-width scrolling waveform. A marks on top, B on the bottom, so labels
    never collide on the shared seam used for beatmatching."""
    g, s = d['g'], d['s']
    visual = (f'<Visual><ObjectName>Wave{s}</ObjectName><Group>{g}</Group><SizePolicy>me,me</SizePolicy>'
              f'<SignalColor>{d["color"]}</SignalColor><SignalHighColor>{d["hi"]}</SignalHighColor>'
              f'<SignalMidColor>{d["color"]}</SignalMidColor><SignalLowColor>{d["lo"]}</SignalLowColor>'
              f'<AxesColor></AxesColor><BeatColor>{FAINT}</BeatColor><PlayPosColor>{LINE}</PlayPosColor>'
              f'<BgColor>{INK}</BgColor><EndOfTrackColor>{RED}</EndOfTrackColor>'
              + hotcue_mark(d, mark_align)
              + cue_mark(mark_align)
              + LOOP_RANGE
              + f'<Mark><Control>loop_start_position</Control><Text>IN</Text><Align>{mark_align}</Align>'
                f'<Color>{LIME}</Color><TextColor>{INK}</TextColor></Mark>'
              + f'<Mark><Control>loop_end_position</Control><Text>OUT</Text><Align>{mark_align}</Align>'
                f'<Color>{LIME}</Color><TextColor>{INK}</TextColor></Mark>'
              '</Visual>')
    # Wrapped + height-capped: <MaximumSize> on Visual itself isn't respected.
    return fixed_group(f'Wave{s}Box', 'horizontal', 960, WAVE_H, visual)


BROWSE = f'''    <!-- ===== WAVEFORM PAGE (shown for push-mixxx scenes without their own
         page - Mix, none): Traktor-style deck headers, then the two
         waveforms stacked edge to edge so a beat line crossing the seam is
         visible for beatmatching. GENERATED by gen_skin.py. ===== -->
{hidden_on((LIBRARY_SCENE, EXPANDED_SCENE, FX_SCENE),
           '<WidgetGroup><ObjectName>BrowsePage</ObjectName><Layout>vertical</Layout>'
           '<Size>960f,160f</Size><MaximumSize>960,160</MaximumSize><Children>'
           + fixed_group('BrHeaderRow', 'horizontal', 960, BROWSE_HEADER_H,
                         browse_header(DECKS[0]) + vrule() + browse_header(DECKS[1]))
           + waveform(DECKS[0], 'top') + waveform(DECKS[1], 'bottom')
           + '</Children></WidgetGroup>')}

'''


# ------------------------------------------------------------ device page ----

def device_deck(d):
    g, s, n = d['g'], d['s'], d['n']

    header = deck_header(d)

    # 48px so the column adds up to exactly 160 (4+48+4+48+4+24+4+24): with
    # spare pixels Qt would centre the rows and the header would drop below
    # the 4px top it shares with the waveform page's header.
    overview = fixed_group('DkOverviewBox', 'horizontal', 100, 48, (
        f'<Overview><Group>{g}</Group><SizePolicy>me,me</SizePolicy>'
        f'<BgColor>{INK}</BgColor>'
        f'<SignalColor>{d["color"]}</SignalColor><SignalHighColor>{d["hi"]}</SignalHighColor>'
        f'<SignalMidColor>{d["color"]}</SignalMidColor><SignalLowColor>{d["lo"]}</SignalLowColor>'
        '<PlayedOverlayColor>#000000a0</PlayedOverlayColor>'
        f'<PlayPosColor>{LINE}</PlayPosColor>'
        f'<EndOfTrackColor>{RED}</EndOfTrackColor>'
        + hotcue_mark(d)
        + cue_mark('bottom')
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
        if i == len(LOOP_SIZES) - 1:
            ctrl_parts.append(loop_size_tail(f'DkLoopSz{i}', g, label, val))
        else:
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
                + vspace(HEADER_TOP) + header + vspace(4) + overview + vspace(4) + ctrl + vspace(4) + hotcues
                + '</Children></WidgetGroup>')

    side_col = deck_letter_column(d, 160, ''.join([
        vspace(6),
        fixed_group('', 'horizontal', 30, 104, ''.join([
            hspace(6),
            f'<SliderComposed><ObjectName>DkPitch</ObjectName><TooltipId>rate</TooltipId><Size>18f,104f</Size>'
            f'<Slider scalemode="STRETCH">image/pitch-track-{s.lower()}.svg</Slider>'
            f'<Handle scalemode="STRETCH_ASPECT">image/pitch-handle-{s.lower()}.svg</Handle>'
            f'<Connection><ConfigKey>{g},rate</ConfigKey></Connection></SliderComposed>',
            hspace(6),
        ])),
        vspace(160 - 2 - 32 - 6 - 104),  # fill to 160 so the letter stays at the top
    ]))

    return (f'<!-- DECK {s} -->'
            f'<WidgetGroup><ObjectName>DeckPanel{s}</ObjectName><Layout>horizontal</Layout><SizePolicy>f,f</SizePolicy>'
            f'<MinimumSize>{HALF_W},160</MinimumSize><MaximumSize>{HALF_W},160</MaximumSize><Children>'
            + hspace(6) + main_col + hspace(6) + side_col + hspace(2)
            + '</Children></WidgetGroup>')


EXPANDED = f'''    <!-- ===== EXPANDED PAGE (ExpandedRow, shown while [Skin],pusher_scene is
         the Device scene, push-mixxx's resting scene): Traktor-style expanded decks. GENERATED by
         gen_skin.py. ===== -->
    <WidgetGroup>
      <ObjectName>ExpandedRow</ObjectName>
      <Layout>horizontal</Layout>
      <Size>960f,160f</Size>
      <MaximumSize>960,160</MaximumSize>
      {scene_visibility(EXPANDED_SCENE, shown=True)}
      <Children>
{device_deck(DECKS[0])}
{vrule()}
{device_deck(DECKS[1])}
      </Children>
    </WidgetGroup>

'''


# ---------------------------------------------------------------- FX page ----
# Push 2 has an encoder and a button above every 120px of the screen; in the
# Clip scene they map to (pusher-script.js fxEncoder/fxButton):
#   col 1-3 = FX unit 1 effects 1-3 (encoder: meta knob, button: on/off)
#   col 4   = FX unit 1 super knob (encoder), reset (button)
#   col 5-8 = same for FX unit 2
# so every column here sits exactly under its encoder/button.

FX_COL_W = 120
FX_COLS_H = 128
FX_FOOTER_H = 28


def display_button(obj, key, text, w, h):
    return (f'<PushButton><ObjectName>{obj}</ObjectName><SizePolicy>f,f</SizePolicy>'
            f'<MinimumSize>{w},{h}</MinimumSize><MaximumSize>{w},{h}</MaximumSize>'
            f'<NumberStates>2</NumberStates>{states(text, 2)}'
            f'<Connection><ConfigKey>{key}</ConfigKey><ConnectValueFromWidget>false</ConnectValueFromWidget></Connection>'
            '</PushButton>')


def label(obj, text, w, h):
    return (f'<Label><ObjectName>{obj}</ObjectName><Text>{text}</Text><SizePolicy>f,f</SizePolicy>'
            f'<MinimumSize>{w},{h}</MinimumSize><MaximumSize>{w},{h}</MaximumSize></Label>')


def fx_knob(key, arc_color):
    knob = ('<KnobComposed><ObjectName>FxKnob</ObjectName><Size>70f,70f</Size>'
            '<Knob>image/fx-knob-indicator.svg</Knob><BackPath>image/fx-knob-bg.svg</BackPath>'
            '<MinAngle>-135</MinAngle><MaxAngle>135</MaxAngle>'
            '<ArcRadius>30</ArcRadius><ArcThickness>4</ArcThickness><ArcBgThickness>4</ArcBgThickness>'
            '<ArcRoundCaps>true</ArcRoundCaps><ArcUnipolar>true</ArcUnipolar>'
            f'<ArcColor>{arc_color}</ArcColor><ArcBgColor>{HAIR}</ArcBgColor>'
            f'<Connection><ConfigKey>{key}</ConfigKey></Connection></KnobComposed>')
    side = (FX_COL_W - 70) // 2
    return fixed_group('', 'horizontal', FX_COL_W, 70, hspace(side) + knob + hspace(side))


def fx_column(top, name, knob):
    return fixed_group('FxCol', 'vertical', FX_COL_W, FX_COLS_H,
                       vspace(4) + fixed_group('', 'horizontal', FX_COL_W, 22, hspace(6) + top + hspace(6))
                       + vspace(6) + name + vspace(2) + knob + vspace(6))


def fx_unit(u):
    unit = f'[EffectRack1_EffectUnit{u}]'
    cols = ''
    for n in (1, 2, 3):
        eff = f'[EffectRack1_EffectUnit{u}_Effect{n}]'
        cols += fx_column(
            display_button('FxOn', f'{eff},enabled', 'ON', FX_COL_W - 12, 22),
            (f'<EffectName><ObjectName>FxName</ObjectName><EffectRack>1</EffectRack><EffectUnit>{u}</EffectUnit>'
             f'<Effect>{n}</Effect><SizePolicy>f,f</SizePolicy>'
             f'<MinimumSize>{FX_COL_W},18</MinimumSize><MaximumSize>{FX_COL_W},18</MaximumSize></EffectName>'),
            fx_knob(f'{eff},meta', LIME))
    cols += fx_column(label('FxReset', 'RESET', FX_COL_W - 12, 22),
                      label('FxSuperName', 'SUPER', FX_COL_W, 18),
                      fx_knob(f'{unit},super1', LINE))
    badges = ''.join(display_button(f'FxDeck{d["s"]}', f'{unit},group_{d["g"]}_enable', d['s'], 28, 20) + hspace(4)
                     for d in DECKS)
    footer = fixed_group('FxFooter', 'horizontal', 4 * FX_COL_W, FX_FOOTER_H,
                         hspace(8) + label('FxUnitLabel', f'FX {u}', 44, FX_FOOTER_H) + hspace(6) + badges
                         + '<WidgetGroup><SizePolicy>me,min</SizePolicy></WidgetGroup>')  # keep the rest left-aligned
    return fixed_group('FxUnit', 'vertical', 4 * FX_COL_W, 160,
                       vspace(4) + fixed_group('', 'horizontal', 4 * FX_COL_W, FX_COLS_H, cols) + footer)


FX = f'''    <!-- ===== FX PAGE (shown while [Skin],pusher_scene is the Clip scene):
         2 FX units, one 120px column per Push encoder/button above the
         screen. GENERATED by gen_skin.py. ===== -->
    <WidgetGroup>
      <ObjectName>FxPage</ObjectName>
      <Layout>horizontal</Layout>
      <Size>960f,160f</Size>
      <MaximumSize>960,160</MaximumSize>
      {scene_visibility(FX_SCENE, shown=True)}
      <Children>
{fx_unit(1)}
{fx_unit(2)}
      </Children>
    </WidgetGroup>

  </Children>
</skin>
'''


# ----------------------------------------------------------- library page ----
# Browse scene. Left (under buttons 1-2, full height): the preview deck -
# artwork, overview, remaining time - with Mixxx's sidebar (folders/
# playlists) below. Right (under buttons 3-8): the sort-button labels
# (CC104-109 in pusher-script.js's library mode: Title/Artist/Album/BPM/Key/
# Duration, TrackModel::SortColumnId values as in PUSH2T.SORT_COLUMNS) double
# as the track table's column header: the table's columns are set to exactly
# those six (set_library_columns.py) and the labels are sized from the same
# widths, so every label sits over its own column; the table's own header is
# hidden. A slim preview column at the
# front of TITLE marks the song playing in preview. The Push browse encoder/
# arrows drive the sidebar and table via [Library] controls.

LIB_TOP_H = 20
LIB_RIGHT_W = sum(w for _, w in LIB_COLUMNS) + LIB_SCROLLBAR_W
LIB_LEFT_W = 960 - LIB_RIGHT_W - 2  # preview + folders/playlists
LIB_PREVIEW_H = 76
LIB_COVER = 68
SORT_LABELS = [('TITLE', 2), ('ARTIST', 1), ('ALBUM', 3), ('BPM', 15), ('KEY', 20), ('LENGTH', 13)]


def lib_top_row():
    widths = dict(LIB_COLUMNS)
    # TITLE also covers the slim preview column in front of the titles
    label_w = [widths['preview'] + widths['title'], widths['artist'], widths['album'], widths['bpm'], widths['key'],
               widths['duration'] + LIB_SCROLLBAR_W]
    cells = ''
    for i, ((text, _), w) in enumerate(zip(SORT_LABELS, label_w)):
        cells += hspace(1) + display_button(f'LibSort{i}', '[Library],sort_column', text, w - 2, LIB_TOP_H) + hspace(1)
    return fixed_group('LibTopRow', 'horizontal', LIB_RIGHT_W, LIB_TOP_H, cells)


def lib_preview():
    side_w = LIB_LEFT_W - LIB_COVER - 4 - 6 - 6
    cover = ('<WidgetGroup><ObjectName>LibPreviewCover</ObjectName><Layout>horizontal</Layout>'
             f'<Size>{LIB_COVER}f,{LIB_COVER}f</Size><Children><CoverArt><Group>[PreviewDeck1]</Group>'
             '<SizePolicy>me,me</SizePolicy></CoverArt></Children></WidgetGroup>')
    overview = fixed_group('LibPreviewOverviewBox', 'horizontal', side_w, LIB_COVER - 24, (
        '<Overview><Group>[PreviewDeck1]</Group><SizePolicy>me,me</SizePolicy>'
        f'<BgColor>{INK}</BgColor><SignalColor>{LIME}</SignalColor><SignalHighColor>#E4FA9C</SignalHighColor>'
        f'<SignalMidColor>{LIME}</SignalMidColor><SignalLowColor>#6E8A1E</SignalLowColor>'
        f'<PlayedOverlayColor>#000000a0</PlayedOverlayColor><PlayPosColor>{LINE}</PlayPosColor>'
        f'<EndOfTrackColor>{RED}</EndOfTrackColor></Overview>'))
    time = fixed_group('', 'horizontal', side_w, 24,
                       hspace(side_w - 74) + time_remaining({'g': '[PreviewDeck1]', 'n': 0}).replace('<Channel>0</Channel>', ''))
    return fixed_group('LibPreview', 'vertical', LIB_LEFT_W, LIB_PREVIEW_H,
                       vspace(4) + fixed_group('', 'horizontal', LIB_LEFT_W, LIB_COVER,
                                               hspace(4) + cover + hspace(6)
                                               + fixed_group('', 'vertical', side_w, LIB_COVER, overview + time)
                                               + hspace(6)))


LIBRARY = f'''    <!-- ===== LIBRARY PAGE (shown while [Skin],pusher_scene is the Browse
         scene): preview deck + folders/playlists on the left, sort labels
         (= column header) + track table on the right.
         GENERATED by gen_skin.py. ===== -->
    <WidgetGroup>
      <ObjectName>LibraryPage</ObjectName>
      <Layout>horizontal</Layout>
      <Size>960f,160f</Size>
      <MaximumSize>960,160</MaximumSize>
      {scene_visibility(LIBRARY_SCENE, shown=True)}
      <Children>
{fixed_group('LibLeft', 'vertical', LIB_LEFT_W, 160,
             lib_preview() + vspace(2)
             + fixed_group('LibSidebarBox', 'horizontal', LIB_LEFT_W, 160 - LIB_PREVIEW_H - 2,
                           '<LibrarySidebar></LibrarySidebar>'))}
{vrule()}
{fixed_group('LibRight', 'vertical', LIB_RIGHT_W, 160,
             lib_top_row() + vspace(2)
             + fixed_group('LibTableBox', 'horizontal', LIB_RIGHT_W, 160 - LIB_TOP_H - 2,
                           '<Library><ShowButtonText>false</ShowButtonText></Library>'))}
      </Children>
    </WidgetGroup>

'''


# -------------------------------------------------------------------- CSS ----

BASE_BTNS = ['DkPlay', 'DkCue', 'DkKey', 'DkSync', 'DkLead', 'DkLoopAct'] + [f'DkLoopSz{i}' for i in range(len(LOOP_SIZES))]
loop_sel = ',\n'.join([f'#DkLoopSz{i}[value="{v}"]' for i, (_, v) in enumerate(LOOP_SIZES)]
                      + [f'#DkLoopSz{len(LOOP_SIZES) - 1}[value="{v}"]' for v in LOOP_TAIL_SIZES])

CSS = f'''
/* GENERATED by gen_skin.py - edit the generator, not this block.
   Design scheme "Scan" register; deck colours kept. */
* {{ font-family: {FONT}; }}

#Mixxx, WWidgetGroup {{ background-color: {INK}; }}
WLabel, WTrackProperty, WNumberBpm, WNumberPos {{ color: {LINE}; }}
#Rule {{ background-color: {HAIR}; }}

#DeckPanelA, #DeckPanelB, #DeckPanelA WWidgetGroup, #DeckPanelB WWidgetGroup {{ background-color: {INK}; }}
#DkCoverA {{ border: 1px solid {DECKS[0]["color"]}; }}
#DkCoverB {{ border: 1px solid {DECKS[1]["color"]}; }}

#DkTitle {{ color: {LINE}; font-family: {DISPLAY}; font-size: 15px; qproperty-alignment: 'AlignLeft|AlignBottom'; }}
#DkArtist {{ color: {DIM}; font-size: 11px; qproperty-alignment: 'AlignLeft|AlignTop'; }}
#DkAlbum {{ color: {FAINT}; font-size: 11px; qproperty-alignment: 'AlignLeft|AlignTop'; }}

#DkTimeRemain, #DkTimeElapsed {{ qproperty-wordWrap: true; padding: 0; }}
#DkTimeRemain {{ color: {LINE}; font-family: {DISPLAY}; font-size: 18px; qproperty-alignment: 'AlignRight|AlignBottom'; }}
#DkTimeElapsed {{ color: {DIM}; font-size: 11px; qproperty-alignment: 'AlignRight|AlignTop'; }}

#DkBpm {{ color: {LINE}; font-family: {DISPLAY}; font-size: 18px; qproperty-alignment: 'AlignRight|AlignBottom'; }}
#DkRatePct, #DkRate, #DkFileBpm {{ color: {DIM}; font-size: 11px; qproperty-alignment: 'AlignRight|AlignTop'; }}

#DkLetterA, #DkLetterB {{ font-family: {DISPLAY}; font-size: 30px; qproperty-alignment: 'AlignCenter'; }}
#DkLetterA {{ color: {DECKS[0]["color"]}; }}
#DkLetterB {{ color: {DECKS[1]["color"]}; }}

#DkOverviewBox {{ background-color: {INK}; border: 1px solid {EDGE}; }}

/* Buttons: outlined boxes; filled only when lit (the deliberate accents) */
{', '.join('#' + b for b in BASE_BTNS)} {{
  font-size: 11px; font-weight: bold; color: {DIM};
  background-color: {INK}; border: 1px solid {EDGE}; border-radius: 0px;
}}
#DkPlay {{ font-size: 15px; }}
#DkPlay[displayValue="1"], #DkLoopAct[displayValue="1"] {{ color: {INK}; background-color: {LIME}; border-color: {LIME}; }}
#DkCue[displayValue="1"] {{ color: {INK}; background-color: {ORANGE}; border-color: {ORANGE}; }}
#DkSync {{ color: #7d93ff; border-color: {BLUE}; }}
#DkSync[displayValue="1"] {{ color: {LINE}; background-color: {BLUE}; border-color: {BLUE}; }}
#DkKey[displayValue="1"], #DkLead[displayValue="2"] {{ color: {INK}; background-color: {LINE}; border-color: {LINE}; }}
#DkLead[displayValue="1"] {{ color: {LINE}; border-color: {LINE}; }}
{loop_sel} {{ color: {LINE}; border-color: {LINE}; }}

#HotcueButton {{
  font-size: 11px; font-weight: bold; border: 1px solid {EDGE}; border-radius: 0px;
  text-align: left; padding-left: 6px;
}}
#HotcueButton[displayValue="0"] {{ background-color: {INK}; color: {FAINT}; }}
#HotcueButton[light="true"] {{ color: {INK}; }}
#HotcueButton[dark="true"] {{ color: {LINE}; }}
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
  background-image: url(skin:/image/hc-{lo}.png); background-repeat: repeat-xy; color: {INK}; border-color: {d["color"]};
}}
{p}[type="loop"][displayValue="1"], {p}[type="loop"][displayValue="2"] {{
  background-image: url(skin:/image/hc-{lo}-loop.png); color: {LINE};
}}
"""


CSS += ''.join(hotcue_tint(d) for d in DECKS)

CSS += f'''
/* Library page */
#LibraryPage, #LibraryPage WWidgetGroup {{ background-color: {INK}; }}
#LibSort0, #LibSort1, #LibSort2, #LibSort3, #LibSort4, #LibSort5 {{
  font-size: 11px; font-weight: bold; color: {DIM}; background-color: {INK}; border: 1px solid {EDGE}; border-radius: 0px;
}}
#LibSort0[value="2"], #LibSort1[value="1"], #LibSort2[value="3"], #LibSort3[value="15"], #LibSort4[value="20"], #LibSort5[value="13"] {{ color: {LINE}; border-color: {LINE}; }}

WTrackTableView, WLibrarySidebar, WLibraryTextBrowser {{
  font-size: 12px; color: {LINE}; border: none;
  background-color: {INK}; alternate-background-color: #121211;
  selection-color: {INK}; selection-background-color: {LIME};
}}
WTrackTableView {{ qproperty-trackPlayedColor: {FAINT}; qproperty-focusBorderColor: {LIME}; }}
/* BPM column: hide Mixxx's BPM-lock checkbox, just show the number */
#LibraryBPMButton::item {{ color: {LINE}; border: 0px; }}
#LibraryBPMButton::indicator {{ width: 0px; height: 0px; image: none; border: none; }}
WTrackTableView::item:selected, WLibrarySidebar::item:selected {{ color: {INK}; background-color: {LIME}; }}
WLibrarySidebar {{ show-decoration-selected: 0; outline: none; }}
/* Thin scroll position indicators (nothing is scrolled with a mouse here) */
QScrollBar:vertical {{ width: 4px; background: {INK}; border: none; margin: 0px; }}
QScrollBar::handle:vertical {{ background: {EDGE}; min-height: 12px; border: none; }}
QScrollBar:horizontal {{ height: 0px; border: none; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ height: 0px; width: 0px; border: none; background: none; }}

/* The sort labels above are the header (columns aligned under them) */
WTrackTableViewHeader {{ max-height: 0px; min-height: 0px; border: none; }}

#LibPreview, #LibPreview WWidgetGroup {{ background-color: {INK}; }}
#LibPreviewCover {{ border: 1px solid {EDGE}; }}
#LibPreviewOverviewBox {{ background-color: {INK}; border: 1px solid {EDGE}; }}
/* Preview column: empty except on the song playing in preview (lime) */
#LibraryPreviewButton {{ background: transparent; margin: 0px; padding: 0px; border: none; }}
#LibraryPreviewButton:!checked {{ image: none; }}
#LibraryPreviewButton:checked {{ image: url(skin:/image/preview-playing.svg); background-color: {LIME}; }}

/* FX page */
#FxUnit, #FxUnit WWidgetGroup {{ background-color: {INK}; }}
#FxCol {{ border-right: 1px solid {HAIR}; }}
#FxFooter {{ border-top: 1px solid {HAIR}; }}
#FxOn {{ font-size: 11px; font-weight: bold; color: {DIM}; background-color: {INK}; border: 1px solid {EDGE}; border-radius: 0px; }}
#FxOn[displayValue="1"] {{ color: {INK}; background-color: {LIME}; border-color: {LIME}; }}
#FxReset {{ font-size: 11px; font-weight: bold; color: {LINE}; background-color: {INK}; border: 1px solid {EDGE}; qproperty-alignment: 'AlignCenter'; }}
#FxName, #FxSuperName {{ color: {LINE}; font-family: {DISPLAY}; font-size: 14px; qproperty-alignment: 'AlignCenter'; }}
#FxUnitLabel {{ color: {LINE}; font-family: {DISPLAY}; font-size: 16px; qproperty-alignment: 'AlignLeft|AlignVCenter'; }}
#FxDeckA, #FxDeckB {{ font-size: 12px; font-weight: bold; color: {FAINT}; background-color: {INK}; border: 1px solid {EDGE}; border-radius: 0px; }}
#FxDeckA[displayValue="1"] {{ color: {INK}; background-color: {DECKS[0]["color"]}; border-color: {DECKS[0]["color"]}; }}
#FxDeckB[displayValue="1"] {{ color: {INK}; background-color: {DECKS[1]["color"]}; border-color: {DECKS[1]["color"]}; }}
'''


# ------------------------------------------------------------------ write ----

src = SKIN.read_text(encoding='utf-8')

src = src[:src.index('    <!-- ===== ')] + BROWSE + LIBRARY + EXPANDED + FX

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
        f'<rect x="7.5" y="1" width="3" height="98" fill="{INK}" stroke="{EDGE}" stroke-width="1"/>'
        f'<g stroke="{EDGE}" stroke-width="1">{ticks}</g>'
        f'<line x1="0" y1="50" x2="18" y2="50" stroke="{LINE}" stroke-width="1"/>'
        '</svg>', encoding='utf-8')
    (SKIN_DIR / 'image' / f'pitch-handle-{lo}.svg').write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="8" viewBox="0 0 18 8">'
        f'<rect x="0.5" y="0.5" width="17" height="7" fill="{LINE}" stroke="{INK}" stroke-width="1"/>'
        f'<rect x="2" y="3.3" width="14" height="1.4" fill="{d["color"]}"/>'
        '</svg>', encoding='utf-8')
    Image.new('RGB', (4, 4), d['cue']).save(SKIN_DIR / 'image' / f'hc-{lo}.png')
    Image.new('RGB', (4, 4), d['loop']).save(SKIN_DIR / 'image' / f'hc-{lo}-loop.png')
(SKIN_DIR / 'image' / 'hotcue-loop.svg').write_text(
    '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="10" viewBox="0 0 14 10">'
    '<path d="M3 2h7a2 2 0 0 1 2 2v2a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5" fill="none" stroke="#ffffff" stroke-width="1.4"/>'
    '<path d="M0 5.5l2-2.5 2 2.5z" fill="#ffffff"/></svg>', encoding='utf-8')
(SKIN_DIR / 'image' / 'fx-knob-bg.svg').write_text(
    '<svg xmlns="http://www.w3.org/2000/svg" width="70" height="70" viewBox="0 0 70 70">'
    f'<circle cx="35" cy="35" r="22" fill="{INK}" stroke="{EDGE}" stroke-width="1.5"/>'
    '</svg>', encoding='utf-8')
(SKIN_DIR / 'image' / 'fx-knob-indicator.svg').write_text(
    '<svg xmlns="http://www.w3.org/2000/svg" width="70" height="70" viewBox="0 0 70 70">'
    f'<rect x="33.75" y="15" width="2.5" height="13" fill="{LINE}"/>'
    '</svg>', encoding='utf-8')
(SKIN_DIR / 'image' / 'preview-playing.svg').write_text(
    '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 10 10">'
    '<path d="M2 1l7 4-7 4z" fill="#0d0d0d"/></svg>', encoding='utf-8')
print('ok')
