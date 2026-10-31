# Technical notes - Fire Pro Wrestling Z

**Conventions:** numbers in hex with `0x`; addresses are RAM addresses unless marked as file
offsets; `u16`/`u32` little-endian unless marked BE. Findings are marked *verified in game* or
*from the code*.

## Contents
- [Image](#image) · [Disc layout](#disc-layout) · [Executable and memory](#executable-and-memory)
- [Archives and compression](#archives-and-compression) · [Text](#text) · [Story scripts](#story-scripts) · [Images](#images)
- [Open questions](#open-questions)

## Image
`Fire Pro Wrestling Z (Japan).bin`, 462422016 bytes, SHA-1 `da2a656e562cb85db3ececacc0d483eb650cb782`.
Redump: *Fire Pro Wrestling Z (Japan)*, serial SLPM-62342 (`SYSTEM.CNF` VER 1.01), a CD-ROM: one
MODE2/2352 track, every sector form 1 (`tools/disc.py` reads the user data and regenerates EDC/ECC
on every sector it writes). Spike, released 2003-06-05; developed by S-NEO and Paon DP.

**Prior art (2026-10-29).** The only English work found is Fatman Dave's menu patch v0.5b
(2004-04-23, "small menu patch, translates some menus", unfinished and abandoned, base CRC32
5A32AF02). No public documentation or tools for this game's formats (`.OAH`, `.TAC`, `.CFF`,
`WAZA.BIN`, `STRHUMAN.BIN`, `ZSTA.ZZZ`, `FEPDIC/FEPIDX.DAT`). The nearest tools are freem's for
the sequel *Fire Pro Wrestling Returns* (https://firepro.ajworld.net/: logo, VPF0 texture,
wrestler-edit tools), which may share some formats - unchecked.

## Disc layout
| LBA | Size | File | Contents |
|---|---|---|---|
| 25 | 90805 | `/MODULES/MCMAN.IRX` |  |
| 70 | 7353 | `/MODULES/MCSERV.IRX` |  |
| 74 | 11013 | `/MODULES/MTAPMAN.IRX` |  |
| 80 | 43861 | `/MODULES/PADMAN.IRX` |  |
| 102 | 6553 | `/MODULES/SIO2MAN.IRX` |  |
| 106 | 59509 | `/MODULES/MODHSYN.IRX` |  |
| 136 | 253201 | `/MODULES/IOPRP243.IMG` |  |
| 260 | 21101 | `/MODULES/MODMIDI.IRX` |  |
| 271 | 25397 | `/MODULES/LIBSD.IRX` |  |
| 284 | 21245 | `/MODULES/FPSOUND.IRX` |  |
| 295 | 701248 | `/SND/SCENARIO.BD` |  |
| 638 | 1126896 | `/SND/VE1.BD` |  |
| 1189 | 1113776 | `/SND/VE2.BD` |  |
| 1733 | 1212256 | `/SND/VE3.BD` |  |
| 2325 | 1138976 | `/SND/VM1.BD` |  |
| 2882 | 975840 | `/SND/VM2.BD` |  |
| 3359 | 1064928 | `/SND/VM3.BD` |  |
| 3879 | 1212096 | `/SND/VM4.BD` |  |
| 4471 | 1156336 | `/SND/VM5.BD` |  |
| 5036 | 1161776 | `/SND/VW1.BD` |  |
| 5604 | 1035328 | `/SND/VW2.BD` |  |
| 6110 | 1001888 | `/SND/VW3.BD` |  |
| 6600 | 8256 | `/SND/SCENARIO.HD` |  |
| 6605 | 12336 | `/SND/VE1.HD` |  |
| 6612 | 12336 | `/SND/VE2.HD` |  |
| 6619 | 12336 | `/SND/VE3.HD` |  |
| 6626 | 12336 | `/SND/VM1.HD` |  |
| 6633 | 12336 | `/SND/VM2.HD` |  |
| 6640 | 12336 | `/SND/VM3.HD` |  |
| 6647 | 12336 | `/SND/VM4.HD` |  |
| 6654 | 12336 | `/SND/VM5.HD` |  |
| 6661 | 12336 | `/SND/VW1.HD` |  |
| 6668 | 12336 | `/SND/VW2.HD` |  |
| 6675 | 12336 | `/SND/VW3.HD` |  |
| 6682 | 13783040 | `/WRSPARTS.OAH` |  |
| 13412 | 325358 | `/FEPIDX.DAT` |  |
| 13571 | 51783680 | `/FPFILES.OAH` |  |
| 38856 | 5400000 | `/GODAFORM.CFF` |  |
| 41493 | 1298440 | `/GODAWAZA.BIN` |  |
| 42128 | 2039808 | `/INFPARTS.OAH` |  |
| 43124 | 147616 | `/LOGO.TAC` |  |
| 43197 | 105984 | `/PALET.TAC` |  |
| 43249 | 2851048 | `/SLPM_623.42` |  |
| 44642 | 27992064 | `/STORY.OAH` |  |
| 58310 | 139568 | `/STRHUMAN.BIN` |  |
| 58379 | 57 | `/SYSTEM.CNF` |  |
| 58380 | 34048 | `/WAZA.BIN` |  |
| 58397 | 206839 | `/FEPDIC.DAT` |  |
| 58498 | 282542080 | `/ZSTA.ZZZ` |  |

## Executable and memory
`SLPM_623.42`: ELF with section headers but no symbols. Entry 0x100008. `.text` 0x100000
(file 0x1000), `.data` 0x213e80 (file 0x114e80, 1.5 MB), `.rodata` 0x393c80 (file 0x294c80),
`.sdata` 0x3aa200 (file 0x2ab200); RAM address = file offset + 0xFF000 for all of them.

## Archives and compression
**.OAH** (`TARCHIVE_HASH`, lookup at 0x101080 - *from the code*, checked on every archive): sector 0
is 512 u32 hash buckets, each an offset into the directory (sector 1 on, -1 = empty). Word 0
doubles as the directory size in sectors: negative = -size (bucket 0 empty), else size (bucket 0
at offset 0). A bucket's chain: name (Shift-JIS/ASCII, `\` for folders), NUL, u32 size, u32
sector (relative to the data start, sector 1 + directory size), unaligned; an empty name ends it.
Hash: sum of the name's bytes, lowercase a-z uppercased, & 0x1FF. Archives nest
(`FPFILES.OAH` holds `EDITMENU\MAINMENU.OAH` etc.).
- `STORY.OAH`: `SCENA\STORY01-07.STO` (story scripts), story pictures (`.LZO`), `AETC\*`.
- `FPFILES.OAH`: menu textures (`EDITMENU\*.GST/.LZO`, nested `.OAH`), arenas, cameras,
  entrances, `VOICE\*.VB` (1066 voice clips).
- `WRSPARTS.OAH` / `INFPARTS.OAH`: wrestler face/body parts (`.LZO`), big and small.

**CP00** (`.LZO`): `CP00`, u32 compressed size?, u32 decompressed size, then the data (format not
yet decoded). Inside: usually a `P2TXB` texture. **P2TXB** (`.GST`): 0x40-byte header, 1 KB
palette (RGBA, alpha 0x80 = opaque), 8bpp pixels (e.g. 66624 = 256x256).

Not text: `ZSTA.ZZZ` (283 MB, PS2 ADPCM audio), `GODAFORM.CFF` / `GODAWAZA.BIN` (motion data),
`FEPIDX.DAT` / `FEPDIC.DAT` (the kana-kanji conversion dictionary of the name entry).

## Text
**How it is drawn** (*seen headless, 2026-10-29*): Shift-JIS, drawn live from a font that has
ASCII and half-width katakana as well as full-width characters. Half-width characters are fixed
width, half a full-width cell (`M` and `m` look cramped). English in single-byte ASCII gets twice
the characters of the Japanese. Many menu labels are pictures (the main menu entries, with small
English subtitles already in them).

**Where the text is:**
- `SLPM_623.42` - menus, options, edit-mode parts, costume names, voice shouts, commentary,
  memory card messages, credits: NUL-terminated Shift-JIS (half-width katakana in places), mostly
  reached through 32-bit pointers in `.data` (1985 strings) or `lui`/`addiu` pairs in the code
  (220). Pools: 0x2950c0-0x295830 (countries), 0x299060-0x2a4ce8 (the main pool, ~26 KB),
  0x2ab240-0x2ad888 (`.sdata`: a full-width character table, then short labels). Fixed records
  with no pointers: promotions at 0x1160d0 (stride 0xD0?), the name-entry grid at 0x2a1910
  (15 characters a row, 32 bytes a row).
- `STRHUMAN.BIN` - the roster: 244 records of 0x23C bytes, the same layout as Fire Pro Wrestling
  D: +0 class, +1 flags (bit 7 name2 first; bits 0-1 separator), +2 name1 (14 bytes, the short
  name), +0x10 name2 (20), +0x24 nickname (26), then stats. Fields are NUL-terminated; bytes after
  the NUL are leftovers.
- `WAZA.BIN` - 1845 move names: u16 offsets (move id -> name), then NUL-terminated names.
- `STORY.OAH` `SCENA\STORY0N.STO` - the story mode, one file per scenario (2836 messages,
  ~312,000 characters). Header (u32): +0 `STO`, +0x10 pool end, +0x14 / +0x1C next sections, +0x28
  the string table (0x20-byte header, then u32 offsets from the pool start, one per string), +0x2C
  pool start - 0x20. Messages are pages of `\r\n` lines ending `%k`; the last section (from
  +0x1C) holds 16-byte story-only names (ネベロ, 初代パンサー...).
  Codes: `%ssN` roster N's short name (12,213 uses: speaker labels `%ss132：`, and in the text),
  `%k` wait for a key, `%k2`, `%c0`/`%c1` colour, `%px`/`%py` position, `%bx`/`%by` scale,
  `%m`, `%w`, `%t` (result screens), `%sw`/`%st`/`%sk`/`%s` match results.

**Zeros after a string aren't always free** (*seen headless, 2026-10-30*): `.sdata` variables are
zero on disc. `fpztext.room_cap` stops a string's room at the first gp-relative load or store; before
that, "GJ Army" was packed against the pointer at 0x3AA8E0 and lost its terminator at run time.
It also stops at empty strings a pointer aims at: "Affinity" landed on 0x3AB898, the move editor's
blank rows, and showed on them.
Code references with the lui in a delay slot are listed in `fpztext.BRANCHED_REFS`.

**Story backgrounds** (*seen headless, 2026-10-30*): 640x448 at 8 bits with the palette at +0x20, though
`tools/gfx.py` exports them as 256x1120 strips.

**Ring textures** (*from the data, 2026-10-30*): `MAT_*` `.GST` are P2TXB files like the menu art, but
their palette starts at +0x20, not +0x40 (pixels still at +0x440). `tools/gfx.py` assumes +0x40, so it
exports them with speckled colours. Neighbouring-pixel difference picks the right offset.

**Fonts** (*verified headless, 2026-10-29*): `BOOTREAD\SCE20I22.GF` (22x22) and `AETC\SCE24I26.GF`
(26x26; also in `STORY.OAH`, with CP00 copies `AETC\SCE20I22.LZO` / `SCE24I26.LZO`): no header, 4bpp
low nibble first, 94x94 JIS grid (glyph = row * 94 + cell, 0-based). Two renderers:
- 0x111ba0 (small menus, help text): single-byte characters through the table at 0x214AE0 to
  the full-width glyph, squeezed to half width (pixel pairs averaged). Double-byte codes:
  0x102F70 (Shift-JIS -> JIS) and 0x111498 (glyph address). Lead bytes 0x81-0x9F, 0xE0-0xEA only
  in some menus (0xEB+ is taken as two single bytes).
- The story window and the big-font lists (config, save/load, wrestler select): every character
  one full cell; single-byte ASCII is drawn full width, and ASCII spaces and punctuation are
  dropped in the story.

**Half-shifted glyphs**: centred menus centre a string by its cells, so an odd-length English run
(its last pair padded with a space) sat half a letter left of even ones. Odd runs in roster short
names and menu strings (not `[left]` rows) are drawn with glyphs shifted half a letter right: cell k
holds the right half of letter 2k-1, letter 2k and the left half of letter 2k+1 (`fpzfont.
encode_shifted`). With the 単漢字 rows free, pair codes use JIS rows 15-62 first (lead bytes below
0xA0), then 84-63: about 5,100 glyphs.

**English: pair glyphs** (`tools/fpzfont.py`, *verified headless*). Every English string is
written two characters to a double-byte code whose glyph holds both characters (DejaVu Sans Mono
Bold - monospaced, so letters space evenly in their half cells; frozen in `tools/fonts/pairletters.bin` so the build needs no Pillow). Codes:
JIS row 15 (empty), then level-2 kanji rows 84 down to 48, skipping any code kept Japanese text
still shows (credits, the name-entry grid). In the small menus a pair is the width of two
half-width letters; in the story and big lists it puts two letters in a cell. A build draws the
pairs it used into all five font copies. The story window holds 20 cells x 4 lines (the speaker
line counts) = 40 characters a line.

**Executable strings** (`fpztext.step_ui`, *verified headless*): references are 32-bit words in
`.data`-`.sdata`, `lui`/`addiu|ori` pairs (the lui within 1024 instructions with nothing writing
the register in between - a looser pairing patched a structure offset, `addiu $v0, $s0, 0x748` at
0x1DF328, and blacked out story mode), and `addiu rt, $gp, imm` ($gp = 0x3B1CF0). Strings are
repacked per run (strings with only NUL between them), keeping each string's alignment (up to
16: some are copied with 128-bit loads - 4-byte alignment broke story mode too), identical
strings stored once; strings with no reference stay in place. Not strings: 1-3 byte "strings"
ending in 0x39-0x3E (a float's high bytes).

**Strings found by reference**: besides the NUL-separated strings in the pools, the dump takes the
Japanese strings the code points at that the pool scan misses: packed right after a pointer (no
NUL before: 試合開始), outside the pools (the story's quick-save prompts and result names,
0x3A65D0-), or a single unit the code reads directly (分 at 0x3ABF00).

**Title and main menu brightness** (*from the code, seen headless 2026-10-29*): the GS multiplies a
texture by the sprite colour, 0x80 = 1.0. The title code (0x1576DC-0x157938) draws the logo with
0x20606060 (75%), the copyright with 0x80606060 and PRESS START with 0x80505050; the background is
a flat grey quad (0x98). The main menu code (0x154EBC-0x157114) uses 0x80585858 (69%) and 0x50
greys for the flame layers. The fade-in itself ends at full (its black quad reaches alpha 0). The mode labels
(PACK01_A) are drawn with 0x505050 built at run time (0x1567B4 lui / 0x15682C ori). So the dim look
is set by constants in the code - a design choice or a tuning for TVs, not a fade that stops early.
The English build always raises them to 0x80 (build.py group `brightness`, owner 2026-10-29); the
redrawn atlas is matched to it: labels sample the palette 8 entries lower than the decode shows
(texel 7 = the white outline), the subtitle strips' text part is drawn again as a darker overlay
over the underline, so the strips keep colour only in the columns the underline is stretched from
(x >= 480) and are transparent elsewhere.

**Button icons** (*from the code, seen headless 2026-10-29*): icon positions in the move editor and
CPU logic are hand-set numbers, not measured from the labels (changing a label in RAM doesn't move
them).
- Move editor (0x14DC50): per move slot a 10-byte record at 0x3112E8 - halfwords label x, icon,
  icon x, icon, icon x (-1 none); the label is drawn at label x + 0x40, the icons (images from
  0x311240) in a fixed column; the Japanese labels were placed to end just before them. The slot's
  label is 0x3108A0[byte 0x3109D8[slot]].
- CPU logic (0x144DAC): condition entries at 0x30C008 (12 bytes: label, damage-level table,
  levels, icon-list index at +9); icon lists via words 0x30B968 / counts 0x30B9B0 (three lists sit
  in the string pool at 0x3AAD28-0x3AAD3F); 3-byte records icon, option row, x - drawn at 2*x after
  the label's start.
- The build recomputes both from the English widths (`fpztext.step_move_icons`, `step_cpu_icons`):
  move editor label and icons centred as one group on the text-only rows' middle (x 148 in label
  terms), CPU icons 8 px after their label.

**3D words** (*from the files, 2026-10-29*): YUSHO / SHOURI / BOUEI / SEIHA / TANJO.SOB in FPFILES.OAH
are the result-screen words 優勝 勝利 防衛 制覇 誕生 as 3D models. Header 0x290 bytes (name at +4,
three textures MOJI_FUCHI / MOJI_SIDE / MOJI_TOP from +0x58, node table: node 1 at [0x17C] with
size/4 at [0x170] and bounding radius [0x174], node 2 at [0x24C] with [0x240]/[0x244]); a trailer
from [0x180] (pointers into itself). Node data: a material block `04 00 01 00 ...` (16 bytes), then
vertex batches `010Fxxxx count` + count x (x y z u v rgba) (24 bytes, <= 102), each followed by
polygon records `0x020000nn, count u16, material u16, indices`. Node 1 = rim (material 0, y 20.7
-> 18.7) and side walls (material 1, down to -20.7); node 2 = the flat face (material 2, y 0),
u/v planar across the word (u from z, v from x). private/work/img/moji3d.py builds English ones
(CHAMPION, VICTORY, DEFENDED, CONQUEST, NEW CHAMP) from Barlow Condensed Black outlines; the
build imports translation/images-handmade/models/*.SOB (`build.models_step`).

**Result time** (*seen headless 2026-10-29*, a CPU match at 800% speed): the result screen builds the
time from 分 and 秒 itself - changing the strings 00分00秒 (0x3A0748) and `%2d分%02d秒` (0x3A0758)
didn't reach it. The fonts redraw those two kanji as "m" and "s" (`fpztext.UNIT_GLYPHS`, kept out
of the pair codes), so it reads "1m 11s"; the two strings stay the original bytes.

**ASCII-only strings** in the pools are skipped by the dump except those the game shows
(`fpztext.ASCII_SHOWN`: venue SPIKE DOME, ring and promotion names, music titles, ON/OFF, cm/kg...):
left as ASCII they are drawn in the font's wide full-width letters; in ui.csv they are re-encoded as
pairs even when the English is the same text.

**Disc**: `STORY.OAH` may grow (re-compressed fonts) and move to the end of the image; the game
finds it through ISO9660. Savestates made on another image don't survive files moving - boot fresh.

## Story scripts

*From the code, 2026-10-29* (`tools/storyflow.py` reads them; `tools/storymap.py` turns them into
`docs/story_matches.csv`, `docs/STORY.md`'s facts and the route map). Each `.STO` is also a
compiled script for a small stack machine, the same in all seven files:
- Symbols at 0x40, 0x38 bytes each (count: header u32 +0x30): name at +5, code position + 1 at
  +0x34. The first 38 are helper functions every file defines (`key_wait` ... `quake`, among them
  `game`, `gm_setp`, `save`, `load`); the rest are the scene labels (`misawa011`, `misawa_gm01`).
- Code from header +0x34 up to the string table: 16-byte instructions (runtime pointer, opcode,
  operand, value). Functions end in `push 0; return`. Scene labels pair in order with the non-empty
  functions from the first that shows a message (a trailing stub has no label).
- Opcodes: 0 load variable (value 1 local, 16 global; operand = variable, the index popped for an
  array), 1 address of a variable, 2 push (operand 1 int, 2 string id), 3 pop, 4 assign, 5 add,
  6-10 / 21-25 arithmetic and logic, 11 compare (operand 44 `==`, 45 `!=`, 46 `<`, 47 `<=`, 48 `>`,
  49 `>=`; table 0x3A6740), 12 return,
  13 jump and 14 jump if false (function-relative), 16 call a script function (operand = symbol),
  20 show a message, 26 choice menu (6 layout ints, then label / caption string pairs), 28 go to the
  scene named by a string (at once: nothing after it runs), 19 / 23 / 27 / 29 / 30 / 31 natives with the argument count in the
  operand. The interpreter's opcode table is at 0x3A66C0 (38 entries); op 29 calls the host
  through the VM object (+0x4D40).
- Globals: 128 int32 at file + 0x20 + (header +0x34), zero in every file; value 16 reads
  global[operand + popped index], so `G64[i]` is global[64 + i]: [0] the story score, [n + 1] the
  result of match n (scenario 6 keeps its mentor and Takada/Orihara answers in [32] and [33]).
  Saving copies all 128 (0x1E9100); loading a story save restores them (0x1E9038).
- `game(n)` saves, plays story match n (native 29 with id 1, host 0x1E9E60), stores the result in
  G64[n + 1] and returns it; the scenes treat a result under 2 as a win. `gm_setp(n)` adds n to the
  score (never below 0); many scenes add their win points in place instead.
- **The match bonus** (0x1E9ECC): after a played match (not an aborted one) the game adds to the
  score +1 if the match clock ended between 8:00 and 15:59, +1 if a counter of hits flagged 0x2000
  (probably criticals) is 1-3, and +1 if slot 0's remaining value at +0x128 (likely stamina, from
  0xFFFF) minus slot 4's is 1-8190 or over 61425. Win or lose. This is what makes the high
  thresholds reachable (Misawa's NOAH route needs > 30; the scenes give 25 at most). *From the code;
  not confirmed in play.*
- Each scenario has a developer chapter menu (`<name>000`, `000a`...) that normal play never
  shows; its first entry is the scenario's first scene. Scenario 7 (Liger) plays no matches: its
  "match" scenes show a card and a Win / Lose choice.
- Match cards are messages with `%px320%py100` (the rules: ６０分　１本勝負, 時間無制限 バトルロイヤル),
  ＶＳ, and the two sides positioned left (x < 320) and right; result pages show 試合結果.
- `%saN` prints story-only name N (the file's last section, `translation/text/story_names.csv`).

**Story matches and wrestlers** (*from the code; seen headless 2026-10-30*). Header u32 (file offsets):
+0x10 match table, +0x14 wrestler records, +0x18 their count, +0x1C story names.
- Match table: u32 count, then 44-byte records indexed by `game(n)` (0x1E9640): +0 eight u16 wrestler
  ids (slots 0-3 one side, 4-7 the other, 0xFFFF empty); +0x10 eight bytes, 1 = the id is a record
  of this file, 0 = a roster id; +0x18 u32 the opponent for the result screen (a roster id, or
  0x80000000 + a story name); +0x1C 16 bytes of match settings: rule flags (+0x1E; 0xA2 normal, 0x26 with
  +0x20 = 3 scenario 6's U-Inter rules), time limit in minutes (+0x21), venue (+0x23: 0 Budokan, 1 Spike Dome, 2 Korakuen Hall, 3 town gym, 4 USA, 6-8
  match rule venues, 10 dojo), ring (+0x24; menu id, 28 UWH with build group rings), referee (+0x26), COM level (+0x25;
  every story opens at 2 and ends at 7-8; read around 0x11FFF0-0x120150) and critical % (+0x29; 0
  off .. 3, the check at 0x12D288). Locked roster wrestlers load fine by id.
- Wrestler record (0x37E bytes): a roster record up to +0x1D4 (the roster then holds four 26-byte
  outfits: face u16, parts); +0x1D6 the colour block (0x164 bytes: 12 + 43 x 8, RGB555 ramps), which
  for roster wrestlers `PALET.TAC` builds (0x116718: section 0 at 88 x (4 x wrestler + colour) gives
  44 u16 ids into sections 1 and 2; `storywrestlers.costume`, checked byte for byte against scenario
  1's Misawa); +0x33A scratch (the finisher's name is copied here); +0x364 one outfit.
  In an outfit (+0x364, *seen headless*): +0x367 and +0x36B the top, +0x36F and +0x372 armbands, +0x379
  long pants (0xFF = none; +0x378 is 2 with none).
- **The Liger scenario.** `STORY07.STO`'s match table and wrestler records are a copy of scenario
  6's: its script never calls `game()`. `tools/ligerstory.py` rebuilds the 26 match scenes on
  the pattern of the other scenarios (card, `game(n)`, result screen, +1 for a win, on to the old Win
  or Lose scene) and writes 26 match records; `tools/storywrestlers.py` fills 13 wrestler records.
  Losing to Pegasus has three new scenes (lyger0082-0084, copies of Misawa's Game Over, Retry and Quit
  scenes): new symbol records go just before `<name>000` and `main`, which must stay last, and calls of
  those two move with them; the file's symbol count and every offset after the records change.
  Growing a script: code is function-relative, so only the symbol records' code positions (file
  0x38 + k x 0x38, +4; frame size +8, 1 for a match scene's local) and the header's offsets after the
  code change (+0x28 table, +0x2C pool, +0x10, +0x14, +0x1C). New strings go at the end of the table,
  so text ids stay. Instructions' first word is unused. It runs on the original bytes, before the
  translation step, which then treats the new cards like any other. Story names 7:6 and 7:7 hold
  Pegasus and Yamada for the cards, pair-encoded so they draw like roster names (plain letters
  draw one a cell). *Seen headless 2026-10-30.*
- Message 120 of `STORY07.STO` (lyger2111) is the only story message with no `%k`: a whole conversation
  as one page. `ligerstory.paged` adds a `%k` before each speaker, in the build and in the dump.
- **Story colours.** `%c0` is white, `%c1` yellow: the hero white, everyone else yellow. The original
  keeps to it but for 26 pages in stories 1-6, and scenario 7 never had the pass (about 465 pages).
  `tools/storycolours.py` sets each labelled page by its speaker (the hero's other ring names count as
  him); pages with no speaker keep their colour and follow the page before.
- How the other stories rate wrestlers: opponents keep their roster ratings (the story records'
  difference is 0 or nearly), except that a rookie hero and his first opponents are far lower: the
  hero's attack + defence goes 99, 130, 167, 175 (Misawa), 109, 175 (Hashimoto), 123, 157 (Onita).
- Fields shared with Fire Pro Wrestling S's roster (0x1AC bytes, big-endian words), compared over
  the 96 wrestlers in both games: +0x3E-0x54 the same (style +0x45 and reversal +0x46 renumbered,
  S value + 1 above 4 and 2), attack ratings at +0x5D (S +0x5E), defence +0x68. Moves: S's 55 words
  from +0x72 are Z's from +0x74 for the first 45, then Z adds a slot (+0xCE) and more after +0xE2.
  CPU logic does not carry over. Moves belong to a slot type: use an id some wrestler has in that
  type (the same name can have several ids).

## Images

*Verified headless, 2026-10-29.*
- Textures (`tools/gfx.py`): P2TXB, 8bpp. Some (WIN01, ICON01, ILL_01, STORY_SYSTEM, PACK01_B) use
  only indices 0-15 with a plain 16-entry palette (no CSM1 swap): the exporter shows them as one
  flat colour; none of them holds Japanese.
- **Screen packs** - `EDITMENU\S_ONEMCH.LZO`, `S_TITLE.LZO`, `OPENING_NEW.LZO` (CP00, 1.5-3 MB):
  a screen's textures back to back (palette then pixels, as in the texture files). Wrestler
  select draws WSELECT from S_ONEMCH, not from `WSELECT.GST`; the main menu atlas (PACK01_A) is
  not in a pack. `gfx.import_images` patches every pack copy of each imported image (an exact
  match of the original palette + pixels).
- The main menu atlas: label rows with the label in two variants (normal, selected), then the
  English subtitle strips (orange, grey). The strip rows with subtitle letters also draw the line
  under each item (grey; yellow when selected); the empty strip rows show as a solid plate behind a
  locked item (Title Match before Victory Road). Subtitles removed: letters painted with the strip
  background, empty rows index 0.
- Pictures with Japanese text: PACK01_A (3 copies), WSELECT / PROFIL_PARTS (profile tags), BAR01
  (elimination positions), BUTTON (move markers) - all redrawn (`private/work/img/`). Kept:
  promotion logos (`EDITMENU/SAMPLES`), LOGO_A, the weapons sheet's dev labels (KYOUKI 不可/ベース),
  SEISIN (an in-world scroll).
- Not decoded: the result banners BOUEI / SEIHA / SHOURI / TANJO / YUSHO.SOB (3D objects; their
  names say title defence, conquest, victory, new champion, tournament win - possibly 3D kanji).
- **Name entry** (*verified headless, 2026-10-29*): rows of 15 double-byte cells (32 bytes) from
  RAM 0x3A0910; pages are row-pointer tables (RAM): hiragana 0x3348D0 (8), katakana 0x3348F0 (8),
  the 単漢字 reading index 0x334910 (8), ABC 0x334930, symbols 0x334950, the 単漢字 list
  0x334980 (283 rows, 7 shown from a scroll offset). Picking an index cell (row r, column c)
  jumps the list to the u16 at 0x3347D8 + 2*(15r + c). CROSS moves to the page menu, CIRCLE
  enters a cell's code, SQUARE deletes, TRIANGLE / R1 switch the field. The English build rewrites
  hiragana -> "Letters" (A-Z a-z with a space, space + capital), katakana -> "More", the index ->
  the 52 first letters and the list -> every pair starting with each (4 rows a letter) -
  `fpztext.step_name_entry`. Typed names are pair codes, like the roster's.

## Open questions
-
