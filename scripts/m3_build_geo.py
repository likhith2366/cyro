"""Build the two small GeoJSON files used by the Milestone 3 D3 maps.

Outputs (WGS84, simplified to ~15 m so the browser loads them quickly):
  milestone3/data/nta2020.geojson  2020 Neighborhood Tabulation Areas (NYC DCP, release 25C)
  milestone3/data/zone.geojson     the hand-digitized Congestion Relief Zone outline used in Milestone 2

NTA source, in order of preference:
  1. data/raw/nta2020.geojson   (written by m2_common.load_nta() from NYC Open Data 9nt8-h7nd)
  2. an .rda copy of the same DCP file from the kjhealy/nycmaps R package
     (git clone --depth 1 https://github.com/kjhealy/nycmaps /tmp/nycmaps)
"""
import json
import sys
from pathlib import Path

import geopandas as gpd
from shapely.geometry import MultiPolygon, Polygon, mapping, shape
from shapely.geometry.polygon import orient

sys.path.insert(0, str(Path(__file__).parent))
from m2_common import ZONE_LONLAT  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "milestone3" / "data"
OUT.mkdir(parents=True, exist_ok=True)


def load_ntas() -> gpd.GeoDataFrame:
    raw = ROOT / "data" / "raw" / "nta2020.geojson"
    if raw.exists():
        g = gpd.read_file(raw)
        g = g.rename(columns={"ntaname": "nta_name", "boroname": "borough"})
        return g[["nta_name", "borough", "geometry"]].to_crs(4326)
    rda = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/nycmaps/data/nyc_nta20_sf.rda")
    import rdata

    df = rdata.conversion.convert(rdata.parser.parse_file(rda), default_encoding="utf8")["nyc_nta20_sf"]

    def to_geom(mp):  # sf MULTIPOLYGON -> nested lists of rings (EPSG:2263)
        polys = [Polygon(p[0], p[1:]) for p in mp]
        return MultiPolygon(polys)

    geoms = [to_geom(g) for g in df["geometry"]]
    g = gpd.GeoDataFrame({"nta_name": df["nta_name"].values, "borough": df["boro_name"].values},
                         geometry=geoms, crs=2263)
    return g.to_crs(4326)


def clockwise(geom):
    """d3-geo treats counter-clockwise exterior rings as 'the whole globe minus this shape'."""
    if geom.geom_type == "Polygon":
        return orient(geom, sign=-1.0)
    return MultiPolygon([orient(p, sign=-1.0) for p in geom.geoms])


def main():
    nta = load_ntas()
    nta["geometry"] = nta.to_crs(2263).simplify(50).to_crs(4326)  # 50 ft
    feats = [{"type": "Feature", "properties": {"nta_name": r.nta_name, "borough": r.borough},
              "geometry": mapping(clockwise(r.geometry))} for r in nta.itertuples()]
    txt = json.dumps({"type": "FeatureCollection", "features": feats}, separators=(",", ":"))
    # round coordinates to 5 decimals (~1 m) to keep the file small
    import re
    txt = re.sub(r"(-?\d+\.\d{5})\d+", r"\1", txt)
    (OUT / "nta2020.geojson").write_text(txt)

    zone = {"type": "FeatureCollection", "features": [{"type": "Feature",
            "properties": {"name": "Congestion Relief Zone (approx.)"},
            "geometry": mapping(clockwise(Polygon(ZONE_LONLAT)))}]}
    (OUT / "zone.geojson").write_text(json.dumps(zone))
    print(f"wrote {len(feats)} NTAs and the zone outline to {OUT}")


if __name__ == "__main__":
    main()
