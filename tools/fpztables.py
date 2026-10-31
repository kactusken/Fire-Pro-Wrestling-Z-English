#!/usr/bin/env python3
"""Fire Pro Wrestling Z's mode and match-engine tables, read from the original executable.

  python3 tools/fpztables.py [--names real|parody] [TABLE ...]     print tables as JSON (default: their names)

    import fpzrecord, fpztables
    t = fpztables.Tables(fpzrecord.Tables(), 'real')
    t.all()    {name: table}, every table below, in one name set

For the guide's tables (tools/guidedata.py), so the page never retypes them. Standard library only.
English comes from translation/text/ through fpzrecord.Tables; addresses are RAM (file offset +
0xFF000). Modes: rings, venues, music, referees, promotions, teams, victory_road, layouts, settings_rows,
skill_costs, cpu_logic, save_files. Match engine (the code's readers are noted at each table): critical
odds, fighting styles, breath cost, size, skills, affinity.
"""
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fpzmoves  # noqa: E402
import fpzrecord  # noqa: E402
import paths  # noqa: E402
import rings as ringpatch  # noqa: E402

OFF = fpzrecord.OFF
RING_MAP, RING_N = 0x398080, 23         # 23 bytes: menu position -> ring id
RING_NAMES = 0x215560                   # string pointers in menu order
VENUE_NAMES, VENUE_N = 0x333AE8, 11
VENUE_ROW = {0: 'Yes', 1: 'Yes', 2: 'Yes', 3: 'Yes', 4: 'Yes', 9: 'Yes', 5: 'Gruesome Fighting only', 6: 'Exploding Cage DM only',
             7: 'Barbed Wire DM only (barbed wire)', 8: 'Barbed Wire DM only (tubes)', 10: 'All Unlocked patches only'}
DOJO = 'Dojo'                           # venue 10 has no name in the game (the patch names it)
MUSIC, MUSIC_N = 0x2155C0, 15
REFEREES, REFEREE_N, REFEREE_SIZE = 0x215C60, 8, 0x198
SPEED_LABELS, LENGTH_LABELS = 0x30EF80, 0x30EF68      # 5 pointers each: Skill Edit's referee choices
PROMO_N = 29
TEAM_NAMES, TEAM_MEMBERS, TEAM_N, TEAMS_OPEN = 0x215A38, 0x215AD8, 39, 29
VR_NAMES = 0x330438
VR_TABLES, VR_N = 0x3301E0, 6           # 6 pointers: each course's match tables by promotion
VR_PROMOS = (0x3301F8, 0x330220, 0x330238, 0x330250, 0x3ABD70, 0x3ABD78)     # u16 lists ending 0xFFFF
VR_ROWS = 0x330280                      # 3 bytes a row: ring, referee, rule
VR_RULES = 0x330310                     # 4 bytes a rule: match type, ?, u16 flags
VR_MUSIC = 0x330328
VR_SIDE = 0x3303B0                      # u32 by course: wrestlers on a side
MATCH_LABELS, MATCH_ROWS = 0x333A18, 33
MATCH_TYPES, TIME_LIMITS, SPEEDS, MATCHUPS, BLAST, CRITICAL = 0x333AB8, 0x333AC8, 0x333A98, 0x333B58, 0x333B70, 0x333B90
CORNER_LABELS = 0x335938
LAYOUT_ROW, LAYOUT_DEFAULT, LAYOUT_LOCK, LAYOUT_COUNT, LAYOUT_N = 0x331C58, 0x331EE8, 0x332178, 0x335518, 31
NEXT_ROW = 0x20                         # the - Next - row of a layout
TYPE_LABELS = (0x39D1A0, 0x39D1B0, 0x39D1C8, 0x39D1E0, 0x39D200)
ROYAL_LABELS = (0x3A3818, 0x3A3828, 0x3A3840)
TYPE_LAYOUT = {'One Night Match': 0x3AC5E8, 'One Night Tournament': 0x3AC5F0, 'Open League': 0x3AC5F8}   # 5 bytes each
ROYAL_LAYOUT = 0x3AC601                 # 4 bytes: Normal, Endless, Over the Rope, Staggered
ELIMINATION_LAYOUT, VICTORY_ROAD_LAYOUT = 5, 25
TITLE_FREE, TITLE_NO_LIMIT = 9, 26      # first of 5 layouts: belt record's first field not 0 / 0
COST_BUDGET = (150, 200, 250, 300)      # gp-0x6E70, by unlock level
SAVE_NAMES, SAVE_N = 0x2E3268, 12
SAVE_SIZES = (0x8744, 0x3888, 0x6E98) + (0x30B8,) * 5 + (0xAED8,) * 4        # 0x2E32A0, 0x2E32D0
SAVE_USE = ('Options, unlock data, 16 edit wrestlers, 8 edit referees, 8 edit teams, 5 story slots, '
            'Victory Road, tournament, league, belts', 'Renames of the 244 wrestlers', 'Recostumes') + \
           tuple(f'Edit promotion {i}' for i in range(1, 6)) + ('50 edit wrestlers',) * 4

# Match engine. All read in the match code (0x117000-0x136000).
CRIT_A = 0x2E02C0                       # 6 critical types x 16 attacker styles (0x12D240)
CRIT_R = 0x2E0268                       # 6 critical types x 14 victim's Reversals types
CRIT_S = 0x2E0320                       # 6 critical types x 16 sixteenths of the victim's stamina
REACH = 0x2E01A8                        # u16 by style, of 256 (0x1272C8, 0x12EF00, 0x11F684)
OWN_DAMAGE = 0x2DFF08                   # u16 by style, of 256 (0x12DA90)
BLEED_SPIRIT = 0x2DFEE8                 # s16 by style, of 65536: spirit when he starts bleeding (0x12D970)
ROPE_STOP = 0x2E0128                    # 16 styles x 4 stamina quarters, % (0x12B558)
WHIP_REVERSE = 0x2E0168                 # 16 styles x 4 stamina quarters, % (0x1293C0)
WHIP_ANIM = 0x2E2350                    # 16 bytes: 0 = another animation instead of the whip reversal
BREATH_STYLE = 0x2DFFA8                 # u16, 16 styles x 12 (11 attack types, running), of 256 (0x12E288)
BREATH_STAMINA = 0x2DFF28               # u16, 16 styles x 4 stamina quarters, of 256
SIZE_DAMAGE, SIZE_BREATH = 0x2DFE78, 0x3AA950     # u16 4 x 4, u16 x 4, of 256
SKILL_FLAGS = 0x2E2068                  # u32 x 22: the bits a skill sets (0x121354)
# What each basic skill does (read in the match code, 0x12CF00-0x12DA40, 0x121354), by Skill Edit list position
SKILL_EFFECTS = {
    'Star Power': 'Below 4% stamina, after a taunt: his next hit does 20% more damage. Any hit that lands uses it up.',
    'Quick Return': 'Gets up eight times faster when his stamina is low but his spirit is high (5-20% stamina with over 60% spirit).',
    'Comeback': 'Below 10% stamina with over 30% spirit: twice the chance to land a critical.',
    'Fast Start': 'Above 70% stamina: +1 to the attack ratings behind every move he does.',
    'Guts': 'When a submission hold empties his spirit, he gives up only 5% of the time instead of every time.',
    'Fightback': 'Below 2% stamina: +2 to the attack ratings behind every move.',
    'One-Hit KO': 'His finisher does 2.5 times its damage, the first two times he lands it in a match.',
    'Bleeding': 'While he is bleeding, his moves do 10% more damage.',
    'Hardcore': 'With a weapon: +3 to his attack ratings. Hit with one: +3 to his defence ratings.',
    'Focus': 'Half as likely to suffer a critical from a Striking, Submission or Technical opponent.',
    'Flexibility': 'A quarter as likely to suffer a critical from a Suplex or Power opponent. Finisher criticals are not reduced.',
    'Hard Body': 'Small moves do not leave him open to a pin: pinned after a hit under about 8% of his stamina, holding the kick-out gets him out at the last moment, even with no spirit left.',
}
SKILL_NOTES = {'Toukon': "Antonio Inoki's skill.", 'Monster': "Jumbo Tsuruta's skill.", 'Ishin': "Riki Choshu's skill."}
FULL_ROPES = 100


class Tables:
    """Every table in one name set; z is a fpzrecord.Tables."""

    def __init__(self, z, names='real'):
        self.z, self.names = z, names
        self.items = {i['off']: i for i in z.skill_items(names)}

    # ---------- reading

    def u8(self, a):
        return self.z.elf[a - OFF]

    def u16(self, a):
        return struct.unpack_from('<H', self.z.elf, a - OFF)[0]

    def u32(self, a):
        return self.z.u32(a)

    def bytes(self, a, n):
        return list(self.z.elf[a - OFF:a - OFF + n])

    def shorts(self, a, n, signed=False):
        return list(struct.unpack_from(f'<{n}{"h" if signed else "H"}', self.z.elf, a - OFF))

    def en(self, a):
        return self.z.label(a, self.names)

    def jp(self, a):
        r = self.z.ui.get(a)
        if r:
            return r['japanese']
        end = self.z.elf.index(b'\0', a - OFF)
        return self.z.elf[a - OFF:end].decode('cp932', 'replace')

    def plist(self, a, n):
        return [self.en(self.u32(a + 4 * i)) for i in range(n)]

    def fixed(self, key):
        return self.z.text(self.z.fixed[key]['english'], self.names)

    def groups(self, table, width):
        rows = self.z.elf[table - OFF:]
        return [list(rows[i * width:(i + 1) * width]) for i in range(16)]

    # ---------- modes

    def ring_order(self):
        return self.bytes(RING_MAP, RING_N)

    def ring_name(self, ring):
        order = self.ring_order()
        return self.en(self.u32(RING_NAMES + 4 * order.index(ring))) if ring in order else str(ring)

    def rings(self):
        """The ring menu, then the (All Unlocked) patches' seven (tools/rings.py)."""
        out = [{'menu': k, 'id': r, 'name': self.en(self.u32(RING_NAMES + 4 * k)), 'ul': 0} for k, r in enumerate(self.ring_order())]
        return out + [{'menu': RING_N + k, 'id': RING_N + k, 'name': self.z.text(r[2], self.names), 'ul': 1}
                      for k, r in enumerate(ringpatch.RINGS)]

    def venue_name(self, i):
        p = self.u32(VENUE_NAMES + 4 * i)
        return (self.en(p).strip() if p else '') or DOJO

    def venues(self):
        out = []
        for i in range(VENUE_N):
            p = self.u32(VENUE_NAMES + 4 * i)
            out.append({'id': i, 'name': self.venue_name(i), 'jp': self.jp(p).strip() if p else '', 'row': VENUE_ROW[i]})
        return out

    def music(self):
        return self.plist(MUSIC, MUSIC_N)

    def referees(self):
        speed, length = self.plist(SPEED_LABELS, 5), self.plist(LENGTH_LABELS, 5)
        out = []
        for i in range(REFEREE_N):
            b = self.bytes(REFEREES + REFEREE_SIZE * i, 8)
            out.append({'id': i, 'name': self.fixed(f'referee:{i}'), 'jp': self.z.fixed[f'referee:{i}']['japanese'],
                        'pin': speed[b[2]], 'foul': speed[b[3]], 'ring_out': speed[b[5]], 'move': speed[b[4]],
                        'run_in': length[b[6]], 'crash_down': length[b[1]], 'voice': self.z.tone(b[7], self.names)})
        return out

    def promotions(self):
        members = {}
        for i in range(fpzrecord.N):
            members.setdefault(self.z.roster[i * fpzrecord.REC + 0x44], []).append(i)
        return [{'id': i, 'name': self.fixed(f'promo:{i}'), 'short': self.fixed(f'promo_short:{i}'),
                 'jp': self.z.fixed[f'promo:{i}']['japanese'], 'members': members.get(i, [])} for i in range(PROMO_N)]

    def teams(self):
        out = []
        for i in range(TEAM_N):
            a = self.u32(TEAM_NAMES + 4 * i)
            ids = [x & 0x1FF for x in self.shorts(TEAM_MEMBERS + i * 10, 5) if x != 0xFFFF]   # bits 9-11: costume
            out.append({'name': self.en(a), 'jp': self.jp(a), 'unlock': i >= TEAMS_OPEN, 'members': ids})
        return out

    def rule_text(self, rule):
        mt, _, fl = struct.unpack_from('<BBH', self.z.elf, VR_RULES + 4 * rule - OFF)
        out = [self.en(self.u32(MATCH_TYPES + 4 * mt))]
        if fl & 0x4000:
            out.append('SWA rules')
        if not fl & 2:
            out.append('no rope breaks')
        if not fl & 0x20:
            out.append('no fouls')
        return ', '.join(out)

    def victory_road(self):
        names = self.plist(VR_NAMES, VR_N)
        tables = [self.u32(VR_TABLES + 4 * c) for c in range(VR_N)]
        out = []
        for c in range(VR_N):
            size, nid = (12, 2) if c < 4 else (16, 4)
            side = self.u32(VR_SIDE + 4 * c)
            ladders, a, k = [], VR_PROMOS[c], 0
            while self.u16(a) != 0xFFFF:
                pid = self.u16(a)
                a += 2
                m = self.u32(tables[c] + 4 * k)
                k += 1
                matches = []
                while self.u16(m) != 0xFFFF:
                    w = self.shorts(m, nid + 4)
                    venue, com, row, song = w[nid:]
                    ring, ref, rule = self.bytes(VR_ROWS + 3 * row, 3)
                    pick = self.u8(VR_MUSIC + (song - 1 if 0 < song <= MUSIC_N else 0))
                    matches.append({'o': [x & 0x1FF for x in w[:side]], 'v': self.venue_name(venue - 1), 'c': com,
                                    'r': self.ring_name(ring), 'f': self.fixed(f'referee:{ref}'), 'u': self.rule_text(rule),
                                    'm': self.en(self.u32(MUSIC + 4 * pick))})
                    m += size
                ladders.append({'p': pid if c < 4 else None, 'name': self.fixed(f'promo:{pid}') if c < 4 else '', 'm': matches})
            out.append({'name': names[c], 'ladders': ladders})
        return out

    def _setting(self, r, v):
        """Row r's stored default v as the screen shows it."""
        if v == 255:
            return '-'
        if r in (0, 1, 0x14, 0x15, 0x16, 0x17, 0x18, 0x19):
            return self.en(self.u32(CORNER_LABELS + 4 * v))
        if r == 2:
            return self.en(self.u32(MATCH_TYPES + 4 * v))
        if r == 3:
            return self.en(self.u32(TIME_LIMITS + 4 * v))
        if r == 4:
            return ('1 Fall', '2 of 3 Falls')[v]
        if r == 5:
            return {0x7F: 'RANDOM', 0x20: 'Deathmatch Ring', 0x40: 'Dodecagon Ring'}.get(v) or \
                self.en(self.u32(RING_NAMES + 4 * v))
        if r == 6:
            return self.venue_name({0x20: 6, 0x40: 5}.get(v, v)) if v != 0x10 else 'RANDOM'
        if r == 7:
            return str(v + 1)
        if r == 8:
            return self.en(self.u32(SPEEDS + 4 * v))
        if r in (9, 0xB, 0xC, 0xD, 0xE, 0xF, 0x10):
            return 'ON' if v else 'OFF'
        if r == 0xA:
            return self.fixed(f'referee:{v}')
        if r == 0x11:
            return 'RANDOM' if v == 0x7F else self.en(self.u32(MUSIC + 4 * v))
        if r == 0x12:
            return self.en(self.u32(MATCHUPS + 4 * v))
        if r == 0x13:
            return self.en(self.u32(BLAST + 4 * v))
        if r == 0x1A:
            return self.en(self.u32(CRITICAL + 4 * v))
        if r == 0x1B:
            return ('Barbed Wire', 'Tubes')[v]
        if r == 0x1C:
            return ('5 Points', '2 Points')[v]
        return str(v)

    def layout(self, n):
        rows = []
        for i in range(self.u8(LAYOUT_COUNT + n)):
            r = self.u8(LAYOUT_ROW + 21 * n + i)
            if r != NEXT_ROW:
                rows.append({'row': self.en(self.u32(MATCH_LABELS + 4 * r)), 'v': self._setting(r, self.u8(LAYOUT_DEFAULT + 21 * n + i)),
                             'lock': bool(self.u8(LAYOUT_LOCK + 21 * n + i))})
        return rows

    def layouts(self):
        """{modes: [{mode, types: [{type, rows}]}]}: what Match Settings shows for each mode and match type."""
        types = [self.en(a) for a in TYPE_LABELS]
        modes = []
        for mode, t in TYPE_LAYOUT.items():
            modes.append({'mode': mode, 'types': [{'type': n, 'rows': self.layout(self.u8(t + i))} for i, n in enumerate(types)]})
        royal = ['Normal'] + [self.en(a) for a in ROYAL_LABELS]
        modes.append({'mode': 'Battle Royal', 'types': [{'type': n, 'rows': self.layout(self.u8(ROYAL_LAYOUT + i))} for i, n in enumerate(royal)]})
        modes.append({'mode': 'Elimination Match', 'types': [{'type': '', 'rows': self.layout(ELIMINATION_LAYOUT)}]})
        modes.append({'mode': 'Victory Road', 'types': [{'type': '', 'rows': self.layout(VICTORY_ROAD_LAYOUT)}]})
        modes.append({'mode': 'Title Match (No Limit)', 'types': [{'type': n, 'rows': self.layout(TITLE_NO_LIMIT + i)} for i, n in enumerate(types)]})
        modes.append({'mode': 'Title Match (Time Limit open)', 'types': [{'type': n, 'rows': self.layout(TITLE_FREE + i)} for i, n in enumerate(types)]})
        return modes

    def settings_rows(self):
        """The Match Settings rows: label, Japanese, the values, in screen order."""
        label = lambda r: self.en(self.u32(MATCH_LABELS + 4 * r))
        jp = lambda r: self.jp(self.u32(MATCH_LABELS + 4 * r))
        onoff = 'OFF, ON'
        rows = [(0, 'CP, 1P-4P; tag sides such as 1P-CP and CP-CP; 3- and 4-man sides'), (1, 'As Blue Corner'),
                (0x12, ', '.join(self.plist(MATCHUPS, 5))), (2, ', '.join(self.plist(MATCH_TYPES, 4))),
                (3, ', '.join(self.plist(TIME_LIMITS, 7))), (0x13, ', '.join(self.plist(BLAST, 8))),
                (0x1B, 'Barbed Wire, Tubes'), (4, '1 Fall, 2 of 3 Falls'), (0x1C, '5 Points, 2 Points'),
                (5, 'Every ring in the Rings table, RANDOM, then edit promotion rings'), (6, 'The venues marked Yes in the Venues table, RANDOM'),
                (7, '1-10'), (8, ', '.join(self.plist(SPEEDS, 8))), (9, onoff), (0xA, 'The 8 referees, then edit referees'),
                (0xB, onoff), (0xC, onoff), (0xD, onoff), (0xE, onoff), (0xF, onoff), (0x10, onoff),
                (0x11, 'The 15 songs, RANDOM'), (0x1A, ', '.join(self.plist(CRITICAL, 4)))]
        return [{'row': label(r), 'jp': jp(r), 'values': v} for r, v in rows]

    def skill_costs(self):
        out = []
        for i in self.z.skill_items(self.names):
            if i['label'].startswith(('Voice', 'Theme')):
                continue
            if i['cost'] and i['choices']:
                out.append({'label': i['label'], 'choices': [[c, p] for c, p in zip(i['choices'], i['cost'])]})
            elif not i['cost']:
                out.append({'label': i['label'], 'free': True})
        return {'rows': out, 'budget': list(COST_BUDGET)}

    def cpu_logic(self):
        out = []
        for s in self.z.cpu_tables(self.names):
            c = s['conditions'][0]
            out.append({'s': s['situation'], 'levels': [x['condition'] for x in s['conditions']],
                        'o': [[a, b] for a, b in zip(c['labels'], c['buttons'])]})
        return out

    def save_files(self):
        out = []
        for i in range(SAVE_N):
            a = self.u32(SAVE_NAMES + 4 * i)
            out.append({'name': self.z.elf[a - OFF:self.z.elf.index(b'\0', a - OFF)].decode('ascii'), 'bytes': SAVE_SIZES[i], 'use': SAVE_USE[i]})
        return out

    # ---------- match engine

    def styles_list(self):
        return self.items[0x45]['choices']

    def reversals_list(self):
        return self.items[0x46]['choices']

    def critical_types(self):
        """The six critical types by stored value (what they do), with the Skill Edit label."""
        choices = self.items[0x54]['choices']
        return [choices[self.u8(fpzrecord.CRIT_TO_CURSOR + k)] for k in range(6)]

    def critical(self):
        rows = lambda table, width: [self.bytes(table + width * k, width) for k in range(6)]
        return {'types': self.critical_types(), 'a': rows(CRIT_A, 16), 'r': rows(CRIT_R, 14), 's': rows(CRIT_S, 16)}

    def styles(self):
        counts = [0] * 16
        for k in range(fpzrecord.N):
            counts[self.z.roster[k * fpzrecord.REC + 0x45]] += 1
        reach, own = self.shorts(REACH, 16), self.shorts(OWN_DAMAGE, 16)
        bleed = self.shorts(BLEED_SPIRIT, 16, signed=True)
        anim = self.bytes(WHIP_ANIM, 16)
        return [{'name': n, 'roster': counts[s], 'reach': round(reach[s] / 2.56), 'own': round(own[s] / 2.56),
                 'bleed': round(bleed[s] / 655.36), 'rope': self.bytes(ROPE_STOP + 4 * s, 4),
                 'whip': self.bytes(WHIP_REVERSE + 4 * s, 4), 'anim': not anim[s]} for s, n in enumerate(self.styles_list())]

    def breath(self):
        pct = lambda v: round(v / 2.56)
        return [{'name': n, 'cost': [pct(v) for v in self.shorts(BREATH_STYLE + 24 * s, 12)],
                 'stamina': [pct(v) for v in self.shorts(BREATH_STAMINA + 8 * s, 4)]} for s, n in enumerate(self.styles_list())]

    def size(self):
        names = [self.z.size(i, self.names) for i in range(4)]
        t = self.shorts(SIZE_DAMAGE, 16)
        return {'names': names, 'damage': [[round(v / 2.56) for v in t[4 * a:4 * a + 4]] for a in range(4)],
                'breath': [round(v / 2.56) for v in self.shorts(SIZE_BREATH, 4)]}

    def skills(self):
        i = self.items[0x5C]
        flags = list(struct.unpack_from('<22I', self.z.elf, SKILL_FLAGS - OFF))
        basic = {f: n for f, n in zip(flags[1:13], i['choices'][1:13])}
        counts = [0] * 22
        for k in range(fpzrecord.N):
            counts[self.z.roster[k * fpzrecord.REC + 0x5C]] += 1
        out = []
        for k, n in enumerate(i['choices']):
            parts = [] if k < 13 else [b for f, b in basic.items() if flags[k] & f]
            out.append({'name': n, 'pts': i['cost'][k], 'roster': counts[k], 'effect': SKILL_EFFECTS.get(n, ''), 'note': SKILL_NOTES.get(n, ''), 'parts': parts})
        return out

    def affinity(self):
        db = fpzmoves.load(self.z)
        return {'styles': self.styles_list(), 'types': db['types']['attack'], 'grades': db['affinity']}

    def all(self):
        return {n: getattr(self, n)() for n in TABLES}


TABLES = ('rings', 'venues', 'music', 'referees', 'promotions', 'teams', 'victory_road', 'layouts', 'settings_rows', 'skill_costs',
          'cpu_logic', 'save_files', 'critical', 'styles', 'breath', 'size', 'skills', 'affinity')


def main(argv=None):
    argv = paths.configure(sys.argv[1:] if argv is None else argv)
    if '-h' in argv or '--help' in argv:
        print(__doc__)
        return 0
    names = 'real'
    if '--names' in argv:
        k = argv.index('--names')
        names = argv[k + 1]
        del argv[k:k + 2]
    if names not in ('real', 'parody'):
        sys.exit('--names takes real or parody')
    bad = [a for a in argv if a not in TABLES]
    if bad:
        sys.exit(f'no table {", ".join(bad)}: the tables are {", ".join(TABLES)}')
    if not argv:
        print(' '.join(TABLES))
        return 0
    t = Tables(fpzrecord.Tables(), names)
    print(json.dumps({a: getattr(t, a)() for a in argv}, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
