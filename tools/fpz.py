#!/usr/bin/env python3
"""Fire Pro Wrestling Z file formats: readers and writers (docs/TECHNICAL.md has the layouts).

  fpz.py oah list <file.OAH>               the archive's entries: sector, size, name
  fpz.py oah extract <file.OAH> <outdir>   every entry (nested archives stay packed)
  fpz.py sto <file.STO> [index...]         the story file's strings (all, or the given indexes)
  fpz.py roster <STRHUMAN.BIN>             the roster's names
  fpz.py roundtrip                         rebuild every archive, story file, the roster and the
                                           move list from extracted/ and compare byte for byte

Standard library only (the build imports it). Every format has a reader and a writer; roundtrip
proves each writer gives the original bytes back when nothing changed.
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402

SECTOR = 2048
ENC = 'cp932'


# ---------------------------------------------------------------- .OAH hashed archives

def oah_hash(name):
    """The game's bucket for a name (0x101080): byte sum, a-z uppercased, & 0x1FF."""
    return sum(c - 0x20 if 0x61 <= c <= 0x7A else c for c in name) & 0x1FF


class Oah:
    """An .OAH archive. entries: name -> [size, sector, field offset] (sector relative to the data
    start); order: names by sector. Writes go in place when the data fits the entry's sectors,
    else after the last entry; the directory keeps its layout."""

    def __init__(self, data):
        self.data = bytearray(data)
        w0 = struct.unpack_from('<i', data, 0)[0]
        self.dir_sectors = abs(w0)
        buckets = list(struct.unpack_from('<512i', data, 0))
        buckets[0] = 0 if w0 >= 0 else -1
        self.entries = {}
        for h, off in enumerate(buckets):
            if off < 0:
                continue
            p = SECTOR + off
            while data[p]:
                e = data.index(b'\0', p)
                name = bytes(data[p:e])
                if oah_hash(name) != h:
                    raise ValueError(f'{name!r}: in bucket {h}, hashes to {oah_hash(name)}')
                size, sec = struct.unpack_from('<II', data, e + 1)
                self.entries[name.decode(ENC)] = [size, sec, e + 1]
                p = e + 9
        self.base = (1 + self.dir_sectors) * SECTOR

    def names(self):
        return sorted(self.entries, key=lambda n: self.entries[n][1])

    def read(self, name):
        size, sec, _ = self.entries[name]
        return bytes(self.data[self.base + sec * SECTOR:self.base + sec * SECTOR + size])

    def room(self, name):
        """Sectors from the entry's start to the next entry's (or the end of the archive)."""
        sec = self.entries[name][1]
        later = [s for _, s, _ in self.entries.values() if s > sec]
        end = min(later) if later else (len(self.data) - self.base) // SECTOR
        return end - sec

    def write(self, name, blob):
        size, sec, field = self.entries[name]
        need = (len(blob) + SECTOR - 1) // SECTOR
        if need > self.room(name):
            sec = (len(self.data) - self.base + SECTOR - 1) // SECTOR
            self.data.extend(bytes(self.base + (sec + need) * SECTOR - len(self.data)))
        start = self.base + sec * SECTOR
        old_end = start + ((size + SECTOR - 1) // SECTOR) * SECTOR if sec == self.entries[name][1] else start
        self.data[start:start + len(blob)] = blob
        pad_end = max(start + need * SECTOR, old_end)
        self.data[start + len(blob):pad_end] = bytes(pad_end - start - len(blob))
        struct.pack_into('<II', self.data, field, len(blob), sec)
        self.entries[name] = [len(blob), sec, field]

    def bytes(self):
        return bytes(self.data)


# ---------------------------------------------------------------- CP00 compression (.LZO)

def cp00_decode(data):
    """Unpack a CP00 file (decoder 0x103000 - from the code): u16 tokens, top nibble 0 = a run of
    (low 12 bits + 1) literal words; else copy N words from (low 12 bits + 1) words back, N = the
    top nibble, or the next u16 when it is 15."""
    if data[:4] != b'CP00':
        raise ValueError('not a CP00 file')
    size, out_size = struct.unpack_from('<II', data, 4)
    src = memoryview(data)[16:16 + size]
    n = (size + 1) // 2
    h = struct.unpack_from(f'<{n}H', bytes(src).ljust(n * 2, b'\0'))
    out = []
    i = 0
    while i < n:
        tok = h[i]
        top, low = tok >> 12, tok & 0xFFF
        if top == 0:
            for k in range(low + 1):
                out.append(h[i + 1 + 2 * k] | h[i + 2 + 2 * k] << 16)
            i += 2 * (low + 1) + 1
            continue
        if top == 15:
            top = h[i + 1]
            i += 2
        else:
            i += 1
        start = len(out) - low - 1
        for k in range(top):
            out.append(out[start + k])
    blob = struct.pack(f'<{len(out)}I', *out)
    return blob[:out_size]


def cp00_encode(blob):
    """Pack data as CP00 (greedy, matches of 2+ words within 4096 words back)."""
    pad = bytes(blob) + bytes(-len(blob) % 4)
    w = struct.unpack(f'<{len(pad) // 4}I', pad)
    toks, lits, last = [], [], {}

    def flush():
        while lits:
            run, rest = lits[:4096], lits[4096:]
            toks.append(len(run) - 1)
            for v in run:
                toks.extend((v & 0xFFFF, v >> 16))
            lits[:] = rest

    i, n = 0, len(w)
    while i < n:
        best_len, best_d = 0, 0
        if i + 1 < n:
            for j in reversed(last.get((w[i], w[i + 1]), [])):
                d = i - j
                if d > 4096:
                    break
                k = 2
                while i + k < n and w[j + k] == w[i + k] and k < 0xFFFF:
                    k += 1
                if k > best_len:
                    best_len, best_d = k, d
                    if k >= 64:
                        break
        if best_len >= 2:
            flush()
            if best_len < 15:
                toks.append(best_len << 12 | (best_d - 1))
            else:
                toks += [0xF000 | (best_d - 1), best_len]
            for k in range(best_len):
                if i + k + 1 < n:
                    last.setdefault((w[i + k], w[i + k + 1]), []).append(i + k)
            i += best_len
        else:
            lits.append(w[i])
            if i + 1 < n:
                last.setdefault((w[i], w[i + 1]), []).append(i)
            i += 1
    flush()
    body = struct.pack(f'<{len(toks)}H', *toks)
    return b'CP00' + struct.pack('<III', len(body), len(blob), 0) + body


# ---------------------------------------------------------------- .STO story scripts

class Sto:
    """A story file. strings: the table's strings in table order (bytes, no NUL); names: the
    16-byte name records after +0x1C. Each string keeps whatever followed its NUL up to the next
    string (gaps), so an unchanged file rebuilds byte for byte."""

    def __init__(self, data):
        self.data = bytes(data)
        if data[:4] != b'STO\0':
            raise ValueError('not an STO file')
        self.h = list(struct.unpack_from('<16I', data, 0))
        self.table = self.h[10] + 0x20
        self.pool = self.h[11] + 0x20
        n = (self.pool - self.table) // 4
        self.offsets = list(struct.unpack_from(f'<{n}I', data, self.table))
        starts = sorted(set(self.offsets))
        pool_len = self.h[4] - self.pool
        self.pieces = {}   # offset -> (string, gap after its NUL)
        for i, o in enumerate(starts):
            end = starts[i + 1] if i + 1 < len(starts) else pool_len
            raw = data[self.pool + o:self.pool + end]
            z = raw.index(b'\0')
            self.pieces[o] = (raw[:z], raw[z + 1:])
        self.strings = [self.pieces[o][0] for o in self.offsets]
        self.names = [data[k:k + 16] for k in range(self.h[7], len(data), 16)]

    def build(self, strings=None, names=None):
        """The file with new strings (list, table order) and names (list of str/bytes, 15 bytes
        at most); strings whose table entries share an offset must stay equal."""
        strings = self.strings if strings is None else strings
        by_off = {}
        for o, s in zip(self.offsets, strings):
            if by_off.setdefault(o, s) != s:
                raise ValueError(f'table entries sharing offset {o:#x} got different strings')
        pool, new_off = bytearray(), {}
        for o in sorted(self.pieces):
            new_off[o] = len(pool)
            pool += by_off[o] + b'\0' + self.pieces[o][1]
        old_len = self.h[4] - self.pool
        if len(pool) < old_len and strings is self.strings:
            pass
        pool += bytes(-len(pool) % 4)
        delta = len(pool) - old_len
        out = bytearray(self.data[:self.pool]) + pool + self.data[self.h[4]:]
        struct.pack_into(f'<{len(self.offsets)}I', out, self.table, *[new_off[o] for o in self.offsets])
        for k in (4, 5, 7):
            struct.pack_into('<I', out, k * 4, self.h[k] + delta)
        if names is not None:
            tail = self.h[7] + delta
            for i, nm in enumerate(names):
                b = nm.encode(ENC) if isinstance(nm, str) else nm
                if len(b) > 15:
                    raise ValueError(f'story name {nm!r}: {len(b)} bytes, 15 at most')
                if b != self.names[i].split(b'\0')[0]:
                    out[tail + i * 16:tail + i * 16 + 16] = b.ljust(16, b'\0')
        return bytes(out)


# ---------------------------------------------------------------- roster and moves

ROSTER_RECORD = 0x23C
ROSTER_FIELDS = (('name1', 2, 14), ('name2', 0x10, 20), ('nick', 0x24, 26))


def roster(data):
    """[(flags, {field: bytes})] for every wrestler in STRHUMAN.BIN."""
    out = []
    for i in range(len(data) // ROSTER_RECORD):
        r = data[i * ROSTER_RECORD:(i + 1) * ROSTER_RECORD]
        out.append((r[1], {f: bytes(r[o:o + n]).split(b'\0')[0] for f, o, n in ROSTER_FIELDS}))
    return out


def put_roster_field(data, index, field, value):
    """Write one name field (bytes) in place: NUL-terminated, the rest of the field zeroed."""
    f, o, n = next(x for x in ROSTER_FIELDS if x[0] == field)
    if len(value) >= n:
        raise ValueError(f'roster {index} {field}: {len(value)} bytes, {n - 1} at most')
    at = index * ROSTER_RECORD + o
    if bytes(data[at:at + len(value) + 1]) != value + b'\0':
        data[at:at + n] = value.ljust(n, b'\0')


def moves(data):
    """The move names of WAZA.BIN (bytes, by move id) and whether the offsets are in order."""
    n = struct.unpack_from('<H', data, 0)[0] // 2
    offs = struct.unpack_from(f'<{n}H', data, 0)
    return [bytes(data[o:data.index(b'\0', o)]) for o in offs]


def build_moves(names, size=None, share=False):
    """WAZA.BIN from names: the offset table, then the names (share: a repeated name is stored
    once - the original stores every copy)."""
    head = len(names) * 2
    body, where = bytearray(), {}
    offs = []
    for nm in names:
        if nm not in where or not share:
            where[nm] = head + len(body)
            body += nm + b'\0'
        offs.append(where[nm])
    if head + len(body) > 0xFFFF:
        raise ValueError(f'move names: {head + len(body)} bytes, over the u16 offsets')
    out = struct.pack(f'<{len(names)}H', *offs) + bytes(body)
    return out if size is None or len(out) >= size else out.ljust(size, b'\0')


# ---------------------------------------------------------------- checks

def roundtrip():
    ok = True
    x = paths.EXTRACTED

    def same(label, a, b):
        nonlocal ok
        good = a == b
        ok &= good
        print(f'{"ok  " if good else "FAIL"} {label}')

    archives = {}
    for name in ('STORY.OAH', 'FPFILES.OAH', 'WRSPARTS.OAH', 'INFPARTS.OAH'):
        a = Oah((x / name).read_bytes())
        archives[name] = a
        b = Oah(a.bytes())
        for n in a.names():
            b.write(n, a.read(n))
        same(f'{name}: {len(a.entries)} entries rewritten in place', b.bytes(), a.bytes())
    st = archives['STORY.OAH']
    for n in st.names():
        if n.endswith('.STO'):
            s = Sto(st.read(n))
            same(f'{n}: {len(s.strings)} strings, {len(s.names)} names rebuilt', s.build(), st.read(n))
    for n in archives['FPFILES.OAH'].names():
        if n.endswith('.OAH'):
            inner = Oah(archives['FPFILES.OAH'].read(n))
            b = Oah(inner.bytes())
            for m in inner.names():
                b.write(m, inner.read(m))
            same(f'{n}: {len(inner.entries)} entries', b.bytes(), inner.bytes())
    data = bytearray((x / 'STRHUMAN.BIN').read_bytes())
    orig = bytes(data)
    for i, (_, f) in enumerate(roster(data)):
        for k, v in f.items():
            put_roster_field(data, i, k, v)
    same(f'STRHUMAN.BIN: {len(data) // ROSTER_RECORD} wrestlers rewritten', bytes(data), orig)
    w = (x / 'WAZA.BIN').read_bytes()
    same(f'WAZA.BIN: {len(moves(w))} moves rebuilt', build_moves(moves(w), len(w)), w)
    return ok


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__)
        return 0
    cmd = argv[0]
    if cmd == 'roundtrip':
        return 0 if roundtrip() else 1
    if cmd == 'oah' and len(argv) >= 3:
        a = Oah(Path(argv[2]).read_bytes())
        for n in a.names():
            if argv[1] == 'list':
                print(f'{a.entries[n][1]:7d} {a.entries[n][0]:10d}  {n}')
            else:
                p = Path(argv[3]) / n.replace('\\', '/')
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(a.read(n))
        return 0
    if cmd == 'sto' and len(argv) >= 2:
        s = Sto(Path(argv[1]).read_bytes())
        pick = [int(i) for i in argv[2:]] or range(len(s.strings))
        for i in pick:
            print(f'--- {i}\n{s.strings[i].decode(ENC, "replace")}')
        return 0
    if cmd == 'roster' and len(argv) >= 2:
        for i, (fl, f) in enumerate(roster(Path(argv[1]).read_bytes())):
            print(i, f'{fl:02x}', *(v.decode(ENC, 'replace') for v in f.values()), sep='\t')
        return 0
    print(__doc__)
    return 1


if __name__ == '__main__':
    sys.exit(main())
