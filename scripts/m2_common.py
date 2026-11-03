"""Shared helpers: Socrata queries, column lookup, time labels, zone/area labels, sample tables."""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
SAMPLES = ROOT / "output" / "samples"
for _d in (RAW, PROC, SAMPLES):
    _d.mkdir(parents=True, exist_ok=True)

NY = "data.ny.gov"
NYC = "data.cityofnewyork.us"
TOKEN = os.environ.get("SOCRATA_APP_TOKEN")  # optional, raises rate limits
TZ = "America/New_York"
TOLL_START = pd.Timestamp("2025-01-05")


# --------------------------------------------------------------------------- Socrata
def columns(domain: str, dataset_id: str) -> dict[str, str]:
    """Return {fieldName: dataTypeName} from the dataset's metadata."""
    r = requests.get(f"https://{domain}/api/views/{dataset_id}.json", timeout=60)
    r.raise_for_status()
    return {c["fieldName"]: c.get("dataTypeName", "") for c in r.json()["columns"]}


def pick(cols: dict, *candidates: str, required: bool = True) -> str | None:
    """Find the first matching column name (exact match first, then substring)."""
    for c in candidates:
        if c in cols:
            return c
    for c in candidates:
        for k in cols:
            if c in k:
                return k
    if required:
        raise SystemExit(
            f"Could not find any of {candidates}.\nAvailable columns: {sorted(cols)}\n"
            "Edit the candidate names in the script to match."
        )
    return None


def soql(domain: str, dataset_id: str, params: dict, page: int = 50000) -> pd.DataFrame:
    """Run a SoQL query with paging. Pass an explicit $order so pages are stable."""
    url = f"https://{domain}/resource/{dataset_id}.json"
    headers = {"X-App-Token": TOKEN} if TOKEN else {}
    rows, offset = [], 0
    while True:
        p = dict(params, **{"$limit": page, "$offset": offset})
        r = requests.get(url, params=p, headers=headers, timeout=600)
        if r.status_code != 200:
            raise SystemExit(f"Query failed ({r.status_code}): {r.text[:600]}\nURL: {r.url}")
        batch = r.json()
        rows.extend(batch)
        print(f"  {dataset_id}: fetched {len(rows):,} rows", flush=True)
        if len(batch) < page:
            break
        offset += page
    return pd.DataFrame(rows)


def to_num(df: pd.DataFrame, *cols: str) -> pd.DataFrame:
    for c in cols:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    return df


# --------------------------------------------------------------------------- time labels
def holidays(start="2019-01-01", end="2027-12-31") -> pd.DatetimeIndex:
    from pandas.tseries.holiday import USFederalHolidayCalendar

    return USFederalHolidayCalendar().holidays(start=start, end=end)


def add_time_labels(df: pd.DataFrame, ts_col: str) -> pd.DataFrame:
    """Add is_weekend, is_holiday, is_peak, year_month. Assumes timestamps are NY local time."""
    ts = pd.to_datetime(df[ts_col])
    df["is_weekend"] = ts.dt.dayofweek >= 5
    df["is_holiday"] = ts.dt.normalize().isin(holidays())
    h = ts.dt.hour
    df["is_peak"] = np.where(df["is_weekend"], (h >= 9) & (h < 21), (h >= 5) & (h < 21))
    df["year_month"] = ts.dt.to_period("M").astype(str)
    return df


# --------------------------------------------------------------------------- space
# Hand-digitized outline of Manhattan south of 60th Street (lon, lat). About 100 m accuracy.
# Replace by putting an official boundary at data/raw/crz_boundary.geojson.
ZONE_LONLAT = [
    (-73.9945, 40.7740), (-73.9580, 40.7600), (-73.9650, 40.7520), (-73.9715, 40.7430),
    (-73.9710, 40.7270), (-73.9770, 40.7110), (-73.9985, 40.7065), (-74.0110, 40.7010),
    (-74.0160, 40.7003), (-74.0170, 40.7100), (-74.0125, 40.7280), (-74.0110, 40.7450),
    (-74.0050, 40.7590),
]
ADJACENT_BUFFER_FT = 6562  # 2 km in EPSG:2263 feet


def zone_polygon_2263():
    import geopandas as gpd
    from shapely.geometry import Polygon

    official = RAW / "crz_boundary.geojson"
    if official.exists():
        g = gpd.read_file(official).to_crs(2263)
        return g.unary_union
    return gpd.GeoSeries([Polygon(ZONE_LONLAT)], crs=4326).to_crs(2263).iloc[0]


def label_area(lon: pd.Series, lat: pd.Series) -> np.ndarray:
    """'inside' the zone, 'adjacent' (within 2 km), or 'elsewhere'."""
    import geopandas as gpd

    pts = gpd.GeoSeries(gpd.points_from_xy(lon.astype(float), lat.astype(float)), crs=4326).to_crs(2263)
    zone = zone_polygon_2263()
    ring = zone.buffer(ADJACENT_BUFFER_FT)
    inside = pts.within(zone).values
    adjacent = pts.within(ring).values & ~inside
    return np.select([inside, adjacent], ["inside", "adjacent"], "elsewhere")


def valid_nyc_coords(df: pd.DataFrame, lon: str, lat: str) -> pd.Series:
    x = pd.to_numeric(df[lon], errors="coerce")
    y = pd.to_numeric(df[lat], errors="coerce")
    return x.between(-74.30, -73.65) & y.between(40.45, 40.95)


def load_nta():
    """NTA 2020 neighborhood polygons (cached)."""
    import geopandas as gpd

    path = RAW / "nta2020.geojson"
    if not path.exists():
        url = f"https://{NYC}/resource/9nt8-h7nd.geojson?$limit=1000"
        r = requests.get(url, timeout=120)
        r.raise_for_status()
        path.write_bytes(r.content)
    nta = gpd.read_file(path)
    name = next(c for c in ("ntaname", "nta_name", "NTAName") if c in nta.columns)
    boro = next(c for c in ("boroname", "boro_name", "BoroName") if c in nta.columns)
    return nta[[name, boro, "geometry"]].rename(columns={name: "nta_name", boro: "borough"}).to_crs(4326)


def join_nta(df: pd.DataFrame, lon: str, lat: str) -> pd.DataFrame:
    import geopandas as gpd

    g = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df[lon].astype(float), df[lat].astype(float)), crs=4326)
    out = gpd.sjoin(g, load_nta(), how="left", predicate="within").drop(columns=["geometry", "index_right"])
    return pd.DataFrame(out)


# --------------------------------------------------------------------------- outputs
def save(df: pd.DataFrame, name: str) -> Path:
    path = PROC / f"{name}.csv"
    df.to_csv(path, index=False)
    print(f"  wrote {path.relative_to(ROOT)} ({len(df):,} rows)")
    return path


def write_sample(df: pd.DataFrame, name: str, n: int = 8, note: str = "") -> None:
    """Markdown sample for the report: first n rows + shape."""
    body = df.head(n).to_markdown(index=False, floatfmt=".2f")
    text = f"{body}\n\n_{len(df):,} rows × {df.shape[1]} columns. {note}_\n"
    (SAMPLES / f"{name}.md").write_text(text)
    print(f"  wrote output/samples/{name}.md")


def log_gaps(dataset: str, dates: pd.Series, freq: str = "D") -> None:
    """Append missing periods for a dataset to data/processed/gaps.csv."""
    d = pd.to_datetime(dates).dt.to_period(freq).drop_duplicates().sort_values()
    if d.empty:
        return
    full = pd.period_range(d.iloc[0], d.iloc[-1], freq=freq)
    missing = sorted(set(full) - set(d))
    path = PROC / "gaps.csv"
    rows = pd.DataFrame({"dataset": dataset, "missing_period": [str(m) for m in missing]})
    old = pd.read_csv(path) if path.exists() else pd.DataFrame(columns=rows.columns)
    old = old[old["dataset"] != dataset]
    pd.concat([old, rows]).to_csv(path, index=False)
    print(f"  {dataset}: {len(missing)} missing {freq} periods logged")


def same_period_last_year(df: pd.DataFrame, keys: list[str], period_col: str, value_col: str,
                          offset: pd.DateOffset) -> pd.DataFrame:
    """Join each row to the same period one year earlier and compute % change."""
    prev = df[keys + [period_col, value_col]].copy()
    prev[period_col] = pd.to_datetime(prev[period_col]) + offset
    prev = prev.rename(columns={value_col: f"{value_col}_prev_year"})
    out = df.copy()
    out[period_col] = pd.to_datetime(out[period_col])
    out = out.merge(prev, on=keys + [period_col], how="left")
    out["pct_change"] = (out[value_col] / out[f"{value_col}_prev_year"] - 1) * 100
    return out
