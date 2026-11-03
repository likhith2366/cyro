"""Q4 (and speed inputs for Q5/Q8): MTA CBD Taxi and FHV Speeds (data.ny.gov 6p29-6xqn).

Output: data/processed/q4_speeds_monthly.csv
  avg speed per month x area x time period, change vs same month of 2024,
  and difference-in-differences vs the rest of the city.
"""
import pandas as pd

from m2_common import NY, columns, log_gaps, pick, save, soql, write_sample

DS = "6p29-6xqn"

cols = columns(NY, DS)
print("Columns:", sorted(cols))
MONTH = pick(cols, "month", "year_month", "date", "period")
AREA = pick(cols, "geography", "region", "area", "location", "zone")
TP = pick(cols, "time_period", "peak", "day_type", "period", required=False)
SPEED = pick(cols, "average_speed", "avg_speed", "speed")
print("Using columns:", MONTH, AREA, TP, SPEED)

df = soql(NY, DS, {"$order": MONTH})
df[SPEED] = pd.to_numeric(df[SPEED], errors="coerce")
df["year_month"] = pd.to_datetime(df[MONTH]).dt.to_period("M").dt.to_timestamp()
log_gaps("cbd_speeds", df["year_month"], "M")

print("Area values found:", sorted(df[AREA].dropna().unique()))


def area_label(v: str) -> str:
    v = str(v).lower()
    if "adjacent" in v or "near" in v:
        return "adjacent"
    if "rest" in v or "outside" in v or "other" in v or "citywide" in v or "greater" in v:
        return "rest_of_nyc"
    if "cbd" in v or "zone" in v or "central" in v or "manhattan" in v:
        return "inside"
    return v


df["area"] = df[AREA].map(area_label)
df["time_period"] = df[TP] if TP else "all"
m = df.groupby(["year_month", "area", "time_period"], as_index=False)[SPEED].mean()
m = m.rename(columns={SPEED: "avg_speed_mph"})

base = m.copy()
base["year_month"] = base["year_month"] + pd.DateOffset(years=1)
base = base.rename(columns={"avg_speed_mph": "speed_same_month_2024"})
m = m.merge(base[base["year_month"].dt.year == 2025], on=["year_month", "area", "time_period"], how="left")
# 2026 months compare to 2024 too (two years earlier), so the baseline stays pre-toll
b2 = base.copy()
b2["year_month"] = b2["year_month"] + pd.DateOffset(years=1)
m = m.merge(b2[b2["year_month"].dt.year == 2026], on=["year_month", "area", "time_period"],
            how="left", suffixes=("", "_y"))
m["speed_same_month_2024"] = m["speed_same_month_2024"].fillna(m.pop("speed_same_month_2024_y"))
m["change_mph"] = m["avg_speed_mph"] - m["speed_same_month_2024"]

rest = m[m["area"] == "rest_of_nyc"][["year_month", "time_period", "change_mph"]].rename(
    columns={"change_mph": "rest_change"})
m = m.merge(rest, on=["year_month", "time_period"], how="left")
m["did_vs_rest_mph"] = m["change_mph"] - m["rest_change"]
m = m.drop(columns="rest_change")
m["year_month"] = m["year_month"].dt.strftime("%Y-%m")
m = m.sort_values(["year_month", "area", "time_period"])
save(m, "m2_q4_speeds_monthly")
write_sample(m[m["year_month"] >= "2025-01"], "q4",
             note="change_mph = vs. same month of 2024; did_vs_rest_mph = inside/adjacent change minus rest-of-NYC change.")
