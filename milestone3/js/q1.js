// Q1. When and where do vehicles enter the zone on a typical weekday?
// Heatmap (entry point × hour) + marginal bars (daily total) + hourly profile of the selected entry point.
/* global d3, DATA, C, makeSvg, tip, axisStyle, gridStyle, legend, colorBar, seqBlue, buttonGroup, fmtInt */

(async function q1() {
  const rows = await d3.csv(DATA + "q1_weekday_profile.csv", d => ({
    entry: d.entry_point, hour: +d.hour,
    tolled: +d.avg_weekday_entries, excluded: +d.avg_excluded_entries,
  }));

  const root = "#q1-viz";
  let metric = "tolled";
  let selected = null;

  const controls = d3.select(root).append("div").attr("class", "controls");
  buttonGroup(controls.node(), [
    { value: "tolled", label: "Tolled entries" },
    { value: "excluded", label: "Excluded-roadway entries" },
    { value: "total", label: "Both" },
  ], metric, v => { metric = v; draw(); });

  const val = d => metric === "total" ? d.tolled + d.excluded : d[metric];

  const W = 900, H = 470;
  const M = { top: 40, right: 190, bottom: 36, left: 190 };
  const iw = W - M.left - M.right, ih = H - M.top - M.bottom;
  const svg = makeSvg(root, W, H).attr("aria-label", "Heatmap of average weekday entries by entry point and hour");
  const g = svg.append("g").attr("transform", `translate(${M.left},${M.top})`);
  const gx = g.append("g").attr("transform", `translate(0,${ih})`);
  const gy = g.append("g");
  const cells = g.append("g");
  const bars = g.append("g").attr("transform", `translate(${iw + 14},0)`);
  const barAxis = bars.append("g");
  const legendG = svg.append("g");
  g.append("text").attr("x", iw / 2).attr("y", ih + 32).attr("text-anchor", "middle").attr("class", "axis-label")
    .text("Hour of day (weekday average, Jan 2025 – Oct 2026)");
  bars.append("text").attr("x", 0).attr("y", -10).attr("class", "axis-label").text("Daily total per weekday");

  // hourly profile of the selected row
  const PH = 230, PM = { top: 26, right: 30, bottom: 34, left: 70 };
  const psvg = makeSvg(root, W, PH).attr("aria-label", "Hourly profile of the selected entry point");
  const pg = psvg.append("g").attr("transform", `translate(${PM.left},${PM.top})`);
  const piw = W - PM.left - PM.right, pih = PH - PM.top - PM.bottom;
  const pTitle = psvg.append("text").attr("x", PM.left).attr("y", 16).attr("class", "chart-subtitle");
  const px = d3.scaleLinear().domain([0, 23]).range([0, piw]);
  const pyGrid = pg.append("g"), pyAxis = pg.append("g");
  pg.append("g").attr("transform", `translate(0,${pih})`)
    .call(d3.axisBottom(px).ticks(24).tickFormat(h => h % 3 === 0 ? (h === 0 ? "12a" : h < 12 ? h + "a" : h === 12 ? "12p" : (h - 12) + "p") : ""))
    .call(axisStyle);
  const avgLine = pg.append("path").attr("fill", "none").attr("stroke", C.muted).attr("stroke-width", 2).attr("stroke-dasharray", "4 3");
  const selLine = pg.append("path").attr("fill", "none").attr("stroke", C.blue).attr("stroke-width", 2);
  const dots = pg.append("g");
  d3.select(root).append("div").attr("class", "legend-holder").call(s => legend(s.node(), [
    { label: "Selected entry point", color: C.blue, type: "line" },
    { label: "Average of all 12 entry points", color: C.muted, type: "dash" },
  ]));

  function draw() {
    const totals = d3.rollup(rows, v => d3.sum(v, val), d => d.entry);
    const order = [...totals.keys()].sort((a, b) => totals.get(b) - totals.get(a));
    if (!selected || !order.includes(selected)) selected = order[0];
    const x = d3.scaleBand().domain(d3.range(24)).range([0, iw]).padding(0.04);
    const y = d3.scaleBand().domain(order).range([0, ih]).padding(0.08);
    const max = d3.max(rows, val) || 1;
    const color = d3.scaleSequential(seqBlue).domain([0, max]);

    gx.call(d3.axisBottom(x).tickValues([0, 3, 6, 9, 12, 15, 18, 21])
      .tickFormat(h => h === 0 ? "12 a.m." : h < 12 ? h + " a.m." : h === 12 ? "12 p.m." : (h - 12) + " p.m."))
      .call(axisStyle).call(a => a.select(".domain").remove());
    gy.transition().duration(500).call(d3.axisLeft(y).tickSize(0)).call(axisStyle);
    gy.select(".domain").remove();
    gy.selectAll(".tick text").attr("dx", -4).style("font-size", "12px").style("cursor", "pointer")
      .style("font-weight", d => d === selected ? 700 : 400)
      .on("click", (e, d) => { selected = d; draw(); });

    cells.selectAll("rect").data(rows, d => d.entry + d.hour).join("rect")
      .attr("rx", 2)
      .on("mousemove", (e, d) => tip.show(e,
        `<b>${d.entry}</b><br>${d.hour}:00–${d.hour}:59 on an average weekday<br>
         Tolled: <b>${fmtInt(d.tolled)}</b><br>Excluded roadway: <b>${fmtInt(d.excluded)}</b>`))
      .on("mouseleave", tip.hide)
      .on("click", (e, d) => { selected = d.entry; draw(); })
      .transition().duration(500)
      .attr("x", d => x(d.hour)).attr("y", d => y(d.entry))
      .attr("width", x.bandwidth()).attr("height", y.bandwidth())
      .attr("fill", d => val(d) === 0 ? C.neutral : color(val(d)))
      .attr("stroke", d => d.entry === selected ? C.ink : "none").attr("stroke-width", 1);

    // marginal bars
    const bx = d3.scaleLinear().domain([0, d3.max(totals.values()) || 1]).range([0, M.right - 70]);
    bars.selectAll("rect").data(order, d => d).join("rect")
      .attr("rx", 2).attr("fill", d => d === selected ? C.blue : "#9ec5f4")
      .on("mousemove", (e, d) => tip.show(e, `<b>${d}</b><br>${fmtInt(totals.get(d))} per weekday`))
      .on("mouseleave", tip.hide)
      .on("click", (e, d) => { selected = d; draw(); })
      .transition().duration(500)
      .attr("y", d => y(d)).attr("height", y.bandwidth()).attr("x", 0).attr("width", d => bx(totals.get(d)));
    bars.selectAll("text.v").data(order, d => d).join("text").attr("class", "v")
      .attr("dy", "0.35em").style("font-size", "11px").attr("fill", C.ink2)
      .transition().duration(500)
      .attr("y", d => y(d) + y.bandwidth() / 2).attr("x", d => bx(totals.get(d)) + 4)
      .text(d => d3.format(".3~s")(totals.get(d)));

    legendG.selectAll("*").remove();
    colorBar(legendG, {
      x: M.left, y: 18, width: 240, color, domain: [0, max],
      title: "Average entries per hour", tickFormat: d3.format(".2~s"), ticks: 4,
    });

    // profile
    const sel = rows.filter(d => d.entry === selected).sort((a, b) => a.hour - b.hour);
    const avg = d3.range(24).map(h => ({ hour: h, v: d3.mean(rows.filter(d => d.hour === h), val) }));
    const py = d3.scaleLinear().domain([0, d3.max([...sel.map(val), ...avg.map(d => d.v)]) * 1.08 || 1]).nice().range([pih, 0]);
    pyGrid.call(d3.axisLeft(py).ticks(5).tickSize(-piw)).call(gridStyle);
    pyAxis.call(d3.axisLeft(py).ticks(5).tickFormat(d3.format(".2~s"))).call(axisStyle).call(a => a.select(".domain").remove());
    const line = d3.line().x(d => px(d.hour)).curve(d3.curveMonotoneX);
    avgLine.datum(avg).transition().duration(400).attr("d", line.y(d => py(d.v)));
    selLine.datum(sel).transition().duration(400).attr("d", d3.line().x(d => px(d.hour)).y(d => py(val(d))).curve(d3.curveMonotoneX));
    dots.selectAll("circle").data(sel).join("circle").attr("r", 4).attr("fill", C.blue)
      .attr("stroke", C.surface).attr("stroke-width", 2)
      .on("mousemove", (e, d) => tip.show(e, `<b>${d.entry}</b>, ${d.hour}:00<br>${fmtInt(val(d))} entries<br>All-entry-point average: ${fmtInt(avg[d.hour].v)}`))
      .on("mouseleave", tip.hide)
      .transition().duration(400).attr("cx", d => px(d.hour)).attr("cy", d => py(val(d)));
    const pk = sel.reduce((a, b) => (val(b) > val(a) ? b : a), sel[0]);
    pTitle.text(`Hourly profile: ${selected} (peak hour ${pk.hour}:00, ${fmtInt(val(pk))} entries). Click any row above to change.`);
  }
  draw();
})();
