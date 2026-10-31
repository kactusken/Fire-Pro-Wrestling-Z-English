#!/usr/bin/env python3
"""The moves no edit list offers, added to them (build.py group `moves`, docs/PATCHES.md).

Edit mode's 43 move lists are (pointer, u16 count, s16 list to merge in) at 0x3106F8. Move ids run
in families, so each move goes after the neighbour that is already listed; the longer lists go in
free room in the dead debug readout, after what tools/rings.py puts there. Lists are copied into
448-entry buffers (0x14E3E0): list 12 with its merges stays below that.

    patches(elf, to_offset)     codepatch entries (group `moves`)
"""
import struct

FILE = 'SLPM_623.42'
TABLE = 0x3106F8
AREA, AREA_END = 0x120C00, 0x121058
# list -> [(move id, the id it follows)]
ADD = {
    5: [(285, 284)],                                    # Phoenix Kick
    12: [(613, 612), (617, 616), (660, 659), (713, 712)],  # Eiffel de Parachute, Blazing Tornado, Muscle Buster, Deadly Go-Round
    20: [(1059, 1058)],                                 # no name in the game
}


def patches(elf, to_offset):
    blob, out = bytearray(), []
    for n, adds in ADD.items():
        entry = TABLE + n * 8
        ptr, count = struct.unpack_from('<IH', elf, to_offset(FILE, entry))
        ids = list(struct.unpack_from(f'<{count}H', elf, to_offset(FILE, ptr)))
        for move, after in adds:
            ids.insert(ids.index(after) + 1, move)
        at = AREA + len(blob)
        blob += struct.pack(f'<{len(ids)}H', *ids)
        old = bytes(elf[to_offset(FILE, entry):to_offset(FILE, entry) + 6])
        out.append(('moves', FILE, entry, old, struct.pack('<IH', at, len(ids)), None))
    if AREA + len(blob) > AREA_END:
        raise SystemExit(f'moves: the lists need {len(blob):#x} bytes, {AREA_END - AREA:#x} are free')
    out.append(('moves', FILE, AREA, bytes(elf[to_offset(FILE, AREA):to_offset(FILE, AREA) + len(blob)]), bytes(blob),
                'six unlisted moves in edit mode'))
    return out
