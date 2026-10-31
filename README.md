# Fire Pro Wrestling Z — English Translation

An English translation patch for **Fire Pro Wrestling Z**, released for the PlayStation 2 in 2003, only in Japan.

The whole game is in English: every mode and menu, the seven story scenarios (over 12,000 pages of
text), the 244 wrestlers' names and profiles, 1,448 moves, and the menu graphics with Japanese text.
The hardest part was the story window, which holds 20 Japanese characters a line: English fits
because each cell is drawn as a pair of letters, in a font made for it.

**[See screenshots](docs/SCREENSHOTS.md)** of the patched game.

**[Read the player's guide](https://kactusken.github.io/Fire-Pro-Wrestling-Z-English/guide/)**: how to play, every mode, all 244 wrestlers and 1,448 moves with their numbers, the story walkthroughs and route map, and the secrets.

> **Status: first public beta.** Everything in scope is translated, and every game mode has been
> played in PCSX2, with the wrestler and team names checked in both name sets. Not every story route
> and ending has been played through, the difficulty of the Liger scenario hasn't been tested, and
> nothing has been tried on a real PS2. Some story lines leave a small gap before a wrestler's name.
> Please report problems ([how to report](#reporting-problems)).
> [CHANGELOG.md](CHANGELOG.md) lists what's in each release.

## Downloads

Get the latest zip from the [Releases](../../releases) page. It contains four patches. Pick one:

| Patch | What you get |
|---|---|
| **Fire Pro Wrestling Z (English) (Real Names)** | The translation with the real wrestlers' names, the game otherwise unchanged. |
| **Fire Pro Wrestling Z (English) (Parody Names)** | The translation with the game's own parody names, translated. |
| **... (Real Names) (All Unlocked)** / **(Parody Names) (All Unlocked)** | The same, plus every unlock: all six story scenarios, the hidden seventh (Jushin Thunder Liger), finished with real matches, Title Match open, the top edit point budget and all 244 wrestlers, 39 preset teams and 404 faces from the start, seven extra rings, six extra moves and the dojo venue. |

Each patch applies to the original disc on its own; they don't stack.

## How to patch

You need your own copy of the original Japanese disc. Disc images are not provided here.

- Game: *Fire Pro Wrestling Z* (Japan), serial SLPM-62342. Other releases haven't been checked.
- The image must match: `Fire Pro Wrestling Z (Japan).bin`, 462422016 bytes, CRC32 `5a32af02`,
  SHA-1 `da2a656e562cb85db3ececacc0d483eb650cb782`.

Then:

1. Apply the `.xdelta` patch with an xdelta tool:
   - [Rom Patcher JS](https://www.marcrobledo.com/RomPatcher.js/) runs in your web browser
     (CD images; it may not cope with a multi-GB DVD image).
   - Delta Patcher is a desktop app for Windows, macOS and Linux.
   - On the command line: `xdelta3 -d -s "Fire Pro Wrestling Z (Japan).bin" "patch.xdelta" "patched.bin"`
2. The zip has a `.cue` for each patch: name the patched `.bin` to match it and keep the two together.
3. Open the patched `.bin` in your emulator. Tested in PCSX2.

## Notes for players

- **Guide.** New to Fire Pro, or stuck? The [player's guide](https://kactusken.github.io/Fire-Pro-Wrestling-Z-English/guide/) covers everything from your first match to every story ending.
- **Names.** Two patches: *Real Names* uses the actual wrestlers' names; *Parody Names* keeps the
  game's own parody names, translated.
- **What's still in Japanese.** The staff credits, the title logo, promotion logos, in-world art
  (signs, T-shirts, arena graphics) and the memory card save title.
- **Saves.** Saves from the original Japanese game, or from another patch, may not be compatible.
  Start a new save with the patch you plan to keep.
- **Hidden content.** The game holds a seventh story scenario nothing can open (Jushin Thunder
  Liger); the *All Unlocked* patches open it, finished with real matches. More in
  [docs/HIDDEN_CONTENT.md](docs/HIDDEN_CONTENT.md); every route and ending in [docs/STORY.md](docs/STORY.md).

## Reporting problems

Open an [issue](../../issues) with:

- a screenshot,
- which patch you used,
- where you were: the mode and menu, or roughly what had just happened.

Text that is cut off, overlaps, or still shows Japanese is especially helpful.

## For ROM hackers and contributors

Everything needed to rebuild the patches from the original disc is in this repository: the
translated text, the patching code (Python 3, no dependencies for the build) and documentation of
the game's formats.

| Document | What's in it |
|---|---|
| [docs/BUILDING.md](docs/BUILDING.md) | Setting up, building, making patches, and the checking tools |
| [docs/TRANSLATION.md](docs/TRANSLATION.md) | Text file formats, scope, style guide, glossary, and naming decisions |
| [docs/EDITING.md](docs/EDITING.md) | Editing the in-game text graphics |
| [docs/PATCHES.md](docs/PATCHES.md) | How each code patch works |
| [docs/TECHNICAL.md](docs/TECHNICAL.md) | The game's disc layout, archives, compression, data formats, and memory map |
| [docs/PLATFORM.md](docs/PLATFORM.md) | PS2 pitfalls for this kind of work |
| [docs/HIDDEN_CONTENT.md](docs/HIDDEN_CONTENT.md) | Unlockables, debug features, and unused and cut content |
| [docs/guide/](docs/guide/index.html) | The player's guide (one page; data from `tools/guidedata.py` and `tools/storymap.py`) |
| [docs/STORY.md](docs/STORY.md) | Story mode: every route, decision, match and ending ([route map](docs/guide/index.html#route-map)) |
| [tools/README.md](tools/README.md) | Every tool, what it's for and how to run it |

Quick start:

```sh
python3 tools/extract.py                 # unpack the disc in rom/ into extracted/
python3 build.py                         # -> build/Fire Pro Wrestling Z (English).bin
python3 make_patches.py --version v0.1   # -> release/*.xdelta and a zip (needs xdelta3)
```

## Credits

- Translation and hacking: kactusken.
- Inspiration: Fatman Dave's 2004 partial menu patch for Fire Pro Wrestling Z - the first English
  work on this game. This translation is a new one, made from scratch.

## AI disclosure

AI assisted with the translation.

## Legal

This is a non-commercial fan translation, not affiliated with or endorsed by the game's developers
or publishers. It contains no copyrighted game data that would let
anyone play without owning the game. The patches only work on your own copy of the disc.
Fire Pro Wrestling Z and its contents belong to their respective owners. The Japanese text in this
repository is included for translation and reference.

The code in this repository is released under the [MIT License](LICENSE).
