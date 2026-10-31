#!/usr/bin/env python3
"""Story mode reference: the match table and the route map's data, from the scene scripts.

  storymap.py            write docs/story_matches.csv, the match tables in docs/STORY.md and the data
                         block of docs/route-map/index.html
  storymap.py --check    exit 1 if either is out of date (tools/check.py)
  storymap.py --json F   also dump the route map's data, indented, for inspection

Reads the original scripts (tools/storyflow.py walks every path), the English story text
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
PAGE = DOCS / 'route-map' / 'index.html'
STORY_MD = DOCS / 'STORY.md'
DATA_START = '<script type="application/json" id="story-data">'
DATA_END = '</script>'

SCENARIOS = {1: 'Mitsuharu Misawa', 2: 'Atsushi Onita', 3: 'Shinya Hashimoto', 4: 'Masahiro Chono',
             5: 'Keiji Mutoh', 6: 'Kazushi Sakuraba', 7: 'Jushin Thunder Liger'}
RULES = {'時間無制限　1本勝負': 'No Time Limit, One Fall',
         '時間無制限　バトルロイヤル': 'No Time Limit, Battle Royal'}
# Scenario 7 plays no matches: a card "試合（ＶＳname）" and a Win / Lose choice
LIGER = {'藤原': 'Fujiwara', '佐野': 'Sano', '武藤': 'Mutoh', 'マーク・ロコ': 'Mark Rocco',
         '小林邦明': 'Kuniaki Kobayashi', '馳浩': 'Hiroshi Hase', 'ワイルドペガサス': 'Wild Pegasus',
         '大谷晋二郎': 'Shinjiro Otani', '佐野直喜': 'Naoki Sano', 'グレート・ムタ': 'The Great Muta',
         'アントニオ猪木': 'Antonio Inoki', '金丸義信': 'Yoshinobu Kanemaru', '三沢光晴': 'Mitsuharu Misawa',
         '蝶野': 'Chono', '前田＜スパーリングマッチ＞': 'Maeda (sparring match)',
         '藤原嘉明': 'Yoshiaki Fujiwara', '佐竹': 'Satake', 'カレリン': 'Karelin',
         '前田２': 'Maeda (retirement match)', 'ミルコ': 'Mirko', 'ヒクソン': 'Rickson', '高田': 'Takada',
         '橋本': 'Hashimoto', 'ルッテン': 'Rutten', '': ''}
NOTES = {'lyger_gm012': 'the card leaves the name blank; the story makes it Naoya Ogawa',
         'lyger_gm410': 'the card leaves the name blank; the story makes it Masakatsu Funaki',
         'lyger_gm014': 'the card says Kanemaru, but the story and the chapter menu say Marufuji'}
# card names the codes print short: Ｓ + Tiger Mask is Super Tiger, %sa0 the story's Guerrero
CARD_FIX = {'ＳTiger Mask': 'Super Tiger', 'Guerrero': 'Chavo Guerrero'}
WIN, LOSE = '勝ち'.encode('cp932'), '負け'.encode('cp932')


class Names:
    """The real-name English for %ss/%sf/%sl/%sa codes and <tokens>."""

    def __init__(self):
        self.w = {int(r['idx']): r for r in fpztext.read_table('wrestlers.csv')}
        self.tok = {r['token']: r['real'] for r in fpztext.read_table('name_tokens.csv')}
        self.story = {r['id']: self.tokens(r['english']) for r in fpztext.read_table('story_names.csv')}
        self.cards = {r['japanese']: self.tokens(r['english'])
                      for r in fpztext.read_table('story_cards.csv') if r.get('english')}
        self.speakers = {r['japanese']: self.tokens(r['english'])
                         for r in fpztext.read_table('speakers.csv') if r.get('english')}

    def tokens(self, s):
        return re.sub(r'<([^>]+)>', lambda m: self.tok.get(m.group(1), m.group(1)), s)

    def full(self, i):
        r = self.w.get(i)
        return fpztext._full(r, 'en_') if r else f'#{i}'

    def code(self, kind, i, n):
        if kind == 'a':
            return self.story.get(f'{n}:{i}', f'?{i}')
        r = self.w.get(i)
        if r is None:
            return f'#{i}'
        return {'s': r['en_name1'], 'f': self.full(i), 'l': r['en_name2'] or r['en_name1']}[kind]

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
        return f'{"lost" if neg else "won"} match {m.group(1)}' + (f' (vs. {vs})' if vs else '')
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
    hero = SCENARIOS[n]
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
        if n == 7 and cards:
            opp = re.sub(r'(?s).*ＶＳ　?', '', cards[0]).split('）')[0].strip('　')
            ch = v['choices'][0] if v['choices'] else []
            res = {s.strings[c]: lab for lab, c in ch}
            matches.append({'match': None, 'hero_side': hero, 'opponents': LIGER.get(opp, opp),
                            'rules': '(not played: you pick Win or Lose)',
                            'win': res.get(WIN, ''), 'lose': res.get(LOSE, ''), 'win_score': None})
        for mid in v['matches']:
            side, opp, rules = card(n, cards[0], names, hero) if cards else (hero, '', '')
            won = [x for x in v['exits'] if f'result(match {mid}) < 2' in x['when']]
            lost = [x for x in v['exits'] if f'not (result(match {mid}) < 2)' in x['when']]
            if not won and not lost:
                won = lost = v['exits'][:1]
            match_vs[mid] = opp
            matches.append({'match': mid, 'hero_side': side, 'opponents': opp, 'rules': rules,
                            'win': won[0]['to'] if won else '', 'lose': lost[0]['to'] if lost else '',
                            'win_score': won[0]['score'] if won else 0})
        for mt in matches:
            mt['notes'] = NOTES.get(k, '')
            rows.append({'scenario': n, 'scene': k, 'match': '' if mt['match'] is None else mt['match'],
                         'hero': hero, **{f: mt[f] for f in ('hero_side', 'opponents', 'rules', 'win', 'lose')},
                         'win_score': '' if mt['win_score'] is None else mt['win_score'], 'notes': mt['notes']})
        choices = []
        for ch in v['choices']:
            choices.append([{'to': lab, 'caption': names.text(eng.get(f'C{n}.{c:03d}', ('', ''))[1]
                                                              or s.strings[c].decode('cp932', 'replace'), n)}
                            for lab, c in ch])
        title, summary = titles.get((n, k), ('', ''))
        out.append({'id': k, 'title': title, 'summary': summary, 'lines': lines, 'matches': matches,
                    'choices': choices, 'menu': k.startswith(menu),
                    'exits': [{'to': x['to'], 'when': x['when'], 'score': x['score']} for x in v['exits']]})
    for sc in out:                                # conditions in words, once every match is known
        for x in sc['exits']:
            x['when'] = [condition(c, match_vs, n) for c in x['when']]
    return {'hero': hero, 'start': start, 'menu': menu, 'scenes': out}, rows


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
             '# match: the game() number (empty in scenario 7, where you pick Win or Lose); win / lose: the\n'
             '# scene each result leads to (the same scene = the result only changes the score); win_score:\n'
             '# story score the script adds for a win.\n' + o.getvalue())
    return data, table, rows


def story_with(rows):
    """docs/STORY.md with each scenario's match table rewritten between its markers."""
    if not STORY_MD.exists():
        return None
    text = STORY_MD.read_text(encoding='utf-8')
    for n in SCENARIOS:
        a, b = f'<!-- matches {n} -->', f'<!-- /matches {n} -->'
        if a not in text:
            continue
        out = ['**Matches** (in story order; win points = what the scene adds for a win, before the match bonus)', '',
               '| Match | Scene | Your side | Opponents | Rules | Win -> | Lose -> | Win points |',
               '|---|---|---|---|---|---|---|---|']
        for r in rows:
            if r['scenario'] != n:
                continue
            note = f" ({r['notes']})" if r['notes'] else ''
            out.append(f"| {r['match'] if r['match'] != '' else '-'} | {r['scene']} | {r['hero_side']} | "
                       f"{r['opponents'] or '?'}{note} | {r['rules']} | {r['win']} | {r['lose']} | "
                       f"{r['win_score'] if r['win_score'] not in ('', 0) else ''} |")
        i, j = text.index(a) + len(a), text.index(b)
        text = text[:i] + '\n' + '\n'.join(out) + '\n' + text[j:]
    return text


def page_with(data):
    if not PAGE.exists():
        return None
    page = PAGE.read_text(encoding='utf-8')
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
