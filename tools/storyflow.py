#!/usr/bin/env python3
"""Story mode flow: every scene, choice, match and branch of the seven scenarios.

  storyflow.py dump [N]          print scenario N's (default all) scenes as a readable outline
  storyflow.py json OUT.json     everything as JSON (the route map in docs/guide/, docs/story_*.csv)

The .STO files are compiled scripts for a small stack machine (docs/TECHNICAL.md "Story
scripts"). Header: +0x30 symbol count, +0x34 code start; symbols at 0x40, 0x38 bytes each (name
at +5; the u32 at -4 is the code position, counted from header +0x24 + 0x20); code = 16-byte instructions (runtime pointer, opcode,
operand, value) up to the string table. Opcodes used here:
   0 load var (operand = index, value 1 local / 16 global)   1 address of var   4 assign
   2 push (operand 1 int, 2 string id)   3 pop   5 add   10 negate   11 compare (44 ==, 45 !=, 46 <, 47 <=, 48 >, 49 >=)
  12 return   13 jump (function-relative)   14 jump if false   16 call script function
  20 show a message   26 choice menu (6 layout ints, then label/caption pairs)
  28 go to scene (at once: nothing after it runs)
Script functions defined in every file: game(n) plays story match n and stores the result in
G64[n + 1]; the scenes treat a result under 2 as a win. The match native itself adds up to 3 to the
score (docs/TECHNICAL.md); gm_setp(n) adds n to the score G64[0] (never below 0), and many scenes
add to G64[0] in place. Scenes are the functions named <wrestler><number> / <wrestler>_gm<nn>.
"""
import json
import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fpz  # noqa: E402
import fpztext  # noqa: E402
import ligerstory  # noqa: E402
import storywrestlers  # noqa: E402

CMP = {44: '==', 45: '!=', 46: '<', 47: '<=', 48: '>', 49: '>='}   # op11, table 0x3A6740


def load(data):
    s = fpz.Sto(data)
    h = s.h
    syms = []
    for k in range(h[12]):
        o = 0x40 + k * 0x38
        name = data[o + 5:o + 0x30].split(b'\0')[0].decode('latin1')
        syms.append((name, struct.unpack_from('<I', data, o - 4)[0] + (h[9] + 0x20 - h[13]) // 16))
    ins = [struct.unpack_from('<3I', data, o + 4) for o in range(h[13], h[10] + 0x20, 16)]
    return s, syms, ins


def functions(ins):
    """[(start, end)] split at `push 0; return` pairs."""
    out, start = [], 0
    for i in range(1, len(ins)):
        if ins[i][0] == 12 and ins[i - 1] == (2, 1, 0):
            out.append((start, i))
            start = i + 1
    return out


class Expr(str):
    pass


def walk(s, syms, ins, start, end):
    """All paths through one function: [(conditions, events)]. Events: ('msg', id), ('goto',
    label), ('choice', [(label, caption id)]), ('game', match), ('score', +n), ('call', name)."""
    paths = []
    names = [n for n, _ in syms]

    def run(pc, stack, conds, events, seen):
        while start <= pc <= end:
            if pc in seen:                 # a loop: this path ends here
                paths.append((conds, events))
                return
            seen = seen | {pc}
            op, t, a = ins[pc]
            if op == 2:
                stack.append(Expr(f'"{s.strings[a].decode("cp932", "replace")}"' if t == 2 else str(a)))
                if t == 2:
                    stack[-1].sid = a
            elif op == 0:
                if a == 16:
                    idx = stack.pop() if stack else '?'
                    stack.append(Expr('score' if (t == 64 and idx == '0') else
                                      f'match{int(idx) - 1}' if t == 64 and idx.isdigit() else f'G{t}[{idx}]'))
                else:
                    stack.append(Expr(f'L{t}'))
            elif op == 1:
                if a == 16:
                    idx = stack.pop() if stack else '?'
                    stack.append(Expr(f'&G{t}[{idx}]'))
                else:
                    stack.append(Expr(f'&L{t}'))
            elif op == 4:
                v = stack.pop() if stack else '?'
                dst = stack.pop() if stack else '?'
                stack.append(v)
                m = re.fullmatch(r'score\+(-?\d+)', v)
                if dst == '&G64[0]' and m:              # the score raised in place, not via gm_setp
                    events.append(('score', int(m.group(1))))
                if dst.startswith('&L'):
                    if v.startswith('game('):
                        events.append(('game', int(v[5:-1])))
                    locals_[dst[1:]] = v      # a copy of the score or a match result
            elif op == 3:
                if stack:
                    stack.pop()
            elif op == 5:
                b, a_ = stack.pop(), stack.pop()
                stack.append(Expr(f'{a_}+{b}'))
            elif op == 11:
                b, a_ = stack.pop(), stack.pop()
                a_ = locals_.get(a_, a_)
                if a_.startswith('game('):
                    a_ = f'result(match {a_[5:-1]})'
                stack.append(Expr(f'{a_} {CMP.get(t, "?")} {b}'))
            elif op == 14:
                c = stack.pop() if stack else '?'
                run(start + t, list(stack), conds + [f'not ({c})'], list(events), seen)
                conds = conds + [c]
            elif op == 13:
                pc = start + t
                continue
            elif op == 12:
                paths.append((conds, events))
                return
            elif op == 16:
                name = names[t] if t < len(names) else f'fn{t}'
                argc = {'game': 1, 'gm_setp': 1}.get(name)
                if name == 'game':
                    arg = stack.pop() if stack else '?'
                    stack.append(Expr(f'game({arg})'))
                elif name == 'gm_setp':
                    arg = stack.pop() if stack else '?'
                    events.append(('score', int(arg) if arg.lstrip('-').isdigit() else arg))
                    stack.append(Expr('0'))
                else:
                    stack.append(Expr('0'))
            elif op == 20:
                m = stack.pop() if stack else None
                if m is not None and hasattr(m, 'sid'):
                    events.append(('msg', m.sid))
                stack.append(Expr('0'))
            elif op == 26:
                n = t
                items = stack[-n:] if n else []
                del stack[-n:]
                pairs = [(items[k].strip('"'), items[k + 1].sid) for k in range(6, len(items) - 1, 2)]
                events.append(('choice', pairs))
                stack.append(Expr('0'))
            elif op == 28:
                lab = stack.pop() if stack else '?'
                events.append(('goto', lab.strip('"')))
                paths.append((conds, events))      # the new scene starts at once
                return
            elif op in (19, 23, 27, 29, 30, 31):
                n = t
                del stack[-n:]
                stack.append(Expr('0'))
            elif op == 10:                  # unary minus (handler 0x1E7AC8)
                v = stack.pop()
                stack.append(Expr(str(-int(v)) if v.lstrip('-').isdigit() else f'(-{v})'))
            elif op in (6, 7, 8, 9, 21, 22, 24, 25):
                if len(stack) >= 2:
                    b, a_ = stack.pop(), stack.pop()
                    stack.append(Expr(f'({a_} op{op} {b})'))
            pc += 1
        paths.append((conds, events))

    locals_ = {}
    run(start, [], [], [], frozenset())
    return paths


SHARED = 38


def scene_functions(s, syms, ins):
    """[(label, (start, end))]: each scene label (the symbols after the 38 shared script functions)
    with the function holding its code position. A trailing stub function has no label."""
    funcs = functions(ins)
    return [(name, next(f for f in funcs if f[0] <= pos <= f[1])) for name, pos in syms[SHARED:]]


def scenario(n):
    """The scenario as players get it: scenario 7 can only be played rebuilt (tools/ligerstory.py)."""
    data = fpztext.story_archive().read(f'SCENA\\STORY0{n}.STO')
    if n == 7:
        data = ligerstory.restore(data, storywrestlers.slots())
    s, syms, ins = load(data)
    scenes = {}
    for name, f in scene_functions(s, syms, ins):
        scenes[name] = {'range': f, 'paths': walk(s, syms, ins, *f)}
    return s, scenes


def summary(paths):
    """Merge paths into: messages (in order, deduplicated), matches, choices, exits with
    conditions, score changes per path."""
    msgs, matches, choices, exits = [], [], [], []
    for conds, ev in paths:
        for e in ev:
            if e[0] == 'msg' and e[1] not in msgs:
                msgs.append(e[1])
            if e[0] == 'game' and e[1] not in matches:
                matches.append(e[1])
            if e[0] == 'choice' and e[1] not in choices:
                choices.append(e[1])
        gotos = [e[1] for e in ev if e[0] == 'goto']
        score = sum(e[1] for e in ev if e[0] == 'score' and isinstance(e[1], int))
        c = [x for x in conds if not x.startswith('not (L') or True]
        exits.append({'to': gotos[-1] if gotos else None, 'when': c, 'score': score})
    # drop duplicate exits
    seen, uniq = set(), []
    for x in exits:
        k = (x['to'], tuple(x['when']), x['score'])
        if k not in seen:
            seen.add(k)
            uniq.append(x)
    return msgs, matches, choices, uniq


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in ('dump', 'json'):
        print(__doc__)
        return 1
    if argv[0] == 'dump':
        ns = [int(argv[1])] if len(argv) > 1 else range(1, 8)
        for n in ns:
            s, scenes = scenario(n)
            print(f'##### scenario {n}: {len(scenes)} scenes')
            for name, sc in sorted(scenes.items(), key=lambda kv: kv[1]['range'][0], reverse=True):
                msgs, matches, choices, exits = summary(sc['paths'])
                first = s.strings[msgs[0]].decode('cp932', 'replace').replace('\r\n', ' ')[:60] if msgs else ''
                print(f'{name}  msgs {msgs[:1]}..{msgs[-1:]}  {first}')
                for m in matches:
                    print(f'   match {m}')
                for ch in choices:
                    for lab, cid in ch:
                        print(f'   choice -> {lab}: {s.strings[cid].decode("cp932", "replace")}')
                for x in exits:
                    if x['to'] or x['when'] or x['score']:
                        print(f'   exit -> {x["to"]}  if {" and ".join(x["when"]) or "always"}  score {x["score"]:+d}')
        return 0
    out = {}
    for n in range(1, 8):
        s, scenes = scenario(n)
        out[n] = {}
        for name, sc in scenes.items():
            msgs, matches, choices, exits = summary(sc['paths'])
            out[n][name] = {'start': sc['range'][0], 'messages': msgs, 'matches': matches,
                            'choices': [[{'to': lab, 'caption': cid} for lab, cid in ch] for ch in choices],
                            'exits': exits}
    Path(argv[1]).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'{argv[1]}: {sum(len(v) for v in out.values())} scenes')
    return 0


if __name__ == '__main__':
    sys.exit(main())
