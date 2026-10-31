#!/usr/bin/env python3
"""Check the translation text: python3 tools/lint.py [--missing] [--warnings] [file...]

Errors (check.py and the build fail on these):
  source       source-language characters (kana, kanji) left in the English (not in a block with
               a `# keep: why` comment - text kept as the original on purpose, e.g. staff credits:
               copy the source into the English line so the entry counts as done)
  codes        control codes in the source missing from the English, or extra ones (CODE)
  lines        more lines than a block file's `# limit lines=N`
  chars        a line longer than `# limit chars=N` (characters; pixel widths need the game's
               own layout check)
  bytes        English longer than a fixed table string's max_bytes (refs == 0), as encoded by
               encoded_length() - adjust it to how the build stores English
  room         more than the string's measured room (translation/text/rooms.csv, below): counted
               by count() (characters - or the game's glyphs/tiles), and pixels by width() if the
               game provides it; and any string over MAX_COUNT (a hard per-string limit, e.g.
               the glyph records of one text object) when it is set
  source lines more lines than the source (SAME_LINES: fixed windows that don't scroll)
  tags         markup copied as it is (TAG, e.g. HTML in a browser's pages) differs from the source's
  token        a name token (NAME_TOKEN) the names tool doesn't know (name_tokens())
A block whose comment holds `# name-token:` may drop wrestler name codes (%ssN...) for a name token
("Super %ss37" = <Super Tiger*>: a different person from the roster's own name).
Deliberate layout changes: a block whose comment holds `# layout:` may change its position codes
(LAYOUT_CODE, e.g. pen moves) - the other codes must still match.

rooms.csv - room measured in the game (a debugger or emulator: which text area the string is drawn
into and how much it holds), one row per string, address range or table column:
  id,count,px,screen,measured
  text/menus.txt|2ND:060BDB54,15,,Mode Select title,2026-10-27 emulator
  text/menus.txt|2ND:060B3634-060B3838,16,96,Moves categories,...   (a range of block ids)
  moves.csv:japanese,20,150,Wrestler Select finisher,...             (every row of a table column)
Warnings (shown with --warnings; counted by status.py):
  glossary     the source contains a glossary term but the English doesn't use its translation
               (translation/glossary.csv: japanese, english, notes; several accepted English forms
               separated by ' | '; put [glossary-ok] in a block comment or row note to silence)
  spacing      trailing spaces or double spaces in the English (leading spaces are left alone:
               continuation lines are often indented)
  width        no measured room, but the English is much wider than the source (WIDER_THAN_SOURCE,
               with width()): check it fits on screen
Two name sets (real / parody, build.py NAME_SETS): names are written as tokens (`<Name>`) that the
build resolves per set; encoded_length() and width() should measure the longer of the sets.
--missing also lists untranslated entries (status.py counts them).
"""
import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402
import textdb  # noqa: E402

SOURCE_CHARS = re.compile(r'[぀-ヿ㐀-䶿一-鿿ｦ-ﾟ]')
CODE = re.compile(r'#x[0-9A-Fa-f]{2}|%(?:ss\d+|sf\d+|sl\d+|sa\d+|sw\d+|st|sk|k2|k|c\d|px\d+|py\d+|bx0x[0-9a-fA-F]+|by0x[0-9a-fA-F]+|m\d|w\d+|t\d)|%[-0-9.]*[sdxc]|\\[nrt]')  # the game's codes (tools/fpztext.py CODE + printf + escapes)


LAYOUT_CODE = re.compile(r'#x[0-9A-Fa-f]{2}')    # the game's jump-to-x code: a `# layout:` row may move it
MAX_COUNT = None      # a hard limit for every string, in count() units (None: no limit)
SAME_LINES = False    # True: the English may not have more lines than the source (windows that don't scroll)
TAG = None            # e.g. re.compile(r'<[^<>]*>'): markup the English keeps as it is (HTML pages)
NAME_TOKEN = re.compile(r'<[A-Za-z0-9][^<>]*>')     # e.g. re.compile(r'<[A-Za-z][^<>]*>'): name tokens resolved per name set
WIDER_THAN_SOURCE = None   # e.g. (1.6, 48): warn when, with no measured room, the English is wider
                           # than both 1.6 x the source and the source + 48 px (needs width())


def encoded_length(text):
    """Bytes the build will store for `text` - change to match the build (e.g. 2 per char for full-width)."""
    return len(text.encode('ascii', 'replace'))


def count(text):
    """What a text area holds, for rooms.csv and MAX_COUNT: characters without codes - change to the
    game's unit (glyphs drawn, tiles) when that differs."""
    return len(CODE.sub('', text).replace('\n', ''))


def width(text):
    """Pixel width of `text` for rooms.csv `px`, or None if the game has no measure (the game's
    font widths: return the widest line)."""
    return None


def tag_key(tag):
    """How a TAG compares with the source's - e.g. an HTML button without name= isn't sent with its
    form, so its value= is only the caption on screen and may be translated:
        if re.search(r'(?i)type="(submit|reset|button)"', tag) and not re.search(r'(?i)\bname=', tag):
            tag = re.sub(r'(?i)\bvalue="[^"]*"', 'value="..."', tag)"""
    return tag.lower()


def name_tokens():
    """The name tokens the project's names tool knows (with NAME_TOKEN): a set of the full tokens."""
    import fpztext
    return {f'<{t}>' for t in fpztext.name_tokens()}


_ROOMS = None


def rooms():
    """{id: (count, px, screen)} from translation/text/rooms.csv."""
    global _ROOMS
    if _ROOMS is None:
        _ROOMS = {}
        p = paths.TEXT / 'rooms.csv'
        if p.exists():
            with open(p, encoding='utf-8', newline='') as f:
                for r in csv.DictReader(ln for ln in f if not ln.startswith('#')):
                    _ROOMS[r['id']] = (int(r['count']) if r.get('count') else None,
                                       int(r['px']) if r.get('px') else None, r.get('screen', ''))
    return _ROOMS


def room_for(e):
    """The rooms.csv row for an entry: its block id, a range holding it, or its table column."""
    rel = f'{e.file.parent.name}/{e.file.name}'
    if f'{rel}|{e.key}' in rooms():
        return rooms()[f'{rel}|{e.key}']
    if e.file.suffix == '.csv':
        col = e.key.partition(':')[2] or textdb.SOURCE_COLUMN
        if f'{e.file.name}:{col}' in rooms():
            return rooms()[f'{e.file.name}:{col}']
    m = re.match(r'(\w+):([0-9A-Fa-f]+)$', e.key)
    if m:
        for k, v in rooms().items():
            r = re.match(rf'{re.escape(rel)}\|(\w+):([0-9A-Fa-f]+)-([0-9A-Fa-f]+)$', k)
            if r and r.group(1) == m.group(1) and int(r.group(2), 16) <= int(m.group(2), 16) <= int(r.group(3), 16):
                return v
    return None


def glossary():
    if not paths.GLOSSARY.exists():
        return []
    with open(paths.GLOSSARY, encoding='utf-8', newline='') as f:
        return [(r['japanese'].strip(), [e.strip() for e in r['english'].split(' | ') if e.strip()])
                for r in csv.DictReader(f) if (r.get('japanese') or '').strip() and (r.get('english') or '').strip()]


def check_entry(e, terms):
    """[(severity, kind, message)] for one entry."""
    out = []
    en = e.english
    if not en:
        return out
    m = SOURCE_CHARS.search(en)
    if m and '# keep:' not in (e.notes or ''):     # `# keep:` = left as the original on purpose
        out.append(('error', 'source', f'source-language text left in the English: {m.group()!r}'))
    a, b = Counter(CODE.findall(e.source)), Counter(CODE.findall(en))
    if NAME_TOKEN:          # name tokens stand for names written out in the source
        b = Counter({k: v for k, v in b.items() if k not in name_tokens()})
    if '# name-token:' in (e.notes or ''):    # a wrestler's name code replaced by a name token on purpose
        a, b = (Counter({k: v for k, v in c.items() if not re.match(r'%s[sfl]\d', k)}) for c in (a, b))
    if LAYOUT_CODE and '# layout:' in (e.notes or ''):     # deliberate English layout: positions may differ
        a, b = (Counter({k: v for k, v in c.items() if not LAYOUT_CODE.match(k)}) for c in (a, b))
    if a != b:
        miss, extra = list((a - b).elements()), list((b - a).elements())
        out.append(('error', 'codes', 'control codes ' + '; '.join(
            x for x in (f'missing {miss}' if miss else '', f'extra {extra}' if extra else '') if x)))
    lines = en.split('\n')
    if 'lines' in e.limits and len(lines) > e.limits['lines']:
        out.append(('error', 'lines', f'{len(lines)} lines, limit {e.limits["lines"]}'))
    if 'chars' in e.limits:
        for ln in lines:
            plain = CODE.sub('', ln)
            if len(plain) > e.limits['chars']:
                out.append(('error', 'chars', f'{len(plain)} characters, limit {e.limits["chars"]}: {ln!r}'))
    if 'max_bytes' in e.limits and e.limits.get('refs', 0) == 0 and encoded_length(en) > e.limits['max_bytes']:
        out.append(('error', 'bytes', f'{encoded_length(en)} bytes, room for {e.limits["max_bytes"]} (fixed string)'))
    n = count(en)
    if MAX_COUNT and n > MAX_COUNT:
        out.append(('error', 'room', f'{n} in one string: the game holds at most {MAX_COUNT}'))
    room = room_for(e)
    if room:
        if room[0] is not None and n > room[0]:
            out.append(('error', 'room', f'{n}, its text area holds {room[0]} ({room[2]})'))
        w = width(en)
        if room[1] is not None and w is not None and w > room[1]:
            out.append(('error', 'room', f'{w} px, room for {room[1]} ({room[2]})'))
    if SAME_LINES and en.count('\n') > e.source.count('\n'):
        out.append(('error', 'lines', f'{len(lines)} lines, the source has {e.source.count(chr(10)) + 1}'))
    src_tags = {tag_key(g) for g in TAG.findall(e.source)} if TAG else set()
    is_token = lambda g: NAME_TOKEN and NAME_TOKEN.fullmatch(g) and tag_key(g) not in src_tags
    if TAG:
        tags = lambda t: sorted(tag_key(g) for g in TAG.findall(t) if not is_token(g))
        if tags(e.source) != tags(en):
            out.append(('error', 'tags', f'tags differ from the source: {tags(e.source)} vs {tags(en)}'))
    if NAME_TOKEN:
        unknown = [t for t in NAME_TOKEN.findall(en) if is_token(t) and t not in name_tokens()]
        if unknown:
            out.append(('error', 'token', f'unknown name token(s) {unknown}'))
    if WIDER_THAN_SOURCE and not room:
        src_w, w = width(e.source), width(en)
        if src_w is not None and w is not None and w > max(src_w * WIDER_THAN_SOURCE[0], src_w + WIDER_THAN_SOURCE[1]):
            out.append(('warning', 'width', f'~{w} px wide, the source {src_w} px: check it fits on screen'))
    if any(ln != ln.rstrip() or '  ' in ln.strip() for ln in lines):
        out.append(('warning', 'spacing', f'trailing or double spaces: {en!r}'))
    for jp, accepted in terms:
        if jp in e.source and not any(x.lower() in en.lower() for x in accepted):
            out.append(('warning', 'glossary', f'{jp} should be "{" | ".join(accepted)}"'))
    out += game_check(e)
    return out


def game_check(e):
    """This game's own checks: the story page layout (tools/fpztext.py)."""
    import fpztext
    return fpztext.check_story(e)


def run(files=None, missing=False):
    """{'error': n, 'warning': n, 'missing': n, 'total': n} plus the printed lines."""
    terms = glossary()
    ents = []
    for p in files or textdb.text_files():
        ents += textdb.read_file(p)
    report, counts = [], Counter()
    for e in ents:
        counts['total'] += 1
        if not e.english:
            counts['missing'] += 1
            if missing:
                report.append(('missing', e, 'no English yet'))
            continue
        for sev, kind, msg in check_entry(e, [] if '[glossary-ok]' in e.notes else terms):
            counts[sev] += 1
            report.append((sev, e, f'{kind}: {msg}'))
    return counts, report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0], epilog=paths.FOLDER_HELP,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('files', nargs='*', type=Path, help='only these text files (default: all)')
    ap.add_argument('--missing', action='store_true', help='also list untranslated entries')
    ap.add_argument('--warnings', action='store_true', help='also list warnings')
    args = ap.parse_args(paths.configure(sys.argv[1:] if argv is None else argv))
    counts, report = run(args.files or None, args.missing)
    for sev, e, msg in report:
        if sev == 'warning' and not args.warnings:
            continue
        print(f'{e.where}: {"! " if sev == "error" else ""}{msg}')
    print(f'{counts["total"]} entries, {counts["total"] - counts["missing"]} translated: '
          f'{counts["error"]} error(s), {counts["warning"]} warning(s)'
          + ('' if args.warnings or not counts['warning'] else ' (--warnings to list them)'))
    return 1 if counts['error'] else 0


if __name__ == '__main__':
    sys.exit(main())
