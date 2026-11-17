# Congestion Pricing in NYC: What Changed After the Toll?

CS-GY 6313 B Information Visualization, Fall 2026, final project of **Team 3: cyro**

- Praneeth Yashovardhan Kadem (pk3206)
- Bhavana Peruri (bp2847)
- Likhith Vardhan Goruputi (lvg8030)

On January 5, 2025 New York began tolling vehicles entering Manhattan at or below 60th Street (the
Congestion Relief Zone, CRZ). This project uses public data to look at how traffic, speeds, safety and
transit use changed, and where.

## Milestones

| Milestone | Where to find it |
|---|---|
| **Milestone 3 – D3 visualizations (current)** | **Interactive page: [`milestone3/index.html`](milestone3/index.html)** · write-up with screenshots: [`milestone3/README.md`](milestone3/README.md) |
| Milestone 2 – Data handling & sketches (submitted, unchanged) | [`report/Team_cyro_Milestone2.pdf`](report/Team_cyro_Milestone2.pdf), sketches in `sketches/`, pipelines described below |
| Milestone 1 – Proposal | Submitted on Brightspace (topic, datasets and questions are repeated below) |

### Milestone 3: how to view the D3 visualizations

```bash
git clone https://github.com/likhith2366/cyro.git
cd cyro                      # serve from the repository root
python -m http.server 8000   # any static server works
```

Open **http://localhost:8000/milestone3/**. The page has one section per domain question (Q1–Q8), each with the D3
visualization, a description of what it shows, and a "Show the D3 code" panel. D3 v7 is bundled in `milestone3/vendor/`, so
nothing needs to be installed. (Opening `index.html` directly from disk does not work because browsers block `fetch` on
`file://` URLs.) The visualizations read the Milestone 2 tables in `data/processed/` directly; the only new data files are the
map boundaries in `milestone3/data/`, built by `python scripts/m3_build_geo.py`.

## What is in this repository

The repository holds two data pipelines that the team built in parallel for Milestone 2. Both answer the
same domain questions from the same public datasets; they differ in some definitions (noted below).

> **Pipeline B is the authoritative pipeline** for the submitted Milestone 2 report, for the Milestone 3
> visualizations, and for the rest of the project. Everywhere we say *adjacent*, we mean within 2 km of the
> hand-digitized zone outline, and the Q2 before/after comparison is the Manhattan-bound tunnel crossings.
> Pipeline A is kept for reference only — it produced an earlier draft report and the Vega-Lite sketches — and
> its tables and its 1.5 km adjacency are **not** mixed into Milestone 3, with one flagged exception: the Q6
> subway origin–destination table (`q6_subway_od_into_crz_by_neighborhood.csv`) is a Pipeline A output, so its
> "into the zone" test uses the official MTA geofence rather than our outline. This is stated on the Milestone 3
> page as well; rebuilding that table under Pipeline B is a Milestone 4 task.

| | Pipeline A (reference) | Pipeline B (authoritative) |
|---|---|---|
| Scripts | `scripts/fetch_data.py`, `process_citibike.py`, `process_data.py`, `make_sketches.py`, `build_report.py` (helpers: `scripts/common.py`) | `scripts/q1_q3_crz_entries.py`, `q2_bt_crossings.py`, `q4_speeds.py`, `q5_q7_collisions.py`, `q6_subway.py`, `q6_citibike.py`, `q8_summary.py` (helpers: `scripts/m2_common.py`) |
| Processed tables | `data/processed/q1_entry_point_summary.csv`, `q2_vmt_monthly.csv`, `q3_excluded_share_monthly.csv`, `q4_speeds_monthly.csv`, `q5_q7_*`, `q6_*_into_crz_*`, `q6_subway_monthly_by_area.csv`, `q8_area_scorecard.csv`, ... | `data/processed/q1_weekday_profile.csv`, `q2_weekly_by_class.csv`, `q2_bt_yoy.csv`, `q3_excluded_share.csv`, `m2_q4_speeds_monthly.csv`, `q5_nta_crash_change.csv`, `q6_subway_monthly.csv`, `q6_citibike_origins.csv`, `q7_monthly_by_area.csv`, `q8_nta_summary.csv`; samples in `output/samples/` |
| Sketches | Vega-Lite: `sketches/*.vl.json` + PNG, viewable in `sketches/index.html` | Hand-drawn: `sketches/hand_drawn/q1_sketch.png` ... `q8_sketch.png` |
| Adjacent area | within 1.5 km of the MTA geofence | within 2 km of a hand-digitized zone outline |
| Pre-toll baseline for Q2 | MTA Vehicle Miles Traveled in the CBD | MTA Bridges & Tunnels crossings (Hugh L. Carey, Queens Midtown, Manhattan-bound) |
| Citi Bike months | Feb 2024 vs Feb 2025 | Oct 2024 vs Oct 2025 |

**Milestone 2 report (submitted):** [`report/Team_cyro_Milestone2.pdf`](report/Team_cyro_Milestone2.pdf). An earlier draft built by Pipeline A is in `report/Milestone2_Report.pdf`.

## Domain questions

| # | Question |
|---|----------|
| Q1 | When and where do vehicles enter the zone on a typical weekday? |
| Q2 | How have entries changed since the toll, by vehicle class and peak/off-peak? |
| Q3 | Are drivers avoiding the toll via the FDR Drive / West Side Highway? |
| Q4 | Is traffic in the zone faster than before, and than the rest of the city? |
| Q5 | Did traffic or crashes get worse just outside the zone? |
| Q6 | Did more people take the subway / Citi Bike into the zone, and from where? |
| Q7 | Have crashes and injuries inside the zone gone down compared with the rest of the city? |
| Q8 | Which areas gained and which carried the costs? |

## How to run

Requires Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**Pipeline A**

```bash
python scripts/fetch_data.py        # downloads aggregated data into data/raw/ (about 10 minutes)
python scripts/process_citibike.py  # downloads 2 Citi Bike months (~800 MB), keeps trips ending in the zone
python scripts/process_data.py      # builds data/processed/*.csv
python scripts/make_sketches.py     # builds sketches/*.vl.json, *.png, index.html
python scripts/build_report.py      # builds report/Milestone2_Report.html (+ PDF if Edge/Chrome is installed)
```

To view the interactive sketches, run `python -m http.server` inside `sketches/` and open
http://localhost:8000, or paste any `.vl.json` file into the [Vega editor](https://vega.github.io/editor).

**Pipeline B**

```bash
bash run_all.sh                     # runs scripts/q*.py in order (20-40 min; Citi Bike step downloads ~1 GB)
```

Each script writes a CSV to `data/processed/` and a Markdown sample to `output/samples/`.
A free Socrata app token (`export SOCRATA_APP_TOKEN=...`) avoids rate limits.

`data/raw/` is not committed (it is large and can be regenerated). `data/processed/` is committed.

## Data access

All datasets are public. No API key is needed; the scripts use the Socrata SODA API with server-side
aggregation (`$select`, `$group`, `within_polygon`) so only small summaries are downloaded.

| Dataset | Publisher | URL | Used for |
|---------|-----------|-----|----------|
| MTA Congestion Relief Zone Vehicle Entries: Beginning 2025 | NY State Open Data | https://data.ny.gov/d/t6yz-b64h | Q1, Q2, Q3 |
| MTA Vehicle Miles Traveled in the CBD: Beginning 2024 | NY State Open Data | https://data.ny.gov/d/jbxx-kxff | Q2 baseline (A) |
| MTA Bridges and Tunnels Hourly Crossings | NY State Open Data | https://data.ny.gov/d/ebfx-2m7v | Q2 baseline (B) |
| MTA CBD Taxi and For-Hire Vehicle Speeds: Beginning October 2019 | NY State Open Data | https://data.ny.gov/d/6p29-6xqn | Q4, Q8 |
| MTA CBD Geofence (zone outline) | NY State Open Data | https://data.ny.gov/d/srxy-5nxn | maps, area assignment (A) |
| MTA Subway Hourly Ridership: 2020-2024 | NY State Open Data | https://data.ny.gov/d/wujg-7c2s | Q6, Q8 |
| MTA Subway Hourly Ridership: Beginning 2025 | NY State Open Data | https://data.ny.gov/d/5wq4-mkjj | Q6, Q8 |
| MTA Subway Origin-Destination Ridership Estimate: 2024 | NY State Open Data | https://data.ny.gov/d/jsu2-fbtj | Q6 (A) |
| MTA Subway Origin-Destination Ridership Estimate: 2025 | NY State Open Data | https://data.ny.gov/d/y2qv-fytt | Q6 (A) |
| Motor Vehicle Collisions - Crashes | NYC Open Data (NYPD) | https://data.cityofnewyork.us/d/h9gi-nx95 | Q5, Q7, Q8 |
| 2020 Neighborhood Tabulation Areas (NTAs) | NYC Open Data (DCP) | https://data.cityofnewyork.us/d/9nt8-h7nd | maps, neighborhood joins |
| Citi Bike System Data (monthly trip files) | Citi Bike / Lyft | https://citibikenyc.com/system-data (files at https://s3.amazonaws.com/tripdata/) | Q6 |
| TLC Trip Record Data (deferred) | NYC TLC | https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page | not yet used |

Data was retrieved on 2026-11-02. Coverage at that time: CRZ entries to 2026-10-24, speeds to 2025-08,
VMT to 2026-06, subway ridership to 2026-09, crashes to 2026-10-27.

## Key processing decisions

- **Areas.** Points are assigned to inside the zone, adjacent, or rest of NYC (definitions per pipeline above).
- **Peak / off-peak.** Weekdays 5 a.m.-9 p.m. and weekends 9 a.m.-9 p.m. are peak (the toll schedule).
- **Seasonality.** Comparisons use the same calendar months in each year; partial months are dropped.
- **Cleaning.** Crashes without valid coordinates are dropped (about 6%); Citi Bike trips without
  coordinates, shorter than 1 minute or longer than 3 hours are dropped.
- **Known data limits.** CRZ entries start on the toll's first day (no pre-toll baseline); the speeds dataset
  is monthly with no peak/off-peak split; excluded-roadway entries also occur at the Brooklyn Bridge and
  Hugh L. Carey Tunnel (traffic that stays on the FDR / West Side Highway).

## Observable

We do not use Observable notebooks at this stage. If we add any, their URLs will be listed here.

## AI use

### Milestone 3

Per the course AI policy, this is how AI was used for Milestone 3 (the same statement is at the end of
[`milestone3/index.html`](milestone3/index.html) and [`milestone3/README.md`](milestone3/README.md)):

- **Model:** Claude (Anthropic), Claude Opus 5.5, used through the Claude app.
- **Coding:** Claude wrote the first drafts of all D3 code in `milestone3/js/` (the eight charts and the shared helpers in
  `common.js`), the page layout and CSS (`milestone3/index.html`, `milestone3/css/style.css`), and `scripts/m3_build_geo.py`,
  which converts the 2020 NTA boundaries to GeoJSON. The team specified the chart type, encodings and interactions for each
  question (from our Milestone 2 sketches), ran the page, checked tooltip numbers against the CSVs, and asked for fixes where a
  chart was wrong or unclear.
- **Writing:** Claude drafted the "What the visualization shows" paragraphs from summary numbers computed from our processed
  tables, the Milestone 3 introduction and this README section. The team reviewed every number and edited the wording.
- **Not AI:** the choice of questions, datasets and processing rules (Milestones 1–2), the hand-drawn sketches, and the
  interpretation decisions (e.g., presenting results as associations, not causal effects).
- **Split of work:** most of the first-draft code and text for Milestone 3 came from Claude; the team's work was the design
  decisions, the data preparation behind every chart (Milestone 2 pipelines), testing and verification, and editing.

### Milestone 2 and earlier

Per the course AI policy: we used **Claude (Anthropic)** as an assistant for:

- writing the data download and processing scripts for both pipelines (`scripts/`);
- writing the Vega-Lite specifications for the Pipeline A sketches (`sketches/*.vl.json` and their PNGs);
- drafting the Milestone 2 report(s) and this README;
- brainstorming the topic and drafting parts of the proposal (Milestone 1).

The hand-drawn sketches (`sketches/hand_drawn/`) were made by the team. The team chose the questions,
reviewed the transformations, ran the scripts, checked the outputs against the source data, and edited all text.
