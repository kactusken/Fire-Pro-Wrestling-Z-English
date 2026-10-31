#!/usr/bin/env python3
"""The unused ring sets, and a square F.P.Z. ring, in the ring menu (build.py group `rings`,
docs/PATCHES.md).

Ring ids 0-22 index three pointer tables (mat, posts, post layout) and ids 23 up are edit rings
(edit promotion = id - 23). patches() moves the tables and the menu's name table and order list
into the dead debug readout at 0x1206A0, appends the new rings as ids 23-29, and moves the edit
rings to id 30 up. build.py calls it after the text steps, so the name table copies the pointers
the translation left; names() runs among the text steps, so the pair glyphs get drawn.

The F.P.Z. mat (MAT_99_1225) is the dodecagon's, whose model names it; a model's texture field
holds 11 characters, so assets() copies it over the unused MAT_99.GST and points the unused model
MAT97.SOB at that, with the plain white apron of set 13.

    names(name_set)                    the menu names, as the game's bytes
    patches(elf, names, to_offset)     codepatch entries (group `rings`) for the bytes in `elf`
    assets(files)                      the F.P.Z. ring's two file edits in FPFILES.OAH
"""
import struct

import fpz
import fpztext
import gfx
import mips_asm

FILE = 'SLPM_623.42'
AREA, AREA_END = 0x1206A0, 0x120C00    # the readout's code: nothing calls it (docs/HIDDEN_CONTENT.md)
LAYOUT_8, LAYOUT_4 = 0x37EA90, 0x37EA78  # post layouts, by the size of the POST model
# (mat model, post model, menu name, post layout)
RINGS = [
    ('MAT03.SOB', 'POST03.SOB', 'Independent World', LAYOUT_8),
    ('MAT08.SOB', 'POST08.SOB', 'Pale Blue', LAYOUT_8),
    ('MAT09.SOB', 'POST09.SOB', 'Lilac', LAYOUT_8),
    ('MAT11.SOB', 'POST11.SOB', 'NONNON', LAYOUT_4),
    ('MAT13.SOB', 'POST13.SOB', '<BATTRATION>', LAYOUT_4),
    ('MAT16.SOB', 'POST16.SOB', '<UWH>', LAYOUT_4),
    ('MAT97.SOB', 'POST13.SOB', 'F.P.Z.', LAYOUT_4),
]
VENUE_NAMES, VENUE_DOJO = 0x333AE8, 'Dojo'
OLD = 23                               # ring ids in the original tables
COUNT = OLD + len(RINGS)
MAT, POST, LAYOUT, NAME, ORDER = 0x2E2F18, 0x2E2EB8, 0x37EB38, 0x215560, 0x398080


def names(name_set):
    return [fpztext.encode(fpztext.resolve(n, name_set), center=True) for _, _, n, _ in RINGS]


def venue_patches(elf, encoded, to_offset):
    """Group `venues`: venue 10, the story's dojo, has no name of its own in the table."""
    entry, at = VENUE_NAMES + 10 * 4, 0x120F00
    data = (encoded or VENUE_DOJO.encode('ascii')) + b'\0'
    old = lambda a, n: bytes(elf[to_offset(FILE, a):to_offset(FILE, a) + n])
    return [('venues', FILE, entry, old(entry, 4), struct.pack('<I', at), None),
            ('venues', FILE, at, old(at, len(data)), data, None)]


PHOTO_HOOK = 0x120F20                  # after the dojo's name
PHOTO_DRAW, PHOTO_GRID, PHOTO_RANDOM, PHOTO_END = 0x183160, 0x183198, 0x183168, 0x1832A8


def venue_photo_code(elf, to_offset):
    """The Venue row's picture: RANDOM has a case of its own on the second sheet, the rest come from
    a grid on the first. The dojo gets a case too, the card below RANDOM's."""
    code, _ = mips_asm.assemble(f'''
        bne $a2, $a1, not_random
        nop
        j {PHOTO_RANDOM:#x}
        nop
    not_random:
        addiu $at, $zero, 10
        bne $a2, $at, grid
        lui $at, 0x3b00
        sw $at, 0xc($sp)
        lui $at, 0x3f00
        ori $at, $at, 0x8000
        sw $at, 0x10($sp)
        lw $at, -0x7d88($gp)
        sw $at, 0x14($sp)
        lui $at, 0x3f7e
        ori $at, $at, 0x8000
        sw $at, 0x18($sp)
        addiu $at, $zero, 0xa1
        j {PHOTO_END:#x}
        sw $at, 0($sp)
    grid:
        j {PHOTO_GRID:#x}
        nop
    ''', PHOTO_HOOK)
    old = bytes(elf[to_offset(FILE, PHOTO_HOOK):to_offset(FILE, PHOTO_HOOK) + len(code)])
    return [('venues', FILE, PHOTO_HOOK, old, code, None),
            ('venues', FILE, PHOTO_DRAW, 0x14C5000D, 0x08000000 | PHOTO_HOOK >> 2, 'the dojo in the Venue row')]


def _median_cut(colours, n):
    boxes = [colours]
    while len(boxes) < n:
        box = max((b for b in boxes if len(set(b)) > 1), key=len, default=None)
        if box is None:
            break
        boxes.remove(box)
        axis = max(range(3), key=lambda c: max(p[c] for p in box) - min(p[c] for p in box))
        box = sorted(box, key=lambda p: p[axis])
        boxes += [box[:len(box) // 2], box[len(box) // 2:]]
    return [tuple(sum(p[c] for p in b) // len(b) for c in range(3)) for b in boxes]


def dojo_photo(files):
    """Draw the card: the story's dojo background, cropped and scaled to the size of RANDOM's
    card, in its outline, in the colours the sheet has free. Made at build time from the game's own
    picture."""
    story = fpz.Oah(bytes(files.get('STORY.OAH')))
    art = fpz.cp00_decode(story.read('DOUJYOU.LZO'))
    pal = [art[0x20 + gfx.csm1(i) * 4:0x20 + gfx.csm1(i) * 4 + 3] for i in range(256)]
    pixels = art[0x440:]
    a = fpz.Oah(bytes(files.get('FPFILES.OAH')))
    sheet = bytearray(a.read('EDITMENU\\PLACE02.GST'))
    original = bytes(sheet)
    used = set(sheet[0x440:])
    free = [i for i in range(256) if i not in used]
    w, h, top = 206, 126, 30
    dx, dy = 640 / w, 388 / h
    card = []
    for y in range(h):
        for x in range(w):
            box = [pal[pixels[int(top + (y + v / 3) * dy) * 640 + int((x + u / 3) * dx)]]
                   for v in range(3) for u in range(3)]
            card.append(tuple(sum(p[c] for p in box) // 9 for c in range(3)))
    colours = _median_cut(card, len(free))
    for i, c in zip(free, colours):
        at = 0x20 + gfx.csm1(i) * 4
        sheet[at:at + 4] = bytes((*c, 0x80))
    cache = {}
    for y in range(h):
        for x in range(w):
            if sheet[0x440 + y * 256 + x]:      # inside RANDOM's rounded outline
                p = card[y * w + x]
                if p not in cache:
                    cache[p] = min(range(len(colours)), key=lambda k: sum((p[c] - colours[k][c]) ** 2 for c in range(3)))
                sheet[0x440 + (y + 128) * 256 + x] = free[cache[p]]
    a.write('EDITMENU\\PLACE02.GST', bytes(sheet))
    files.put('FPFILES.OAH', a.bytes())
    for arc, chain in gfx.PACKS:              # the screens load the sheet from their packs
        blob = bytes(files.get(arc))
        pack = bytearray(fpz.cp00_decode(gfx._get(blob, chain)))
        at = pack.find(original[0x440:])
        if at >= 0:
            pack[at - 0x420:at - 0x20] = sheet[0x20:0x420]
            pack[at:at + 0x10000] = sheet[0x440:]
            files.put(arc, gfx._put(blob, chain, fpz.cp00_encode(bytes(pack))))
    print(f'venues: dojo photo in {len(colours)} colours')


def assets(files):
    a = fpz.Oah(bytes(files.get('FPFILES.OAH')))
    model = a.read('MAT97.SOB')
    for old, new in ((b'MAT_00B.PNG', b'MAT_13B.PNG'), (b'MAT_00A.PNG', b'MAT_99.PNG\0')):
        if model.count(old) != 1:
            raise SystemExit(f'MAT97.SOB: expected one {old.decode()}: wrong image, or built twice')
        model = model.replace(old, new)
    a.write('MAT97.SOB', model)
    a.write('MAT_99.GST', a.read('MAT_99_1225.GST'))
    files.put('FPFILES.OAH', a.bytes())


def hi(a):
    return ((a + 0x8000) >> 16) & 0xFFFF


def lo(a):
    return a & 0xFFFF


def patches(elf, menu_names, to_offset):
    """`menu_names`: names() or, without the translation, None (plain ASCII, no tokens)."""
    menu_names = menu_names or [n.strip('<>').encode('ascii') for _, _, n, _ in RINGS]
    blob, addr = bytearray(), {}

    def put(key, data, align=16):
        blob.extend(b'\0' * (-len(blob) % align))
        addr[key] = AREA + len(blob)
        blob.extend(data)

    def word(table, i):
        return struct.unpack_from('<I', elf, to_offset(FILE, table + i * 4))[0]

    for n, (mat, post, _, _) in enumerate(RINGS):      # file names: 16-byte aligned, as the game's
        put(('mat', n), mat.encode() + b'\0')
        put(('post', n), post.encode() + b'\0')
        put(('name', n), menu_names[n] + b'\0')
    for key, table, tail in (('MAT', MAT, 'mat'), ('POST', POST, 'post'), ('NAME', NAME, 'name')):
        put(key, b''.join(struct.pack('<I', word(table, i)) for i in range(OLD)) +
            b''.join(struct.pack('<I', addr[(tail, n)]) for n in range(len(RINGS))), 4)
    put('LAYOUT', b''.join(struct.pack('<I', word(LAYOUT, i)) for i in range(OLD)) +
        b''.join(struct.pack('<I', layout) for _, _, _, layout in RINGS), 4)
    order = elf[to_offset(FILE, ORDER):to_offset(FILE, ORDER) + OLD]
    put('ORDER', bytes(order) + bytes(range(OLD, COUNT)), 4)
    if AREA + len(blob) > AREA_END:
        raise SystemExit(f'rings: the tables need {len(blob):#x} bytes, {AREA_END - AREA:#x} are free')

    edit = OLD + 6 - COUNT              # edit ring id + this = its promotion (29 + n), id 30 + n
    sites = [
        (0x114F4C, 0x3C02003A, hi(addr['ORDER'])), (0x114F60, 0x24468080, lo(addr['ORDER'])),  # the order list
        (0x114FC4, 0x2A020017, COUNT), (0x114FE0, 0x26230017, COUNT),                  # list length, first edit ring
        (0x115028, 0x2C820017, COUNT), (0x11503C, 0x3C020021, hi(addr['NAME'])),       # the name of a menu entry
        (0x115044, 0x8C425560, lo(addr['NAME'])), (0x11505C, 0x2610FFE9, -COUNT & 0xFFFF),
        (0x1150E0, 0x28A20017, COUNT),                                                 # id -> menu entry
    ]
    for start, test in ((0x134A34, (0x1349C0, 0x1349F0)), (0x1378A4, (0x137834, 0x137860))):   # the two ring loaders
        reg = 0x2A920017 if start == 0x134A34 else 0x2A740017
        sites += [(a, reg, COUNT) for a in test]
        sites += [
            (start, 0x3C04002E, hi(addr['MAT'])), (start + 8, 0x8C842F18, lo(addr['MAT'])),
            (start + 0x14, 0x3C04002E, hi(addr['POST'])), (start + 0x1C, 0x8C842EB8, lo(addr['POST'])),
            (start + 0x28, 0x3C020038, hi(addr['LAYOUT'])), (start + 0x30, 0x8C42EB38, lo(addr['LAYOUT'])),
        ]
    sites += [(a, 0x2C620017, COUNT) for a in (0x1356D0, 0x137F38)]                    # edit ring colours
    sites += [(a, 0x24840006, edit & 0xFFFF) for a in (0x1356E8, 0x137F4C)]
    sites += [(0x134CA4, 0x26840006, edit & 0xFFFF), (0x137AAC, 0x26640006, edit & 0xFFFF)]     # edit ring logo
    out = [('rings', FILE, a, old, (old & 0xFFFF0000) | new, None) for a, old, new in sites]
    out.append(('rings', FILE, 0x114FB4, 0x03B01021, 0x00D01021, None))                # addu v0,sp,s0 -> a2,s0
    out.append(('rings', FILE, AREA, bytes(elf[to_offset(FILE, AREA):to_offset(FILE, AREA) + len(blob)]), bytes(blob),
                f'{len(RINGS)} unused rings in the menu'))
    return out
