// Q6. Did more people take the subway or Citi Bike into the zone, and from which neighborhoods?
// (a) Origin map: % change in trips INTO the zone by origin neighborhood (Oct 2024 vs Oct 2025),
//     subway (MTA origin–destination estimates) or Citi Bike (trip records); click to draw the flow.
// (b) Bars of the biggest gains / losses. (c) Station-entry trend by area (all subway fare entries).
/* global d3, DATA, C, AREA, makeSvg, tip, axisStyle, gridStyle, legend, buttonGroup, loadGeo, baseMap, colorBar, divergingScale, hatch, fmtInt, fmtPct, parseYM, fmtMonth */

(async function q6() {
  const [geo, od, bike, areaTrend] = await Promise.all([
    loadGeo(),
    d3.csv(DATA + "q6_subway_od_into_zone.csv", d => ({
      nta: d.nta, borough: d.borough, a: +d.avg_weekday_riders_oct2024, b: +d.avg_weekday_riders_oct2025,
    })),
    d3.csv(DATA + "q6_citibike_origins.csv", d => ({
      nta: d.origin_nta, borough: d.origin_borough, area: d.origin_area,
      a: +d.trips_into_zone_202410, b: +d.trips_into_zone_202510,
    })),
    d3.csv(DATA + "q6_subway_by_area.csv", d => ({ month: parseYM(d.year_month), area: d.area, pct: +d.pct_change, e: +d.entries, p: +d.entries_same_month_2024 })),
  ]);
  const MODES = {
    subway: { rows: od, min: 200, unit: "average weekday riders", label: "Subway",
      src: "MTA subway origin–destination estimates; riders whose trip ends at a station inside the zone" },
    bike: { rows: bike, min: 100, unit: "trips", label: "Citi Bike",
      src: "Citi Bike trip records; trips that end at a dock inside the zone" },
  };
  Object.values(MODES).forEach(m => m.rows.forEach(d => { d.chg = d.b - d.a; d.pct = d.a > 0 ? (d.b / d.a - 1) * 100 : null; }));
  let mode = "subway", selected = null;

  const root = "#q6-viz";
  const ctl = d3.select(root).append("div").attr("class", "controls");
  buttonGroup(ctl.node(), [{ value: "subway", label: "Subway" }, { value: "bike", label: "Citi Bike" }], mode,
    v => { mode = v; selected = null; update(); });
  const summary = d3.select(root).append("div").attr("class", "callout");

  const wrap = d3.select(root).append("div").attr("class", "two-col");
  const MW = 470, MH = 560;
  const svg = makeSvg(wrap.append("div").attr("class", "col-map").node(), MW, MH).attr("id", "q6map").attr("aria-label", "Origin map");
  const few = hatch(svg, "q6hatch");
  const { g, path, projection, ntaSel } = baseMap(svg, geo, { width: MW, height: MH - 56, focus: [[-74.06, 40.57], [-73.75, 40.915]] });
  const zoneC = projection(d3.geoCentroid(geo.zone.features[0]));
  const flowG = g.append("g");
  const legendG = svg.append("g");

  const BW = 430, BH = 560, BM = { top: 34, right: 56, bottom: 26, left: 190 };
  const bsvg = makeSvg(wrap.append("div").attr("class", "col-chart").node(), BW, BH).attr("aria-label", "Largest changes");
  const bg = bsvg.append("g").attr("transform", `translate(${BM.left},${BM.top})`);
  const biw = BW - BM.left - BM.right, bih = BH - BM.top - BM.bottom;
  const bTitle = bsvg.append("text").attr("x", 8).attr("y", 14).attr("class", "chart-subtitle");
  const bSub = bsvg.append("text").attr("x", 8).attr("y", 28).attr("class", "note");

  function drawFlow(d, M) {
    flowG.selectAll("*").remove();
    if (!d) return;
    const f = geo.nta.features.find(n => n.properties.nta_name === d.nta);
    const s = path.centroid(f);
    const mx = (s[0] + zoneC[0]) / 2 - (zoneC[1] - s[1]) * 0.25, my = (s[1] + zoneC[1]) / 2 + (zoneC[0] - s[0]) * 0.25;
    const w = d3.scaleSqrt().domain([0, d3.max(M.rows, r => r.b)]).range([1.5, 10])(d.b);
    flowG.append("path").attr("d", `M${s[0]},${s[1]} Q${mx},${my} ${zoneC[0]},${zoneC[1]}`)
      .attr("fill", "none").attr("stroke", C.ink).attr("stroke-width", w).attr("stroke-linecap", "round").attr("opacity", 0.75);
    flowG.append("circle").attr("cx", s[0]).attr("cy", s[1]).attr("r", 4).attr("fill", C.ink);
    flowG.append("circle").attr("cx", zoneC[0]).attr("cy", zoneC[1]).attr("r", 5).attr("fill", "#fff").attr("stroke", C.ink).attr("stroke-width", 2);
    flowG.append("text").attr("x", s[0] + 6).attr("y", s[1] - 6).attr("class", "map-label strong")
      .text(`${d.nta}: ${fmtInt(d.b)} ${M.unit} (${fmtPct(d.pct)})`)
      .attr("text-anchor", s[0] > MW * 0.55 ? "end" : "start").attr("x", s[0] > MW * 0.55 ? s[0] - 6 : s[0] + 6);
  }

  function update() {
    const M = MODES[mode];
    const by = new Map(M.rows.map(d => [d.nta, d]));
    const big = M.rows.filter(d => d.a >= M.min);
    const m = 30;
    const color = divergingScale(m, true); // growth = blue, decline = red
    const totA = d3.sum(M.rows, d => d.a), totB = d3.sum(M.rows, d => d.b);
    const outA = d3.sum(M.rows.filter(d => d.area !== "inside"), d => d.a), outB = d3.sum(M.rows.filter(d => d.area !== "inside"), d => d.b);
    summary.html(`<b>${M.label}, October 2024 → October 2025.</b> ${M.src}.<br>Total into the zone: ${fmtInt(totA)} → ${fmtInt(totB)} ${M.unit}
      (<b>${fmtPct((totB / totA - 1) * 100)}</b>)` + (mode === "bike" ? `; from outside the zone only: ${fmtInt(outA)} → ${fmtInt(outB)} (<b>${fmtPct((outB / outA - 1) * 100)}</b>).` : "."));

    ntaSel.attr("fill", d => {
      const r = by.get(d.properties.nta_name);
      if (!r) return C.land;
      return r.a < M.min ? few : color(r.pct);
    }).style("cursor", d => by.has(d.properties.nta_name) ? "pointer" : null)
      .on("mousemove", (e, d) => {
        const r = by.get(d.properties.nta_name);
        if (!r) return tip.hide();
        tip.show(e, `<b>${r.nta}</b> (${r.borough})<br>${M.label} ${M.unit} into the zone:<br>Oct 2024: ${fmtInt(r.a)}<br>Oct 2025: ${fmtInt(r.b)}
          <br><b>${fmtSigned(r.chg)} (${fmtPct(r.pct)})</b>${r.a < M.min ? "<br><i>Too few trips to color reliably</i>" : ""}<br><i>Click to draw the flow</i>`);
      })
      .on("mouseleave", tip.hide)
      .on("click", (e, d) => { const r = by.get(d.properties.nta_name); if (r) { selected = r.nta; drawFlow(r, M); } });
    drawFlow(selected ? by.get(selected) : null, M);
    legendG.selectAll("*").remove();
    colorBar(legendG, { x: 20, y: MH - 32, width: 240, color, domain: [-m, m], title: `% change in ${M.label} ${M.unit} into the zone` });
    legendG.append("rect").attr("x", 300).attr("y", MH - 32).attr("width", 14).attr("height", 10).attr("fill", few);
    legendG.append("text").attr("x", 318).attr("y", MH - 23).attr("class", "note").text(`< ${M.min} in Oct 2024`);

    // bars: 9 largest gains + 9 largest losses (absolute change)
    // Citi Bike: list only origins outside the zone (trips that start inside it are within-zone trips)
    const srt = M.rows.filter(d => d.area !== "inside").sort((a, b) => b.chg - a.chg);
    const list = [...srt.slice(0, 9), ...srt.slice(-9)];
    const y = d3.scaleBand().domain(list.map(d => d.nta)).range([0, bih]).padding(0.2);
    const mx = d3.max(list, d => Math.abs(d.chg));
    const x = d3.scaleLinear().domain([-mx, mx]).nice().range([0, biw]);
    bTitle.text(`Largest gains and losses (${M.unit}${mode === "bike" ? ", origins outside the zone" : ""})`);
    bSub.text("Click a bar to draw that neighborhood's flow on the map");
    bg.selectAll("g.ax").data([0]).join("g").attr("class", "ax").attr("transform", `translate(0,${bih})`)
      .call(d3.axisBottom(x).ticks(4).tickFormat(d3.format("+.2~s"))).call(axisStyle);
    bg.selectAll("line.z").data([0]).join("line").attr("class", "z").attr("y1", 0).attr("y2", bih).attr("stroke", C.ink2).attr("x1", x(0)).attr("x2", x(0));
    bg.selectAll("line.sep").data([0]).join("line").attr("class", "sep").attr("x1", -BM.left + 8).attr("x2", biw)
      .attr("y1", y(list[9].nta) - y.step() * y.padding() / 2 - 1).attr("y2", y(list[9].nta) - y.step() * y.padding() / 2 - 1).attr("stroke", C.grid);
    const row = bg.selectAll("g.row").data(list, d => d.nta).join(en => {
      const r = en.append("g").attr("class", "row").style("cursor", "pointer");
      r.append("rect").attr("class", "bar").attr("rx", 2);
      r.append("text").attr("class", "lbl").attr("x", -8).attr("text-anchor", "end").attr("dy", "0.35em").style("font-size", "10.5px").attr("fill", C.ink2);
      r.append("text").attr("class", "val").attr("dy", "0.35em").style("font-size", "10px").attr("fill", C.ink2);
      return r;
    });
    row.attr("transform", d => `translate(0,${y(d.nta)})`)
      .on("click", (e, d) => { selected = d.nta; drawFlow(d, M); })
      .on("mousemove", (e, d) => tip.show(e, `<b>${d.nta}</b><br>${fmtInt(d.a)} → ${fmtInt(d.b)} ${M.unit} (${fmtPct(d.pct)})`))
      .on("mouseleave", tip.hide);
    row.select("rect.bar").attr("height", y.bandwidth()).transition().duration(400)
      .attr("x", d => x(Math.min(0, d.chg))).attr("width", d => Math.abs(x(d.chg) - x(0)))
      .attr("fill", d => d.chg >= 0 ? "#3987e5" : "#e66767");
    row.select("text.lbl").attr("y", y.bandwidth() / 2).text(d => d.nta.length > 28 ? d.nta.slice(0, 27) + "…" : d.nta);
    row.select("text.val").attr("y", y.bandwidth() / 2)
      .attr("x", d => d.chg >= 0 ? x(d.chg) + 3 : x(0) + 3).attr("text-anchor", "start")
      .text(d => d3.format("+,.0f")(d.chg));
  }
  update();

  // ---------- (c) subway station entries by area, each month vs. same month of 2024 ----------
  const root2 = "#q6-viz-trend";
  const areas = ["inside", "adjacent", "elsewhere"];
  legend(root2, areas.map(a => ({ label: AREA[a].label + (a === "inside" ? " (stations in the zone)" : ""), color: AREA[a].color, type: "line" })));
  const W = 900, H = 250, Mg = { top: 14, right: 20, bottom: 30, left: 50 };
  const iw = W - Mg.left - Mg.right, ih = H - Mg.top - Mg.bottom;
  const s3 = makeSvg(root2, W, H).attr("aria-label", "Subway entries change by area");
  const g3 = s3.append("g").attr("transform", `translate(${Mg.left},${Mg.top})`);
  const x = d3.scaleTime().domain(d3.extent(areaTrend, d => d.month)).range([0, iw]);
  const y = d3.scaleLinear().domain([Math.min(0, d3.min(areaTrend, d => d.pct)), d3.max(areaTrend, d => d.pct)]).nice().range([ih, 0]);
  g3.append("g").call(d3.axisLeft(y).ticks(5).tickSize(-iw)).call(gridStyle);
  g3.append("g").call(d3.axisLeft(y).ticks(5).tickFormat(t => (t > 0 ? "+" : "") + t + "%")).call(axisStyle).call(a => a.select(".domain").remove());
  g3.append("g").attr("transform", `translate(0,${ih})`).call(d3.axisBottom(x).ticks(8).tickFormat(d3.timeFormat("%b %Y"))).call(axisStyle);
  g3.append("line").attr("x1", 0).attr("x2", iw).attr("y1", y(0)).attr("y2", y(0)).attr("stroke", C.ink2);
  g3.append("text").attr("transform", "rotate(-90)").attr("x", -ih / 2).attr("y", -38).attr("text-anchor", "middle").attr("class", "axis-label").text("vs. same month of 2024");
  g3.selectAll("path.l").data(d3.groups(areaTrend, d => d.area)).join("path").attr("class", "l")
    .attr("fill", "none").attr("stroke-width", 2).attr("stroke", d => AREA[d[0]].color)
    .attr("d", d => d3.line().x(r => x(r.month)).y(r => y(r.pct))(d[1].sort((a, b) => a.month - b.month)));
  const hv = g3.append("g");
  g3.append("rect").attr("width", iw).attr("height", ih).attr("fill", "transparent")
    .on("mousemove", e => {
      const ms = [...new Set(areaTrend.map(d => +d.month))].sort((a, b) => a - b);
      const mm = ms[d3.bisectCenter(ms, +x.invert(d3.pointer(e)[0]))];
      const at = areas.map(a => areaTrend.find(d => d.area === a && +d.month === mm)).filter(Boolean);
      hv.selectAll("circle").data(at).join("circle").attr("r", 4).attr("cx", x(mm)).attr("cy", d => y(d.pct)).attr("fill", d => AREA[d.area].color).attr("stroke", "#fff").attr("stroke-width", 2);
      tip.show(e, `<b>${fmtMonth(new Date(mm))}</b><br>` + at.map(d => `${AREA[d.area].label}: <b>${fmtPct(d.pct)}</b> (${d3.format(".3~s")(d.e)} entries)`).join("<br>"));
    })
    .on("mouseleave", () => { tip.hide(); hv.selectAll("*").remove(); });
})();
