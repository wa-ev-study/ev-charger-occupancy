# EV Charger Usage Study — Project Record

*A plain-English record of what this project is, how it was built, the decisions
made along the way, and how to extend it. Written so it can be loaded directly
into Claude as context.*

---

## 1. The objective

Washington State, Bellevue, and other cities are under pressure to spend more
public money building EV charging stations. The hypothesis: many existing public
chargers are heavily underused, so additional public spending may be hard to
justify. This project builds a **credible, defensible dataset** measuring how
heavily public chargers are actually used — starting with a Bellevue pilot — to
inform the fall budget conversations.

Two special angles matter:
- **State-funded chargers** — the hypothesis is these are especially underused,
  because they're deliberately placed where demand is low.
- **Apartment/condo chargers** — a fair counter-argument is that these are
  "home-charger equivalents" and legitimately used overnight, so they're tracked
  separately.

## 2. What we measure — and how we keep it honest

We measure **occupancy**: the share of a station's ports that are in use at a
given moment, sampled on a schedule. We are deliberate about language and method
so the result survives scrutiny from a hostile analyst:

- We call it **occupancy**, never "utilization." We observe port status, not
  energy delivered or session counts. Occupancy is a legitimate proxy, labeled
  as one.
- **Occupancy % = occupied / (available + occupied + reserved).** Broken
  (out-of-service) and unknown ports are excluded so a dead charger is never
  counted as either busy or idle.
- Sampling every 30 minutes means a session shorter than 30 minutes can fall
  between checks. That makes our "never used" and low-occupancy figures
  **conservative lower bounds** on real usage — the safe direction for an
  under-use argument. (At a ~10-minute average session, a 30-minute poll still
  captures a solid, statistically defensible fraction.)
- Every observation is timestamped (local + UTC) and the entire pipeline — code
  and data — lives in a **public, version-controlled repository**, so anyone can
  reproduce every number.

## 3. Data sources

- **TomTom EV Charging Availability API** — the live source. It reports, per
  station, how many ports are available / occupied / reserved / out-of-service,
  aggregated across networks (ChargePoint, Blink, EV Connect, etc.). It also
  gave us the master list of Bellevue stations (75 stations, 721 ports).
  TomTom's free tier is **2,500 calls/day** — enough for one city at 30-minute
  polling. Beyond that it's $2.50 per 1,000 calls.
- **NREL (U.S. Alternative Fuels Data Center)** — a free government database used
  to tag which chargers are state-funded and which are at apartments/condos.
  NREL does **not** provide real-time status, so it's used as a once-daily
  reference, not a live feed. (During the pilot build NREL's site was down; the
  system is wired to switch these tags on automatically once it's reachable.)

We deliberately do **not** scrape PlugShare or any source whose terms forbid it.

## 4. How it's built (the architecture)

Four pieces:

- **A GitHub repository** — the home for the code, the schedule, and all the
  collected data. Public, so the whole method is auditable.
- **GitHub Actions** — the cloud compute that replaces a server, running in
  GitHub's cloud so nothing depends on anyone's computer being on. Because
  GitHub's *scheduler* is unreliable for frequent jobs, the collector doesn't
  rely on it for timing: one job stays alive and polls every 30 minutes on the
  runner's own clock (poll → sleep → poll), and the scheduler is only used to
  (re)start that loop a few times a day. A separate nightly job builds and emails
  the report.
- **TomTom** — reached with a secret API key stored in GitHub's encrypted secret
  store (never in the code, even though the code is public).
- **Small Python scripts**, each with one job:
  - `stations.py` — builds the list of Bellevue chargers (from TomTom) and tags
    funded / apartment-condo (from NREL when available).
  - `collect.py` / `run_due.py` — every 15 minutes, checks whether it's within
    7am-9pm Pacific and whether polling is due, then polls TomTom and writes one
    timestamped row per charger. A hard budget guard stops before the free
    2,500/day limit, so it can never cost money.
  - `rollup.py` — condenses raw readings into daily summaries and prunes old raw
    data so storage stays tiny.
  - `build_report.py` — compiles one Excel workbook per day (see section 5).
  - `send_report.py` — emails that workbook.
- **`config.yaml`** — a plain-English control panel: cities, polling frequency,
  hours, the safety cap, the pilot dates, and the email recipients. Scope changes
  here, not in code.

**One flow, end to end:** every 15 minutes the scheduler wakes, checks the clock
and the budget, asks TomTom the live status of each Bellevue charger, and appends
the readings. Each night after 9pm it refreshes tags, rolls up the day, builds the
Excel report, and emails it.

## 5. The 7-day Bellevue pilot (current setup)

- **Window:** Saturday July 18 - Friday July 24, 2026, 7am-9pm Pacific, polling
  every 30 minutes. Collection **keeps running** after the 24th (no auto-stop),
  so data is ready if we expand.
- **Cost:** $0. ~75 stations x ~28 polls ≈ 2,100 TomTom calls/day, under the
  free 2,500. Hosting and email are free.
- **Nightly deliverable:** one Excel file with two tabs —
  - **Today:** every Bellevue charger's occupancy % and zero-use flag for the
    day, headline totals, and the funded / apartment-condo subsets (which
    activate once NREL is back).
  - **Running Total:** cumulative occupancy and % never-used across the pilot,
    with a day-by-day trend.
- **Nightly email:** at ~9:15pm Pacific the report is emailed automatically to
  Todd (tmyers@washingtonpolicy.org) and Adam, with the running total in the body
  and the spreadsheet attached.

## 6. Early findings (illustrative, pre-pilot test data)

In the test runs, Bellevue showed roughly **6% occupancy on a single evening
snapshot**, and on a full day of daytime polling about **31% average occupancy
with ~28% of chargers unused that day**. These are preliminary — the pilot's
value is the full week across all days and times. The direction (a lot of idle
capacity) is consistent with the hypothesis, but the pilot is designed to let the
data speak and to surface any anomalies before expanding.

## 7. What's next

- Run the 7-day Bellevue pilot and review the nightly reports.
- Turn on the funded / apartment-condo subsets automatically when NREL returns.
- After the week, decide whether to expand (Seattle, Spokane, others). A useful
  free-scaling trick: each TomTom account (tied to a separate Gmail alias) gets
  its own 2,500 free calls/day, so several cities can be covered at no cost by
  using multiple aliases. Paid expansion (one account, more cities) runs roughly
  $5-7.50/day.
- Optionally add a dashboard or charts for the budget hearings.

## 8. How this was built — the working method (useful for Todd)

This entire system was built by working iteratively with Claude: describing the
goal in plain language, reviewing Claude's proposed approach, approving or
adjusting, and letting Claude write and debug the code. Key habits that made it
work:

- **Decide the approach before building.** Most of the effort was clarifying
  objectives, data sources, cost, and methodology *first* — the code came last.
- **Insist on defensibility.** Every metric was pressure-tested for how a
  skeptic would attack it, which drove choices like "occupancy not utilization"
  and conservative claims.
- **Keep the human in the loop.** Claude laid out each step for review and
  approval before acting.
- **Debug by leaving breadcrumbs.** When the cloud runner failed silently,
  the fix was to have it write its own logs into the repo so the problem could
  be read and fixed — including pivoting from NREL to TomTom for the station list
  when NREL went down.
- **Ask every "obvious" question.** Screenshots when stuck, plain-English
  questions, iterate. That's the whole workflow.

*Repository: github.com/wa-ev-study/ev-charger-occupancy (public).*
