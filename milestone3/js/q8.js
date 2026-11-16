// Q8. Putting everything together: which areas gained the most and which carried the costs?
// Matrix heatmap (neighborhood × benefit metric, signed so blue = better, red = worse) linked to a map.
/* global d3, DATA, C, AREA, makeSvg, tip, axisStyle, legend, selectBox, loadGeo, baseMap, colorBar, divergingScale, hatch, fmtPct */

(async function q8() {
  const [geo, rows] = await Promise.all([
    loadGeo(),
    d3.csv(DATA + "q8_nta_summary.csv", d => {
      const n = v => v === "" ? null : +v;
      return {
        nta: d.nta_name, borough: d.borough, area: d.area,
        safety: n(d.safety_benefit), bike: n(d.citibike_benefit), subway: n(d.subway_benefit), speed: n(d.speed_benefit),
        raw: { safety: n(d.crash_change_pct), bike: n(d.citibike_change_pct), subway: n(d.subway_change_pct), speed: n(d.speed_change_mph) },
      };
    }),
  ]);
  const COLS = [
    { key: "safety", label: "Safety", sub: "fewer crashes", desc: "Crashes, 2025 vs. 2024 (same months)", unit: "%" },
    { key: "subway", label: "Subway use", sub: "entries", desc: "Subway entries at stations in the neighborhood, 2025 vs. 2024", unit: "%" },
    { key: "bike", label: "Citi Bike", sub: "trips to zone", desc: "Citi Bike trips from here into the zone, Oct 2025 vs. Oct 2024", unit: "%" },
    { key: "speed", label: "Speed", sub: "taxi/FHV", desc: "Average taxi/FHV speed, Jan–Aug 2025 vs. 2024 (one value per area)", unit: " mph" },
  ];
  // Each column on its own scale (units differ); clip at the 90th percentile of |value| so one outlier doesn't wash out the rest
  COLS.forEach(c => {
    const m = d3.quantile(rows.map(r => Math.abs(r[c.key])).filter(v => v != null).sort(d3.ascending), 0.9);
    c.max = c.key === "speed" ? 0.3 : Math.ceil(m / 5) * 5;
    c.color = divergingScale(c.max, true);
  });
  const fmtVal = (c, v) => v == null ? "–" : c.unit === "%" ? (v > 0 ? "+" : "") + v.toFixed(0) : (v > 0 ? "+" : "") + v.toFixed(2);
  let sortKey = "safety", mapKey = "safety", borough = "All", hovered = null;

  const root = "#q8-viz";
  const ctl = d3.select(root).append("div").attr("class", "controls");
  selectBox(ctl.node(), "Borough:", ["All", ...new Set(rows.map(d => d.borough))].map(b => ({ value: b, label: b })), borough,
    v => { borough = v; draw(); });
  ctl.append("span").attr("class", "note").text("Click a column header to sort by it and color the map with it.");

  const wrap = d3.select(root).append("div").attr("class", "two-col");
  const W = 520, cellW = 66, cellH = 15, M = { top: 64, left: 214 };
  const svg = makeSvg(wrap.append("div").attr("class", "col-chart").node(), W, M.top + (rows.length + 3) * cellH + 30)
    .attr("aria-label", "Benefit matrix");
  const noData = hatch(svg, "q8hatch");
  const g = svg.append("g").attr("transform", `translate(${M.left},${M.top})`);
  const head = g.append("g");
  const body = g.append("g");

  const MW = 400, MH = 560;
  const msvg = makeSvg(wrap.append("div").attr("class", "col-map").node(), MW, MH).attr("id", "q8map").attr("aria-label", "Map of selected metric");
  const mHatch = hatch(msvg, "q8mhatch");
  const { ntaSel } = baseMap(msvg, geo, { width: MW, height: MH - 70, focus: [[-74.025, 40.69], [-73.925, 40.79]] });
  const mTitle = msvg.append("text").attr("x", 10).attr("y", MH - 54).attr("class", "chart-subtitle");
  const mLegend = msvg.append("g");
  const byName = new Map(rows.map(d => [d.nta, d]));

  function hi(name) {
    hovered = name;
    body.selectAll("g.row").attr("opacity", d => !name || d.nta === name ? 1 : 0.5);
    ntaSel.attr("stroke", d => d.properties.nta_name === name ? C.ink : "#fff").attr("stroke-width", d => d.properties.nta_name === name ? 2 : 0.6);
    ntaSel.filter(d => d.properties.nta_name === name).raise();
  }
  const rowTip = d => `<b>${d.nta}</b> (${d.borough}, ${d.area === "inside" ? "inside the zone" : "adjacent"})<br>` +
    COLS.map(c => `${c.label}: ${d.raw[c.key] == null ? "no data" : c.key === "safety" ? `crashes ${fmtPct(d.raw.safety)}`
      : c.unit === "%" ? fmtPct(d.raw[c.key]) : (d.raw[c.key] > 0 ? "+" : "") + d.raw[c.key].toFixed(2) + " mph"}`).join("<br>");

  function draw() {
    const vis = rows.filter(d => borough === "All" || d.borough === borough);
    const groups = ["inside", "adjacent"].map(a => [a, vis.filter(d => d.area === a)
      .sort((p, q) => (q[sortKey] ?? -1e9) - (p[sortKey] ?? -1e9))]).filter(gp => gp[1].length);
    // layout: rows with a header line per group
    let yy = 0;
    const layout = [];
    groups.forEach(([a, list]) => { layout.push({ header: a, y: yy }); yy += cellH + 4; list.forEach(d => { layout.push({ d, y: yy }); yy += cellH; }); yy += 8; });

    head.selectAll("g.h").data(COLS, c => c.key).join(en => {
      const h = en.append("g").attr("class", "h").style("cursor", "pointer");
      h.append("rect").attr("y", -58).attr("height", 54).attr("width", cellW - 2).attr("rx", 3);
      h.append("text").attr("class", "t1").attr("x", cellW / 2).attr("y", -36).attr("text-anchor", "middle").style("font-size", "11.5px").style("font-weight", 600);
      h.append("text").attr("class", "t2").attr("x", cellW / 2).attr("y", -22).attr("text-anchor", "middle").style("font-size", "9.5px").attr("fill", C.ink2);
      h.append("text").attr("class", "t3").attr("x", cellW / 2).attr("y", -9).attr("text-anchor", "middle").style("font-size", "10px").attr("fill", C.ink2);
      return h;
    }).attr("transform", (c, i) => `translate(${i * cellW},0)`)
      .on("click", (e, c) => { sortKey = c.key; mapKey = c.key; draw(); })
      .on("mousemove", (e, c) => tip.show(e, `<b>${c.label}</b><br>${c.desc}<br>Blue = better for the neighborhood, red = worse.<br>Color saturates at ±${c.max}${c.unit}.`))
      .on("mouseleave", tip.hide)
      .call(h => {
        h.select("rect").attr("fill", c => c.key === sortKey ? "#cde2fb" : "transparent");
        h.select(".t1").text(c => c.label);
        h.select(".t2").text(c => c.sub);
        h.select(".t3").text(c => (c.key === sortKey ? "▼ " : "") + (c.unit === "%" ? "%" : "mph"));
      });

    body.selectAll("text.gh").data(layout.filter(l => l.header), l => l.header).join("text").attr("class", "gh")
      .attr("x", -M.left + 4).attr("dy", "0.9em").style("font-size", "11px").style("font-weight", 700).attr("fill", l => AREA[l.header].color === C.blue ? "#1c5cab" : "#a8481f")
      .transition().duration(400).attr("y", l => l.y).text(l => l.header === "inside" ? "INSIDE THE ZONE" : "ADJACENT (WITHIN 2 KM)");

    const rowsL = layout.filter(l => l.d);
    const row = body.selectAll("g.row").data(rowsL, l => l.d.nta).join(en => {
      const r = en.append("g").attr("class", "row").attr("opacity", 0);
      r.append("rect").attr("class", "hit").attr("x", -M.left).attr("width", M.left + COLS.length * cellW).attr("height", cellH).attr("fill", "transparent");
      r.append("text").attr("class", "lbl").attr("x", -8).attr("y", cellH / 2).attr("dy", "0.35em").attr("text-anchor", "end").style("font-size", "10.5px").attr("fill", C.ink);
      COLS.forEach((c, i) => {
        r.append("rect").attr("class", "cell c-" + c.key).attr("x", i * cellW).attr("width", cellW - 2).attr("height", cellH - 2).attr("rx", 2);
        r.append("text").attr("class", "cv cv-" + c.key).attr("x", i * cellW + cellW / 2 - 1).attr("y", cellH / 2 - 1).attr("dy", "0.35em").attr("text-anchor", "middle").style("font-size", "9.5px");
      });
      return r;
    });
    row.transition().duration(400).attr("opacity", 1).attr("transform", l => `translate(0,${l.y})`);
    row.select("text.lbl").text(l => l.d.nta.length > 31 ? l.d.nta.slice(0, 30) + "…" : l.d.nta);
    COLS.forEach(c => {
      row.select(".c-" + c.key).attr("fill", l => l.d[c.key] == null ? noData : c.color(l.d[c.key]));
      row.select(".cv-" + c.key).text(l => fmtVal(c, l.d[c.key]))
        .attr("fill", l => l.d[c.key] != null && Math.abs(l.d[c.key]) > c.max * 0.6 ? "#fff" : C.ink);
    });
    row.on("mousemove", (e, l) => { tip.show(e, rowTip(l.d)); hi(l.d.nta); }).on("mouseleave", () => { tip.hide(); hi(null); });
    svg.attr("viewBox", `0 0 ${W} ${M.top + yy + 10}`);

    // linked map
    const col = COLS.find(c => c.key === mapKey);
    const visSet = new Set(vis.map(d => d.nta));
    ntaSel.attr("fill", f => {
      const r = byName.get(f.properties.nta_name);
      if (!r || !visSet.has(r.nta)) return C.land;
      return r[mapKey] == null ? mHatch : col.color(r[mapKey]);
    }).style("cursor", f => byName.has(f.properties.nta_name) ? "pointer" : null)
      .on("mousemove", (e, f) => { const r = byName.get(f.properties.nta_name); if (r) { tip.show(e, rowTip(r)); hi(r.nta); } })
      .on("mouseleave", () => { tip.hide(); hi(null); });
    mTitle.text(`Map: ${col.label} (${col.sub})`);
    mLegend.selectAll("*").remove();
    colorBar(mLegend, { x: 10, y: MH - 26, width: 240, color: col.color, domain: [-col.max, col.max], title: "",
      tickFormat: v => (v > 0 ? "+" : "") + (col.unit === "%" ? v + "%" : v.toFixed(1)), ticks: 5 });
    mLegend.append("text").attr("x", 10).attr("y", MH - 30).attr("class", "note").text("← cost");
    mLegend.append("text").attr("x", 250).attr("y", MH - 30).attr("text-anchor", "end").attr("class", "note").text("benefit →");
    hi(hovered);
  }
  draw();
})();
