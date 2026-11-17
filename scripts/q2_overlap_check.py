"""Q2 comparability check: do the Bridges & Tunnels crossings and the CRZ entries agree?

The Q2 before/after view uses MTA Bridges and Tunnels crossings (ebfx-2m7v) because the CRZ
entries feed (t6yz-b64h) only starts on toll day. That substitution is only defensible if the
two sources count the same traffic where their date ranges overlap (2025 onward).

For the two facilities that appear in both feeds -- the Hugh L. Carey and Queens Midtown
tunnels -- this script puts the monthly Manhattan-bound B&T crossings next to the monthly CRZ
entries and reports the ratio and correlation. A ratio that stays near a constant means the
B&T series tracks zone entries at those facilities and can stand in for the missing 2024 level.

Output: data/processed/q2_overlap_check.csv
"""
import pandas as pd

from m2_common import NY, save, soql, to_num, write_sample

# detection_group (CRZ entries) -> facility substring (B&T crossings)
FACILITIES = {"Hugh L. Carey Tunnel": "carey", "Queens Midtown Tunnel": "midtown"}

print("CRZ entries: monthly totals at the two tunnels")
crz = soql(NY, "t6yz-b64h", {
    "$select": "date_trunc_ym(toll_date) as year_month, detection_group, sum(crz_entries) as crz_entries, "
               "sum(excluded_roadway_entries) as excluded_entries",
    "$where": "detection_group in('Hugh L. Carey Tunnel','Queens Midtown Tunnel')",
    "$group": "date_trunc_ym(toll_date), detection_group",
    "$order": "date_trunc_ym(toll_date), detection_group",
})
crz = to_num(crz, "crz_entries", "excluded_entries")
crz["year_month"] = pd.to_datetime(crz["year_month"])

print("B&T crossings: monthly Manhattan-bound totals at the same tunnels")
bt = soql(NY, "ebfx-2m7v", {
    "$select": "date_trunc_ym(transit_timestamp) as year_month, facility, direction, "
               "sum(traffic_count) as crossings",
    "$where": "transit_timestamp >= '2025-01-01T00:00:00'",
    "$group": "date_trunc_ym(transit_timestamp), facility, direction",
    "$order": "date_trunc_ym(transit_timestamp), facility",
})
bt = to_num(bt, "crossings")
bt["year_month"] = pd.to_datetime(bt["year_month"])
bt = bt[bt["direction"].str.lower().str.contains("to manhattan", na=False)]
bt["detection_group"] = bt["facility"].str.lower().apply(
    lambda f: next((k for k, v in FACILITIES.items() if v in f), None))
bt = bt.dropna(subset=["detection_group"])
bt = bt.groupby(["year_month", "detection_group"], as_index=False)["crossings"].sum()

df = crz.merge(bt, on=["year_month", "detection_group"], how="inner")
# January 2025 is partial in the CRZ feed (it starts on the 5th), so it cannot be compared
df = df[df["year_month"] > "2025-01-01"]
# drop the newest month of either feed, which may still be filling in
df = df[df["year_month"] < df["year_month"].max()]

# Two ratios. The first compares B&T crossings with tolled entries only; at the Carey Tunnel that
# overstates B&T, because vehicles leaving the tunnel onto the FDR / West Side Highway are counted
# as crossings but recorded as *excluded-roadway* entries, not tolled ones. The second ratio adds
# those back, which is the like-for-like comparison.
df["all_zone_entries"] = df["crz_entries"] + df["excluded_entries"]
df["bt_per_tolled_entry"] = (df["crossings"] / df["crz_entries"]).round(4)
df["bt_per_zone_entry"] = (df["crossings"] / df["all_zone_entries"]).round(4)

print("\nComparability by facility (overlap period only):")
summary = []
for fac, g in df.groupby("detection_group"):
    r = g["crossings"].corr(g["all_zone_entries"])
    ratio, spread = g["bt_per_zone_entry"].mean(), g["bt_per_zone_entry"].std()
    print(f"  {fac}: {len(g)} months, B&T per zone entry {ratio:.3f} "
          f"(sd {spread:.3f}, {100 * spread / ratio:.1f}% of mean), monthly correlation r = {r:.3f}"
          f"  [tolled entries only: {g['bt_per_tolled_entry'].mean():.3f}]")
    summary.append({"detection_group": fac, "months": len(g),
                    "mean_bt_per_zone_entry": round(ratio, 3),
                    "mean_bt_per_tolled_entry": round(g["bt_per_tolled_entry"].mean(), 3),
                    "sd_ratio": round(spread, 3), "cv_pct": round(100 * spread / ratio, 1),
                    "correlation_r": round(r, 3)})

df["year_month"] = df["year_month"].dt.strftime("%Y-%m")
save(df, "q2_overlap_check")
write_sample(df, "q2_overlap_check",
             note="Monthly Manhattan-bound B&T crossings beside CRZ tolled entries at the same "
                  "two tunnels, over the period both feeds cover.")
save(pd.DataFrame(summary), "q2_overlap_summary")
