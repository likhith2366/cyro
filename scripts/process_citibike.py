"""Step 2a: reduce Citi Bike monthly trip files to trips ending inside the CRZ.

Downloads data/raw/citibike/202402.zip and 202502.zip (about 800 MB) from
https://s3.amazonaws.com/tripdata/ if they are not already there. Writes data/raw/citibike_into_crz_<yyyymm>.csv (one row per start station
x hour x day type), which process_data.py then aggregates.
"""
import zipfile

import pandas as pd
import requests

from common import RAW, area_classifier, label_time

MONTHS = ["202402", "202502"]
COLS = ["started_at", "ended_at", "start_station_name", "start_lat", "start_lng",
        "end_lat", "end_lng", "member_casual", "rideable_type"]


def main():
    classify = area_classifier()
    for m in MONTHS:
        out = RAW / f"citibike_into_crz_{m}.csv"
        if out.exists():
            continue
        src = RAW / "citibike" / f"{m}.zip"
        if not src.exists():
            src.parent.mkdir(exist_ok=True)
            print(f"downloading {m} Citi Bike trips", flush=True)
            with requests.get(f"https://s3.amazonaws.com/tripdata/{m}-citibike-tripdata.zip", stream=True, timeout=600) as r:
                r.raise_for_status()
                with open(src, "wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
        z = zipfile.ZipFile(src)
        parts = []
        for name in sorted(n for n in z.namelist() if n.endswith(".csv")):
            df = pd.read_csv(z.open(name), usecols=COLS, low_memory=False)
            n0 = len(df)
            df = df.dropna(subset=["start_lat", "start_lng", "end_lat", "end_lng"])
            dur = (pd.to_datetime(df.ended_at) - pd.to_datetime(df.started_at)).dt.total_seconds()
            # drop broken trips: < 1 min or > 3 h
            df = df[(dur >= 60) & (dur <= 3 * 3600)]
            # classify on rounded coordinates to keep the point-in-polygon work small
            for end in ("start", "end"):
                key = df[f"{end}_lng"].round(4).astype(str) + "," + df[f"{end}_lat"].round(4).astype(str)
                lut = {k: classify(*map(float, k.split(","))) for k in key.unique()}
                df[f"{end}_area"] = key.map(lut)
            print(f"  {name}: kept {len(df):,}/{n0:,}", flush=True)
            parts.append(df)
        df = pd.concat(parts)
        df["month"] = m
        df["hour"] = pd.to_datetime(df.started_at).dt.hour
        df = label_time(df, "started_at")
        into = df[(df.end_area == "CRZ")]
        agg = (into.groupby(["month", "start_station_name", "start_area", "day_type", "hour",
                             "member_casual"], as_index=False)
               .agg(trips=("started_at", "size"), start_lat=("start_lat", "median"),
                    start_lng=("start_lng", "median")))
        agg.to_csv(out, index=False)
        totals = df.groupby(["start_area", "end_area"]).size().rename("trips").reset_index()
        totals["month"] = m
        totals.to_csv(RAW / f"citibike_area_matrix_{m}.csv", index=False)
        print(f"{m}: {len(into):,} trips end in CRZ", flush=True)


if __name__ == "__main__":
    main()
