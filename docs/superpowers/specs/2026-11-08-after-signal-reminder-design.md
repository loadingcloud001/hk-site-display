# Reminder after Signal 8 or Black rain ends

Date: 2026-11-08. The follow-up in `2026-11-08-no-operator-switch-design.md` §7.

## 1. What

For 24 hours after HKO cancels Signal 8 or above, or the Black Rainstorm Warning Signal, or replaces it with a lower signal, the screen shows one more 主管注意 line:

> 主管注意　留意天氣信息，保持高度警覺：可能仍持續影響工作安全　八號東北烈風或暴風信號　14:00 改發較低警告信號

The trigger comes only from HKO's warnsum, so no person and no secret is involved.

It is never the main instruction. It only joins the supervisor lines, ranked after every line for a warning in force.

## 2. Wording

Labour Department 《惡劣天氣及「極端情況」下工作守則》 (May 2026), source `ld-cop-weather`, Chapter 3 復工安排的安全要點, (c) 保持警覺, printed page 28 (PDF page 16). Checked on the page image on 2026-11-08. The PDF's sha256 equals the lock.

> 留意天氣信息，保持高度警覺，防範雷暴、暴雨和熱帶氣旋警告取消或改發較低警告信號後，或「極端情況」結束後，可能仍持續影響工作安全；定期檢討惡劣天氣及「極端情況」下工作安全指引。

English Code (`ld-cop-weather-en`), Chapter 3 "Safety considerations for work resumption arrangements", (c) "Remain vigilant", same page, also checked on the page image:

> Pay attention to weather information and remain highly vigilant; be aware that work safety may still be affected even after the cancellation or lowering of warning signals of thunderstorms, rainstorms and tropical cyclones or ending of “extreme conditions”, regularly review work safety guidelines for adverse weather and “extreme conditions”.

What is shown, all verbatim and contiguous (`tests/test_display_actions.py`):

| Part | Shown |
|---|---|
| Line | 「留意天氣信息，保持高度警覺」 and 「可能仍持續影響工作安全」, joined with ： as the other two-part lines are |
| How it ended (`when`) | 「取消」 or 「改發較低警告信號」, both from the same sentence and checked by the same guard |
| Signal and time | HKO's name for the signal from warnsum, and HKO's time. The date is added when it was not today (`11月7日 18:45`) |
| English line | "Pay attention to weather information and remain highly vigilant; be aware that work safety may still be affected even after the cancellation or lowering of warning signals" |
| English name | HKO's English name for the signal, from HKO's English warnsum, never from a table |

Left out on purpose:
- 「或「極端情況」結束後」: no feed carries 「極端情況」 (no-operator spec §3).
- The review of guidelines: it is not for the gate.

The English line keeps "even after the cancellation or lowering of warning signals". The Chinese says the same through 取消 / 改發較低警告信號 next to the signal's name. The English row only has HKO's name, and without that clause it would read as if the signal were still in force.

## 3. What HKO's feeds give (checked 2026-11-08)

| Source | Finding |
|---|---|
| HKO Open Data API documentation v1.13 | warnsum has one entry per kind of warning (`WTCSGNL`, `WRAIN`, ...). Tropical cyclone codes include `CANCEL`. actionCode is ISSUE, REISSUE (WCOLD, WHOT, WFNTSA), CANCEL, EXTEND and UPDATE (WTS) |
| Live feed, 2026-11-08 | Yellow fire danger cancelled at 17:00: warnsum kept `{"code": "WFIREY", "actionCode": "CANCEL", "issueTime": 09:45, "updateTime": 17:00}`, and warningInfo kept 「火災危險警告現已取消。」. Both were gone at 18:02, so HKO listed the cancellation for about an hour (61 minutes) |
| Internet Archive copies of warnsum, 2019 to 2026 | Seven copies show a cancelled entry 1 to 50 minutes after it was cancelled. One shows it after 152 minutes |
| HKO's own warning summary (`DYN_DAT_WARNSUM.json`, Internet Archive) | 2024-11-14: `ISSUE TC3` at 10:20. Only the free text says 「取代八號東北烈風或暴風信號」. 2026-07-31: `ISSUE WRAINA` at 14:10, 「…取代紅色暴雨警告信號」. 2025-09-24: `CANCEL WRAINA` at 11:50, issue time still 02:45 |

So:
- **A lowered signal is a plain issue of the lower one.** Signal 3 after Signal 8 reads exactly like Signal 3 after Signal 1, and Red after Black like Red after Amber. Only warningInfo's bulletin text names the signal it replaced.
- **When every tropical cyclone signal is cancelled**, the code is `CANCEL`, which does not say which signal ended.
- **A cancelled rainstorm signal keeps its code**, with actionCode CANCEL and the cancellation in `updateTime`, for about an hour.

## 4. Design

A stateless rule, like the 10-minute change banner, can only see the last case: Black rain cancelled outright, which is rare. The usual end, Signal 8 lowered to 3 and Black lowered to Red or Amber, needs the reading before the change. Two other routes were rejected:
- Reading warningInfo's bulletin text: free text that is not meant to be parsed. A raise mentions both signals too (「以八號…取代三號…」).
- Guessing from times.

So `services/ingest/app/after.py` remembers.

- `remember(memory, warnsum, warnsum_en, read_at, triggers)` is a pure function of the readings: same readings, same memory, no clock. The poller calls it after every refresh with the feed's own fetch time. The preview cases call it with their earlier readings.
- For each kind (WTCSGNL, WRAIN), it keeps the last trigger seen in force: code, HKO's Chinese and English names, issue time, and when it was last seen.
- The end is recorded when HKO shows the kind again with a lower signal (`lower`, at the new entry's issue time) or with `CANCEL` (`cancel`, at its update time). A signal that moves between triggers (10 to 9 to 8, or a new direction for 8) is still in force.
- Nothing is put down to the remembered signal without HKO saying so:
  - a reading without the entry is no evidence;
  - a change dated before the signal was issued, or more than 2 hours after it was last seen in force, is not attributed: the service lost track, so it forgets;
  - a later cancellation of the lower signal does not move the time.
- A trigger HKO still lists as cancelled (`WRAINB` with actionCode CANCEL) is read from the reading itself, so it needs no memory.
- The memory is in the ingest process only (decided with the owner on 2026-11-08). A restart or deploy within the 24 hours forgets it. The screen then shows what HKO's warnings alone give, as before this change. A volume would have kept it, at the cost of one more thing to roll out and look after.

`ended_signal()` picks the most recent end within `hours`, skipping a kind whose signal is back in force. `snapshot.py` passes it to `supervisor_lines()`, which ranks it last (rank 5) among at most two lines.

Like every supervisor line, it shows only on a normal or heat-stress screen. While Red rain, Signal 8, landslip or another weather instruction is in force, the screen shows that instruction alone. After Black is lowered to Red, the reminder appears once Red is lowered or cancelled, if the 24 hours have not run out.

## 5. How long: 24 hours (owner's choice, 2026-11-08)

The Code asks staff to return within two hours when a warning is cancelled in working hours (「僱員應盡量在兩小時內返回工作崗位」), and lets them stay home when it ends near the end of the day. Options offered:
- **24 hours (chosen).** It reaches the first shift back whenever the signal ends. Typhoons often end in the evening or at night, and staff then return the next morning, 12 to 16 hours later.
- **12 hours.** It covers a daytime or late-night end, but is gone before the next morning's shift after an evening end.
- **4 hours.** The return window plus two hours of work, for a daytime end only.

Two hours was not offered: it would end just as staff arrive back. The number lives in the config (`hours` in the `supervisor` entry), next to the wording.

## 6. Preview cases and tests

| Case | Shows |
|---|---|
| `tc8-lowered` 八號改發三號後 | Signal 3's line, then the reminder: 八號東北烈風或暴風信號 14:00 改發較低警告信號 |
| `tc8-all-cancelled` 八號後信號全部取消 | 正常工作 with the reminder only, 5 hours after Signal 8 was lowered |
| `rain-black-lowered` 黑雨改發紅雨、黃雨後 | Amber's line, then the reminder from the Black-to-Red change |
| `rain-black-cancel` 黑雨（剛取消）, now also | The banner, and the reminder read from HKO's listed cancellation alone |
| `amber-after-tc8` 黃暑熱＋昨日八號後 | Heat-stress tiles with the reminder, dated the day before |

Tests:
- `tests/test_after.py`: each rule in §4.
- `tests/test_state.py`: ranking, cap, English.
- `tests/test_display_actions.py`: the `when` labels and the entry's shape.
- `tests/test_sim_cases.py`: the cases above. It also checks the reminder never appears while a weather instruction is in force.
- `tests/test_live_api.py`: the live path end to end, including a restart forgetting it.

## 7. Limits

- A restart or deploy within the 24 hours forgets the reminder (§4).
- If the service is down when HKO lowers the signal, it never sees the change.
- Only Signal 8 or above and Black rain trigger it, as briefed. The Code's sentence also covers thunderstorm, Amber and Red rain, and Signal 1 and 3. Those would show it after most showers, and it would soon go unread.
- 「極端情況」 ending is not covered: there is no feed (no-operator spec §3).

## 8. Rollout

Deploy as usual. Nothing to configure: no setting, no volume, no secret. The ingest log records each end:

```
TC8NE lowered at 2026-09-24 16:20: supervisor reminder for 24 hours
```
