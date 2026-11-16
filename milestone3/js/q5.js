// Q5. Did traffic or crashes get worse just outside the zone?
// Choropleth of % change in crashes (or injuries) per neighborhood, linked to a ranked bar chart,
// with a callout for the adjacent-area speed change from Q4.
/* global d3, DATA, C, AREA, makeSvg, tip, axisStyle, gridStyle, legend, buttonGroup, loadGeo, baseMap, colorBar, divergingScale, hatch, fmtInt, fmtPct */

(async function q5() {
  const [geo, rows, speeds] = await Promise.all([
    loadGeo(),
    d3.csv(DATA + "q5_nta_crash_change.csv", d => ({
      nta: d.nta_name, borough: d.borough, area: d.area,
      c24: +d.crashes_2024, c25: +d.crashes_2025, i24: +d.injured_2024, i25: +d.injured_2025,
    })),
    d3.csv(DATA + "m2_q4_speeds_monthly.csv", d => ({ year_month: d.year_month, area: d.area, avg_speed_mph: +d.avg_speed_mph })),
  ]);
  rows.forEach(d => { d.crashes = (d.c25 / d.c24 - 1) * 100; d.injured = (d.i25 / d.i24 - 1) * 100; });
  const byName = new Map(rows.map(d => [d.nta, d]));
  let metric = "crashes";
  const LBL = { crashes: "crashes", injured: "people injured" };

  // speed change Jan–Aug 2025 vs Jan–Aug 2024 per area (Q4 data)
  const sp = a => {
    const f = y => d3.mean(speeds.filter(d => d.area === a && String(d.year_month).startsWith(y)
      && +String(d.year_month).slice(5) <= 8), d => d.avg_speed_mph);
    return { s24: f("2024"), s25: f("2025") };
  };
  const adj = sp("adjacent"), ins = sp("inside");

  const root = "#q5-viz";
  const ctl = d3.select(root).append("div").attr("class", "controls");
  buttonGroup(ctl.node(), [{ value: "crashes", label: "Crashes" }, { value: "injured", label: "People injured" }], metric,
    v => { metric = v; update(); });
  const callout = d3.select(root).append("div").attr("class", "callout");
  callout.html(`<b>Traffic speed just outside the zone (Q4 data):</b> taxi/FHV speeds in the adjacent area averaged
    <b>${adj.s25.toFixed(2)} mph</b> in Jan–Aug 2025 vs. ${adj.s24.toFixed(2)} mph in Jan–Aug 2024
    (<b>${(adj.s25 - adj.s24 > 0 ? "+" : "") + (adj.s25 - adj.s24).toFixed(2)} mph</b>); inside the zone they went from
    ${ins.s24.toFixed(2)} to ${ins.s25.toFixed(2)} mph (${(ins.s25 - ins.s24 > 0 ? "+" : "") + (ins.s25 - ins.s24).toFixed(2)} mph).`);

  const wrap = d3.select(root).append("div").attr("class", "two-col");
  const MW = 440, MH = 560;
  const svg = makeSvg(wrap.append("div").attr("class", "col-map").node(), MW, MH).attr("id", "q5map").attr("aria-label", "Choropleth of crash change");
  const noData = hatch(svg, "q5hatch");
  const { ntaSel } = baseMap(svg, geo, { width: MW, height: MH - 60, focus: [[-74.03, 40.685], [-73.925, 40.795]] });
  ntaSel.style("cursor", d => byName.has(d.properties.nta_name) ? "pointer" : null);
  const legendG = svg.append("g");

  const BW = 450, BH = 560, BM = { top: 30, right: 50, bottom: 24, left: 200 };
  const bsvg = makeSvg(wrap.append("div").attr("class", "col-chart").node(), BW, BH).attr("aria-label", "Ranked change per neighborhood");
  const bg = bsvg.append("g").attr("transform", `translate(${BM.left},${BM.top})`);
  const biw = BW - BM.left - BM.right, bih = BH - BM.top - BM.bottom;
  const bTitle = bsvg.append("text").attr("x", 8).attr("y", 14).attr("class", "chart-subtitle");
  legend(root, [{ label: "Inside the zone", color: AREA.inside.color }, { label: "Adjacent (≤ 2 km)", color: AREA.adjacent.color }])
    .append("span").attr("class", "item note").text("(bar-label dot = area; bar color = change)");

  let hovered = null;
  function highlight(name) {
    hovered = name;
    ntaSel.attr("stroke", d => d.properties.nta_name === name ? C.ink : "#fff")
      .attr("stroke-width", d => d.properties.nta_name === name ? 2 : 0.6);
    ntaSel.filter(d => d.properties.nta_name === name).raise();
    bg.selectAll("g.row").attr("opacity", d => !name || d.nta === name ? 1 : 0.45);
  }
  const html = d => `<b>${d.nta}</b> (${d.borough}, ${d.area === "inside" ? "inside the zone" : "adjacent"})<br>
      Crashes: ${fmtInt(d.c24)} → ${fmtInt(d.c25)} (${fmtPct(d.crashes)})<br>
      Injured: ${fmtInt(d.i24)} → ${fmtInt(d.i25)} (${fmtPct(d.injured)})`;

  function update() {
    const m = Math.ceil(d3.max(rows, d => Math.abs(d[metric])) / 5) * 5;
    const color = divergingScale(m, false); // more crashes = red
    ntaSel.attr("fill", d => {
      const r = byName.get(d.properties.nta_name);
      return r ? color(r[metric]) : (d.properties.borough === "Manhattan" ? noData : C.land);
    })
      .on("mousemove", (e, d) => { const r = byName.get(d.properties.nta_name); if (r) { tip.show(e, html(r)); highlight(r.nta); } })
      .on("mouseleave", () => { tip.hide(); highlight(null); });
    legendG.selectAll("*").remove();
    colorBar(legendG, { x: 20, y: MH - 34, width: 260, color, domain: [-m, m], title: `Change in ${LBL[metric]}, 2025 vs. 2024 (same months)` });

    const sorted = rows.slice().sort((a, b) => b[metric] - a[metric]);
    const y = d3.scaleBand().domain(sorted.map(d => d.nta)).range([0, bih]).padding(0.18);
    const x = d3.scaleLinear().domain([-m, m]).range([0, biw]);
    bTitle.text(`Neighborhoods ranked by change in ${LBL[metric]}`);
    bg.selectAll("g.axis").data([0]).join("g").attr("class", "axis").attr("transform", `translate(0,${bih})`)
      .call(d3.axisBottom(x).ticks(5).tickFormat(t => (t > 0 ? "+" : "") + t + "%")).call(axisStyle);
    bg.selectAll("line.zero").data([0]).join("line").attr("class", "zero").attr("x1", x(0)).attr("x2", x(0)).attr("y1", 0).attr("y2", bih).attr("stroke", C.ink2);
    const row = bg.selectAll("g.row").data(sorted, d => d.nta).join(enter => {
      const r = enter.append("g").attr("class", "row");
      r.append("rect").attr("class", "hit").attr("x", -BM.left).attr("width", BW).attr("fill", "transparent");
      r.append("rect").attr("class", "bar").attr("rx", 2);
      r.append("circle").attr("r", 4);
      r.append("text").attr("class", "lbl").attr("x", -16).attr("dy", "0.35em").attr("text-anchor", "end").style("font-size", "10.5px").attr("fill", C.ink2);
      return r;
    });
    row.on("mousemove", (e, d) => { tip.show(e, html(d)); highlight(d.nta); }).on("mouseleave", () => { tip.hide(); highlight(null); });
    row.transition().duration(500).attr("transform", d => `translate(0,${y(d.nta)})`);
    row.select("rect.hit").attr("height", y.step());
    row.select("rect.bar").transition().duration(500).attr("x", d => x(Math.min(0, d[metric]))).attr("width", d => Math.abs(x(d[metric]) - x(0)))
      .attr("height", y.bandwidth()).attr("fill", d => color(d[metric]));
    row.select("circle").attr("cx", -8).attr("cy", y.bandwidth() / 2).attr("fill", d => AREA[d.area].color);
    row.select("text.lbl").attr("y", y.bandwidth() / 2).text(d => d.nta.length > 30 ? d.nta.slice(0, 29) + "…" : d.nta);
    highlight(hovered);
  }
  update();
})();
