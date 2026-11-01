#!/usr/bin/env python3
"""Story mode reference: the match table and the route map's data, from the scene scripts.

  storymap.py            write docs/story_matches.csv, the match tables in docs/STORY.md and the data
                         block of docs/guide/story/index.html (its Route Map)
  storymap.py --check    exit 1 if either is out of date (tools/check.py)
  storymap.py --json F   also dump the route map's data, indented, for inspection

The page's data carries both name sets: a string that differs is {"~": [real, parody]} (routemap.js
picks by the guide's Names switch). The script's names are resolved as the parody build does, so names
the story keeps real in both builds stay real; the hand-written titles and summaries go through
fpztext.swap_names.

Reads the scripts as players get them (tools/storyflow.py walks every path), the English story text
(translation/script/story0N.txt, real names) and the scene titles and summaries in
docs/story_scenes.csv (scenario, label, title, summary - written by hand from the script).

Per scenario the data holds every scene: title, summary, the English lines with speakers, the
matches played (card: sides, rules), the choices (caption, target), the exits with their
conditions (score checks, match results) and the score each path adds. The scenario's start
is the first entry of its developer chapter menu (<name>000), which normal play never shows.
"""
import csv
import io
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fpz  # noqa: E402
import fpztext  # noqa: E402
import paths  # noqa: E402
import storyflow  # noqa: E402

DOCS = paths.ROOT / 'docs'
SCENES_CSV = DOCS / 'story_scenes.csv'
MATCHES_CSV = DOCS / 'story_matches.csv'
PAGE = DOCS / 'guide' / 'story' / 'index.html'
STORY_MD = DOCS / 'STORY.md'
DATA_START = '<script type="application/json" id="story-data">'
DATA_END = '</script>'

SCENARIOS = {1: 'Mitsuharu Misawa', 2: 'Atsushi Onita', 3: 'Shinya Hashimoto', 4: 'Masahiro Chono',
             5: 'Keiji Mutoh', 6: 'Kazushi Sakuraba', 7: 'Jushin Thunder Liger'}
RULES = {'時間無制限　1本勝負': 'No Time Limit, One Fall',
         '時間無制限　バトルロイヤル': 'No Time Limit, Battle Royal'}
# card names the codes print short: Ｓ + Tiger Mask is Super Tiger, %sa0 the story's Guerrero
CARD_FIX = {'ＳTiger Mask': 'Super Tiger', 'Guerrero': 'Chavo Guerrero',
            'ＳMask de Panther': 'Super Panther', 'Nevelo': 'Hab Nevelo'}
# A match record of the .STO (a count at header +0x10, then 44 bytes each): what the guide's tables show
MATCH_RECORD = 44
SETTINGS = {'rule': 0x1E, 'rule2': 0x20, 'minutes': 0x21, 'venue': 0x23, 'ring': 0x24, 'com': 0x25,
            'referee': 0x26, 'critical': 0x29}


class Names:
    """The English for %ss/%sf/%sl/%sa codes and <tokens>, in the real names or the parody ones."""

    def __init__(self, version='real'):
        self.pre = 'en_' if version == 'real' else 'parody_'
        self.w = {int(r['idx']): r for r in fpztext.read_table('wrestlers.csv')}
        self.tok = ({r['token']: r['real'] for r in fpztext.read_table('name_tokens.csv')} if version == 'real'
                    else {t: p for t, (_, p) in fpztext.name_tokens().items()})
        self.story = {r['id']: self.tokens(r['english']) for r in fpztext.read_table('story_names.csv')}
        self.cards = {r['japanese']: self.tokens(r['english'])
                      for r in fpztext.read_table('story_cards.csv') if r.get('english')}
        self.speakers = {r['japanese']: self.tokens(r['english'])
                         for r in fpztext.read_table('speakers.csv') if r.get('english')}

    def tokens(self, s):
        return re.sub(r'<([^>]+)>', lambda m: self.tok.get(m.group(1), m.group(1)), s)

    def full(self, i):
        r = self.w.get(i)
        return fpztext._full(r, self.pre) if r else f'#{i}'

    def code(self, kind, i, n):
        if kind == 'a':
            return self.story.get(f'{n}:{i}', f'?{i}')
        r = self.w.get(i)
        if r is None:
            return f'#{i}'
        return {'s': r[self.pre + 'name1'], 'f': self.full(i), 'l': r[self.pre + 'name2'] or r[self.pre + 'name1']}[kind]

    def text(self, s, n):
        s = self.tokens(fpztext.unesc(s))
        s = re.sub(r'%s([sfla])(\d+)', lambda m: self.code(m.group(1), int(m.group(2)), n), s)
        return re.sub(r'%[a-z]\w*', '', s).strip()


def english(n, names):
    """{block id: (speaker, English)} of story0N.txt."""
    out = {}
    path = paths.TRANSLATION / 'script' / f'story0{n}.txt'
    for b in path.read_text(encoding='utf-8').split('\n@ ')[1:]:
        lines = b.split('\n')
        sp = next((ln[11:] for ln in lines if ln.startswith('# speaker: ')), '')
        m = re.search(r'\((%s[sfl]\d+)\)', sp)
        sp = names.text(m.group(1), n) if m else names.speakers.get(sp.strip(), sp.strip())
        out[lines[0].strip()] = (sp, names.text(' '.join(ln[3:] for ln in lines if ln.startswith('EN ')), n))
    return out


def card(n, txt, names, hero):
    """(hero side, opponents, rules) from a match card's text."""
    sides = []
    for x, body in re.findall(r'%px(\d+)%py\d+(?:%bx\S+?%by0x[0-9a-f]+)?([^\r\n]*)', txt):
        if not body or 'ＶＳ' in body or re.search('分|無制限', body):
            continue
        body = re.sub(r'%s([sa])(\d+)', lambda m: names.full(int(m.group(2))) if m.group(1) == 's'
                      else names.code('a', int(m.group(2)), n), body)
        body = body.replace('Ⅱ', ' II').replace('Ⅲ', ' III').replace('Ｊｒ．', ' Jr.').replace('Ｊｒ', ' Jr.')
        for jp, en in sorted(names.cards.items(), key=lambda kv: -len(kv[0])):
            body = body.replace(jp, en + ' ' if jp == 'キラー' else en)
        sides.append((int(x), CARD_FIX.get(body.strip(), body.strip())))
    if 'ＶＳ' not in txt:            # a battle royal lists everyone in one column
        left, right = [hero], [w for _, w in sides if w != hero]
    else:
        left, right = [w for x, w in sides if x < 320], [w for x, w in sides if x >= 320]
    rules = ''
    r = re.search(r'%py100([^%\r\n]+)', txt)
    if r:
        jp = r.group(1).translate(str.maketrans('０１２３４５６７８９', '0123456789'))
        m = re.fullmatch(r'(\d+)分　?1本勝負', jp)
        rules = f'{m.group(1)} Min. One Fall' if m else RULES.get(jp, jp)
    return ' & '.join(left) or hero, ' & '.join(right), rules


FLAGS = {(6, 31): 'mentor', (6, 32): 'followed'}     # scenario 6 keeps two choices in match slots 31, 32
FLAG_VALUES = {('mentor', 1): 'Minato', ('mentor', 2): 'Anjo', ('followed', 1): 'Takada',
               ('followed', 0): 'Orihara'}
NEGATE = {'<': '>=', '>': '<=', '==': '≠', '!=': '=', '<=': '>', '>=': '<'}


def condition(c, matches, n):
    """storyflow's condition text in words."""
    neg = c.startswith('not (')
    c = c[5:-1] if neg else c
    m = re.fullmatch(r'match(\d+) (==|!=) (-?\d+)', c)
    if m and (n, int(m.group(1))) in FLAGS:
        flag = FLAGS[n, int(m.group(1))]
        val = FLAG_VALUES.get((flag, int(m.group(3))), m.group(3))
        return f'{flag} {"is not" if neg != (m.group(2) == "!=") else "is"} {val}'
    m = re.fullmatch(r'result\(match (\d+)\) < 2', c)
    if m:
        vs = matches.get(int(m.group(1)), '')
        return f'{"lost" if neg else "won"} match {int(m.group(1)) + 1}' + (f' (vs. {vs})' if vs else '')
    m = re.fullmatch(r'(score|match(\d+)) (<=|>=|<|>|==|!=) (-?\d+)', c)
    if m and m.group(1) == 'score':
        op, v = m.group(3), int(m.group(4))
        if neg:
            op = NEGATE[op]
        return f'score {op} {v}'
    if m:
        return f'{"not " if neg else ""}match {m.group(2)} result {m.group(3)} {m.group(4)}'
    return ('not ' if neg else '') + c


def scenario_data(n, names, titles):
    s, scenes = storyflow.scenario(n)
    flow = {k: dict(zip(('messages', 'matches', 'choices', 'exits'), storyflow.summary(v['paths'])))
            for k, v in scenes.items()}
    eng = english(n, names)
    hero = SCENARIOS[n] if names.pre == 'en_' else fpztext.swap_names(SCENARIOS[n])
    menu = next(k for k in flow if k.endswith('000'))
    start = flow[menu]['choices'][0][0][0]
    order, seen, todo = [], set(), [start]
    while todo:                                   # story order: breadth first from the start
        k = todo.pop(0)
        if k in seen or k not in flow:
            continue
        seen.add(k)
        order.append(k)
        v = flow[k]
        todo += [lab for ch in v['choices'] for lab, _ in ch] + [x['to'] for x in v['exits'] if x['to']]
    order += [k for k in flow if k not in seen]
    rows, out = [], []
    match_vs = {}
    for k in order:
        v = flow[k]
        lines = []
        cards = []
        for m in v['messages']:
            raw = s.strings[m].decode('cp932', 'replace')
            if re.search(r'%py100(?!%bx)', raw) or 'ＶＳ' in raw:
                cards.append(raw)
                continue
            for bid in (b for b in eng if b.startswith(f'{n}.{m:03d}.')):
                sp, en = eng[bid]
                if en:
                    lines.append([sp, en])
        matches = []
        for mid in v['matches']:
            side, opp, rules = card(n, cards[0], names, hero) if cards else (hero, '', '')
            won = [x for x in v['exits'] if f'result(match {mid}) < 2' in x['when']]
            lost = [x for x in v['exits'] if f'not (result(match {mid}) < 2)' in x['when']]
            if not won and not lost:
                won = lost = v['exits'][:1]
            match_vs[mid] = opp
            rec = s.h[4] + 4 + mid * MATCH_RECORD
            matches.append({'match': mid, 'hero_side': side, 'opponents': opp, 'rules': rules,
                            'win': won[0]['to'] if won else '', 'lose': lost[0]['to'] if lost else '',
                            'win_score': won[0]['score'] if won else 0,
                            'lose_score': lost[0]['score'] if lost else 0,
                            **{f: s.data[rec + at] for f, at in SETTINGS.items()}})
        for mt in matches:
            rows.append({'scenario': n, 'scene': k, 'match': mt['match'], 'hero': hero,
                         **{f: mt[f] for f in ('hero_side', 'opponents', 'rules', 'win', 'lose', 'win_score',
                                               'lose_score', *SETTINGS)}})
        choices = []
        for ch in v['choices']:
            choices.append([{'to': lab, 'caption': names.text(eng.get(f'C{n}.{c:03d}', ('', ''))[1]
                                                              or s.strings[c].decode('cp932', 'replace'), n)}
                            for lab, c in ch])
        title, summary = titles.get((n, k), ('', ''))
        if names.pre != 'en_':
            title, summary = fpztext.swap_names(title), fpztext.swap_names(summary)
        out.append({'id': k, 'title': title, 'summary': summary, 'lines': lines, 'matches': matches,
                    'choices': choices, 'menu': k.startswith(menu),
                    'exits': [{'to': x['to'], 'when': x['when'], 'score': x['score']} for x in v['exits']]})
    for sc in out:                                # conditions in words, once every match is known
        for x in sc['exits']:
            x['when'] = [condition(c, match_vs, n) for c in x['when']]
    short = SCENARIOS[n].split()[-1]             # the map's chip
    if names.pre != 'en_':
        short = fpztext.swap_names(short)
    return {'hero': hero, 'short': short, 'start': start, 'menu': menu, 'scenes': out}, rows


def titles_table():
    out = {}
    if SCENES_CSV.exists():
        lines = [ln for ln in SCENES_CSV.read_text(encoding='utf-8').splitlines() if not ln.startswith('#')]
        for r in csv.DictReader(lines):
            out[(int(r['scenario']), r['label'])] = (r['title'], r['summary'])
    return out


def build():
    names = Names()
    titles = titles_table()
    data, rows = {}, []
    for n in SCENARIOS:
        data[n], r = scenario_data(n, names, titles)
        rows += r
    o = io.StringIO()
    w = csv.DictWriter(o, list(rows[0]), lineterminator='\n')
    w.writeheader()
    w.writerows(rows)
    table = ('# Story mode matches, from the scene scripts and match cards (tools/storymap.py; real names).\n'
             '# match: the game() number; win / lose: the scene each result leads to (the same scene = the\n'
             '# result only changes the score); win_score, lose_score: story score the script adds for each\n'
             '# result; rule ... critical: the match record\'s settings, as stored.\n' + o.getvalue())
    return merge(data, {n: scenario_data(n, Names('parody'), titles)[0] for n in SCENARIOS}), table, rows


def merge(a, b):
    """The real and parody data as one: every string that differs becomes {"~": [real, parody]}."""
    if isinstance(a, dict):
        return {k: merge(v, b[k]) for k, v in a.items()}
    if isinstance(a, list):
        return [merge(x, y) for x, y in zip(a, b, strict=True)]
    return {'~': [a, b]} if a != b else a


def story_with(rows):
    """docs/STORY.md with each scenario's match table rewritten between its markers."""
    if not STORY_MD.exists():
        return None
    text = STORY_MD.read_text(encoding='utf-8')
    for n in SCENARIOS:
        a, b = f'<!-- matches {n} -->', f'<!-- /matches {n} -->'
        if a not in text:
            continue
        out = ['**Matches** (in story order; win and loss points = what the scene adds for each result, before '
               'the match bonus)', '',
               '| Match | Scene | Your side | Opponents | Rules | Win -> | Lose -> | Win points | Loss points |',
               '|---|---|---|---|---|---|---|---|---|']
        for r in rows:
            if r['scenario'] != n:
                continue
            out.append(f"| {r['match']} | {r['scene']} | {r['hero_side']} | "
                       f"{r['opponents'] or '?'} | {r['rules']} | {r['win']} | {r['lose']} | "
                       f"{r['win_score'] or ''} | {r['lose_score'] or ''} |")
        i, j = text.index(a) + len(a), text.index(b)
        text = text[:i] + '\n' + '\n'.join(out) + '\n' + text[j:]
    return text


def page_with(data):
    if not PAGE.exists():
        return None
    page = PAGE.read_text(encoding='utf-8')
    if DATA_START not in page:
        sys.exit(f'{paths.show(PAGE)}: no story-data block. Put back {DATA_START}{DATA_END}')
    a = page.index(DATA_START) + len(DATA_START)
    b = page.index(DATA_END, a)
    blob = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    return page[:a] + blob + page[b:]


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in ('-h', '--help'):
        print(__doc__)
        return 0
    data, table, rows = build()
    page = page_with(data)
    story = story_with(rows)
    if '--check' in argv:
        stale = [p.name for p, new in ((MATCHES_CSV, table), (PAGE, page), (STORY_MD, story))
                 if new is not None and (not p.exists() or p.read_text(encoding='utf-8') != new)]
        if stale:
            print(f'out of date: {", ".join(stale)} - run python3 tools/storymap.py')
            return 1
        return 0
    MATCHES_CSV.write_text(table, encoding='utf-8')
    print(f'{MATCHES_CSV.relative_to(paths.ROOT)}: {table.count(chr(10)) - 5} matches')
    if story is not None:
        STORY_MD.write_text(story, encoding='utf-8')
    if page is not None:
        PAGE.write_text(page, encoding='utf-8')
        print(f'{PAGE.relative_to(paths.ROOT)}: {sum(len(d["scenes"]) for d in data.values())} scenes')
    if '--json' in argv:
        Path(argv[argv.index('--json') + 1]).write_text(json.dumps(data, ensure_ascii=False, indent=1),
                                                         encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
