"""
collect.py  -  Poll TomTom for live charger availability (ONE collection group).

Run as:  python src/collect.py <group_name>
e.g.     python src/collect.py bellevue_census

What this does, in plain English:
  1. Checks the clock. If this group only runs during the day (7am-9pm Pacific)
     and it's currently outside that window, it does nothing and exits cleanly.
  2. Checks today's free-tier budget. If we're near the 2,500/day TomTom limit,
     it stops so the pilot can never cost money.
  3. For every charger in this group, asks TomTom "how many ports are available
     vs occupied right now?" and writes one timestamped row per station to a
     daily CSV in data/raw/.

It never deletes anything and never spends money beyond the cap. The math that
turns these rows into percentages lives in rollup.py, not here -- this file only
records raw facts, which keeps the data defensible.
"""

import csv
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = yaml.safe_load((ROOT / "config.yaml").read_text())
MASTER = json.loads((ROOT / "data" / "master" / "stations.json").read_text())
TOMTOM_KEY = os.environ.get("TOMTOM_API_KEY", "")

AVAIL_URL = "https://api.tomtom.com/search/2/chargingAvailability.json"
TZ = ZoneInfo(CONFIG["project"]["timezone"])
THROTTLE_SECONDS = 0.3   # spacing between requests to stay under TomTom's per-second limit


def now_local():
    return datetime.now(TZ)


def in_window(group):
    """Is this group allowed to run right now?"""
    if group["window"] == "24h":
        return True
    h = now_local().hour
    w = CONFIG["daytime_window"]
    return w["start_hour"] <= h < w["end_hour"]


def usage_path(day):
    return ROOT / "data" / "usage" / f"{day}.json"


def get_usage(day):
    p = usage_path(day)
    return json.loads(p.read_text()) if p.exists() else {"requests": 0}


def save_usage(day, usage):
    p = usage_path(day)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(usage))


def budget_remaining(day):
    cap = CONFIG["budget"]["daily_request_cap"]
    return cap - get_usage(day)["requests"]


def select_stations(group):
    out = []
    for s in MASTER:
        if s["city"] not in group["cities"]:
            continue
        if group["funded_only"] and not s["funded"]:
            continue
        if group["multifamily_only"] and not s["multifamily"]:
            continue
        if not s["tomtom_availability_id"]:
            continue  # can't poll a station we couldn't match in TomTom
        out.append(s)
    return out


def poll_one(avail_id, tries=3):
    """Return (counts, error). Retries transient rate-limits with backoff; on
    persistent failure returns (None, "<reason>") so the caller can SKIP this
    station and keep polling the rest — never aborting the whole cycle."""
    last = "unknown"
    for attempt in range(tries):
        try:
            r = requests.get(AVAIL_URL,
                             params={"key": TOMTOM_KEY, "chargingAvailability": avail_id},
                             timeout=30)
        except requests.RequestException:
            last = "neterr"
            time.sleep(1 + attempt)
            continue
        if r.status_code in (403, 429):
            last = f"HTTP{r.status_code}:" + r.text[:80].replace(chr(10)," ").strip()
            time.sleep(2 * (attempt + 1))     # back off, then retry
            continue
        if not r.ok:
            return None, f"HTTP{r.status_code}:" + r.text[:80].replace(chr(10)," ").strip()
        data = r.json()
        avail = occ = res = oos = unk = total = 0
        for c in data.get("connectors", []):
            cur = c.get("availability", {}).get("current", {})
            avail += cur.get("available", 0)
            occ += cur.get("occupied", 0)
            res += cur.get("reserved", 0)
            oos += cur.get("outOfService", 0)
            unk += cur.get("unknown", 0)
            total += c.get("total", 0)
        return dict(available=avail, occupied=occ, reserved=res,
                    out_of_service=oos, unknown=unk, total_ports=total), None
    return None, last


def main(group_name):
    group = CONFIG["groups"].get(group_name)
    if not group or not group.get("enabled"):
        print(f"Group '{group_name}' is disabled or missing. Nothing to do.")
        return
    if not in_window(group):
        print(f"Outside the allowed window for '{group_name}'. Skipping.")
        return
    if not TOMTOM_KEY:
        print("No TOMTOM_API_KEY set. (This is expected during a dry run.)")
        return

    ts = now_local()
    day = ts.strftime("%Y-%m-%d")
    usage = get_usage(day)
    stations = select_stations(group)
    print(f"[{group_name}] {len(stations)} stations; "
          f"budget left today: {budget_remaining(day)}")

    out_path = ROOT / "data" / "raw" / f"{day}.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not out_path.exists()
    fields = ["timestamp_local", "timestamp_utc", "group", "nrel_id", "city",
              "network", "funded", "multifamily", "available", "occupied",
              "reserved", "out_of_service", "unknown", "total_ports"]

    written = 0
    errors = {}
    with out_path.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new_file:
            w.writeheader()
        for s in stations:
            if CONFIG["budget"]["stop_when_exceeded"] and budget_remaining(day) <= 0:
                print("Daily free-tier cap reached. Stopping to avoid charges.")
                break
            counts, err = poll_one(s["tomtom_availability_id"])
            usage["requests"] += 1
            if counts is None:
                errors[err] = errors.get(err, 0) + 1
                time.sleep(THROTTLE_SECONDS)
                continue                       # skip this station; keep polling the rest
            w.writerow({
                "timestamp_local": ts.isoformat(),
                "timestamp_utc": ts.astimezone(ZoneInfo("UTC")).isoformat(),
                "group": group_name,
                "nrel_id": s["nrel_id"], "city": s["city"],
                "network": s["network"], "funded": s["funded"],
                "multifamily": s["multifamily"], **counts,
            })
            written += 1
            time.sleep(THROTTLE_SECONDS)

    save_usage(day, usage)
    # Append a committed diagnostic line so failures are visible without runner logs.
    log = ROOT / "data" / "master" / "_collect_log.txt"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a") as lf:
        lf.write(f"{ts.isoformat()} {group_name}: wrote={written} "
                 f"failed={len(stations) - written} errors={errors} "
                 f"requests_today={usage['requests']}\n")
    print(f"[{group_name}] wrote {written} rows, errors={errors}.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python src/collect.py <group_name>")
        sys.exit(1)
    main(sys.argv[1])
