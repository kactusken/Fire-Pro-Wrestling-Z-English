#!/usr/bin/env python3
"""Fire Pro Wrestling Z text: dump the game's text into translation/, and the build steps that put
the English back (docs/TECHNICAL.md has the formats, docs/TRANSLATION.md the conventions).

  fpztext.py dump [story|roster|moves|ui|all]   (re)write the translation files from extracted/
                                             (keeps the English and hand comments)
  fpztext.py show STORY_ID [parody]          one story page: JP, and the English as the window
                                             shows it (names filled in, wrapped)

Story (translation/script/storyNN.txt, one block per page): the build keeps each page's codes,
speaker line and script lines from the original and puts the English text lines in their place,
word-wrapped to the story window (20 cells a line, 4 lines with the speaker) and encoded as pair
glyphs (two letters a cell - tools/fpzfont.py). Literal speaker labels (記者：) are translated in
translation/text/speakers.csv; %ssN is roster N's short name and needs nothing.
"""
import csv
import io
import os
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blocks  # noqa: E402
import fpz  # noqa: E402
import ligerstory  # noqa: E402
import paths  # noqa: E402
import storycolours  # noqa: E402
import storywrestlers  # noqa: E402

ENC = 'cp932'
STORY_FILES = [f'SCENA\\STORY0{i}.STO' for i in range(1, 8)]
JP = re.compile(r'[぀-ヿ㐀-䶿一-鿿＀-￯　-〿]')
CODE = re.compile(r'#x[0-9A-Fa-f]{2}|%(?:ss\d+|sf\d+|sl\d+|sa\d+|sw\d+|st|sk|s|k2|k|c\d|px\d+|py\d+|bx0x[0-9a-fA-F]+|by0x[0-9a-fA-F]+|m\d|w\d+|t\d)')
CELLS_PER_LINE = 20
LINES_PER_PAGE = 4          # the speaker line counts


def dec(b):
    return b.decode(ENC)


def nfkc(s):
    return unicodedata.normalize('NFKC', s)


# ---------------------------------------------------------------- the story

class Page:
    """One page of a story message: lines (str) between two %k codes. kind: speaker index, text
    line indexes; the rest of the lines (codes, script commands) stay as they are."""

    def __init__(self, raw):
        self.raw = raw
        self.lines = raw.split('\r\n')
        self.speaker = None
        self.text = []
        for i, ln in enumerate(self.lines):
            bare = CODE.sub('', ln)
            if not bare.strip() or ln.startswith('\t'):
                continue
            if self.speaker is None and not self.text and re.fullmatch(r'(?:%c\d)*(?:%ss\d+|[^「」『』、。\s]{1,10})：', ln):
                self.speaker = i
                continue
            self.text.append(i)
        if self.text and self.text != list(range(self.text[0], self.text[-1] + 1)):
            # text split by other lines: treat everything from the first to the last text line as text
            self.text = list(range(self.text[0], self.text[-1] + 1))

    def jp_lines(self):
        return [self.lines[i] for i in self.text]

    def speaker_label(self):
        if self.speaker is None:
            return None
        m = re.fullmatch(r'((?:%c\d)*)(.+)：', self.lines[self.speaker])
        return m.group(1), m.group(2)


def split_pages(s):
    """[(page text, terminator)]: a message split at its %k / %k2 codes."""
    parts = re.split(r'(%k2?)', s)
    out = []
    for i in range(0, len(parts), 2):
        out.append((parts[i], parts[i + 1] if i + 1 < len(parts) else ''))
    return out


def story_kind(s):
    if not JP.search(s):
        return None
    if '%px' in s:
        return 'card'
    if '%k' in s or '\r\n' in s.strip():
        return 'dialog'
    return 'line'


# ---------------------------------------------------------------- story layout (lint and build)

NAME_CELLS_UNKNOWN = 8      # a %ssN whose English name isn't known yet
_NAME_CELLS = None


def name_cells():
    """{(code, roster index): cells the name takes in the story} - the longer of the two name sets.
    Names are pair glyphs too: two letters a cell. ss = short name, sl = the other part, sf = full."""
    global _NAME_CELLS
    if _NAME_CELLS is None:
        _NAME_CELLS = {}
        for r in read_table('wrestlers.csv'):
            i = int(r['idx'])
            for code, f in (('ss', lambda p: r.get(p + 'name1') or ''), ('sl', lambda p: r.get(p + 'name2') or ''),
                            ('sf', lambda p: _full(r, p))):
                w = max(len(f('en_')), len(f('parody_') if r.get('parody_name1') else f('en_')))
                _NAME_CELLS[code, i] = (w + 1) // 2 + 1 if w else NAME_CELLS_UNKNOWN
    return _NAME_CELLS


def line_cells(line):
    """Cells a story line takes: plain text two characters a cell (per run between names), a name
    one cell a letter, other codes nothing."""
    n = 0
    for part in re.split(r'(%s[sfl]\d+)', line):
        if re.fullmatch(r'%s[sfl]\d+', part):
            n += name_cells().get((part[1:3], int(part[3:])), NAME_CELLS_UNKNOWN)
        else:
            plain = CODE.sub('', part)
            n += (len(plain) + 1) // 2
    return n


def wrap(lines, width=CELLS_PER_LINE):
    """The translator's lines word-wrapped to the story window."""
    out = []
    for ln in lines:
        cur = ''
        for word in ln.split(' '):
            trial = word if not cur else cur + ' ' + word
            if line_cells(trial) <= width or not cur:
                cur = trial
            else:
                out.append(cur)
                cur = word
        out.append(cur)
    return out


def check_story(e):
    """lint: [(severity, kind, message)] for a story entry - the page must fit the window."""
    if not e.english or not re.match(r'script/story\d+\.txt', f'{e.file.parent.name}/{e.file.name}'):
        return []
    lines = e.english.split('\n')
    if e.key.startswith('C'):
        w = max(line_cells(ln) for ln in lines)
        if len(lines) > 1 or w > CELLS_PER_LINE:
            return [('error', 'room', f'a choice is one line of {CELLS_PER_LINE * 2} characters')]
        return []
    room = LINES_PER_PAGE - (1 if '# speaker:' in (e.notes or '') else 0)
    wrapped = wrap(lines)
    if len(wrapped) > room:
        return [('error', 'room', f'{len(wrapped)} lines after wrapping, the page holds {room} '
                 f'(40 characters a line; split the page or shorten): {wrapped!r}')]
    for ln in wrapped:
        if line_cells(ln) > CELLS_PER_LINE:
            return [('error', 'room', f'a word too long for a line: {ln!r}')]
    return []


# ---------------------------------------------------------------- name tokens (two name sets)

TOKEN = re.compile(r'<([A-Za-z0-9][^<>]*)>')


def _full(r, pre):
    n1, n2 = r.get(pre + 'name1', ''), r.get(pre + 'name2', '')
    parts = [n2, n1] if (r.get(pre + 'order') or '1-2') == '2-1' else [n1, n2]
    return ' '.join(x for x in parts if x)


_TOKENS = None


def name_tokens():
    """{token: (real, parody)}: every wrestler's parody short and full name (wrestlers.csv), and
    translation/text/name_tokens.csv (token, real, parody - empty parody = the token itself)."""
    global _TOKENS
    if _TOKENS is None:
        out = {}
        for r in read_table('wrestlers.csv'):
            if r.get('parody_name1') and r.get('en_name1'):
                out.setdefault(r['parody_name1'], (r['en_name1'], r['parody_name1']))
                out.setdefault(_full(r, 'parody_'), (_full(r, 'en_'), _full(r, 'parody_')))
        for r in read_table('name_tokens.csv'):
            out[r['token']] = (r['real'], r.get('parody') or r['token'].rstrip('*'))
        _TOKENS = out
    return _TOKENS


def resolve(text, names, where=''):
    """`text` with every <Token> replaced by its real (names='real') or parody name."""
    tokens = name_tokens()

    def sub(m):
        if m.group(1) not in tokens:
            sys.exit(f'{where}: unknown name token <{m.group(1)}> (wrestlers.csv parody names, name_tokens.csv)')
        return tokens[m.group(1)][0 if names == 'real' else 1]
    return TOKEN.sub(sub, text)


def roster_short():
    data = (paths.EXTRACTED / 'STRHUMAN.BIN').read_bytes()
    return [dec(f['name1']) for _, f in fpz.roster(data)]


def story_archive():
    return fpz.Oah((paths.EXTRACTED / 'STORY.OAH').read_bytes())


STORY_HEADER = '''# Story mode, scenario {n} (STORY.OAH SCENA\\STORY0{n}.STO). One block per page; ids are
# story.message.page. Only the text lines are here: the build keeps each page's speaker and codes,
# puts in the English, word-wraps it and encodes it for the story window.
# Room: 20 cells a line, 4 lines a page counting the speaker line (so 3 text lines with a speaker,
# 4 without). English is drawn two letters a cell: about 40 characters a line, 120 a page with a
# speaker. %ssN is wrestler N's short name (roster), drawn one cell a letter. Write plain lines;
# your line breaks are kept where they fit, and long lines are wrapped.
# Codes: %ssN name (keep), %c0 / %c1 colour (keep where they are), %sw/%st/%sk match results.
# Speaker labels that are words (記者 Reporter) are in translation/text/speakers.csv.
# Choices and chapter titles (ids C...) are one line each: 40 characters at most.
'''


def dump_story():
    a = story_archive()
    names = roster_short()
    speakers = {}
    cards = {}
    for n, fname in enumerate(STORY_FILES, 1):
        s = fpz.Sto(ligerstory.paged(a.read(fname)) if n == 7 else a.read(fname))
        items = []
        seen = set()
        for i, raw in enumerate(s.strings):
            text = dec(raw)
            kind = story_kind(text)
            off = s.offsets[i]
            if kind is None or off in seen:
                continue
            seen.add(off)
            if kind == 'card':
                for ln in text.split('\r\n'):
                    seg = re.sub(r'%(?:px|py)\d+|%(?:bx|by)0x[0-9a-fA-F]+', '', ln)
                    for piece in re.split(r'%[a-z]+\d*|　', seg):
                        if JP.search(piece) and re.search(r'[^　-〿＀-￯]|[ァ-ヿ]', piece):
                            cards[piece] = cards.get(piece, 0) + 1
                continue
            if kind == 'line':
                items.append((f'C{n}.{i:03d}', '', [text], ['# choice or chapter title']))
                continue
            for p, (page, term) in enumerate(split_pages(text)):
                pg = Page(page)
                if not pg.text:
                    continue
                lab = pg.speaker_label()
                head = []
                if lab:
                    m = re.fullmatch(r'%ss(\d+)', lab[1])
                    if m:
                        head = [f'# speaker: {names[int(m.group(1))]} (%ss{m.group(1)})']
                    else:
                        head = [f'# speaker: {lab[1]}']
                        speakers[lab[1]] = speakers.get(lab[1], 0) + 1
                items.append((f'{n}.{i:03d}.{p:02d}', '', pg.jp_lines(), head))
        path = paths.SCRIPT / f'story{n:02d}.txt'
        path.parent.mkdir(parents=True, exist_ok=True)
        blocks.merge(path, STORY_HEADER.format(n=n).rstrip('\n').split('\n'), items, quiet=True)
        print(f'{path.name}: written')
    write_table('story_names.csv', [
        'Story-only wrestler names (the last section of each STORY0N.STO): 15 bytes each, printable',
        'ASCII. id = story file : record.'],
        ['id', 'japanese', 'english', 'notes'],
        [{'id': f'{n}:{k}', 'japanese': dec(x.split(b'\0')[0])}
         for n, fname in enumerate(STORY_FILES, 1) for k, x in enumerate(fpz.Sto(a.read(fname)).names)], key='id')
    write_table('speakers.csv', [
        'Speaker labels in the story that are words, not a wrestler code (記者： Reporter). The build',
        'adds the colon. Real people the story names (猪木, 長州...) stay their real names in both builds.'],
        ['japanese', 'uses', 'english', 'notes'],
        [{'japanese': k, 'uses': v} for k, v in sorted(speakers.items(), key=lambda x: -x[1])], key='japanese')
    write_table('story_cards.csv', [
        'Text on the story\'s match cards and result screens (positioned, drawn large): 試合結果, the',
        'match type and time. Keep it about as short as the Japanese.'],
        ['japanese', 'uses', 'english', 'notes'],
        [{'japanese': k, 'uses': v} for k, v in sorted(cards.items(), key=lambda x: -x[1])], key='japanese')


# ---------------------------------------------------------------- tables

def read_table(name):
    p = paths.TEXT / name
    if not p.exists():
        return []
    lines = p.read_text(encoding='utf-8').splitlines(keepends=True)
    head = next((i for i, ln in enumerate(lines) if not ln.startswith('#')), len(lines))
    return list(csv.DictReader(lines[head:]))


def write_table(name, comment, fields, rows, key):
    """Write translation/text/NAME: the comment lines, then the rows; columns not in `rows` are
    taken from the existing file's row with the same key (English and notes are kept)."""
    old = {r[key]: r for r in read_table(name)}
    buf = io.StringIO()
    for c in comment:
        buf.write(f'# {c}\n')
    w = csv.DictWriter(buf, fieldnames=fields, lineterminator='\n')
    w.writeheader()
    for r in rows:
        prev = old.get(str(r[key]), {})
        w.writerow({f: r.get(f, prev.get(f, '')) if r.get(f, '') != '' else prev.get(f, r.get(f, '')) for f in fields})
    p = paths.TEXT / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(buf.getvalue(), encoding='utf-8', newline='\n')
    print(f'{name}: {len(rows)} rows')


# ---------------------------------------------------------------- roster and moves

ROSTER_COMMENT = [
    'The roster: 244 wrestlers (STRHUMAN.BIN, 0x23C-byte records). Fields: name1 13 bytes (the short',
    'name the game shows alone, and in the story for %ssN), name2 19 bytes, nick 25 bytes. flags: bit 7',
    '= name2 comes first in the full name, bits 0-1 = the separator (0 a space, 1 "・", 2 "=", 3 none).',
    'Two English versions of every name: en_* the real wrestler (default build), parody_* the game\'s',
    'own name romanized (build.py --names parody). *_order: 1-2 (name1 name2) or 2-1 (name2 name1),',
    'joined with a space; empty = 1-2. jp_full: the name as the game shows it. Nicknames: en_nick in',
    'the real build, parody_nick in the parody build (empty = en_nick). Printable ASCII only.',
]
ROSTER_FIELDS = ['idx', 'flags', 'name1', 'name2', 'nick', 'jp_full', 'en_name1', 'en_name2', 'en_order',
                 'parody_name1', 'parody_name2', 'parody_order', 'en_nick', 'parody_nick', 'notes']
SEPARATORS = (' ', '・', '=', '')


def jp_full(flags, n1, n2):
    if not n2:
        return n1
    a, b = (n2, n1) if flags & 0x80 else (n1, n2)
    return a + SEPARATORS[flags & 3] + b


def dump_roster():
    data = (paths.EXTRACTED / 'STRHUMAN.BIN').read_bytes()
    rows = []
    for i, (fl, f) in enumerate(fpz.roster(data)):
        n1, n2, nick = dec(f['name1']), dec(f['name2']), dec(f['nick'])
        rows.append({'idx': i, 'flags': f'0x{fl:02x}', 'name1': n1, 'name2': n2, 'nick': nick,
                     'jp_full': jp_full(fl, n1, n2)})
    write_table('wrestlers.csv', ROSTER_COMMENT, ROSTER_FIELDS, rows, key='idx')


MOVES_COMMENT = [
    'Move names (WAZA.BIN: u16 offsets by move id, then the names). The build rebuilds the file; its',
    'size can\'t grow past the original (34048 bytes - repeated names are stored once). Move lists on',
    'screen are narrow: keep about the Japanese width (a kana or kanji = 2 letters). Printable ASCII.',
    '(予約) = reserved, unused slots: no translation needed.',
]


def dump_moves():
    w = fpz.moves((paths.EXTRACTED / 'WAZA.BIN').read_bytes())
    rows = [{'index': i, 'japanese': dec(nm)} for i, nm in enumerate(w)]
    write_table('moves.csv', MOVES_COMMENT, ['index', 'japanese', 'english', 'notes'], rows, key='index')


# ---------------------------------------------------------------- the executable

EXE = 'SLPM_623.42'
EXE_BASE = 0xFF000                     # RAM address = file offset + EXE_BASE (.data .. .sdata)
DATA_FILE = (0x114E80, 0x2AE080)       # file range of .data .. .sdata
TEXT_FILE = (0x1000, 0x1000 + 0x10DAD8)
POOLS = [(0x2950C0, 0x295840), (0x299060, 0x2A1910), (0x2A3AE0, 0x2A75A0), (0x2AB200, 0x2ADA00)]
CHAR_TABLE = 0x214AE0                  # 256 pointers: single-byte character -> full-width string
GP = 0x3B1CF0                          # $gp (set at the entry, 0x10005C): .sdata is reached as gp + imm


# Pairs the straight-line scan in exe_refs can't see: the lui is in a branch's delay slot, so another
# write to the register comes between them in the file (private/work/strayrefs.py follows the
# branches and found no others). Overwrite? in Quick Save and the Edit Data screens: play-test 2026-10-30.
BRANCHED_REFS = {0x39A480: [(0x147B58, 0x147BB4), (0x148724, 0x148780)]}


def exe_refs(d):
    """({address: [data word offsets]}, {address: [(lui offset, low offset)]}) for every word in
    .data-.sdata and every lui/addiu|ori pair in .text that gives an address in the data sections."""
    import struct
    lo, hi_end = DATA_FILE[0] + EXE_BASE, DATA_FILE[1] + EXE_BASE
    data = {}
    for o in range(DATA_FILE[0], DATA_FILE[1], 4):
        v = struct.unpack_from('<I', d, o)[0]
        if lo <= v < hi_end:
            data.setdefault(v, []).append(o)
    code, hi = {}, {}
    for o in range(*TEXT_FILE, 4):
        w = struct.unpack_from('<I', d, o)[0]
        op = w >> 26
        if op == 0x09 and (w >> 21) & 31 == 28:            # addiu rt, $gp, imm
            imm = w & 0xFFFF
            v = GP + (imm - 0x10000 if imm & 0x8000 else imm)
            if lo <= v < hi_end:
                code.setdefault(v, []).append((None, o))
        elif op in (0x09, 0x0D) and ((w >> 21) & 31) in hi:
            base, at = hi[(w >> 21) & 31]
            if o - at <= 1024 * 4:                          # a lui before, register untouched since
                imm = w & 0xFFFF
                v = (base + (imm - 0x10000 if op == 0x09 and imm & 0x8000 else imm)) & 0xFFFFFFFF
                if lo <= v < hi_end:
                    code.setdefault(v, []).append((at, o))
        # what this instruction writes ends any lui pairing on that register
        if op == 0x0F:
            hi[(w >> 16) & 31] = ((w & 0xFFFF) << 16, o)
            continue
        if w == 0x03E00008:                                  # jr $ra: a function ends
            hi.clear()
            continue
        if op == 0x00:
            hi.pop((w >> 11) & 31, None)
        elif op in (0x03,):                                  # jal writes $ra
            hi.pop(31, None)
        elif 0x08 <= op <= 0x0E or 0x18 <= op <= 0x1B or 0x20 <= op <= 0x27 or op in (0x1E, 0x37):
            hi.pop((w >> 16) & 31, None)
        elif op == 0x1C:                                     # MMI: rd
            hi.pop((w >> 11) & 31, None)
    for addr, pairs in BRANCHED_REFS.items():
        code.setdefault(addr, []).extend((lui - EXE_BASE, low - EXE_BASE) for lui, low in pairs)
    return data, code


def _string_len(d, o):
    i = o
    while d[i]:
        b = d[i]
        if 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xFC:
            if not 0x40 <= d[i + 1] <= 0xFC:
                return None
            i += 2
        elif 0x20 <= b < 0x7F or 0xA1 <= b <= 0xDF or b in (0x0A, 0x0D, 0x09):
            i += 1
        else:
            return None
    return i - o


# ASCII-only strings the game shows (seen on screen or next to shown text): without Japanese the
# dump would skip them, and the game would draw them in its own wide full-width letters ("S P I K E
# D O M E" - owner play-test 2026-10-29). The rest of the pools' ASCII is file names, internal
# labels and debug output: not text.
ASCII_SHOWN = {
    0x394110, 0x394120, 0x394130, 0x394160, 0x394190,             # promotion names
    0x3941B8, 0x3941C8, 0x3941D8, 0x3941F0, 0x394218, 0x394230, 0x394240, 0x394258, 0x394268,
    0x394278, 0x394290, 0x3942A8, 0x3942B8, 0x39BB08, 0x39BB80,   # music titles
    0x39F630,                                                     # venue SPIKE DOME
    0x3A0868,                                                     # Data Error
    0x3AA808, 0x3AA810, 0x3AA820, 0x3AA830, 0x3AA838, 0x3AA840, 0x3AA850, 0x3AA868,  # rings
    0x3AA9B0, 0x3AA9B8, 0x3AAAF0, 0x3AAE90, 0x3AAEB0, 0x3AB670, 0x3AB718, 0x3AB728,
    0x3AB990, 0x3AB998, 0x3AC2E8, 0x3AC2F0, 0x3AC390, 0x3AC398, 0x3AC628,
}


def room_cap(d):
    """cap(o, n, end): `end` (where the zeros after the string at o, n bytes long, stop), held back
    to the first .sdata variable or empty string there. Variables are zero on disc and written at
    run time: GJ Army was packed against one, which overwrote its terminator (play-test 2026-10-30)."""
    import bisect
    import struct
    sizes = {0x20: 1, 0x24: 1, 0x28: 1, 0x21: 2, 0x25: 2, 0x29: 2, 0x23: 4, 0x2B: 4, 0x31: 4, 0x39: 4,
             0x1E: 8, 0x1F: 8, 0x37: 8, 0x3F: 8, 0x27: 8}        # gp-relative loads and stores
    variables = set()
    for o in range(*TEXT_FILE, 4):
        w = struct.unpack_from('<I', d, o)[0]
        if w >> 26 in sizes and (w >> 21) & 31 == 28:
            imm = w & 0xFFFF
            at = GP + (imm - 0x10000 if imm & 0x8000 else imm) - EXE_BASE
            variables.update(range(at, at + sizes[w >> 26]))
    # an empty string some pointer aims at is one zero byte too: Affinity was packed onto 0x3AB898,
    # the move editor's blank rows (play-test 2026-10-30)
    data, code = exe_refs(d)
    variables.update(a - EXE_BASE for a in set(data) | set(code)
                     if any(lo <= a - EXE_BASE < hi for lo, hi in POOLS) and not d[a - EXE_BASE])
    variables = sorted(variables)

    def cap(o, n, end):
        i = bisect.bisect_left(variables, o + n + 1)
        return min(end, variables[i]) if i < len(variables) else end
    return cap


def exe_strings(d=None):
    """[{addr, file offset, bytes, refs data/code, room}] for every Japanese string in the pools
    (and the ASCII ones in ASCII_SHOWN), except the character tables."""
    import struct
    d = d or (paths.EXTRACTED / EXE).read_bytes()
    data, code = exe_refs(d)
    skip = {struct.unpack_from('<I', d, CHAR_TABLE - EXE_BASE + 4 * i)[0] for i in range(256)}
    out = []
    cap = room_cap(d)
    for a, b in POOLS:
        o = a
        while o < b:
            if d[o] and not d[o - 1]:
                n = _string_len(d, o)
                if n:
                    addr = o + EXE_BASE
                    raw = bytes(d[o:o + n])
                    end = o + n + 1
                    while end < len(d) and not d[end]:
                        end += 1
                    floaty = n <= 4 and raw[-1:] in (b'9', b':', b';', b'<', b'=', b'>')   # a float's high bytes
                    shown = JP.search(raw.decode(ENC, 'replace')) or addr in ASCII_SHOWN
                    if shown and addr not in skip and not floaty:
                        out.append({'addr': addr, 'off': o, 'raw': raw, 'data': data.get(addr, []),
                                    'code': code.get(addr, []), 'room': cap(o, n, end) - o - 1})
                    o += n
                    continue
            o += 1
    # Strings the code points at that the pool scan misses: packed right after a pointer or other
    # data (no NUL before them: 試合開始, a 戻る), or outside the pools (the story's quick-save
    # prompts and result names at 0x3A65D0-). Real text only: two kana/kanji in a row.
    taken = [(s['off'], s['off'] + len(s['raw'])) for s in out if s['data'] or s['code']]
    for addr in sorted(set(data) | set(code)):
        o = addr - EXE_BASE
        if not (REF_TEXT[0] <= o < REF_TEXT[1]) or NAME_GRID[0] <= o < NAME_GRID[1] or addr in skip:
            continue
        if any(a <= o < b for a, b in taken):
            continue
        n = _string_len(d, o)
        raw = bytes(d[o:o + n]) if n else b''
        text = raw.decode(ENC, 'replace')
        if not n or not (REAL_TEXT.search(text) or SHORT_WORD.fullmatch(text)) \
                or any(ord(c) < 0x20 or c == '\ufffd' for c in text):
            continue
        end = o + n + 1
        while end < len(d) and not d[end]:
            end += 1
        out.append({'addr': addr, 'off': o, 'raw': raw, 'data': data.get(addr, []),
                    'code': code.get(addr, []), 'room': cap(o, n, end) - o - 1})
        taken.append((o, o + n))
    for addr in EXTRA_STRINGS:              # referenced strings outside REF_TEXT / with line breaks
        o = addr - EXE_BASE
        n = _string_len(d, o)
        if n and not any(x['addr'] == addr for x in out):
            end = o + n + 1
            while end < len(d) and not d[end]:
                end += 1
            out.append({'addr': addr, 'off': o, 'raw': bytes(d[o:o + n]), 'data': data.get(addr, []),
                        'code': code.get(addr, []), 'room': cap(o, n, end) - o - 1})
    out.sort(key=lambda s: s['addr'])
    return out


# the story's START pause menu "0000　続ける\n　中　断\n" (play-test 2026-10-29)
EXTRA_STRINGS = [0x383948]
REF_TEXT = (0x295000, 0x2AF000)         # file range where referenced strings are looked for
NAME_GRID = (0x2A1910, 0x2A3AE0)        # the name-entry grid (fixed rows, not strings)
REAL_TEXT = re.compile(r'[ぁ-んァ-ヶ一-龠ｦ-ﾟ]{2}')
SHORT_WORD = re.compile(r'[ぁ-んァ-ヶ一-龠]{1,3}')     # 分, 秒: units the code reads directly


def esc(s):
    return s.replace('\\', '\\\\').replace('\r', '\\r').replace('\n', '\\n').replace('\t', '\\t')


def unesc(s):
    return re.sub(r'\\([\\rnt])', lambda m: {'r': '\r', 'n': '\n', 't': '\t', '\\': '\\'}[m.group(1)], s)


UI_COMMENT = [
    'The program\'s own text (SLPM_623.42): menus, options, edit mode, costume parts, shouts, memory',
    'card messages, credits. id = RAM address. refs = pointers to the string (data words + code); a',
    'string with refs can grow (the build moves it); refs 0 = fixed in place: max_bytes is its room',
    '(ASCII letter = 1 byte, Japanese character = 2). Menus draw ASCII half-width: English gets about',
    'twice as many letters as the Japanese has characters, but menu boxes are narrow - stay near',
    'that. \\n is a line break, %s %d are filled in by the game, %c0 / %c1 change colour (keep them).',
    'Odd-length labels are drawn half a letter right so centred menus line up; notes `[left]` = a',
    'left-aligned list (no shift).',
]


# Fixed-size name fields in the executable: (id prefix, file offset, stride, count, field bytes, what)
FIXED_TABLES = [
    ('promo', 0x1160D0, 0x1A, 29, 0x1A, 'promotion, full name'),
    ('promo_short', 0x1163C8, 0x0E, 29, 0x0E, 'promotion, short name'),
    ('referee', 0x116C68, 0x198, 8, 0x12, 'referee name'),
    # the record a new edit wrestler starts from (roster layout: +1 flags, +2 name1, +0x10 name2,
    # +0x24 nickname - play-test 2026-10-29), and a new edit referee's name
    ('edit_name1', 0x20D2F2, 0, 1, 0x0E, 'new edit wrestler: short name (default)'),
    ('edit_name2', 0x20D300, 0, 1, 0x14, 'new edit wrestler: other name part (default)'),
    ('edit_nick', 0x20D314, 0, 1, 0x1A, 'new edit wrestler: nickname (default)'),
    ('edit_referee', 0x20D678, 0, 1, 0x12, 'new edit referee: name (default)'),
]
EDIT_FLAGS = 0x20D2F1      # the default edit wrestler's flags: separator bits (as the roster's)

FIXED_COMMENT = [
    'Fixed-size name fields in the program (SLPM_623.42): promotions (full and short) and referees.',
    'Written in place: max_bytes is the room (ASCII letter = 1 byte). Players can rename these in',
    'edit mode; these are the defaults.',
]


def fixed_fields(d=None):
    d = d or (paths.EXTRACTED / EXE).read_bytes()
    for pre, off, stride, n, size, what in FIXED_TABLES:
        for i in range(n):
            o = off + i * stride
            yield f'{pre}:{i}', o, size, bytes(d[o:o + size]).split(b'\0')[0], what


def dump_fixed():
    rows = [{'id': k, 'max_bytes': size - 1, 'japanese': dec(raw), 'notes': what}
            for k, o, size, raw, what in fixed_fields()]
    write_table('fixed.csv', FIXED_COMMENT, ['id', 'max_bytes', 'japanese', 'english', 'notes'], rows, key='id')


def dump_ui():
    d = (paths.EXTRACTED / EXE).read_bytes()
    rows = []
    done = {r['id'] for r in read_table('ui.csv') if r.get('english')}
    for s in exe_strings(d):
        refs = len(s['data']) + len(s['code'])
        if not refs and f'{s["addr"]:08X}' not in done:
            continue   # in the pools, every real string has a pointer: the rest is binary data
            #            (but a translated row stays: the build writes it in place)
        rows.append({'id': f'{s["addr"]:08X}', 'refs': refs, 'max_bytes': '' if refs else s['room'],
                     'japanese': esc(dec(s['raw']))})
    write_table('ui.csv', UI_COMMENT, ['id', 'refs', 'max_bytes', 'japanese', 'english', 'notes'], rows, key='id')


# ---------------------------------------------------------------- build steps
# Each takes the build's Files (get/put by disc path) and the name set ('real' / 'parody').

def english_text(text, names, where):
    """Translator English -> what the game gets: tokens resolved, escapes undone, ASCII checked."""
    t = resolve(unesc(text), names, where)
    bad = sorted({c for c in t if not (0x20 <= ord(c) < 0x7F or c in '\r\n\t' or c in SYMBOLS)})
    if bad:
        sys.exit(f'{where}: characters the game can\'t show in {t!r}: {bad} (printable ASCII, and {SYMBOLS})')
    return t


SYMBOLS = '○●△▲□■☆★◎×±・…♪０１２３４５６７８９\u3000'    # full-width symbols the fonts have, allowed in menu text (not the
#   story); full-width digits for rows the game lays out by cells (the appearance list's 1-4)


# One pair table per build: every step encodes its English with it; step_fonts draws it.
PAIRS = None
GAME_CODE = re.compile(CODE.pattern + r'|%[-0-9.]*[sdxc]|[\r\n\t]')


def kept_codes():
    """Double-byte codes the build still shows as Japanese: entries without English or kept on
    purpose, and the name-entry grid - pair glyphs must not replace them."""
    import textdb
    out = set()
    for e in textdb.entries():
        if not e.english or '# keep:' in (e.notes or '') or e.english == e.source:
            for ch in e.source:
                b = ch.encode(ENC, 'ignore')
                if len(b) == 2:
                    out.add(b)
    out |= {k.encode(ENC) for k in UNIT_GLYPHS}             # redrawn as m / s (step_fonts)
    # the name-entry rows the build keeps (ABC and symbols pages: 一二三... are kanji)
    d = (paths.EXTRACTED / EXE).read_bytes()
    for a in NAME_KEEP_ROWS:
        row = d[a - EXE_BASE:a - EXE_BASE + 30]
        for i in range(0, 30, 2):
            out.add(bytes(row[i:i + 2]))
    return out


def pairs():
    global PAIRS
    if PAIRS is None:
        import fpzfont
        PAIRS = {None: fpzfont.free_codes(kept_codes())}
    return PAIRS


def encode(text, room=None, center=False, digits=False, ascii=False):
    """English as the game's bytes: game codes and line breaks as they are, every run of plain
    characters as pair glyphs (two a code), full-width symbols as themselves. center: a text that
    is one odd-length run is drawn half a letter to the right (fpzfont.encode_shifted), so a game
    that centres it by its cells centres the letters (play-test 2026-10-29: odd labels sat half a
    letter left of even ones)."""
    if ascii:                            # plain single bytes, drawn through the character table
        return text.encode('ascii')
    if len(text) == 1 and 0x20 < ord(text) < 0x7F:
        return text.encode()             # one character: a plain byte (a pair would add a space)
    import fpzfont
    if center and len(text) % 2 and not re.search(f'{GAME_CODE.pattern}|[{SYMBOLS}]', text):
        b = fpzfont.encode_shifted(text, pairs())
        if room is None or len(b) <= room:
            return b
    out = bytearray()
    split = f'({GAME_CODE.pattern}|[{SYMBOLS}]' + ('|[0-9]+' if digits else '') + ')'
    for part in re.split(split, text):
        if not part:
            continue
        if GAME_CODE.fullmatch(part) or part in SYMBOLS or (digits and part.isdigit()):
            out += part.encode(ENC)
        else:
            out += fpzfont.encode_run(part, pairs())
    if room is not None and len(out) > room:
        return encode_tight(text)
    return bytes(out)


def encode_tight(text):
    """encode() keeping odd last letters as single bytes (one byte shorter per run)."""
    import fpzfont
    out = bytearray()
    for part in re.split(f'({GAME_CODE.pattern}|[{SYMBOLS}])', text):
        if part:
            out += part.encode(ENC) if GAME_CODE.fullmatch(part) or part in SYMBOLS else \
                fpzfont.encode_run(part, pairs(), odd_ascii=True)
    return bytes(out)


# ---------------------------------------------------------------- name entry
# The name-entry keyboard (docs/TECHNICAL.md, Name entry): pages of rows of 15 double-byte cells
# reached through row-pointer tables; the 単漢字 page jumps from a reading index through a table of
# start rows. The English keyboard (owner 2026-10-29): the cells insert pair glyphs, the same codes
# the build gives English text, so a name is typed two letters a cell like the names already there.
#   Hiragana page -> "Letters": a letter + space (A..Z a..z, for an odd last letter), space + capital
#   Katakana page -> "More": space + lowercase, digits, punctuation
#   単漢字 index  -> the 52 first letters; the list -> 4 rows a letter: every pair starting with it
# The ABC and symbols pages stay (full-width characters, one a cell).
NAME_ROW_BASE = 0x3A0910            # row storage (RAM), 32 bytes a row (15 cells + 2 NUL)
NAME_ROWS_FREE = [(0x3A0910, 7), (0x3A0A10, 7), (0x3A0CF0, 240)]   # (first row, count) rewritable
NAME_BLANK = 0x3A09F0               # an all-blank row
NAME_KEEP_ROWS = [0x3A0AF0 + 0x20 * i for i in range(6)] + [0x3A0BB0 + 0x20 * i for i in range(10)]
NAME_PAGES = {'hira': (0x3348D0, 8), 'kata': (0x3348F0, 8), 'index': (0x334910, 8), 'kanji': (0x334980, 283)}
NAME_JUMP = 0x3347D8                # u16 start row in the kanji page, per index cell (row * 15 + col)
UPPER = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
LOWER = UPPER.lower()


def name_entry_pages():
    """{page: [rows of 15 pairs or None]}, and the index letters in jump order."""
    letters = UPPER + LOWER
    seconds = LOWER + UPPER + " .-'"                     # 56: four rows of 15 hold them
    def rows(cells):
        cells = list(cells)
        cells += [None] * (-len(cells) % 15)
        return [cells[i:i + 15] for i in range(0, len(cells), 15)]
    hira = rows([c + ' ' for c in UPPER] + [None, None, None, None]
                + [c + ' ' for c in LOWER] + [None, None, None, None]
                + [' ' + c for c in UPPER])
    kata = rows([' ' + c for c in LOWER] + [None, None, None, None]
                + [d + ' ' for d in '0123456789'] + ['. ', '- ', "' ", '& ', '! ']
                + [' ' + d for d in '0123456789'] + ['? ', ', ', ': ', '/ ', ' .'])
    index = rows([c + ' ' for c in UPPER] + [None] * 4 + [c + ' ' for c in LOWER] + [None] * 4)
    kanji = []
    for c in letters:
        kanji += rows([c + x for x in seconds])
    return {'hira': hira, 'kata': kata, 'index': index, 'kanji': kanji}, letters


def step_name_entry(files, names):
    """Write the English keyboard (see above) into the program: rows, page tables, jump table."""
    import struct
    import fpzfont
    d = files.get(EXE)
    pages, letters = name_entry_pages()
    blank = '\x81\x40'.encode('latin-1')
    free = [a + 0x20 * i for a, n in NAME_ROWS_FREE for i in range(n)]
    used = 0
    for page, (table, count) in NAME_PAGES.items():
        rows = pages[page]
        if len(rows) > count:
            sys.exit(f'name entry: page {page} has {len(rows)} rows, room for {count}')
        for k in range(count):
            if k < len(rows):
                a = free[used]
                used += 1
                cells = b''.join(fpzfont.encode_run(c, pairs()) if c else blank for c in rows[k])
                o = a - EXE_BASE
                d[o:o + 32] = cells + bytes(2)
                ptr = a
            else:
                ptr = NAME_BLANK
            struct.pack_into('<I', d, table - EXE_BASE + 4 * k, ptr)
    for i in range(60):                                    # 4 index rows of 15
        struct.pack_into('<H', d, NAME_JUMP - EXE_BASE + 2 * i, 0)
    for k, c in enumerate(letters):
        cell = k if k < 26 else 30 + (k - 26)              # row 3 and 4 start at cells 30
        struct.pack_into('<H', d, NAME_JUMP - EXE_BASE + 2 * cell, 4 * k)
    files.put(EXE, d)
    print(f'name entry: {used} keyboard rows, {len(letters)} index letters')


# CPU logic: the button icons after an option's label are placed by hand-set numbers, not by
# the label's width (docs/TECHNICAL.md "Button icons"). Per condition (CPU_CONDS, 12-byte entries:
# label, damage-level table, levels, icon-list index) an icon list (CPU_ICON_PTRS words,
# CPU_ICON_COUNTS halfwords) of 3-byte records: icon, option row, x - drawn at 2*x after the
# label's start. The build sets x from the English label's width.
CPU_CONDS, CPU_CONDS_N = 0x30C008, 0x18
CPU_ICON_PTRS, CPU_ICON_COUNTS = 0x30B968, 0x30B9B0
CPU_CELL, CPU_GAP = 20, 8          # px a double-byte code takes; px between label and icon


def step_cpu_icons(files, names):
    """Set every CPU-logic icon's x from the English width of the label before it."""
    import struct
    orig = (paths.EXTRACTED / EXE).read_bytes()
    d = files.get(EXE)
    eng = {r['id']: r['english'] for r in read_table('ui.csv') if r.get('english')}
    left = {r['id'] for r in read_table('ui.csv') if '[left]' in (r.get('notes') or '')}

    def word(a, f='<I'):
        return struct.unpack_from(f, orig, a - EXE_BASE)[0]
    n = 0
    seen = set()
    for c in range(CPU_CONDS_N):
        e = CPU_CONDS + 12 * c
        idx = struct.unpack_from('<b', orig, e + 9 - EXE_BASE)[0]
        if idx < 0 or idx in seen:
            continue
        seen.add(idx)
        options = word(word(e + 4) + 4)          # the first damage level's option list
        recs, count = word(CPU_ICON_PTRS + 4 * idx), word(CPU_ICON_COUNTS + 2 * idx, '<H')
        rows = {}
        for k in range(count):
            icon, row, x = struct.unpack_from('<bbb', orig, recs + 3 * k - EXE_BASE)
            rows.setdefault(row, []).append((k, x))
        for row, items in rows.items():
            label = word(options + 8 * row)
            text = eng.get(f'{label:08X}')
            if text is None:
                continue
            plain = CODE.sub('', english_text(text, names, f'ui.csv {label:08X}'))
            # letters are half a cell each; an odd centred label is drawn half a letter right
            shifted = len(plain) % 2 and f'{label:08X}' not in left
            width = (len(plain) + (1 if shifted else 0)) * CPU_CELL // 2
            first = min(x for _, x in items)
            for k, x in items:
                new = (width + CPU_GAP) // 2 + (x - first)
                d[recs + 3 * k + 2 - EXE_BASE] = new
                n += 1
    files.put(EXE, d)
    print(f'cpu logic: {n} button icons placed after their English labels')


# Move editor: per move slot a 10-byte record at MOVE_SLOTS (halfwords: label x, icon, icon x, icon,
# icon x; -1 = none). With a label x the label is drawn left-aligned at x + 0x40; with -1 it is centred
# in the 240 pixels from 0x40. The Japanese columns made rows with buttons look unaligned (owner
# 2026-10-30): the build centres label + buttons as one group on the same point. The slot's label:
# MOVE_LABELS[MOVE_LABEL_OF[slot]].
MOVE_SLOTS, MOVE_SLOTS_N = 0x3112E8, 0x4E
MOVE_LABELS, MOVE_LABEL_OF = 0x3108A0, 0x3109D8
MOVE_GAP = 7                           # label to first button
MOVE_ICON = 24                         # a button's width
MOVE_CENTRE = 148                      # the centred rows' middle, in label x + 0x40 terms (measured: the window sits 32 right)


def step_move_icons(files, names):
    """Centre each move-editor slot's label and buttons as one group."""
    import struct
    orig = (paths.EXTRACTED / EXE).read_bytes()
    d = files.get(EXE)
    eng = {r['id']: r['english'] for r in read_table('ui.csv') if r.get('english')}
    left = {r['id'] for r in read_table('ui.csv') if '[left]' in (r.get('notes') or '')}
    n = 0
    for slot in range(MOVE_SLOTS_N):
        rec = MOVE_SLOTS + 10 * slot - EXE_BASE
        lx, icon, ix, icon2, ix2 = struct.unpack_from('<5h', orig, rec)
        if lx < 0 or icon < 0:
            continue
        which = struct.unpack_from('<b', orig, MOVE_LABEL_OF + slot - EXE_BASE)[0]
        label = struct.unpack_from('<I', orig, MOVE_LABELS + 4 * which - EXE_BASE)[0]
        k = f'{label:08X}'
        if k not in eng:
            continue
        plain = CODE.sub('', english_text(eng[k], names, f'ui.csv {k}'))
        shifted = len(plain) % 2 and k not in left
        width = (len(plain) + (1 if shifted else 0)) * CPU_CELL // 2
        second = ix2 - ix if icon2 >= 0 else 0
        start = MOVE_CENTRE - (width + MOVE_GAP + MOVE_ICON + second) // 2
        struct.pack_into('<h', d, rec, start - 0x40)
        struct.pack_into('<h', d, rec + 4, start + width + MOVE_GAP)
        if icon2 >= 0:
            struct.pack_into('<h', d, rec + 8, start + width + MOVE_GAP + second)
        n += 1
    files.put(EXE, d)
    print(f'move editor: {n} slots centred with their button icons')


# Kanji the game puts into English screens itself, redrawn as English in the fonts: the match
# result time is built from 分 and 秒 by code (play-test 2026-10-29: "13分11秒" - no string of
# ours reaches it), so those two glyphs become "m" and "s" (kept out of the pair codes).
UNIT_GLYPHS = {'分': 'm ', '秒': 's '}


def step_fonts(files, names):
    """Draw every pair glyph this build used into every copy of both fonts (runs last), and the
    UNIT_GLYPHS."""
    import fpzfont
    codes = {v: k for k, v in pairs().items() if k is not None}
    for kanji, pair in UNIT_GLYPHS.items():
        codes[kanji.encode(ENC)] = pair
    fonts = {}
    for arc, entry, size, comp in fpzfont.FONT_COPIES:
        if arc not in fonts:
            fonts[arc] = fpz.Oah(files.get(arc))
        f = fonts[arc].read(entry)
        f = fpz.cp00_decode(f) if comp else f
        f = fpzfont.patch_font(f, size, codes)
        fonts[arc].write(entry, fpz.cp00_encode(f) if comp else f)
    for arc, o in fonts.items():
        files.put(arc, o.bytes())
    print(f'fonts: {len(codes)} pair glyphs drawn')


def step_roster(files, names):
    data = files.get('STRHUMAN.BIN')
    pre = 'en_' if names == 'real' else 'parody_'
    n = 0
    for r in read_table('wrestlers.csv'):
        i = int(r['idx'])
        n1 = r.get(pre + 'name1') or r.get('en_name1')
        if not n1:
            continue
        n2 = r.get(pre + 'name2') if r.get(pre + 'name1') else r.get('en_name2')
        order = (r.get(pre + 'order') if r.get(pre + 'name1') else r.get('en_order')) or '1-2'
        nick = (r.get('parody_nick') if names == 'parody' else '') or r.get('en_nick') or ''
        where = f'wrestlers.csv row {i}'
        if n2:      # the space goes into name2 (a separator would double a pair's padding); after
            # an odd name1 its padding is the space already
            if order == '2-1':
                n2 = n2 + ' '
            elif len(english_text(n1, names, where)) % 2 == 0:
                n2 = ' ' + n2
        for field, v in (('name1', n1), ('name2', n2 or ''), ('nick', nick)):
            if field == 'nick' and not v:
                continue
            room = {'name1': 13, 'name2': 19, 'nick': 25}[field]
            t = english_text(v, names, where)
            # an odd last letter is paired with a space, as everywhere: a single byte would be the
            # font's own full-width letter (smaller, another style) in the same full cell
            b = encode(t, room, center=field == 'name1')    # short names: centred in the lists
            fpz.put_roster_field(data, i, field, b)
        at = i * fpz.ROSTER_RECORD + 1
        flags = data[at] & ~0x83
        flags |= 0x03 | (0x80 if n2 and order == '2-1' else 0)     # separator: none (see above)
        data[at] = flags
        n += 1
    files.put('STRHUMAN.BIN', data)
    print(f'roster: {n} wrestlers ({names} names)')


def step_moves(files, names):
    orig = files.get('WAZA.BIN')
    w = fpz.moves(orig)
    n = 0
    for r in read_table('moves.csv'):
        if r.get('english'):
            w[int(r['index'])] = encode(english_text(r['english'], names, f'moves.csv row {r["index"]}'))
            n += 1
    out = fpz.build_moves(w, share=True)
    if len(out) > len(orig):
        sys.exit(f'moves.csv: the move names take {len(out)} bytes, the game\'s buffer {len(orig)} - shorten '
                 f'{len(out) - len(orig)} bytes')
    files.put('WAZA.BIN', out.ljust(len(orig), b'\0'))
    print(f'moves: {n} names, {len(out)} of {len(orig)} bytes')


def step_fixed(files, names):
    d = files.get(EXE)
    eng = {r['id']: r['english'] for r in read_table('fixed.csv') if r.get('english')}
    n = 0
    for k, o, size, raw, what in fixed_fields(d):
        if k in eng:
            b = encode(english_text(eng[k], names, f'fixed.csv {k}'), size - 1)
            if len(b) >= size:
                sys.exit(f'fixed.csv {k}: "{eng[k]}" takes {len(b)} bytes, room for {size - 1}')
            d[o:o + size] = b.ljust(size, b'\0')
            n += 1
    if 'edit_name2:0' in eng:
        # as step_roster: no separator, the space goes into name2 - unless an odd name1's
        # padding space already gives one
        name1 = english_text(eng.get('edit_name1:0', ''), names, 'fixed.csv edit_name1:0')
        if len(name1) % 2 == 0:
            o = FIXED_TABLES[4][1]
            b = encode(' ' + english_text(eng['edit_name2:0'], names, 'fixed.csv edit_name2:0'), 0x13)
            d[o:o + 0x14] = b.ljust(0x14, b'\0')
        d[EDIT_FLAGS] = (d[EDIT_FLAGS] & ~0x03) | 0x03
    files.put(EXE, d)
    print(f'fixed fields: {n}')


def _hi(a):
    return (a + 0x8000) >> 16


def _align(addr):
    """The alignment a moved string keeps: the largest power of two up to 16 its address had (the
    EE copies some strings with 128-bit loads - 4-byte alignment broke story mode, 2026-10-29)."""
    for al in (16, 8, 4, 2):
        if addr % al == 0:
            return al
    return 1


def step_ui(files, names):
    """The program's strings, repacked. A run is a series of strings with only NUL padding between
    them (data between strings ends a run and is never touched); each run is laid out again in
    order with every string's English (or its original bytes), 4-byte aligned, and every
    reference is updated: data pointers, and the low half of lui/addiu pairs - a string reached
    from code keeps its 64 KB (lui) half, so it is pushed forward when packing would cross it.
    Strings a run can't hold go to room left in other runs (those reached from data only)."""
    import struct
    d = files.get(EXE)
    orig = bytes(d)
    eng = {r['id']: r['english'] for r in read_table('ui.csv')
           if r.get('english') and '# keep:' not in (r.get('notes') or '')
           # the same text is "kept as Japanese" - except ASCII, which still needs pair glyphs
           and (r['english'] != r['japanese'] or not JP.search(r['japanese']))}
    # rows drawn left-aligned (notes `[left]`): no half-letter shift for odd lengths (encode center)
    left = {r['id'] for r in read_table('ui.csv') if '[left]' in (r.get('notes') or '')}
    # notes `[digits]`: digits stay single bytes, the rest pairs - the shape of a template the game
    # fills in place (the result time 00分00秒: 2 digits, a 2-byte unit, 2 digits, a 2-byte unit)
    digits = {r['id'] for r in read_table('ui.csv') if '[digits]' in (r.get('notes') or '')}
    # notes `[ascii]`: the English as plain single bytes (drawn through the game's character table,
    # like the numbers next to it) - the result time, whose screen takes no pair glyphs
    ascii_rows = {r['id'] for r in read_table('ui.csv') if '[ascii]' in (r.get('notes') or '')}

    strings = sorted(exe_strings(orig), key=lambda x: x['off'])
    lim = os.environ.get('FPZ_UI_RANGE')       # research: repack only runs in lo-hi (hex RAM)
    if lim:
        lo, hi = (int(x, 16) for x in lim.split('-'))
        outside = [st for st in strings if not lo <= st['addr'] < hi]
        strings = [st for st in strings if lo <= st['addr'] < hi]
    else:
        outside = []
    if os.environ.get('FPZ_UI_INPLACE') or outside:
        for st in (strings if os.environ.get('FPZ_UI_INPLACE') else outside):
            k = f'{st["addr"]:08X}'
            if k in eng:
                b = encode(english_text(eng[k], names, f'ui.csv {k}'), st['room'], center=k not in left, digits=k in digits, ascii=k in ascii_rows)
                if len(b) <= st['room']:
                    d[st['off']:st['off'] + st['room'] + 1] = (b + b'\0').ljust(st['room'] + 1, b'\0')
        if os.environ.get('FPZ_UI_INPLACE'):
            files.put(EXE, d)
            print('ui: in place only (FPZ_UI_INPLACE)')
            return
    pinned = [st for st in strings if not st['data'] and not st['code']]    # nothing known points here
    for st in pinned:
        k = f'{st["addr"]:08X}'
        if k in eng:
            b = encode(english_text(eng[k], names, f'ui.csv {k}'), st['room'], center=k not in left, digits=k in digits, ascii=k in ascii_rows)
            if len(b) > st['room']:
                sys.exit(f'ui.csv {k}: "{eng[k]}" takes {len(b)} bytes, room for {st["room"]} (no pointer found: '
                         f'it stays in place)')
            d[st['off']:st['off'] + st['room'] + 1] = (b + b'\0').ljust(st['room'] + 1, b'\0')
    runs, cur = [], []
    for st in strings:
        if not st['data'] and not st['code']:
            if cur:
                runs.append(cur)
            cur = []
            continue
        if cur and cur[-1]['off'] + cur[-1]['room'] + 1 != st['off']:
            runs.append(cur)
            cur = []
        cur.append(st)
    if cur:
        runs.append(cur)
    strings = [st for st in strings if st['data'] or st['code']]
    place = {}          # off -> new off
    content = {}
    shared = {}         # bytes -> [offsets already holding them]

    def reuse(st, b):
        """An offset already holding the same bytes this string may point to, or None."""
        lui_refs = any(lui is not None for lui, _ in st['code'])
        gp_refs = any(lui is None for lui, _ in st['code'])
        for a in shared.get(b, []):
            if _align(a + EXE_BASE) >= _align(st['addr']) and (not lui_refs or _hi(a + EXE_BASE) == _hi(st['addr'])) \
                    and (not gp_refs or -0x8000 <= a + EXE_BASE - GP < 0x8000):
                return a
        return None
    leftover = []       # (start, end) free after packing
    homeless = []
    for run in runs:
        start, end = run[0]['off'], run[-1]['off'] + run[-1]['room'] + 1
        c = start
        for st in run:
            k = f'{st["addr"]:08X}'
            b = encode(english_text(eng[k], names, f'ui.csv {k}'), None, center=k not in left, digits=k in digits, ascii=k in ascii_rows) if k in eng else st['raw']
            content[st['off']] = b
            r = reuse(st, b)
            if r is not None:
                place[st['off']] = r
                continue
            al = _align(st['addr'])
            a = (c + al - 1) & -al
            if any(lui is not None for lui, _ in st['code']):
                h = _hi(st['addr'])
                while _hi(a + EXE_BASE) < h:
                    a = ((h << 16) - 0x8000 - EXE_BASE + al - 1) & -al
                if _hi(a + EXE_BASE) != h:
                    a = None
            if a is None or a + len(b) + 1 > end:
                homeless.append(st)
                continue
            place[st['off']] = a
            shared.setdefault(b, []).append(a)
            c = a + len(b) + 1
        leftover.append([c, end])
        d[start:end] = bytes(end - start)
    for st in sorted(homeless, key=lambda x: (-_align(x['addr']), -len(content[x['off']]))):
        b = content[st['off']]
        r = reuse(st, b)
        if r is not None:
            place[st['off']] = r
            continue
        al = _align(st['addr'])
        for g in leftover:
            a = (g[0] + al - 1) & -al
            lui_refs = any(lui is not None for lui, _ in st['code'])
            gp_refs = any(lui is None for lui, _ in st['code'])
            if g[1] - a >= len(b) + 1 and (not lui_refs or _hi(a + EXE_BASE) == _hi(st['addr'])) \
                    and (not gp_refs or -0x8000 <= a + EXE_BASE - GP < 0x8000):
                break
        else:
            k = f'{st["addr"]:08X}'
            gaps = sorted((e - a for a, e in leftover if e > a), reverse=True)
            sys.exit(f'ui.csv {k}: no room for "{eng.get(k, dec(st["raw"]))}" ({len(b) + 1} bytes, align {al}) - '
                     f'shorten it or its neighbours in the menu ({len(homeless)} strings to place; free: '
                     f'{sum(gaps)} bytes, largest gaps {gaps[:8]})')
        place[st['off']] = a
        shared.setdefault(b, []).append(a)
        g[0] = a + len(b) + 1
    moved = 0
    for st in strings:
        a = place[st['off']]
        b = content[st['off']]
        d[a:a + len(b) + 1] = b + b'\0'
        if a == st['off']:
            continue
        moved += 1
        new = a + EXE_BASE
        for w in st['data']:
            struct.pack_into('<I', d, w, new)
        for lui, low in st['code']:
            ins = struct.unpack_from('<I', d, low)[0]
            imm = (new - GP) & 0xFFFF if lui is None else new & 0xFFFF
            if lui is None and not -0x8000 <= new - GP < 0x8000:
                sys.exit(f'ui.csv {st["addr"]:08X}: moved out of $gp range')
            struct.pack_into('<I', d, low, (ins & 0xFFFF0000) | imm)
    files.put(EXE, d)
    free = sum(e - a for a, e in leftover if e > a)
    print(f'ui: {len(eng)} strings in English, {moved} moved, {len(homeless)} into other runs, {free} bytes left')


def story_names_english(names):
    out = {}
    for r in read_table('story_names.csv'):
        if r.get('english'):
            out[r['id']] = english_text(r['english'], names, f'story_names.csv {r["id"]}')
    return out


# Story short names that differ from the roster's (the roster short name also builds the full
# name): Yoshinari and Naoya Ogawa both print "Ogawa" - the story says "Y Ogawa" / "N Ogawa"
# (owner 2026-10-29). Roster index -> name token (name_tokens.csv).
STORY_SHORT = {81: 'Y Nogawa', 94: 'H Nogawa'}


def _story_short(text, names, where):
    return re.sub(r'%ss(\d+)\b', lambda m: resolve(f'<{STORY_SHORT[int(m.group(1))]}>', names, where)
                  if int(m.group(1)) in STORY_SHORT else m.group(0), text)


def build_story_page(page, english, speakers, pairs, names, where):
    """A page's bytes with English: speaker and codes kept, text wrapped and pair-encoded."""
    import fpzfont
    pg = Page(page)
    english = _story_short(english, names, where)
    lines = [ln.encode(ENC) for ln in pg.lines]
    if pg.speaker is not None:
        pre, label = pg.speaker_label()
        if re.fullmatch(r'%ss\d+', label) and int(label[3:]) in STORY_SHORT:
            label = _story_short(label, names, where)
        elif not label.startswith('%ss') or not re.fullmatch(r'%ss\d+', label):
            label = speakers.get(label)
            if label is None:
                sys.exit(f'{where}: speaker {pg.speaker_label()[1]} has no English (speakers.csv)')
        lines[pg.speaker] = pre.encode() + encode_story_line(label + ':', pairs)
    text = wrap(english.split('\n'))
    room = LINES_PER_PAGE - (1 if pg.speaker is not None else 0)
    if len(text) > room:
        sys.exit(f'{where}: {len(text)} lines after wrapping, the page holds {room}')
    # codes at the start of the first text line (%c0) stay in front
    lead = re.match(r'(?:%c\d)*', pg.lines[pg.text[0]]).group().encode()
    enc = [encode_story_line(t, pairs) for t in text]
    if enc:
        enc[0] = lead + enc[0]
    lines[pg.text[0]:pg.text[-1] + 1] = enc
    return b'\r\n'.join(lines)


def encode_story_line(text, pairs):
    """A story line as the game's bytes: %codes as they are, plain runs as pair codes."""
    import fpzfont
    out = bytearray()
    for part in re.split(r'(%ss\d+|%sf\d+|%sl\d+|%sa\d+|%sw\d+|%st|%sk|%c\d|%s)', text):
        if not part:
            continue
        if CODE.fullmatch(part) or part == '%s':
            out += part.encode()
        else:
            out += fpzfont.encode_run(part, pairs)
    return bytes(out)


def step_story(files, names):
    """Every story file: dialog pages, choices and cards in English pair glyphs; the story names;
    the pair glyphs drawn into every copy of both fonts."""
    import fpzfont
    blocks_by_file = {}
    for n in range(1, 8):
        p = paths.SCRIPT / f'story{n:02d}.txt'
        bf = blocks.BlockFile(p)
        blocks_by_file[n] = {b.id: '\n'.join(b.english) for b in bf.blocks if b.english}
    speakers = {r['japanese']: english_text(r['english'], names, f'speakers.csv {r["japanese"]}')
                for r in read_table('speakers.csv') if r.get('english')}
    cards = {r['japanese']: english_text(r['english'], names, f'story_cards.csv {r["japanese"]}')
             for r in read_table('story_cards.csv') if r.get('english')}
    snames = story_names_english(names)
    pairs = globals()['pairs']()
    a = fpz.Oah(files.get('STORY.OAH'))
    pages_done = 0
    for n, fname in enumerate(STORY_FILES, 1):
        eng = blocks_by_file[n]
        data = a.read(fname)
        if n == 7:                     # the Liger scenario's matches
            data = ligerstory.restore(data, storywrestlers.slots())
        s = fpz.Sto(data)
        new = list(s.strings)
        for i, raw in enumerate(s.strings):
            text = dec(raw)
            kind = story_kind(text)
            if kind == 'line':
                e = eng.get(f'C{n}.{i:03d}')
                if e:
                    new[i] = encode_story_line(english_text(e, names, f'story C{n}.{i:03d}'), pairs)
                continue
            if kind == 'card':
                t = raw
                for k in sorted(cards, key=len, reverse=True):
                    if k.encode(ENC) in t:
                        t = t.replace(k.encode(ENC), encode_story_line(cards[k], pairs))
                new[i] = t
                continue
            if kind != 'dialog':
                continue
            out = []
            changed = False
            parts = split_pages(text)
            for p, (page, term) in enumerate(parts):
                key = f'{n}.{i:03d}.{p:02d}'
                if key in eng:
                    page = build_story_page(page, english_text(eng[key], names, f'story {key}'), speakers,
                                            pairs, names, f'story {key}')
                    changed = True
                    pages_done += 1
                out.append(page if isinstance(page, bytes) else page.encode(ENC))
            coloured = storycolours.fix(n, [(parts[p][0], b) for p, b in enumerate(out)])
            if changed or coloured != out:
                new[i] = b''.join(b + parts[p][1].encode() for p, b in enumerate(coloured))
        nm = [snames.get(f'{n}:{k}') for k in range(len(s.names))]
        nm = [x if x is not None else s.names[k].split(b'\0')[0] for k, x in enumerate(nm)]
        if n == 7:                     # the match cards' names, drawn like the roster's
            nm[6], nm[7] = encode(nm[6], 15), encode(nm[7], 15)
        a.write(fname, storywrestlers.apply(n, s.build(new, nm), files, encode))
    files.put('STORY.OAH', a.bytes())
    print(f'story: {pages_done} pages')


# ---------------------------------------------------------------- command line

def show(story_id, names='real'):
    """Print a story page's JP and its English as the window will show it: tokens resolved,
    names filled in (`names` real / parody), wrapped to the window's lines."""
    n = story_id.lstrip('C')[0]
    path = paths.TRANSLATION / 'script' / f'story0{n}.txt'
    block = next((b for b in path.read_text(encoding='utf-8').split('\n@ ')[1:]
                  if b.split('\n', 1)[0].strip() == story_id), None)
    if block is None:
        sys.exit(f'{story_id}: no such block in {path.name} (ids look like 1.000.01 or C1.408)')
    rows = {int(r['idx']): r for r in read_table('wrestlers.csv')}
    pre = 'en_' if names == 'real' else 'parody_'

    def name(m):
        r = rows.get(int(m.group(2)))
        if r is None:
            return m.group(0)
        if m.group(1) == 's':
            return r[pre + 'name1'] or r['en_name1']
        if m.group(1) == 'f':
            return _full(r, pre)
        return r[pre + 'name2'] or r['en_name2']
    lines = block.split('\n')
    for ln in lines[1:]:
        if ln.startswith(('#', 'JP ')):
            print(ln)
    en = [resolve(unesc(ln[3:]), names, story_id) for ln in lines if ln.startswith('EN ')]
    print('--- as shown:')
    for ln in wrap(en):
        print('  ' + re.sub(r'%s([sfl])(\d+)', name, ln))
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__)
        return 0
    if argv[0] == 'dump':
        what = argv[1] if len(argv) > 1 else 'all'
        if what in ('story', 'all'):
            dump_story()
        if what in ('roster', 'all'):
            dump_roster()
        if what in ('moves', 'all'):
            dump_moves()
        if what in ('ui', 'all'):
            dump_ui()
            dump_fixed()
        return 0
    if argv[0] == 'show' and len(argv) > 1:
        return show(argv[1], argv[2] if len(argv) > 2 else 'real')
    print(__doc__)
    return 1


if __name__ == '__main__':
    sys.exit(main())
