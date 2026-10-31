# Hidden content

Unlockables, debug features, button codes, cut and unused content. Every find says how sure it
is:

- *verified in game* - seen in an emulator (with the date, and the build or code used to get there)
- *verified headless* - seen running in the headless emulator (PCSX2 core), not yet by a player
- *from the code* - read in the disassembly, not seen running
- *from the data* - in the game's files or tables, whether or not the code uses it
- *from a guide* / *from fans* - a published source, not yet matched with the code

Addresses are virtual addresses in the executable `SLPM_623.42` (file offset = address - 0xFF000);
files are named by their archive path (`FPFILES.OAH > EDITMENU\PACK01_A.LZO`). Optional patches
that switch some of this on are in [PATCHES.md](PATCHES.md). Story mode's own routes and endings
are in [STORY.md](STORY.md).

**Prior art (2026-10-29).** No Cutting Room Floor or Data Crystal page found (TCRF refused
automated reading - worth a look by hand), and no cheat codes for this game in any database
searched (Action Replay, CodeBreaker, PCSX2 pnach collections, GameHacking.org). Known unlocks,
*from fans* (Japanese Wikipedia, a cheat site): story mode has six scenarios; four are open from the
start, the fifth (Onita's parody) opens after reading each of the four once (any ending), the
sixth (Sakuraba's) after the fifth. The code agrees (below). Nobody mentions the seventh.

**Prior art, second pass (2026-10-30).** Japanese cheat lists give an unlock ladder (edit points,
45 wrestlers, 10 teams, 17 parts) that the code confirms: see [What unlocks what](#what-unlocks-what).
No raw cheat device codes turned up. GameFAQs, Neoseeker, CheatCC and Wazap could not be read
automatically and TCRF's real page was not seen, so they are worth a look by hand.

## Contents
- [The hidden seventh scenario: Jushin Thunder Liger](#the-hidden-seventh-scenario-jushin-thunder-liger)
- [Story chapter menus](#story-chapter-menus) · [Scenario unlocks](#scenario-unlocks) ·
  [What unlocks what](#what-unlocks-what) · [Hidden wrestlers](#hidden-wrestlers) ·
  [Extra faces](#extra-faces) · [Extra preset teams](#extra-preset-teams) ·
  [Unused unlock code](#unused-unlock-code)
- [Edit mode button shortcuts](#edit-mode-button-shortcuts)
- [The developers' mode select](#the-developers-mode-select) · [Other debug code](#other-debug-code)
- [Unused rings](#unused-rings) · [Moves nobody can get](#moves-nobody-can-get) ·
  [Downloadable moves](#downloadable-moves) · [Story-only wrestlers](#story-only-wrestlers) ·
  [Unused music](#unused-music)
- [Unused story pictures](#unused-story-pictures) · [Cut main menu entries](#cut-main-menu-entries) ·
  [Unused files and leftovers](#unused-files-and-leftovers) · [Unused text, moves and names](#unused-text-moves-and-names)
- [Searched and not found](#searched-and-not-found) · [How to see it yourself](#how-to-see-it-yourself)

## The hidden seventh scenario: Jushin Thunder Liger
*verified headless (2026-10-29, `build.py --unlocks liger`)* / *from the code*

`STORY.OAH > SCENA\STORY07.STO` is a complete seventh story: Keiichi Yamada, a small boy in the New
Japan dojo, becomes Jushin Thunder Liger (the game's parody name is Super Kaiser). 125 scenes, a
route split between New Japan and the UWF (then RINGS, U-Inter or Pancrase, then New Japan or
mixed martial arts), two endings - all fully written and translated. The game can't open it:

- The scenario select builds its list from a table of wrestler ids (copied from 0x3A6518): six
  entries. Liger's id (0x0F, in the file's header) is in no table, and the lookup from id to
  file (0x1E51E8) stops after six.
- The script looks unfinished. Its `main` starts at the developer chapter menu (`lyger000`)
  instead of chapter 1, like a test file. It plays no matches: each match scene shows
  "Match (VS name)" and asks **Win** or **Lose**. Its one score check (the G1 final with Chono,
  `lyger113`) can never pass, because nothing in it raises the score. Two match cards leave the
  opponent's name blank, one names the wrong opponent (Kanemaru for Marufuji), and its list of
  story-only names is a copy of scenario 6's that it never uses.

The patches go further than opening it: in this translation's *All Unlocked* patches its 26 matches
are real matches (see STORY.md). Wild Pegasus and Bas Rutten aren't on Z's roster: Pegasus is rebuilt as a
story-only wrestler from Fire Pro Wrestling S's data, and Rutten's match is Minoru Suzuki's.

With the `liger` patch the select lists **Liger** seventh, and the story starts at chapter 1. With
`debug-chapters` it opens its chapter menu (13 chapters
on its first page: "Chapter 01: 001 Joining Up" ... "Chapter 13: 013 vs Inoki") and plays from the chapter picked.
STORY.md has the whole route map.

## Story chapter menus
*verified headless (2026-10-29, `build.py --unlocks debug-chapters`)* / *from the code*

Every scenario script holds a chapter-select menu (`misawa000`, `oonita000`/`000a`/`000b`, ...:
one to six pages) that jumps to any chapter, including each branch's own chapters and endings
("011 Ch.11 NOAH (Branch)", "113 vs Chono", "PRIDE Route", "Batroi" = battle royal). Normal play
never shows it: the story VM (init 0x1E5408) always starts at the script's `main`, which calls
`<name>001`. The menu is the symbol just before `main` in every file. The engine already treats a
menu as the start function correctly (a choice or a jump moves the start; returning from it ends
the story and counts as a clear), so the patch only moves the start one symbol back.
Jumping in mid-story starts with the score at 0, so the score checks of that route go the
low way unless the chapter is played from earlier.

## Scenario unlocks
*from the code* (matches the fans' account)

The scenario select (0x150DA0) shows the first *unlock level + 4* entries of 氷川 (Misawa),
俊藤 (Mutoh), 旗本 (Hashimoto), 河野 (Chono), 沖田 (Onita), 柏田 (Sakuraba). A story counts as cleared
when it ends, any ending (0x1E8590): the scenario's id goes into a list of five in the save
(+0x49F0); the 4th clear sets the level to 1 (Onita), the 5th to 2 (Sakuraba).

## What unlocks what
*from the code*; the extra faces, teams and Staff Credit *verified headless (2026-10-30, RAM pokes
on the original disc)*

| Needs | Opens |
|---|---|
| Nothing | Edit points 150, four story scenarios, 199 wrestlers, 29 preset teams |
| 1 story clear (any ending) | Unlock level 1: edit points 200, the [45 hidden wrestlers](#hidden-wrestlers), Staff Credit in Options |
| 1 Victory Road course | Title Match, the [10 extra preset teams](#extra-preset-teams), Staff Credit in Options |
| 1 story clear and 1-2 courses, or 3+ courses and fewer than 5 stories | Unlock level 2: edit points 250 |
| 4 story clears | The fifth scenario (沖田勝志, Onita's parody) |
| 5 story clears | The sixth scenario (柏田一樹, Sakuraba's parody) |
| 5 story clears and 3 courses | Unlock level 3: edit points 300, the [17 extra faces](#extra-faces) |

- **Level** (save +0x46D2, recalculated by 0x113520, only ever raised): it stays 0 until a story is
  cleared, however many Victory Road courses are.
- **Victory Road** has six courses (SWA Unified Heavy Singles, Heavy Tag, Jr. Singles, Jr. Tag,
  6-Man, 8-Man), bits 0-5 of byte +0x9C of save block 5. Only the number cleared matters: no course
  opens anything of its own. Each clear also plays the staff credits.
- **Title Match** (flag 0x3AD168, rebuilt each time the main menu opens; 0x1564EC) refuses with
  "Clear one Victory Road course first" until a course is cleared.
- **Staff Credit**: Options goes from 6 to 7 rows (0x173524-0x173550).
- No win count, title holder, match count or ending seen opens anything that was found, though
  the mode records were not followed field by field inside each mode.

## Hidden wrestlers
*verified in game (2026-10-30, with `--unlocks unlock-level`)*; the locked lists *verified headless (2026-10-30, original disc, One Night Match select)*; the rest *from the code*

45 of the 244 wrestlers are missing from the select screens (One Night Match, edit) until the
unlock level is 1 or more, i.e. until any story scenario has been cleared (any ending). Victory
Road alone does not do it: with no story cleared 0x113520 leaves the level at 0. The promotion
lists are a working copy in RAM, not save data (34 lists of 0x382 bytes, u16 ids ending 0xFFFF,
at 0x19F7F04 in this session), rebuilt by 0x114708: 0x117A30 fills them from the order table
0x215848 and, while save +0x46D2 is 0, skips every wrestler marked in the byte table 0x215940.
0x117438 applies the same filter to a second list. Both read +0x46D2 themselves, not through the
getter 0x113460; `--unlocks unlock-level` patches all three reads. Hidden at the start (ids, real
names):
5 Kengo Kimura, 33-40 (Kazuo Yamazaki, Animal Hamaguchi, Osamu Kido, Kotetsu Yamamoto, Tiger Mask,
Dynamite Kid, Kuniaki Kobayashi, Black Tiger), 43 The Great Muta, 58-65 (Giant Baba, Jumbo Tsuruta,
Dory Funk Jr., Stan Hansen, Bruiser Brody, Terry Gordy, Gary Albright, Johnny Ace), 84 Satoru
Asako, 98 Antonio Inoki, 102 Hiromichi Fuyuki, 118 Yasushi Kanda, 120 Ultimo Dragon, 130 The Great
Kabuki, 150 Andre the Giant, 151 Tiger Jeet Singh, 153 Davey Boy Smith, 156-160 (Terry Funk, Hawk
and Animal Warrior, Randy Savage, Bret Hart), 164 Sting, 165 Sid Vicious, 172 Dos Caras, 173 Mil
Mascaras, 178 Masakatsu Funaki, 184 Akira Maeda, 203 Roland Bock, 204 Aleksandr Karelin, 205 Andy
Hug, 206 Ensen Inoue, 215 Akira Hokuto, 218 Bull Nakano, 221 Rikidozan. A story clear rebuilds
the lists straight after raising the level (0x1E8648, 0x1E865C), so they appear at once. The second
list (0x117438) is the wrestler pool of Promotion Edit.

## Extra faces
*verified headless (2026-10-30, level poked to 3)*

The Face row of Wrestler Make (Edit Mode > Wrestler Edit) stops at 386 until unlock level 3, then
at 403 (0x1142D0, table 0x30D920). The 17 extra `WRSPARTS.OAH > FACE_387-403` are mostly joke and
anime heads: a tiger mask, a bear, a duck-billed creature, a skull, a monkey-like mascot, a black
panther, hoods, anime girls, cat ears. No built-in wrestler uses them.

Each has a full preset (0x30DC48, 26 bytes a face from 244): hold SQUARE on the Face row and press
LEFT / RIGHT to load it. *Seen headless 2026-10-30*: 402 a cat-eared girl in a bunny suit with paw
gloves and shoes, 401 a sailor suit, 400 a blonde in pink. 389 and 390 point at the Bear and Builder
bodies. A plain press keeps the current colours, and the default edit wrestler's face colours 18-25
are a placeholder green in the original, which the hood and hair of these faces use (the
`edit-colours` patch, docs/PATCHES.md).

## Extra preset teams
*list verified headless (2026-10-30); the team screen itself not seen*

Elimination and Team Edit offer 29 preset teams (names 0x215A38, members 0x215AD8, list built by
0x115C60). Ten more appear after any Victory Road course (save +0x46D1, tested at 0x115D0C): 旧VIEW軍,
力丸隊, レジェンドジュニア, 歴代OLIVE軍, OLIVE伝説軍, ビバ！メヒコ軍, 旧最強外国人軍, 新生UWH軍, ブラッディヒール,
スーパースターズ. Each of the ten holds hidden wrestlers and none of the first 29 does. The teams do not
go through the wrestler filter, so a Victory Road clear with no story clear should reach those
wrestlers through a team (*from the code*, not tried).

## Unused unlock code
*from the code*

- 31 bytes at save +0x46B2 are a 248-bit lock list: 0x1144A0 sets one bit for each of the 45 hidden
  wrestlers at boot, and a Victory Road clear wipes them (0x113418). Its test (0x114378) and clear
  (0x114338) have no callers and nothing else reads the bytes, so it does nothing. It looks like an
  earlier design in which Victory Road unlocked the wrestlers.
- A list of user faces (ids 0x3EF or 0x400 up, 0x114208, list 0x419EB0) is always empty: its only
  writer, 0x114178, has no caller.

## Edit mode button shortcuts
*verified headless (2026-10-30, original disc)*

Nothing in the game mentions these. In Edit Mode > Wrestler Edit > Wrestler Make:
- **Copy and paste colours:** CIRCLE on a body-part row opens the swatch bar. Hold SQUARE: L2 copies
  one swatch, R2 pastes it. Hold TRIANGLE: L2 copies four, R2 pastes four (0x149F58-0x14A0B0).
- **A built-in wrestler as a base:** on the Face row, hold SQUARE and press LEFT / RIGHT to load
  that face's whole wrestler: stance, size, parts, colours, outfit (0x14B608). A plain press changes
  only the face. Hold R1 to step by 10 (0x14AB38).
- **Auto gradation:** in the swatch bar, SELECT fills the ramp with a straight blend between its first and last shades (0x14A248, 0x14B7C8; *verified headless 2026-10-30*).

## The developers' mode select
*verified headless (2026-10-30, the numbers noted below, test50 with `--unlocks all` groups + `debug-chapters`, `debug-menu`)* / *from the code*

A plain green text menu that nothing calls, left over from development. `--unlocks debug-menu` puts
it where the main menu would be: press START at the title and it opens. The real main menu is gone
from that build. Everything still works, because the menu is a working (if unlabelled) mode select.

**Controls** (one step for each press; the number is not limited and starts at 0 each time):

| Button | Does |
|---|---|
| RIGHT / LEFT | number +1 / -1 |
| UP / DOWN | number +10 / -10 |
| CIRCLE | go |

There is no cursor: the number at the top, "select mode number : %d", is the choice.

**The list on screen is out of date.** Its rows (0x3128C0, x, y and text, ending at -1) describe an
older numbering, and the number goes straight to the release main menu's switch (0x151770). So the
label beside a number says nothing about what it opens:

| Number | The list says | What it opens | Handled by |
|---|---|---|---|
| Below 0 | | Leaves to the title screen | 0x1518C8 |
| 0 | MAIN MENU | One Night Match | 0x1A82B0 |
| 1 | ---- | One Night Tournament | 0x1A83F8 |
| 2 | ---- | Open League | 0x1A8850 |
| 3 | ---- | Elimination Match | 0x1A8C58 |
| 4 | ---- | Battle Royal | 0x1A8F30 |
| 5 | (no row) | Victory Road | 0x165AA0 |
| 6 | (no row) | Title Match | 0x1A9098 |
| 7 | (no row) | Edit Mode | 0x145400 |
| 8 | SAVE TEST | Story | 0x150928 |
| 9 | ---- | Save / Load | 0x159938 |
| 10 | ------------------ | Options | 0x1733C0 |
| 11 | Set Dummy all clear flag | Nothing | |
| 12 | System save/load test | Nothing | |
| 13 | 2D Texture test | Nothing | |
| 14 | PAD test | Nothing | |
| 15 | ROM Party LOGO test | Nothing | |
| 16 | Stream test | Nothing | |
| 17 | Sound test | Nothing | |
| 18 | Enter test | Nothing | |
| 19 | Voice test | Nothing | |

Numbers below 0, 0-12 and 19 were each run; 13-18 were not, but the switch has no
case for them, nor for anything higher. A number with no case redraws the menu at 0.

- Each mode behaves as it does from the main menu. Back out with CROSS and the menu returns, at 0
  again.
- 0x151AA8 only passes the list to 0x151930, which draws and reads it. Nothing else calls either.
- The main menu's own checks are skipped. Title Match's "Clear one Victory Road course first" lives
  in the main menu (0x1564EC, 0x156748), so number 6 should open it without the `title-match` patch
  (*from the code*: the test build has that patch). Inside, Title Match, Past Champions and Vacate
  Title are dimmed on a new save, exactly as they are from the main menu.
- After a mode the main loop also runs 0x13E048, for every number but 9. That routine is not
  identified.
- "Set Dummy all clear flag" (an unlock-everything switch) has no code left: every write to the
  unlock data is a normal game path.

Some tests' code does survive, with nothing calling it (*verified headless 2026-10-30*, each run in
place of the main menu): a stream test (0x151D98, STOP changes to PLAYING), an SE test (0x151F50,
"BANK number / select se number"), a voice test (0x1520CC, the screen works; the headless core
crashed on CIRCLE, which may be the core's fault) and a promotion logo viewer (0x151AC8). Three more
have no callers and are unidentified: 0x15AA28, 0x1601B8, 0x1609E8.

## Other debug code
*from the code*

- 0x1206A0, never called: an in-match debug readout from `mch_dbug.cpp`, and it can't draw as it
  stands: its print routine 0x120640 saves its arguments and returns. While the match is paused (+0x1401,
  set and cleared by START at 0x1233B0, 0x123310) R1 steps a page (+0x1CCC, 0-9) and L1 a value (+0x1CC8,
  0-8). Pages 0 and 1 show nothing; 2-9 are positions ("P ID J G XPS YPS ZPS"), states ("P ST1 ST2 ST3"),
  vitals ("P HP SP BP NC AM WT LG DP DT PT"), the current move ("P T WAZA WT"), "N P T ST1 AN FOM Z", match
  settings ("SPD INFO T B R TM B RG PT LV BGM"), damage ("P T HP DAMAGE REV HCT CCW") and pad input ("P
  KEYD KEYP"). Not run so far. It would need a new print routine (the mode select's text routines are
  still there, though they may not draw over a match), a per-frame call, and +0x13A0 saved around it,
  as other code uses that field. Match debug strings nearby: CRITICAL / REVERSAL / 100P_REV, "Referee
  Voice = %d".
- 0x162808, never called: a frame grabber that writes `frm_%04x.bmp` to the development PC
  (`host:/public/FRAME01.FRM`).
- "Press Y to reset the position" with X= / Y= (0x39EDD0): the options code tests neither button,
  so this looks like a cut feature.
- An HDD install path with a placeholder product code (`hdd0:PP.SLPS-00000.FPZ.FPZ`) that nothing
  uses, and source-control headers (`/home/fpddev/fpz/...`, 2002-03), with source names such as
  `mch_dbug.cpp` and `mch_dojo.cpp`.

## Unused rings
*verified in game (2026-10-30, with `--unlocks rings`)*

The ring tables (0x2E2EB8 posts, 0x2E2F18 mats) list 23 ids, and six complete sets are in neither,
so no menu can reach them. All six load and play correctly:

| Set | Mat | Apron | Post model (0x37EB38) |
|---|---|---|---|
| `MAT03` / `POST03` | Red, "Independent World" logo | Blue, "ALEC TV" | 0x37EA90 |
| `MAT08` / `POST08` | Pale blue | Red with a teal band, no text | 0x37EA90 |
| `MAT09` / `POST09` | Grey-lilac | Black, no text | 0x37EA90 |
| `MAT11` / `POST11` | Blue | White, "NONNON" with a green eye in the first O | 0x37EA78 |
| `MAT13` / `POST13` | Blue, star logo reading "BATTRATION" | White, no text | 0x37EA78 |
| `MAT16` / `POST16` | Deep blue | White with a blue band, "UWH" | 0x37EA78 |

UWH is a promotion in the story with no ring in the menu, though this one exists. Battration (the
star logo) is in the promotion list and one team name, not the story. `--unlocks rings` puts all
six in the menu.

Also unused: `MAT97.SOB` (a copy of `MAT00`) and `MAT_99.GST`. The dodecagon's model `MAT99.SOB` names
`MAT_99_1225`, the cyan "F.P.Z." mat, not `MAT_99`. `--unlocks rings` also makes a square F.P.Z. ring
from the two unused files.

## Hidden venues
*seen headless (2026-10-30, a CPU match on each under a Normal Match)*

The Venue row skips five of its eleven venues (0x187FE0, 0x18C638). Four belong to match rules: 5
Bayside Coliseum (the caged dodecagon with the F.P.Z. mat, Gruesome Fighting), 6 Kawashima Ballpark
(the cage ring) and 7, 8 Korakuen Hall (the hazard boards). Picked by hand they only turn a match into
those rules, so they stay with them. The fifth, 10, is a dojo with a wooden floor and no name, used by
8 story matches in scenarios 6-7. `--unlocks venues` adds it to the row as Dojo, with a photo card made from the story's dojo
background (`DOUJYOU`).

## Moves nobody can get
*from the data, 2026-10-30*

`WAZA.BIN` has 1,845 move ids. The u16 table at 0x37EB98 gives each one its first motion in
`GODAWAZA.BIN` (3,456 motions), so every id can be checked. 1,443 are offered in edit mode's 43 lists
(0x3106F8), every one with motion data. Of the rest:
- Five named moves have normal motions and are in no list, roster record or story record: 285 Phoenix
  Kick, 613 Eiffel de Parachute, 617 Blazing Tornado, 660 Muscle Buster, 713 Deadly Go-Round.
- One "(予約)" (reserved) slot has a motion too: 1059, right after the ground move Ghost Clutch. It is
  a jumping splash on a downed opponent.
- The other 395 reserved slots and the blank 176 have no motion, so nothing is hiding there.

Each of the six sits inside a run of listed moves, so they look removed rather than never made.
`--unlocks moves` adds them, and all six play properly (*verified in game 2026-10-30*). Motions past the move table (reactions and the like) were not audited.

## Downloadable moves
*from the code*

A download system survives from the cut Network Mode: card files DOWNWAZA and NETWORK (0x2E3268),
0x13AB80 and 0x113EC8 decode a file into 100 move slots, and 0x14E4A8-0x14E4F8 merge them into the
edit lists as ids 0x800 + n. The disc has no such file, and it is not known whether a normal load
ever asks for one. A crafted card file might add moves.

## Story-only wrestlers
*from the data, 2026-10-30*

Each story script holds full wrestler records (0x37E bytes, STO header +0x14; the roster's layout, with
colours and an outfit added). There are 101 records in all, 97 of them different, but they are only 39
people. They load only into story matches, never into a menu list.

**27 are roster wrestlers.** Their records are the same person at another moment in the story, up to 12
records for one person (Sakuraba, 8 for Mutoh and Chono). Height, weight and birth date match the roster, except Takada and Kashin in
some records. What changes is the outfit (nearly always) and the moves and skills (from 0 of 75 moves
to 55, usually under 30). Some have a face of their own that no roster costume uses: Misawa 255 and
279, Muta 271, Mutoh 272, Kashin 256, and the leads of scenario 6 (Sakuraba 142, Tamura 316 and 336,
Rickson 142 and 188, Kerr 336). Tiger Mask and Kanemoto share 110, Onita and Liger 130, and Sakuraba
borrows Tiger Mask's face 37.

**12 are not on the roster:**

| Record | Person | Scenario | Face |
|---|---|---|---|
| ゲレロ チャボ | Chavo Guerrero | 2 | 48, Nobutaka Araya's |
| 青柳 政司 | Masashi Aoyagi | 2 | 73, Jun Izumida's |
| 阿修羅 原 | Ashura Hara | 2 | 34, Animal Hamaguchi's |
| トニー ホーム | Tony Halme | 3 | 267, Scott Norton's second |
| 中内 中内 | Seiji Sakaguchi | 4 | 252, its own |
| ディック ヒール | Rick Rude | 4 | 13, Don Frye's |
| ディック スレンダー | Ric Flair | 4-5 | 319, its own |
| アレックス スーパースター | Scott Steiner | 5 | 228, The Gladiator's |
| 宮戸 | Yuki Miyato | 6-7 | 49, Tomoaki Honma's |
| ネルソン | Nelson | 6-7 | 351 and 332, its own |
| ヤマケン | Kenichi Yamamoto | 6-7 | 210, Shinobu Kandori's |
| キモ | Kimo | 6 | 355, its own |

Several reuse another wrestler's details as well as a face: Sakaguchi has Ogawa's size and birth date,
and Nelson and Miyato keep Anjo's nickname and size. Rude and Flair share theirs. These look like
quick stand-ins for one match each rather than finished wrestlers. The real names here are read from
the owner's list where the story's names are parodies (Sakaguchi, Rude, Flair, Steiner, Halme), and
plain readings of the name otherwise (Miyato and Yamamoto are guesses). Nelson is not identified.

## Unused music
*from the data and the code, 2026-10-30; listened to from a decoded export*

`ZSTA.ZZZ` holds 101 stereo PS2 ADPCM streams (2 KB interleave). It opens with a 512-bucket name hash,
then entries of name, NUL, u32 size in bytes, u32 position in 2048-byte sectors. Stream numbers run to
125, plus 999. Five complete songs are never played:

| Stream | Length | Beside |
|---|---|---|
| 44 | 10 s | the short pieces 43 and 45 the program plays |
| 102 | 22 s | 103-109, the main story music of scenarios 1-7 |
| 111 | 30 s | the story's music |
| 121 | 43 s | the story's music |
| 124 | 48 s | the story's music |

They share no data with any other stream, and they sound like story music rather than entrance
themes. Nothing reaches them: all 45 places that start a stream were read (38 fixed numbers, the
entrance theme table at 0x32D1E0, the match music table at 0x32D210, a wrapper, the story's call), and
all 810 `bgm_play` calls in the scripts use a fixed number. Only the unreachable stream test (0x151D98)
could play them, since it takes any number. They are left as they are.

## Unused story pictures
*from the data*

Story pictures are loaded through a table (`STORY.OAH > AETC\GRA_MAS.LZO`, 184 entries). 88
pictures in `STORY.OAH` are not in it, so the game can never show them:
- backgrounds: a press-conference brawl (KAIKEN_RANTO, KAIKEN_RANTO2), an exploding bomb
  (JIGEN_BAKUHA), a ripped shirt (T_YABURI), dojo weights (RENSHU), a president's office
  (SHACHOUROOM), two hospital rooms (BYOUIN_1/2), a corridor, a press conference, a waiting area,
  three greyscale match pieces (SIAI-BACK1-3), ring views (RING_MIAGE, RING_1B-3B, RING5A);
- a belt (BERUTO), a flat green DUMMY, a second Wild Pegasus portrait with a garbled name;
- 31 older portraits (OLD*: Liger, Inoki, Baba, Flair and others) and duplicate portraits under
  other spellings (HASIMOTO1-4, MUTOU1-4, FLIAR, MIRUCO, Y-OGAWA, N-OGAWA...).

14 pictures are in the table but no script shows them: Sakuraba 1-3, a second Rickson, Yasuda,
Nakano, Kashin, Kanemoto, Black Tiger, a second Liger, a second Hiro Saito, a Kensuke Sasaki
portrait, and the "jumbo" and "rannyu1" backgrounds.

## Cut main menu entries
*from the data*

The main menu's picture (`FPFILES.OAH > EDITMENU\MAINMENU.OAH > PACK01_A.LZO`) has two labels
with their subtitles that the menu never shows: ネットワークモード / NETWORK MODE and
メモリーカード / MEMORY CARD. The executable has no network code or text left.

## Unused files and leftovers
*from the data*

- `FPFILES.OAH > BELT.OAH` and `BELTM.OAH`: the executable names neither, but they are only
  duplicates of chunks in `BELT.LZO` and `MINIBELT.LZO`, which the game uses.
- `ENTRANCE\MB_A00.DAT`, `MD_A00.DAT`, `MU_A00.DAT`: the entrance lists start at 01.
- File names in the executable with no file and no code using them: LOADING_384.PNG, SWA_LR.BMP,
  FIRE_0708.BMP.
- `ZSTA.ZZZ` (283 MB) is the streamed audio archive used by the game (and by the cut "Stream test"): see [Unused music](#unused-music).

## Unused text, moves and names
*from the data*

- 番号エラー and 未登録技 belong to the [downloadable moves](#downloadable-moves).
- `WAZA.BIN`: 396 move slots are "(予約)" (reserved), none of them offered anywhere.
- The roster has no test or placeholder wrestlers.

## Searched and not found
- Button codes: none. Every read of the pad was followed (from scePadRead, 0x1EF0F8, including
  pointer routes): the title screen tests only START, the main menu only UP / DOWN / CIRCLE / CROSS,
  no multi-bit mask needs its buttons together, and no pad word is compared with a table, so there
  are no sequence codes. Five combos held at the main menu changed nothing in the save. In-match
  inputs share their words with the CPU's logic and were not audited as codes.
- Name-entry passwords: none. No compare of an entered name with a constant, literal or hash.
- Hidden heads and costume parts: none beyond the [17 extra faces](#extra-faces). All 894 files of
  `WRSPARTS.OAH` match the edit lists (`FACE`, `M_CH`, `BO`, `UA`, `FA`, `TH`, `SH`, `HA`, `FO`; ids from the
  lists, not traced to each file in the code). The gaps in their file numbers are empty slots. The
  Bear and Builder bodies are selectable; no built-in wrestler uses them.
- Hidden match settings: none. The 31 tables at 0x331C58 are layouts of the match settings screen (21
  bytes each, 12 different). Row ids 0x18 and 0x19 are a spare Blue / Red pair, and 0x1D-0x1F do
  nothing. Which mode uses each layout was not mapped.
- Cheat codes on the web: none for this game.
- An "unlock everything" switch: the debug menu names one, but no code is left.
- Unused story text: every message and caption of the seven scripts is used by some scene, and
  every chapter-menu entry has a scene.

## How to see it yourself
| Find | How |
|---|---|
| Liger scenario | `python3 build.py --unlocks liger` (with the other unlocks: `--unlocks all`) |
| Chapter menus | `python3 build.py --unlocks debug-chapters` (never in a release) |
| All six scenarios | `python3 build.py --unlocks scenarios` |
| Title Match | `python3 build.py --unlocks title-match` |
| Unlock level 3, all 244 wrestlers, all 39 teams | `python3 build.py --unlocks unlock-level` |
| Developers' mode select | `python3 build.py --unlocks debug-menu` (replaces the main menu; developer build only) |
| Unused rings, F.P.Z. ring | `python3 build.py --unlocks rings` |
| The dojo venue | `python3 build.py --unlocks venues` |
| The six unlisted moves | `python3 build.py --unlocks moves` |
| Unused pictures | `tools/gfx.py` exports `STORY.OAH` (not in the table: see above) |
