# Patches

What the build changes besides text and images, one section per patch: what the original code
does, what changed, why it works, the tool that makes it, limits to respect, and whether it was
*verified in game*.

All addresses are in `SLPM_623.42` (file offset = address - 0xFF000); the patches are
`build.py` `CODE_PATCHES`, picked with `--unlocks GROUP,...` (`all` = every group but
`debug-*`). The plain English build has none of them unless listed in `DEFAULT_GROUPS`.

## brightness (always on)
The title screen and the main menu are drawn at about 60-75% grey in the original; the English
build draws them at full brightness (owner's decision). docs/TECHNICAL.md has the sites.

## scenarios - all six story scenarios
- **Original:** the scenario select (0x150DA0) lists the first *unlock level + 4* scenarios;
  the level (save +0x4A04) becomes 1 after four stories are cleared and 2 after five.
- **Change:** 0x150DE4 `lw v1,0x4A04(v0)` -> `li v1,2`: the level is read as 2.
- **Limits:** the save's own level is untouched; clears are still recorded.
- *Verified headless 2026-10-29* (with `liger`: the select lists all seven).

## liger - the hidden seventh scenario
- **Original:** the select copies a 12-byte table of scenario wrestler ids from 0x3A6518 (six
  u16 ids) and maps an id to its script file by searching six entries (0x1E51E8). STORY07's id
  0x0F is in neither.
- **Change:** 0x150DE8 `addiu s4,v1,4` -> `li s4,7` (seven entries, whatever the level); the
  table copy at 0x1E51C0-0x1E51D4 copies 16 bytes instead of 12 (`lwl/lwr/swl/swr` ->
  `ldl/ldr/sdl/sdr`; the stack frame holds 16); entry 7 (0x3A6524) = 0x0F; the lookup takes
  seven entries (`slti v0,a0,6` -> 7).
- **Limits:** on its own it also opens the six normal scenarios (the list is in order). The script's
  `main` called its chapter menu; `tools/ligerstory.py` points it at chapter 1, like the other stories.
  Clearing it is recorded like any story.
- *Verified headless 2026-10-29*: "Liger" appears seventh and chapter 1
  plays.
- **The matches:** the scenario's script is rebuilt so its matches are played (`tools/ligerstory.py`,
  `tools/storywrestlers.py`; docs/TECHNICAL.md "The Liger scenario"). This is in the story data of
  every build, but only this group can reach it. *Seen headless 2026-10-30*: a test build chained all
  26 matches (1-minute limit): each loads with its card, wrestlers, ring and results screen. Both
  endings play, roll the credits (START leaves them), offer the save and return to the main menu, as
  Misawa's ending does. Losing to Pegasus goes to Game Over: Retry replays the match, Quit > Yes returns to
  the main menu. Saving mid-story and resuming *verified in game (owner, 2026-10-30)*. Difficulty is not tested.

## debug-chapters - stories start at the chapter menu (developer builds only)
- **Original:** VM init (0x1E5408) starts at symbol record *count* (`main`), which calls
  `<name>001`. Record *count - 1* is every script's chapter menu `<name>000`.
- **Change:** 0x1E5480 `lw v1,0(a1)` (0x18, the record base) -> `li v1,-0x20`, so the start is
  record *count - 1*. A choice or jump moves the VM's start function, and returning from it ends
  the story as usual (a clear), so the menu works as a start.
- **Limits:** a resumed story save starts where it was saved (0x1E9038 sets its own start).
  Starting mid-story begins with score 0.
- *Verified headless 2026-10-29* (Misawa's menu, chapter 1 plays).

## title-match - Title Match open
- **Original:** the main menu's Title Match needs a flag set at 0x1564EC when the count of
  cleared Victory Road courses is above 0 (`blezl v0,+3` skips the set).
- **Change:** 0x1564F4 -> `nop`: the flag is always set.
- *Not yet verified.*

## unlock-level - the top unlock level
- **Original:** the unlock level 0-3 (save +0x46D2) rises with cleared stories and Victory Road
  courses. Through the getter 0x113460 it sets the edit wrestler's point budget (150/200/250/300),
  at 3 adds 17 faces, and above 0 adds Staff Credit to Options. Two more reads, 0x117A48 (the
  promotion lists) and 0x117438 (Promotion Edit's pool), hide 45 wrestlers while it is 0. 10 preset
  teams wait on a separate flag, save +0x46D1, set by a Victory Road clear
  (docs/HIDDEN_CONTENT.md "What unlocks what").
- **Change:** all three reads return 3: 0x11346C `lbu v0,0x46D2(v1)` -> `li v0,3`, 0x117438
  `lbu a0,0x46D2(v1)` -> `li a0,3`, 0x117A48 `lbu v1,0x46D2(v0)` -> `li v1,3`; and 0x115D14 `beqz`
  -> `nop` lists the teams. As in Fire Pro Wrestling D, the save is not changed: the same card works
  with the normal patches, which go back to what the save says.
- *Verified in game 2026-10-30* (all wrestlers listed and playable, 300 edit points; save unchanged
  seen headless). The teams: *verified headless 2026-10-30* (39 in the list, save flag still 0).

## rings - the unused rings in the menu
- **Original:** ring ids 0-22 index tables of mat and post files and post layouts; ids 23 up are
  edit rings. Six complete ring sets are in no table (docs/HIDDEN_CONTENT.md "Unused rings").
- **Change:** `tools/rings.py` moves the tables, the menu's names and its order list into the dead
  debug readout at 0x1206A0 (2,488 bytes) and adds seven rings as ids 23-29: Independent World, Pale
  Blue, Lilac, NONNON, Battration / Battlarts, UWH / UWF and F.P.Z. Edit rings move to id 30 up. The
  F.P.Z. ring is the unused model `MAT97.SOB` pointed at the unused `MAT_99.GST`, which is overwritten
  with the F.P.Z. mat, with the apron and posts of set 13.
- **Limits:** a saved setting holding an edit ring points at a different ring under this patch. New
  rings take Grey's values from the table at 0x2E03F8 (read for every id above 22, as for edit rings).
- *Verified in game 2026-10-30* (the new rings, an edit promotion's ring, logo and colours).

## venues - the dojo in the Venue row
- **Original:** the row's cycle skips the story's dojo (venue 10), which has no name.
- **Change:** the row goes on from venue 9 to 10 and then RANDOM, in both copies of the menu (0x18801C,
  0x188080, 0x18C660, 0x18C6C0), and `tools/rings.py` names it "Dojo" at 0x120F00. The rule-only venues
  5-8 stay out: they only turn a match into those rules (owner 2026-10-30).
- **Photo:** the row's picture (0x183160) has a case for RANDOM on the second sheet (`PLACE02`) and a
  grid on the first, which is full. A hook at 0x120F20 gives the dojo a case too: the card below
  RANDOM's, drawn at build time from the story's `DOUJYOU` in the sheet's 54 free colours, in RANDOM's
  outline. The screens read the sheet from the packs `S_ONEMCH` and `S_TITLE`, so they are patched too.
- *Verified in game 2026-10-30* (the row, the photo, One Night Match and Tournament).

## moves - the unlisted moves in edit mode
- **Original:** edit mode's move lists leave out six moves that have motion data
  (docs/HIDDEN_CONTENT.md "Moves nobody can get").
- **Change:** `tools/movelists.py` moves lists 5, 12 and 20 into the dead debug readout (0x120C00) with
  the six added after their neighbours. Move 1059 has no name in the game: Jumping Splash, for what
  it does. 660 translates the same as 659, so it is Super Muscle Buster.
- *Verified in game 2026-10-30* (all six in the lists, animations and reactions in a match).

## edit-colours - neutral default costume colours (every translated build)
- **Original:** pure green is the placeholder for unset colours: ramp 322 of `PALET.TAC` (all four
  entries, 30,094 uses across the built-in wrestlers' unset slots), the default edit wrestler and
  referee, and the eight built-in referees. A newly added part came out flat green, with its design
  lost, and the 17 extra faces' hair and hoods turned green.
- **Change:** those colours become black-to-grey ramps. Wrestlers already saved keep their colours,
  and a face's preset (SQUARE + LEFT / RIGHT) still loads its own.
- *Verified in game 2026-10-30* (faces, costume parts, referees).

## cpu-labels - CPU logic labels off the diamonds (every translated build)
- **Original:** option labels start at x 0x1A (0x143F30), right against the diamonds; the English needs
  more room than the Japanese did.
- **Change:** labels and their button icons (0x144EBC) move 7 px right together, the gap the
  half-letter shift gave Pick Up. All 39 labels are drawn without that shift.
- *Verified in game 2026-10-30.*

## debug-menu - the developers' mode select (developer builds only)
- **Original:** 0x151AA8 (a number picker over the list at 0x3128C0) has no caller.
- **Change:** the main loop's call to the main menu (0x151758 `jal 0x156470`) calls it instead.
- **Limits:** the real main menu is gone while it is in, and the labels on screen are out of date:
  the number goes to the main menu's switch, so 0-10 open the eleven modes in menu order and the test
  rows do nothing. The full table is in [HIDDEN_CONTENT.md](HIDDEN_CONTENT.md#the-developers-mode-select). Never released.
- *Verified headless 2026-10-30*: every mode number run, and backing out returns to the menu.
