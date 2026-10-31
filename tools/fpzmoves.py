#!/usr/bin/env python3
"""Fire Pro Wrestling Z's move data: names, the Move Edit lists and each move's numbers.

  python3 tools/fpzmoves.py            print a summary and run the sanity checks
  python3 tools/fpzmoves.py 613 1059   print those move ids

    import fpzmoves
    db = fpzmoves.load()
    db['moves']   1845 dicts by move id (fields: FIELDS below)
    db['lists']   the 43 Move Edit lists: index, title, chain, slots, own_ids, menu_ids, patch_adds
    db['slots']   the 78 Move Edit rows in screen order (fpzrecord.Tables.rows)
    db['styles'], db['types'], db['affinity']   the style x attack type grades of Move Edit's box

Standard library only. Reads extracted/ (the executable, WAZA.BIN, GODAWAZA.BIN, STRHUMAN.BIN) with
the English of translation/text/. tools/guidedata.py uses this for the guide's move tables.

A move's numbers are the GS block of its first motion in GODAWAZA.BIN (an id's variants hold the same
numbers), read in the match code (RAM addresses, file offset + 0xFF000 = RAM):
  +0x12-18 base stamina, spirit, neck, arm, back, leg, breath damage (0x12D590..); +0x19 bleed: below
  50 the % chance per hit, 50 or more is not a chance (Bronco Buster, 0x1185CC: reported as None);
  +0x1A main << 4 | sub attack type, +0x1B the same for defence (a type indexes the wrestler's
  ratings); +0x1C parts that weaken the move when hurt; +0x1D-22 the attacker's own loss; +0x23 flags:
  0x80 illegal, 0x40 submission, 0x01-0x20 critical classes; +0x30 16 section ends, +0x40 12-byte frames,
  each with its length in ticks at +6, so `ticks` (the first section, the attacker's own motion)
  compares move speed before the wrestler's speed is added.
"""
import collections
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fpzrecord  # noqa: E402
import fpztext  # noqa: E402
import movelists  # noqa: E402
import paths  # noqa: E402

OFF = fpzrecord.OFF
AFFINITY = 0x310A28                 # 16 styles x 11 attack types: 0 A .. 4 E
STYLE_NAMES = 0x30F0A8              # 16 string pointers: Skill Edit's fighting styles
TYPE_NAMES = 0x310AD8               # 11 string pointers: Move Edit box's attack types
RATING_NAMES = 0x30EE98             # 22 string pointers: Param Edit (11 attack, 11 defence)
MOVE_FIRST = 0x37EB98               # u16 by move id: first motion in GODAWAZA.BIN
N_MOVES = 1845
MOVE_MOTIONS_END = 2452             # the last id's motion + 1; later motions have no id

GS_DAMAGE = {'stamina': 0x12, 'spirit': 0x13, 'breath': 0x18, 'neck': 0x14, 'arm': 0x15, 'back': 0x16, 'leg': 0x17}
GS_SELF = {'stamina': 0x1D, 'spirit': 0x1E, 'neck': 0x1F, 'arm': 0x20, 'back': 0x21, 'leg': 0x22}
GS_BLEED, GS_ATTACK, GS_DEFENCE, GS_LOWERED, GS_FLAGS = 0x19, 0x1A, 0x1B, 0x1C, 0x23
GS_CUTS, GS_FRAMES, FRAME, F_TICKS = 0x30, 0x40, 12, 6
BLEED_LIMIT = 50                    # +0x19 from here up isn't a chance (0x12D930)
FLAG_CRIT = {0x01: 'Finisher', 0x02: 'Striking', 0x04: 'Suplex', 0x08: 'Submission', 0x10: 'Power',
             0x20: 'Technical'}
LOWERED = {8: 'neck', 4: 'arm', 2: 'back', 1: 'leg'}

# Ids whose Japanese name isn't in Fire Pro Wrestling D's move list (compared by name, NFKC, spaces
# and dots removed, against D's 1600 ids; kept here so this tool doesn't need the D project).
NEW_IN_Z = [(76, 76), (103, 103), (120, 120), (256, 256), (283, 283), (285, 285), (354, 354), (613, 613),
            (617, 617), (624, 624), (657, 657), (660, 660), (668, 668), (694, 694), (713, 713), (718, 718),
            (740, 740), (965, 965), (1008, 1008), (1038, 1038), (1059, 1059), (1180, 1185), (1366, 1369),
            (1378, 1378), (1380, 1380), (1400, 1400), (1457, 1457), (1465, 1465), (1547, 1547), (1549, 1549),
            (1556, 1557), (1559, 1560), (1566, 1566), (1568, 1568), (1579, 1580), (1585, 1587), (1591, 1591),
            (1594, 1594), (1597, 1599), (1602, 1606), (1612, 1615), (1621, 1627), (1633, 1664), (1678, 1681),
            (1688, 1689), (1691, 1698), (1706, 1706), (1710, 1717), (1723, 1724), (1730, 1733), (1740, 1740),
            (1748, 1749), (1751, 1756), (1760, 1761), (1766, 1767), (1771, 1772), (1780, 1780), (1800, 1800),
            (1803, 1803), (1806, 1822), (1828, 1830), (1832, 1833)]

FIELDS = {
    'id': 'move id (WAZA.BIN index); what a wrestler record stores',
    'jp': 'Japanese name in WAZA.BIN',
    'en, en_parody': "the patch's English in each name set",
    'status': 'none (id 0) | standard | unlisted-patch (only with --unlocks moves) | reserved | blank',
    'lists': 'Move Edit lists that hold the id; an unlisted move has the one the patch adds it to',
    'damage, self_damage': 'base numbers by meter; the second is what the attacker loses',
    'attack, defence': '(main, sub) type indexes; lowered_by: hurt parts that weaken the move',
    'bleed': '% chance per hit; None when the byte is not a chance',
    'illegal, submission, critical': 'flags: critical is a list of FLAG_CRIT names',
    'ticks': "length of the attacker's own motion",
    'users': 'roster wrestlers (of 244) with the id in a slot',
    'new_in_z': 'no move of this name in Fire Pro Wrestling D',
}


def _block(g, k):
    off, size = struct.unpack_from('<II', g, k * 8)
    return g[off:off + size] if size else b''


def decode_block(b):
    """The numbers of one GS block as plain values."""
    fl = b[GS_FLAGS]
    cuts = list(b[GS_CUTS:GS_CUTS + 16])
    assert len(b) == GS_FRAMES + cuts[-1] * FRAME, 'block size is not header + frames'
    ticks = sum(b[GS_FRAMES + k * FRAME + F_TICKS] for k in range(cuts[0]))
    return {'damage': {k: b[o] for k, o in GS_DAMAGE.items()},
            'self_damage': {k: b[o] for k, o in GS_SELF.items()},
            'attack': (b[GS_ATTACK] >> 4, b[GS_ATTACK] & 15), 'defence': (b[GS_DEFENCE] >> 4, b[GS_DEFENCE] & 15),
            'lowered_by': [n for bit, n in LOWERED.items() if b[GS_LOWERED] & bit],
            'bleed': b[GS_BLEED] if b[GS_BLEED] < BLEED_LIMIT else None,
            'illegal': bool(fl & 0x80), 'submission': bool(fl & 0x40),
            'critical': [n for bit, n in FLAG_CRIT.items() if fl & bit], 'ticks': ticks}


def read_lists(exe):
    """The 43 lists as stored: [{index, count, chain, ids}], before the game merges the chains."""
    out = []
    for k in range(fpzrecord.LIST_N):
        ptr, count, chain = struct.unpack_from('<IHh', exe, fpzrecord.MOVE_LISTS + 8 * k - OFF)
        out.append({'index': k, 'count': count, 'chain': chain,
                    'ids': list(struct.unpack_from(f'<{count}H', exe, ptr - OFF))})
    return out


def merged(lists):
    """Each list's menu as the game builds it (0x14E50C): for k ascending, list k gets list
    chain[k]'s current contents appended, so a chain runs all the way down."""
    menus = [list(x['ids']) for x in lists]
    for x in lists:
        if x['chain'] >= 0:
            menus[x['index']] += menus[x['chain']]
    return menus


def _used(roster):
    used = collections.Counter()
    for i in range(fpzrecord.N):
        rec = roster[i * fpzrecord.REC:(i + 1) * fpzrecord.REC]
        used.update({v & 0xFFF for v in struct.unpack_from(f'<{fpzrecord.SLOT_N}H', rec, fpzrecord.SLOTS)})
    return used


def load(z=None):
    """The whole database; z: a fpzrecord.Tables to share."""
    z = z or fpzrecord.Tables()
    exe = z.elf
    g = (paths.EXTRACTED / 'GODAWAZA.BIN').read_bytes()
    w = (paths.EXTRACTED / 'WAZA.BIN').read_bytes()
    added = {m: k for k, v in movelists.ADD.items() for m, _ in v}
    first = struct.unpack_from(f'<{N_MOVES}H', exe, MOVE_FIRST - OFF)
    w_off = struct.unpack_from(f'<{N_MOVES}H', w, 0)
    lists = read_lists(exe)
    menus = merged(lists)
    used = _used(z.roster)
    in_list = collections.defaultdict(list)
    for x in lists:
        for i in x['ids']:
            if x['index'] not in in_list[i]:
                in_list[i].append(x['index'])
    new = {i for a, b in NEW_IN_Z for i in range(a, b + 1)}
    moves = []
    for i in range(N_MOVES):
        o = w_off[i]
        jp = w[o:w.find(b'\0', o)].decode('cp932')
        a, b = first[i], first[i + 1] if i + 1 < N_MOVES else MOVE_MOTIONS_END
        block = next((bl for bl in (_block(g, k) for k in range(a, max(a, b))) if bl), None)
        status = ('none' if i == 0 else 'unlisted-patch' if i in added else 'standard' if i in in_list
                  else 'reserved' if '予約' in jp else 'blank')
        m = {'id': i, 'jp': jp, 'en': z.move_name(i, 'real') or '', 'en_parody': z.move_name(i, 'parody') or '',
             'status': status, 'lists': sorted(in_list.get(i, [])) or ([added[i]] if i in added else []),
             'users': used.get(i, 0), 'new_in_z': i in new}
        if block:
            m.update(decode_block(block))
        moves.append(m)
    out_lists = [{'index': k, 'title': fpzrecord.LIST_TITLES[k], 'chain': x['chain'] if x['chain'] >= 0 else None,
                  'own_ids': x['ids'], 'menu_ids': menus[k], 'patch_adds': [m for m, l in added.items() if l == k]}
                 for k, x in enumerate(lists)]
    t = exe[AFFINITY - OFF:AFFINITY - OFF + 16 * 11]
    return {'moves': moves, 'lists': out_lists, 'slots': z.rows(),
            'affinity': [['ABCDE'[t[s * 11 + j]] for j in range(11)] for s in range(16)],
            'styles': [z.label(a) for a in struct.unpack_from('<16I', exe, STYLE_NAMES - OFF)],
            'types': {'attack': [z.label(a) for a in struct.unpack_from('<11I', exe, TYPE_NAMES - OFF)],
                      'param_edit': z.param_labels()}}


def check(db):
    """The sanity checks: every listed move has a name and numbers, the counts are the known ones."""
    c = collections.Counter(m['status'] for m in db['moves'])
    bad = [m['id'] for m in db['moves'] if m['status'] in ('standard', 'unlisted-patch')
           and not (m['en'] and 'damage' in m)]
    print(dict(c), 'new in Z:', sum(m['new_in_z'] for m in db['moves']))
    if bad:
        print('no name or no numbers:', bad[:20])
    return 1 if bad or c['standard'] != 1442 or c['unlisted-patch'] != 6 else 0


def main(argv=None):
    argv = paths.configure(sys.argv[1:] if argv is None else argv)
    if '-h' in argv or '--help' in argv:
        print(__doc__)
        return 0
    db = load()
    if argv:
        for a in argv:
            if not a.isdigit() or int(a) >= N_MOVES:
                sys.exit(f'{a}: give move ids, 0-{N_MOVES - 1}')
            print(json.dumps(db['moves'][int(a)], ensure_ascii=False, indent=1))
        return 0
    return check(db)


if __name__ == '__main__':
    sys.exit(main())
