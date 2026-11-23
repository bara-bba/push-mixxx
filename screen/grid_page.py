"""Beatgrid edit mode, painted over the Mix page (Pi).

pusher-script.js (PUSH2T.grid) enters it on a 2 s SELECT hold in Device and
switches the skin to the waveform page (zoomed, scrolling, beat lines). This
draws the labels of the top buttons that edit the grid and, over the parts of
the page not needed (the deck headers, the other deck's waveform), the
edited deck's grid BPM and what to do next. State comes through
bridge-script.js (SysEx 0x06): deck, BEAT 1 time, file BPM, beats measured.
"""

from PIL import ImageDraw

from pi_stats import BODY_BOLD_FONTS, BODY_FONTS, DIM, EDGE, FAINT, INK, LIME, LINE, _font, DISPLAY_FONTS

# Pusher160 waveform page (gen_skin.py): 52px of deck headers, then deck A's
# and deck B's waveform lanes, 54px each
HEADER_BOTTOM = 52
LANES = {1: (52, 105), 2: (106, 159)}
LABEL_H = 17
DECK_COLORS = {1: (60, 200, 90), 2: (170, 90, 230)}

# Push 2 top display buttons: CC 102 + i sits above x 120 * i .. 120 * (i + 1)
LABELS = ['BEAT HERE', 'BEAT 1', 'BEAT 2', '÷ 2', '× 2', 'UNDO', 'ZOOM', 'DONE']


def _fmt_time(seconds):
    m, s = divmod(seconds, 60)
    return f'{int(m)}:{s:04.1f}'


class GridPage:
    def __init__(self):
        self._f_label = _font(BODY_BOLD_FONTS, 11)
        self._f_big = _font(DISPLAY_FONTS, 26)
        self._f = _font(BODY_FONTS, 12)
        self._f_bold = _font(BODY_BOLD_FONTS, 12)

    def draw(self, frame, deck, mark_a, bpm, n):
        """deck 1/2; mark_a = BEAT 1 in seconds or None; bpm = grid BPM; n =
        beats the last BEAT 2 measured over (0 = none yet)."""
        draw = ImageDraw.Draw(frame)
        # button labels
        draw.rectangle([0, 0, 959, LABEL_H], fill=INK)
        for i, label in enumerate(LABELS):
            x0, x1 = 120 * i + 3, 120 * (i + 1) - 4
            on = (i == 1 and mark_a is not None) or i == 7
            if on:
                draw.rectangle([x0, 1, x1, LABEL_H - 2], fill=LIME)
            else:
                draw.rectangle([x0, 1, x1, LABEL_H - 2], outline=EDGE)
            tw = draw.textlength(label, font=self._f_label)
            draw.text(((x0 + x1 - tw) / 2, 3), label, font=self._f_label, fill=INK if on else LINE)

        # info band over the deck headers
        y0, y1 = LABEL_H + 1, HEADER_BOTTOM - 1
        draw.rectangle([0, y0, 959, y1], fill=INK)
        draw.line([0, y1, 959, y1], fill=EDGE)
        color = DECK_COLORS.get(deck, LINE)
        draw.text((10, y0 + 2), 'GRID EDIT', font=self._f_bold, fill=LINE)
        draw.text((10, y0 + 17), f'DECK {"AB"[deck - 1]}', font=self._f_bold, fill=color)
        bpm_txt = f'{bpm:.2f}' if bpm > 0 else '—'
        draw.text((100, y0 + 2), bpm_txt, font=self._f_big, fill=LINE)
        bx = 100 + draw.textlength(bpm_txt, font=self._f_big) + 6
        draw.text((bx, y0 + 14), 'BPM', font=self._f_bold, fill=DIM)
        sx = 300
        if mark_a is None:
            line1 = 'Jog onto a beat (best: the first downbeat), press BEAT 1'
            line2 = 'or move the grid with ◄ ► and the BPM with ▲ ▼'
        else:
            line1 = f'BEAT 1 at {_fmt_time(mark_a)} — now jog to a beat further on and press BEAT 2'
            line2 = 'the further away, the more precise the BPM'
            if n:
                line2 = f'BPM set from {n} beats — BEAT 2 again on a later beat to refine'
        draw.text((sx, y0 + 2), line1, font=self._f, fill=LINE)
        draw.text((sx, y0 + 17), line2, font=self._f, fill=DIM)

        # hints over the other deck's lane
        other = 2 if deck == 1 else 1
        ly0, ly1 = LANES[other]
        draw.rectangle([0, ly0, 959, ly1], fill=INK)
        if other == 2:
            draw.line([0, ly0, 959, ly0], fill=EDGE)
        hints = [('◄ ►', 'grid earlier / later'), ('▲ ▼', 'BPM ±0.01'), ('SHIFT', '× 10'), ('DELETE', 'undo all'),
                 ('JOG', 'scrub'), ('SHIFT + A / B', 'switch deck'), ('SELECT', 'exit')]
        x, y = 10, ly0 + (ly1 - ly0) // 2 - 8
        for key, what in hints:
            draw.text((x, y), key, font=self._f_bold, fill=LINE)
            x += draw.textlength(key, font=self._f_bold) + 6
            draw.text((x, y), what, font=self._f, fill=FAINT)
            x += draw.textlength(what, font=self._f) + 22
        return frame
