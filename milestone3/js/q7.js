// Q7. Have crashes and injuries inside the zone gone down compared with the rest of the city?
// (a) Indexed line chart: each month vs. the same month of 2024 (= 100), one line per area.
// (b) Year-over-year "slope" chart of Jan–Sep totals, indexed to 2024 = 100.
/* global d3, DATA, C, AREA, makeSvg, tip, axisStyle, gridStyle, legend, buttonGroup, parseYM, fmtMonth, fmtInt, TOLL_START */

(async function q7() {
  const rows = await d3.csv(DATA + "q7_monthly_by_area.csv", d => ({
    month: parseYM(d.year_month), area: d.area,
    crashes: +d.crashes, injured: +d.persons_injured, killed: +d.persons_killed,
  }));
  const areas = ["inside", "adjacent", "elsewhere"];
  const MET = { crashes: "Crashes", injured: "People injured", killed: "People killed" };
  let metric = "crashes", smooth = true;

  const root = "#q7-viz";
  const ctl = d3.select(root).append("div").attr("class", "controls");
  buttonGroup(ctl.node(), Object.entries(MET).map(([value, label]) => ({ value, label })), metric, v => { metric = v; draw(); });
  const chk = ctl.append("label").attr("class", "check");
  chk.append("input").attr("type", "checkbox").property("checked", smooth).on("change", e => { smooth = e.target.checked; draw(); });
  chk.append("span").text("3-month rolling average");
  legend(root, areas.map(a => ({ label: AREA[a].label, color: AREA[a].color, type: "line" })));

  const wrap = d3.select(root).append("div").attr("class", "two-col wide-left");
  const W = 600, H = 340, M = { top: 16, right: 16, bottom: 30, left: 48 };
  const iw = W - M.left - M.right, ih = H - M.top - M.bottom;
  const svg = makeSvg(wrap.append("div").node(), W, H).attr("aria-label", "Indexed monthly crashes");
  const g = svg.append("g").attr("transform", `translate(${M.left},${M.top})`);
  const x = d3.scaleTime().domain(d3.extent(rows, d => d.month)).range([0, iw]);
  const grid = g.append("g"), yA = g.append("g");
  g.append("g").attr("transform", `translate(0,${ih})`).call(d3.axisBottom(x).ticks(d3.timeMonth.every(6)).tickFormat(d3.timeFormat("%b %Y"))).call(axisStyle);
  g.append("text").attr("transform", "rotate(-90)").attr("x", -ih / 2).attr("y", -36).attr("text-anchor", "middle").attr("class", "axis-label").text("Index (same month of 2024 = 100)");
  const ref = g.append("line").attr("stroke", C.ink2).attr("stroke-dasharray", "4 3");
  const toll = g.append("line").attr("stroke", C.ink).attr("stroke-width", 1.5);
  g.append("text").attr("x", x(TOLL_START) + 4).attr("y", 10).attr("class", "note-strong").text("Toll starts");
  const lines = g.append("g"), hov = g.append("g");

  const SW = 300, SH = 340, SM = { top: 16, right: 90, bottom: 42, left: 44 };
  const siw = SW - SM.left - SM.right, sih = SH - SM.top - SM.bottom;
  const s2 = makeSvg(wrap.append("div").node(), SW, SH).attr("aria-label", "Year over year totals");
  const g2 = s2.append("g").attr("transform", `translate(${SM.left},${SM.top})`);
  const years = [2023, 2024, 2025, 2026];
  const xs = d3.scalePoint().domain(years).range([0, siw]).padding(0.2);
  const grid2 = g2.append("g"), yA2 = g2.append("g");
  g2.append("g").attr("transform", `translate(0,${sih})`).call(d3.axisBottom(xs)).call(axisStyle);
  g2.append("text").attr("x", siw / 2).attr("y", sih + 36).attr("text-anchor", "middle").attr("class", "axis-label").text("Jan–Sep totals, 2024 = 100");
  const sl = g2.append("g");

  function draw() {
    // monthly index vs. same month of 2024
    const base = new Map(rows.filter(d => d.month.getFullYear() === 2024).map(d => [d.area + d.month.getMonth(), d[metric]]));
    const series = areas.map(a => {
      const r = rows.filter(d => d.area === a).sort((p, q) => p.month - q.month);
      return [a, r.map((d, i) => {
        const win = smooth ? r.slice(Math.max(0, i - 2), i + 1) : [d];
        const num = d3.sum(win, w => w[metric]);
        const den = d3.sum(win, w => base.get(a + w.month.getMonth()));
        return { ...d, idx: den > 0 ? 100 * num / den : null, base: base.get(a + d.month.getMonth()) };
      }).filter((d, i) => !smooth || i >= 2)];
    });
    const all = series.flatMap(s => s[1]).filter(d => d.idx != null);
    const y = d3.scaleLinear().domain(d3.extent([...all.map(d => d.idx), 100])).nice().range([ih, 0]);
    grid.call(d3.axisLeft(y).ticks(6).tickSize(-iw)).call(gridStyle);
    yA.transition().call(d3.axisLeft(y).ticks(6)).call(axisStyle);
    yA.select(".domain").remove();
    ref.attr("x1", 0).attr("x2", iw).transition().attr("y1", y(100)).attr("y2", y(100));
    toll.attr("x1", x(TOLL_START)).attr("x2", x(TOLL_START)).attr("y1", 0).attr("y2", ih);
    lines.selectAll("path").data(series, d => d[0]).join("path").attr("fill", "none").attr("stroke-width", 2)
      .attr("stroke", d => AREA[d[0]].color)
      .transition().duration(500).attr("d", d => d3.line().defined(r => r.idx != null).x(r => x(r.month)).y(r => y(r.idx))(d[1]));
    g.selectAll("rect.hit").data([0]).join("rect").attr("class", "hit").attr("width", iw).attr("height", ih).attr("fill", "transparent")
      .on("mousemove", e => {
        const ms = [...new Set(all.map(d => +d.month))].sort((a, b) => a - b);
        const m = ms[d3.bisectCenter(ms, +x.invert(d3.pointer(e)[0]))];
        const at = series.map(s => s[1].find(d => +d.month === m)).filter(Boolean);
        hov.selectAll("line").data([m]).join("line").attr("x1", x(m)).attr("x2", x(m)).attr("y1", 0).attr("y2", ih).attr("stroke", C.muted).attr("pointer-events", "none");
        hov.selectAll("circle").data(at).join("circle").attr("r", 4).attr("cx", x(m)).attr("cy", d => y(d.idx))
          .attr("fill", d => AREA[d.area].color).attr("stroke", "#fff").attr("stroke-width", 2).attr("pointer-events", "none");
        tip.show(e, `<b>${fmtMonth(new Date(m))}</b> — ${MET[metric].toLowerCase()}${smooth ? " (3-month window)" : ""}<br>` + at.map(d =>
          `${AREA[d.area].label}: index <b>${d.idx.toFixed(0)}</b> · ${fmtInt(d[metric])} this month vs. ${fmtInt(d.base)} in ${d3.timeFormat("%b")(d.month)} 2024`).join("<br>"));
      })
      .on("mouseleave", () => { tip.hide(); hov.selectAll("*").remove(); });

    // Jan–Sep totals by year, indexed to 2024
    const tot = areas.map(a => {
      const v = years.map(yr => ({ yr, area: a, v: d3.sum(rows.filter(d => d.area === a && d.month.getFullYear() === yr && d.month.getMonth() <= 8), d => d[metric]) }));
      const b = v.find(d => d.yr === 2024).v;
      v.forEach(d => { d.idx = 100 * d.v / b; });
      return [a, v];
    });
    const ys = d3.scaleLinear().domain(d3.extent([...tot.flatMap(t => t[1].map(d => d.idx)), 100])).nice().range([sih, 0]);
    grid2.call(d3.axisLeft(ys).ticks(6).tickSize(-siw)).call(gridStyle);
    yA2.transition().call(d3.axisLeft(ys).ticks(6)).call(axisStyle);
    yA2.select(".domain").remove();
    const grp = sl.selectAll("g.s").data(tot, d => d[0]).join(en => { const s = en.append("g").attr("class", "s"); s.append("path"); s.append("text").attr("class", "direct-label"); return s; });
    grp.select("path").attr("fill", "none").attr("stroke-width", 2).attr("stroke", d => AREA[d[0]].color)
      .transition().duration(500).attr("d", d => d3.line().x(r => xs(r.yr)).y(r => ys(r.idx))(d[1]));
    grp.selectAll("circle").data(d => d[1]).join("circle").attr("r", 4.5).attr("fill", d => AREA[d.area].color).attr("stroke", "#fff").attr("stroke-width", 2)
      .on("mousemove", (e, d) => tip.show(e, `<b>${AREA[d.area].label}</b>, Jan–Sep ${d.yr}<br>${MET[metric]}: <b>${fmtInt(d.v)}</b> (index ${d.idx.toFixed(0)})`))
      .on("mouseleave", tip.hide)
      .transition().duration(500).attr("cx", d => xs(d.yr)).attr("cy", d => ys(d.idx));
    // label positions with simple collision nudging
    const ends = tot.map(t => ({ a: t[0], y: ys(t[1][t[1].length - 1].idx), v: t[1][t[1].length - 1].idx }));
    ends.sort((p, q) => p.y - q.y).forEach((e, i, arr) => { if (i && e.y - arr[i - 1].y < 13) e.y = arr[i - 1].y + 13; });
    grp.select("text").attr("x", siw + 8).attr("dy", "0.35em")
      .transition().duration(500).attr("y", d => ends.find(e => e.a === d[0]).y)
      .text(d => AREA[d[0]].label.split(" (")[0].replace("Inside the zone", "Inside zone") + " " + ends.find(e => e.a === d[0]).v.toFixed(0));
  }
  draw();
})();
