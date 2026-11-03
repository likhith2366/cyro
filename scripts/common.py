"""Shared helpers: paths, Socrata download, and zone geometry."""
import json
import math
import time
from pathlib import Path

import pandas as pd
import requests
from shapely.geometry import Point, shape
from shapely.ops import transform, unary_union

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
SKETCHES = ROOT / "sketches"
for d in (RAW, PROCESSED, SKETCHES):
    d.mkdir(parents=True, exist_ok=True)

NY = "https://data.ny.gov/resource"
NYC = "https://data.cityofnewyork.us/resource"

# Socrata dataset IDs
CRZ_ENTRIES = f"{NY}/t6yz-b64h.json"      # MTA CRZ Vehicle Entries: Beginning 2025
CBD_SPEEDS = f"{NY}/6p29-6xqn.json"       # MTA CBD Taxi & FHV Speeds: Beginning Oct 2019
CBD_VMT = f"{NY}/jbxx-kxff.json"          # MTA Vehicle Miles Traveled in the CBD: Beginning 2024
CBD_GEOFENCE = f"{NY}/srxy-5nxn.json"     # MTA CBD Geofence (zone outline)
SUBWAY_2024 = f"{NY}/wujg-7c2s.json"      # MTA Subway Hourly Ridership: 2020-2024
SUBWAY_2025 = f"{NY}/5wq4-mkjj.json"      # MTA Subway Hourly Ridership: Beginning 2025
OD_2024 = f"{NY}/jsu2-fbtj.json"          # MTA Subway Origin-Destination Ridership Estimate: 2024
OD_2025 = f"{NY}/y2qv-fytt.json"          # MTA Subway Origin-Destination Ridership Estimate: 2025
COLLISIONS = f"{NYC}/h9gi-nx95.json"      # NYPD Motor Vehicle Collisions - Crashes

TOLL_START = pd.Timestamp("2025-01-05")


def socrata(url, params, page=50000, cache=None):
    """Download every row of a SoQL query, paging with $offset. Cached to data/raw."""
    if cache is not None:
        path = RAW / cache
        if path.exists():
            return pd.read_csv(path, low_memory=False)
    rows, offset = [], 0
    while True:
        p = dict(params, **{"$limit": page, "$offset": offset})
        for attempt in range(5):
            try:
                r = requests.get(url, params=p, timeout=600)
                r.raise_for_status()
                break
            except requests.RequestException:
                if attempt == 4:
                    raise
                time.sleep(5 * (attempt + 1))
        chunk = r.json()
        rows.extend(chunk)
        print(f"  {url.rsplit('/', 1)[-1]}: {len(rows):,} rows", flush=True)
        if len(chunk) < page:
            break
        offset += page
    df = pd.DataFrame(rows)
    if cache is not None:
        df.to_csv(RAW / cache, index=False)
    return df


# --- geometry -----------------------------------------------------------------
# Local equirectangular projection (metres) so we can buffer the zone by a distance.
LAT0 = 40.75
KX = 111_320 * math.cos(math.radians(LAT0))
KY = 110_540


def to_m(x, y, z=None):
    return (x * KX, y * KY)


def to_deg(x, y, z=None):
    return (x / KX, y / KY)


def crz_polygon():
    """Union of the MTA geofence polygons = the Congestion Relief Zone outline (lon/lat)."""
    path = RAW / "crz_geofence.geojson"
    if not path.exists():
        rows = requests.get(CBD_GEOFENCE, timeout=120).json()
        geom = unary_union([shape(r["polygon"]) for r in rows])
        path.write_text(json.dumps(geom.__geo_interface__))
    return shape(json.loads(path.read_text()))


ADJACENT_KM = 1.5


def area_classifier():
    """Return f(lon, lat) -> 'CRZ' | 'Adjacent' | 'Rest of NYC'.

    'Adjacent' = within ADJACENT_KM of the zone boundary but outside it
    (Upper East/West Side below ~85th St, Long Island City, Downtown Brooklyn,
    plus the Jersey shoreline which has no NYC data anyway).
    """
    crz = crz_polygon()
    crz_m = transform(to_m, crz)
    ring_m = crz_m.buffer(ADJACENT_KM * 1000)
    from shapely.prepared import prep
    p_crz, p_ring = prep(crz_m), prep(ring_m)

    def classify(lon, lat):
        pt = Point(lon * KX, lat * KY)
        if p_crz.contains(pt):
            return "CRZ"
        if p_ring.contains(pt):
            return "Adjacent"
        return "Rest of NYC"

    return classify


def label_time(df, col):
    """Add peak/off-peak, weekday/weekend and pre/post toll labels to a timestamp column."""
    t = pd.to_datetime(df[col])
    weekend = t.dt.dayofweek >= 5
    h = t.dt.hour
    peak = (~weekend & h.between(5, 20)) | (weekend & h.between(9, 20))
    df["day_type"] = weekend.map({True: "Weekend", False: "Weekday"})
    df["toll_period"] = peak.map({True: "Peak", False: "Off-peak"})
    df["post_toll"] = t >= TOLL_START
    return df
