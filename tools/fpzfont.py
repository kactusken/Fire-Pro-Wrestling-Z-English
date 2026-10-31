#!/usr/bin/env python3
"""The story's two-letter glyphs: English drawn two letters a cell in the game's own fonts.

  fpzfont.py sheet PNG [TEXT]     the pair glyphs of TEXT (default: a sample) at 4x, both fonts
  fpzfont.py letters              redraw tools/fonts/pairletters.bin (Pillow): every printable
                                  character, left and right half, both sizes - the build combines
                                  them into pairs without Pillow

Why: the story window puts every character in a full cell (20 a line) and drops ASCII spaces and
punctuation (docs/TECHNICAL.md, Text). The fonts (SCE24I26.GF 26x26, SCE20I22.GF 22x22, 4bpp,
94x94 JIS grid - no header) get new glyphs: each holds two characters, so a line holds 40. The
codes come from JIS row 15 (empty in the font), then level-2 kanji the English build never shows
(rows 85-94 are empty too, but menus don't take their lead byte 0xEB+).

The build (fpztext.py) collects every pair its English needs, gives each a code (pair_codes()),
draws them into every copy of both fonts (patch_font()) and writes the text with those codes
(encode()). Glyph style as the game's: white core (15), anti-aliased, a dark ring (4) with soft
edges. Pillow is needed to draw - the build imports it only when there is English to encode.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402

FONTS = {26: 'SCE24I26', 22: 'SCE20I22'}
# Monospaced, so every letter fills its half cell: a proportional font left gaps around narrow
# letters ("Ha l l", owner play-test 2026-10-29)
FONT_FILE = Path(__file__).resolve().parent / 'fonts' / 'DejaVuSansMono-Bold.ttf'
# Where the fonts are: (archive, entry, size, compressed)
FONT_COPIES = [
    ('FPFILES.OAH', 'BOOTREAD\\SCE20I22.GF', 22, False),
    ('FPFILES.OAH', 'AETC\\SCE24I26.GF', 26, False),
    ('STORY.OAH', 'AETC\\SCE24I26.GF', 26, False),
    ('STORY.OAH', 'AETC\\SCE20I22.LZO', 22, True),
    ('STORY.OAH', 'AETC\\SCE24I26.LZO', 26, True),
]
# JIS rows (1-based), in order. Not 85-94: lead byte 0xEB+ is a single byte to the menu renderers
# (verified headless 2026-10-29); row 15 is empty, 16-84 are kanji the English build never shows
# (16-47 were the name entry's 単漢字 list until the English keyboard replaced it, 2026-10-29).
# Lead bytes below 0xA0 first (rows 15-62), the rest after.
PAIR_ROWS = list(range(15, 63)) + list(range(84, 62, -1))
CHARSET = set(' !"#$%&\'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[]_abcdefghijklmnopqrstuvwxyz')


def sjis(row, cell):
    """Shift-JIS bytes of JIS row/cell (1-based)."""
    b1 = (row + 1) // 2 + (0x80 if row <= 62 else 0xC0)
    if row % 2:
        b2 = cell + (0x3F if cell <= 63 else 0x40)
    else:
        b2 = cell + 0x9E
    return bytes((b1, b2))


def index_of(code):
    """Glyph index of a Shift-JIS code in the fonts (row * 94 + cell, 0-based)."""
    b1, b2 = code[0], code[1]
    r = (b1 - 0x81 if b1 < 0xA0 else b1 - 0xC1) * 2
    if b2 >= 0x9F:
        r, c = r + 1, b2 - 0x9F
    else:
        c = b2 - 0x40 - (1 if b2 >= 0x80 else 0)
    return r * 94 + c


def free_codes(exclude=()):
    """Shift-JIS codes for pairs, in order, skipping any code in `exclude` (codes still shown)."""
    ex = set(exclude)
    for row in PAIR_ROWS:
        for cell in range(1, 95):
            c = sjis(row, cell)
            if c not in ex:
                yield c


# ---------------------------------------------------------------- drawing

_FONT_CACHE = {}


def _font(half):
    """The font at the size whose advance fills a half cell `half` pixels wide."""
    from PIL import ImageFont
    if half not in _FONT_CACHE:
        f = ImageFont.truetype(str(FONT_FILE), 100)
        _FONT_CACHE[half] = ImageFont.truetype(str(FONT_FILE), int(100 * half * 0.98 / f.getlength('M')))
    return _FONT_CACHE[half]


def glyph(pair, n, centres=(0.25, 0.75)):
    """The 4bpp pixels (list of n*n values 0-15) of a glyph in an n-pixel cell: the characters of
    `pair` centred at `centres` (fractions of the cell; letters past an edge are clipped)."""
    from PIL import Image, ImageDraw, ImageFilter
    s = 4                                    # supersampling
    W = n * s
    half = W // 2
    font = _font(half)
    mask = Image.new('L', (W, W), 0)
    dr = ImageDraw.Draw(mask)
    asc, desc = font.getmetrics()
    base_y = int(W * 0.80)                   # baseline: as the game's capitals, descenders below
    for ch, c in zip(pair, centres):
        if ch == ' ':
            continue
        w = dr.textlength(ch, font=font)
        x = c * W - w / 2
        dr.text((x, base_y - asc), ch, font=font, fill=255)
    fill = mask.resize((n, n), Image.LANCZOS)
    ring = mask.filter(ImageFilter.MaxFilter(2 * s + 1)).resize((n, n), Image.LANCZOS)
    out = []
    for f, r in zip(fill.getdata(), ring.getdata()):
        v = 0
        if r:
            v = min(4, round(r / 255 * 4.4))
        if f > 24:
            v = max(v, 4 + round(f / 255 * 11))
        out.append(v)
    return out


LETTERS = Path(__file__).resolve().parent / 'fonts' / 'pairletters.bin'
PRINTABLE = ''.join(chr(c) for c in range(0x20, 0x7F))
_LETTERS = None


# Letter positions frozen in LETTERS (centre, fraction of the cell): the two halves of a pair; and
# for half-shifted glyphs (encode_shifted) the left edge, the middle and the right edge.
POSITIONS = (0.25, 0.75, 0.0, 0.5, 1.0)


def make_letters():
    """Draw every printable character at each of POSITIONS, both sizes, into LETTERS (Pillow; run
    `fpzfont.py letters` after changing the font or glyph())."""
    out = bytearray()
    for n in (26, 22):
        for c in POSITIONS:
            for ch in PRINTABLE:
                out += bytes(glyph(ch, n, (c,)))
    LETTERS.write_bytes(out)
    print(f'{LETTERS.name}: {len(PRINTABLE)} characters x {len(POSITIONS)} positions x 2 sizes')


def _letter(ch, n, pos):
    """Frozen pixels of `ch` at POSITIONS[pos] in an n-pixel cell."""
    global _LETTERS
    if _LETTERS is None:
        _LETTERS = LETTERS.read_bytes()
    g = n * n
    base = 0 if n == 26 else len(POSITIONS) * len(PRINTABLE) * 26 * 26
    i = base + (pos * len(PRINTABLE) + PRINTABLE.index(ch)) * g
    return _LETTERS[i:i + g]


def pair_pixels(pair, n):
    """A glyph from the frozen letters (no Pillow), the brighter pixel where letters meet: a pair
    (2 characters: left and right half), or a half-shifted glyph (3 characters, encode_shifted: the right
    half of the first, the second in the middle, the left half of the third)."""
    poss = (0, 1) if len(pair) == 2 else (2, 3, 4)
    layers = [_letter(ch, n, p) for ch, p in zip(pair, poss) if ch != ' ']
    if not layers:
        return [0] * (n * n)
    return [max(v) for v in zip(*layers)]


def pack(px):
    """4bpp, low nibble first (as the .GF files)."""
    return bytes(px[i] | px[i + 1] << 4 for i in range(0, len(px), 2))


def patch_font(font, n, codes):
    """Draw {code: pair} into a font's bytes (n = cell size)."""
    font = bytearray(font)
    g = n * n // 2
    for code, pair in codes.items():
        i = index_of(code)
        font[i * g:(i + 1) * g] = pack(pair_pixels(pair, n))
    return bytes(font)


# ---------------------------------------------------------------- text

def encode_shifted(text, pairs):
    """Bytes for an odd-length run drawn half a letter to the right: its padding split
    between both ends, so it centres like an even run. Cell k holds the right half of character
    2k-1, character 2k and the left half of character 2k+1 (blanks past the ends)."""
    s = ' ' + text + ' '
    out = bytearray()
    for k in range((len(text) + 1) // 2):
        t = s[2 * k:2 * k + 3]
        if t not in pairs:
            pairs[t] = next(pairs[None])
        out += pairs[t]
    return bytes(out)


def encode_run(text, pairs, odd_ascii=False):
    """Bytes for a run of plain characters: two a code; `pairs` (dict pair -> code) is filled
    with codes from the generator stored under the key None. An odd last character is paired with
    a space, or (odd_ascii, for tight fields) stays one ASCII byte."""
    tail = b''
    if len(text) % 2:
        if odd_ascii:
            text, tail = text[:-1], text[-1].encode('ascii')
        else:
            text += ' '
    out = bytearray()
    for i in range(0, len(text), 2):
        p = text[i:i + 2]
        if p not in pairs:
            pairs[p] = next(pairs[None])
        out += pairs[p]
    return bytes(out) + tail


def sheet(png, text='Hey, Hikawa. You\'re back! "How was Mexico?" 0123456789 (Yes...) Wait-up; OK?'):
    from PIL import Image
    pairs = [text[i:i + 2].ljust(2) for i in range(0, len(text), 2)]
    rows = []
    for n in (26, 22):
        im = Image.new('L', (n * len(pairs), n))
        for k, p in enumerate(pairs):
            px = glyph(p, n)
            for i, v in enumerate(px):
                im.putpixel((k * n + i % n, i // n), v * 17)
        rows.append(im)
    out = Image.new('L', (max(r.width for r in rows), sum(r.height for r in rows) + 4))
    y = 0
    for r in rows:
        out.paste(r, (0, y))
        y += r.height + 4
    out.resize((out.width * 3, out.height * 3), Image.NEAREST).save(png)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == 'letters':
        make_letters()
        return 0
    if len(argv) >= 2 and argv[0] == 'sheet':
        sheet(argv[1], *argv[2:3])
        return 0
    print(__doc__)
    return 0 if argv and argv[0] in ('-h', '--help') else 1


if __name__ == '__main__':
    sys.exit(main())
