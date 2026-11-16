// Q4. Has traffic inside the zone become faster vs. 2019–2024 and vs. the rest of the city?
// Line chart of monthly taxi/FHV speeds by area + difference-in-differences bars for 2025.
/* global d3, DATA, C, AREA, makeSvg, tip, axisStyle, gridStyle, legend, buttonGroup, parseYM, fmtMonth, TOLL_START */

(async function q4() {
  const rows = await d3.csv(DATA + "m2_q4_speeds_monthly.csv", d => ({
    month: parseYM(d.year_month), area: d.area, speed: +d.avg_speed_mph,
    change: d.change_mph === "" ? null : +d.change_mph,
    did: d.did_vs_rest_mph === "" ? null : +d.did_vs_rest_mph,
  }));
  const areas = ["inside", "adjacent", "rest_of_nyc"];
  const root = "#q4-viz";
  let view = "speed";
  const ctl = d3.select(root).append("div").attr("class", "controls");
  buttonGroup(ctl.node(), [
    { value: "speed", label: "Average speed (mph)" },
    { value: "index", label: "Index vs. 2022–24 same-month average" },
  ], view, v => { view = v; draw(); });
  legend(root, areas.map(a => ({ label: AREA[a].label, color: AREA[a].color, type: "line" })));

  // baseline per area × calendar month: mean of 2022-2024 (post-pandemic, pre-toll)
  const base = d3.rollup(rows.filter(d => d.month.getFullYear() >= 2022 && d.month.getFullYear() <= 2024),
    v => d3.mean(v, d => d.speed), d => d.area, d => d.month.getMonth());
  rows.forEach(d => { d.idx = 100 * d.speed / base.get(d.area).get(d.month.getMonth()); });

  const W = 900, H = 360, M = { top: 18, right: 120, bottom: 32, left: 50 };
  const iw = W - M.left - M.right, ih = H - M.top - M.bottom;
  const svg = makeSvg(root, W, H).attr("aria-label", "Monthly speeds by area");
  const g = svg.append("g").attr("transform", `translate(${M.left},${M.top})`);
  const x = d3.scaleTime().domain(d3.extent(rows, d => d.month)).range([0, iw]);
  // shading: spring 2020 lockdown
  g.append("rect").attr("x", x(new Date(2020, 2, 1))).attr("width", x(new Date(2020, 5, 30)) - x(new Date(2020, 2, 1)))
    .attr("y", 0).attr("height", ih).attr("fill", C.neutral);
  g.append("text").attr("x", x(new Date(2020, 2, 1)) + 4).attr("y", 12).attr("class", "note").text("2020 lockdown");
  const grid = g.append("g"), yA = g.append("g"), ylab = g.append("text").attr("class", "axis-label")
    .attr("transform", "rotate(-90)").attr("x", -ih / 2).attr("y", -38).attr("text-anchor", "middle");
  g.append("g").attr("transform", `translate(0,${ih})`).call(d3.axisBottom(x).ticks(d3.timeYear)).call(axisStyle);
  g.append("line").attr("x1", x(TOLL_START)).attr("x2", x(TOLL_START)).attr("y1", 0).attr("y2", ih).attr("stroke", C.ink).attr("stroke-width", 1.5);
  g.append("text").attr("x", x(TOLL_START) - 4).attr("y", 12).attr("text-anchor", "end").attr("class", "note-strong").text("Toll starts Jan 5, 2025 →");
  const lines = g.append("g"), labels = g.append("g"), hov = g.append("g");

  function draw() {
    const v = d => view === "speed" ? d.speed : d.idx;
    const y = view === "speed"
      ? d3.scaleLinear().domain([0, d3.max(rows, v) * 1.05]).nice().range([ih, 0])
      : d3.scaleLinear().domain(d3.extent(rows, v)).nice().range([ih, 0]);
    grid.call(d3.axisLeft(y).ticks(6).tickSize(-iw)).call(gridStyle);
    yA.transition().call(d3.axisLeft(y).ticks(6)).call(axisStyle);
    yA.select(".domain").remove();
    ylab.text(view === "speed" ? "Average taxi/FHV speed (mph)" : "Index (2022–24 same-month average = 100)");
    const by = d3.groups(rows, d => d.area);
    lines.selectAll("path").data(by, d => d[0]).join("path").attr("fill", "none").attr("stroke-width", 2)
      .attr("stroke", d => AREA[d[0]].color)
      .transition().duration(500).attr("d", d => d3.line().x(r => x(r.month)).y(r => y(v(r)))(d[1]));
    g.selectAll("line.ref100").data(view === "index" ? [100] : []).join("line").attr("class", "ref100")
      .attr("x1", 0).attr("x2", iw).attr("y1", y(100)).attr("y2", y(100)).attr("stroke", C.ink2).attr("stroke-dasharray", "4 3");
    // direct labels at the right end
    labels.selectAll("text").data(by, d => d[0]).join("text").attr("class", "direct-label")
      .attr("x", iw + 6).attr("dy", "0.35em")
      .transition().duration(500).attr("y", d => y(v(d[1][d[1].length - 1])))
      .text(d => AREA[d[0]].label.replace(" (≤ 2 km)", ""));

    g.selectAll("rect.hit").data([0]).join("rect").attr("class", "hit").attr("width", iw).attr("height", ih).attr("fill", "transparent")
      .on("mousemove", e => {
        const months = [...new Set(rows.map(d => +d.month))].sort((a, b) => a - b);
        const m = months[d3.bisectCenter(months, +x.invert(d3.pointer(e)[0]))];
        const at = areas.map(a => rows.find(d => d.area === a && +d.month === m));
        hov.selectAll("line").data([m]).join("line").attr("x1", x(m)).attr("x2", x(m)).attr("y1", 0).attr("y2", ih).attr("stroke", C.muted).attr("pointer-events", "none");
        hov.selectAll("circle").data(at).join("circle").attr("r", 4).attr("cx", x(m)).attr("cy", d => y(v(d)))
          .attr("fill", d => AREA[d.area].color).attr("stroke", "#fff").attr("stroke-width", 2).attr("pointer-events", "none");
        tip.show(e, `<b>${fmtMonth(new Date(m))}</b><br>` + at.map(d =>
          `<span class="dot" style="background:${AREA[d.area].color}"></span>${AREA[d.area].label}: <b>${d.speed.toFixed(2)} mph</b>` +
          (d.change != null ? ` (${d.change > 0 ? "+" : ""}${d.change.toFixed(2)} vs. 2024)` : "")).join("<br>"));
      })
      .on("mouseleave", () => { tip.hide(); hov.selectAll("*").remove(); });
  }
  draw();

  // ---------- difference-in-differences bars ----------
  const root2 = "#q4-viz-did";
  const did = rows.filter(d => d.did != null && d.area !== "rest_of_nyc");
  legend(root2, ["inside", "adjacent"].map(a => ({ label: AREA[a].label, color: AREA[a].color })));
  const W2 = 900, H2 = 240, M2 = { top: 14, right: 20, bottom: 36, left: 56 };
  const iw2 = W2 - M2.left - M2.right, ih2 = H2 - M2.top - M2.bottom;
  const s2 = makeSvg(root2, W2, H2).attr("aria-label", "Difference in differences");
  const g2 = s2.append("g").attr("transform", `translate(${M2.left},${M2.top})`);
  const months = [...new Set(did.map(d => +d.month))].sort((a, b) => a - b);
  const x0 = d3.scaleBand().domain(months).range([0, iw2]).padding(0.3);
  const x1 = d3.scaleBand().domain(["inside", "adjacent"]).range([0, x0.bandwidth()]).padding(0.12);
  const m = d3.max(did, d => Math.abs(d.did));
  const y2 = d3.scaleLinear().domain([-m, m]).nice().range([ih2, 0]);
  g2.append("g").call(d3.axisLeft(y2).ticks(5).tickSize(-iw2)).call(gridStyle);
  g2.append("g").call(d3.axisLeft(y2).ticks(5).tickFormat(t => (t > 0 ? "+" : "") + t.toFixed(1))).call(axisStyle).call(a => a.select(".domain").remove());
  g2.append("text").attr("transform", "rotate(-90)").attr("x", -ih2 / 2).attr("y", -42).attr("text-anchor", "middle").attr("class", "axis-label").text("mph, relative to rest of NYC");
  g2.append("g").attr("transform", `translate(0,${ih2})`).call(d3.axisBottom(x0).tickFormat(t => fmtMonth(new Date(t)))).call(axisStyle);
  g2.selectAll("rect").data(did).join("rect")
    .attr("x", d => x0(+d.month) + x1(d.area)).attr("width", x1.bandwidth())
    .attr("y", d => y2(Math.max(0, d.did))).attr("height", d => Math.abs(y2(d.did) - y2(0))).attr("rx", 2)
    .attr("fill", d => AREA[d.area].color)
    .on("mousemove", (e, d) => {
      const rest = rows.find(r => r.area === "rest_of_nyc" && +r.month === +d.month);
      tip.show(e, `<b>${AREA[d.area].label}</b>, ${fmtMonth(d.month)}<br>Change vs. same month 2024: ${d.change > 0 ? "+" : ""}${d.change.toFixed(2)} mph<br>
        Rest of NYC change: ${rest.change > 0 ? "+" : ""}${rest.change.toFixed(2)} mph<br>Difference: <b>${d.did > 0 ? "+" : ""}${d.did.toFixed(2)} mph</b>`);
    })
    .on("mouseleave", tip.hide);
  g2.append("line").attr("x1", 0).attr("x2", iw2).attr("y1", y2(0)).attr("y2", y2(0)).attr("stroke", C.ink2);
})();
