# No operator features: 「極端情況」 switch and supervisor alerts removed

Date: 2026-11-08. Removes the 「極端情況」 switch (PR #5, merge 38bb226, spec `2026-11-07-extreme-conditions-design.md`) and supervisor alerts (PR #4, merge 7fc59ba, spec `2026-11-07-supervisor-alerts-design.md`). Both specs were removed with them; they are in the git history.

## 1. Why

hk-site-display is a public service, not one site's system. Nobody is on call to operate it.

The owner's rule (2026-11-08): nothing may depend on an operator, or on a secret an operator must hold. Everything on the screen comes from official machine-readable feeds, like the heat stress warning and HKO's warnings already do.

Both features broke that rule.

## 2. Why each needed a secret

**The 「極端情況」 switch.**
- No feed carries 「極端情況」, so PR #5 made it a manual switch: `PUT` / `DELETE` on `/api/v1/admin/extreme`.
- That is a write endpoint on a public server, and it changes every screen at once. Without a key, anyone on the internet could put 「極端情況」 on every gate screen, or take it off.
- Hence `ADMIN_KEY`, a Bitwarden secret, the server's `.env`, https-only checks, and a person on call to use the switch after a typhoon.

**Supervisor alerts.**
- They emailed a site's supervisors when that site's screen changed.
- They needed each site's supervisor addresses in its site file on the server (personal data held by the operator).
- They needed an SMTP account whose password lives on the server, so real email also meant a secret.
- Without that account they only logged. A public service has no supervisors to register, so they never had anyone to tell.

## 3. Is there an official feed for 「極端情況」? (checked 2026-11-08)

| Source | Finding |
|---|---|
| HKO Open Data API documentation, v1.13 (September 2025), Chinese and English | No item or warning code for 「極端情況」. The warnsum codes are WFIRE, WFROST, WHOT, WCOLD, WMSGNL, WRAIN, WFNTSA, WL, WTCSGNL, WTMW, WTS and WTCPRE8 |
| LegCo question 13, 8 July 2026 (`info.gov.hk/gia/general/202607/08/P2026070800422.htm`) | A steering committee decides whether to announce. Information goes out "through the Information Services Department, the media and social media platforms". No data feed |
| Government press releases (`info.gov.hk`) | Free text. On 8 September 2023: "will continue at least until 6pm", later "until midnight". Each extension and the end are separate releases. A misread would put 「極端情況」 on every public screen, or miss it, so they cannot drive the screen |
| HKO's tropical cyclone precautions page | No mention of 「極端情況」 |
| Labour Department Code of Practice, May 2026 (sha256 still equals the lock) | Footnote 2: the Government decides case by case whether to make a territory-wide announcement. No channel the screen could read |

So 「極端情況」 cannot be detected automatically, and a public screen cannot show it honestly.

## 4. Decision

Remove both. The screen shows what HKO's and the Labour Department's feeds say, and the service needs no person and no secret.

**Removed with the switch:**
- The admin endpoints, `ADMIN_KEY`, `STATE_DIR` and the `extreme-state` volume.
- `app/extreme.py`, the 「極端情況」 display state, its banner, tone and priority band.
- Its four preview cases, its gallery group, the kiosk's notice plate and its staleness rule.
- The `extreme` section of `config/display_actions.json` (Chinese and English).
- `extreme` and `extremeProblem` in `/api/v1/health`.

**Removed with the alerts:**
- `app/alerts.py` and `app/senders.py`, and the alert check in the feed poller.
- The `alerts.email` site-file field. A site file that still has it keeps working: unknown fields are ignored.
- The SMTP and `ALERT_*` settings, `PUBLIC_URL`, and the `alert-state` volume.
- `alerts` in `/api/v1/health`.

**Removed with both:** their specs, their operator guides (site-setup §8 and §9), their README sections, their screenshots and their tests.

**Kept from those PRs, because they are neither feature:**
- The Code of Practice's title without 的, as on its cover.
- One fixed list of wording sections (`SECTIONS`), shared by the tests and the weekly check, which rejects a section neither knows.
- The ingest log format: time and level on the service's own lines.

**Unchanged:**
- The official English line.
- Every screen state.
- The weekly official-source check.

## 5. The gap, stated plainly

During 「極端情況」 the screen shows HKO's state, as it did before PR #5:
- usually Signal 3, which shows 正常工作 with the 主管注意 line 停止操作起重機、吊船;
- 正常工作 alone, once HKO has no warning in force.

That is the gap PR #5 closed with a person. A public service cannot close it without a feed. The README ("What the screen does not show") and `docs/site-setup.md` §6 say so, and tell people to follow the Government's announcement.

## 6. Rollout

1. Deploy as usual, ingest then web. The compose file changed, so `up -d` recreates both services. `/api/v1/health` loses the `extreme`, `extremeProblem` and `alerts` fields; uptime monitors only read the status code.
2. After the deploy, remove the two unused volumes: `docker volume rm hk-site-display_extreme-state hk-site-display_alert-state`. Neither feature was ever used: the switch had no key, and the alerts ran in dry run with no site configured.
3. No `.env` keys are needed. The Bitwarden secret `HK_SITE_DISPLAY_ADMIN_KEY`, if one was made, can be deleted. The `HK_SITE_DISPLAY_SMTP_*` secrets were never created.

## 7. Follow-up (not done)

After Signal 8 or above, or Black rain, is cancelled or lowered, the Code (Chapter 3, 復工安排的安全要點 (c)) asks employers to 「留意天氣信息，保持高度警覺」, because effects may continue. The screen could show that line automatically for a while after such a cancellation, from HKO's data alone. How long it should show is a product decision.
