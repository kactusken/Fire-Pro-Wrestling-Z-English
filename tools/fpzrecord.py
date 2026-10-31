#!/usr/bin/env python3
"""Fire Pro Wrestling Z's wrestler records (extracted/STRHUMAN.BIN) as English profiles.

  python3 tools/fpzrecord.py [NAME|INDEX ...]    print profiles (default: a few samples)
  python3 tools/fpzrecord.py --check             check every record against the layout
  python3 tools/fpzrecord.py --tables            print the choice, slot and CPU tables
  python3 tools/fpzrecord.py --json FILE         write all 244 profiles as JSON

    import fpzrecord
    z = fpzrecord.Tables()                 # the original executable + translation/text/*.csv
    p = z.profile(k)                       # record k as a dict; z.profile(k, names='parody')

Standard library only. Everything is read from the original executable's own tables (Skill Edit
descriptors, Move Edit tables, CPU Logic tables) with the English of translation/text/, so labels
are what the patched game shows; names='real' or 'parody' picks the name set. tools/guidedata.py
uses this for the guide's roster and profiles.

Record layout (0x23C bytes, 244 records; RAM address = file offset + 0xFF000): +0x00 class, +0x01
name flags, +0x02 short name, +0x10 name 2, +0x24 nickname, +0x3E height cm, +0x3F weight kg, +0x40
hometown, +0x41-43 birth year-1900 (0xFF unknown), month, day, +0x44 promotion, +0x45 style, +0x46
reversals, +0x47-53 the Skill Edit ratings (Skill Edit's descriptors give each one's offset), +0x54
critical in effect order (0x3AB7E0 converts it to the list position the costs and labels use),
+0x55 theme - 1, +0x56 / +0x58 voices (bits 9-12 tone, bits 0-8 type), +0x5A stance, +0x5B size, +0x5C
skill, +0x5D-67 attack ratings and +0x68-72 defence ratings (stored 3-12, shown 1-10), +0x74 78 move
slots (bits 0-11 move id, 0x1000 signature, 0x2000 finisher, 0x4000 / 0x8000 voice 1 / 2), +0x110-1D2
CPU Logic (cumulative percentages; the last option gets the rest), +0x1D4 four 26-byte outfits.
"""
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fpztext  # noqa: E402
import paths  # noqa: E402

REC = 0x23C
N = 244
OFF = 0xFF000                  # RAM address = file offset + OFF
EDIT_BUF = 0x30C2F0            # editor copy of the record: value pointer - EDIT_BUF = record offset
SKILL_DESC, SKILL_N = 0x30F750, 30      # 24 bytes each: u16 kind, u16 ?, u16 lo, u16 hi, choices, ?, label, value
COST_TABLES = 0x30FA38         # u32 x 8, by descriptor kind >> 4 (1-based): cost by value
CRIT_TO_CURSOR = 0x3AB7E0      # 6 bytes: stored critical -> Skill Edit list position
PARAM_LABELS, PARAM_N = 0x30EE98, 22    # +0x5D..+0x72, stored 3..12, shown 1..10
TONES, TONE_N = 0x30EF98, 11
VOICE_TYPES = (0x30F258, 0x30F458, 0x30F590)     # tone 0-4, 5-7, 8-10
STANCES, SIZES = 0x30C9F8, 0x30CA58              # 8-byte records (u32 value, u32 label)
STANCE_N, SIZE_N = 12, 4
MOVE_LISTS, LIST_N = 0x3106F8, 43       # u32 pointer, u16 count, s16 list also offered
SLOT_LIST = 0x310850           # 78 bytes by record slot: its list
SLOT_LABELS = 0x3108A0         # 78 label pointers by record slot
ROW_SLOT = 0x3109D8            # 78 bytes: Move Edit row -> record slot
ROW_ICONS = 0x3112E8           # 78 x 5 halfwords by row: label x, icon, x, icon, x
SLOT_BREATH = 0x2E07A8         # 78 u16 by record slot: the base breath cost of using it
SLOTS, SLOT_N = 0x74, 78
MOVE_FLAGS = {0x1000: 'Signature', 0x2000: 'Finisher', 0x4000: 'Voice 1', 0x8000: 'Voice 2'}
CPU_SITUATIONS, CPU_N = 0x30C008, 20    # 12 bytes: label, conditions, u8 n, u8 icon list
STYLE_ACTIONS = 0x30C0F8       # 16 styles x 3 label pointers: CPU actions 0x201 / 0x202 / 0x203
CPU_ICON_PTRS, CPU_ICON_COUNTS = 0x30B968, 0x30B9B0
HIDDEN = 0x215940              # 244 bytes: nonzero = locked until unlock level 1
# BUTTON.GST's cells. 11 is a D-pad with nothing lit: any direction held (0x127D3C picks slot 75 if
# one is, slot 2 if none). 12-15 are the left stick (0x126C38, record slots 0x4C, 0x4D, 0x31, 0x32).
ICONS = {0: 'Square', 1: 'Cross', 2: 'Circle', 3: 'Triangle', 4: 'Up', 5: 'Down', 6: 'Left/Right',
         7: 'Up/Down', 8: 'R1', 9: 'L1', 11: 'Any direction', 12: 'Stick Up', 13: 'Stick Down',
         14: 'Stick Left', 15: 'Stick Right'}
ATTACK_TYPES = 11              # Param list order: attack types 0-10 (+0x5D), defence types 11-21 (+0x68)
# The guide's name for each Move Edit list (the game only shows the slot labels; D's guide, same 43
# lists; 31-32 renamed for Z's Guard Position).
LIST_TITLES = [
    'Standing strikes: weak', 'Standing strikes: medium', 'Standing strikes: strong', 'Running attacks',
    'Counters to a running opponent', 'Diagonal run', 'Dives to the outside', 'From the apron to the outside',
    'From the apron into the ring', 'Off the top rope', 'Grapples: weak', 'Grapples: medium', 'Grapples: strong',
    'From behind: weak', 'From behind: medium', 'From behind: strong', 'Reversals from behind (Square)',
    'Reversals from behind (Cross)', 'Downed opponent: face up, at the head', 'Downed opponent: face up, at the legs',
    'Downed opponent: face down, at the head', 'Downed opponent: face down, at the legs',
    'Running attacks on a downed opponent', 'Opponent in the corner', 'Taunts', 'Double-team: in front',
    'Triple-team: in front', 'Double-team: from behind', 'Triple-team: from behind', 'Double-team: in the corner',
    'Triple-team: in the corner', 'Guard position: attacks', 'Guard position: reversals', 'Front facelock: attacks',
    'Front facelock: reversals', 'Back mount: attacks', 'Back mount: reversals',
    'Corner dives: standing opponent', 'Corner dives: downed opponent', 'Apron grapples: from inside the ring',
    'Apron grapples: from the apron', 'Top-rope reversals: in front', 'Top-rope reversals: from behind']


class Tables:
    """The original program's tables and the English; a profile for any record."""

    def __init__(self):
        self.elf = (paths.EXTRACTED / fpztext.EXE).read_bytes()
        self.roster = (paths.EXTRACTED / 'STRHUMAN.BIN').read_bytes()
        self.ui = {int(r['id'], 16): r for r in fpztext.read_table('ui.csv')}
        self.moves = {int(r['index']): r for r in fpztext.read_table('moves.csv')}
        self.wrestlers = {int(r['idx']): r for r in fpztext.read_table('wrestlers.csv')}
        self.fixed = {r['id']: r for r in fpztext.read_table('fixed.csv')}
        self._cache = {}

    def u32(self, a):
        return struct.unpack_from('<I', self.elf, a - OFF)[0]

    def text(self, english, names):
        return fpztext.resolve(fpztext.unesc(english), names, 'fpzrecord').replace('\n', ' ')

    def label(self, a, names='real'):
        """The English of the string at RAM a; the Japanese if it has none."""
        r = self.ui.get(a)
        if r and r['english']:
            return self.text(r['english'], names)
        end = self.elf.index(b'\0', a - OFF)
        return self.elf[a - OFF:end].decode('cp932', 'replace')

    def move_name(self, i, names='real'):
        r = self.moves.get(i)
        return self.text(r['english'], names) if r and r['english'] else None

    def promotion(self, k, names='real'):
        r = self.fixed.get(f'promo:{k}')
        return self.text(r['english'], names) if r else str(k)

    def full_name(self, k, names='real'):
        r = self.wrestlers[k]
        a, b, order = ((r['en_name1'], r['en_name2'], r['en_order']) if names == 'real' else
                       (r['parody_name1'], r['parody_name2'], r['parody_order']))
        a, b = self.text(a, names), self.text(b, names)
        return ' '.join(x for x in ((b, a) if order == '2-1' else (a, b)) if x)

    def skill_items(self, names='real'):
        """Skill Edit in screen order: dicts label, kind, off, lo, hi, choices, cost, field."""
        out = []
        for k in range(SKILL_N):
            kind, _, lo, hi, ch, _, lab, val = struct.unpack_from('<HHHHIIII', self.elf, SKILL_DESC - OFF + 24 * k)
            t = kind & 15
            choices = [self.label(self.u32(ch + 4 * j), names) for j in range(lo, hi + 1)] if ch else None
            cost = None
            if kind >> 4:
                p = self.u32(COST_TABLES + 4 * ((kind >> 4) - 1)) - OFF
                cost = list(self.elf[p:p + hi + 1])[lo:]
            out.append({'label': self.label(lab, names), 'kind': t, 'off': val - EDIT_BUF, 'lo': lo,
                        'hi': hi, 'choices': choices, 'cost': cost, 'cost_kind': kind >> 4})
        return out

    def param_labels(self, names='real'):
        return [self.label(self.u32(PARAM_LABELS + 4 * k), names) for k in range(PARAM_N)]

    def tone(self, t, names='real'):
        return self.label(self.u32(TONES + 4 * t), names)

    def voice(self, v, names='real'):
        """A voice field: bits 9-12 tone, bits 0-8 the type (0x14CF48, 0x14CF58, 0x14D0A8)."""
        tone, typ = v >> 9 & 15, v & 0x1FF
        base = VOICE_TYPES[0 if tone < 5 else 1 if tone < 8 else 2]
        return {'tone': self.tone(tone, names), 'type': self.label(self.u32(base + 4 * typ), names),
                'tone_id': tone, 'type_id': typ}

    def stance(self, v, names='real'):
        return self.label(self.u32(STANCES + 4 + 8 * v), names)

    def size(self, v, names='real'):
        return self.label(self.u32(SIZES + 4 + 8 * v), names)

    def rows(self, names='real'):
        """78 Move Edit rows: row, slot, offset, label, buttons, list (index, title, also offered)."""
        out = []
        for row in range(SLOT_N):
            slot = self.elf[ROW_SLOT - OFF + row]
            _, i1, _, i2, _ = struct.unpack_from('<5h', self.elf, ROW_ICONS - OFF + 10 * row)
            btn = ' + '.join(ICONS[i] for i in (i1, i2) if i >= 0)
            lab = self.label(self.u32(SLOT_LABELS + 4 * slot), names)
            lst = self.elf[SLOT_LIST - OFF + slot]
            _, count, also = struct.unpack_from('<IHh', self.elf, MOVE_LISTS - OFF + 8 * lst)
            breath = struct.unpack_from('<H', self.elf, SLOT_BREATH - OFF + 2 * slot)[0]
            out.append({'row': row, 'slot': slot, 'off': SLOTS + 2 * slot, 'label': lab, 'buttons': btn,
                        'name': f'{lab} {btn}' if btn else lab, 'list': lst, 'list_title': LIST_TITLES[lst],
                        'list_count': count, 'also_offers': also, 'breath': breath})
        return out

    def cpu_tables(self, names='real'):
        """[{situation, conditions: [{condition, off, codes, labels}]}], as the CPU Logic screen."""
        out = []
        for s in range(CPU_N):
            lab, conds, n, icons = struct.unpack_from('<IIBB', self.elf, CPU_SITUATIONS - OFF + 12 * s)
            glyph = {}
            if icons != 0xFF:
                recs = self.u32(CPU_ICON_PTRS + 4 * icons)
                cnt = struct.unpack_from('<H', self.elf, CPU_ICON_COUNTS - OFF + 2 * icons)[0]
                for k in range(cnt):
                    ic, row, _ = struct.unpack_from('<bbb', self.elf, recs + 3 * k - OFF)
                    glyph.setdefault(row, []).append(ICONS.get(ic, f'icon {ic}'))
            cl = []
            for c in range(n):
                clab, acts, na, data = struct.unpack_from('<IIII', self.elf, conds - OFF + 16 * c)
                na &= 0xFFFF
                codes, labs, btns = [], [], []
                for a in range(na):
                    alab, code = struct.unpack_from('<II', self.elf, acts - OFF + 8 * a)
                    codes.append(code)
                    labs.append(self.label(alab, names))
                    btns.append(' + '.join(glyph.get(a, [])))
                cl.append({'condition': self.label(clab, names), 'off': data - EDIT_BUF, 'codes': codes,
                           'labels': labs, 'buttons': btns})
            out.append({'situation': self.label(lab, names), 'conditions': cl})
        return out

    def edit_points(self, rec):
        """What the record costs in edit points (0x14CDC0): Skill Edit costs + Param Edit steps."""
        rec = bytearray(rec)
        rec[0x54] = self.elf[CRIT_TO_CURSOR - OFF + rec[0x54]]        # the costs are in list order
        total = 0
        for k in range(SKILL_N):
            kind, _, _, _, _, _, _, val = struct.unpack_from('<HHHHIIII', self.elf, SKILL_DESC - OFF + 24 * k)
            if kind >> 4:
                total += self.elf[self.u32(COST_TABLES + 4 * ((kind >> 4) - 1)) - OFF + rec[val - EDIT_BUF]]
        return total + sum(rec[0x5D + k] - 3 for k in range(PARAM_N))

    def cached(self, what, names):
        """skill_items / rows / cpu_tables once per name set."""
        key = what, names
        if key not in self._cache:
            self._cache[key] = getattr(self, what)(names)
        return self._cache[key]

    def profile(self, k, names='real'):
        """Record k as a dict of English values (labels as the patched game shows them)."""
        rec = self.roster[k * REC:(k + 1) * REC]
        w = self.wrestlers[k]
        items = {i['off']: i for i in self.cached('skill_items', names)}

        def choice(off, shift=0):
            return items[off]['choices'][rec[off] - items[off]['lo'] + shift]
        crit = self.elf[CRIT_TO_CURSOR - OFF + rec[0x54]]
        p = {'id': k, 'name': self.full_name(k, names), 'short': self.text(w['en_name1'] if names == 'real' else w['parody_name1'], names),
             'nickname': self.text((w['parody_nick'] or w['en_nick']) if names == 'parody' else w['en_nick'], names),
             'japanese': w['jp_full'], 'class': self.label(self.u32(0x30F098 + 4 * rec[0]), names),
             'height_cm': rec[0x3E], 'weight_kg': rec[0x3F], 'hometown': choice(0x40),
             'birth': None if rec[0x41] == 0xFF else {'year': 1900 + rec[0x41], 'month': rec[0x42], 'day': rec[0x43]},
             'promotion': self.promotion(rec[0x44], names), 'style': choice(0x45), 'reversals': choice(0x46),
             'critical': items[0x54]['choices'][crit], 'skill': choice(0x5C), 'theme': rec[0x55] + 1,
             'stance': self.stance(rec[0x5A], names), 'size': self.size(rec[0x5B], names),
             'voice1': self.voice(struct.unpack_from('<H', rec, 0x56)[0], names),
             'voice2': self.voice(struct.unpack_from('<H', rec, 0x58)[0], names),
             'edit_points': self.edit_points(rec), 'hidden': bool(self.elf[HIDDEN - OFF + k]), 'raw': {'style': rec[0x45], 'reversals': rec[0x46],
                                                           'critical': rec[0x54], 'skill': rec[0x5C], 'size': rec[0x5B]}}
        p['skill_edit'] = {items[o]['label']: choice(o) for o in (0x47, 0x48, 0x49, 0x4A, 0x4B, 0x4C, 0x4D, 0x4E,
                                                                  0x4F, 0x50, 0x51, 0x52, 0x53)}
        labs = self.param_labels(names)
        p['params'] = {labs[j]: rec[0x5D + j] - 2 for j in range(PARAM_N)}
        slots = struct.unpack_from(f'<{SLOT_N}H', rec, SLOTS)
        moves = []
        for r in self.cached('rows', names):
            v = slots[r['slot']]
            moves.append({'row': r['row'], 'slot': r['slot'], 'label': r['name'], 'id': v & 0xFFF,
                          'move': self.move_name(v & 0xFFF, names),
                          'marks': [n for b, n in MOVE_FLAGS.items() if v & b]})
        p['moves'] = moves
        p['finisher'] = next((m['move'] for m in moves if 'Finisher' in m['marks']), None)
        p['signature'] = [m['move'] for m in moves if 'Signature' in m['marks']]
        logic = []
        for s in self.cached('cpu_tables', names):
            cl = []
            for c in s['conditions']:
                n, off = len(c['codes']), c['off']
                cum = list(rec[off:off + n - 1]) + [100]
                pct = [cum[0]] + [cum[i] - cum[i - 1] for i in range(1, n)]
                acts = []
                for code, lab, btn, pc in zip(c['codes'], c['labels'], c['buttons'], pct):
                    if code < 0x100:
                        detail = self.move_name(slots[code] & 0xFFF, names)
                    elif code in (0x201, 0x202, 0x203):
                        detail = self.label(self.u32(STYLE_ACTIONS + 12 * rec[0x45] + 4 * (code - 0x201)), names)
                    else:
                        detail = None
                    acts.append({'action': lab, 'buttons': btn, 'move': detail, 'slot': code if code < 0x100 else None,
                                 'pct': pc})
                cl.append({'condition': c['condition'], 'actions': acts})
            logic.append({'situation': s['situation'], 'conditions': cl})
        p['cpu_logic'] = logic
        p['outfits_raw'] = [rec[0x1D4 + 26 * i:0x1D4 + 26 * (i + 1)].hex() for i in range(4)]
        return p


def show(p):
    b = p['birth']
    print(f"#{p['id']} {p['name']} \"{p['nickname']}\" ({p['japanese']}) - {p['promotion']}")
    print(f"  {p['class']}, {p['height_cm']} cm, {p['weight_kg']} kg, {p['hometown']}, born "
          f"{'unknown' if not b else '%d-%02d-%02d' % (b['year'], b['month'], b['day'])}; size {p['size']}, stance {p['stance']}")
    print(f"  Style {p['style']}, Reversals {p['reversals']}, Critical {p['critical']}, Skill {p['skill']}, Theme {p['theme']}, {p['edit_points']} points")
    print('  ' + ', '.join(f'{a}: {v}' for a, v in p['skill_edit'].items()))
    print(f"  Voices: {p['voice1']['tone']} {p['voice1']['type']} / {p['voice2']['tone']} {p['voice2']['type']}")
    print('  Params: ' + ', '.join(f'{a} {v}' for a, v in p['params'].items()))
    print(f"  Finisher: {p['finisher']} | Signature: {', '.join(m or '-' for m in p['signature'])}")
    for m in p['moves']:
        print(f"  {m['row'] + 1:2d} {m['label']:<30} {m['move'] or '-'}{' [' + ', '.join(m['marks']) + ']' if m['marks'] else ''}")
    for s in p['cpu_logic']:
        for c in s['conditions']:
            acts = '; '.join(f"{a['action']} {a['buttons']}{' (' + a['move'] + ')' if a['move'] else ''} {a['pct']}%"
                             for a in c['actions'] if a['pct'])
            print(f"  [{s['situation']} / {c['condition']}] {acts}")


def check(z):
    """Every record against the layout: nothing out of range, CPU percentages cumulative."""
    bad = []
    items = z.skill_items()
    cpu = z.cpu_tables()
    for k in range(N):
        r = z.roster[k * REC:(k + 1) * REC]
        for i in items:
            if i['kind'] == 1 and i['choices'] and not i['lo'] <= r[i['off']] <= i['hi']:
                bad.append((k, i['label'], r[i['off']]))
        if not all(3 <= r[0x5D + j] <= 12 for j in range(PARAM_N)):
            bad.append((k, 'param'))
        if not 150 <= r[0x3E] <= 220 or not 40 <= r[0x3F] <= 250:
            bad.append((k, 'height/weight', r[0x3E], r[0x3F]))
        if r[0x41] != 0xFF and not (1 <= r[0x42] <= 12 and 1 <= r[0x43] <= 31):
            bad.append((k, 'birth'))
        s = struct.unpack_from(f'<{SLOT_N}H', r, SLOTS)
        if sum(1 for v in s if v & 0x2000) != 1:
            bad.append((k, 'finishers'))
        for sit in cpu:
            for c in sit['conditions']:
                n = len(c['codes']) - 1
                v = list(r[c['off']:c['off'] + n])
                if v != sorted(v) or (v and v[-1] > 100):
                    bad.append((k, sit['situation'], c['condition'], v))
    print(f'{N} records, {len(bad)} problems')
    for b in bad[:40]:
        print(' ', b)
    return len(bad)


def tables(z):
    for i in z.skill_items():
        print(f"+{i['off']:#04x} {i['label']}: {i['choices'] or (i['lo'], i['hi'])}" + (f" cost {i['cost']}" if i['cost'] else ''))
    print('Params (+0x5D..):', z.param_labels())
    for r in z.rows():
        print(f"{r['row'] + 1:2d} slot {r['slot']:2d} +{r['off']:#05x} {r['name']:<30} list {r['list']:2d} {r['list_title']} ({r['list_count']}"
              + (f", plus list {r['also_offers']})" if r['also_offers'] >= 0 else ')') + f" breath {r['breath']}")
    for s in z.cpu_tables():
        print(s['situation'])
        for c in s['conditions']:
            print(f"  +{c['off']:#05x} {c['condition']}: {c['labels']}")


def main(argv=None):
    argv = list(paths.configure(sys.argv[1:] if argv is None else argv))
    if '-h' in argv or '--help' in argv:
        print(__doc__)
        return 0
    z = Tables()
    if '--check' in argv:
        return 1 if check(z) else 0
    if '--tables' in argv:
        tables(z)
        return 0
    if '--json' in argv:
        out = argv[argv.index('--json') + 1]
        Path(out).write_text(json.dumps([z.profile(k) for k in range(N)], ensure_ascii=False, indent=1), encoding='utf-8')
        print('wrote', out)
        return 0
    for w in argv or ['Misawa', 'Hashimoto', 'Inoki']:
        ks = [int(w)] if w.isdigit() else [k for k in range(N) if w.lower() in z.full_name(k).lower()]
        if not ks:
            sys.exit(f'no wrestler matches {w!r}: give a roster index or part of an English name (translation/text/wrestlers.csv)')
        for k in ks:
            show(z.profile(k))
    return 0


if __name__ == '__main__':
    sys.exit(main())
