"""Step 1: download (server-side aggregated) raw tables from NY State / NYC Open Data.

Run:  python scripts/fetch_data.py
Everything is cached in data/raw/, so re-running is cheap.
"""
import pandas as pd
import requests

from common import (NYC, RAW, CBD_SPEEDS, CBD_VMT, COLLISIONS, CRZ_ENTRIES, OD_2024, OD_2025,
                    SUBWAY_2024, SUBWAY_2025, crz_polygon, socrata)


def crz_wkt():
    """Simplified zone outline as WKT, for SoQL within_polygon() filters."""
    return crz_polygon().simplify(0.0003).wkt


def main():
    nta = RAW / "nta2020.geojson"
    if not nta.exists():
        print("NYC 2020 Neighborhood Tabulation Areas")
        nta.write_bytes(requests.get(f"{NYC}/9nt8-h7nd.geojson", params={"$limit": 500}, timeout=300).content)

    print("CRZ entries: date x hour x entry point")
    socrata(CRZ_ENTRIES, {
        "$select": "toll_date, hour_of_day, day_of_week, detection_group, detection_region,"
                   "sum(crz_entries) as crz_entries,"
                   "sum(excluded_roadway_entries) as excluded_roadway_entries",
        "$group": "toll_date, hour_of_day, day_of_week, detection_group, detection_region",
    }, cache="crz_entries_date_hour_group.csv")

    print("CRZ entries: date x vehicle class x time period")
    socrata(CRZ_ENTRIES, {
        "$select": "toll_date, vehicle_class, time_period,"
                   "sum(crz_entries) as crz_entries,"
                   "sum(excluded_roadway_entries) as excluded_roadway_entries",
        "$group": "toll_date, vehicle_class, time_period",
    }, cache="crz_entries_date_class_period.csv")

    print("CBD taxi/FHV speeds (monthly) and VMT")
    socrata(CBD_SPEEDS, {}, cache="cbd_speeds_monthly.csv")
    socrata(CBD_VMT, {}, cache="cbd_vmt_monthly.csv")

    print("Collisions 2023-01-01 onward (with coordinates)")
    socrata(COLLISIONS, {
        "$select": "collision_id, crash_date, crash_time, borough, latitude, longitude,"
                   "number_of_persons_injured, number_of_persons_killed,"
                   "number_of_pedestrians_injured, number_of_cyclist_injured,"
                   "number_of_motorist_injured",
        "$where": "crash_date >= '2023-01-01'",
        "$order": "collision_id",
    }, cache="collisions_2023on.csv")

    print("Subway monthly ridership per station (2024 and 2025+), one query per month")
    for url, first, last, name in [
        (SUBWAY_2024, "2024-01", "2024-12", "subway_monthly_2024.csv"),
        (SUBWAY_2025, "2025-01", pd.Timestamp.today().strftime("%Y-%m"), "subway_monthly_2025on.csv"),
    ]:
        if (RAW / name).exists():
            continue
        parts = []
        for m in pd.period_range(first, last, freq="M"):
            parts.append(socrata(url, {
                "$select": "station_complex_id, station_complex, borough, latitude, longitude,"
                           "date_trunc_ym(transit_timestamp) as month, sum(ridership) as ridership",
                "$where": f"transit_timestamp between '{m.start_time:%Y-%m-%d}' and '{m.end_time:%Y-%m-%dT23:59:59}'",
                "$group": "station_complex_id, station_complex, borough, latitude, longitude, month",
            }))
        pd.concat(parts).to_csv(RAW / name, index=False)

    print("Subway OD: weekday trips ending inside the CRZ, by origin station (October)")
    wkt = crz_wkt()
    for url, name in [(OD_2024, "od_into_crz_oct2024.csv"), (OD_2025, "od_into_crz_oct2025.csv")]:
        socrata(url, {
            "$select": "origin_station_complex_id, origin_station_complex_name,"
                       "origin_latitude, origin_longitude, hour_of_day,"
                       "sum(estimated_average_ridership) as riders",
            "$where": f"month = '10' and day_of_week not in ('Saturday', 'Sunday')"
                      f" and within_polygon(destination_point, '{wkt}')"
                      f" and not within_polygon(origin_point, '{wkt}')",
            "$group": "origin_station_complex_id, origin_station_complex_name,"
                      "origin_latitude, origin_longitude, hour_of_day",
        }, cache=name)


if __name__ == "__main__":
    main()
