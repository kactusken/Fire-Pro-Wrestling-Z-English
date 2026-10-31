#!/usr/bin/env python3
"""Game images: export every original texture and import the English ones.

  gfx.py export [OUT]     every texture to OUT/<id>.png + .json (default review/images-original)

Textures are P2TXB (docs/TECHNICAL.md): a 0x40-byte header, a 256-colour RGBA palette in CSM1
order (alpha 0x80 = opaque), then 8bpp pixels, unswizzled; the size isn't in the header - square
when the pixel count is a square, else 256 wide (and 512 for 512x256 etc. by pixel count). They are
.GST files or CP00-compressed .LZO files inside the .OAH archives, which nest. Ids are the archive
chain with `/` for each level: `FPFILES/EDITMENU/MAINMENU/PACK01_A`.

export_all(extracted, out) -> count; import_images(images, files) -> count (see build.py).
No dependencies: build.py must run on a plain python3.
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fpz  # noqa: E402
import paths  # noqa: E402
import pngio  # noqa: E402

ARCHIVES = ['FPFILES.OAH', 'STORY.OAH']        # WRSPARTS / INFPARTS: wrestler faces and parts, no text
HEADER, PALETTE = 0x40, 0x400


def csm1(i):
    """Palette slot <-> colour index (CSM1 swaps the 8-entry blocks 8-15 and 16-23 of every 32)."""
    return (i & 0xE7) | ((i & 0x10) >> 1) | ((i & 0x08) << 1)


def size_of(n):
    s = int(math.isqrt(n))
    if s * s == n:
        return s, s
    for w in (512, 256, 128, 64):
        if n % w == 0 and n // w <= w:
            return w, n // w
    return 256, n // 256


def textures(blob, chain):
    """Yield (id, chain, P2TXB bytes) for every texture in an archive, recursing into nested ones."""
    a = fpz.Oah(blob)
    for name in a.names():
        data = a.read(name)
        sub = chain + [name]
        if name.upper().endswith('.OAH'):
            yield from textures(data, sub)
            continue
        if data[:4] == b'CP00':
            try:
                data = fpz.cp00_decode(data)
            except (ValueError, IndexError, struct_error):
                continue
        if data[:5] == b'P2TXB' and len(data) > HEADER + PALETTE:
            yield texture_id(sub), sub, data


struct_error = __import__('struct').error


def texture_id(chain):
    parts = [chain[0].rsplit('.', 1)[0]] + [c.replace('\\', '/').rsplit('.', 1)[0] for c in chain[1:]]
    return '/'.join(parts)


def decode(data):
    pal = data[HEADER:HEADER + PALETTE]
    px = data[HEADER + PALETTE:]
    w, h = size_of(len(px))
    colours, alpha = [], []
    for i in range(256):
        s = csm1(i) * 4
        colours.append((pal[s], pal[s + 1], pal[s + 2]))
        alpha.append(min(255, pal[s + 3] * 2))
    rows = [list(px[y * w:(y + 1) * w]) for y in range(h)]
    return w, h, rows, colours, alpha


def export_all(extracted, out):
    out = Path(out)
    n = 0
    for arc in ARCHIVES:
        for tid, chain, data in textures((Path(extracted) / arc).read_bytes(), [arc]):
            w, h, rows, colours, alpha = decode(data)
            p = out / (tid + '.png')
            p.parent.mkdir(parents=True, exist_ok=True)
            pngio.write(p, rows, colours, alpha)
            p.with_suffix('.json').write_text(json.dumps({'chain': chain, 'width': w, 'height': h}))
            n += 1
    return n


def _put(blob, chain, data):
    """`blob` (an archive) with the entry at `chain` replaced by `data`, nested archives rebuilt."""
    a = fpz.Oah(blob)
    if len(chain) == 1:
        a.write(chain[0], data)
    else:
        a.write(chain[0], _put(a.read(chain[0]), chain[1:], data))
    return a.bytes()


def _get(blob, chain):
    a = fpz.Oah(blob)
    d = a.read(chain[0])
    return d if len(chain) == 1 else _get(d, chain[1:])


# Screen packs: CP00 files holding a screen's textures back to back (palette, then pixels, as in
# the texture files). The game loads some screens from these, not from the texture files
# (wrestler select shows S_ONEMCH's WSELECT - seen headless 2026-10-29), so every imported image
# is also patched wherever its original palette + pixels appear in one.
PACKS = [('FPFILES.OAH', ['EDITMENU\\S_ONEMCH.LZO']), ('FPFILES.OAH', ['EDITMENU\\S_TITLE.LZO']),
         ('FPFILES.OAH', ['EDITMENU\\OPENING_NEW.LZO'])]


def _patch_packs(originals, files):
    """originals: [(original P2TXB bytes, new pixels)] -> packs patched (count of copies)."""
    n = 0
    for arc, chain in PACKS:
        blob = bytes(files.get(arc))
        pack = bytearray(fpz.cp00_decode(_get(blob, chain)))
        hits = 0
        for orig, new in originals:
            block = orig[HEADER:]
            at = pack.find(block)
            while at >= 0:
                pack[at + PALETTE:at + PALETTE + len(new)] = new
                hits += 1
                at = pack.find(block, at + 1)
        if hits:
            files.put(arc, _put(blob, chain, fpz.cp00_encode(bytes(pack))))
            n += hits
    return n


def import_images(images, files):
    n = 0
    originals = []
    for tid, png in sorted(images.items()):
        meta = json.loads((paths.ORIGINAL_IMAGES / (tid + '.json')).read_text())
        chain = meta['chain']
        arc = files.get(chain[0])
        raw = _get(bytes(arc), chain[1:])
        packed = raw[:4] == b'CP00'
        data = bytearray(fpz.cp00_decode(raw) if packed else raw)
        img = pngio.read(png)
        w, h = meta['width'], meta['height']
        if (img.width, img.height) != (w, h):
            sys.exit(f'{png}: {img.width}x{img.height}, the game\'s texture is {w}x{h}')
        flat = bytes(v for row in img.rows for v in row)
        originals.append((bytes(data), flat))
        data[HEADER + PALETTE:HEADER + PALETTE + w * h] = flat
        new = fpz.cp00_encode(bytes(data)) if packed else bytes(data)
        files.put(chain[0], _put(bytes(arc), chain[1:], new))
        n += 1
    if originals:
        print(f'images: {_patch_packs(originals, files)} copies in screen packs')
    return n


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == 'export':
        out = Path(argv[1]) if len(argv) > 1 else paths.ORIGINAL_IMAGES
        print(f'{export_all(paths.EXTRACTED, out)} textures -> {out}')
        return 0
    print(__doc__)
    return 1


if __name__ == '__main__':
    sys.exit(main())
