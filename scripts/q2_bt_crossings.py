"""Q2 baseline: MTA Bridges and Tunnels Hourly Crossings (data.ny.gov ebfx-2m7v).

The CRZ entries data starts on the toll's first day, so this dataset provides the
2024 vs 2025 comparison for Manhattan-bound crossings at tunnels that feed the zone.

Output: data/processed/q2_bt_yoy.csv
"""
import pandas as pd

from common import NY, RAW, columns, pick, save, soql, to_num, write_sample

DS = "ebfx-2m7v"

# Facilities that lead straight into the zone, and the direction values that mean "into Manhattan".
# Check data/raw/bt_facility_direction.csv after the first run and adjust if needed.
FACILITIES = {"carey": "Hugh L. Carey Tunnel", "midtown": "Queens Midtown Tunnel"}
INTO_MANHATTAN = {"carey": {"n", "nb", "north", "northbound", "i", "in", "inbound"},
                  "midtown": {"w", "wb", "west", "westbound", "i", "in", "inbound"}}

cols = columns(NY, DS)
print("Columns:", sorted(cols))
TS = pick(cols, "date", "timestamp", "hour")
FAC = pick(cols, "facility", "plaza")
DIR = pick(cols, "direction")
VC = pick(cols, "vehicle_class", "class")
CNT = pick(cols, "vehicles", "crossings", "total", "traffic", "count")
print("Using columns:", TS, FAC, DIR, VC, CNT)

is_ts = cols[TS] in ("calendar_date", "floating_timestamp")
day_expr = f"date_trunc_ymd({TS})" if is_ts else TS
where = f"{TS} >= '2024-01-01T00:00:00'" if is_ts else None

params = {
    "$select": f"{day_expr} as day, {FAC} as facility, {DIR} as direction, {VC} as vehicle_class, "
               f"sum({CNT}) as crossings",
    "$group": f"{day_expr}, {FAC}, {DIR}, {VC}",
    "$order": f"{day_expr}, {FAC}, {DIR}, {VC}",
}
if where:
    params["$where"] = where
df = to_num(soql(NY, DS, params), "crossings")
df["day"] = pd.to_datetime(df["day"])
df = df[df["day"] >= "2024-01-01"]

# record which facility/direction values exist, so the filter above can be checked
df.groupby(["facility", "direction"], as_index=False)["crossings"].sum().to_csv(
    RAW / "bt_facility_direction.csv", index=False)


def keep(row) -> bool:
    fac = str(row["facility"]).lower()
    d = str(row["direction"]).strip().lower()
    return any(k in fac and "to manhattan" in d for k in FACILITIES)


mask = df[["facility", "direction"]].drop_duplicates()
mask = mask[mask.apply(keep, axis=1)]
print("Keeping facility/direction pairs:\n", mask.to_string(index=False))
df = df.merge(mask, on=["facility", "direction"])

df["year_month"] = df["day"].dt.to_period("M").dt.to_timestamp()
m = df.groupby(["year_month", "facility", "vehicle_class"], as_index=False)["crossings"].sum()
prev = m.copy()
prev["year_month"] = prev["year_month"] + pd.DateOffset(years=1)
prev = prev.rename(columns={"crossings": "crossings_same_month_2024"})
out = m[m["year_month"].dt.year == 2025].merge(prev, on=["year_month", "facility", "vehicle_class"], how="left")
out["pct_change"] = (out["crossings"] / out["crossings_same_month_2024"] - 1) * 100
out["year_month"] = out["year_month"].dt.strftime("%Y-%m")
save(out, "q2_bt_yoy")
write_sample(out, "q2_bt", note="Manhattan-bound crossings; 2025 month vs. same month of 2024.")
