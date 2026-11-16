// Shared helpers for all Milestone 3 charts: data paths, colors, tooltip, legends, map loading.
/* global d3 */

const DATA = "../data/processed/"; // CSVs produced by the Milestone 2 pipelines
const GEO = "data/";               // simplified GeoJSON built by scripts/m3_build_geo.py

// ---- colors (validated reference palette; light mode) ----------------------------------
const C = {
  blue: "#2a78d6", orange: "#eb6834", aqua: "#1baf7a", yellow: "#eda100",
  magenta: "#e87ba4", green: "#008300", violet: "#6250d6", red: "#e34948",
  ink: "#0b0b0b", ink2: "#52514e", muted: "#8a8984", grid: "#e6e5e1", surface: "#fcfcfb",
  neutral: "#f0efec", land: "#ecebe7", landStroke: "#d6d5d0", nodata: "#dddcd7",
};

// One color per area, used consistently on every chart.
const AREA = {
  inside:    { label: "Inside the zone",   color: C.blue },
  adjacent:  { label: "Adjacent (≤ 2 km)", color: C.orange },
  elsewhere: { label: "Rest of NYC",       color: C.aqua },
};
AREA.rest_of_nyc = AREA.elsewhere;

// Sequential blue ramp (100 → 700) and diverging blue ↔ gray ↔ red.
const BLUE_RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"];
const seqBlue = t => d3.interpolateRgbBasis(BLUE_RAMP)(t);
const DIV_RAMP = ["#184f95", "#3987e5", "#9ec5f4", C.neutral, "#f4b0ae", "#e66767", "#b52f2f"];
// t = 0 → strong blue, 0.5 → gray, 1 → strong red
const divBlueRed = t => d3.interpolateRgbBasis(DIV_RAMP)(t);

// "good" values blue, "bad" values red. goodWhenPositive flips the direction.
function divergingScale(maxAbs, goodWhenPositive) {
  const s = d3.scaleDiverging(divBlueRed).domain([-maxAbs, 0, maxAbs]).clamp(true);
  return goodWhenPositive ? (v => s(-v)) : s;
}

// ---- formatting ---------------------------------------------------------------------
const fmtInt = d3.format(",.0f");
const fmt1 = d3.format(",.1f");
const fmtPct = v => (v == null || isNaN(v)) ? "no data" : (v > 0 ? "+" : "") + d3.format(".1f")(v) + "%";
const fmtSigned = (v, f = fmt1) => (v > 0 ? "+" : "") + f(v);
const parseYM = d3.timeParse("%Y-%m");
const parseDate = d3.timeParse("%Y-%m-%d");
const fmtMonth = d3.timeFormat("%b %Y");
const fmtDay = d3.timeFormat("%b %-d, %Y");
const TOLL_START = new Date(2025, 0, 5);

// ---- SVG + tooltip ------------------------------------------------------------------
function makeSvg(sel, width, height) {
  return d3.select(sel).append("svg")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("width", "100%")
    .style("max-width", width + "px")
    .attr("role", "img");
}

const tip = (() => {
  const el = d3.select("body").append("div").attr("class", "tooltip").style("opacity", 0);
  return {
    show(event, html) {
      el.html(html).style("opacity", 1);
      const { innerWidth: W } = window;
      const w = el.node().offsetWidth;
      let x = event.pageX + 14;
      if (event.clientX + w + 24 > W) x = event.pageX - w - 14;
      el.style("left", x + "px").style("top", (event.pageY + 12) + "px");
    },
    hide() { el.style("opacity", 0); },
  };
})();

function axisStyle(g) {
  g.selectAll(".domain").attr("stroke", C.muted);
  g.selectAll(".tick line").attr("stroke", C.muted);
  g.selectAll(".tick text").attr("fill", C.ink2).style("font-size", "11px");
}
function gridStyle(g) {
  g.selectAll(".domain").remove();
  g.selectAll(".tick line").attr("stroke", C.grid);
  g.selectAll(".tick text").remove();
}

// Small categorical legend (HTML, above the chart)
function legend(sel, items) {
  const div = d3.select(sel).append("div").attr("class", "legend");
  const it = div.selectAll("span.item").data(items).join("span").attr("class", "item");
  it.append("span").attr("class", d => "swatch " + (d.type || ""))
    .style("background", d => d.type === "line" || d.type === "dash" ? "none" : d.color)
    .style("border-color", d => d.color);
  it.append("span").text(d => d.label);
  return div;
}

// Continuous color legend (SVG gradient bar)
function colorBar(svg, { x, y, width = 220, color, domain, title, tickFormat = v => (v > 0 ? "+" : "") + d3.format("~f")(v) + "%", ticks = 5 }) {
  const id = "grad" + Math.random().toString(36).slice(2);
  const defs = svg.append("defs");
  const lg = defs.append("linearGradient").attr("id", id);
  d3.range(0, 1.0001, 0.1).forEach(t => lg.append("stop")
    .attr("offset", t * 100 + "%").attr("stop-color", color(domain[0] + t * (domain[1] - domain[0]))));
  const g = svg.append("g").attr("transform", `translate(${x},${y})`);
  g.append("text").attr("y", -6).attr("class", "legend-title").text(title);
  g.append("rect").attr("width", width).attr("height", 10).attr("rx", 2).attr("fill", `url(#${id})`);
  const sc = d3.scaleLinear().domain(domain).range([0, width]);
  g.append("g").attr("transform", "translate(0,10)")
    .call(d3.axisBottom(sc).ticks(ticks).tickSize(4).tickFormat(tickFormat)).call(axisStyle)
    .call(a => a.select(".domain").remove());
  return g;
}

// ---- geo ------------------------------------------------------------------------------
let _geo;
function loadGeo() {
  if (!_geo) {
    _geo = Promise.all([d3.json(GEO + "nta2020.geojson"), d3.json(GEO + "zone.geojson")])
      .then(([nta, zone]) => ({ nta, zone }));
  }
  return _geo;
}

// Draws the NTA base map + zone outline. Returns {g, path, projection, ntaSel}.
function baseMap(svg, geo, { width, height, focus, pad = 10, fillFor }) {
  // focus: any GeoJSON object (e.g. a MultiPoint of bbox corners [[lon,lat],[lon,lat]])
  const projection = d3.geoMercator().fitExtent([[pad, pad], [width - pad, height - pad]],
    Array.isArray(focus) ? { type: "MultiPoint", coordinates: focus } : focus);
  const path = d3.geoPath(projection);
  svg.append("defs").append("clipPath").attr("id", "clip-" + svg.attr("id"))
    .append("rect").attr("width", width).attr("height", height);
  const g = svg.append("g").attr("clip-path", `url(#clip-${svg.attr("id")})`);
  const ntaSel = g.append("g").selectAll("path").data(geo.nta.features).join("path")
    .attr("d", path)
    .attr("fill", d => (fillFor ? fillFor(d) : null) || C.land)
    .attr("stroke", "#fff").attr("stroke-width", 0.6);
  g.append("path").datum(geo.zone.features[0]).attr("class", "zone-outline").attr("d", path)
    .attr("fill", "none").attr("stroke", C.ink).attr("stroke-width", 1.6).attr("stroke-dasharray", "5 3")
    .attr("pointer-events", "none");
  return { g, path, projection, ntaSel };
}

// Hatch pattern for "no data"
function hatch(svg, id = "hatch") {
  const p = svg.append("defs").append("pattern").attr("id", id).attr("patternUnits", "userSpaceOnUse")
    .attr("width", 6).attr("height", 6).attr("patternTransform", "rotate(45)");
  p.append("rect").attr("width", 6).attr("height", 6).attr("fill", C.land);
  p.append("line").attr("x1", 0).attr("y1", 0).attr("x2", 0).attr("y2", 6).attr("stroke", "#c9c8c2").attr("stroke-width", 2);
  return `url(#${id})`;
}

// Reusable control builders (one row above each chart)
function buttonGroup(sel, options, value, onChange) {
  const g = d3.select(sel).append("div").attr("class", "btn-group").attr("role", "group");
  const b = g.selectAll("button").data(options).join("button")
    .attr("type", "button").text(d => d.label)
    .classed("active", d => d.value === value)
    .on("click", (e, d) => {
      b.classed("active", x => x.value === d.value);
      onChange(d.value);
    });
  return g;
}
function selectBox(sel, label, options, value, onChange) {
  const w = d3.select(sel).append("label").attr("class", "select");
  w.append("span").text(label);
  const s = w.append("select").on("change", e => onChange(e.target.value));
  s.selectAll("option").data(options).join("option")
    .attr("value", d => d.value).text(d => d.label).property("selected", d => d.value === value);
  return s;
}
