"""Step 4: assemble the Milestone 2 report (HTML + PDF) from the processed tables and sketches.

Run after make_sketches.py:
    python scripts/build_report.py
Writes report/Milestone2_Report.html and, if Microsoft Edge or Chrome is installed,
report/Milestone2_Report.pdf (headless print).
"""
import base64
import shutil
import subprocess
from pathlib import Path

import pandas as pd

from common import PROCESSED, ROOT, SKETCHES

REPORT = ROOT / "report"
REPORT.mkdir(exist_ok=True)


def table(name, cols=None, n=8, sort=None, query=None, caption=""):
    df = pd.read_csv(PROCESSED / name)
    if query:
        df = df.query(query)
    if sort:
        df = df.sort_values(sort[0], ascending=sort[1])
    if cols:
        df = df[cols]
    total = len(pd.read_csv(PROCESSED / name))
    html = df.head(n).to_html(index=False, border=0, classes="data", float_format=lambda x: f"{x:,.0f}" if float(x).is_integer() else f"{x:,.2f}")
    return (f'<p class="cap"><b>Table.</b> {caption} Sample of {min(n, len(df))} of {total:,} rows '
            f'in <code>data/processed/{name}</code>.</p>{html}')


def img(name, caption):
    b64 = base64.b64encode((SKETCHES / f"{name}.png").read_bytes()).decode()
    return (f'<figure><img src="data:image/png;base64,{b64}"><figcaption><b>Sketch.</b> {caption} '
            f'Interactive version: <code>sketches/{name}.vl.json</code> / <code>sketches/index.html</code>.'
            f'</figcaption></figure>')


def change(text):
    return f'<div class="change"><b>Change from proposal:</b> {text}</div>'


SECTIONS = []

SECTIONS.append(f"""
<h2>Q1. When and where do vehicles enter the zone on a typical weekday, and which entry points are busiest?</h2>
<p><b>Data:</b> MTA CRZ Vehicle Entries (10-minute bins, Jan 5 2025 - Oct 24 2026).
<b>Transformation:</b> summed entries server-side (SoQL) to date x hour x entry point; kept Mon-Fri;
divided by the number of weekdays to get the average weekday entries per hour; summed hours for a daily
total, share of all entries, and busiest hour. Each MTA detection group was given an approximate
Manhattan-side coordinate for the map.</p>
{table("q1_entry_point_summary.csv", ["detection_group", "detection_region", "avg_weekday_crz_entries", "share_pct", "peak_hour"], n=12, caption="Average weekday tolled entries per entry point.")}
{table("q1_weekday_hourly_by_entry_point.csv", ["detection_group", "hour_of_day", "avg_crz_entries", "avg_excluded_entries"], n=6, query="detection_group == 'Lincoln Tunnel' and 5 <= hour_of_day <= 10", caption="Hourly profile (Lincoln Tunnel, 5-10 a.m. shown).")}
<p><b>What we see so far:</b> East 60th St (the avenues crossing 60th St from the Upper East Side) is the single
busiest entry (~75k/weekday, 15% of entries) and peaks in the afternoon (4 p.m.). The New Jersey tunnels peak
very early (6 a.m.), Brooklyn and Queens crossings at 7-9 a.m.</p>
{img("q1_entries_when_where", "Linked map + bar chart (click an entry point to highlight it) above an entry-point x hour heatmap. Circle area and bar length = average weekday entries; colour = origin region; heatmap colour = entries per hour.")}
""")

SECTIONS.append(f"""
<h2>Q2. How has the number of entries changed since the toll started, by vehicle class and peak vs. off-peak?</h2>
{change("The entries dataset begins on the day the toll started, so it has <i>no pre-toll baseline</i>. We split the question: (a) trends <i>since</i> the toll, comparing the same months of 2026 vs 2025 by vehicle class and time period; (b) before vs after, using a dataset we added: <b>MTA Vehicle Miles Traveled in the CBD (Beginning 2024)</b>.")}
<p><b>Transformation:</b> summed entries to date x vehicle class x time period (MTA's Peak / Overnight label);
grouped to month and divided by days in the month (average daily entries); dropped incomplete months
(January 2025 starts on the 5th, October 2026 is partial); compared the months present in both years (Feb-Sep).
VMT is used as published (monthly average daily VMT for the zone and for the excluded roadways).</p>
{table("q2_yoy_by_class_period.csv", n=12, caption="Average daily entries, Feb-Sep 2025 vs Feb-Sep 2026.")}
{table("q2_vmt_monthly.csv", ["date", "area", "daily_vmt_agps", "indexed_average_vmt", "post_toll"], n=6, query="area == 'Congestion Relief Zone' and (date.str.startswith('2024-0') or date.str.startswith('2025-0')) and date.str[5:7] <= '03'", caption="Daily VMT inside the zone, Jan-Mar 2024 vs Jan-Mar 2025.")}
<p><b>What we see so far:</b> peak-period car entries are ~8% lower in 2026 than in the same months of 2025,
multi-unit trucks and motorcycles fell 20-30%, while taxis/FHVs are flat or slightly up. VMT inside the zone
averaged 3.15M/day in 2024 and 3.03M/day in 2025 (about -4%).</p>
{img("q2_entries_change", "Top left: monthly average daily entries (log scale), colour = vehicle class, dash = peak/overnight, legend click isolates a class. Top right: % change 2026 vs 2025 per class and period. Bottom: daily VMT with the toll start marked.")}
""")

SECTIONS.append(f"""
<h2>Q3. Are drivers avoiding the toll by using the FDR Drive and West Side Highway?</h2>
<p><b>Transformation:</b> four crossings report both tolled entries and <i>excluded-roadway</i> entries
(vehicles that stay on the untolled FDR / West Side Highway): FDR at 60th, West Side Highway at 60th,
Brooklyn Bridge and the Hugh L. Carey Tunnel. For each we computed
<code>excluded share = excluded / (tolled + excluded)</code> per month and per weekday hour,
and labelled hours as peak (5 a.m.-9 p.m.) or overnight.</p>
{table("q3_excluded_share_monthly.csv", n=8, query="month >= '2026-01-01' and month < '2026-03-01'", caption="Monthly excluded-roadway share at each edge crossing (Jan-Feb 2026 shown).")}
{table("q3_excluded_share_by_hour_weekday.csv", ["detection_group", "hour_of_day", "toll_period", "excluded_share_pct"], n=6, query="detection_group == 'West Side Highway at 60th St' and hour_of_day in [3, 8, 13, 15, 16, 22]", caption="Weekday hourly share, West Side Highway.")}
<p><b>What we see so far:</b> the shares are stable month to month (no growing shift onto the free roads), but at
the West Side Highway the excluded share almost doubles in peak hours (11.1% vs 5.9% overnight), which is the kind of
time-of-day signal that toll avoidance would produce. We will treat this as a hypothesis, not proof, because
the hourly mix of trip purposes also changes.</p>
{img("q3_toll_avoidance", "Left: monthly excluded-roadway share per crossing (legend click isolates one). Right: weekday share by hour with the peak toll window shaded.")}
""")

SECTIONS.append(f"""
<h2>Q4. Has traffic inside the zone become faster than in 2019-2024, and than the rest of the city?</h2>
{change("The MTA speed dataset is <b>monthly taxi/FHV speeds</b> for three areas (CBD, CBD Adjacent, Greater NYC), not hourly speeds for all vehicles, and it currently ends in <b>August 2025</b>. Because 2020-2022 speeds are inflated by the pandemic, we compare against the same calendar month in <b>2023-2024</b> rather than 2019-2024; the full 2019-2025 series is still shown for context.")}
<p><b>Transformation:</b> for each area and calendar month we averaged 2023 and 2024 speeds as a baseline and
computed the difference (mph and %) for every month.</p>
{table("q4_speeds_monthly.csv", ["month", "zone", "zonal_speed", "baseline_2023_24_mph", "diff_vs_baseline_mph", "pct_vs_baseline"], n=9, query="month >= '2025-01-01' and month < '2025-04-01'", caption="Taxi/FHV speeds, Jan-Mar 2025, vs the 2023-24 same-month baseline.")}
<p><b>What we see so far:</b> CBD speeds were +3.1% higher in Jan-Aug 2025 than Jan-Aug 2024, while the adjacent area
and the rest of the city were about 1% slower; the CBD is the only area consistently above its baseline after January 2025.</p>
{img("q4_speeds", "Top: monthly speed by area (toll start marked; drag to brush a time range, legend click isolates an area). Bottom: difference from the 2023-24 same-month baseline, zoomed to the brushed range.")}
""")

SECTIONS.append(f"""
<h2>Q5 + Q7. Did crashes and injuries fall inside the zone, and did they rise just outside it?</h2>
{change("Q5 and Q7 use the same crash data with the same three-area split, so we merged them into one view. Q5's traffic part is answered by Q3/Q4 (excluded roadways and the CBD Adjacent speed series).")}
<p><b>Transformation:</b> downloaded all NYPD crash records since Jan 2023 (342k); dropped 20k with missing
or out-of-city coordinates; assigned each crash to <b>CRZ</b> (inside the MTA geofence polygon),
<b>Adjacent</b> (outside but within 1.5 km of the zone boundary: Upper East/West Side to roughly 85th St,
Long Island City, Downtown Brooklyn) or <b>Rest of NYC</b> by point-in-polygon; aggregated to month x area
(crashes, injured, killed, pedestrians, cyclists); compared the same months (Jan-Sep) each year.</p>
{table("q5_q7_collisions_yoy_by_area.csv", ["area", "year", "crashes", "persons_injured", "pedestrians_injured", "cyclist_injured", "crashes_pct_vs_2024", "persons_injured_pct_vs_2024"], n=12, sort=(["area", "year"], True), caption="Crashes and injuries, Jan-Sep of each year.")}
<p><b>What we see so far:</b> in 2025 crashes fell 3.6% inside the zone and rose 9.2% in the adjacent ring (vs -1.5%
citywide). In 2026 the CRZ is back near its 2024 level while the adjacent ring stays about 9% higher. The
monthly index is noisy (e.g. a snowy February 2025), so the final view will show monthly values, not only totals.</p>
{img("q5_q7_crashes", "Top: monthly crashes indexed to each area's 2024 average (a dropdown switches the measure to injuries, pedestrians or cyclists). Bottom: % change vs 2024 for the same months.")}
""")

SECTIONS.append(f"""
<h2>Q6. Did more people take the subway or Citi Bike into the zone, and from which neighbourhoods?</h2>
{change("Station tap counts cannot tell where a rider is going, so we added the <b>MTA Subway Origin-Destination Ridership Estimate</b> (2024 and 2025) to answer the &ldquo;from which neighbourhoods&rdquo; part. Citi Bike monthly files are 0.4-1 GB each, so for this milestone we processed one matched pair of months (February 2024 vs February 2025).")}
<p><b>Transformation:</b> (1) subway hourly ridership summed to station x month and classified by station
location (CRZ / Adjacent / Rest); (2) OD estimates filtered server-side with <code>within_polygon()</code> to weekday trips
that <i>end</i> inside the zone and start outside it, for October 2024 and October 2025; averaged to an average weekday;
origin stations joined to 2020 Neighbourhood Tabulation Areas; (3) Citi Bike: removed trips without coordinates,
shorter than 1 minute or longer than 3 hours (~0.3%), kept trips ending in the zone, and grouped by start neighbourhood.</p>
{table("q6_subway_od_into_crz_by_neighborhood.csv", n=8, caption="Average weekday subway trips into the zone by origin neighbourhood.")}
{table("q6_citibike_into_crz_by_start_area.csv", caption="Citi Bike trips ending in the zone, by start area.")}
<p><b>What we see so far:</b> average weekday subway trips into the zone rose ~3.4% (985k to 1.02M) between October 2024
and October 2025, with the largest absolute gains from Brooklyn. However, station entries rose 7-9% in
<i>every</i> area in 2025, so much of this is citywide ridership recovery. Citi Bike trips into the zone were
lower in February 2025 than February 2024; one winter month is not enough, so we will add more months.</p>
{img("q6_transit_into_zone", "Left: choropleth of % change in weekday subway trips into the zone by origin neighbourhood (zone outlined; hover for values). Right: top origin neighbourhoods and Citi Bike trips by start area. Bottom: monthly subway entries by station area.")}
""")

SECTIONS.append(f"""
<h2>Q8. Putting it together: which areas gained, and which carried the costs?</h2>
<p><b>Transformation:</b> joined the per-area results from Q4, Q5/Q7 and Q6 into one long table
(area x measure, 2024 vs 2025 over the months each dataset covers) and computed % change; for display, the sign
is flipped for crashes and injuries so that green always means "better for that area".</p>
{table("q8_area_scorecard.csv", n=12, caption="Area scorecard.")}
{img("q8_area_scorecard", "Area x measure heatmap; colour = better (green) / worse (purple), label = % change, tooltip = raw values. In the final version clicking a cell will open the Q1-Q6 chart behind it, and we plan a neighbourhood-level map version.")}
""")

HTML = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Milestone 2 Report</title>
<style>
body {{ font-family: "Times New Roman", serif; max-width: 900px; margin: 30px auto; color: #111; line-height: 1.4; font-size: 14px; }}
h1 {{ text-align: center; font-size: 22px; margin-bottom: 2px; }}
.sub {{ text-align: center; margin-top: 0; }}
h2 {{ font-size: 17px; margin-top: 30px; border-bottom: 1px solid #999; padding-bottom: 3px; page-break-after: avoid; }}
table.data {{ border-collapse: collapse; font-size: 11.5px; margin: 4px 0 14px; font-family: Arial, sans-serif; }}
table.data th, table.data td {{ border: 1px solid #bbb; padding: 3px 6px; text-align: right; }}
table.data th {{ background: #eee; }}
table.data td:first-child, table.data th:first-child {{ text-align: left; }}
.cap {{ font-size: 12.5px; margin-bottom: 2px; }}
figure {{ margin: 10px 0 20px; page-break-inside: avoid; }}
figure img {{ width: 100%; border: 1px solid #ddd; }}
figcaption {{ font-size: 12.5px; }}
.change {{ background: #fff4d6; border-left: 4px solid #e6a700; padding: 6px 10px; margin: 8px 0; }}
.ai {{ font-size: 12.5px; font-style: italic; border-top: 1px solid #999; margin-top: 30px; padding-top: 8px; }}
code {{ font-size: 12px; }}
</style></head><body>
<h1>Milestone 2: Data Handling &amp; Sketches</h1>
<p class="sub">Congestion Pricing in New York City: What Changed After the Toll?<br>
Team 3: cyro &mdash; Praneeth Yashovardhan Kadem (pk3206), Bhavana Peruri (bp2847), Likhith Vardhan Goruputi (lvg8030)<br>
Code: <a href="https://github.com/likhith2366/cyro">github.com/likhith2366/cyro</a></p>

<h2>Overview of data handling</h2>
<p>All data is public and is downloaded by <code>scripts/fetch_data.py</code>. Large tables (CRZ entries: 10-minute bins;
subway: 168M hourly rows; OD estimates: 120M rows/year) are aggregated <i>on the server</i> with SoQL
(<code>$select ... sum() ... $group</code>, <code>within_polygon()</code>) so only small summaries are downloaded.
<code>scripts/process_data.py</code> then builds one processed table per question in <code>data/processed/</code>.
Common steps: timestamps are treated as New York local time; hours are labelled peak (weekdays 5 a.m.-9 p.m.,
weekends 9 a.m.-9 p.m.) or off-peak and weekday/weekend; points (crashes, stations, Citi Bike docks) are assigned to
<b>CRZ</b> (the MTA geofence polygon), <b>Adjacent</b> (within 1.5 km of the zone boundary) or <b>Rest of NYC</b>;
seasonal effects are handled by comparing the same calendar months across years; partial months are dropped.</p>
<p><b>Datasets added since the proposal:</b> MTA Vehicle Miles Traveled in the CBD (pre-toll baseline for Q2),
MTA Subway Origin-Destination Ridership Estimates 2024/2025 (Q6), MTA CBD Geofence (zone outline) and NYC 2020
Neighbourhood Tabulation Areas (maps). <b>Deferred:</b> TLC trip records (the CRZ entries feed already has a TLC Taxi/FHV class).
<b>Known gaps:</b> speeds end Aug 2025; VMT ends Jun 2026; crash data lags ~1 week; Citi Bike is one month per year so far.</p>
<p><b>Sketches:</b> all sketches are Vega-Lite specifications rendered from the processed data (the course allows sketches
made with data-viz tools). They are drafts of layout and encoding; colours, annotation and final interaction will be
refined in D3/Vega-Lite for the final project.</p>

{''.join(SECTIONS)}

<p class="ai"><b>AI-use statement (per course policy):</b> We used Claude (Anthropic) as a coding assistant to help write
the data download / processing scripts and the Vega-Lite specifications for the sketches, and to help draft parts of this
report. The domain questions, the choice of data transformations and chart designs, and the interpretation of results were
reviewed, checked against the data, and edited by the team. The same statement is in the repository README.</p>
</body></html>
"""


def main():
    out = REPORT / "Milestone2_Report.html"
    out.write_text(HTML, encoding="utf-8")
    print(f"wrote {out}")
    browser = next((b for b in [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        shutil.which("chromium"), shutil.which("google-chrome")] if b and Path(b).exists()), None)
    if browser:
        pdf = REPORT / "Milestone2_Report.pdf"
        subprocess.run([browser, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={pdf}", out.as_uri()], check=False, timeout=180)
        print(f"wrote {pdf}" if pdf.exists() else "PDF export failed")


if __name__ == "__main__":
    main()
