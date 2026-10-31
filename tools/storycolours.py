#!/usr/bin/env python3
"""Story text colours, made consistent (docs/TECHNICAL.md "Story colours").

The story draws the hero in white (%c0) and everyone else in yellow (%c1). Stories 1-6 hold to that
but for a few pages, and scenario 7 never had the pass. fix() is called by fpztext.step_story for
every story message, on each page: it reads the speaker from the original text and sets the colour
of the page's codes, adding one code where the page needs it and has none. Pages with no speaker
keep what they have, so they follow the page before them.
"""
import re

# The hero's labels: %ssN or a story name, with the hero's other ring names
HEROES = {
    1: {'%ss66'}, 2: {'%ss132'}, 3: {'%ss88'}, 4: {'%ss21'},
    5: {'%ss42', '%ss43', '暗黒坊'},                # Mutoh, The Great Muta, Kokushi Muso
    6: {'%ss100', 'ティグレ', 'キラー・%ss37'},      # Sakuraba, Tigre, Killer Tiger Mask
    7: {'ライガー', '山田'},
}
CODE = re.compile(rb'%c\d')


def speaker(page):
    """A page's speaker label ('' for none): its first line, with or without the colon, when text
    follows; without the colon only a name counts (not a heading such as ―アメリカ)."""
    lines = [ln for ln in (re.sub(r'%c\d', '', x).strip() for x in page.split('\r\n')) if ln]
    if len(lines) < 2:
        return ''
    first = lines[0]
    if first.endswith('：') and len(first) <= 16 and '「' not in first:
        return first[:-1]
    return first if re.fullmatch(r'%ss\d+|山田|ライガー', first) else ''


def fix(n, pages):
    """pages: [(original page text, page bytes)] of one message. The new page bytes."""
    out = []
    active = None
    for text, data in pages:
        label = speaker(text)
        has = CODE.findall(data)
        if label:
            want = b'0' if label in HEROES[n] else b'1'
            if has:
                data = CODE.sub(b'%c' + want, data)
            elif active != want:
                head = re.match(rb'(?:\r\n)*', data).end()
                data = data[:head] + b'%c' + want + data[head:]
            active = want
        elif has:
            active = has[-1][-1:]
        out.append(data)
    return out
