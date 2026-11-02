"""Step 2b: turn the raw downloads into one processed table per domain question.

Run after fetch_data.py (and process_citibike.py for Q6):
    python scripts/process_data.py
Writes CSVs to data/processed/.
"""
import json

import pandas as pd
from shapely.geometry import Point, shape
from shapely.prepared import prep

from common import PROCESSED, RAW, TOLL_START, area_classifier, label_time

# Approximate Manhattan-side location of each MTA detection group (for the entry-point map).
ENTRY_POINTS = {
    "East 60th St": (40.7625, -73.9640),
    "West 60th St": (40.7700, -73.9850),
    "FDR Drive at 60th St": (40.7590, -73.9580),
    "West Side Highway at 60th St": (40.7735, -73.9920),
    "Queens Midtown Tunnel": (40.7440, -73.9710),
    "Queensboro Bridge": (40.7590, -73.9620),
    "Lincoln Tunnel": (40.7600, -74.0020),
    "Holland Tunnel": (40.7260, -74.0100),
    "Williamsburg Bridge": (40.7180, -73.9860),
    "Manhattan Bridge": (40.7140, -73.9930),
    "Brooklyn Bridge": (40.7120, -74.0030),
    "Hugh L. Carey Tunnel": (40.7040, -74.0140),
}


def save(df, name):
    df.to_csv(PROCESSED / name, index=False)
    print(f"  wrote {name} ({len(df):,} rows)")
    return df


def load_entries():
    e = pd.read_csv(RAW / "crz_entries_date_hour_group.csv")
    e["toll_date"] = pd.to_datetime(e.toll_date)
    e["weekday"] = e.toll_date.dt.day_of_week < 5
    e["month"] = e.toll_date.dt.to_period("M").dt.to_timestamp()
    return e


def q1(e):
    """Typical weekday: average entries per hour per entry point."""
    wd = e[e.weekday]
    n_days = wd.toll_date.nunique()
    t = (wd.groupby(["detection_group", "detection_region", "hour_of_day"], as_index=False)
         [["crz_entries", "excluded_roadway_entries"]].sum())
    t["avg_crz_entries"] = (t.crz_entries / n_days).round(1)
    t["avg_excluded_entries"] = (t.excluded_roadway_entries / n_days).round(1)
    t = t.drop(columns=["crz_entries", "excluded_roadway_entries"])
    save(t, "q1_weekday_hourly_by_entry_point.csv")

    daily = t.groupby(["detection_group", "detection_region"], as_index=False).avg_crz_entries.sum()
    daily = daily.rename(columns={"avg_crz_entries": "avg_weekday_crz_entries"}).round({"avg_weekday_crz_entries": 0})
    daily["share_pct"] = (100 * daily.avg_weekday_crz_entries / daily.avg_weekday_crz_entries.sum()).round(1)
    daily["peak_hour"] = daily.detection_group.map(
        t.loc[t.groupby("detection_group").avg_crz_entries.idxmax()].set_index("detection_group").hour_of_day)
    daily["lat"] = daily.detection_group.map(lambda g: ENTRY_POINTS[g][0])
    daily["lon"] = daily.detection_group.map(lambda g: ENTRY_POINTS[g][1])
    save(daily.sort_values("avg_weekday_crz_entries", ascending=False), "q1_entry_point_summary.csv")


def q2():
    """Entries by vehicle class / time period: monthly average per day + same-month YoY."""
    c = pd.read_csv(RAW / "crz_entries_date_class_period.csv")
    c["toll_date"] = pd.to_datetime(c.toll_date)
    c["month"] = c.toll_date.dt.to_period("M").dt.to_timestamp()
    days = c.groupby("month").toll_date.nunique().rename("days")
    m = c.groupby(["month", "vehicle_class", "time_period"], as_index=False).crz_entries.sum()
    m = m.join(days, on="month")
    m["avg_daily_entries"] = (m.crz_entries / m.days).round(0)
    m = m[m.days == m.month.dt.days_in_month]  # keep complete months only
    save(m[["month", "vehicle_class", "time_period", "days", "avg_daily_entries"]],
         "q2_monthly_entries_by_class_period.csv")

    m["year"] = m.month.dt.year
    m["mon"] = m.month.dt.month
    common = sorted(set(m[m.year == 2025].mon) & set(m[m.year == 2026].mon))
    yy = (m[m.mon.isin(common)].groupby(["vehicle_class", "time_period", "year"])
          .avg_daily_entries.mean().unstack("year").reset_index())
    yy.columns.name = None
    yy = yy.rename(columns={2025: "avg_daily_2025", 2026: "avg_daily_2026"})
    yy["pct_change"] = (100 * (yy.avg_daily_2026 / yy.avg_daily_2025 - 1)).round(1)
    yy["months_compared"] = f"{common[0]}-{common[-1]}"
    save(yy.round({"avg_daily_2025": 0, "avg_daily_2026": 0}), "q2_yoy_by_class_period.csv")

    # Pre/post toll baseline: the entries feed only starts on toll day, so use MTA VMT (2024+)
    v = pd.read_csv(RAW / "cbd_vmt_monthly.csv")
    v["date"] = pd.to_datetime(v.date)
    v = v.rename(columns={"area": "area_code"})
    v["area"] = v.area_code.map({"CRZ": "Congestion Relief Zone", "ER": "Excluded roadways (FDR/WSH)"})
    v["post_toll"] = v.date >= TOLL_START.replace(day=1)
    save(v[["date", "area", "daily_vmt_agps", "daily_vmt_cvd", "indexed_average_vmt", "post_toll"]]
         .sort_values(["area", "date"]), "q2_vmt_monthly.csv")


def q3(e):
    """Toll avoidance: share of vehicles at each edge crossing that use the free roadways."""
    edge = e[e.excluded_roadway_entries > 0].detection_group.unique()
    x = e[e.detection_group.isin(edge)]
    m = x.groupby(["month", "detection_group"], as_index=False)[["crz_entries", "excluded_roadway_entries"]].sum()
    m["excluded_share_pct"] = (100 * m.excluded_roadway_entries /
                               (m.crz_entries + m.excluded_roadway_entries)).round(1)
    save(m, "q3_excluded_share_monthly.csv")

    wd = x[x.weekday]
    h = wd.groupby(["detection_group", "hour_of_day"], as_index=False)[["crz_entries", "excluded_roadway_entries"]].sum()
    h["excluded_share_pct"] = (100 * h.excluded_roadway_entries /
                               (h.crz_entries + h.excluded_roadway_entries)).round(1)
    h["toll_period"] = h.hour_of_day.between(5, 20).map({True: "Peak", False: "Overnight"})
    save(h, "q3_excluded_share_by_hour_weekday.csv")


def q4():
    """Taxi/FHV speeds by zone vs. the same calendar month in 2023-2024."""
    s = pd.read_csv(RAW / "cbd_speeds_monthly.csv")
    s["month"] = pd.to_datetime(s.month)
    s["year"], s["mon"] = s.month.dt.year, s.month.dt.month
    # 2020-2022 speeds are inflated by the pandemic, so the baseline is the two years before the toll
    base = (s[s.year.between(2023, 2024)].groupby(["zone", "mon"]).zonal_speed.mean()
            .rename("baseline_2023_24_mph"))
    s = s.join(base, on=["zone", "mon"])
    s["diff_vs_baseline_mph"] = (s.zonal_speed - s.baseline_2023_24_mph).round(2)
    s["pct_vs_baseline"] = (100 * s.diff_vs_baseline_mph / s.baseline_2023_24_mph).round(1)
    s["post_toll"] = s.month >= TOLL_START.replace(day=1)
    save(s.drop(columns=["year", "mon", "post_toll"]).round(2).assign(post_toll=s.post_toll).sort_values(["zone", "month"]), "q4_speeds_monthly.csv")


def load_collisions(classify):
    c = pd.read_csv(RAW / "collisions_2023on.csv", low_memory=False)
    n0 = len(c)
    c = c.dropna(subset=["latitude", "longitude"])
    c = c[c.latitude.between(40.4, 41.0) & c.longitude.between(-74.3, -73.6)]
    print(f"  collisions: kept {len(c):,}/{n0:,} with valid coordinates")
    key = c.longitude.round(4).astype(str) + "," + c.latitude.round(4).astype(str)
    lut = {k: classify(*map(float, k.split(","))) for k in key.unique()}
    c["area"] = key.map(lut)
    c["crash_date"] = pd.to_datetime(c.crash_date)
    c["month"] = c.crash_date.dt.to_period("M").dt.to_timestamp()
    return c


def q5_q7(c):
    """Crashes and injuries per month by area (CRZ / Adjacent / Rest of NYC)."""
    inj = ["number_of_persons_injured", "number_of_persons_killed",
           "number_of_pedestrians_injured", "number_of_cyclist_injured", "number_of_motorist_injured"]
    m = c.groupby(["month", "area"]).agg(crashes=("collision_id", "size"),
                                          **{k.replace("number_of_", ""): (k, "sum") for k in inj}).reset_index()
    last_full = c.crash_date.max().to_period("M").to_timestamp() - pd.offsets.MonthBegin(1)
    m = m[m.month <= last_full]
    save(m, "q5_q7_collisions_monthly_by_area.csv")

    # Same calendar window each year (Jan .. last full month) so seasons line up
    m["year"], m["mon"] = m.month.dt.year, m.month.dt.month
    win = m[m.mon <= last_full.month]
    y = win.groupby(["area", "year"])[["crashes", "persons_injured", "persons_killed",
                                       "pedestrians_injured", "cyclist_injured"]].sum().reset_index()
    for col in ["crashes", "persons_injured"]:
        y[f"{col}_pct_vs_2024"] = y.apply(
            lambda r: round(100 * (r[col] / y[(y.area == r.area) & (y.year == 2024)][col].iloc[0] - 1), 1), axis=1)
    y["window"] = f"Jan-{last_full.strftime('%b')}"
    save(y, "q5_q7_collisions_yoy_by_area.csv")


def nta_lookup():
    feats = json.loads((RAW / "nta2020.geojson").read_text())["features"]
    polys = [(prep(shape(f["geometry"])), f["properties"]["ntaname"], f["properties"]["boroname"]) for f in feats]

    def find(lon, lat):
        p = Point(lon, lat)
        for poly, name, boro in polys:
            if poly.contains(p):
                return name, boro
        return None, None
    return find


def q6(classify):
    """Transit into the zone: subway station ridership by area, subway OD origins, Citi Bike."""
    find = nta_lookup()
    sub = pd.concat([pd.read_csv(RAW / "subway_monthly_2024.csv"),
                     pd.read_csv(RAW / "subway_monthly_2025on.csv")])
    sub["month"] = pd.to_datetime(sub.month)
    st = sub.groupby("station_complex_id")[["longitude", "latitude"]].first()
    st["area"] = [classify(lo, la) for lo, la in zip(st.longitude, st.latitude)]
    sub["area"] = sub.station_complex_id.map(st.area)
    m = sub.groupby(["month", "area"], as_index=False).ridership.sum()
    m = m[m.month < sub.month.max()]  # drop partial last month
    save(m, "q6_subway_monthly_by_area.csv")

    # Subway OD: where do weekday riders into the CRZ come from? (Oct 2024 vs Oct 2025)
    od = []
    for yr in (2024, 2025):
        d = pd.read_csv(RAW / f"od_into_crz_oct{yr}.csv")
        d["year"] = yr
        od.append(d)
    od = pd.concat(od)
    od["riders"] = od.riders / 5  # summed over Mon..Fri averages -> average weekday
    g = od.groupby(["origin_station_complex_id", "origin_station_complex_name",
                    "origin_latitude", "origin_longitude", "year"], as_index=False).riders.sum()
    g[["nta", "borough"]] = [find(lo, la) for lo, la in zip(g.origin_longitude, g.origin_latitude)]
    by_nta = g.groupby(["nta", "borough", "year"]).riders.sum().unstack("year").reset_index()
    by_nta.columns.name = None
    by_nta = by_nta.rename(columns={2024: "avg_weekday_riders_oct2024", 2025: "avg_weekday_riders_oct2025"})
    by_nta["change"] = by_nta.avg_weekday_riders_oct2025 - by_nta.avg_weekday_riders_oct2024
    by_nta["pct_change"] = 100 * by_nta.change / by_nta.avg_weekday_riders_oct2024
    save(by_nta.round(1).sort_values("avg_weekday_riders_oct2025", ascending=False),
         "q6_subway_od_into_crz_by_neighborhood.csv")

    # Citi Bike trips ending in the CRZ, by start neighborhood (Feb 2024 vs Feb 2025)
    cb = []
    for mth in ("202402", "202502"):
        p = RAW / f"citibike_into_crz_{mth}.csv"
        if p.exists():
            cb.append(pd.read_csv(p, dtype={"month": str}))
    if len(cb) == 2:
        cb = pd.concat(cb)
        stn = cb.groupby("start_station_name")[["start_lng", "start_lat"]].median()
        nta = {s: find(lo, la) for s, (lo, la) in stn.iterrows()}
        cb["nta"] = cb.start_station_name.map(lambda s: nta[s][0])
        cb["borough"] = cb.start_station_name.map(lambda s: nta[s][1])
        t = cb.groupby(["start_area", "nta", "borough", "month"]).trips.sum().unstack("month").reset_index()
        t.columns.name = None
        t = t.rename(columns={"202402": "trips_feb2024", "202502": "trips_feb2025"}).fillna(0)
        t["pct_change"] = (100 * (t.trips_feb2025 / t.trips_feb2024.where(t.trips_feb2024 > 0) - 1)).round(1)
        save(t.sort_values("trips_feb2025", ascending=False), "q6_citibike_into_crz_by_neighborhood.csv")
        a = cb.groupby(["start_area", "month"]).trips.sum().unstack("month").reset_index()
        a.columns.name = None
        a = a.rename(columns={"202402": "trips_feb2024", "202502": "trips_feb2025"})
        a["pct_change"] = (100 * (a.trips_feb2025 / a.trips_feb2024 - 1)).round(1)
        save(a, "q6_citibike_into_crz_by_start_area.csv")


def q8():
    """Area scorecard combining the per-question results (2025 vs 2024, same months)."""
    rows = []
    s = pd.read_csv(PROCESSED / "q4_speeds_monthly.csv", parse_dates=["month"])
    zmap = {"CBD": "CRZ", "CBD Adjacent": "Adjacent", "Greater NYC": "Rest of NYC"}
    s["year"], s["mon"] = s.month.dt.year, s.month.dt.month
    months = sorted(s[s.year == 2025].mon.unique())
    for z, a in zmap.items():
        v = s[(s.zone == z) & s.mon.isin(months)].groupby("year").zonal_speed.mean()
        rows.append({"area": a, "metric": "Taxi/FHV speed (mph)", "window": f"months {months[0]}-{months[-1]}",
                     "value_2024": round(v[2024], 2), "value_2025": round(v[2025], 2)})
    c = pd.read_csv(PROCESSED / "q5_q7_collisions_yoy_by_area.csv")
    for a in zmap.values():
        for col, label in [("crashes", "Crashes"), ("persons_injured", "People injured")]:
            r = c[c.area == a].set_index("year")[col]
            rows.append({"area": a, "metric": label, "window": c.window.iloc[0],
                         "value_2024": r[2024], "value_2025": r[2025]})
    sub = pd.read_csv(PROCESSED / "q6_subway_monthly_by_area.csv", parse_dates=["month"])
    sub["year"], sub["mon"] = sub.month.dt.year, sub.month.dt.month
    for a in zmap.values():
        r = sub[sub.area == a].groupby("year").ridership.sum()
        rows.append({"area": a, "metric": "Subway entries (station taps)", "window": "Jan-Dec",
                     "value_2024": r[2024], "value_2025": r[2025]})
    sc = pd.DataFrame(rows)
    sc["pct_change"] = (100 * (sc.value_2025 / sc.value_2024 - 1)).round(1)
    save(sc, "q8_area_scorecard.csv")


def main():
    classify = area_classifier()
    e = load_entries()
    print("Q1"); q1(e)
    print("Q2"); q2()
    print("Q3"); q3(e)
    print("Q4"); q4()
    print("Q5/Q7"); q5_q7(load_collisions(classify))
    print("Q6"); q6(classify)
    print("Q8"); q8()


if __name__ == "__main__":
    main()
