#!/usr/bin/env python3
"""The Liger scenario made playable (docs/TECHNICAL.md "The Liger scenario").

STORY07.STO was left unfinished: its match scenes (lyger_gmNNN) show "Match (VS name)" and a Win /
Lose menu, and its match table and wrestler records are a copy of scenario 6's. restore(data) gives
the file back with a match table of its own and every match scene rebuilt on the pattern of the
other scenarios (card, game(n), result screen, win points, on to the Win or Lose scene). It works on
the original bytes, before the translation: new strings go at the end of the table, so every text
id stays. paged() splits the one message the original left as a single page. The wrestlers
themselves are in tools/storywrestlers.py.

  ligerstory.py dump     print the rebuilt file's matches
"""
import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fpz  # noqa: E402

ENC = 'cp932'
# Script function numbers (the same 38 helpers in every file) and instruction shapes
FD_IN, FD_OUT, BACK_SET, BACK_BRI, GAME, GM_SETP = 20, 21, 15, 27, 31, 32
BACKGROUND = 27 << 16           # the arena, as in scenario 1's match scenes
WIN_POINTS = 1
MAEDA = 120                     # message of the scene after losing Maeda's retirement match

# Who wrestles: a roster id (int), or a record of this file (storywrestlers.RECORDS), as a string
NAME = {'yamada1': '%sa7', 'yamada2': '%sa7', 'pegasus': '%sa6'}     # story names 7:6, 7:7

# Match settings, record +0x1C (16 bytes; the time limit is +0x21), from matches of the same kind
DOJO = '00012600030f000a1605064000021200'       # scenario 6, the U-Inter dojo
DOJO_NORMAL = '0001a200000f000a1605064000021200'       # the same ring, normal rules
NJ = '0001a200003c00000005003c00021200'         # scenario 3, IWGP title match
UWF = '00012640033c00001606031f00021200'        # scenario 6, U-Inter's Kama match
MMA = '00010440033c00011208032300031200'        # scenario 6, PRIDE
NOAH = '0001a200003c00010207072500031200'        # scenario 1, NOAH title match

# scene, hero, opponent, opponent's roster id (for the result screen), name on the cards, settings,
# minutes. Opponents named by a string are lowered or raised for the story (RECORDS).
MATCHES = [
    ('lyger_gm001', 'yamada1', 'fujiwara', 131, '%ss131', DOJO_NORMAL, 15),
    ('lyger_gm002', 'yamada1', 'sano', 82, '%ss82', NJ, 15),
    ('lyger_gm004', 'yamada2', 'mutoh', 42, '%ss42', NJ, 15),
    ('lyger_gm005', 'yamada2', 'rocco', 40, '%ss40', NJ, 60),
    ('lyger_gm006', 'liger', 39, 39, '%ss39', NJ, 60),
    ('lyger_gm206', 'yamada2', 184, 184, '%ss184', DOJO, 15),
    ('lyger_gm007', 'liger', 45, 45, '%ss45', NJ, 60),
    ('lyger_gm207', 'liger', 131, 131, '%ss131', UWF, 60),
    ('lyger_gm008', 'liger', 'pegasus', 0x80000006, '%sa6', NJ, 60),
    ('lyger_gm209', 'liger', 'satake', 179, '%ss179', UWF, 60),
    ('lyger_gm309', 'liger', 99, 99, '%ss99', UWF, 60),
    ('lyger_gm409', 'liger', 'suzuki', 240, '%ss240', UWF, 60),
    ('lyger_gm009', 'champion', 89, 89, '%ss89', NJ, 60),
    ('lyger_gm210', 'liger', 204, 204, '%ss204', UWF, 60),
    ('lyger_gm310', 'liger', 88, 88, '%ss88', NJ, 60),
    ('lyger_gm410', 'liger', 178, 178, '%ss178', UWF, 60),
    ('lyger_gm010', 'champion', 82, 82, '%ss82', NJ, 60),
    ('lyger_gm211', 'liger', 184, 184, '%ss184', UWF, 60),
    ('lyger_gm011', 'champion', 43, 43, '%ss43', NJ, 60),
    ('lyger_gm012', 'champion', 94, 94, '%ss94', NJ, 60),
    ('lyger_gm013', 'champion', 98, 98, '%ss98', NJ, 60),
    ('lyger_gm113', 'champion', 21, 21, '%ss21', NJ, 60),
    ('lyger_gm014', 'champion', 'marufuji', 86, '%ss86', NOAH, 60),
    ('lyger_gm015', 'champion', 66, 66, '%ss66', NOAH, 60),
    ('lyger_gm213', 'champion', 'crocop', 201, '%ss201', MMA, 60),
    ('lyger_gm214', 'champion', 185, 185, '%ss185', MMA, 60),
]
# Where each match happens, from its scene: venue (+0x23), ring (+0x24), referee (+0x26).
BUDOKAN, DOME, HALL, OVERSEAS, DOJO_FLOOR = 0, 1, 2, 4, 10      # the closest of the game's venues
VJP, NOAH_RING, HIGH_CLASS, BLADE, GREY = 0, 2, 14, 18, 22      # BLADE = PRIDE, High Class = Pancrase
UWH = 28                        # the unused ring set (build.py group rings, docs/HIDDEN_CONTENT.md)
PLACE = {
    'lyger_gm001': (DOJO_FLOOR, GREY, 6), 'lyger_gm002': (HALL, VJP, 0),          # dojo; the undercard
    'lyger_gm004': (BUDOKAN, VJP, 0), 'lyger_gm005': (OVERSEAS, GREY, 4),         # final; Liverpool
    'lyger_gm006': (DOME, VJP, 0), 'lyger_gm007': (BUDOKAN, VJP, 0),              # the Dome debut
    'lyger_gm008': (BUDOKAN, VJP, 0), 'lyger_gm009': (BUDOKAN, VJP, 0),
    'lyger_gm010': (DOME, VJP, 0), 'lyger_gm011': (BUDOKAN, VJP, 0),              # New Japan vs. U-Inter
    'lyger_gm012': (BUDOKAN, VJP, 0), 'lyger_gm013': (DOME, VJP, 0),              # Inoki's last match
    'lyger_gm113': (BUDOKAN, VJP, 0), 'lyger_gm014': (BUDOKAN, NOAH_RING, 7),     # G1; NOAH's mat
    'lyger_gm015': (DOME, GREY, 6),                                               # a neutral ring
    'lyger_gm206': (DOJO_FLOOR, GREY, 6), 'lyger_gm207': (HALL, UWH, 6),          # the UWF
    'lyger_gm209': (HALL, GREY, 6), 'lyger_gm210': (BUDOKAN, GREY, 6),            # RINGS: no ring of its own
    'lyger_gm211': (BUDOKAN, GREY, 6),
    'lyger_gm309': (BUDOKAN, UWH, 6), 'lyger_gm310': (DOME, VJP, 0),              # U-Inter; the war
    'lyger_gm409': (HALL, HIGH_CLASS, 6), 'lyger_gm410': (DOME, HIGH_CLASS, 6),   # Pancrase
    'lyger_gm213': (DOME, BLADE, 3), 'lyger_gm214': (DOME, BLADE, 3),             # mixed martial arts
}
# COM level (+0x25) and critical % (+0x29) by place in the story, on the curve of the other scenarios
# (every one opens at level 2, critical off, and ends at 7-8, critical 3)
DIFFICULTY = {
    'lyger_gm001': (2, 0), 'lyger_gm002': (2, 1), 'lyger_gm004': (3, 2), 'lyger_gm005': (3, 2),
    'lyger_gm206': (3, 2), 'lyger_gm006': (3, 2), 'lyger_gm007': (3, 2), 'lyger_gm207': (3, 2),
    'lyger_gm008': (4, 2), 'lyger_gm209': (4, 2), 'lyger_gm309': (4, 2), 'lyger_gm409': (4, 2),
    'lyger_gm009': (4, 2), 'lyger_gm210': (5, 2), 'lyger_gm310': (5, 2), 'lyger_gm410': (5, 2),
    'lyger_gm010': (5, 2), 'lyger_gm211': (6, 3), 'lyger_gm011': (6, 3), 'lyger_gm012': (6, 3),
    'lyger_gm014': (6, 3), 'lyger_gm013': (7, 3), 'lyger_gm113': (7, 3), 'lyger_gm213': (7, 3),
    'lyger_gm015': (8, 3), 'lyger_gm214': (8, 3),
}


def wide(n):
    return str(n).translate(str.maketrans('0123456789', '０１２３４５６７８９'))


def card(hero, opponent, minutes):
    return (f'%m2%w600\r\n%px320%py100{wide(minutes)}分　１本勝負\r\n'
            '%px320%py224%bx0x16000%by0x18000ＶＳ\r\n'
            f'%px150%py224%bx0x1c000%by0x1c000{hero}\r\n'
            f'%px490%py224%bx0x1c000%by0x1c000{opponent}\r\n%k2\r\n%m0%w5\r\n').encode(ENC)


def result(hero, opponent):
    return ('%m2%w600\r\n%px320%py100%bx0x1c000%by0x1c000試合結果\r\n'
            '%px320%py200%st\r\n%px320%py236%sk\r\n'
            f'%px200%py274{hero}　%sw0\r\n%px440%py274%sw4　{opponent}\r\n%k2\r\n%m0%w5\r\n').encode(ENC)


def push(v):
    return (2, 1, v)


def call(fn):
    return [(16, fn, 0), (3, 0, 0)]


def window():
    return [push(4), push(32), push(32), push(21), push(13), push(2), (23, 6, 0)]


def screen(sid):
    """A full-screen card over the arena, as misawa_gm01 shows them."""
    return [push(BACKGROUND), *call(BACK_SET), push(50), *call(BACK_BRI), push(50), *call(FD_IN), *window(),
            (2, 2, sid), (20, 1, 0), push(50), *call(FD_OUT)]


def scene(n, card_id, result_id, win, lose):
    """The match scene: its instructions (op, operand, value)."""
    code = [push(50), *call(FD_OUT), *screen(card_id),
            (1, 0, 1), push(n), (16, GAME, 0), (4, 0, 0), (3, 0, 0),      # L0 = game(n)
            *screen(result_id), push(0), *call(BACK_BRI),
            (0, 0, 1), push(2), (11, 46, 0)]                              # L0 < 2: won
    tail = [push(WIN_POINTS), *call(GM_SETP), (2, 2, win), (28, 1, 0)]
    lose_at = len(code) + 1 + len(tail) + 1
    end_at = lose_at + 2
    return code + [(14, lose_at, 0)] + tail + [(13, end_at, 0), (2, 2, lose), (28, 1, 0), push(0), (12, 0, 0)]


# Losing to Pegasus: the script has one scene after the match, and it says Liger won; the next chapter
# has him champion. So a loss means Game Over and a retry, as at the final matches: copies of
# Misawa's three scenes, with the script's own text, added to the file. (new label, copied from)
GAME_OVER = [('lyger0082', 'lyger0151'), ('lyger0083', 'lyger0152'), ('lyger0084', 'lyger0154')]
GAME_OVER_LABELS = {'lyger0152': 'lyger0083', 'lyger0153': 'lyger_gm008', 'lyger0154': 'lyger0084'}


def records(data):
    """[(name, record offset, code position, frame)] of the file's symbols, `main` last."""
    h = struct.unpack_from('<16I', data, 0)
    out = []
    for k in range(h[12] + 1):
        o = 0x38 + k * 0x38
        pos, frame = struct.unpack_from('<II', data, o + 4)
        out.append((data[o + 0xD:o + 0x38].split(b'\0')[0].decode('latin1'), o, pos, frame))
    return out


def old_targets(words, sto):
    """(win label id, lose label id) of an old match scene: the menu's label / caption pairs."""
    ops = [struct.unpack_from('<3I', w, 4) for w in words]
    at = next(i for i, x in enumerate(ops) if x[0] == 26)
    labels = [ops[i][2] for i in range(at - 4, at) if ops[i][:2] == (2, 2)]
    pairs = dict(zip([sto.strings[c].decode(ENC) for c in labels[1::2]], labels[0::2]))
    return pairs['勝ち'], pairs['負け']


def match_record(name, hero, opp, opp_id, settings, minutes, slots):
    r = bytearray(struct.pack('<8H', 0, 0xFFFF, 0xFFFF, 0xFFFF, 0, 0xFFFF, 0xFFFF, 0xFFFF)) + bytes(0x1C)
    for k, who in ((0, hero), (4, opp)):
        story = isinstance(who, str)
        struct.pack_into('<H', r, k * 2, slots[who] if story else who)
        r[0x10 + k] = story
    struct.pack_into('<I', r, 0x18, opp_id)
    r[0x1C:0x2C] = bytes.fromhex(settings)
    r[0x21] = minutes
    r[0x25], r[0x29] = DIFFICULTY[name]
    r[0x23], r[0x24], r[0x26] = PLACE[name]
    return bytes(r)


def paged(data):
    """STORY07 with message 120 (lyger2111, losing Maeda's retirement match) split into pages: it is
    the only message left as one page, a whole conversation with no %k. Each speaker gets a page,
    as in its winning twin, message 118. Used by the build and by fpztext dump."""
    sto = fpz.Sto(data)
    strings = list(sto.strings)
    text = strings[MAEDA].decode(ENC)
    if '%k' in text:
        return data
    text = re.sub('\\r\\n(前田：|ライガー：)', r'\r\n%k\r\n\1', text)
    text = text.replace('%c0\r\n%k\r\n', '%c0\r\n', 1)
    strings[MAEDA] = text.replace('\r\n\t', '\r\n%k\r\n\t').encode(ENC)
    return sto.build(strings)


def restore(data, slots):
    """STORY07's bytes with the matches in. slots: record name -> index."""
    data = paged(data)
    sto = fpz.Sto(data)
    h = list(sto.h)
    code_at, table, pool = h[9] + 0x20, sto.table, sto.pool
    syms = records(data)
    order = sorted(range(len(syms)), key=lambda i: syms[i][2])
    count = (table - code_at) // 16
    word_at = lambda i: data[code_at + i * 16:code_at + (i + 1) * 16]
    by_name = {s[0]: i for i, s in enumerate(syms)}
    new_strings, plan = [], {}
    base = len(sto.strings)

    def add(s):
        new_strings.append(s)
        return base + len(new_strings) - 1
    labels = {t: add(t.encode()) for t in ('lyger0082', 'lyger0083', 'lyger0084', 'lyger_gm008')}
    for n, (name, hero, opp, _, opp_name, _, minutes) in enumerate(MATCHES):
        i = by_name[name]
        k = order.index(i)
        end = syms[order[k + 1]][2] if k + 1 < len(order) else count
        win, lose = old_targets([word_at(p) for p in range(syms[i][2], end)], sto)
        who = NAME.get(hero, '%ss15')
        if name == 'lyger_gm008':
            lose = labels['lyger0082']
        plan[i] = scene(n, add(card(who, opp_name, minutes)), add(result(who, opp_name)), win, lose)
    code, new_pos = bytearray(), {}
    for k, i in enumerate(order):
        new_pos[i] = len(code) // 16
        if i in plan:
            code += b''.join(struct.pack('<4I', 0, *w) for w in plan[i])
        else:
            end = syms[order[k + 1]][2] if k + 1 < len(order) else count
            code += data[code_at + syms[i][2] * 16:code_at + end * 16]
    # main calls the chapter menu in this file alone: it starts at chapter 1 like the others
    i, end = by_name['main'], len(code) // 16
    at = new_pos[i]
    calls = [k for k in range(at, end) if struct.unpack_from('<I', code, k * 16 + 4)[0] == 16
             and struct.unpack_from('<I', code, k * 16 + 8)[0] == by_name['lyger000']]
    if len(calls) != 1:
        raise SystemExit(f'STORY07: main has {len(calls)} calls of lyger000, 1 expected')
    struct.pack_into('<I', code, calls[0] * 16 + 8, by_name['lyger001'])
    head = bytearray(data[:code_at])
    for i, (_, off, _, frame) in enumerate(syms):
        struct.pack_into('<II', head, off + 4, new_pos[i], 1 if i in plan else frame)
    # the new scenes: their code at the end, their records just before the chapter menu and main, whose
    # place the engine works out from the count; calls of those two move with them
    new_records = bytearray()
    for label, source in GAME_OVER:
        i = by_name[source]
        k = order.index(i)
        rec = bytearray(data[syms[i][1]:syms[i][1] + 0x38])
        struct.pack_into('<I', rec, 4, len(code) // 16)
        rec[0xD:0x38] = label.encode().ljust(0x2B, b'\0')
        new_records += rec
        for p in range(syms[i][2], syms[order[k + 1]][2]):
            word = bytearray(word_at(p))
            op, kind, value = struct.unpack_from('<3I', word, 4)
            if (op, kind) == (2, 2):
                to = GAME_OVER_LABELS.get(sto.strings[value].decode(ENC, 'replace'))
                if to:
                    struct.pack_into('<I', word, 12, labels[to])
            code += word
    menu = by_name['lyger000']
    for at in range(0, len(code), 16):
        if struct.unpack_from('<I', code, at + 4)[0] == 16:
            target = struct.unpack_from('<I', code, at + 8)[0]
            if target >= menu:
                struct.pack_into('<I', code, at + 8, target + len(GAME_OVER))
    head[syms[menu][1]:syms[menu][1]] = new_records
    # the string table and pool, with the new strings at the end
    offs = list(sto.offsets)
    tail = bytearray(data[pool:h[4]])
    tail += bytes(-len(tail) % 4)
    for s in new_strings:
        offs.append(len(tail))
        tail += s + b'\0'
    tail += bytes(-len(tail) % 4)
    grow_head = len(new_records)
    grow_code = len(code) - (table - code_at) + grow_head
    new_table = table + grow_code
    new_pool = new_table + len(offs) * 4
    new_match = new_pool + len(tail)
    shift = new_match - h[4]
    out = head + code + struct.pack(f'<{len(offs)}I', *offs) + tail + data[h[4]:]
    h[12] += len(GAME_OVER)
    h[13] += grow_head
    h[9] += grow_head
    h[10] += grow_code
    h[11] = new_pool - 0x20
    h[4], h[5], h[7] = new_match, h[5] + shift, h[7] + shift
    struct.pack_into('<16I', out, 0, *h)
    # the match table, in place (26 of its 38 records; the rest keep what they had, unused)
    for n, (name, hero, opp, opp_id, _, settings, minutes) in enumerate(MATCHES):
        out[new_match + 4 + n * 44:new_match + 4 + (n + 1) * 44] = match_record(
            name, hero, opp, opp_id, settings, minutes, slots)
    return bytes(out)


def main(argv=None):
    import fpztext
    import storyflow
    import storywrestlers
    data = restore(fpztext.story_archive().read('SCENA\\STORY07.STO'), storywrestlers.slots())
    s, syms, ins = storyflow.load(data)
    print(f'{len(data)} bytes, {len(s.strings)} strings')
    for name, f in storyflow.scene_functions(s, syms, ins):
        if name.startswith('lyger_gm'):
            print(name, storyflow.summary(storyflow.walk(s, syms, ins, *f))[1:2],
                  [x['to'] for x in storyflow.summary(storyflow.walk(s, syms, ins, *f))[3]])
    return 0


if __name__ == '__main__':
    sys.exit(main())
