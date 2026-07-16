"""Probe TomTom search endpoints to find the one that lists EV chargers + availability IDs."""
import os, json, requests
key = os.environ.get("TOMTOM_API_KEY", "")
LAT, LON = 47.6101, -122.2015  # Bellevue center

def show(name, url, params):
    try:
        r = requests.get(url, params=params, timeout=30)
        print(f"\n=== {name}: HTTP {r.status_code} ===")
        if not r.ok:
            print("  body:", r.text[:200]); return
        j = r.json()
        results = j.get("results", [])
        print(f"  results={len(results)}")
        for x in results[:3]:
            poi = x.get("poi", {}).get("name")
            avail = x.get("dataSources", {}).get("chargingAvailability", {}).get("id")
            cats = x.get("poi", {}).get("categories")
            addr = x.get("address", {}).get("freeformAddress")
            print(f"   - {poi} | avail_id={avail} | {addr} | {cats}")
    except Exception as e:
        print(f"\n=== {name}: ERROR {repr(e)[:150]} ===")

# 1. nearbySearch by EV category
show("nearbySearch cat7309", "https://api.tomtom.com/search/2/nearbySearch/.json",
     {"key": key, "lat": LAT, "lon": LON, "radius": 8000, "categorySet": 7309, "limit": 20})
# 2. categorySearch text
show("categorySearch 'electric vehicle station'",
     "https://api.tomtom.com/search/2/categorySearch/electric%20vehicle%20station.json",
     {"key": key, "lat": LAT, "lon": LON, "radius": 8000, "limit": 20})
# 3. poiSearch cat only (no restrictive text)
show("poiSearch cat7309 broad",
     "https://api.tomtom.com/search/2/poiSearch/ev.json",
     {"key": key, "lat": LAT, "lon": LON, "radius": 8000, "categorySet": 7309, "limit": 20})
