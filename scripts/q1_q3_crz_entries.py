"""Q1-Q3: MTA Congestion Relief Zone Vehicle Entries (data.ny.gov t6yz-b64h).

Outputs
  data/processed/q1_weekday_profile.csv   avg weekday entries by entry point x hour
  data/processed/q2_weekly_by_class.csv   weekly entries by vehicle class x time period, YoY change
  data/processed/q3_excluded_share.csv    weekly tolled vs excluded-roadway entries by entry point
"""
import pandas as pd

from m2_common import NY, columns, holidays, log_gaps, pick, save, soql, to_num, write_sample

DS = "t6yz-b64h"

cols = columns(NY, DS)
EP = pick(cols, "detection_group")
HOD = pick(cols, "hour_of_day")
DATE = pick(cols, "toll_date")
WEEK = pick(cols, "toll_week")
VC = pick(cols, "vehicle_class")
TP = pick(cols, "time_period")
CRZ = pick(cols, "crz_entries")
EXC = pick(cols, "excluded_roadway_entries")
print("Using columns:", EP, HOD, DATE, WEEK, VC, TP, CRZ, EXC)

# ----------------------------------------------------------------- Q1: weekday profile
print("Q1: entries by date x entry point x hour")
q1 = soql(NY, DS, {
    "$select": f"{DATE} as toll_date, {EP} as entry_point, {HOD} as hour, "
               f"sum({CRZ}) as tolled, sum({EXC}) as excluded",
    "$group": f"{DATE}, {EP}, {HOD}",
    "$order": f"{DATE}, {EP}, {HOD}",
})
q1 = to_num(q1, "tolled", "excluded", "hour")
q1["toll_date"] = pd.to_datetime(q1["toll_date"])
log_gaps("crz_entries", q1["toll_date"], "D")

wk = q1[(q1["toll_date"].dt.dayofweek < 5) & ~q1["toll_date"].isin(holidays())]
n_days = wk["toll_date"].nunique()
prof = (wk.groupby(["entry_point", "hour"], as_index=False)[["tolled", "excluded"]].sum())
prof["avg_weekday_entries"] = prof["tolled"] / n_days
prof["avg_excluded_entries"] = prof["excluded"] / n_days
prof["n_weekdays"] = n_days
prof["hour"] = prof["hour"].astype(int)
order = prof.groupby("entry_point")["avg_weekday_entries"].sum().sort_values(ascending=False).index
prof["entry_point"] = pd.Categorical(prof["entry_point"], categories=order, ordered=True)
prof = prof.sort_values(["entry_point", "hour"])[
    ["entry_point", "hour", "avg_weekday_entries", "avg_excluded_entries", "n_weekdays"]]
save(prof, "q1_weekday_profile")
write_sample(prof, "q1", note=f"Averages over {n_days} non-holiday weekdays since Jan 5, 2025.")

# ----------------------------------------------------------------- Q2: weekly by class
print("Q2: weekly entries by vehicle class x time period")
q2 = soql(NY, DS, {
    "$select": f"{WEEK} as week_start, {VC} as vehicle_class, {TP} as time_period, sum({CRZ}) as entries",
    "$group": f"{WEEK}, {VC}, {TP}",
    "$order": f"{WEEK}, {VC}, {TP}",
})
q2 = to_num(q2, "entries")
q2["week_start"] = pd.to_datetime(q2["week_start"])
# the most recent week is usually partial, so drop it
q2 = q2[q2["week_start"] < q2["week_start"].max()]

prev = q2.copy()
prev["week_start"] = prev["week_start"] + pd.Timedelta(days=364)  # same weekday, one year later
prev = prev.rename(columns={"entries": "entries_same_week_prev_year"})
q2 = q2.merge(prev, on=["week_start", "vehicle_class", "time_period"], how="left")
q2["pct_change"] = (q2["entries"] / q2["entries_same_week_prev_year"] - 1) * 100
q2["week_start"] = q2["week_start"].dt.date
save(q2, "q2_weekly_by_class")
write_sample(q2.dropna(subset=["pct_change"]).head(8) if q2["pct_change"].notna().any() else q2,
             "q2_weekly", note="pct_change is vs. the same week one year earlier (blank for 2025 weeks).")

# ----------------------------------------------------------------- Q3: excluded share
print("Q3: weekly tolled vs excluded entries by entry point")
q3 = soql(NY, DS, {
    "$select": f"{WEEK} as week_start, {EP} as entry_point, "
               f"sum({CRZ}) as tolled_entries, sum({EXC}) as excluded_entries",
    "$group": f"{WEEK}, {EP}",
    "$order": f"{WEEK}, {EP}",
})
q3 = to_num(q3, "tolled_entries", "excluded_entries")
q3["week_start"] = pd.to_datetime(q3["week_start"]).dt.date
total = q3.groupby("week_start", as_index=False)[["tolled_entries", "excluded_entries"]].sum()
total["entry_point"] = "ALL ENTRY POINTS"
q3 = pd.concat([total, q3], ignore_index=True)
q3["excluded_share_pct"] = 100 * q3["excluded_entries"] / (q3["tolled_entries"] + q3["excluded_entries"])
q3 = q3.sort_values(["week_start", "entry_point"])[
    ["week_start", "entry_point", "tolled_entries", "excluded_entries", "excluded_share_pct"]]
save(q3, "q3_excluded_share")
write_sample(q3[q3["excluded_entries"] > 0], "q3", note="Rows with excluded-roadway traffic shown.")
