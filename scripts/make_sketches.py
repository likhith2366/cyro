"""Step 3: Vega-Lite sketches for each domain question.

Run after process_data.py:
    python scripts/make_sketches.py
Writes sketches/<name>.vl.json (open in https://vega.github.io/editor), a PNG of each,
and sketches/index.html, which renders all of them interactively with vega-embed.
"""
import json

import pandas as pd
import vl_convert as vlc
from shapely.geometry import mapping, shape

from common import PROCESSED, RAW, SKETCHES

TOLL_DAY = "2025-01-05"
AREA_COLORS = {"domain": ["CRZ", "Adjacent", "Rest of NYC"], "range": ["#c0392b", "#e69f00", "#7f8c8d"]}
W = 560


def rows(name, **parse):
    df = pd.read_csv(PROCESSED / name)
    for c in parse.get("dates", []):
        df[c] = pd.to_datetime(df[c]).dt.strftime("%Y-%m-%d")
    return json.loads(df.to_json(orient="records"))


def crz_geo():
    g = json.loads((RAW / "crz_geofence.geojson").read_text())
    return {"type": "Feature", "properties": {"name": "Congestion Relief Zone"}, "geometry": g}


def nta_geo(keep):
    """Manhattan/Brooklyn/Queens/Bronx NTAs, simplified so the spec stays small."""
    feats = json.loads((RAW / "nta2020.geojson").read_text())["features"]
    out = []
    for f in feats:
        geom = shape(f["geometry"]).simplify(0.0008)
        out.append({"type": "Feature", "properties": {"nta": f["properties"]["ntaname"],
                                                      "borough": f["properties"]["boroname"]},
                    "geometry": mapping(geom)})
    return [f for f in out if f["properties"]["borough"] in keep]


def toll_rule():
    return {"data": {"values": [{"d": TOLL_DAY}]},
            "mark": {"type": "rule", "strokeDash": [4, 3], "color": "black"},
            "encoding": {"x": {"field": "d", "type": "temporal"}}}


def toll_label():
    return {"data": {"values": [{"d": TOLL_DAY}]},
            "mark": {"type": "text", "align": "right", "dx": -4, "y": 8, "fontSize": 10},
            "encoding": {"x": {"field": "d", "type": "temporal"}, "text": {"value": "Toll starts Jan 5, 2025"}}}


# --- Q1 -----------------------------------------------------------------------
def q1():
    hourly = rows("q1_weekday_hourly_by_entry_point.csv")
    summary = rows("q1_entry_point_summary.csv")
    order = [r["detection_group"] for r in summary]
    pick = {"name": "entry", "select": {"type": "point", "fields": ["detection_group"]}}
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": {"text": "Q1. When and where do vehicles enter the zone on a typical weekday?",
                  "subtitle": "Average weekday tolled entries, Jan 2025 - Oct 2026. Click an entry point (map or bars) to highlight it."},
        "vconcat": [{
            "hconcat": [{
                "title": "Entry points (circle area = avg weekday entries)",
                "width": 300, "height": 330,
                "projection": {"type": "mercator"},
                "layer": [
                    {"data": {"values": [crz_geo()]}, "mark": {"type": "geoshape", "fill": "#fdecea", "stroke": "#c0392b"}},
                    {"data": {"values": summary}, "params": [pick],
                     "mark": {"type": "circle", "stroke": "black", "strokeWidth": 0.5},
                     "encoding": {
                         "longitude": {"field": "lon", "type": "quantitative"},
                         "latitude": {"field": "lat", "type": "quantitative"},
                         "size": {"field": "avg_weekday_crz_entries", "type": "quantitative", "title": "Avg weekday entries",
                                  "scale": {"range": [40, 1200]}},
                         "color": {"field": "detection_region", "type": "nominal", "title": "Region"},
                         "opacity": {"condition": {"param": "entry", "value": 1}, "value": 0.25},
                         "tooltip": [{"field": "detection_group", "title": "Entry point"},
                                     {"field": "avg_weekday_crz_entries", "format": ",.0f", "title": "Avg weekday entries"},
                                     {"field": "share_pct", "title": "Share of all entries (%)"},
                                     {"field": "peak_hour", "title": "Busiest hour"}]}}]
            }, {
                "title": "Avg weekday entries by entry point",
                "width": 260, "height": 330,
                "data": {"values": summary}, "params": [dict(pick, name="entry_bar")],
                "mark": "bar",
                "encoding": {
                    "y": {"field": "detection_group", "type": "nominal", "sort": order, "title": None},
                    "x": {"field": "avg_weekday_crz_entries", "type": "quantitative", "title": "Avg weekday entries"},
                    "color": {"field": "detection_region", "type": "nominal", "legend": None},
                    "opacity": {"condition": {"param": "entry", "value": 1}, "value": 0.25}}
            }]
        }, {
            "title": "Hour-of-day profile (heatmap: rows = entry point, columns = hour)",
            "width": W + 60, "height": 300,
            "data": {"values": hourly},
            "mark": "rect",
            "encoding": {
                "x": {"field": "hour_of_day", "type": "ordinal", "title": "Hour of day (0 = midnight)"},
                "y": {"field": "detection_group", "type": "nominal", "sort": order, "title": None},
                "color": {"field": "avg_crz_entries", "type": "quantitative", "title": "Avg entries / hour",
                          "scale": {"scheme": "orangered"}},
                "tooltip": [{"field": "detection_group"}, {"field": "hour_of_day"},
                            {"field": "avg_crz_entries", "format": ",.0f"}]}
        }]
    }


# --- Q2 -----------------------------------------------------------------------
def q2():
    m = rows("q2_monthly_entries_by_class_period.csv", dates=["month"])
    yy = rows("q2_yoy_by_class_period.csv")
    vmt = rows("q2_vmt_monthly.csv", dates=["date"])
    cls = {"name": "cls", "select": {"type": "point", "fields": ["vehicle_class"]}, "bind": "legend"}
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": {"text": "Q2. How have entries changed since the toll started, by vehicle class and time period?",
                  "subtitle": "Click a vehicle class in the legend to isolate it. Bottom: vehicle-miles in the zone, the only series with a 2024 (pre-toll) baseline."},
        "vconcat": [{
            "hconcat": [{
                "title": "Avg daily entries per month",
                "width": 380, "height": 220, "data": {"values": m},
                "params": [cls],
                "mark": {"type": "line", "point": True},
                "encoding": {
                    "x": {"field": "month", "type": "temporal", "title": "Month"},
                    "y": {"field": "avg_daily_entries", "type": "quantitative", "title": "Avg daily entries", "scale": {"type": "log"}},
                    "color": {"field": "vehicle_class", "type": "nominal", "title": "Vehicle class"},
                    "strokeDash": {"field": "time_period", "type": "nominal", "title": "Time period"},
                    "opacity": {"condition": {"param": "cls", "value": 1}, "value": 0.1},
                    "tooltip": [{"field": "month", "type": "temporal", "format": "%b %Y"}, {"field": "vehicle_class"},
                                {"field": "time_period"}, {"field": "avg_daily_entries", "format": ",.0f"}]}
            }, {
                "title": "Same months, 2026 vs 2025 (% change)",
                "width": 200, "height": 220, "data": {"values": yy},
                "mark": "bar",
                "encoding": {
                    "y": {"field": "vehicle_class", "type": "nominal", "title": None},
                    "yOffset": {"field": "time_period"},
                    "x": {"field": "pct_change", "type": "quantitative", "title": "% change"},
                    "color": {"field": "time_period", "type": "nominal", "title": "Time period",
                              "scale": {"range": ["#4c78a8", "#f58518"]}},
                    "tooltip": [{"field": "vehicle_class"}, {"field": "time_period"},
                                {"field": "avg_daily_2025", "format": ",.0f"}, {"field": "avg_daily_2026", "format": ",.0f"},
                                {"field": "pct_change"}, {"field": "months_compared"}]}
            }]
        }, {
            "title": "Vehicle-miles travelled per day (MTA estimate), before vs after the toll",
            "width": W + 120, "height": 170,
            "layer": [{
                "data": {"values": vmt},
                "mark": {"type": "line", "point": True},
                "encoding": {
                    "x": {"field": "date", "type": "temporal", "title": "Month"},
                    "y": {"field": "daily_vmt_agps", "type": "quantitative", "title": "Daily VMT"},
                    "color": {"field": "area", "type": "nominal", "title": "Area"},
                    "tooltip": [{"field": "date", "type": "temporal", "format": "%b %Y"}, {"field": "area"},
                                {"field": "daily_vmt_agps", "format": ",.0f"}]}
            }, toll_rule(), toll_label()]
        }]
    }


# --- Q3 -----------------------------------------------------------------------
def q3():
    m = rows("q3_excluded_share_monthly.csv", dates=["month"])
    h = rows("q3_excluded_share_by_hour_weekday.csv")
    sel = {"name": "grp", "select": {"type": "point", "fields": ["detection_group"]}, "bind": "legend"}
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": {"text": "Q3. Are drivers using the toll-free FDR Drive and West Side Highway instead?",
                  "subtitle": "Share of vehicles at each edge crossing that stay on the excluded (untolled) roadway. Click legend to isolate."},
        "hconcat": [{
            "title": "Excluded-roadway share by month",
            "width": 340, "height": 240, "data": {"values": m}, "params": [sel],
            "mark": {"type": "line", "point": True},
            "encoding": {
                "x": {"field": "month", "type": "temporal", "title": "Month"},
                "y": {"field": "excluded_share_pct", "type": "quantitative", "title": "% of vehicles on excluded roadway"},
                "color": {"field": "detection_group", "type": "nominal", "title": "Crossing"},
                "opacity": {"condition": {"param": "grp", "value": 1}, "value": 0.15},
                "tooltip": [{"field": "detection_group"}, {"field": "month", "type": "temporal", "format": "%b %Y"},
                            {"field": "excluded_share_pct"}, {"field": "excluded_roadway_entries", "format": ","}]}
        }, {
            "title": "Weekday share by hour (shaded = peak toll hours)",
            "width": 300, "height": 240,
            "layer": [
                {"data": {"values": [{"a": 5, "b": 21}]}, "mark": {"type": "rect", "color": "#eee"},
                 "encoding": {"x": {"field": "a", "type": "quantitative"}, "x2": {"field": "b"}}},
                {"data": {"values": h}, "mark": "line",
                 "encoding": {
                     "x": {"field": "hour_of_day", "type": "quantitative", "title": "Hour of day", "scale": {"domain": [0, 23]}},
                     "y": {"field": "excluded_share_pct", "type": "quantitative", "title": "% on excluded roadway"},
                     "color": {"field": "detection_group", "type": "nominal", "legend": None}}}]
        }]
    }


# --- Q4 -----------------------------------------------------------------------
def q4():
    s = rows("q4_speeds_monthly.csv", dates=["month"])
    zone = {"name": "zone", "select": {"type": "point", "fields": ["zone"]}, "bind": "legend"}
    brush = {"name": "span", "select": {"type": "interval", "encodings": ["x"]}}
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": {"text": "Q4. Has traffic inside the zone become faster than in 2019-2024, and than the rest of the city?",
                  "subtitle": "MTA taxi/for-hire-vehicle speeds (monthly). Drag on the top chart to zoom the bottom one."},
        "vconcat": [{
            "width": W + 120, "height": 200,
            "layer": [{
                "data": {"values": s}, "params": [zone, brush],
                "mark": "line",
                "encoding": {
                    "x": {"field": "month", "type": "temporal", "title": "Month", "axis": {"format": "%b %Y"}},
                    "y": {"field": "zonal_speed", "type": "quantitative", "title": "Average speed (mph)", "scale": {"zero": False}},
                    "color": {"field": "zone", "type": "nominal", "title": "Area",
                              "scale": {"domain": ["CBD", "CBD Adjacent", "Greater NYC"], "range": AREA_COLORS["range"]}},
                    "opacity": {"condition": {"param": "zone", "value": 1}, "value": 0.15},
                    "tooltip": [{"field": "zone"}, {"field": "month", "type": "temporal", "format": "%b %Y"},
                                {"field": "zonal_speed"}]}
            }, toll_rule(), toll_label()]
        }, {
            "title": "Difference from the same calendar month's 2023-2024 average (mph), 2023 onward",
            "width": W + 120, "height": 160,
            "layer": [{
                "data": {"values": s},
                "transform": [{"filter": "year(datum.month) >= 2023"}, {"filter": {"param": "zone"}}],
                "mark": {"type": "line", "point": True},
                "encoding": {
                    "x": {"field": "month", "type": "temporal", "title": "Month", "scale": {"domain": {"param": "span"}},
                          "axis": {"format": "%b %Y"}},
                    "y": {"field": "diff_vs_baseline_mph", "type": "quantitative", "title": "mph vs baseline"},
                    "color": {"field": "zone", "type": "nominal", "legend": None,
                              "scale": {"domain": ["CBD", "CBD Adjacent", "Greater NYC"], "range": AREA_COLORS["range"]}},
                    "tooltip": [{"field": "zone"}, {"field": "month", "type": "temporal", "format": "%b %Y"},
                                {"field": "zonal_speed"}, {"field": "baseline_2023_24_mph"},
                                {"field": "diff_vs_baseline_mph"}, {"field": "pct_vs_baseline"}]}
            }, {"data": {"values": [{"y": 0}]}, "mark": {"type": "rule", "color": "black"},
                "encoding": {"y": {"field": "y", "type": "quantitative"}}}, toll_rule()]
        }]
    }


# --- Q5 / Q7 ------------------------------------------------------------------
def q5_q7():
    m = rows("q5_q7_collisions_monthly_by_area.csv", dates=["month"])
    y = rows("q5_q7_collisions_yoy_by_area.csv")
    metric = {"name": "metric", "value": "crashes",
              "bind": {"input": "select", "options": ["crashes", "persons_injured", "pedestrians_injured", "cyclist_injured"],
                       "name": "Measure: "}}
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": {"text": "Q5 + Q7. Did crashes fall inside the zone, and rise just outside it?",
                  "subtitle": "NYPD crash reports, assigned to CRZ / within 1.5 km of it (Adjacent) / Rest of NYC. Index: each area's 2024 monthly average = 100."},
        "params": [metric],
        "vconcat": [{
            "width": W + 120, "height": 220,
            "layer": [{
                "data": {"values": m},
                "transform": [
                    {"calculate": "datum[metric]", "as": "value"},
                    {"calculate": "year(datum.month) == 2024 ? datum.value : null", "as": "v2024"},
                    {"joinaggregate": [{"op": "mean", "field": "v2024", "as": "base"}], "groupby": ["area"]},
                    {"calculate": "100 * datum.value / datum.base", "as": "index"}],
                "mark": {"type": "line", "point": True},
                "encoding": {
                    "x": {"field": "month", "type": "temporal", "title": "Month"},
                    "y": {"field": "index", "type": "quantitative", "title": "Index (2024 avg = 100)", "scale": {"zero": False}},
                    "color": {"field": "area", "type": "nominal", "title": "Area", "scale": AREA_COLORS},
                    "tooltip": [{"field": "area"}, {"field": "month", "type": "temporal", "format": "%b %Y"},
                                {"field": "value", "title": "count", "format": ","}, {"field": "index", "format": ".0f"}]}
            }, toll_rule(), toll_label()]
        }, {
            "title": "Same months each year: total crashes and injuries, % change vs 2024",
            "width": 300, "height": 140, "data": {"values": y},
            "transform": [{"filter": "datum.year > 2024"},
                          {"fold": ["crashes_pct_vs_2024", "persons_injured_pct_vs_2024"], "as": ["measure", "pct"]},
                          {"calculate": "datum.measure == 'crashes_pct_vs_2024' ? 'Crashes' : 'People injured'", "as": "measure"}],
            "mark": "bar",
            "encoding": {
                "x": {"field": "area", "type": "nominal", "title": None, "sort": AREA_COLORS["domain"], "axis": {"labelAngle": 0}},
                "xOffset": {"field": "measure"},
                "column": {"field": "year", "type": "ordinal", "title": None},
                "y": {"field": "pct", "type": "quantitative", "title": "% vs 2024"},
                "color": {"field": "measure", "type": "nominal", "title": None,
                          "scale": {"range": ["#4c78a8", "#e45756"]}},
                "tooltip": [{"field": "area"}, {"field": "year"}, {"field": "measure"}, {"field": "pct"}, {"field": "window"}]}
        }]
    }


# --- Q6 -----------------------------------------------------------------------
def q6():
    sub = rows("q6_subway_monthly_by_area.csv", dates=["month"])
    od = rows("q6_subway_od_into_crz_by_neighborhood.csv")
    cb = rows("q6_citibike_into_crz_by_start_area.csv")
    boros = ["Manhattan", "Brooklyn", "Queens", "Bronx"]
    geo = nta_geo(boros)
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": {"text": "Q6. Did more people take the subway or Citi Bike into the zone, and from where?",
                  "subtitle": "Map: % change in average weekday subway trips into the CRZ by origin neighbourhood, Oct 2025 vs Oct 2024 (grey = no origin data / inside zone). Hover for values."},
        "vconcat": [{
            "hconcat": [{
                "width": 360, "height": 420,
                "projection": {"type": "mercator"},
                "layer": [{
                    "data": {"values": geo},
                    "mark": {"type": "geoshape", "fill": "#e8e8e8", "stroke": "white", "strokeWidth": 0.3}
                }, {
                    "data": {"values": geo},
                    "transform": [{"lookup": "properties.nta",
                                   "from": {"data": {"values": od}, "key": "nta",
                                            "fields": ["pct_change", "change", "avg_weekday_riders_oct2024", "avg_weekday_riders_oct2025"]}},
                                  {"filter": "isValid(datum.pct_change)"}],
                    "mark": {"type": "geoshape", "stroke": "white", "strokeWidth": 0.3},
                    "encoding": {
                        "color": {"field": "pct_change", "type": "quantitative", "title": "% change",
                                  "scale": {"scheme": "redblue", "domainMid": 0, "domain": [-30, 30], "clamp": True}},
                        "tooltip": [{"field": "properties.nta", "title": "Neighbourhood"},
                                    {"field": "avg_weekday_riders_oct2024", "format": ",.0f", "title": "Oct 2024"},
                                    {"field": "avg_weekday_riders_oct2025", "format": ",.0f", "title": "Oct 2025"},
                                    {"field": "pct_change", "format": ".1f", "title": "% change"}]}},
                    {"data": {"values": [crz_geo()]}, "mark": {"type": "geoshape", "fill": None, "stroke": "black", "strokeWidth": 1.5}}]
            }, {
                "vconcat": [{
                    "title": "Top 15 origin neighbourhoods (avg weekday riders into CRZ)",
                    "width": 220, "height": 260, "data": {"values": od},
                    "transform": [{"window": [{"op": "rank", "as": "rank"}],
                                   "sort": [{"field": "avg_weekday_riders_oct2025", "order": "descending"}]},
                                  {"filter": "datum.rank <= 15"},
                                  {"fold": ["avg_weekday_riders_oct2024", "avg_weekday_riders_oct2025"], "as": ["yr", "riders"]},
                                  {"calculate": "'Oct ' + slice(datum.yr, -4)", "as": "yr"}],
                    "mark": "bar",
                    "encoding": {
                        "y": {"field": "nta", "type": "nominal", "sort": "-x", "title": None},
                        "yOffset": {"field": "yr"},
                        "x": {"field": "riders", "type": "quantitative", "title": "Avg weekday riders"},
                        "color": {"field": "yr", "type": "nominal", "title": None,
                                  "scale": {"range": ["#bbbbbb", "#4c78a8"]}}}
                }, {
                    "title": "Citi Bike trips ending in CRZ, by start area (Feb)",
                    "width": 220, "height": 90, "data": {"values": cb},
                    "transform": [{"fold": ["trips_feb2024", "trips_feb2025"], "as": ["month", "trips"]},
                                  {"calculate": "'Feb ' + slice(datum.month, -4)", "as": "month"}],
                    "mark": "bar",
                    "encoding": {
                        "y": {"field": "start_area", "type": "nominal", "title": None, "sort": AREA_COLORS["domain"]},
                        "yOffset": {"field": "month"},
                        "x": {"field": "trips", "type": "quantitative", "title": "Trips"},
                        "color": {"field": "month", "type": "nominal", "title": None,
                                  "scale": {"range": ["#bbbbbb", "#54a24b"]}},
                        "tooltip": [{"field": "start_area"}, {"field": "month"}, {"field": "trips", "format": ","},
                                    {"field": "pct_change"}]}
                }]
            }]
        }, {
            "title": "Subway station entries per month, by where the station is",
            "width": W + 160, "height": 160,
            "layer": [{
                "data": {"values": sub}, "mark": {"type": "line", "point": True},
                "encoding": {
                    "x": {"field": "month", "type": "temporal", "title": "Month"},
                    "y": {"field": "ridership", "type": "quantitative", "title": "Monthly entries"},
                    "color": {"field": "area", "type": "nominal", "title": "Station area", "scale": AREA_COLORS},
                    "tooltip": [{"field": "area"}, {"field": "month", "type": "temporal", "format": "%b %Y"},
                                {"field": "ridership", "format": ",.0f"}]}
            }, toll_rule(), toll_label()]
        }]
    }


# --- Q8 -----------------------------------------------------------------------
def q8():
    sc = rows("q8_area_scorecard.csv")
    # +1 when the change is good for the area (faster, fewer crashes/injuries, more transit)
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": {"text": "Q8. Who gained and who paid? Area scorecard, 2025 vs 2024",
                  "subtitle": "Each cell = % change for that area and measure. Green = better for the area, purple = worse. Hover for raw values."},
        "data": {"values": sc},
        "transform": [{"calculate": "indexof(['Crashes','People injured'], datum.metric) >= 0 ? -datum.pct_change : datum.pct_change",
                       "as": "benefit"}],
        "width": 360, "height": 200,
        "layer": [{
            "mark": "rect",
            "encoding": {
                "x": {"field": "area", "type": "nominal", "sort": AREA_COLORS["domain"], "title": None, "axis": {"orient": "top"}},
                "y": {"field": "metric", "type": "nominal", "title": None},
                "color": {"field": "benefit", "type": "quantitative", "title": "Better / worse (%)",
                          "scale": {"scheme": "purplegreen", "domainMid": 0, "domain": [-15, 15], "clamp": True}},
                "tooltip": [{"field": "area"}, {"field": "metric"}, {"field": "window"},
                            {"field": "value_2024", "format": ",.2f"}, {"field": "value_2025", "format": ",.2f"},
                            {"field": "pct_change", "title": "% change"}]}
        }, {
            "mark": {"type": "text", "fontSize": 13},
            "encoding": {
                "x": {"field": "area", "type": "nominal", "sort": AREA_COLORS["domain"]},
                "y": {"field": "metric", "type": "nominal"},
                "text": {"field": "pct_change", "type": "quantitative", "format": "+.1f"}}
        }]
    }


SKETCH_LIST = [("q1_entries_when_where", q1), ("q2_entries_change", q2), ("q3_toll_avoidance", q3),
               ("q4_speeds", q4), ("q5_q7_crashes", q5_q7), ("q6_transit_into_zone", q6),
               ("q8_area_scorecard", q8)]


def independent_colors(spec):
    """Give every concatenated view its own colour scale/legend."""
    if isinstance(spec, dict):
        if "hconcat" in spec or "vconcat" in spec:
            spec["resolve"] = {"scale": {"color": "independent"}}
        for v in spec.values():
            independent_colors(v)
    elif isinstance(spec, list):
        for v in spec:
            independent_colors(v)
    return spec


def main():
    specs = {}
    for name, fn in SKETCH_LIST:
        spec = independent_colors(fn())
        specs[name] = spec
        (SKETCHES / f"{name}.vl.json").write_text(json.dumps(spec))
        (SKETCHES / f"{name}.png").write_bytes(vlc.vegalite_to_png(spec, scale=2))
        print(f"  {name}")
    blocks = "\n".join(f'<section><div id="{n}"></div></section>' for n in specs)
    calls = "\n".join(f'vegaEmbed("#{n}", "{n}.vl.json", {{actions: true}});' for n in specs)
    (SKETCHES / "index.html").write_text(f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Congestion Pricing Sketches</title>
<script src="https://cdn.jsdelivr.net/npm/vega@5.30.0"></script>
<script src="https://cdn.jsdelivr.net/npm/vega-lite@5.21.0"></script>
<script src="https://cdn.jsdelivr.net/npm/vega-embed@6.26.0"></script>
<style>body{{font-family:system-ui,sans-serif;margin:24px;background:#fff}} section{{margin-bottom:48px}}</style>
</head><body>
<h1>Congestion Pricing in NYC: Milestone 2 sketches (Vega-Lite)</h1>
<p>Serve this folder (e.g. <code>python -m http.server</code> inside <code>sketches/</code>) and open it in a browser.</p>
{blocks}
<script>{calls}</script>
</body></html>
""")


if __name__ == "__main__":
    main()
