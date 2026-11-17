"""Q6 (subway origins): MTA Subway Origin-Destination Ridership Estimates, Oct 2024 vs Oct 2025.

Station fare entries (q6_subway.py) count where a rider starts, not where they are going, so they
cannot answer the "from which neighborhoods" half of Q6. These OD estimates can: each row is an
origin/destination station pair with an estimated average ridership for that hour of that month.

This is the Pipeline B version of the table. It uses the same hand-digitized zone outline as every
other area label in Pipeline B (m2_common.ZONE_LONLAT), filtering server-side with within_polygon()
for weekday trips that END inside the zone and START outside it. An earlier Pipeline A build of the
same table used the official MTA geofence instead; both are kept so the two can be compared.

Output: data/processed/q6_subway_od_into_zone.csv
"""
import json

import pandas as pd
from shapely.geometry import Point, Polygon, shape
from shapely.prepared import prep

from m2_common import NY, RAW, save, soql, to_num, write_sample, zone_polygon_lonlat

DATASETS = {2024: "jsu2-fbtj", 2025: "y2qv-fytt"}
WEEKDAYS = "('Monday','Tuesday','Wednesday','Thursday','Friday')"

zone_wkt = zone_polygon_lonlat().wkt
print(f"Zone outline (Pipeline B, hand-digitized): {len(zone_wkt)} chars of WKT")

frames = []
for year, ds in DATASETS.items():
    print(f"{ds}: October {year} weekday trips ending inside the zone")
    part = soql(NY, ds, {
        "$select": "origin_station_complex_id, origin_station_complex_name, origin_latitude, "
                   "origin_longitude, sum(estimated_average_ridership) as riders",
        "$where": f"month = '10' and day_of_week in {WEEKDAYS} "
                  f"and within_polygon(destination_point, '{zone_wkt}') "
                  f"and not within_polygon(origin_point, '{zone_wkt}')",
        "$group": "origin_station_complex_id, origin_station_complex_name, origin_latitude, origin_longitude",
        "$order": "origin_station_complex_id",
    })
    part["year"] = year
    frames.append(part)

df = to_num(pd.concat(frames, ignore_index=True), "riders", "origin_latitude", "origin_longitude")
# riders is summed over the five weekday labels, each already an average for that day type
df["riders"] = df["riders"] / 5


def nta_lookup():
    """Point-in-polygon against the 2020 NTAs, using shapely only (no geopandas needed)."""
    path = RAW / "nta2020.geojson"
    if not path.exists():
        raise SystemExit("Missing data/raw/nta2020.geojson -- run scripts/fetch_data.py first.")
    feats = json.loads(path.read_text())["features"]
    polys = [(prep(shape(f["geometry"])), f["properties"]["ntaname"], f["properties"]["boroname"])
             for f in feats]

    def find(lon, lat):
        p = Point(lon, lat)
        for poly, name, boro in polys:
            if poly.contains(p):
                return name, boro
        return None, None
    return find


find = nta_lookup()
stations = df.groupby("origin_station_complex_id", as_index=False)[
    ["origin_longitude", "origin_latitude"]].mean()
loc = {sid: find(lon, lat) for sid, lon, lat in stations.itertuples(index=False)}
df["nta"] = df["origin_station_complex_id"].map(lambda s: loc[s][0])
df["borough"] = df["origin_station_complex_id"].map(lambda s: loc[s][1])
unmatched = df["nta"].isna().sum()
if unmatched:
    print(f"  {unmatched} origin rows fell outside every NTA polygon and are dropped")
df = df.dropna(subset=["nta"])

out = (df.groupby(["nta", "borough", "year"])["riders"].sum().unstack("year").reset_index())
out.columns.name = None
out = out.rename(columns={2024: "avg_weekday_riders_oct2024", 2025: "avg_weekday_riders_oct2025"})
out["change"] = out["avg_weekday_riders_oct2025"] - out["avg_weekday_riders_oct2024"]
out["pct_change"] = 100 * out["change"] / out["avg_weekday_riders_oct2024"]
out = out.round(1).sort_values("avg_weekday_riders_oct2025", ascending=False)
save(out, "q6_subway_od_into_zone")
write_sample(out, "q6_subway_od",
             note="Average weekday subway trips into the zone by origin neighborhood, Oct 2024 vs "
                  "Oct 2025, using the Pipeline B zone outline.")

tot24, tot25 = out["avg_weekday_riders_oct2024"].sum(), out["avg_weekday_riders_oct2025"].sum()
print(f"\nTotal average weekday trips into the zone from outside: "
      f"{tot24:,.0f} (Oct 2024) -> {tot25:,.0f} (Oct 2025), {100 * (tot25 / tot24 - 1):+.1f}%")

# How much does the boundary choice matter? Compare with the Pipeline A build if it is present.
old = RAW.parent / "processed" / "q6_subway_od_into_crz_by_neighborhood.csv"
if old.exists():
    a = pd.read_csv(old)
    cmp = a.merge(out, on="nta", suffixes=("_pipelineA", "_pipelineB"))
    d24 = (cmp["avg_weekday_riders_oct2024_pipelineB"] - cmp["avg_weekday_riders_oct2024_pipelineA"])
    print(f"Boundary comparison: {len(cmp)} neighborhoods in both builds "
          f"(Pipeline A had {len(a)}, Pipeline B has {len(out)}); "
          f"median difference in Oct 2024 riders {d24.median():+,.0f} "
          f"({100 * d24.abs().median() / cmp['avg_weekday_riders_oct2024_pipelineA'].median():.1f}% of the median neighborhood)")
