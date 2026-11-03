"""Q5 + Q7: NYPD Motor Vehicle Collisions - Crashes (NYC Open Data h9gi-nx95).

Outputs
  data/processed/collisions_labeled.csv   one row per crash with area + NTA (input for Q8)
  data/processed/q7_monthly_by_area.csv   monthly crashes/injuries/deaths per area, indexed to 2024
  data/processed/q5_nta_crash_change.csv  per-NTA 2025 vs 2024 change, inside + adjacent areas
"""
import pandas as pd

from common import NYC, PROC, join_nta, label_area, log_gaps, save, soql, to_num, valid_nyc_coords, write_sample

DS = "h9gi-nx95"
START = "2023-01-01T00:00:00"

print("Downloading crashes since 2023 (about 8 pages)")
df = soql(NYC, DS, {
    "$select": "collision_id, crash_date, crash_time, latitude, longitude, "
               "number_of_persons_injured, number_of_persons_killed",
    "$where": f"crash_date >= '{START}'",
    "$order": "collision_id",
})
n_all = len(df)
df = to_num(df, "number_of_persons_injured", "number_of_persons_killed")
ok = valid_nyc_coords(df, "longitude", "latitude")
print(f"  dropped {int((~ok).sum()):,} of {n_all:,} crashes with missing/invalid coordinates")
dropped = df[~ok].assign(ym=pd.to_datetime(df["crash_date"]).dt.strftime("%Y-%m")).groupby("ym").size()
dropped.rename("crashes_without_coords").to_csv(PROC / "collisions_dropped_by_month.csv")
df = df[ok].copy()

df["crash_date"] = pd.to_datetime(df["crash_date"])
log_gaps("collisions", df["crash_date"], "D")
df["area"] = label_area(df["longitude"], df["latitude"])
df = join_nta(df, "longitude", "latitude")
df["year_month"] = df["crash_date"].dt.to_period("M").dt.to_timestamp()
save(df.drop(columns=["crash_time"]), "collisions_labeled")

# the latest month is often incomplete (reports lag), drop it
last_full = df["year_month"].max() - pd.DateOffset(months=1)
df = df[df["year_month"] <= last_full]

# ----------------------------------------------------------------- Q7
m = (df.groupby(["year_month", "area"])
       .agg(crashes=("collision_id", "count"),
            persons_injured=("number_of_persons_injured", "sum"),
            persons_killed=("number_of_persons_killed", "sum"))
       .reset_index())
base = m[m["year_month"].dt.year == 2024][["year_month", "area", "crashes"]].copy()
base["month"] = base["year_month"].dt.month
base = base.drop(columns="year_month").rename(columns={"crashes": "crashes_2024"})
m["month"] = m["year_month"].dt.month
m = m.merge(base, on=["month", "area"], how="left").drop(columns="month")
m["crash_index_2024_100"] = 100 * m["crashes"] / m["crashes_2024"]
m = m.drop(columns="crashes_2024")
m["year_month"] = m["year_month"].dt.strftime("%Y-%m")
m = m.sort_values(["year_month", "area"])
save(m, "q7_monthly_by_area")
write_sample(m[m["year_month"] >= "2025-01"], "q7", note="Index: same calendar month of 2024 = 100.")

# ----------------------------------------------------------------- Q5
months_2025 = sorted(df.loc[df["year_month"].dt.year == 2025, "year_month"].dt.month.unique())
sub = df[df["year_month"].dt.month.isin(months_2025) & df["year_month"].dt.year.isin([2024, 2025])]
sub = sub[sub["nta_name"].notna()].copy()
# each NTA gets the area label most of its crashes fall in
nta_area = sub.groupby("nta_name")["area"].agg(lambda s: s.mode().iloc[0])
sub["area"] = sub["nta_name"].map(nta_area)
sub = sub[sub["area"].isin(["inside", "adjacent"])]
g = (sub.assign(year=sub["year_month"].dt.year)
        .groupby(["nta_name", "borough", "area", "year"])
        .agg(crashes=("collision_id", "count"), injured=("number_of_persons_injured", "sum"))
        .unstack("year"))
g.columns = [f"{a}_{b}" for a, b in g.columns]
g = g.reset_index().fillna(0)
g["crash_change_pct"] = 100 * (g["crashes_2025"] / g["crashes_2024"] - 1)
g = g[["nta_name", "borough", "area", "crashes_2024", "crashes_2025", "crash_change_pct",
       "injured_2024", "injured_2025"]].sort_values("crash_change_pct", ascending=False)
save(g, "q5_nta_crash_change")
write_sample(g[g["area"] == "adjacent"], "q5",
             note=f"Same months in both years (months {months_2025[0]}-{months_2025[-1]}); "
                  "NTAs whose crashes fall in the zone or the 2 km ring.")
