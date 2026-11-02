# Congestion Pricing in NYC: What Changed After the Toll?

CS-GY 6313 B Information Visualization, Fall 2026, final project of **Team 3: cyro**
(Praneeth Yashovardhan Kadem, Bhavana Peruri, Likhith Vardhan Goruputi).

On January 5, 2025 New York began tolling vehicles entering Manhattan at or below 60th Street (the
Congestion Relief Zone, CRZ). This project uses public data to look at how traffic, speeds, safety and
transit use changed, and where.

- **Milestone 2 report:** [`report/Milestone2_Report.pdf`](report/Milestone2_Report.pdf) (HTML version alongside)
- **Sketches (Vega-Lite):** [`sketches/`](sketches/): one `.vl.json` spec + PNG per question, and
  `sketches/index.html` to view them all interactively
- **Processed tables:** [`data/processed/`](data/processed/): one CSV per domain question

## Domain questions

| # | Question | Processed table(s) | Sketch |
|---|----------|--------------------|--------|
| Q1 | When and where do vehicles enter the zone on a typical weekday? | `q1_*` | `q1_entries_when_where` |
| Q2 | How have entries changed since the toll, by vehicle class and peak/off-peak? | `q2_*` | `q2_entries_change` |
| Q3 | Are drivers avoiding the toll via the FDR Drive / West Side Highway? | `q3_*` | `q3_toll_avoidance` |
| Q4 | Is traffic in the zone faster than before, and than the rest of the city? | `q4_*` | `q4_speeds` |
| Q5 + Q7 | Did crashes fall inside the zone, and rise just outside it? (merged) | `q5_q7_*` | `q5_q7_crashes` |
| Q6 | Did more people take the subway / Citi Bike into the zone, and from where? | `q6_*` | `q6_transit_into_zone` |
| Q8 | Which areas gained and which carried the costs? | `q8_area_scorecard.csv` | `q8_area_scorecard` |

Changes from the proposal are described in the report (highlighted boxes).

## How to run

Requires Python 3.10+.

```bash
pip install -r requirements.txt
python scripts/fetch_data.py        # downloads aggregated data into data/raw/ (about 10 minutes)
python scripts/process_citibike.py  # downloads 2 Citi Bike months (~800 MB), keeps trips ending in the zone
python scripts/process_data.py      # builds data/processed/*.csv
python scripts/make_sketches.py     # builds sketches/*.vl.json, *.png, index.html
python scripts/build_report.py      # builds report/Milestone2_Report.html (+ PDF if Edge/Chrome is installed)
```

To view the interactive sketches, run `python -m http.server` inside `sketches/` and open
http://localhost:8000. You can also paste any `.vl.json` file into the [Vega editor](https://vega.github.io/editor).

`data/raw/` is not committed (it is large and can be regenerated). `data/processed/` is committed.

## Data access

All datasets are public. No API key is needed; the scripts use the Socrata SODA API with server-side
aggregation (`$select`, `$group`, `within_polygon`) so only small summaries are downloaded.

| Dataset | Publisher | URL | Used for |
|---------|-----------|-----|----------|
| MTA Congestion Relief Zone Vehicle Entries: Beginning 2025 | NY State Open Data | https://data.ny.gov/d/t6yz-b64h | Q1, Q2, Q3 |
| MTA Vehicle Miles Traveled in the CBD: Beginning 2024 | NY State Open Data | https://data.ny.gov/d/jbxx-kxff | Q2 (pre-toll baseline) |
| MTA CBD Taxi and For-Hire Vehicle Speeds: Beginning October 2019 | NY State Open Data | https://data.ny.gov/d/6p29-6xqn | Q4, Q8 |
| MTA CBD Geofence (zone outline) | NY State Open Data | https://data.ny.gov/d/srxy-5nxn | all maps, area assignment |
| MTA Subway Hourly Ridership: 2020-2024 | NY State Open Data | https://data.ny.gov/d/wujg-7c2s | Q6, Q8 |
| MTA Subway Hourly Ridership: Beginning 2025 | NY State Open Data | https://data.ny.gov/d/5wq4-mkjj | Q6, Q8 |
| MTA Subway Origin-Destination Ridership Estimate: 2024 | NY State Open Data | https://data.ny.gov/d/jsu2-fbtj | Q6 |
| MTA Subway Origin-Destination Ridership Estimate: 2025 | NY State Open Data | https://data.ny.gov/d/y2qv-fytt | Q6 |
| Motor Vehicle Collisions - Crashes | NYC Open Data (NYPD) | https://data.cityofnewyork.us/d/h9gi-nx95 | Q5, Q7, Q8 |
| 2020 Neighborhood Tabulation Areas (NTAs) | NYC Open Data (DCP) | https://data.cityofnewyork.us/d/9nt8-h7nd | Q6 map |
| Citi Bike System Data (monthly trip files) | Citi Bike / Lyft | https://citibikenyc.com/system-data (files at https://s3.amazonaws.com/tripdata/) | Q6 |
| TLC Trip Record Data (deferred) | NYC TLC | https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page | not yet used |

Data was retrieved on 2026-11-02. Coverage at that time: CRZ entries to 2026-10-24, speeds to 2025-08,
VMT to 2026-06, subway ridership to 2026-09, crashes to 2026-10-27.

## Key processing decisions

- **Areas.** Points are assigned to *CRZ* (inside the MTA geofence polygon), *Adjacent* (outside the zone but
  within 1.5 km of its boundary) or *Rest of NYC* (`scripts/common.py`, `area_classifier`).
- **Peak / off-peak.** Weekdays 5 a.m.-9 p.m. and weekends 9 a.m.-9 p.m. are peak (the toll schedule).
- **Seasonality.** Comparisons use the same calendar months in each year; partial months are dropped.
- **Speed baseline.** 2023-2024 same-month average (2020-2022 are distorted by the pandemic).
- **Cleaning.** Crashes without valid coordinates are dropped (about 6%); Citi Bike trips without
  coordinates, shorter than 1 minute or longer than 3 hours are dropped (about 0.3%).

## Observable

We do not use Observable notebooks at this stage. If we add any, their URLs will be listed here.

## AI use

Per the course AI policy: we used **Claude (Anthropic)** as a coding assistant to help write the data
download and processing scripts (`scripts/`), the Vega-Lite specifications for the Milestone 2 sketches,
and drafts of the Milestone 2 report and this README. It was also used to brainstorm the topic and draft parts
of the proposal (Milestone 1). The team chose the questions, reviewed the transformations, checked the
outputs against the source data, and edited all text.
