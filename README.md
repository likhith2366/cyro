# Congestion Pricing in New York City: What Changed After the Toll?

CS-GY 6313 B Information Visualization, Fall 2026, team **cyro** (Team 3)

- Praneeth Yashovardhan Kadem (pk3206)
- Bhavana Peruri (bp2847)
- Likhith Vardhan Goruputi (lvg8030)

On January 5, 2025 New York began tolling vehicles that enter Manhattan at or below 60th Street (the
Congestion Relief Zone). This project uses public data to look at what changed: entries into the zone,
toll-avoiding routes, speeds, crashes, and subway / Citi Bike use, inside the zone, next to it and citywide.

## Repository layout

```
scripts/            data download + processing (one script per question group)
  common.py         shared helpers: Socrata queries, time labels, zone/area labels, sample tables
data/raw/           downloaded files (git-ignored)
data/processed/     processed CSVs used by the visualizations
output/samples/     Markdown samples of each processed table (pasted into the report)
sketches/           our hand-made sketches for each question
report/             Milestone 2 report (PDF)
```

## How to run

Requires Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# optional: a free Socrata app token avoids rate limits
export SOCRATA_APP_TOKEN=your_token  # https://data.ny.gov/profile/edit/developer_settings

bash run_all.sh
```

`run_all.sh` runs the scripts in this order (each can also be run alone from `scripts/`):

| Script | Questions | Approx. time |
| --- | --- | --- |
| `q1_q3_crz_entries.py` | Q1, Q2, Q3 | 2–5 min |
| `q2_bt_crossings.py` | Q2 baseline | 2–5 min |
| `q4_speeds.py` | Q4 | < 1 min |
| `q5_q7_collisions.py` | Q5, Q7 | 3–6 min |
| `q6_subway.py` | Q6 | 5–10 min (server-side aggregation) |
| `q6_citibike.py` | Q6 | 10–20 min (two ~500 MB downloads) |
| `q8_summary.py` | Q8 | seconds (needs the outputs above) |

Each script prints the columns it found. If the MTA renames a column, the script stops and lists the
available names; update the candidate names at the top of that script.

## Data access

All data is public; no account is needed.

| Dataset | Publisher | Access |
| --- | --- | --- |
| MTA Congestion Relief Zone Vehicle Entries: Beginning 2025 | NY State Open Data | https://data.ny.gov/d/t6yz-b64h (API: `https://data.ny.gov/resource/t6yz-b64h.json`) |
| MTA Bridges and Tunnels Hourly Crossings | NY State Open Data | https://data.ny.gov/d/ebfx-2m7v |
| MTA Central Business District Taxi and FHV Speeds: Beginning Oct 2019 | NY State Open Data | https://data.ny.gov/d/6p29-6xqn |
| MTA Subway Hourly Ridership: 2020–2024 | NY State Open Data | https://data.ny.gov/d/wujg-7c2s |
| MTA Subway Hourly Ridership: Beginning 2025 | NY State Open Data | https://data.ny.gov/d/5wq4-mkjj |
| Citi Bike System Data (monthly trip ZIPs) | Lyft / Citi Bike | https://s3.amazonaws.com/tripdata/index.html |
| Motor Vehicle Collisions – Crashes | NYC Open Data (NYPD) | https://data.cityofnewyork.us/d/h9gi-nx95 |
| 2020 Neighborhood Tabulation Areas (NTAs) | NYC Open Data (DCP) | https://data.cityofnewyork.us/d/9nt8-h7nd |

Zone boundary: `scripts/common.py` contains a hand-digitized outline of Manhattan south of 60th Street
(about 100 m accuracy). To use an official boundary instead, save it as `data/raw/crz_boundary.geojson`.

## Processing notes

- Timestamps are New York local time. Rows get `is_peak` (weekdays 5 a.m.–9 p.m., weekends 9 a.m.–9 p.m.),
  `is_weekend`, `is_holiday` and `year_month`.
- Year-over-year comparisons always use the same calendar month or week.
- Points are labeled `inside` the zone, `adjacent` (within 2 km) or `elsewhere`, and joined to NTAs.
- Citi Bike trips under 60 seconds or over 3 hours are dropped; crashes without valid coordinates are
  dropped and counted per month in `data/processed/collisions_dropped_by_month.csv`.
- Missing days/months per dataset are written to `data/processed/gaps.csv`.

## AI use statement

Per the course AI policy: we used Claude (Anthropic) to help brainstorm the topic and draft parts of the
proposal (Milestone 1), and to draft the data-processing scripts, this README and the structure and
text of the Milestone 2 report. We reviewed, ran and edited all of it ourselves. All sample tables come
from running these scripts. All sketches in `sketches/` are our own work; no AI tool was used to create them.
