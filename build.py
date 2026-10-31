#!/usr/bin/env python3
"""Build the translated image from the original. Standard library only.

  python3 build.py [--name NAME] [--unlocks all|none|GROUP,...] [--clean]
      -> build/NAME.<ext> (default NAME: "<game> (English)")

Steps (default folders shown; move any of them with the folder options - see --help):
  1. verify the original in rom/ (size + SHA-1; --skip-verify skips the hash)
  2. prepare build/NAME: a fresh copy of the original, or - much faster for big images - the last
     build with every range it wrote restored from the original (tools/image.py; --clean copies)
  3. text: translation/script/ and translation/text/ into the game's files (TEXT_STEPS)
  4. code patches picked by --unlocks (CODE_PATCHES, tools/codepatch.py; debug-* groups only when named)
  5. images: for every catalogued image the English file the catalogue picks (hand-made >
     approved > rendered), imported by tools/gfx.py; the final set is copied to review/images-english/
  6. write every changed file back into the image (files that fit in place first)

Two name sets (e.g. real wrestlers' names and the game's parody names, two releases): fill
NAME_SETS; --names picks one (default the first) and text steps read NAMES. Names are written as
tokens in translation/ (`<Name>`) that the project's names tool resolves per set (Fire Pro
Wrestling S tools/names.py, D tools/fpdtext.py); lint's NAME_TOKEN checks them.

Test builds: --boot PART starts the game straight in PART (BOOT_PATCHES, once known);
--no-translation skips text and images, and gameplay patches unless --unlocks is given - on its
own the result is byte-identical to the original (tools/check.py --control proves it).
Developer flags (never for releases): --no-text FILE skips one text file.
"""
import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'tools'))
import catalog  # noqa: E402
import codepatch  # noqa: E402
import disc  # noqa: E402
import fpz  # noqa: E402
import gfx  # noqa: E402
import image  # noqa: E402
import fpztext  # noqa: E402
import paths  # noqa: E402
import movelists  # noqa: E402
import rings  # noqa: E402

# Gameplay patches: (group, file, address, original, new, description) - see tools/codepatch.py.
# Groups named debug-* are developer extras (debug menus, cheat windows): never in "all" or the
# default, only when named, never in a release variant.
GREY_4 = bytes.fromhex('c6986bad31c618e3')    # 4 and 8 colours, black to grey
GREY_8 = bytes.fromhex('638ca594e79c4aa9adb510c294d218e3')
REFEREE_GREEN = [      # the 8 built-in edit referees' unset colours: (address, ramps of 4)
    (0x215C9E, 5), (0x215CF6, 3), (0x215D26, 3), (0x215D4E, 2), (0x215D66, 3), (0x215D8E, 4),
    (0x215DBE, 4), (0x215E36, 5), (0x215E8E, 3), (0x215EBE, 3), (0x215EE6, 2), (0x215EFE, 3),
    (0x215F26, 4), (0x215F56, 4), (0x215FCE, 5), (0x216026, 3), (0x216056, 3), (0x21607E, 2),
    (0x216096, 3), (0x2160BE, 4), (0x2160EE, 4), (0x216166, 5), (0x2161BE, 3), (0x2161EE, 3),
    (0x216216, 2), (0x21622E, 3), (0x216256, 4), (0x216286, 4), (0x2162FE, 5), (0x216356, 3),
    (0x216386, 3), (0x2163AE, 6), (0x2163EE, 4), (0x21641E, 4), (0x216496, 5), (0x2164EE, 3),
    (0x21651E, 1), (0x216546, 2), (0x21655E, 3), (0x216586, 4), (0x2165B6, 4), (0x21662E, 5),
    (0x216686, 3), (0x2166B6, 3), (0x2166DE, 2), (0x2166F6, 3), (0x21671E, 4), (0x21674E, 4),
    (0x2167C6, 5), (0x21681E, 3), (0x21684E, 3), (0x216876, 2), (0x21688E, 3), (0x2168B6, 4),
    (0x2168E6, 4),
]
CODE_PATCHES = [
    # Group 'brightness': always part of the English build (owner 2026-10-29: the dim title and main
    # menu are to be full brightness, not optional - docs/TECHNICAL.md "Title and main menu
    # brightness"). Title screen: the title code draws the logo pieces with colour
    # 0x20606060 (RGB 0x60 = 75% of the GS's 0x80 = 1.0), the copyright with 0x80606060 and PRESS
    # START with 0x80505050; these set RGB to 0x80.
    ('brightness', 'SLPM_623.42', 0x1576DC, 0x3C082060, 0x3C082080, 'title logo at full brightness'),  # lui t0,0x2060
    ('brightness', 'SLPM_623.42', 0x1576F0, 0x35086060, 0x35088080, None),                           # ori t0,0x6060
    ('brightness', 'SLPM_623.42', 0x15774C, 0x3C088060, 0x3C088080, 'copyright at full brightness'),
    ('brightness', 'SLPM_623.42', 0x15776C, 0x35086060, 0x35088080, None),
    ('brightness', 'SLPM_623.42', 0x15791C, 0x3C088050, 0x3C088080, 'PRESS START at full brightness'),
    ('brightness', 'SLPM_623.42', 0x157938, 0x35085050, 0x35088080, None),
    # Main menu at full brightness: its code draws the label strip with 0x80585858 and
    # the flame layers with 0x50 grey (alpha computed); these set RGB to 0x80.
    ('brightness', 'SLPM_623.42', 0x154EBC, 0x3C088058, 0x3C088080, 'main menu colours at full brightness'),
    ('brightness', 'SLPM_623.42', 0x155800, 0x3C088058, 0x3C088080, None),
    ('brightness', 'SLPM_623.42', 0x155838, 0x3C088058, 0x3C088080, None),
    ('brightness', 'SLPM_623.42', 0x1561F0, 0x3C088058, 0x3C088080, None),
    ('brightness', 'SLPM_623.42', 0x155A54, 0x3C080058, 0x3C080080, None),
    ('brightness', 'SLPM_623.42', 0x15710C, 0x3C080058, 0x3C080080, None),
    ('brightness', 'SLPM_623.42', 0x154EC4, 0x35085858, 0x35088080, None),
    ('brightness', 'SLPM_623.42', 0x155818, 0x35085858, 0x35088080, None),
    ('brightness', 'SLPM_623.42', 0x155868, 0x35085858, 0x35088080, None),
    ('brightness', 'SLPM_623.42', 0x155A60, 0x35085858, 0x35088080, None),
    ('brightness', 'SLPM_623.42', 0x156208, 0x35085858, 0x35088080, None),
    ('brightness', 'SLPM_623.42', 0x157114, 0x35085858, 0x35088080, None),
    ('brightness', 'SLPM_623.42', 0x155024, 0x3C150050, 0x3C150080, None),
    ('brightness', 'SLPM_623.42', 0x155044, 0x36B55050, 0x36B58080, None),
    ('brightness', 'SLPM_623.42', 0x15512C, 0x3C130050, 0x3C130080, None),
    ('brightness', 'SLPM_623.42', 0x155154, 0x36735050, 0x36738080, None),
    ('brightness', 'SLPM_623.42', 0x155DAC, 0x3C160050, 0x3C160080, None),
    ('brightness', 'SLPM_623.42', 0x155DD8, 0x36D65050, 0x36D68080, None),
    ('brightness', 'SLPM_623.42', 0x1568E0, 0x3C130050, 0x3C130080, None),
    ('brightness', 'SLPM_623.42', 0x1568F4, 0x36735050, 0x36738080, None),
    # the mode labels (PACK01_A) are drawn with 0x505050 built at run time (0x1567B4 / 0x15682C)
    ('brightness', 'SLPM_623.42', 0x1567B4, 0x3C030050, 0x3C030080, 'main menu labels at full brightness'),
    ('brightness', 'SLPM_623.42', 0x15682C, 0x34425050, 0x34428080, None),
    # The other menus' backgrounds (flames, wrestler select, edit, story, save, options, results):
    # grey sprite colours 0x40-0x70 in the menu code raised to 0x80 (owner approved 2026-10-29 after
    # a before/after sweep). Colours 0x7F (already full) and alpha-FF 0x5F/0x3F shades are left.
    ('brightness', 'SLPM_623.42', 0x142E90, 0x3C088060, 0x3C088080, 'menu backgrounds at full brightness'),
    ('brightness', 'SLPM_623.42', 0x142ED8, 0x35086060, 0x35088080, None),
    ('brightness', 'SLPM_623.42', 0x143964, 0x3C088040, 0x3C088080, None),
    ('brightness', 'SLPM_623.42', 0x143980, 0x35084040, 0x35088080, None),
    ('brightness', 'SLPM_623.42', 0x1439D0, 0x3C088040, 0x3C088080, None),
    ('brightness', 'SLPM_623.42', 0x1439E0, 0x35084040, 0x35088080, None),
    ('brightness', 'SLPM_623.42', 0x143A14, 0x3C088040, 0x3C088080, None),
    ('brightness', 'SLPM_623.42', 0x143A2C, 0x35084040, 0x35088080, None),
    ('brightness', 'SLPM_623.42', 0x143AF0, 0x3C084040, 0x3C084080, None),
    ('brightness', 'SLPM_623.42', 0x143B04, 0x35084040, 0x35088080, None),
    ('brightness', 'SLPM_623.42', 0x143B54, 0x3C084040, 0x3C084080, None),
    ('brightness', 'SLPM_623.42', 0x143B64, 0x35084040, 0x35088080, None),
    ('brightness', 'SLPM_623.42', 0x143B98, 0x3C084040, 0x3C084080, None),
    ('brightness', 'SLPM_623.42', 0x143BAC, 0x35084040, 0x35088080, None),
    ('brightness', 'SLPM_623.42', 0x143BF4, 0x3C084060, 0x3C084080, None),
    ('brightness', 'SLPM_623.42', 0x143C0C, 0x35086060, 0x35088080, None),
    ('brightness', 'SLPM_623.42', 0x143CF0, 0x3C080060, 0x3C080080, None),
    ('brightness', 'SLPM_623.42', 0x143D00, 0x35086060, 0x35088080, None),
    ('brightness', 'SLPM_623.42', 0x1477A4, 0x3C050050, 0x3C050080, None),
    ('brightness', 'SLPM_623.42', 0x1477AC, 0x34A55050, 0x34A58080, None),
    ('brightness', 'SLPM_623.42', 0x14786C, 0x3C050050, 0x3C050080, None),
    ('brightness', 'SLPM_623.42', 0x147878, 0x34A55050, 0x34A58080, None),
    ('brightness', 'SLPM_623.42', 0x147BD4, 0x3C050050, 0x3C050080, None),
    ('brightness', 'SLPM_623.42', 0x147BE0, 0x34A55050, 0x34A58080, None),
    ('brightness', 'SLPM_623.42', 0x147BE8, 0x3C050050, 0x3C050080, None),
    ('brightness', 'SLPM_623.42', 0x147BF0, 0x34A55050, 0x34A58080, None),
    ('brightness', 'SLPM_623.42', 0x147C3C, 0x3C050050, 0x3C050080, None),
    ('brightness', 'SLPM_623.42', 0x147C44, 0x34A55050, 0x34A58080, None),
    ('brightness', 'SLPM_623.42', 0x147C4C, 0x3C050050, 0x3C050080, None),
    ('brightness', 'SLPM_623.42', 0x147C54, 0x34A55050, 0x34A58080, None),
    ('brightness', 'SLPM_623.42', 0x148534, 0x3C050050, 0x3C050080, None),
    ('brightness', 'SLPM_623.42', 0x148538, 0x34A55050, 0x34A58080, None),
    ('brightness', 'SLPM_623.42', 0x148790, 0x3C050050, 0x3C050080, None),
    ('brightness', 'SLPM_623.42', 0x14879C, 0x34A55050, 0x34A58080, None),
    ('brightness', 'SLPM_623.42', 0x148BC4, 0x3C050050, 0x3C050080, None),
    ('brightness', 'SLPM_623.42', 0x148BC8, 0x34A55050, 0x34A58080, None),
    ('brightness', 'SLPM_623.42', 0x148E68, 0x3C050050, 0x3C050080, None),
    ('brightness', 'SLPM_623.42', 0x148E74, 0x34A55050, 0x34A58080, None),
    ('brightness', 'SLPM_623.42', 0x148E80, 0x3C050050, 0x3C050080, None),
    ('brightness', 'SLPM_623.42', 0x148E88, 0x34A55050, 0x34A58080, None),
    ('brightness', 'SLPM_623.42', 0x148E98, 0x3C050050, 0x3C050080, None),
    ('brightness', 'SLPM_623.42', 0x148EA0, 0x34A55050, 0x34A58080, None),
    ('brightness', 'SLPM_623.42', 0x14936C, 0x3C050050, 0x3C050080, None),
    ('brightness', 'SLPM_623.42', 0x14937C, 0x34A55050, 0x34A58080, None),
    ('brightness', 'SLPM_623.42', 0x15633C, 0x3C088070, 0x3C088080, None),
    ('brightness', 'SLPM_623.42', 0x156344, 0x35087070, 0x35088080, None),
    ('brightness', 'SLPM_623.42', 0x15820C, 0x3C088070, 0x3C088080, None),
    ('brightness', 'SLPM_623.42', 0x15823C, 0x35087070, 0x35088080, None),
    ('brightness', 'SLPM_623.42', 0x158E8C, 0x3C050060, 0x3C050080, None),
    ('brightness', 'SLPM_623.42', 0x158E94, 0x34A56060, 0x34A58080, None),
    ('brightness', 'SLPM_623.42', 0x159288, 0x3C088060, 0x3C088080, None),
    ('brightness', 'SLPM_623.42', 0x159290, 0x35086060, 0x35088080, None),
    ('brightness', 'SLPM_623.42', 0x15A7DC, 0x3C05FF5F, 0x3C05FF80, None),
    ('brightness', 'SLPM_623.42', 0x15A7E4, 0x34A55F5F, 0x34A58080, None),
    ('brightness', 'SLPM_623.42', 0x15CD28, 0x3C05FF5F, 0x3C05FF80, None),
    ('brightness', 'SLPM_623.42', 0x15CD30, 0x34A55F5F, 0x34A58080, None),
    ('brightness', 'SLPM_623.42', 0x15CD50, 0x3C05FF5F, 0x3C05FF80, None),
    ('brightness', 'SLPM_623.42', 0x15CD58, 0x34A55F5F, 0x34A58080, None),
    ('brightness', 'SLPM_623.42', 0x15CD70, 0x3C05FF5F, 0x3C05FF80, None),
    ('brightness', 'SLPM_623.42', 0x15CD7C, 0x34A55F5F, 0x34A58080, None),
    ('brightness', 'SLPM_623.42', 0x15F180, 0x3C05FF5F, 0x3C05FF80, None),
    ('brightness', 'SLPM_623.42', 0x15F188, 0x34A55F5F, 0x34A58080, None),
    ('brightness', 'SLPM_623.42', 0x15F190, 0x3C05FF5F, 0x3C05FF80, None),
    ('brightness', 'SLPM_623.42', 0x15F198, 0x34A55F5F, 0x34A58080, None),
    ('brightness', 'SLPM_623.42', 0x15F1A0, 0x3C05FF5F, 0x3C05FF80, None),
    ('brightness', 'SLPM_623.42', 0x15F1A8, 0x34A55F5F, 0x34A58080, None),
    ('brightness', 'SLPM_623.42', 0x15F1B0, 0x3C05FF5F, 0x3C05FF80, None),
    ('brightness', 'SLPM_623.42', 0x15F1B8, 0x34A55F5F, 0x34A58080, None),
    ('brightness', 'SLPM_623.42', 0x161EC0, 0x3C088050, 0x3C088080, None),
    ('brightness', 'SLPM_623.42', 0x161ED0, 0x35085050, 0x35088080, None),
    ('brightness', 'SLPM_623.42', 0x16200C, 0x3C083050, 0x3C083080, None),
    ('brightness', 'SLPM_623.42', 0x16205C, 0x35085050, 0x35088080, None),
    ('brightness', 'SLPM_623.42', 0x162094, 0x3C088050, 0x3C088080, None),
    ('brightness', 'SLPM_623.42', 0x1620D0, 0x35085050, 0x35088080, None),
    ('brightness', 'SLPM_623.42', 0x16221C, 0x3C088060, 0x3C088080, None),
    ('brightness', 'SLPM_623.42', 0x162234, 0x35086060, 0x35088080, None),
    ('brightness', 'SLPM_623.42', 0x162284, 0x3C088060, 0x3C088080, None),
    ('brightness', 'SLPM_623.42', 0x16229C, 0x35086060, 0x35088080, None),
    ('brightness', 'SLPM_623.42', 0x1622F4, 0x3C087050, 0x3C087080, None),
    ('brightness', 'SLPM_623.42', 0x162330, 0x35085050, 0x35088080, None),
    ('brightness', 'SLPM_623.42', 0x162364, 0x3C088060, 0x3C088080, None),
    ('brightness', 'SLPM_623.42', 0x1623A4, 0x35086060, 0x35088080, None),
    ('brightness', 'SLPM_623.42', 0x16563C, 0x3C05FF6F, 0x3C05FF80, None),
    ('brightness', 'SLPM_623.42', 0x165674, 0x34A56F6F, 0x34A58080, None),
    # Pure green is the game's placeholder for unset costume colours: PALET.TAC's ramp 322 (a built-in
    # wrestler's unset slots, 30,094 uses), the default edit wrestler and referee, the 8 built-in
    # referees. It flattens a new part's design: black-to-grey ramps instead (owner 2026-10-30).
    ('edit-colours', 'SLPM_623.42', 0x30C4EA, bytes.fromhex('e083') * 8, GREY_8, 'neutral default costume colours'),
    ('edit-colours', 'SLPM_623.42', 0x30C6AE, bytes.fromhex('e083') * 8, GREY_8, None),
    ('edit-colours', 'PALET.TAC', 0x19170, bytes.fromhex('e083') * 4, GREY_4, None),
    *[('edit-colours', 'SLPM_623.42', a, bytes.fromhex('e083') * (n * 4), GREY_4 * n, None) for a, n in REFEREE_GREEN],
    # CPU logic: option labels and their button icons 7 px further from the diamonds, the gap the
    # half-letter shift gave Pick Up (owner 2026-10-30).
    ('cpu-labels', 'SLPM_623.42', 0x143F30, 0x2406001A, 0x24060021, None),  # li a2,0x1a -> 0x21
    ('cpu-labels', 'SLPM_623.42', 0x144EBC, 0x24420017, 0x2442001E, 'CPU logic labels moved off the diamonds'),
    # 'venues': the Venue row cycles 0-4, 9, RANDOM. The story's dojo (10) goes after 9, in the two
    # copies of the menu. Venues 5-8 stay with their match rules (owner 2026-10-30).
    *[('venues', 'SLPM_623.42', a, 0x24020009, 0x2402000A, None) for a in (
        0x18801C, 0x188080, 0x18C660, 0x18C6C0)],    # RANDOM <- 10 going left, 10 -> RANDOM going right
    # Unlocks and hidden content (docs/HIDDEN_CONTENT.md, docs/PATCHES.md).
    # 'scenarios': story select shows table entries 0 .. unlock level + 4 (level 1 after four
    # clears adds Okita, 2 after five adds Kashiwada); reading the level as 2 shows all six.
    ('scenarios', 'SLPM_623.42', 0x150DE4, 0x8C434A04, 0x24030002, 'all six story scenarios open'),  # lw v1,0x4a04(v0) -> li v1,2
    # 'liger': the 7th scenario (STORY07, Keiichi Yamada / Liger, wrestler 0x0F) is in no table.
    # The select shows 7 entries; the id table copied from 0x3A6518 grows to 16 bytes with 0x0F
    # as entry 7, and the id -> file lookup (0x1E51E8) takes 7 entries.
    # Its main called its chapter menu; tools/ligerstory.py points it at chapter 1 like the others.
    ('liger', 'SLPM_623.42', 0x150DE8, 0x24740004, 0x24140007, 'hidden Liger scenario in story select'),  # count = 7
    ('liger', 'SLPM_623.42', 0x1E51C0, 0x88E5000B, 0x68E5000F, None),   # lwl a1 -> ldl: copy 16 bytes
    ('liger', 'SLPM_623.42', 0x1E51C4, 0x98E50008, 0x6CE50008, None),   # lwr a1 -> ldr
    ('liger', 'SLPM_623.42', 0x1E51D0, 0xABA5000B, 0xB3A5000F, None),   # swl a1 -> sdl
    ('liger', 'SLPM_623.42', 0x1E51D4, 0xBBA50008, 0xB7A50008, None),   # swr a1 -> sdr
    ('liger', 'SLPM_623.42', 0x1E51E8, 0x28820006, 0x28820007, None),   # slti v0,a0,6 -> 7
    ('liger', 'SLPM_623.42', 0x3A6524, b'\x00\x00', b'\x0f\x00', None),  # table entry 7 = 0x0F
    # 'debug-chapters' (developers only, owner 2026-10-30): every story starts at its chapter menu (<name>000, the symbol
    # before main) instead of main: VM init reads the start record as symbols + count * 0x38;
    # v1 = 0x18 - 0x38 = -0x20 makes it count - 1. Resumed saves set their own start.
    ('debug-chapters', 'SLPM_623.42', 0x1E5480, 0x8CA30000, 0x2403FFE0, 'stories start at the chapter menu'),
    # 'title-match': the main menu's Title Match needs one Victory Road course cleared (flag set
    # at 0x1564EC when the course count is > 0); skip the count check.
    ('title-match', 'SLPM_623.42', 0x1564F4, 0x58400003, 0x00000000, 'Title Match open'),  # blezl -> nop
    # 'unlock-level': the unlock level (0-3, from stories and Victory Road courses) read as 3 at
    # all three reads: edit wrestlers get the top point budget (300) and the 17 extra faces, Staff
    # Credit is in Options, and the 45 hidden wrestlers are listed. The 10 extra preset teams hang
    # on a flag of their own (save +0x46D1, set by a Victory Road clear). The save is not changed.
    ('unlock-level', 'SLPM_623.42', 0x11346C, 0x906246D2, 0x24020003, 'unlock level 3'),  # lbu -> li v0,3
    ('unlock-level', 'SLPM_623.42', 0x117438, 0x906446D2, 0x24040003, None),  # lbu -> li a0,3
    ('unlock-level', 'SLPM_623.42', 0x117A48, 0x904346D2, 0x24030003, 'hidden wrestlers listed'),  # lbu -> li v1,3
    ('unlock-level', 'SLPM_623.42', 0x115D14, 0x1040001D, 0x00000000, 'preset teams 29-38 listed'),  # beqz -> nop
    # 'debug-menu': the developers' mode select (0x151AA8, no callers) in place of the main menu.
    # Its test modes are gone: the number it returns goes to the normal main-menu switch.
    ('debug-menu', 'SLPM_623.42', 0x151758, 0x0C05591C, 0x0C0546AA, 'developer mode select instead of the main menu'),
]
ALWAYS_GROUPS = {'brightness', 'edit-colours', 'cpu-labels'}       # in every translated build, not a choice (--unlocks can't drop them)
UNLOCK_GROUPS = sorted(({p[0] for p in CODE_PATCHES} | {'rings', 'moves'}) - ALWAYS_GROUPS)
PLAYER_GROUPS = [g for g in UNLOCK_GROUPS if not g.startswith('debug-')]
DEFAULT_GROUPS = set()               # groups in the plain English build (owner decides; --unlocks all = PLAYER_GROUPS)

# --boot: (part, file, address, original, new) - patches that start the game in a given part.
BOOT_PATCHES = {
}


def to_offset(name, addr):
    """GAME-SPECIFIC: file offset of a RAM address in file `name` (overlay base, ELF segments, ...)."""
    if name == 'SLPM_623.42':
        return addr - 0xFF000           # the ELF's segments: RAM = file offset + 0xFF000
    if name == 'PALET.TAC':
        return addr
    raise SystemExit(f'build.py to_offset(): no address mapping for {name} yet')


# Text steps: (text file or folder under translation/, function(path, files)). Each inserts the
# English into the game's files through `files` and stops with a clear message if anything doesn't fit.
# Zero-padding files a grown file may take room from when the disc is full (PS2 disc.py
# take_from_padding: their end is cut off) - e.g. ['/DUMMY.DAT']; check they are all zeros.
PADDING_DONORS = []

# Name sets for the --names option, e.g. ('real', 'parody') - empty: one set, no option.
NAME_SETS = ('real', 'parody')   # owner, 2026-10-29: test builds use real (the default)
NAMES = NAME_SETS[0] if NAME_SETS else None

TEXT_STEPS = [
    ('text/wrestlers.csv', lambda p, f: fpztext.step_roster(f, NAMES)),
    ('text/moves.csv', lambda p, f: fpztext.step_moves(f, NAMES)),
    ('text/fixed.csv', lambda p, f: fpztext.step_fixed(f, NAMES)),
    ('text/ui.csv', lambda p, f: fpztext.step_ui(f, NAMES)),
    ('script', lambda p, f: fpztext.step_story(f, NAMES)),
    ('text/ui.csv', lambda p, f: fpztext.step_name_entry(f, NAMES)),    # the English keyboard
    ('text/ui.csv', lambda p, f: fpztext.step_cpu_icons(f, NAMES)),     # CPU logic button icons
    ('text/ui.csv', lambda p, f: fpztext.step_move_icons(f, NAMES)),    # move editor labels
    ('text/ui.csv', lambda p, f: ring_names_step()),              # the new rings' menu names
    ('text', lambda p, f: fpztext.step_fonts(f, NAMES)),          # last: the pair glyphs all steps used
]


RING_NAMES = None    # the rings group: names as the game's bytes, or None (no translation)
RING_GROUP = False
DOJO_NAME = None     # the same for the venues group
DOJO_GROUP = False


def ring_names_step():
    global RING_NAMES, DOJO_NAME
    if RING_GROUP:
        RING_NAMES = rings.names(NAMES)
    if DOJO_GROUP:
        DOJO_NAME = fpztext.encode(rings.VENUE_DOJO, center=True)


class Files:
    """The game's files for this build: read from the image on first use, written back at the end."""

    def __init__(self, d):
        self.d, self.data, self.changed = d, {}, set()

    def get(self, name):
        if name not in self.data:
            self.data[name] = bytearray(self.d.read_file(self.d.find(name)))
        return self.data[name]

    def put(self, name, data):
        self.data[name] = bytearray(data)
        self.changed.add(name)


def unlock_groups(value):
    if value == 'all':
        return set(PLAYER_GROUPS)
    if value == 'none':
        return set()
    groups = {g.strip() for g in value.split(',') if g.strip()}
    if groups - set(UNLOCK_GROUPS):
        raise argparse.ArgumentTypeError(f'expected all, none or some of {",".join(UNLOCK_GROUPS) or "(no groups yet)"}')
    return groups


def models_step(files):
    """3D models made for the English (the result-screen words, private/work/img/moji3d.py):
    every translation/images-handmade/models/NAME.SOB replaces FPFILES.OAH's NAME.SOB."""
    folder = paths.HANDMADE / 'models'
    models = sorted(folder.glob('*.SOB')) if folder.exists() else []
    if not models:
        return
    a = fpz.Oah(bytes(files.get('FPFILES.OAH')))
    for m in models:
        a.write(m.name, m.read_bytes())
    files.put('FPFILES.OAH', a.bytes())
    print(f'models: {len(models)} 3D words ({", ".join(m.stem for m in models)})')


def images_step(files):
    final = catalog.final_images()
    missing, changed, _ = catalog.stale()
    if missing or changed:
        print(f'note: {len(missing) + len(changed)} automatic renders are out of date - run tools/render.py '
              f'(building with the frozen files there are)')
    n = gfx.import_images({k: p for k, (tag, p) in final.items()}, files)
    if paths.ENGLISH_IMAGES.exists():
        shutil.rmtree(paths.ENGLISH_IMAGES)
    if final:
        paths.ENGLISH_IMAGES.mkdir(parents=True)
        for name, (tag, p) in final.items():
            dst = paths.ENGLISH_IMAGES / f'{name}.png'
            dst.parent.mkdir(parents=True, exist_ok=True)      # ids can be archive paths
            shutil.copyfile(p, dst)
        counts = {}
        for tag, _ in final.values():
            counts[tag] = counts.get(tag, 0) + 1
        print(f'images: {n} imported (' + ', '.join(f'{c} {t}' for t, c in sorted(counts.items())) + ')')


def verify_original(original):
    """SHA-1 of the original image, once: the result is remembered with the file's size and
    modification time (build/original.verified), so later builds only re-hash a changed file
    (a DVD image takes ~20 s to hash)."""
    st = original.stat()
    stamp = f'{original.resolve()} {st.st_size} {st.st_mtime_ns} {paths.ORIGINAL["sha1"]}'
    memo = paths.BUILD / 'original.verified'
    if memo.exists() and memo.read_text() == stamp:
        return
    print('verifying the original...')
    if image.sha1(original) != paths.ORIGINAL['sha1']:
        sys.exit(f'{original.name} does not match the expected SHA-1 {paths.ORIGINAL["sha1"]}')
    paths.BUILD.mkdir(parents=True, exist_ok=True)
    memo.write_text(stamp)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0], epilog=paths.FOLDER_HELP,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--name', default=f'{paths.GAME_FILE} (English)')
    ap.add_argument('--skip-verify', action='store_true', help="don't hash the original image")
    ap.add_argument('--clean', action='store_true', help='copy the original instead of restoring the last build')
    ap.add_argument('--no-translation', action='store_true', help='skip text and images (alone: identical to the original)')
    ap.add_argument('--unlocks', type=unlock_groups, metavar='all|none|GROUP,...',
                    help='gameplay patches: all (default; debug-* groups only when named), none or some groups; '
                         'none with --no-translation')
    if NAME_SETS:
        ap.add_argument('--names', choices=NAME_SETS, default=NAME_SETS[0],
                        help=f'name set: {" or ".join(NAME_SETS)} (default {NAME_SETS[0]})')
    ap.add_argument('--boot', choices=sorted(BOOT_PATCHES), help='TEST BUILD: start the game in this part')
    ap.add_argument('--no-text', action='append', default=[], metavar='FILE',
                    help='developer: leave this text file untranslated (repeatable)')
    args = ap.parse_args(paths.configure(sys.argv[1:] if argv is None else argv))
    global NAMES
    NAMES = getattr(args, 'names', NAMES)
    if args.unlocks is None:
        args.unlocks = set() if args.no_translation else set(DEFAULT_GROUPS)

    original = paths.ROM
    if not original.exists():
        sys.exit(f'put the original image in {paths.show(paths.ROM_DIR)} (or pass --rom): {paths.ORIGINAL_NAME}')
    if original.stat().st_size != paths.ORIGINAL['size']:
        sys.exit(f'{original.name}: {original.stat().st_size} bytes, expected {paths.ORIGINAL["size"]} - not the right image')
    if not args.skip_verify:
        verify_original(original)

    out = paths.BUILD / (args.name + original.suffix)
    with image.prepare(original, out, clean=args.clean) as f:
        d = disc.Disc(f, writable=True)
        files = Files(d)

        global RING_GROUP, DOJO_GROUP
        RING_GROUP = 'rings' in args.unlocks
        DOJO_GROUP = 'venues' in args.unlocks
        if not args.no_translation:
            for rel, step in TEXT_STEPS:
                if rel in args.no_text:
                    print(f'text: skipped {rel} (--no-text)')
                    continue
                step(paths.TRANSLATION / rel, files)

        codepatch.apply(files, CODE_PATCHES, set(args.unlocks) - ALWAYS_GROUPS, to_offset)
        if RING_GROUP:
            codepatch.apply(files, rings.patches(files.get('SLPM_623.42'), RING_NAMES, to_offset), {'rings'}, to_offset)
            rings.assets(files)
        if DOJO_GROUP:
            codepatch.apply(files, rings.venue_patches(files.get('SLPM_623.42'), DOJO_NAME, to_offset), {'venues'}, to_offset)
            codepatch.apply(files, rings.venue_photo_code(files.get('SLPM_623.42'), to_offset), {'venues'}, to_offset)
            rings.dojo_photo(files)
        if 'moves' in args.unlocks:
            codepatch.apply(files, movelists.patches(files.get('SLPM_623.42'), to_offset), {'moves'}, to_offset)
        if not args.no_translation:
            codepatch.apply(files, CODE_PATCHES, ALWAYS_GROUPS, to_offset)

        if not args.no_translation:
            images_step(files)
            models_step(files)

        if args.boot:
            codepatch.apply(files, [(args.boot, *p, f'TEST BUILD: boots into {args.boot}') for p in BOOT_PATCHES[args.boot]],
                            {args.boot}, to_offset)

        def fits(name):
            return (len(files.data[name]) + disc.SECTOR - 1) // disc.SECTOR <= d.allocated_sectors(d.find(name))
        for name in sorted(files.changed, key=lambda n: (not fits(n), n)):  # fixed order: same disc layout every build
            d.write_file(d.find(name), bytes(files.data[name]), relocate=True,
                         **({'donors': PADDING_DONORS} if PADDING_DONORS else {}))
            print(f'patched {name}')
    disc.companion_files(out, original)
    print(f'done: {paths.show(out)}  ({len(files.changed)} files patched)')
    return out


if __name__ == '__main__':
    main()
