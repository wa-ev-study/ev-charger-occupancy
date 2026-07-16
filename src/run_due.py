"""
run_due.py  -  Decide which collection groups are "due" and run them.

A single scheduled job calls this every ~15 minutes. For each enabled group it
checks how long since that group last ran; if at least `poll_minutes` have
passed, it runs it. This makes the schedule robust to GitHub's clock jitter
(a run that fires a few minutes late still does the right thing) and avoids
multiple jobs fighting to commit at once.

Last-run times are stored in data/usage/last_run.json.
"""

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

import collect  # reuse the collector

ROOT = Path(__file__).resolve().parent.parent
CONFIG = yaml.safe_load((ROOT / "config.yaml").read_text())
TZ = ZoneInfo(CONFIG["project"]["timezone"])
LAST_RUN = ROOT / "data" / "usage" / "last_run.json"


def load_last():
    return json.loads(LAST_RUN.read_text()) if LAST_RUN.exists() else {}


def save_last(d):
    LAST_RUN.parent.mkdir(parents=True, exist_ok=True)
    LAST_RUN.write_text(json.dumps(d, indent=2))


def main():
    now = datetime.now(TZ)
    last = load_last()
    for name, group in CONFIG["groups"].items():
        if not group.get("enabled"):
            continue
        prev = last.get(name)
        due = True
        if prev:
            mins = (now - datetime.fromisoformat(prev)).total_seconds() / 60
            # small slack so a slightly-early fire still counts
            due = mins >= (group["poll_minutes"] - 2)
        if due:
            print(f"== Running group '{name}' ==")
            collect.main(name)
            last[name] = now.isoformat()
        else:
            print(f"-- '{name}' not due yet --")
    save_last(last)


if __name__ == "__main__":
    main()
