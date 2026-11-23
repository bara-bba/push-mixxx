"""Renders Pushy's PNG/ICO icons from the same shapes as icon.svg (the style of
itunes-usb-exporter's icon: lime lines on a near-black rounded square).
Needs Pillow (the screen app has it).  python screen/web/make_icons.py"""
import os

from PIL import Image, ImageDraw

INK, LIME = (11, 11, 11, 255), (200, 245, 60, 255)
HERE = os.path.dirname(os.path.abspath(__file__))
SS = 8  # supersampling for smooth edges

# 3x3 Push pads in the 64x64 icon space; the diagonal ones lit
PAD, GAP = 12, 5
X0 = Y0 = (64 - (3 * PAD + 2 * GAP)) / 2   # centred: 46 wide -> 9
LIT = {(0, 0), (1, 1), (2, 2)}


def icon(size, rounded=True):
    n = size * SS
    s = n / 64.0
    img = Image.new('RGBA', (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if rounded:
        d.rounded_rectangle([0, 0, n - 1, n - 1], radius=12 * s, fill=INK)
    else:
        d.rectangle([0, 0, n, n], fill=INK)
    for r in range(3):
        for c in range(3):
            x, y = X0 + c * (PAD + GAP), Y0 + r * (PAD + GAP)
            box = [x * s, y * s, (x + PAD) * s, (y + PAD) * s]
            if (r, c) in LIT:
                d.rounded_rectangle(box, radius=2.5 * s, fill=LIME)
            else:
                d.rounded_rectangle(box, radius=2.5 * s, outline=LIME, width=round(2.5 * s))
    return img.resize((size, size), Image.LANCZOS)


def svg():
    pads = []
    for r in range(3):
        for c in range(3):
            x, y = X0 + c * (PAD + GAP), Y0 + r * (PAD + GAP)
            if (r, c) in LIT:
                pads.append(f'<rect x="{x}" y="{y}" width="{PAD}" height="{PAD}" rx="2.5" fill="#C8F53C"/>')
            else:
                pads.append(f'<rect x="{x + 1.25}" y="{y + 1.25}" width="{PAD - 2.5}" height="{PAD - 2.5}" rx="1.5" '
                            f'fill="none" stroke="#C8F53C" stroke-width="2.5"/>')
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">\n'
            '  <rect width="64" height="64" rx="12" fill="#0B0B0B"/>\n  ' + '\n  '.join(pads) + '\n</svg>\n')


def main():
    icon(192).save(os.path.join(HERE, 'icon-192.png'))
    icon(512).save(os.path.join(HERE, 'icon-512.png'))
    icon(180, rounded=False).save(os.path.join(HERE, 'apple-touch-icon.png'))  # iOS rounds it itself
    icon(48).save(os.path.join(HERE, 'favicon.ico'), sizes=[(16, 16), (32, 32), (48, 48)])
    with open(os.path.join(HERE, 'icon.svg'), 'w', encoding='utf-8') as f:
        f.write(svg())
    print('icons written to', HERE)


if __name__ == '__main__':
    main()
