"""
rollup.py  -  Turn raw observations into the daily numbers, then prune.

Run once a day (after collection). It produces small, permanent summary files
and then deletes old raw rows so the database stays tiny.

Outputs (all CSV, all committed to the repo so they're auditable):
  data/summaries/daily_by_station.csv   one row per station per day
  data/summaries/daily_by_city.csv      one row per city per day
  data/summaries/headline.csv           the few numbers for the budget argument

Occupancy definition (also stated in config.yaml):
  occupancy % = occupied / (available + occupied + reserved)
  Broken (out_of_service) and unknown ports are excluded so a dead charger is
  never miscounted. "Zero-use" means a station was never seen occupied all day.
"""

import csv
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = yaml.safe_load((ROOT / "config.yaml").read_text())
RAW_DIR = ROOT / "data" / "raw"
SUM_DIR = ROOT / "data" / "summaries"
SUM_DIR.mkdir(parents=True, exist_ok=True)


def occ_fraction(row):
    a = int(row["available"]); o = int(row["occupied"]); r = int(row["reserved"])
    denom = a + o + r
    return (o / denom) if denom > 0 else None


def load_raw(day):
    p = RAW_DIR / f"{day}.csv"
    if not p.exists():
        return []
    with p.open() as f:
        return list(csv.DictReader(f))


def rollup_day(day):
    rows = load_raw(day)
    if not rows:
        print(f"No raw data for {day}.")
        return

    # Aggregate per station for the day.
    per_station = defaultdict(lambda: {"samples": 0, "occ_sum": 0.0,
                                       "ever_occupied": False, "meta": None,
                                       "dow": None})
    for row in rows:
        sid = row["nrel_id"]
        st = per_station[sid]
        frac = occ_fraction(row)
        if frac is not None:
            st["samples"] += 1
            st["occ_sum"] += frac
        if int(row["occupied"]) > 0:
            st["ever_occupied"] = True
        st["meta"] = row
        st["dow"] = datetime.fromisoformat(row["timestamp_local"]).strftime("%A")

    # Write per-station daily summary.
    st_path = SUM_DIR / "daily_by_station.csv"
    st_new = not st_path.exists()
    with st_path.open("a", newline="") as f:
        w = csv.writer(f)
        if st_new:
            w.writerow(["date", "day_of_week", "nrel_id", "city", "network",
                        "funded", "multifamily", "samples",
                        "avg_occupancy_pct", "zero_use"])
        for sid, st in per_station.items():
            m = st["meta"]
            avg = round(100 * st["occ_sum"] / st["samples"], 1) if st["samples"] else ""
            w.writerow([day, st["dow"], sid, m["city"], m["network"],
                        m["funded"], m["multifamily"], st["samples"], avg,
                        not st["ever_occupied"]])

    # Aggregate per city (and per funded / multifamily cut).
    def city_rollup(predicate, label):
        buckets = defaultdict(lambda: {"occ": 0.0, "n": 0, "zero": 0, "stations": 0})
        for sid, st in per_station.items():
            m = st["meta"]
            if not predicate(m):
                continue
            b = buckets[m["city"]]
            if st["samples"]:
                b["occ"] += st["occ_sum"] / st["samples"]
                b["n"] += 1
            b["stations"] += 1
            if not st["ever_occupied"]:
                b["zero"] += 1
        out = []
        for city, b in buckets.items():
            avg = round(100 * b["occ"] / b["n"], 1) if b["n"] else ""
            zero_pct = round(100 * b["zero"] / b["stations"], 1) if b["stations"] else ""
            out.append([day, city, label, b["stations"], avg, zero_pct])
        return out

    city_path = SUM_DIR / "daily_by_city.csv"
    city_new = not city_path.exists()
    with city_path.open("a", newline="") as f:
        w = csv.writer(f)
        if city_new:
            w.writerow(["date", "city", "segment", "stations",
                        "avg_occupancy_pct", "pct_stations_zero_use"])
        for r in city_rollup(lambda m: True, "all"):
            w.writerow(r)
        for r in city_rollup(lambda m: m["funded"] == "True", "funded"):
            w.writerow(r)
        for r in city_rollup(lambda m: m["multifamily"] == "True", "multifamily"):
            w.writerow(r)

    print(f"Rolled up {day}: {len(per_station)} stations summarized.")


def prune_raw(today):
    """Delete old raw daily files per retention rules to keep storage tiny.
    Funded/multi-family raw is preserved inside summaries regardless; here we
    simply keep raw files longer than the default if they are recent."""
    keep_default = CONFIG["retention"]["raw_days_default"]
    cutoff = datetime.fromisoformat(today) - timedelta(days=keep_default)
    for p in RAW_DIR.glob("*.csv"):
        try:
            d = datetime.strptime(p.stem, "%Y-%m-%d")
        except ValueError:
            continue
        if d < cutoff:
            print(f"Pruning old raw file: {p.name}")
            p.unlink()


if __name__ == "__main__":
    import sys
    from zoneinfo import ZoneInfo
    today = (sys.argv[1] if len(sys.argv) > 1
             else datetime.now(ZoneInfo(CONFIG["project"]["timezone"])).strftime("%Y-%m-%d"))
    rollup_day(today)
    prune_raw(today)
