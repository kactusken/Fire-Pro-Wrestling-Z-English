#!/usr/bin/env python3
"""The wrestlers of the Liger scenario (tools/ligerstory.py, docs/TECHNICAL.md "The Liger scenario").

Wild Pegasus isn't on Z's roster, but the story names him and shows his portrait. STORY07.STO's
wrestler records are a leftover copy of scenario 6's and nothing uses them, so they are replaced in
place (file size unchanged): RECORDS. apply(n, data, files, encode) is called by fpztext.step_story
for every story file.

A story record (0x37E bytes) is a roster record up to +0x1D4, a colour block at +0x1D6 (0x164 bytes,
the costume PALET.TAC builds: costume()), scratch at +0x33A and one outfit at +0x364 (26 bytes: face,
parts; the roster holds four from +0x1D4). Pegasus is built from:
- base and CPU logic: Dynamite Kid (roster 38), the wrestler Pegasus modelled himself on;
- profile and skills: Fire Pro Wrestling S's record (height 175, weight 100, Canada, born
  1967-05-21; style 5 and reversal 7 are 6 and 8 in Z, attack ratings sit one byte earlier);
- ratings: S's, raised to his story peers;
- moves: S's list by Japanese name, with the same move's id for each slot type in Z (MOVES);
- looks: Bret Hart (roster 160): long dark hair, as in the story's portrait; no top, dark blonde hair, his
  green and pink turned to the blue of the portrait's singlet.
"""
import struct

import fpz
import paths

RECORD = 0x37E
PEGASUS_SLOT = 0        # STORY07 record replaced
KID, BRET = 38, 160
YAMADA_FACE = 112      # chosen by the owner, 2026-10-30

# Bytes from S's Wild Pegasus, in Z's layout
STATS = bytes.fromhex('af6403430515')                                 # +0x3E height .. +0x43 day
SKILLS = bytes.fromhex('06080201010001010101010106060200')        # +0x45 style, +0x46 reversal, .. +0x54 critical
# S's ratings (attack 72, defence 79) raised to his story peers: Kobayashi 77 / 83, Hase 77 / 87
ATTACK = bytes((7, 6, 8, 7, 8, 8, 10, 7, 9, 7))                        # +0x5D Punch .. Rough
DEFENCE = bytes((9, 8, 9, 8, 9, 11, 7, 6, 9, 8))                       # +0x68 Strike .. vs. Rough

# +0x74 onwards: move id | 0x1000 signature | 0x2000 finisher | 0x4000 / 0x8000 shouts. Slots not
# listed (Z's ground and apron slots, which S doesn't have) keep Dynamite Kid's.
MOVES = {
    0x74: 1, 0x76: 10, 0x78: 64, 0x7A: 60, 0x7C: 107, 0x7E: 97, 0x80: 235, 0x82: 210, 0x84: 275,
    0x86: 303, 0x88: 319, 0x8A: 328, 0x8C: 344 | 0x1000, 0x8E: 346, 0x90: 373, 0x92: 341,
    0x94: 401, 0x96: 430, 0x98: 436, 0x9A: 406, 0x9C: 456, 0x9E: 493 | 0x1000, 0xA0: 505,
    0xA2: 513, 0xA4: 542, 0xA6: 676, 0xA8: 686, 0xAA: 707 | 0x9000, 0xAC: 705 | 0x8000,
    0xAE: 750, 0xB0: 775 | 0x4000, 0xB2: 811, 0xB4: 837 | 0x4000, 0xB6: 835, 0xB8: 857 | 0x5000,
    0xBA: 875, 0xBC: 894, 0xBE: 953, 0xC0: 984, 0xC2: 1040, 0xC4: 1088, 0xC6: 920, 0xC8: 976,
    0xCA: 1032, 0xCC: 1033, 0xD0: 1145, 0xD2: 1166 | 0xA000, 0xD4: 1161 | 0x4000, 0xD6: 1372,
    0xD8: 1381, 0xDA: 1492, 0xDC: 1522, 0xDE: 1502, 0xE0: 1526, 0xE2: 1513,
}


def rgb(r, g, b):
    return 0x8000 | r >> 3 | (g >> 3) << 5 | (b >> 3) << 10


PINK = [rgb(96, 16, 64), rgb(136, 40, 104), rgb(176, 64, 144), rgb(216, 80, 176)]    # Bret's trim
GREEN = [rgb(8, 24, 8), rgb(24, 40, 24), rgb(48, 64, 48), rgb(80, 96, 80)]           # and his top
YAMADA_BLACK = (2, 8, 9, 27, 31, 32, 37, 41, 42)     # colour ramps: hair, then the boots' white parts
ROOKIE_RED = [0x8C6B, 0x8C70, 0x9095, 0x98DA]
BLACK = [rgb(8, 8, 8), rgb(20, 20, 20), rgb(36, 36, 36), rgb(60, 60, 60)]
HAIR = 12 + 2 * 8                      # the third ramp of the colour block
BLONDE = [rgb(64, 40, 24), rgb(104, 72, 40), rgb(144, 108, 60), rgb(184, 148, 92)]
BLUE = [rgb(16, 24, 72), rgb(24, 40, 112), rgb(40, 64, 160), rgb(64, 96, 200)]


def costume(palet, wrestler, colour=0):
    """A roster wrestler's colour block, as 0x116718 builds it from PALET.TAC's three sections."""
    _, s0, _, s1, _, s2 = struct.unpack_from('<6I', palet, 0)
    ids = struct.unpack_from('<44H', palet, s0 + 88 * (4 * wrestler + colour))
    out = bytearray(palet[s1 + ids[0] * 12:s1 + ids[0] * 12 + 12])
    for i in ids[1:]:
        out += palet[s2 + i * 8:s2 + i * 8 + 8]
    return bytes(out)


def pegasus(roster, palet, template, encode):
    """The record. `template` is any story record (for its scratch bytes); encode is fpztext.encode."""
    kid = roster[KID * fpz.ROSTER_RECORD:(KID + 1) * fpz.ROSTER_RECORD]
    bret = roster[BRET * fpz.ROSTER_RECORD:(BRET + 1) * fpz.ROSTER_RECORD]
    r = bytearray(template)
    r[:0x1D4] = kid[:0x1D4]
    r[0] = 2                    # class: junior
    r[1] = (r[1] & ~0x83) | 0x83    # name2 first, no separator (as the build's roster)
    for off, room, text in ((2, 14, 'Pegasus'), (0x10, 20, 'Wild '), (0x24, 26, 'Pegasus in the Sky')):
        r[off:off + room] = encode(text, room - 1, center=off == 2).ljust(room, b'\0')
    r[0x3E:0x3E + len(STATS)] = STATS
    r[0x44] = 0                 # New Japan
    r[0x45:0x45 + len(SKILLS)] = SKILLS
    r[0x5D:0x5D + len(ATTACK)] = ATTACK
    r[0x68:0x68 + len(DEFENCE)] = DEFENCE
    for off, word in MOVES.items():
        struct.pack_into('<H', r, off, word)
    colours = bytearray(costume(palet, BRET))
    for ramp in (PINK, GREEN):         # the singlet of the story's portrait
        for a, b in zip(ramp, BLUE):
            colours = colours.replace(struct.pack('<H', a), struct.pack('<H', b))
    colours[HAIR:HAIR + 8] = struct.pack('<4H', *BLONDE)
    r[0x1D6:0x33A] = colours
    r[0x364:0x37E] = bret[0x1D4:0x1D4 + 26]
    r[0x367] = r[0x36B] = 0xFF  # no top: bare-chested, like Misawa's outfit
    return bytes(r)


def scale(values, total):
    """Ratings changed to add up to `total`, keeping their shape (largest remainders round up)."""
    exact = [v * total / sum(values) for v in values]
    out = [int(v) for v in exact]
    for i in sorted(range(len(out)), key=lambda k: out[k] - exact[k])[:total - sum(out)]:
        out[i] += 1
    return bytes(out)


def person(roster, palet, template, wrestler, attack, defence, colour=0):
    """A roster wrestler at another point in his career: his record with other ratings."""
    w = roster[wrestler * fpz.ROSTER_RECORD:(wrestler + 1) * fpz.ROSTER_RECORD]
    r = bytearray(template)
    r[:0x1D4] = w[:0x1D4]
    r[0x5D:0x67] = scale(w[0x5D:0x67], attack)
    r[0x68:0x72] = scale(w[0x68:0x72], defence)
    r[0x1D6:0x33A] = costume(palet, wrestler, colour)
    r[0x364:0x37E] = w[0x1D4 + colour * 26:0x1D4 + (colour + 1) * 26]
    return bytes(r)


def yamada(rookie, roster, encode):
    """Keiichi Yamada before the mask: a record of scenario 1's rookie Misawa (his moves and ratings) with
    Liger's profile and a rookie's weight."""
    liger = roster[15 * fpz.ROSTER_RECORD:16 * fpz.ROSTER_RECORD]
    r = bytearray(rookie)
    r[0] = 2
    r[1] = (r[1] & ~0x83) | 0x83
    for off, room, text in ((2, 14, 'Yamada'), (0x10, 20, 'Keiichi '), (0x24, 26, 'Young Lion')):
        r[off:off + room] = encode(text, room - 1, center=off == 2).ljust(room, b'\0')
    r[0x3E:0x44] = bytes((170, 78, liger[0x40], 64, 11, 30))     # born 1964-11-30
    r[0x45:0x47] = liger[0x45:0x47]
    struct.pack_into('<H', r, 0x364, YAMADA_FACE)
    for a, b in zip(ROOKIE_RED, BLACK):     # a young lion's plain black trunks and boots
        r[0x1D6:0x33A] = bytes(r[0x1D6:0x33A]).replace(struct.pack('<H', a), struct.pack('<H', b))
    black = struct.pack('<4H', *BLACK)
    for ramp in YAMADA_BLACK:
        at = 0x1D6 + 12 + ramp * 8
        r[at:at + 8] = black
    return bytes(r)


def yamada_red(rookie, roster, palet, encode):
    """Yamada after his first year: red pants, white boots, no top. The long pants are Bret Hart's
    outfit, as Pegasus's; the face, skin and hair stay."""
    r = bytearray(yamada(rookie, roster, encode))
    bret = roster[BRET * fpz.ROSTER_RECORD:(BRET + 1) * fpz.ROSTER_RECORD]
    colours = bytearray(costume(palet, BRET))
    for ramp in (PINK, GREEN):
        for a, b in zip(ramp, ROOKIE_RED):
            colours = colours.replace(struct.pack('<H', a), struct.pack('<H', b))
    colours[:12] = r[0x1D6:0x1D6 + 12]                      # skin
    colours[12 + 8:12 + 16] = r[0x1D6 + 12 + 8:0x1D6 + 12 + 16]     # face
    colours[HAIR:HAIR + 8] = struct.pack('<4H', *BLACK)
    r[0x1D6:0x33A] = colours
    r[0x364:0x37E] = bret[0x1D4:0x1D4 + 26]
    struct.pack_into('<H', r, 0x364, YAMADA_FACE)
    r[0x367] = r[0x36B] = 0xFF                  # no top
    r[0x36F] = r[0x372] = 0xFF                  # no armbands
    return bytes(r)


# STORY07's records, on the curve the other stories use: rookies far below their roster ratings
# (Misawa 99, 130, then 167, then 175), early opponents lowered to match (his first is 50 under),
# then the roster. (name: attack, defence) for a roster wrestler at that time:
PEOPLE = {
    'liger': (15, 78, 77, 3),       # 155 until he is champion (Misawa: 8 under the roster)
    'champion': (15, 82, 81, 3),    # the roster's ratings; both: costume 3, red like his portraits
    'fujiwara': (131, 55, 60),      # as Misawa's first opponent, Koshinaka (EARLY)
    'sano': (82, 61, 64),           # as Misawa's second, Kobayashi
    'mutoh': (42, 71, 80),          # replaced by scenario 3's young Mutoh in apply()
    'rocco': (40, 72, 78),          # the veteran Black Tiger; 168 would overwhelm a 130 rookie
    # low on the roster for a singles main event here (129-137): lifted to the story's lowest
    'satake': (179, 72, 78),
    'suzuki': (240, 78, 72),
    'marufuji': (86, 75, 80),
    'crocop': (201, 86, 69),
}
# Misawa's first opponents in scenario 1 are cut down in more than ratings: a rookie-era move list and
# CPU logic, no critical type. These two take those from the record of that match.
EARLY = {'fujiwara': 4, 'sano': 5}
RECORDS = ['pegasus', 'yamada1', 'yamada2', *PEOPLE]


def slots():
    return {name: i for i, name in enumerate(RECORDS)}


def apply(n, data, files, encode):
    """Story file n's bytes with its made-up wrestlers in place."""
    if n != 7:
        return data
    _, _, _, _, _, at, count, _ = struct.unpack_from('<8I', data, 0)
    if len(RECORDS) > count:
        raise SystemExit(f'STORY07: {count} wrestler records, {len(RECORDS)} needed')
    roster = bytes(files.get('STRHUMAN.BIN'))       # with the English names
    palet = (paths.EXTRACTED / 'PALET.TAC').read_bytes()
    misawa = fpz.Oah((paths.EXTRACTED / 'STORY.OAH').read_bytes()).read('SCENA\\STORY01.STO')
    first = struct.unpack_from('<8I', misawa, 0)[5]
    out = bytearray(data)
    for i, name in enumerate(RECORDS):
        off = at + i * RECORD
        old = data[off:off + RECORD]
        if name == 'pegasus':
            new = pegasus(roster, palet, old, encode)
        elif name.startswith('yamada'):
            k = int(name[-1]) - 1
            rookie = misawa[first + k * RECORD:first + (k + 1) * RECORD]
            new = yamada(rookie, roster, encode) if k == 0 else yamada_red(rookie, roster, palet, encode)
        else:
            new = bytearray(person(roster, palet, old, *PEOPLE[name]))
            if name == 'mutoh':        # the young Mutoh of scenario 3 (record 3): looks, moves, logic
                other = fpz.Oah((paths.EXTRACTED / 'STORY.OAH').read_bytes()).read('SCENA\\STORY03.STO')
                at3 = struct.unpack_from('<8I', other, 0)[5] + 3 * RECORD
                new[0x3E:] = other[at3 + 0x3E:at3 + RECORD]
            if name in EARLY:
                early = misawa[first + EARLY[name] * RECORD:first + (EARLY[name] + 1) * RECORD]
                new[0x74:0x1D4] = early[0x74:0x1D4]
                new[0x54] = 0
        out[off:off + RECORD] = new
    return bytes(out)
