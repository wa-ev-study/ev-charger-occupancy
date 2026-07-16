"""
stations.py  -  Build the master list of chargers to poll.

PRIMARY SOURCE: TomTom nearbySearch (reachable, returns each station's
chargingAvailability ID directly). We enumerate EV charging stations per city
and keep the ones inside that city.

OPTIONAL ENRICHMENT: NREL (funding / multi-family tags). NREL is attempted but
is currently unreachable in some environments; if it fails we proceed without
those tags and can back-fill later, since raw data is retained.

Output: data/master/stations.json
"""

import json
import os
import time
from pathlib import Path

import requests

TOMTOM_KEY = os.environ.get("TOMTOM_API_KEY", "")
NREL_KEY = os.environ.get("NREL_API_KEY") or "DEMO_KEY"

ROOT = Path(__file__).resolve().parent.parent
MASTER_PATH = ROOT / "data" / "master" / "stations.json"

NEARBY = "https://api.tomtom.com/search/2/nearbySearch/.json"
EV_CATEGORY = 7309  # TomTom category id for "electric vehicle station"

# City center + search radius (meters). nearbySearch is paginated to cover all.
CITY_GEO = {
    "Bellevue": (47.6101, -122.2015, 9000),
    "Seattle":  (47.6062, -122.3321, 13000),
    "Redmond":  (47.6740, -122.1215, 8000),
}

MULTIFAMILY_HINTS = ["apartment", "apartments", "condo", "condominium",
                     "residence", "residences", "residential", "lofts",
                     "flats", "villas", "village apartments"]


def fetch_city_stations(city):
    """Enumerate EV stations in a city via paginated nearbySearch."""
    if city not in CITY_GEO:
        print(f"  ! no center defined for {city}; skipping")
        return []
    lat, lon, radius = CITY_GEO[city]
    found = {}
    ofs = 0
    while ofs <= 1900:
        params = {"key": TOMTOM_KEY, "lat": lat, "lon": lon, "radius": radius,
                  "categorySet": EV_CATEGORY, "limit": 100, "ofs": ofs,
                  "countrySet": "US"}
        r = requests.get(NEARBY, params=params, timeout=30)
        if not r.ok:
            print(f"  ! nearbySearch {city} HTTP {r.status_code}: {r.text[:120]}")
            break
        results = r.json().get("results", [])
        if not results:
            break
        for x in results:
            avail = x.get("dataSources", {}).get("chargingAvailability", {}).get("id")
            if not avail:
                continue
            muni = (x.get("address", {}).get("municipality") or "")
            if muni.lower() != city.lower():
                continue  # keep only stations actually in this city
            addr = x.get("address", {}).get("freeformAddress", "")
            name = x.get("poi", {}).get("name", "")
            pos = x.get("position", {})
            multifamily = any(h in (name + " " + addr).lower() for h in MULTIFAMILY_HINTS)
            found[avail] = {
                "nrel_id": avail,            # kept for schema compatibility
                "tomtom_availability_id": avail,
                "name": name,
                "address": addr,
                "city": city,
                "lat": pos.get("lat"),
                "lon": pos.get("lon"),
                "network": name,             # TomTom poi.name is usually the network
                "funded": False,             # pending NREL enrichment
                "multifamily": multifamily,  # best-effort until NREL enrichment
            }
        if len(results) < 100:
            break
        ofs += 100
        time.sleep(0.2)
    return list(found.values())


def try_nrel_enrichment(stations):
    """If NREL is reachable, tag funded / multi-family by matching location.
    Best-effort: any failure leaves stations as-is."""
    try:
        by_city = {}
        for s in stations:
            by_city.setdefault(s["city"], []).append(s)
        for city, group in by_city.items():
            r = requests.get(
                "https://developer.nrel.gov/api/alt-fuel-stations/v1.json",
                params={"api_key": NREL_KEY, "fuel_type": "ELEC", "state": "WA",
                        "access": "public", "status": "E", "city": city,
                        "limit": "all"}, timeout=30)
            r.raise_for_status()
            nrel = r.json().get("fuel_stations", [])
            print(f"  NREL enrichment: {city} has {len(nrel)} records")
            for s in group:
                best = _nearest(s, nrel, 0.003)  # ~300m
                if best:
                    otc = str(best.get("owner_type_code", "")).upper()
                    if otc in {"FG", "LG", "SG", "T"} or best.get("funding_sources"):
                        s["funded"] = True
                    if str(best.get("facility_type", "")).lower() in {"multi_unit_dwelling", "mud"}:
                        s["multifamily"] = True
        return True
    except Exception as e:
        print(f"  NREL enrichment skipped (unreachable): {repr(e)[:120]}")
        return False


def _nearest(s, nrel, tol):
    best = None
    bd = tol
    for n in nrel:
        try:
            d = abs(float(n["latitude"]) - s["lat"]) + abs(float(n["longitude"]) - s["lon"])
        except (TypeError, ValueError):
            continue
        if d < bd:
            bd, best = d, n
    return best


def build_master(cities):
    stations = []
    for city in cities:
        print(f"TomTom: enumerating {city} ...")
        city_stations = fetch_city_stations(city)
        print(f"  {city}: {len(city_stations)} stations with availability IDs")
        stations.extend(city_stations)

    try_nrel_enrichment(stations)

    MASTER_PATH.parent.mkdir(parents=True, exist_ok=True)
    MASTER_PATH.write_text(json.dumps(stations, indent=2))
    funded = sum(1 for s in stations if s["funded"])
    mf = sum(1 for s in stations if s["multifamily"])
    print(f"Saved {len(stations)} stations total ({funded} funded, {mf} multi-family).")
    return stations


if __name__ == "__main__":
    import sys
    cities = sys.argv[1:] or ["Bellevue", "Seattle"]
    build_master(cities)
