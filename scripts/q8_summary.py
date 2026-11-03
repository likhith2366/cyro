"""Q8: per-neighborhood summary joining the Q4-Q7 outputs.

Every *_benefit column is signed so that positive = the neighborhood gained
(fewer crashes, more transit/bike trips, faster speeds).

Output: data/processed/q8_nta_summary.csv
"""
import pandas as pd

from common import PROC, save, write_sample

crash = pd.read_csv(PROC / "q5_nta_crash_change.csv")
bike = pd.read_csv(PROC / "q6_citibike_origins.csv")
subway = pd.read_csv(PROC / "q6_subway_monthly.csv")
speeds = pd.read_csv(PROC / "q4_speeds_monthly.csv")

# subway: total 2025 entries vs same months of 2024, per NTA
s = subway[subway["year_month"].str.startswith("2025") & subway["entries_same_month_2024"].notna()]
s = s.groupby("nta_name", as_index=False)[["entries", "entries_same_month_2024"]].sum()
s["subway_change_pct"] = 100 * (s["entries"] / s["entries_same_month_2024"] - 1)

# speeds: mean 2025 change per area (speeds are only published at area level)
sp = speeds[speeds["year_month"].str.startswith("2025")].groupby("area")["change_mph"].mean()
sp = sp.rename({"rest_of_nyc": "elsewhere"})

b = bike[["origin_nta", "origin_borough", "origin_area", "pct_change"]].rename(
    columns={"origin_nta": "nta_name", "origin_borough": "borough", "origin_area": "area",
             "pct_change": "citibike_change_pct"})
c = crash[["nta_name", "borough", "area", "crash_change_pct"]]

out = (c.merge(b, on=["nta_name", "borough"], how="outer", suffixes=("", "_bike"))
        .merge(s[["nta_name", "subway_change_pct"]], on="nta_name", how="left"))
out["area"] = out["area"].fillna(out.pop("area_bike"))
out = out[out["area"].isin(["inside", "adjacent"])]
out["speed_change_mph"] = out["area"].map(sp)

out["safety_benefit"] = -out["crash_change_pct"]
out["citibike_benefit"] = out["citibike_change_pct"]
out["subway_benefit"] = out["subway_change_pct"]
out["speed_benefit"] = out["speed_change_mph"]
out = out.sort_values(["area", "nta_name"])
save(out, "q8_nta_summary")
write_sample(out[["nta_name", "borough", "area", "crash_change_pct", "citibike_change_pct",
                  "subway_change_pct", "speed_change_mph"]].dropna(subset=["crash_change_pct"]),
             "q8", note="NTAs inside the zone or within 2 km; speed change is the area-level value from Q4.")
