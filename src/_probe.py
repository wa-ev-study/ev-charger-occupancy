"""Connectivity probe: what can the GitHub runner actually reach?"""
import os, requests

def probe(name, url, params):
    try:
        r = requests.get(url, params=params, timeout=30)
        print(f"{name}: HTTP {r.status_code} | bytes={len(r.content)}")
        if r.ok:
            try:
                j = r.json()
                if "total_results" in j:
                    print(f"   NREL total_results={j['total_results']}")
                if "results" in j:
                    print(f"   TomTom results={len(j['results'])}; "
                          f"has_avail_id="
                          f"{any(x.get('dataSources',{}).get('chargingAvailability',{}).get('id') for x in j['results'])}")
            except Exception as e:
                print("   (json parse issue)", e)
    except Exception as e:
        print(f"{name}: ERROR {repr(e)[:160]}")

key = os.environ.get("TOMTOM_API_KEY", "")
print("TOMTOM key present:", bool(key))
probe("NREL", "https://developer.nrel.gov/api/alt-fuel-stations/v1.json",
      {"api_key": "DEMO_KEY", "fuel_type": "ELEC", "state": "WA",
       "access": "public", "status": "E", "city": "Bellevue", "limit": "1"})
probe("TomTom-poiSearch", "https://api.tomtom.com/search/2/poiSearch/charging%20station.json",
      {"key": key, "lat": 47.6101, "lon": -122.2015, "radius": 8000,
       "categorySet": 7309, "limit": 10})
probe("TomTom-evSearch", "https://api.tomtom.com/search/2/evsearch.json",
      {"key": key, "lat": 47.6101, "lon": -122.2015, "radius": 8000, "limit": 10})
