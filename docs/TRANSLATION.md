# Translation

## Where the text is

| File | Holds | Checked by |
|---|---|---|
| `translation/script/story01-07.txt` | story mode, one block per page (+ C ids: choices, chapter titles) | `tools/lint.py` (page room) |
| `translation/text/ui.csv` | the program's strings (menus, edit mode, shouts, messages, credits) | `tools/lint.py` |
| `translation/text/fixed.csv` | promotion and referee names (fixed fields) | `tools/lint.py` (bytes) |
| `translation/text/wrestlers.csv` | the roster: real and parody names, nicknames | `tools/lint.py` |
| `translation/text/moves.csv` | move names | `tools/lint.py` |
| `translation/text/speakers.csv`, `story_cards.csv`, `story_names.csv` | story speaker labels, match cards, story-only wrestlers | `tools/lint.py` |
| `translation/text/name_tokens.csv` | `<Token>` names swapped per name set (real / parody) | `tools/lint.py` (token) |
| `translation/graphics.csv` | images with text | `tools/check.py` |

## File formats

Message blocks: `@ id`, source lines (`JP `), translation lines (`EN `); no `EN` lines = original
kept. A file's header says what it holds and its limits (`# limit lines=3 chars=28` is checked by
lint). Tables: original columns beside English ones (`japanese`/`english`, or `X`/`en_X`). See
`tools/blocks.py` and `tools/textdb.py`.

Control codes: `%ssN` / `%sfN` / `%slN` wrestler N's short / full / other name; `%k` `%k2` wait
for a key (page end); `%c0` `%c1` colour; `%px` `%py` `%bx` `%by` `%m` `%w` `%t` layout on match
cards; `%sw` `%st` `%sk` `%s` `%d` filled in by the game; `#xNN` spacing in costume labels; `\n` a
line break in ui.csv. Names as `<Token>` (wrestlers.csv parody names and name_tokens.csv).

## Style guide

- Name order, romanization: given name first, Hepburn without macrons, the game's kana readings;
  a wrestler's short name (what %ss prints) is the family / ring name.
- Quotes and speakers: story dialogue in "double quotes", narration without; the build draws the
  speaker labels; ・・・ becomes ..., no Japanese punctuation, printable ASCII (menus may also use
  ○●△▲□■☆★◎×・…♪).
- Voice: blunt fiery wrestlers, excited announcers and reporters, gruff presidents, polite young
  boys; Kansai dialect folksy casual English; Ando's "Me"/"You" (owner kept, 2026-10-29).
- Room: story 40 characters a line, 3 lines with a speaker / 4 without (lint checks the wrap,
  counting names at their English length); menus about twice the Japanese character count;
  fixed fields per max_bytes.

## Glossary

`translation/glossary.csv` (`japanese, english, notes`): lint warns when a source line contains a
term and the English doesn't use its translation (several accepted forms: `A | B`). Prefer
established community names (existing English guides) over new coinages.

## Decisions

| Decision | Who / why |
|---|---|
| Scope: the whole game - menus, wrestlers (names, profiles), moves, story mode, and images with game text | owner, 2026-10-29 |
| Not translated: staff credits; in-world art that doesn't affect play (signs, T-shirts, arena graphics); the memory card title | owner, 2026-10-29 |
| Two name sets (`build.py --names`): `real` - the actual wrestlers' names; `parody` - the game's parody names, translated | owner, 2026-10-29 |
| Test builds use real names; the parody build is tested in the final round | owner, 2026-10-29 |
| Translated from scratch; Fatman Dave's 2004 partial menu patch is credited as inspiration | owner, 2026-10-29 |
| English everywhere as two-letter pair glyphs drawn into the game's fonts (tools/fpzfont.py) | lead, 2026-10-29 (the story and big-font menus put every character in a full cell) |
| Wrestler short names = family / ring name (what the story prints) | lead, 2026-10-29; owner approved 2026-10-29 |
| Promotions, titles, venues get real names in the real build via tokens (as FPW D): IGP = IWGP, NEO-ONE = ZERO-ONE, UWH Integral = UWF International, NAW = NWA, V1 Climax = G1 Climax, Yurakuen Hall = Korakuen Hall, Butokan = Budokan | owner rule from D; these approved 2026-10-29 |
| Z-only promotions in the real build: NEO-ONE = ZERO-ONE, U.N.O = UFO, SANADA DOJO = TAKADA DOJO, EWF = WEW, AWG = WCW, WPA = WWE, S-1 = K-1, GLOBAL JAPAN = WORLD JAPAN, MONSTER CLUB = MONSTER ARMY, MUSCLE-1 = WRESTLE-1, S-DOJYO = K-DOJO | owner, 2026-10-29 |
| Promotion 格闘探検隊バトレーション: Battration in the parody build (the spelling on its ring logo), Battlarts in the real build, after the real shoot-style promotion | owner, 2026-10-30 |
| The extra rings (`rings`) ship in the (All Unlocked) patches; names Independent World, Pale Blue, Lilac, NONNON, Battration / Battlarts, UWH / UWF, F.P.Z. | owner, 2026-10-30 |
| Moves added by `moves`: 1059 (unnamed in the game) = Jumping Splash; 660 = Super Muscle Buster, as 659 is Muscle Buster | owner, 2026-10-30 |
| Move Edit categories: Strike, Running, Run Corner, Top Rope, Grapple, Bk Grapple; every row centred, buttons beside the label. CPU Logic matches: Strike, Grapple, Bk Grapple, Running, Top Rope (登って) | owner, 2026-10-30 |
| Venue row adds only the dojo, named Dojo; venues 5-8 stay with their match rules | owner, 2026-10-30 |
| Wrestler names (real and parody) follow the owner's list (private/wrestlernames.txt); story characters from it (Doogan, Slender, Nevelo, Hakuyobo) are tokens | owner, 2026-10-29 |
| Developer chapter-select lists are translated (all scenarios) | owner, 2026-10-29 |
| Parody names Sergeant Smith and Shiori Kanzaki (the list's Sargeant / Shioru were typos); promotion logos kept as art; move-link markers 前1/前2 drawn F1/F2 | owner, 2026-10-29 |
| Scenario 7 pages that write the speaker's name into the text (no speaker field) keep it as the Japanese does | owner, 2026-10-29 |
| Story characters, real build: Dick Road = Rick Rude, Nakauchi = Sakaguchi, Alex = Scott Steiner, Ankokubo = Kokushi Muso, Okano = Nakano, Zombie = Saito, Jimmy Hawk = Tony Halme; the story calls the two Ogawas "Y Ogawa" / "N Ogawa" | owner, 2026-10-29 |
| Story terms: the Three War Demons, the Rebel Army, the Outlaw, the Seigi Army, Paper Fighting, Bureido Akkija, President Tomoko, Kagawa | owner approved 2026-10-29 |
| Scenario 7's real promotions stay plain English in both builds (they are plain names in the Japanese too) | owner, 2026-10-29 |
| Main menu labels redrawn as large English in the same italic style; the small English subtitles removed | owner, 2026-10-29 |
| Hidden-content extras (Liger scenario, all scenarios, chapter menus, Title Match, unlock level 3) ship only in separate "(All Unlocked)" patches, one per name set; the plain patches have none; the developer mode select is a build option only | owner, 2026-10-30 |
| Liger scenario, made playable: Bas Rutten's match becomes Minoru Suzuki (already named at lyger206; the story's four lines are reworded, only seen in the All Unlocked patches). Wild Pegasus stays, as a story-only wrestler: S's profile, skills and moves, ratings raised to his story peers (attack 77, defence 84), Dynamite Kid's CPU logic, Bret Hart's body with no top, blue pants and dark blonde hair (`tools/storywrestlers.py`) | owner, 2026-10-30 |
| Liger scenario's wrestlers (owner, 2026-10-30): Young Yamada for the matches before the mask (a story record, rookie ratings; head 112, black hair; black trunks and boots in his first year, gm001-002, then red pants and white boots, gm004, 005, 206), Marufuji in gm014 (the card's Kanemaru was the odd one out), ratings on the curve the other stories use (tools/storywrestlers.py PEOPLE) | owner, 2026-10-30 |
| Story text colours consistent in every story: the hero (and his other ring names: Muta, Kokushi Muso, Tigre, Killer Tiger Mask) white, everyone else yellow | owner, 2026-10-30 |
| The chapter menus are developer-only (`debug-chapters`), in no release; Liger's story starts at chapter 1. Venues, rings and referees in Liger's story follow each scene (ligerstory.PLACE) | owner, 2026-10-30 |
| Losing to Pegasus is a Game Over with Retry, as at Misawa, Mirko and Rickson: the original has no losing scene and the next chapter has Liger as champion. His difficulty stays | owner, 2026-10-30 |
| Saves: the README says old saves may not be compatible, and save compatibility is not tested or promised | owner, 2026-10-30 |
| Name entry: replace the kana/kanji grid with an English keyboard | owner, 2026-10-29 (built: fpztext.step_name_entry) |
| Factions and titles, real build (tokens): T-BLACK / TEAM BLACK = Team 2000, NUCLEAR = No Fear, ZETT = BATT, BLADE = PRIDE, RYU = WAR, GMC = GHC, Young Tiger Cup = Young Lion Cup; 王道特攻隊長 = King's Road Vanguard | owner, 2026-10-29 |

## What stays untranslated

- Staff credits.
- In-world art that doesn't affect play: signs, T-shirts, arena and ring graphics.
- The memory card save title.

- Promotion logos (edit-mode samples, the wrestler-select backdrop): logos, like the title logo.
