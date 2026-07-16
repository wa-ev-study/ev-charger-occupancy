"""
stations.py  -  Build and tag the master list of chargers.

What this does, in plain English:
  1. Asks NREL (a free U.S. government database) for every PUBLIC electric
     charging station in the cities we care about.
  2. Tags each station:
        - funded   : built with state/federal money (NEVI / public grants)
        - multifamily : located at an apartment or condo complex
  3. Looks each station up ONCE in TomTom to get the "chargingAvailability" ID
     that the live poller needs. This lookup is cached, so we don't repeat it.

The output is data/master/stations.json -- the universe we then poll.

Nothing here needs editing for normal use. Keys come from environment variables
(GitHub Secrets), never hard-coded.
"""

import json
import os
import time
from pathlib import Path

import requests

NREL_KEY = os.environ.get("NREL_API_KEY", "DEMO_KEY")
TOMTOM_KEY = os.environ.get("TOMTOM_API_KEY", "")

ROOT = Path(__file__).resolve().parent.parent
MASTER_PATH = ROOT / "data" / "master" / "stations.json"

NREL_URL = "https://developer.nrel.gov/api/alt-fuel-stations/v1.json"
TOMTOM_NEARBY = "https://api.tomtom.com/search/2/poiSearch/{q}.json"

# Words in a station's name/owner that suggest it was publicly funded.
FUNDED_HINTS = ["nevi", "wsdot", "commerce", "state of washington", "grant",
                "public", "city of", "county", "department of transportation"]
# Words that suggest an apartment / condo (multi-family) location.
MULTIFAMILY_HINTS = ["apartment", "apartments", "condo", "condominium",
                     "residences", "residential", "flats", "lofts", "village",
                     "place", "commons", "terrace", "court"]


def fetch_nrel_stations(city, state="WA"):
    """Return all public, available electric stations NREL lists for a city."""
    params = {
        "api_key": NREL_KEY,
        "fuel_type": "ELEC",
        "state": state,
        "access": "public",
        "status": "E",          # E = available/operational
        "city": city,
        "limit": "all",
    }
    r = requests.get(NREL_URL, params=params, timeout=60)
    r.raise_for_status()
    return r.json().get("fuel_stations", [])


def tag_station(s):
    """Add funded / multifamily flags based on NREL fields. Conservative:
    a station is only flagged funded if there is a real signal for it."""
    text = " ".join(str(s.get(f, "")) for f in
                    ["station_name", "ev_network", "owner_type_code",
                     "federal_agency", "facility_type"]).lower()

    funded = any(h in text for h in FUNDED_HINTS)
    # NREL marks government ownership with owner_type_code in {FG, LG, SG, T}
    if str(s.get("owner_type_code", "")).upper() in {"FG", "LG", "SG", "T"}:
        funded = True
    # NREL flags federal funding sources directly when known.
    if s.get("funding_sources"):
        funded = True

    facility = str(s.get("facility_type", "")).lower()
    name = str(s.get("station_name", "")).lower()
    multifamily = (facility in {"multi_unit_dwelling", "mud"}
                   or any(h in name for h in MULTIFAMILY_HINTS))

    return funded, multifamily


def tomtom_availability_id(lat, lon, name):
    """Find the station in TomTom and return its chargingAvailability UUID.
    Returns None if no match or if no key is set (e.g., dry-run)."""
    if not TOMTOM_KEY:
        return None
    url = TOMTOM_NEARBY.format(q="charging%20station")
    params = {
        "key": TOMTOM_KEY,
        "lat": lat, "lon": lon,
        "radius": 150,                       # meters; tight to avoid mismatches
        "categorySet": 7309,                 # TomTom category: EV charging station
        "limit": 5,
    }
    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        for result in r.json().get("results", []):
            ds = result.get("dataSources", {}).get("chargingAvailability", {})
            if ds.get("id"):
                return ds["id"]
    except requests.RequestException as e:
        print(f"  ! TomTom lookup failed for {name}: {e}")
    return None


def build_master(cities, resolve_ids=True):
    stations = {}
    for city in cities:
        print(f"NREL: fetching {city} ...")
        for s in fetch_nrel_stations(city):
            sid = str(s.get("id"))
            funded, multifamily = tag_station(s)
            stations[sid] = {
                "nrel_id": sid,
                "name": s.get("station_name"),
                "city": city,
                "lat": s.get("latitude"),
                "lon": s.get("longitude"),
                "network": s.get("ev_network"),
                "owner_type_code": s.get("owner_type_code"),
                "facility_type": s.get("facility_type"),
                "funded": funded,
                "multifamily": multifamily,
                "tomtom_availability_id": None,
            }
        time.sleep(1)  # be polite to the API

    if resolve_ids:
        print(f"TomTom: resolving availability IDs for {len(stations)} stations ...")
        for sid, st in stations.items():
            st["tomtom_availability_id"] = tomtom_availability_id(
                st["lat"], st["lon"], st["name"])
            time.sleep(0.2)  # stay well under any per-second limit

    MASTER_PATH.parent.mkdir(parents=True, exist_ok=True)
    MASTER_PATH.write_text(json.dumps(list(stations.values()), indent=2))
    matched = sum(1 for s in stations.values() if s["tomtom_availability_id"])
    funded_n = sum(1 for s in stations.values() if s["funded"])
    mf_n = sum(1 for s in stations.values() if s["multifamily"])
    print(f"Saved {len(stations)} stations "
          f"({funded_n} funded, {mf_n} multi-family, {matched} matched to TomTom).")
    return list(stations.values())


if __name__ == "__main__":
    import sys
    cities = sys.argv[1:] or ["Bellevue", "Seattle"]
    build_master(cities)
