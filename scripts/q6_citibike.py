"""Q6 (Citi Bike): trips that end inside the zone, by origin neighborhood (NTA).

Downloads the monthly system data ZIPs from https://s3.amazonaws.com/tripdata/ and
compares the same month before and after the toll (default: October 2024 vs October 2025).

Usage: python q6_citibike.py [--before 202410] [--after 202510]
Output: data/processed/q6_citibike_origins.csv
"""
import argparse
import io
import zipfile

import pandas as pd
import requests

from m2_common import RAW, join_nta, label_area, save, write_sample

ap = argparse.ArgumentParser()
ap.add_argument("--before", default="202410")
ap.add_argument("--after", default="202510")
args = ap.parse_args()

USECOLS = ["started_at", "ended_at", "start_lat", "start_lng", "end_lat", "end_lng"]


def get_zip(ym: str) -> zipfile.ZipFile:
    path = RAW / f"{ym}-citibike-tripdata.zip"
    if not path.exists():
        url = f"https://s3.amazonaws.com/tripdata/{ym}-citibike-tripdata.zip"
        print(f"Downloading {url} (several hundred MB)")
        with requests.get(url, stream=True, timeout=600) as r:
            r.raise_for_status()
            with open(path, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
    return zipfile.ZipFile(path)


def csv_members(z: zipfile.ZipFile):
    for name in z.namelist():
        if name.endswith(".csv") and not name.startswith("__MACOSX"):
            yield z.open(name)
        elif name.endswith(".zip"):  # some months nest zips
            yield from csv_members(zipfile.ZipFile(io.BytesIO(z.read(name))))


label_cache: dict[tuple, str] = {}


def labels_for(lon: pd.Series, lat: pd.Series) -> pd.Series:
    keys = list(zip(lon.round(4), lat.round(4)))
    new = [k for k in set(keys) if k not in label_cache]
    if new:
        nk = pd.DataFrame(new, columns=["lon", "lat"])
        for k, v in zip(new, label_area(nk["lon"], nk["lat"])):
            label_cache[k] = v
    return pd.Series([label_cache[k] for k in keys], index=lon.index)


def origins_into_zone(ym: str) -> pd.DataFrame:
    counts = []
    total = kept = 0
    for f in csv_members(get_zip(ym)):
        for chunk in pd.read_csv(f, usecols=USECOLS, chunksize=500_000, low_memory=False):
            total += len(chunk)
            chunk = chunk.dropna(subset=["start_lat", "start_lng", "end_lat", "end_lng"])
            dur = (pd.to_datetime(chunk["ended_at"]) - pd.to_datetime(chunk["started_at"])).dt.total_seconds()
            chunk = chunk[(dur >= 60) & (dur <= 3 * 3600)]
            chunk = chunk[labels_for(chunk["end_lng"], chunk["end_lat"]) == "inside"]
            kept += len(chunk)
            counts.append(chunk.assign(lon=chunk["start_lng"].round(4), lat=chunk["start_lat"].round(4))
                          .groupby(["lon", "lat"]).size().rename("trips"))
    print(f"  {ym}: {total:,} trips, {kept:,} valid trips ending in the zone")
    c = pd.concat(counts).groupby(level=[0, 1]).sum().reset_index()
    c["origin_area"] = labels_for(c["lon"], c["lat"]).values
    c = join_nta(c, "lon", "lat").dropna(subset=["nta_name"])
    out = c.groupby(["nta_name", "borough"], as_index=False)["trips"].sum()
    # an NTA can straddle the 2 km line; label it by where most of its trips start
    major = (c.groupby(["nta_name", "origin_area"])["trips"].sum().reset_index()
              .sort_values("trips").drop_duplicates("nta_name", keep="last"))
    return out.merge(major[["nta_name", "origin_area"]], on="nta_name")


b = origins_into_zone(args.before).rename(columns={"trips": f"trips_into_zone_{args.before}"})
a = origins_into_zone(args.after).rename(columns={"trips": f"trips_into_zone_{args.after}"})
out = b.merge(a, on=["nta_name", "borough"], how="outer", suffixes=("", "_after"))
out["origin_area"] = out["origin_area"].fillna(out.pop("origin_area_after"))
out = out.fillna(0)
out["pct_change"] = 100 * (out[f"trips_into_zone_{args.after}"] / out[f"trips_into_zone_{args.before}"] - 1)
out["added_trips"] = out[f"trips_into_zone_{args.after}"] - out[f"trips_into_zone_{args.before}"]
out = out.rename(columns={"nta_name": "origin_nta", "borough": "origin_borough"})
out = out[["origin_nta", "origin_borough", "origin_area", f"trips_into_zone_{args.before}",
           f"trips_into_zone_{args.after}", "pct_change", "added_trips"]]
out = out.sort_values("added_trips", ascending=False)
save(out, "q6_citibike_origins")
write_sample(out, "q6_citibike",
             note=f"Trips ending inside the zone, by start-station NTA; {args.before} vs {args.after}. "
                  "Trips under 60 s or over 3 h removed.")
