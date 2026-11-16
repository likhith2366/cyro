// Q3. Are drivers using the FDR Drive and West Side Highway to avoid the toll?
// Map of entry points (pie = tolled vs excluded-roadway share, size = weekday volume) linked to
// a line chart of the weekly excluded share over time.
/* global d3, DATA, C, makeSvg, tip, axisStyle, gridStyle, legend, loadGeo, baseMap, fmtInt, fmtDay, parseDate */

(async function q3() {
  const [geo, pts, profile, weekly] = await Promise.all([
    loadGeo(),
    d3.csv(DATA + "q1_entry_point_summary.csv", d => ({ entry: d.detection_group, lat: +d.lat, lon: +d.lon })),
    d3.csv(DATA + "q1_weekday_profile.csv", d => ({ entry: d.entry_point, t: +d.avg_weekday_entries, ex: +d.avg_excluded_entries })),
    d3.csv(DATA + "q3_excluded_share.csv", d => ({
      week: parseDate(d.week_start), entry: d.entry_point,
      tolled: +d.tolled_entries, excluded: +d.excluded_entries, share: +d.excluded_share_pct,
    })),
  ]);
  // The last week in the file can be partial: drop weeks with < 80% of the median total volume
  const allW = weekly.filter(d => d.entry === "ALL ENTRY POINTS");
  const med = d3.median(allW, d => d.tolled + d.excluded);
  const okWeeks = new Set(allW.filter(d => d.tolled + d.excluded > 0.8 * med).map(d => +d.week));
  const series = weekly.filter(d => okWeeks.has(+d.week));

  const daily = d3.rollup(profile, v => ({ t: d3.sum(v, d => d.t), ex: d3.sum(v, d => d.ex) }), d => d.entry);
  pts.forEach(p => Object.assign(p, daily.get(p.entry)));
  const ALL = "ALL ENTRY POINTS";
  let selected = ALL;

  const root = "#q3-viz";
  legend(root, [
    { label: "Tolled entries", color: C.blue },
    { label: "Excluded-roadway entries (stay on FDR / West Side Hwy, not tolled)", color: C.orange },
  ]);
  const wrap = d3.select(root).append("div").attr("class", "two-col");
  const mapDiv = wrap.append("div").attr("class", "col-map");
  const lineDiv = wrap.append("div").attr("class", "col-chart");

  // ---------- map ----------
  const MW = 440, MH = 520;
  const svg = makeSvg(mapDiv.node(), MW, MH).attr("id", "q3map").attr("aria-label", "Map of entry points");
  const { g, projection } = baseMap(svg, geo, {
    width: MW, height: MH, focus: [[-74.04, 40.70], [-73.925, 40.776]],
    fillFor: d => d.properties.borough === "Manhattan" ? "#e4e3de" : C.land,
  });
  const r = d3.scaleSqrt().domain([0, d3.max(pts, d => d.t + d.ex)]).range([0, 24]);
  // Several entry points sit within a few hundred meters (60th St / Queensboro / FDR), so we let a small
  // force simulation push overlapping circles apart and draw a leader line back to the true location.
  pts.forEach(d => { [d.px, d.py] = projection([d.lon, d.lat]); d.x0 = d.px; d.y0 = d.py; });
  const sim = d3.forceSimulation(pts)
    .force("x", d3.forceX(d => d.px).strength(0.3)).force("y", d3.forceY(d => d.py).strength(0.3))
    .force("c", d3.forceCollide(d => r(d.t + d.ex) + 3)).stop();
  for (let i = 0; i < 200; i++) sim.tick();
  g.append("g").selectAll("line").data(pts).join("line")
    .attr("x1", d => d.px).attr("y1", d => d.py).attr("x2", d => d.x).attr("y2", d => d.y)
    .attr("stroke", C.ink2).attr("stroke-width", 1);
  g.append("g").selectAll("circle").data(pts).join("circle").attr("cx", d => d.px).attr("cy", d => d.py).attr("r", 2.5).attr("fill", C.ink2);
  const arc = d3.arc().innerRadius(0);
  const pie = d3.pie().sort(null).value(d => d.v);
  const node = g.append("g").selectAll("g").data(pts.sort((a, b) => (b.t + b.ex) - (a.t + a.ex))).join("g")
    .attr("transform", d => `translate(${d.x},${d.y})`)
    .style("cursor", "pointer")
    .on("click", (e, d) => { selected = selected === d.entry ? ALL : d.entry; update(); })
    .on("mousemove", (e, d) => tip.show(e, `<b>${d.entry}</b> (average weekday)<br>Tolled: ${fmtInt(d.t)}<br>
        Excluded roadway: ${fmtInt(d.ex)} (${d3.format(".1f")(100 * d.ex / (d.t + d.ex))}%)<br><i>Click to filter the chart</i>`))
    .on("mouseleave", tip.hide);
  node.append("circle").attr("class", "ring").attr("r", d => r(d.t + d.ex) + 2.5).attr("fill", "#fff");
  node.selectAll("path").data(d => pie([{ k: "t", v: d.t }, { k: "x", v: d.ex }]).map(s => ({ ...s, R: r(d.t + d.ex) })))
    .join("path").attr("d", s => arc.outerRadius(s.R)(s)).attr("fill", s => s.data.k === "t" ? C.blue : C.orange)
    .attr("stroke", "#fff").attr("stroke-width", 1);
  // label side per entry point, chosen by hand to avoid collisions
  const SIDE = { "Brooklyn Bridge": "left", "Hugh L. Carey Tunnel": "right", "Holland Tunnel": "left", "Lincoln Tunnel": "left",
                 "East 60th St": "below", "West 60th St": "left", "West Side Highway at 60th St": "above" };
  node.append("text").attr("class", "map-label")
    .each(function (d) {
      const R = r(d.t + d.ex), side = SIDE[d.entry] || "right", t = d3.select(this);
      if (side === "below" || side === "above") t.attr("x", 0).attr("y", side === "below" ? R + 11 : -R - 5).attr("text-anchor", "middle");
      else t.attr("x", side === "left" ? -R - 5 : R + 5).attr("dy", "0.35em").attr("text-anchor", side === "left" ? "end" : "start");
    })
    .text(d => d.entry.replace(" at 60th St", "").replace("West Side Highway", "West Side Hwy").replace(" Tunnel", " Tun.").replace(" Bridge", " Br."));
  // size legend
  const sl = svg.append("g").attr("transform", `translate(${MW - 112},${MH - 150})`);
  sl.append("rect").attr("x", -8).attr("y", -22).attr("width", 104).attr("height", 120).attr("fill", "#fff").attr("opacity", 0.85).attr("rx", 4);
  sl.append("text").attr("class", "legend-title").attr("y", -8).text("Entries / weekday");
  [80000, 40000, 10000].forEach((v, i) => {
    sl.append("circle").attr("cx", 32).attr("cy", 90 - r(v)).attr("r", r(v)).attr("fill", "none").attr("stroke", C.ink2);
    sl.append("text").attr("x", 68).attr("y", 90 - 2 * r(v) + 4).style("font-size", "10px").attr("fill", C.ink2).text(d3.format(".2~s")(v));
  });
  svg.append("text").attr("x", 10).attr("y", MH - 10).attr("class", "note").text("Dashed line: approximate zone outline");

  // ---------- line chart ----------
  const W = 450, H = 520, M = { top: 40, right: 18, bottom: 40, left: 46 };
  const iw = W - M.left - M.right, ih = H - M.top - M.bottom;
  const ls = makeSvg(lineDiv.node(), W, H).attr("aria-label", "Weekly excluded share");
  const title = ls.append("text").attr("x", M.left).attr("y", 16).attr("class", "chart-subtitle");
  const sub = ls.append("text").attr("x", M.left).attr("y", 32).attr("class", "note");
  const lg = ls.append("g").attr("transform", `translate(${M.left},${M.top})`);
  const x = d3.scaleTime().domain(d3.extent(series, d => d.week)).range([0, iw]);
  const grid = lg.append("g"), yA = lg.append("g");
  lg.append("g").attr("transform", `translate(0,${ih})`).call(d3.axisBottom(x).ticks(6).tickFormat(d3.timeFormat("%b %Y"))).call(axisStyle);
  lg.append("text").attr("transform", "rotate(-90)").attr("x", -ih / 2).attr("y", -36).attr("text-anchor", "middle").attr("class", "axis-label").text("Excluded share of all entries (%)");
  const ref = lg.append("line").attr("stroke", C.ink2).attr("stroke-dasharray", "4 3");
  const refT = lg.append("text").attr("class", "map-label").attr("text-anchor", "start");
  const path = lg.append("path").attr("fill", "none").attr("stroke", C.orange).attr("stroke-width", 2);
  const hover = lg.append("g");

  function update() {
    node.attr("opacity", d => selected === ALL || d.entry === selected ? 1 : 0.35);
    node.select("circle.ring").attr("stroke", d => d.entry === selected ? C.ink : "none").attr("stroke-width", 2);
    const data = series.filter(d => d.entry === selected).sort((a, b) => a.week - b.week);
    const first = d3.mean(data.filter(d => d.week < new Date(2025, 1, 2)), d => d.share);
    const hi = d3.max(data, d => d.share);
    const y = d3.scaleLinear().domain([0, Math.max(hi * 1.15, 1)]).nice().range([ih, 0]);
    grid.call(d3.axisLeft(y).ticks(6).tickSize(-iw)).call(gridStyle);
    yA.transition().call(d3.axisLeft(y).ticks(6).tickFormat(t => t + "%")).call(axisStyle);
    yA.select(".domain").remove();
    path.datum(data).transition().duration(500).attr("d", d3.line().x(d => x(d.week)).y(d => y(d.share)));
    ref.transition().attr("x1", 0).attr("x2", iw).attr("y1", y(first)).attr("y2", y(first));
    refT.transition().attr("x", 4).attr("y", y(first) + 16).text(`Dashed: January 2025 level, ${d3.format(".1f")(first)}%`);
    const last8 = d3.mean(data.slice(-8), d => d.share);
    title.text(selected === ALL ? "All 12 entry points combined" : selected);
    sub.text(hi === 0 ? "No excluded-roadway traffic is recorded at this entry point."
      : `Last 8 weeks: ${d3.format(".1f")(last8)}% (${Math.abs(last8 - first) < 0.05 ? "same as" : d3.format("+.1f")(last8 - first) + " pts vs."} Jan 2025). Click a circle to filter.`);

    lg.selectAll("rect.hit").data([0]).join("rect").attr("class", "hit").attr("width", iw).attr("height", ih).attr("fill", "transparent")
      .on("mousemove", e => {
        const i = d3.bisectCenter(data.map(d => +d.week), +x.invert(d3.pointer(e)[0]));
        const d = data[i];
        hover.selectAll("circle").data([d]).join("circle").attr("r", 4).attr("fill", C.orange).attr("stroke", "#fff").attr("stroke-width", 2)
          .attr("cx", x(d.week)).attr("cy", y(d.share)).attr("pointer-events", "none");
        tip.show(e, `Week of ${fmtDay(d.week)}<br>Excluded share: <b>${d3.format(".1f")(d.share)}%</b><br>Tolled ${fmtInt(d.tolled)} · Excluded ${fmtInt(d.excluded)}`);
      })
      .on("mouseleave", () => { tip.hide(); hover.selectAll("*").remove(); });
  }
  update();
})();
