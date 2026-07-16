# WA EV Charger Occupancy Study

An automated, cloud-based system that measures how heavily public EV chargers in
Bellevue (and, later, Seattle) are actually used — to inform the conversation
about whether more public spending on charging stations is warranted.

It runs entirely in the cloud on a schedule, with **no computer left on** and,
during the pilot, **no cost** (it stays inside TomTom's free daily allowance).

---

## What it does, in one paragraph

Every 15–30 minutes during the day, the system asks a charging-data provider how
many ports at each station are in use right now, and saves that snapshot. Once a
day it turns those snapshots into a few simple numbers — average occupancy, the
share of chargers that went completely unused, broken out by city, by funding
source, and by apartment/condo location — and then deletes the bulky raw data so
the database stays tiny. All the numbers, and all the code that produced them,
live in this public repository so anyone can check the work.

## The "blended" free pilot

The pilot is sized to stay under TomTom's free limit of 2,500 checks/day:

| Group | What | How often | Window |
|---|---|---|---|
| `bellevue_census` | **All** Bellevue public chargers | every 30 min | 7am–9pm |
| `funded_subset` | State/federally **funded** chargers | every 15 min | 7am–9pm |
| `multifamily` | Apartment/condo chargers | every 30 min | 24 hours |

This proves both *breadth* (all of Bellevue) and *full production speed* (the
15-minute funded group) at the same time, for free. Seattle (`seattle_census`)
is built but switched off until a paid plan is added.

## How it's built

```
config.yaml          <- the ONE file you edit (cities, cadence, limits)
src/stations.py      <- builds the station list from NREL + tags funded/multifamily
src/collect.py       <- polls TomTom for one group, with a free-tier budget guard
src/run_due.py       <- decides which groups are due and runs them
src/rollup.py        <- daily: computes the numbers, prunes old raw data
.github/workflows/   <- the cloud schedule (collect every 15 min, roll up nightly)
data/                <- master list, raw snapshots, and the summary CSVs
docs/METHODOLOGY.md  <- why the numbers are defensible
docs/SETUP.md        <- step-by-step first-time setup (start here)
```

## Cost & safety

- **Pilot: $0.** `config.yaml` caps usage at 2,400 checks/day and the collector
  stops before crossing TomTom's free 2,500 limit. No credit card is on the
  account during the pilot, so it physically cannot bill.
- **Hosting: $0.** Runs on GitHub Actions, free and unlimited for public repos.
- **Upgrade later:** add a payment method to TomTom and flip `seattle_census`
  and tighter cadences on in `config.yaml`. That is the only step that spends money.

## Getting started

See **`docs/SETUP.md`**. In short: create one shared Google account, use it to
make a free TomTom key and a GitHub account, paste the key into the repo's
Secrets, and turn the schedule on. The system does the rest.

> Note: a full, screenshot-level operator runbook will be finalized against the
> first live run. This README + `docs/SETUP.md` cover everything needed to start.
