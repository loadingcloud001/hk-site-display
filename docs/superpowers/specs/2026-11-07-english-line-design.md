# Official English line: design

Date: 2026-11-07. Builds on `2026-10-06-gate-screen-upgrade-design.md` (wording rules, §3 and §9) and `2026-11-07-site-ready-upgrade-design.md` (site files, the measured fit, the weekly source check).

## 1. Goal

Many workers on Hong Kong sites read English but not Chinese. A site can now add an English line to its gate screen, under the Chinese, using **only the official English version of each sentence the screen already shows**:

- The instruction under each warning, from HKO's English advice pages and LD's English Code of Practice.
- The heat-stress tiles and the normal-day rest lines, from LD's English guidance notes.
- HKO's English warning names, from HKO's English feeds.

Chinese stays the main text. Where LD or HKO publish no English version of a sentence, the screen shows no English for it. Nothing is translated by us.

## 2. Non-goals

- **Translating anything.** No English is written by us. When an official English sentence does not exist, the line stays Chinese only.
- **The banner, the bar and the screen's own words** stay Chinese: 主管注意, 正常工作, 最新, 資料過期, 陣風, 濕度 and so on. They are not official sentences, so they have no official English.
- **The banner in English.** HKO's English feeds have the English text, but the banner is a one-line ticker and would need its own layout. A follow-up if sites ask for it (§12).
- **Other languages.** Many workers read neither Chinese nor English (South Asian languages in particular), but LD and HKO do not publish these instructions in them, so the same rule allows nothing for them yet.
- **Changing what is in force.** English never decides a warning, a rest time or a tile. It is looked up after the Chinese screen is decided.

## 3. Sources (checked 2026-11-07)

The current English versions on labour.gov.hk and hko.gov.hk, each the counterpart of a Chinese source already used:

| Key | Source | Edition |
|---|---|---|
| `ld-gn-heat-en` | LD, Guidance Notes on Prevention of Heat Stroke at Work, https://www.labour.gov.hk/common/public/oh/Heat_Stress_GN_en.pdf | Third edition (Revised) August 2026 |
| `ld-cop-weather-en` | LD, Code of Practice in Times of Adverse Weather and "Extreme Conditions", https://www.labour.gov.hk/eng/public/wcp/Rainstorm.pdf | May 2026 |
| `hko-tc-en` | HKO, Precautionary Measures when Tropical Cyclone Warning Signals are in force, https://www.hko.gov.hk/en/informtc/precaution.htm | web page |
| `hko-rain-en` | HKO, Rainstorm Warning System, https://www.hko.gov.hk/en/wservice/warning/rainstor.htm | web page |
| `hko-landslip-en` | HKO, Landslip Warning, https://www.hko.gov.hk/en/wservice/warning/landslip.htm | web page |
| `hko-tsunami-en` | HKO, Tsunami Monitoring and Warning in Hong Kong, https://www.hko.gov.hk/en/gts/equake/tsunami_mon.htm | web page |

Both English PDFs are the same editions as the Chinese ones (the Code's Chinese version is dated June 2026, its English May 2026), and the English Appendix 4 and 4(a) give the same rest times as `config/rest_schedule.json`. Their sha256, size and Last-Modified are in `config/official_sources_lock.json` (27 Aug 2026 and 4 May 2026).

**Warning names** come from HKO, never from us:

- Warnings in force: HKO's English warning summary, `warnsum` with `lang=en`, the same feed as the Chinese one in English. Polled every 60 s, last in the cycle, so a slow English endpoint never delays the Chinese feeds. It never decides what is in force: names are looked up by code for the warnings the Chinese feed says are in force. A warning whose English name HKO has not sent shows no English name.
- Heat Stress at Work Warning: `TitleEN` in `hkhi_icon.xml`, next to the `TitleTC` already used (for example "Amber Heat Stress at Work Warning").
- Pre-No. 8 Special Announcement: not in `warnsum`. Its English name, "Pre-no.8 Special Announcement", is HKO's own, from the English Open Data API documentation (`warningInfo`, code `WTCPRE8`).

## 4. Every English sentence on the screen

Each is a verbatim, contiguous part of the quoted official sentence. The quotes are in `config/display_actions.json`, next to the Chinese.

**Weather instructions** (under the Chinese instruction):

| Warning | English shown | Source |
|---|---|---|
| Signal 10 | Remain where you are if protected and be prepared for destructive winds and the change in wind directions | `hko-tc-en` |
| Signal 9 | Stay indoors. If you are reasonably protected, stay where you are | `hko-tc-en` |
| Black rain | Employees working outdoors in exposed areas should stop work and take shelter | `hko-rain-en` |
| Signal 8 | employees should be released from workplaces or from work by batches / Return home as soon as possible if conditions so permit | `ld-cop-weather-en`, `hko-tc-en` |
| Landslip | Pedestrians should avoid walking or standing close to steep slopes and retaining walls / the operation of cranes, suspended working platforms, slope works, etc. should be suspended | `hko-landslip-en`, `ld-cop-weather-en` |
| Tsunami | Stay away from shores, beaches and low-lying coastal areas. If you are there, move inland or to higher grounds | `hko-tsunami-en` |
| Pre-No. 8 | employees should be released from workplaces or from work by batches | `ld-cop-weather-en` |
| Red rain | Employees working outdoors in areas exposed to rain should suspend outdoor duties if weather conditions in those areas so warrant | `hko-rain-en` |

**Supervisor lines** (CoP Appendix 2):

| Warning | English shown |
|---|---|
| Thunderstorm | where employees are liable to lightning strikes: stop work as far as practicable and take shelter in a safe place immediately |
| Strong Monsoon | the operation of cranes, suspended working platforms, slope works, etc. should be suspended |
| Signals 1 and 3 | Stop the operation of cranes, suspended working platforms, etc. |
| Amber rain | Suspend the operation of suspended working platforms, slope works, etc. |

**「極端情況」** (CoP Appendix 2, "General staff", (b) "Issued / in force within working hours", "Extreme conditions" column, bullets 1 and 2 on page 53, the same bullets as the Chinese):

| Where | English shown |
|---|---|
| Under the instruction | To stay where they are or in a safe place / instead of heading for work at workplaces immediately |
| Supervisor line | immediately suspend the work of employees working outdoors and in exposed areas and arrange temporary shelter in a safe place for them |

As in Chinese, the instruction leaves out the announced period ("during the specified period of announcement", 在公布的指定期間), which the plate shows, and the supervisor line leaves out "Supervisors should" (主管應). 「極端情況」 is not an HKO warning, so it has no English name: the plate in place of its icon shows the Chinese name and the period, and its supervisor line hides its trigger, as in Chinese.

**Heat stress** (guidance notes):

| Where | English shown | Source in the guidance notes |
|---|---|---|
| Tile, rest and work | `{rest} mins rest`, `{work} mins work` | Appendix 4 cells, e.g. "45 mins work 15 mins rest (75% work; 25% rest)" |
| Tile, suspended | Suspension of work | Appendix 4 |
| Tile, 2-hour baseline | at least `{rest}` minutes of rest for every `{hours}` hours of work | §5.5.4 |
| Generic site's tile labels | Light, Moderate, Heavy, Very Heavy | Appendix 4 column headings |
| Note | employees are unacclimatised or need to re-acclimate to hot work environment: increase the hourly rest time for such employees by 15 minutes | §5.4.4 |
| Normal day | heavy to very heavy levels of physical work: at least a `{rest}`-minute rest break after every `{hours}` hours of work, and the same for light to moderate work with "a minimum of a `{rest}`-minute rest break" | §4.7.1 |

The rest wording is a template because the numbers live in `config/rest_schedule.json` only (AGENTS.md). The test fills it in with every value the schedule can produce, for every warning level, workload, environment and site adjustment, and checks each result against the quotes. A schedule change that the quoted paragraphs do not cover (a baseline of 20 minutes, say) fails the test until a person re-verifies the guidance notes.

**Where the official English and Chinese differ.** Each language shows its own official text, so these differences reach the screen as LD and HKO wrote them:

- **Red rain:** the Chinese says suspend outdoor work 直至天氣情況許可為止 (until the weather permits). The English says "suspend outdoor duties if weather conditions in those areas so warrant".
- **Signal 10:** the Chinese says do not leave shelter (切勿離開有遮蔽的地方). The English says "Remain where you are if protected".
- **Thunderstorm:** the English shown includes "as far as practicable", which sits inside the one English clause. The Chinese line leaves out 在切實可行範圍內盡量, which comes before its fragment.
- **Signals 1 and 3, amber rain:** the English keeps "etc.", and the Chinese fragments end before 等.
- **Strong Monsoon and Landslip (CoP):** the condition says "Strong Monsoon Signal **or** Landslip Warning" in English and 強烈季候風信號**及**山泥傾瀉警告 in Chinese. The screen shows only the instruction, which is the same in both.
- **Signal 8 (HKO):** the English puts the condition last ("…if conditions so permit"), the Chinese first (如情況許可，…).

## 5. Data

**Site file.** Two optional fields, validated like the others (a mistake leaves the file out and names it in `/api/v1/health`):

| Field | Meaning |
|---|---|
| `languages` | `["zh"]` (the default) or `["zh", "en"]`. Chinese is always shown, so anything without `"zh"`, an unknown code or a repeat is a mistake |
| `primaryTrades[].labelEn` | The trade's English name, shown under `labelZh` on the tiles. A non-empty string |

`labelEn` is the site's own name for the trade, as `labelZh` is. The demo site uses the names in the English Appendix 1 of the guidance notes, which is what sites should use where the trade is listed. A tile shows English names only when every trade on it has one. Otherwise it shows the English rest times without names, never a mix. The generic site's tiles use the official English workload levels.

**`config/display_actions.json`.**

- Every source has `"lang": "zh"` or `"en"`, and the six English sources are added (§3).
- Every weather, supervisor, note and 「極端情況」 entry has an `"en"` key: its English `lines` (an instruction: weather, and 「極端情況」's `display`) or `fragments` (supervisor lines and notes), with their own `quotes`. `"en": null` means no official English sentence exists, and the screen shows none. The key is required, so a new entry cannot silently miss its English.
- A new `rest` section holds the English rest templates and their quotes.

**The guard** (`app/actions.py`, `tests/test_display_actions.py`):

- An English fragment must be a contiguous part of one of its quotes, and the quote must come from an English source. Chinese must come from a Chinese source.
- Chinese ignores whitespace, because PDF text breaks lines anywhere. English treats a run of whitespace as one space, so a changed word boundary ("Stayindoors") fails. A line break inside a stored fragment does not.
- The only text on the screen that is not quoted is the joiner between fragments, `：` in Chinese and `: ` in English.

**Snapshot.** English fields appear only for a site that shows English, so a Chinese-only snapshot is unchanged apart from `site.languages`:

| Field | Content |
|---|---|
| `display.en` | The English lines under the instruction: the warning's or 「極端情況」's, or the normal day's rest lines. `[]` on heat-stress days, whose English is on the tiles |
| `display.metaEn` | HKO's English warning or HSWW name, or `null` (always for 「極端情況」) |
| `restTiles[].en` | `trades`: the English names, or `null`. `lines`: the tile's English |
| `supervisor[].textEn`, `fromEn` | The line's English and the warning's English name, either `null` when there is none (`fromEn` always for 「極端情況」) |
| `notesEn` | One per Chinese note, in the same order, `null` where there is none |
| `site.languages` | Always present |

## 6. Warning names fixed on the way

HKO's `warnsum` puts only the colour in `type` for rainstorm and fire danger warnings (`"黃色"`, `"Amber"`), with the name in `name`. The screen showed `type` whenever it was present, so the live screen named a black rainstorm 「黑色」. Tropical cyclone signals carry their full name in `type`. `warning_name()` now joins colour and name for `WRAIN*` and `WFIRE*` (黑色暴雨警告信號, "Black Rainstorm Warning Signal"). The preview cases now use the live feed's shape. Separate commit, `82b8bed`.

## 7. Screen

- **Weather and normal days:** the English lines go under the Chinese instruction as one block, a little smaller than the Chinese sub-line (Latin letters already look smaller than Chinese at the same size) and lighter. They are balanced when they wrap and never hyphenated, and a hyphenated word ("re-acclimate", "15-minute") never breaks at its hyphen. HKO's English warning name goes under the Chinese warning line.
- **Tiles:** the English trade names go under the Chinese ones, in the tile's heading. The tile's English goes under its Chinese lines as one block: "45 mins rest" and "15 mins work" side by side when they fit, "Suspension of work", or the 2-hour baseline's one sentence, which covers both its Chinese lines. So the Chinese lines stay together, as on a Chinese-only site. An English trade name stays on one line when it fits and wraps inside itself only when it is wider than the tile. An earlier version put each English line under its own Chinese line. It was busier and taller: 65 % against 67 % for the busy test site's Amber day in landscape.
- **Supervisor lines:** the English takes a row of its own in the same box, with the warning's English name after it.
- **「極端情況」:** the English lines go under the Chinese instruction, below the plate that takes the icon's place. Its supervisor line has its English row, without a name.
- **The icon gives up room first.** On a site that shows English, the large icon is smaller (landscape weather and normal days 26 % of the height instead of 34 %), so most screens fit without shrinking.
- **The measured fit still applies.** The centre is scaled down as a whole when it is too tall, to no less than 60 %.
- **English never takes the Chinese's room.** If the centre does not fit even at 60 %, the screen gives up English, lowest value first: the warning's English name and the note's English, then the supervisor lines' English, then all of it. With everything given up, the centre is no taller than on a Chinese-only site, because the icon is smaller too. New content or a new screen size starts again from nothing given up, and the measurement runs before paint. The rule is to shrink first and give up English only at the floor, because the English is official safety wording too, and the existing design already accepts 60 % on busy days.

**Measured** at 1920×1080 and 1080×1920 with the demo site, every preview case (§10). The scale is the centre's size (100 % = not shrunk), with the Chinese-only figure for the same case in brackets:

| Case | Landscape | Portrait |
|---|---|---|
| Weather instructions (Signals 8–10, black and red rain, tsunami, Pre-No. 8, landslip) | 98–100 % (100 %) | 100 % (100 %) |
| Normal day, with or without other warnings on the bar | 95 % (100 %) | 91–100 % (100 %) |
| Heat stress, Amber / Red / Black | 96–100 % (100 %) | 76–78 % (96–100 %) |
| Normal day with one supervisor line (Signal 1 or 3, Strong Monsoon, amber rain, thunderstorm, and Signal 1 just after 「極端情況」 ends) | 83–86 % (100 %) | 75–89 % (94–100 %) |
| Amber heat stress with Signal 1 or 3 | 85 % (100 %) | 66 % (94 %) |
| Amber rain with Signal 3 (two supervisor lines) | 78 % (98 %) | 71 % (94 %) |
| Amber heat stress with a thunderstorm | 82 % (100 %) | 64 %, the warning's and the note's English given up (81 %) |
| 「極端情況」, alone or with warnings on the bar | 89 % (100 %) | 95–100 % (100 %) |

Nothing runs into the bar or under the banner in any case, in either orientation. After merging master (supervisor alerts, 「極端情況」, the sky-blue weather tiles), all 48 cases were measured again: the 44 earlier ones gave the same scales, to the percent. The busiest days are portrait heat-stress days with a supervisor line, which the Chinese-only screen already shrinks. A busy test site with five or six tile groups and long English names shows everything at 60–67 % in landscape. In portrait it gives up the warning's and the note's English on heat-stress days (63 %), and all of the English when a supervisor line is added too (67–75 %). Nothing overlaps there either.

## 8. Rules for the future

- English wording follows the same rule as Chinese: a verbatim, contiguous part of a quoted official English sentence, from an English source, in `config/display_actions.json`. Never a translation and never a paraphrase. AGENTS.md says so.
- A new instruction needs its `"en"`: the official English, or `null` when there is none.
- The screen's position, like everything else, never changes the English.

## 9. Re-verification

- The weekly check (`scripts/check_official_sources.py`) downloads the English sources too and checks every English quote, including the rest wording. The two English LD PDFs are in the lock, so a change to either fails the check until a person has re-verified it.
- The April checklist (main spec §9) now includes the English documents. Compare the English Appendix 4 and 4(a) with `config/rest_schedule.json` as well, and check the English trade names in site files when Appendix 1 changes.
- Run on 2026-11-07: all 12 sources downloaded and every Chinese and English quote found. The two English PDFs were then added to the lock.
- Run again on 2026-11-08 (Hong Kong time), after merging 「極端情況」: all 12 sources downloaded and all 37 quotes found, including the two new English ones. The Labour Department PDFs were unchanged, so the lock was not touched.

## 10. Testing

- pytest: 484 tests after merging master (supervisor alerts and 「極端情況」). New with this work: 4 for the warning names, 39 for the English line and 3 for 「極端情況」's English. New:
  - the guard: an English paraphrase, a joined-up word, a line break, a Chinese source cited for English and the reverse, a missing `"en"`, `null`, an empty list, and a missing or unknown `lang`;
  - the rest wording: every value the schedule can give, a schedule the quotes do not cover, a broken template, and the normal-day grouping;
  - site files: `languages` (valid, missing `"zh"`, unknown code, repeat, not a list) and `labelEn`;
  - tiles: English names, the generic site's workload levels, and a tile with a trade that has no English name;
  - snapshots: a Chinese-only site gets no English field; weather, Pre-No. 8, heat and normal days in English; no English name rather than a guess;
  - every preview case: English never changes the Chinese, and every case has its English where an official one exists;
  - the API: names from HKO's English feed, a Chinese-only `?site=`, a failing English feed never affecting warnings or health, and the poller asking for `lang=en`;
  - the source check: English sources, quotes and the rest section;
  - 「極端情況」: its English quotes, the English kept where the screen reads it (`lines` under the instruction, `fragments` for the supervisor line), and the preview cases' English.
- Real Chrome (Playwright, by hand), every preview case at 1920×1080 and 1080×1920:
  - with English (demo site): nothing runs into the bar or under the banner, nothing leaves the screen or its tile, no text wider than its box, no overlap between lines, and no console errors;
  - Chinese-only (the demo site without `languages`): pixel-identical to the screen before this change in all 88 screens. A first pass differed in a few screens only where HKO's blinking "issuing" icons (two-frame GIFs) were caught on the other frame, or a web-font subset arrived late; each was identical when shot again. The new Chinese-only screenshot `docs/demo/amber-zh.png` is byte-identical to the old `amber.png`;
  - a busy test site (five or six tile groups, long English names) on heat-stress days, to check the English is given up in order and nothing overlaps.

## 11. Rollout

1. Deploy as usual. The snapshot is backward compatible: new fields only, and only for sites that show English. An older kiosk ignores them, and the new kiosk shows no English with an older server.
2. **The demo site now shows English**, so the live demo will too.
3. Real sites stay Chinese only until their file says `"languages": ["zh", "en"]`. Add `labelEn` to the trades at the same time, then preview the tiles (`?preview=1&site=<siteId>&fixture=amber`) in both orientations.

## 12. Follow-ups

- **The banner in English**, from HKO's English warning text, if sites ask for it.
- **English in supervisor alerts.** The alerts stay in Chinese, built from the screen's lines (supervisor alerts spec §12). English messages would follow the same rule.
- **An English name for 「極端情況」** on the plate (the Code's "Extreme conditions"), if English sites ask for it. It would need its own quote, like any other wording.
- **The worker phone page**, as in the site-ready spec §12, with its English under the same rule.
