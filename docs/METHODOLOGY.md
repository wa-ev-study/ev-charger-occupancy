# Methodology & Defensibility Note

This document explains *what* the dataset measures, *how*, and *why the method
holds up* to scrutiny from a data scientist or a skeptical official. It is meant
to be read alongside the data, and to be published with it.

## What we measure: occupancy, not "utilization"

We sample each charging station's **live availability** — how many of its ports
read `available`, `occupied`, `reserved`, or `out of service` at a moment in
time — on a fixed schedule. From those snapshots we compute **occupancy**:

> occupancy % = occupied ports ÷ (available + occupied + reserved) ports

We deliberately call this *occupancy*, not *utilization*. We do **not** observe
energy dispensed, session counts, or revenue. Occupancy is a well-established
proxy for how heavily a charger is used, but it is a proxy, and we label it as
one. Overstating it as "utilization" would be the easiest way for an opponent to
discredit the work, so we don't.

## Why the numbers are conservative (this is intentional)

Because we sample on an interval (e.g., every 15 or 30 minutes), a charging
session shorter than the interval can fall *between* two snapshots and go
unseen. This means our "never used today" and "low occupancy" figures are
**conservative lower bounds on usage** — real usage is equal to or higher than
what we report, never lower. That is the safe direction for an argument about
*under*-use: we can defend "at least this idle," which is stronger than a number
that could be attacked as overstating idleness.

Sampling cadence is chosen accordingly: fast chargers (short sessions) are
polled more frequently than Level 2 chargers (long sessions).

## Excluded from the denominator

Ports reporting `out_of_service` or `unknown` are excluded from the occupancy
calculation. A broken charger is neither "in use" nor "idle demand" — counting
it either way would distort the result. We report broken-port counts separately.

## Data sources and their standing

- **NREL Alternative Fuels Data Center** (U.S. Dept. of Energy): the master list
  of stations, networks, ownership, and facility type. Authoritative, public.
- **TomTom EV Charging Availability API**: licensed, commercial real-time
  availability aggregated across networks. Used under its terms of service —
  no scraping.
- **Funded-charger subset**: federal rule 23 CFR 680.116 requires NEVI-funded
  stations to publish real-time per-port status via the OCPI 2.2.1 standard,
  free to third parties. The publicly-funded data therefore rests on a source
  the government itself mandates be open.

We do not scrape PlugShare or any site whose terms prohibit it.

## Reproducibility

Every observation is stored with its source, station ID, and a timestamp in both
local and UTC time. The entire pipeline — collection code, configuration, and
the raw and summarized data — lives in a public version-controlled repository.
Any analyst can re-run the code, inspect exactly what was collected and when,
and recompute every published number. New metrics can be back-computed from
retained raw data within the retention window.

## Known limitations (stated up front)

1. Occupancy is a proxy for usage, not a direct session/energy measurement.
2. Interval sampling can miss sub-interval sessions (biases toward *under*-counting use).
3. Coverage depends on a station being matched in the availability source; unmatched stations are excluded and counted, not silently dropped.
4. Network-reported status can occasionally be stale; we record `unknown` rather than guessing.
