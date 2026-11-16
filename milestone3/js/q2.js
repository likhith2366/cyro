// Q2. How have entries changed since the toll started, by vehicle class and time period?
// (a) Small multiples of weekly CRZ entries per vehicle class (peak vs overnight), linked by a brush.
// (b) Before/after baseline: Manhattan-bound tunnel crossings, 2025 vs same month of 2024.
/* global d3, DATA, C, makeSvg, tip, axisStyle, gridStyle, legend, buttonGroup, fmtInt, fmtPct, parseDate, parseYM, fmtDay, fmtMonth */

(async function q2() {
  const [weekly, bt] = await Promise.all([
    d3.csv(DATA + "q2_weekly_by_class.csv", d => ({
      week: parseDate(d.week_start), cls: d.vehicle_class, period: d.time_period,
      entries: +d.entries, prev: d.entries_same_week_prev_year === "" ? null : +d.entries_same_week_prev_year,
      pct: d.pct_change === "" ? null : +d.pct_change,
    })),
    d3.csv(DATA + "q2_bt_yoy.csv", d => ({
      month: parseYM(d.year_month), facility: d.facility,
      crossings: +d.crossings, prev: +d.crossings_same_month_2024,
    })),
  ]);

  const PERIOD = { Peak: { color: C.blue, label: "Peak (toll in effect at full rate)" },
                   Overnight: { color: C.orange, label: "Overnight (reduced toll)" } };
  const classes = [...new Set(weekly.map(d => d.cls))];
  const nice = c => c.replace(/^\d - /, "");
  const FLAG_FROM = new Date(2026, 9, 1); // weeks of Oct 4 and Oct 11, 2026
  let mode = "entries";

  // ---------- (a) small multiples ----------
  const root = "#q2-viz";
  const ctl = d3.select(root).append("div").attr("class", "controls");
  buttonGroup(ctl.node(), [
    { value: "entries", label: "Weekly entries" },
    { value: "pct", label: "% change vs. same week of 2025" },
  ], mode, v => { mode = v; update(); });
  legend(root, [...Object.values(PERIOD).map(p => ({ ...p, type: "line" })),
    { label: "Last two weeks: unusual peak→overnight shift, under review", color: "#d6d5d0" }]);

  const W = 900, cols = 3, PW = 280, PH = 150, gapX = 30, gapY = 46;
  const M = { top: 10, left: 50 };
  const OH = 70; // overview height
  const H = M.top + 2 * (PH + gapY) + OH + 40;
  const svg = makeSvg(root, W, H).attr("aria-label", "Weekly entries by vehicle class");
  const xFull = d3.extent(weekly, d => d.week);
  let xDomain = xFull.slice();

  const panels = classes.map((cls, i) => {
    const col = i % cols, row = Math.floor(i / cols);
    const g = svg.append("g").attr("transform", `translate(${M.left + col * (PW + gapX)},${M.top + row * (PH + gapY) + 16})`);
    g.append("text").attr("y", -6).attr("class", "panel-title").text(nice(cls));
    g.append("clipPath").attr("id", "q2clip" + i).append("rect").attr("width", PW - 40).attr("height", PH);
    return {
      cls, g,
      grid: g.append("g"), yAx: g.append("g"), xAx: g.append("g").attr("transform", `translate(0,${PH})`),
      flag: g.append("rect").attr("fill", C.neutral).attr("y", 0),
      zero: g.append("line").attr("stroke", C.ink2),
      plot: g.append("g").attr("clip-path", `url(#q2clip${i})`),
      hover: g.append("g"),
    };
  });

  // overview + brush (total entries of all classes)
  const ov = svg.append("g").attr("transform", `translate(${M.left},${H - OH - 26})`);
  const OW = W - M.left - 40;
  ov.append("text").attr("y", -8).attr("class", "axis-label").text("All vehicle classes — drag across this strip to zoom every panel; double-click to reset");
  const xo = d3.scaleTime().domain(xFull).range([0, OW]);
  const tot = d3.rollups(weekly, v => d3.sum(v, d => d.entries), d => +d.week).map(([k, v]) => ({ week: new Date(k), v })).sort((a, b) => a.week - b.week);
  const yo = d3.scaleLinear().domain([0, d3.max(tot, d => d.v)]).range([OH - 20, 0]);
  ov.append("path").datum(tot).attr("fill", "#cde2fb").attr("stroke", C.blue).attr("stroke-width", 1)
    .attr("d", d3.area().x(d => xo(d.week)).y0(OH - 20).y1(d => yo(d.v)));
  ov.append("g").attr("transform", `translate(0,${OH - 20})`).call(d3.axisBottom(xo).ticks(10).tickFormat(d3.timeFormat("%b %Y"))).call(axisStyle);
  const brush = d3.brushX().extent([[0, 0], [OW, OH - 20]]).on("brush end", e => {
    xDomain = e.selection ? e.selection.map(xo.invert) : xFull.slice();
    update(e.type === "end" ? 300 : 0);
  });
  const bg = ov.append("g").call(brush);
  bg.on("dblclick", () => bg.call(brush.move, null));

  function update(dur = 400) {
    panels.forEach(p => {
      const data = weekly.filter(d => d.cls === p.cls && (mode === "entries" || d.pct != null));
      // % change only exists for 2026 weeks, so clamp the domain to 2026 in that mode
      let dom = xDomain;
      if (mode === "pct") {
        const lo = d3.max([xDomain[0], new Date(2026, 0, 4)]);
        dom = lo < xDomain[1] && +xDomain[1] - +lo > 14 * 864e5 ? [lo, xDomain[1]] : [new Date(2026, 0, 4), xFull[1]];
      }
      const x = d3.scaleTime().domain(dom).range([0, PW - 40]);
      let vis = data.filter(d => d.week >= x.domain()[0] && d.week <= x.domain()[1]);
      // keep the flagged weeks from setting the y-scale (they are still drawn, clipped at the panel edge)
      if (vis.some(d => d.week < FLAG_FROM)) vis = vis.filter(d => d.week < FLAG_FROM);
      const v = d => mode === "entries" ? d.entries : d.pct;
      let y;
      if (mode === "entries") y = d3.scaleLinear().domain([0, d3.max(vis, v) * 1.05 || 1]).nice().range([PH, 0]);
      else {
        const m = d3.max(vis, d => Math.abs(d.pct)) || 10;
        y = d3.scaleLinear().domain([-m, m]).nice().range([PH, 0]);
      }
      const fmtY = mode === "entries" ? d3.format(".2~s") : (t => (t > 0 ? "+" : "") + t + "%");
      p.grid.call(d3.axisLeft(y).ticks(4).tickSize(-(PW - 40))).call(gridStyle);
      p.yAx.transition().duration(dur).call(d3.axisLeft(y).ticks(4).tickFormat(fmtY)).call(axisStyle);
      p.yAx.select(".domain").remove();
      p.xAx.transition().duration(dur).call(d3.axisBottom(x).ticks(3).tickFormat(d3.timeFormat("%b '%y"))).call(axisStyle);
      // flag the last two weeks: every class shifts sharply from peak to overnight (possible source reporting change)
      const fx0 = Math.max(0, x(FLAG_FROM)), fx1 = x.range()[1];
      p.flag.attr("x", fx0).attr("width", Math.max(0, fx1 - fx0)).attr("height", PH);
      p.zero.attr("x1", 0).attr("x2", PW - 40).attr("y1", y(0)).attr("y2", y(0)).attr("opacity", mode === "pct" ? 1 : 0);
      const series = d3.groups(data, d => d.period);
      p.plot.selectAll("path").data(series, d => d[0]).join("path")
        .attr("fill", "none").attr("stroke-width", 2).attr("stroke", d => PERIOD[d[0]].color)
        .transition().duration(dur)
        .attr("d", d => d3.line().defined(r => v(r) != null).x(r => x(r.week)).y(r => y(v(r)))(d[1].sort((a, b) => a.week - b.week)));

      // crosshair hover per panel
      p.hover.selectAll("rect").data([0]).join("rect").attr("width", PW - 40).attr("height", PH).attr("fill", "transparent")
        .on("mousemove", e => {
          const [mx] = d3.pointer(e);
          const t = x.invert(mx);
          const weeks = [...new Set(data.map(d => +d.week))].sort((a, b) => a - b);
          const wk = weeks[Math.max(0, Math.min(weeks.length - 1, d3.bisectCenter(weeks, +t)))];
          const at = data.filter(d => +d.week === wk);
          p.hover.selectAll("line").data([wk]).join("line").attr("stroke", C.muted).attr("pointer-events", "none")
            .attr("x1", x(wk)).attr("x2", x(wk)).attr("y1", 0).attr("y2", PH);
          p.hover.selectAll("circle").data(at).join("circle").attr("r", 4).attr("pointer-events", "none")
            .attr("fill", d => PERIOD[d.period].color).attr("stroke", C.surface).attr("stroke-width", 2)
            .attr("cx", d => x(d.week)).attr("cy", d => y(v(d)));
          tip.show(e, `<b>${nice(p.cls)}</b>, week of ${fmtDay(new Date(wk))}<br>` + at.map(d =>
            `${d.period}: <b>${fmtInt(d.entries)}</b>${d.pct != null ? ` (${fmtPct(d.pct)} vs. ${fmtInt(d.prev)} a year earlier)` : ""}`).join("<br>"));
        })
        .on("mouseleave", () => { tip.hide(); p.hover.selectAll("line,circle").remove(); });
    });
  }
  update(0);

  // ---------- (b) before/after baseline from B&T tunnel crossings ----------
  const root2 = "#q2-viz-bt";
  const byFac = d3.rollups(bt, v => {
    const c = d3.sum(v, d => d.crossings), p = d3.sum(v, d => d.prev);
    return { c, p, pct: (c / p - 1) * 100 };
  }, d => d.facility, d => +d.month);
  const facs = byFac.map(d => d[0]);
  const FAC_COLOR = { [facs[0]]: C.violet, [facs[1]]: C.aqua };
  const flat = byFac.flatMap(([f, ms]) => ms.map(([m, v]) => ({ facility: f, month: new Date(m), ...v })));
  legend(root2, facs.map(f => ({ label: f + " (Manhattan-bound)", color: FAC_COLOR[f] })));

  const W2 = 900, H2 = 280, M2 = { top: 16, right: 20, bottom: 40, left: 56 };
  const iw = W2 - M2.left - M2.right, ih = H2 - M2.top - M2.bottom;
  const s2 = makeSvg(root2, W2, H2).attr("aria-label", "Percent change in tunnel crossings, 2025 vs 2024");
  const g2 = s2.append("g").attr("transform", `translate(${M2.left},${M2.top})`);
  const months = [...new Set(flat.map(d => +d.month))].sort((a, b) => a - b);
  const x0 = d3.scaleBand().domain(months).range([0, iw]).padding(0.25);
  const x1 = d3.scaleBand().domain(facs).range([0, x0.bandwidth()]).padding(0.1);
  const m = d3.max(flat, d => Math.abs(d.pct));
  const y2 = d3.scaleLinear().domain([-m, m]).nice().range([ih, 0]);
  g2.append("g").call(d3.axisLeft(y2).ticks(6).tickSize(-iw)).call(gridStyle);
  g2.append("g").call(d3.axisLeft(y2).ticks(6).tickFormat(t => (t > 0 ? "+" : "") + t + "%")).call(axisStyle).call(a => a.select(".domain").remove());
  g2.append("g").attr("transform", `translate(0,${ih})`).call(d3.axisBottom(x0).tickFormat(t => d3.timeFormat("%b")(new Date(t)))).call(axisStyle);
  g2.append("text").attr("x", iw / 2).attr("y", ih + 34).attr("text-anchor", "middle").attr("class", "axis-label").text("2025 month (each compared with the same month of 2024)");
  g2.selectAll("rect.bar").data(flat).join("rect").attr("class", "bar")
    .attr("x", d => x0(+d.month) + x1(d.facility)).attr("width", x1.bandwidth())
    .attr("y", d => y2(Math.max(0, d.pct))).attr("height", d => Math.abs(y2(d.pct) - y2(0)))
    .attr("rx", 2).attr("fill", d => FAC_COLOR[d.facility])
    .on("mousemove", (e, d) => tip.show(e, `<b>${d.facility}</b>, ${fmtMonth(d.month)}<br>${fmtInt(d.c)} crossings vs. ${fmtInt(d.p)} in ${d3.timeFormat("%b")(d.month)} 2024<br><b>${fmtPct(d.pct)}</b>`))
    .on("mouseleave", tip.hide);
  g2.append("line").attr("x1", 0).attr("x2", iw).attr("y1", y2(0)).attr("y2", y2(0)).attr("stroke", C.ink2);
})();
