#!/usr/bin/env python3
"""Test cheats: a PCSX2 .pnach file that makes rare or late screens reachable on demand.

  python3 tools/pnach.py [IMAGE] [--out DIR]    write <DIR>/<SERIAL>_<CRC>.pnach for a build
                                                (default: the newest build/*.iso, into build/cheats/)

PCSX2 finds a cheat file by the executable's CRC (the XOR of its 32-bit words), which changes with
every build - write a new file for each build. The tester copies it into PCSX2's `cheats` folder
and turns single cheats on and off in the game's Properties > Cheats while playing: each
[section] is one cheat. Describe what each does and what to watch out for ("Save first",
"turn off again after one month") - the descriptions are what the tester reads. Pair the file
with a recipe list (which cheats reach which screen) in the test notes.

Fill CHEATS with the game's addresses (*from the code*; say where each is documented). A cheat
that writes save data keeps its effect after it is turned off - prefer one that only changes RAM,
or say so in its description. From Wrestle Angels Survivor (tools/cheats.py there: event chances,
money, wrestler stats, month, gallery, hidden roster).
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402

# (section, description, [(type, address, value)]) - type: byte, short, word (EE memory)
# Sections with a backslash group the cheats in PCSX2's list: 'Money\\AP 99,999'.
CHEATS = [
    # ('Calendar\\Month = November (turn off again!)', 'Jumps to November so the December events come '
    #  'soon. Turn it on, end the month once, turn it off.', [('byte', 0x82aef3, 11)]),
]


def crc(elf):
    """PCSX2's game CRC: the XOR of the executable's 32-bit words."""
    c = 0
    for i in range(0, len(elf) - len(elf) % 4, 4):
        c ^= int.from_bytes(elf[i:i + 4], 'little')
    return c


def boot_file(d):
    """The executable SYSTEM.CNF boots, as a disc path ('/SLPM_662.39')."""
    cnf = d.read_file(d.find('/SYSTEM.CNF')).decode('ascii', 'replace')
    m = re.search(r'BOOT2\s*=\s*cdrom0:\\?([^;\s]+)', cnf)
    if not m:
        sys.exit('SYSTEM.CNF has no BOOT2 line')
    return '/' + m.group(1).replace('\\', '/')


def pnach(game_crc):
    serial = getattr(paths, 'SERIAL', '') or 'unknown serial'
    out = [f'gametitle={paths.GAME} ({serial})',
           f'comment=Test cheats for the executable with CRC {game_crc:08X}; turn single cheats on in the '
           "game's properties", '']
    for name, desc, lines in CHEATS:
        out += [f'[{name}]', f'description={desc}']
        out += [f'patch=1,EE,{a:08X},{kind},{v & 0xffffffff:08X}' for kind, a, v in lines]
        out.append('')
    return '\n'.join(out)


def write(out, game_crc):
    """Write the cheat file for an executable CRC into folder out; returns its path."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    serial = (getattr(paths, 'SERIAL', '') or 'GAME').replace('_', '-')
    f = out / f'{serial}_{game_crc:08X}.pnach'
    f.write_text(pnach(game_crc), encoding='utf-8')
    return f


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0], epilog=paths.FOLDER_HELP,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('image', nargs='?', type=Path, help='the build (default: the newest build/*.iso)')
    ap.add_argument('--out', type=Path, help='output folder (default: build/cheats/)')
    args = ap.parse_args(paths.configure(sys.argv[1:] if argv is None else argv))
    if not CHEATS:
        sys.exit('CHEATS is empty: add the game\'s cheats to tools/pnach.py first')
    import disc
    builds = sorted(paths.BUILD.glob('*.iso'), key=lambda p: p.stat().st_mtime)
    image = args.image or (builds[-1] if builds else None)
    if image is None:
        sys.exit(f'no build in {paths.show(paths.BUILD)}: give the image')
    d = disc.Disc(str(image))
    game_crc = crc(d.read_file(d.find(boot_file(d))))
    f = write(args.out or paths.BUILD / 'cheats', game_crc)
    print(f'{image.name}: CRC {game_crc:08X} -> {paths.show(f)} ({len(CHEATS)} cheats)')


if __name__ == '__main__':
    main()
