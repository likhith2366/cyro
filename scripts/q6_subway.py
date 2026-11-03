"""Q6 (subway): MTA Subway Hourly Ridership, 2020-2024 (wujg-7c2s) + Beginning 2025 (5wq4-mkjj).

The two years live in separate datasets, so we aggregate each to monthly entries per
station complex on the server and stitch them together.

Output: data/processed/q6_subway_monthly.csv
"""
import pandas as pd

from m2_common import NY, columns, join_nta, label_area, log_gaps, pick, save, soql, to_num, write_sample

PARTS = [("wujg-7c2s", "2024-01-01T00:00:00", "2025-01-01T00:00:00"),
         ("5wq4-mkjj", "2025-01-01T00:00:00", "2030-01-01T00:00:00")]

frames = []
for ds, start, end in PARTS:
    cols = columns(NY, ds)
    TS = pick(cols, "transit_timestamp", "timestamp")
    SID = pick(cols, "station_complex_id")
    SNAME = pick(cols, "station_complex")
    RID = pick(cols, "ridership")
    LAT = pick(cols, "latitude")
    LON = pick(cols, "longitude")
    print(f"{ds}: monthly entries per station ({start[:4]}+), aggregated server-side")
    part = soql(NY, ds, {
        "$select": f"date_trunc_ym({TS}) as year_month, {SID} as station_complex_id, "
                   f"{SNAME} as station_complex, avg({LAT}) as latitude, avg({LON}) as longitude, "
                   f"sum({RID}) as entries",
        "$where": f"{TS} >= '{start}' and {TS} < '{end}'",
        "$group": f"date_trunc_ym({TS}), {SID}, {SNAME}",
        "$order": f"date_trunc_ym({TS}), {SID}",
    })
    frames.append(part)

df = to_num(pd.concat(frames, ignore_index=True), "entries", "latitude", "longitude")
df["year_month"] = pd.to_datetime(df["year_month"])
log_gaps("subway_hourly", df["year_month"], "M")
df = df[df["year_month"] < df["year_month"].max()]  # latest month may be partial

stations = df.groupby("station_complex_id", as_index=False)[["latitude", "longitude"]].mean()
stations["area"] = label_area(stations["longitude"], stations["latitude"])
stations = join_nta(stations, "longitude", "latitude")[["station_complex_id", "area", "nta_name", "borough"]]
df = df.drop(columns=["latitude", "longitude"]).merge(stations, on="station_complex_id", how="left")

prev = df[["year_month", "station_complex_id", "entries"]].copy()
prev = prev[prev["year_month"].dt.year == 2024]
prev["month"] = prev["year_month"].dt.month
prev = prev.drop(columns="year_month").rename(columns={"entries": "entries_same_month_2024"})
df["month"] = df["year_month"].dt.month
df = df.merge(prev, on=["month", "station_complex_id"], how="left").drop(columns="month")
df.loc[df["year_month"].dt.year == 2024, "entries_same_month_2024"] = None
df["pct_change"] = 100 * (df["entries"] / df["entries_same_month_2024"] - 1)
df["year_month"] = df["year_month"].dt.strftime("%Y-%m")
df = df.sort_values(["year_month", "area", "station_complex"])
save(df, "q6_subway_monthly")
write_sample(df[(df["area"] == "inside") & df["pct_change"].notna()], "q6_subway",
             note="Fare entries; 2025+ months compared with the same month of 2024.")

zone = (df[df["entries_same_month_2024"].notna()]
        .groupby(["year_month", "area"], as_index=False)[["entries", "entries_same_month_2024"]].sum())
zone["pct_change"] = 100 * (zone["entries"] / zone["entries_same_month_2024"] - 1)
save(zone, "q6_subway_by_area")
