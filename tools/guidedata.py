#!/usr/bin/env python3
"""The data blocks of the guide's four pages (docs/guide/, block id page-data): every table the game holds.

  python3 tools/guidedata.py [--check]

Reads the original's tables from extracted/ (tools/fpzrecord.py the wrestlers, tools/fpzmoves.py the
moves, tools/fpztables.py the modes and match engine) with the English of translation/text/, in both
name versions, so the page always shows the patch's names; and docs/story_matches.csv (tools/storymap.py).
--check only compares, on all four pages (tools/check.py runs it). The pages themselves come from
private/work/guide/page/: assemble.py there leaves these blocks empty, and this tool fills them.

Each page gets only what it uses (page_blocks below): Guide wn and its rules and engine tables, Story
wslugs and the story tables, Wrestlers the roster and what the dialog and the move card need, Create
the moves and the editors' tables. The shapes, for the page's tables/ parts. A value that differs
between the name versions is [real, parody], any other is plain.
  wn        the wrestlers' names, for the Guide's links to their profiles
  wslugs    the roster's real names as #entry- slugs, for the Story page's links to their profiles
  roster    [{n name, k nick, j Japanese, p promotion, c class, st style, cr critical, sk skill, rv reversals,
            f finisher, h, w, o hometown, b birth date, stn stance, sz size, th theme, v voices, pts edit
            points, hid locked at the start, se Skill Edit values (in seLabels order), pa 22 ratings,
            mv 78 slots in Move Edit order (move id * 4 + finisher * 2 + signature), ai CPU Logic (flat
            over `ai` below: percent, or [percent, move id or text])}]
  moves     [{i id, n, j, l lists, d [stamina, spirit, breath, neck, arm, back, leg], b bleed, t ticks,
            a [main, sub], e [main, sub], x flags, c critical classes, u used by, s own loss, w weakened by,
            new, ul (All Unlocked only)}]: every move a player can use
  lists     the 43 Move Edit lists; slots the 78 rows; ai the CPU Logic situations; choice the Skill Edit
            lists; t all other tables (tools/fpztables.py) and story, the match tables by scenario.
            On Wrestlers a move keeps only its first list and lists only their titles: the card's use.
  names     every page: {k: [real, parody]} for its <span class="nm" data-k="k"> names in the prose, k
            being the place in fpztext.prose_names() (assemble.py puts in the spans)
"""
import argparse
import csv
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fpzmoves  # noqa: E402
import fpzrecord  # noqa: E402
import fpztables  # noqa: E402
import fpztext  # noqa: E402
import pagedata  # noqa: E402
import paths  # noqa: E402

VERSIONS = ('real', 'parody')
SE_OFFSETS = (0x47, 0x48, 0x49, 0x4A, 0x4B, 0x4C, 0x4D, 0x4E, 0x4F, 0x50, 0x51, 0x52, 0x53)      # Skill Edit's ratings
MOVE_FIRST_ROW_GROUPS = [(0, 'Standing'), (5, 'Running'), (7, 'Counter (opponent running at you)'),
                         (9, 'Diagonal run, dives and the apron'), (13, 'Off the top rope'), (17, 'Grapple'),
                         (30, 'Behind the opponent'), (36, 'Reversal (opponent behind you)'), (38, 'Downed opponent'),
                         (47, 'Corner'), (50, 'Team moves'), (56, 'Guard position'), (60, 'Front facelock'),
                         (64, 'Back mount'), (68, 'Corner dive'), (70, 'Apron and top-rope reversals'), (74, 'Taunts')]
# Story match rules (docs/story_matches.csv rule, rule2): 0x02 rope breaks, 0x80 ring-out; rule2 3 = Sub Only
ROPE_BREAK, RING_OUT, SUB_ONLY = 0x02, 0x80, 3


def both(a, b):
    """a and b (the real and parody forms of one value), with every difference turned into [a, b]."""
    if isinstance(a, dict):
        return {k: both(a[k], b[k]) for k in a}
    if isinstance(a, (list, tuple)):
        if len(a) != len(b):
            sys.exit(f'name versions differ in shape: {a!r} / {b!r}')
        return [both(x, y) for x, y in zip(a, b)]
    return a if a == b else [a, b]


def slug(t):
    return re.sub(r'[^a-z0-9]+', '-', unicodedata.normalize('NFKD', t).lower()).strip('-')


def roster_rows(z):
    """The roster block and the shapes shared by every profile (Skill Edit labels, CPU Logic)."""
    rows = []
    shape = None
    for k in range(fpzrecord.N):
        r, q = z.profile(k, 'real'), z.profile(k, 'parody')
        rec = z.roster[k * fpzrecord.REC:(k + 1) * fpzrecord.REC]
        items = z.cached('skill_items', 'real')
        labels = {i['off']: i['label'] for i in items}
        se = [r['skill_edit'][labels[o]] for o in SE_OFFSETS]
        fin = next((m['id'] for m in r['moves'] if 'Finisher' in m['marks']), None)
        mv = [m['id'] * 4 + ('Finisher' in m['marks']) * 2 + ('Signature' in m['marks']) for m in r['moves']]
        ai = []
        for s, sq in zip(r['cpu_logic'], q['cpu_logic']):
            for c, cq in zip(s['conditions'], sq['conditions']):
                for a, aq in zip(c['actions'], cq['actions']):
                    if not a['pct'] or not a['move']:
                        ai.append(a['pct'])
                    elif a['slot'] is not None:
                        ai.append([a['pct'], z_slot_move(rec, a['slot'])])
                    else:
                        ai.append([a['pct'], both(a['move'], aq['move'])])
        b = r['birth']
        rows.append({'n': both(r['name'], q['name']), 'k': both(r['nickname'], q['nickname']), 'j': r['japanese'],
                     'p': rec[0x44], 'c': r['class'], 'st': rec[0x45], 'cr': z.elf[fpzrecord.CRIT_TO_CURSOR - fpzrecord.OFF + rec[0x54]],
                     'sk': rec[0x5C], 'rv': rec[0x46], 'f': fin, 'h': r['height_cm'], 'w': r['weight_kg'], 'o': r['hometown'],
                     'b': f"{b['year']}-{b['month']:02d}-{b['day']:02d}" if b else '', 'stn': r['stance'], 'sz': r['size'], 'th': r['theme'],
                     'v': [f"{v['tone']}: {v['type']}" for v in (r['voice1'], r['voice2'])], 'pts': r['edit_points'],
                     'hid': 1 if r['hidden'] else 0, 'se': se, 'pa': list(r['params'].values()), 'mv': mv, 'ai': ai})
        if shape is None:
            shape = {'seLabels': [labels[o] for o in SE_OFFSETS], 'pa': list(r['params']),
                     'ai': [{'s': both(s['situation'], sq['situation']),
                             'c': [{'n': both(c['condition'], cq['condition']),
                                    'a': [[both(a['action'], aq['action']), a['buttons']] for a, aq in zip(c['actions'], cq['actions'])]}
                                   for c, cq in zip(s['conditions'], sq['conditions'])]}
                            for s, sq in zip(r['cpu_logic'], q['cpu_logic'])]}
    return rows, shape


def z_slot_move(rec, slot):
    return int.from_bytes(rec[fpzrecord.SLOTS + 2 * slot:fpzrecord.SLOTS + 2 * slot + 2], 'little') & 0xFFF


def moves_block(db):
    """Every move a player can use (reserved and blank ids left out, id 0 is None)."""
    out = []
    for m in db['moves']:
        if m['status'] not in ('standard', 'unlisted-patch'):
            continue
        d = m['damage']
        s = list(m['self_damage'].values())
        row = {'i': m['id'], 'n': both(m['en'], m['en_parody']), 'j': m['jp'], 'l': m['lists'],
               'd': list(d.values()), 'b': m['bleed'], 't': m['ticks'], 'a': list(m['attack']), 'e': list(m['defence']),
               'x': m['illegal'] * 1 + m['submission'] * 2, 'c': m['critical'], 'u': m['users']}
        if any(s):
            row['s'] = s
        if m['lowered_by']:
            row['w'] = m['lowered_by']
        if m['new_in_z']:
            row['new'] = 1
        if m['status'] == 'unlisted-patch':
            row['ul'] = 1
        out.append(row)
    return out


def lists_block(db, rows):
    label = {}
    for r in rows:
        label.setdefault(r['list'], []).append([r['label'], r['buttons']])
    # Eight lists start with id 0, None (a slot there may stay empty): not a move, so not counted
    real = lambda ids: [i for i in ids if i]
    return [{'t': x['title'], 'inc': x['chain'], 's': label[x['index']], 'own': len(real(x['own_ids'])), 'menu': len(real(x['menu_ids'])),
             'm': sorted(set(real(x['own_ids'])) | set(x['patch_adds'])), 'add': x['patch_adds']} for x in db['lists']]


def story_block(t, z):
    """docs/story_matches.csv by scenario: only what's safe before playing (no scene targets)."""
    with open(paths.DOCS / 'story_matches.csv', encoding='utf-8', newline='') as f:
        rows = list(csv.DictReader(ln for ln in f if not ln.startswith('#')))
    # A card prints a full name, a short one or a story name: all resolve to the parody form
    known = {real: parody for real, parody in fpztext.name_tokens().values()}
    for k in z.wrestlers:
        known[z.full_name(k, 'real')] = z.full_name(k, 'parody')

    def parody(name):
        if name in known:
            return known[name]
        hits = {p for r, p in known.items() if r.endswith(' ' + name)}
        return hits.pop() if len(hits) == 1 else fpztext.swap_names(name)

    def names(text):
        real = text.split(' & ')
        return both(real, [parody(n) for n in real])
    venues = t[0].venues(), t[1].venues()
    crit = t[0].plist(fpztables.CRITICAL, 4)
    out = {}
    for r in rows:
        rule, kind = int(r['rule']), int(r['rule2'])
        if 'Battle Royal' in r['rules']:
            how = 'Battle royal'
        elif kind == SUB_ONLY:
            how = 'Sub Only, rope breaks' if rule & ROPE_BREAK else 'Sub Only, no rope breaks'
        elif not rule & ROPE_BREAK:
            how = 'Deathmatch'
        else:
            how = 'Normal'
        v = int(r['venue'])
        out.setdefault(r['scenario'], []).append({
            'm': int(r['match']), 'side': names(r['hero_side']), 'o': names(r['opponents']),
            'lim': r['rules'].split(' Min.')[0] + ' min' if ' Min.' in r['rules'] else 'No limit', 'r': how,
            'c': int(r['com']) + 1, 'cr': crit[int(r['critical'])], 'v': both(venues[0][v]['name'], venues[1][v]['name']),
            'w': int(r['win_score']) if r['win_score'] else None, 'l': int(r['lose_score']) if r['lose_score'] else None})
    return out


def build():
    z = fpzrecord.Tables()
    db = fpzmoves.load(z)
    t = fpztables.Tables(z, 'real'), fpztables.Tables(z, 'parody')
    tables = both(*(x.all() for x in t))
    roster, shape = roster_rows(z)
    rows = z.rows()
    tables['story'] = story_block(t, z)
    return {'roster': roster, 'moves': moves_block(db), 'lists': lists_block(db, rows),
            'slots': [{'l': r['label'], 'b': r['buttons'], 'k': r['list'], 'br': r['breath']} for r in rows],
            'groups': MOVE_FIRST_ROW_GROUPS, 'seLabels': shape['seLabels'], 'pa': shape['pa'], 'ai': shape['ai'],
            'atk': db['types']['attack'], 'def': db['types']['param_edit'][11:],
            'choice': {'style': both(t[0].styles_list(), t[1].styles_list()), 'rev': both(t[0].reversals_list(), t[1].reversals_list()),
                       'crit': both(*(x.items[0x54]['choices'] for x in t)), 'skill': both(*(x.items[0x5C]['choices'] for x in t))},
            't': tables}


def move_users(d):
    """The moves with who uses them, for Create's move card: uw, wrestler * 4 + flags (2 finisher, 1
    signature), finishers and signatures first. Wrestlers works it out from its roster."""
    users = {}
    for wi, r in enumerate(d['roster']):
        seen = {}
        for v in r['mv']:
            if v >> 2:
                seen[v >> 2] = max(seen.get(v >> 2, 0), v & 3)
        for i, fl in seen.items():
            users.setdefault(i, []).append((-fl, wi))
    return [{**m, 'uw': [wi * 4 - fl for fl, wi in sorted(users[m['i']])]} if m['i'] in users else m for m in d['moves']]


def page_blocks(d):
    """{page under docs/guide/: its data block}: each page gets only what its tables use."""
    t = d['t']
    tables = lambda *names: {n: t[n] for n in names}
    real = lambda n: n[0] if isinstance(n, list) else n
    return {
        'index.html': {'wn': [r['n'] for r in d['roster']], 'atk': d['atk'], 'choice': {k: d['choice'][k] for k in ('style', 'rev')},
                       't': tables('save_files', 'size', 'critical', 'styles', 'breath', 'skills', 'layouts', 'settings_rows',
                                   'rings', 'venues', 'referees', 'music', 'victory_road')},
        'story/index.html': {'wslugs': sorted(slug(real(r['n'])) for r in d['roster']), 't': tables('story')},
        'wrestlers/index.html': {'roster': d['roster'], 'moves': [{**m, 'l': m['l'][:1]} for m in d['moves']], 'lists': [{'t': x['t']} for x in d['lists']],
                                 **{k: d[k] for k in ('slots', 'groups', 'seLabels', 'pa', 'ai', 'atk', 'def', 'choice')},
                                 't': tables('promotions', 'teams')},
        'create/index.html': {**{k: d[k] for k in ('lists', 'slots', 'pa', 'atk', 'def')}, 't': tables('skill_costs', 'affinity', 'cpu_logic', 'skills'),
                              'moves': move_users(d), 'wrestlers': [r['n'] for r in d['roster']]},
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0], epilog=paths.FOLDER_HELP,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--check', action='store_true', help='only check that the page is up to date')
    args = ap.parse_args(paths.configure(sys.argv[1:] if argv is None else argv))
    pages = {paths.DOCS / 'guide' / k: v for k, v in page_blocks(build()).items()}
    gone = [paths.show(p) for p in pages if not p.exists()]
    if gone:
        sys.exit(f'{", ".join(gone)}: not there yet - run private/work/guide/page/assemble.py first')
    pairs = fpztext.prose_names()
    for p, data in pages.items():      # the names in the prose, for the Names switch
        data['names'] = {k: pairs[int(k)] for k in sorted(set(re.findall(r'class="nm" data-k="(\d+)"', p.read_text(encoding='utf-8'))), key=int)}
    if all([pagedata.write(p, data, args.check) for p, data in pages.items()]) and args.check:
        print('docs/guide/: all four pages up to date')
    return 0


if __name__ == '__main__':
    sys.exit(main())
