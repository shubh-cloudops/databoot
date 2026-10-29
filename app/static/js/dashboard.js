// Draws the charts of one dataset page from GET /api/datasets/<id>/app (the shown app's charts, same query string as the page) with the vendored Plotly.
// Spec: docs/DESIGN.md "Charts". Colours come from the CSS tokens at draw time; the OS decides light or dark.
(function () {
  "use strict";
  // Keep the address clean: empty fields are not sent (re-enabled when Back restores the page from cache).
  var form = document.querySelector("form.filters");
  if (form) {
    form.addEventListener("submit", function () {
      form.querySelectorAll("select, input").forEach(function (f) { if (!f.value) f.disabled = true; });
    });
    window.addEventListener("pageshow", function () { form.querySelectorAll(":disabled").forEach(function (f) { f.disabled = false; }); });
  }

  var cross = document.querySelector("form.crosstab");
  if (cross) cross.addEventListener("change", function () { cross.requestSubmit(); });

  var plots = document.querySelectorAll(".chart .plot");
  var id = (location.pathname.match(/\/datasets\/([^/]+)/) || [])[1];
  if (!plots.length || !id) return;

  var CONFIG = { topojsonURL: "/static/vendor/topojson/", displaylogo: false, responsive: true, displayModeBar: true };
  var phone = window.matchMedia("(max-width: 599px)");
  var dark = window.matchMedia("(prefers-color-scheme: dark)");
  var charts = null;

  function tokens() {
    var css = getComputedStyle(document.documentElement);
    var t = {};
    ["--fg", "--bg", "--muted", "--line", "--line-strong", "--surface", "--font", "--seq-lo", "--seq-hi", "--seq-pt-lo",
      "--div-neg", "--div-mid", "--div-pos"].forEach(function (n) { t[n] = css.getPropertyValue(n).trim(); });
    t.c = [];
    for (var i = 1; i <= 8; i++) t.c.push(css.getPropertyValue("--c" + i).trim());
    return t;
  }

  function axis(t, title, extra) {
    var a = { title: { text: title || "", standoff: 8 }, gridcolor: t["--line"], zerolinecolor: t["--line"],
      linecolor: t["--muted"], tickcolor: t["--muted"], automargin: true };
    for (var k in extra) a[k] = extra[k];
    return a;
  }

  function layout(t, c) {
    return {
      paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)", autosize: true, showlegend: false,
      font: { family: t["--font"], size: 13, color: t["--fg"] },
      margin: { l: phone.matches ? 44 : 56, r: 16, t: 36, b: 48 },  // t leaves room for the always-visible mode bar
      modebar: { bgcolor: "rgba(0,0,0,0)", color: t["--muted"], activecolor: t["--fg"] },
      hoverlabel: { bgcolor: t["--surface"], bordercolor: t["--line-strong"], font: { color: t["--fg"] } },
      transition: { duration: 0 },
      xaxis: axis(t, c.x_label), yaxis: axis(t, c.y_label, { tickformat: "," })
    };
  }

  // Heatmap cell values: Plotly's own text colour is only ~3.9:1 on the bright dark-mode blue, so each cell gets
  // black or white, whichever contrasts more with the colour the scale gives that cell.
  function rgb(h) { return [1, 3, 5].map(function (i) { return parseInt(h.substr(i, 2), 16); }); }
  function lum(v) {
    var k = v.map(function (x) { x /= 255; return x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4); });
    return 0.2126 * k[0] + 0.7152 * k[1] + 0.0722 * k[2];
  }
  function cellValues(c, t) {
    var out = [];
    c.data.z.forEach(function (row, i) {
      row.forEach(function (z, j) {
        if (z === null) return;
        var a = rgb(z < 0 ? t["--div-neg"] : t["--div-pos"]), m = rgb(t["--div-mid"]), w = Math.abs(z);
        var L = lum(m.map(function (x, n) { return x + (a[n] - x) * w; }));
        out.push({ x: c.data.labels[j], y: c.data.labels[i], xref: "x", yref: "y", showarrow: false,
          text: z.toFixed(2), font: { size: 13, color: 1.05 / (L + 0.05) >= (L + 0.05) / 0.05 ? "#ffffff" : "#000000" } });
      });
    });
    return out;
  }

  // Each builder returns [data, layout] for one chart.
  var build = {
    line: function (c, t, l) {
      l.xaxis.type = "date";
      return [[{ type: "scatter", mode: c.shown <= 40 ? "lines+markers" : "lines", x: c.data.x, y: c.data.y,
        line: { color: t.c[0], width: 2 }, marker: { color: t.c[0], size: 6 } }], l];
    },
    // Monitoring main line (DESIGN.md "Monitoring and Survey"): value line, dashed grey 7-point mean, a labelled marker on each server-flagged spike; one y-axis.
    monitor: function (c, t, l) {
      var d = c.data, many = c.shown <= 40;
      l.xaxis.type = "date";
      l.showlegend = true;
      l.legend = { orientation: "h", x: 0, y: phone.matches ? -0.75 : -0.25, yanchor: "top" };
      if (phone.matches) l.margin.b = 120;  // the legend wraps under the rotated dates and the axis title
      var traces = [
        { type: "scatter", mode: many ? "lines+markers" : "lines", name: c.y_label, x: d.x, y: d.y, line: { color: t.c[0], width: 2 }, marker: { color: t.c[0], size: 6 } },
        { type: "scatter", mode: "lines", name: "7-point mean", x: d.x, y: d.mean, line: { color: t["--muted"], width: 2, dash: "dash" } }];
      if (d.spike.length) traces.push({ type: "scatter", mode: "markers+text", name: "spike", text: d.spike.map(function () { return "spike"; }), textposition: "top center", cliponaxis: false,
        x: d.spike.map(function (i) { return d.x[i]; }), y: d.spike.map(function (i) { return d.y[i]; }), marker: { color: t.c[4], size: 10 }, textfont: { color: t["--fg"] } });
      return [traces, l];
    },
    // Survey Likert question (DESIGN.md "Monitoring and Survey"): one 100% stacked horizontal bar, a trace per level (zero counts too);
    // levels before the neutral one fade from --div-neg, the neutral one is --div-mid, those after fade to --div-pos.
    likert: function (c, t, l) {
      var d = c.data, last = d.levels.length - 1;
      var mix = function (a, b, w) { if (!w) return a; var x = rgb(a), y = rgb(b); return "rgb(" + x.map(function (v, n) { return Math.round(v + (y[n] - v) * w); }).join(",") + ")"; };
      l.barmode = "stack";
      l.showlegend = true;
      l.legend = { orientation: "h", x: 0, y: phone.matches ? -0.45 : -0.6, yanchor: "top", traceorder: "normal" };  // stacked bars would list the levels backwards
      l.margin.b = phone.matches ? 120 : 96;  // the legend wraps under the axis
      l.xaxis = axis(t, "", { range: [0, 100], ticksuffix: "%", fixedrange: true });
      l.yaxis = axis(t, "", { type: "category", showticklabels: false, fixedrange: true });
      return [d.levels.map(function (lv, i) {
        var color = i === d.neutral ? t["--div-mid"] : i < d.neutral ? mix(t["--div-neg"], t["--div-mid"], i / d.neutral) : mix(t["--div-pos"], t["--div-mid"], (last - i) / (last - d.neutral));
        return { type: "bar", orientation: "h", name: String(lv), x: [d.pct[i]], y: [c.x_label], customdata: [d.counts[i]], marker: { color: color, line: { color: t["--surface"], width: 1 } },
          hovertemplate: "%{fullData.name}: %{customdata} (%{x:.1f}%)<extra></extra>" };
      }), l];
    },
    // Survey cross-tab: one heatmap of counts, one-hue scale, each cell prints "count (row %)"; the colour bar is the count.
    crosstab: function (c, t, l) {
      var d = c.data, bar = { outlinewidth: 0, tickfont: { color: t["--fg"] }, title: { text: "count", font: { color: t["--fg"] } } };
      if (phone.matches) Object.assign(bar, { orientation: "h", x: 0.5, xanchor: "center", y: -0.42, yanchor: "top", len: 0.9, nticks: 4, title: { text: "count", side: "top", font: { color: t["--fg"] } } });
      if (phone.matches) l.margin.b = 170;
      l.xaxis = axis(t, c.x_label, { type: "category" });
      l.yaxis = axis(t, c.y_label, { type: "category", autorange: "reversed" });
      return [[{ type: "heatmap", x: d.x, y: d.y, z: d.z, hoverongaps: false, xgap: 1, ygap: 1, colorscale: [[0, t["--seq-lo"]], [1, t["--seq-hi"]]],
        text: d.z.map(function (row, i) { return row.map(function (n, j) { return n + " (" + d.pct[i][j].toFixed(1) + "%)"; }); }),
        texttemplate: "%{text}", hovertemplate: "%{y} / %{x}<br>%{text}<extra></extra>", colorbar: bar }], l];
    },
    bar: function (c, t, l) {
      var lead = c.orientation === "h";  // Business leaderboard: always horizontal, biggest on top, values printed
      var wide = lead || c.data.x.some(function (s) { return String(s).length > 12; });
      l.xaxis.type = "category";
      l.bargap = 0.2;
      var trace = { type: "bar", marker: { color: t.c[0] } };
      if (wide) {  // horizontal: largest first at the top
        trace.orientation = "h"; trace.x = c.data.y; trace.y = c.data.x;
        l.xaxis = axis(t, c.y_label, { tickformat: "," });
        l.yaxis = axis(t, c.x_label, { type: "category", autorange: "reversed" });
      } else {
        trace.x = c.data.x; trace.y = c.data.y;
      }
      (wide ? l.xaxis : l.yaxis).rangemode = "tozero";  // global rule 1; the server's baseline is 0, so every bar starts there
      var traces = [trace];
      if (lead) {
        var n = c.other ? c.data.x.length - 1 : c.data.x.length;  // Other is the last bar: its own trace in --muted, same axis and order
        traces = [[0, n, t.c[0]], [n, c.data.x.length, t["--muted"]]].filter(function (r) { return r[1] > r[0]; }).map(function (r) {
          return { type: "bar", orientation: "h", x: c.data.y.slice(r[0], r[1]), y: c.data.x.slice(r[0], r[1]), marker: { color: r[2] },
            texttemplate: "%{x:,}", textposition: "outside", cliponaxis: false };
        });
        l.barmode = "overlay";
        l.margin.r = 72;  // room for the value printed outside the longest bar
      }
      return [traces, l];
    },
    donut: function (c, t, l) {
      delete l.xaxis; delete l.yaxis;
      l.showlegend = true;
      l.legend = phone.matches ? { orientation: "h", y: -0.1 } : { orientation: "v" };
      return [[{ type: "pie", hole: 0.55, labels: c.data.labels, values: c.data.values, textinfo: "percent", sort: false,
        marker: { colors: t.c, line: { color: t["--surface"], width: 2 } } }], l];
    },
    histogram: function (c, t, l) {
      var e = c.data.edges;
      l.bargap = 0.02;
      l.xaxis.tickformat = ",";
      var trace = { type: "bar", y: c.data.counts, marker: { color: t.c[0] },
        x: c.data.counts.map(function (_, i) { return (e[i] + e[i + 1]) / 2; }) };
      if (e[1] > e[0]) trace.width = c.data.counts.map(function (_, i) { return e[i + 1] - e[i]; });
      return [[trace], l];
    },
    scatter: function (c, t, l) {
      l.xaxis.tickformat = ",";
      return [[{ type: "scatter", mode: "markers", x: c.data.x, y: c.data.y,
        marker: { color: t.c[0], size: 6, opacity: 0.7 } }], l];
    },
    heatmap: function (c, t, l) {
      l.xaxis = axis(t, "", { type: "category" });
      l.yaxis = axis(t, "", { type: "category", autorange: "reversed" });
      l.annotations = cellValues(c, t);
      return [[{ type: "heatmap", x: c.data.labels, y: c.data.labels, z: c.data.z, zmin: -1, zmax: 1,
        colorscale: [[0, t["--div-neg"]], [0.5, t["--div-mid"]], [1, t["--div-pos"]]], hoverongaps: false,
        xgap: 1, ygap: 1, colorbar: { outlinewidth: 0, tickfont: { color: t["--fg"] } } }], l];
    },
    map3d: function (c, t, l) {
      var real = c.data.z.some(function (z) { return z !== null && z !== 0; });
      var ax = function (title, extra) { return axis(t, title, Object.assign({ backgroundcolor: "rgba(0,0,0,0)", showbackground: false }, extra)); };
      var marker = { size: 3, color: t.c[0] };
      if (real) marker = { size: 3, color: c.data.z, colorscale: [[0, t["--seq-lo"]], [1, t["--seq-hi"]]],
        colorbar: { outlinewidth: 0, thickness: 12, tickfont: { color: t["--fg"] }, title: { text: c.z_label || "", font: { color: t["--fg"] } } } };
      delete l.xaxis; delete l.yaxis;
      l.margin = { l: 0, r: 0, t: 32, b: 40 };
      l.scene = { bgcolor: "rgba(0,0,0,0)", camera: { eye: phone.matches ? { x: 3, y: 3, z: 1.9 } : { x: 1.8, y: 1.8, z: 1.2 } }, xaxis: ax(c.x_label), yaxis: ax(c.y_label), zaxis: ax(c.z_label, { visible: real }) };
      return [[{ type: "scatter3d", mode: "markers", x: c.data.lon, y: c.data.lat, z: c.data.z, marker: marker }], l];
    },
    country_map: function (c, t, l) {
      delete l.xaxis; delete l.yaxis;
      l.margin = { l: 0, r: 0, t: 32, b: 0 };
      l.geo = { projection: { type: "natural earth" }, showframe: false, showcoastlines: true,
        coastlinecolor: t["--line-strong"], showcountries: true, countrycolor: t["--line-strong"], showland: true,
        landcolor: t["--bg"], bgcolor: "rgba(0,0,0,0)", showocean: false, showlakes: false };
      return [[{ type: "choropleth", locations: c.data.locations, z: c.data.values, locationmode: c.data.locationmode,
        colorscale: [[0, t["--seq-lo"]], [1, t["--seq-hi"]]], marker: { line: { color: t["--line-strong"], width: 0.5 } },
        colorbar: { outlinewidth: 0, thickness: 12, tickfont: { color: t["--fg"] } } }], l];
    },
    // Map app (DESIGN.md "map2d"): points on the point scale, or (hex mode) one choropleth of hexagons built from the server's centres.
    map2d: function (c, t, l) {
      var d = c.data, scale = [[0, t["--seq-pt-lo"]], [1, t["--seq-hi"]]];
      var bar = function (title) {
        var b = { outlinewidth: 0, thickness: 12, tickformat: ",", tickfont: { color: t["--fg"] }, title: { text: title || "", font: { color: t["--fg"] } } };
        // phone: a vertical bar would take half the 375px; lay it under the map instead
        if (phone.matches) Object.assign(b, { orientation: "h", x: 0.5, xanchor: "center", y: -0.02, yanchor: "top", len: 0.9, nticks: 4, title: { text: title || "", side: "top", font: { color: t["--fg"] } } });
        return b;
      };
      delete l.xaxis; delete l.yaxis;
      l.margin = { l: 0, r: 0, t: 32, b: phone.matches ? 72 : 0 };
      l.dragmode = phone.matches ? false : "pan";  // a finger drag scrolls the page on the phone
      l.geo = { projection: { type: "natural earth" }, fitbounds: "locations", showframe: false, showcoastlines: true,
        coastlinecolor: t["--line-strong"], showcountries: true, countrycolor: t["--line-strong"], showland: true,
        landcolor: t["--bg"], bgcolor: t["--surface"], showocean: false, showlakes: false };
      if (d.mode === "hex") {
        var ring = /* clockwise: d3-geo reads the other winding as the whole globe minus the cell */ [30, 330, 270, 210, 150, 90, 30].map(function (a) { return a * Math.PI / 180; });
        var features = d.lon.map(function (x, i) {
          return { type: "Feature", id: String(i), properties: {}, geometry: { type: "Polygon", coordinates: [ring.map(function (a) {
            return [Math.max(-180, Math.min(180, x + d.size * Math.cos(a))), Math.max(-90, Math.min(90, d.lat[i] + d.size * Math.sin(a)))];  // edge cells must not cross the antimeridian or a pole
          })] } };
        });
        return [[{ type: "choropleth", geojson: { type: "FeatureCollection", features: features }, featureidkey: "id",
          locations: features.map(function (f) { return f.id; }), z: d.count, customdata: d.lon.map(function (x, i) { return [x, d.lat[i]]; }),
          colorscale: scale, marker: { line: { color: t["--bg"], width: 0.5 } }, text: d.count.map(function (n) { return plural(n, "point"); }), hovertemplate: "%{text}<extra></extra>",
          colorbar: bar("Points per cell") }], l];
      }
      var has = [], none = [];
      d.color.forEach(function (v, i) { (v === null ? none : has).push(i); });
      var pick = function (ix, k) { return ix.map(function (i) { return d[k][i]; }); };
      var line = { color: t["--muted"], width: 0.5 };
      var traces = [];
      if (has.length) traces.push({ type: "scattergeo", mode: "markers", name: c.z_label, lon: pick(has, "lon"), lat: pick(has, "lat"), customdata: has,
        hovertemplate: "%{marker.color:,}<extra></extra>",
        marker: { size: 6, opacity: 0.8, line: line, color: pick(has, "color"), colorscale: scale, colorbar: bar(c.z_label) } });
      if (none.length) traces.push({ type: "scattergeo", mode: "markers", name: "no value", lon: pick(none, "lon"), lat: pick(none, "lat"), customdata: none,
        hovertemplate: "%{lat}, %{lon}<extra></extra>", marker: { size: 6, opacity: 0.8, line: line, color: t["--muted"] } });
      l.showlegend = traces.length > 1;
      l.legend = { orientation: "h", x: 0, y: phone.matches ? 0.06 : 0, bgcolor: t["--surface"] };
      return [traces, l];
    }
  };

  // Global rules (DESIGN.md "Global chart rules" 9, 10): thousands separators in ticks and tooltips on every figure.
  // Plain axes (c.plain: identifier, code or year columns) print as they are, with no separator.
  function plural(n, word) { return n.toLocaleString("en-US") + " " + word + (n === 1 ? "" : "s"); }
  var HOVER = { pie: "%{label}<br>%{value:,}<extra></extra>", choropleth: "%{location}<br>%{z:,}<extra></extra>" };
  function globalRules(data, l, c) {
    l.separators = ".,";
    var sc = l.scene || {}, plain = c.plain || [];
    [l.xaxis, l.yaxis, sc.xaxis, sc.yaxis, sc.zaxis].forEach(function (a) {
      if (!a || a.type === "date" || a.type === "category") return;
      var p = plain.some(function (k) { return c[k + "_label"] === a.title.text; });
      a.hoverformat = p ? "" : ",";
      if (p) a.tickformat = "";
    });
    var at = function (k) { return "%{" + k + (plain.indexOf(k) < 0 ? ":," : "") + "}"; };
    HOVER.scatter3d = at("x") + ", " + at("y") + ", " + at("z") + "<extra></extra>";
    data.forEach(function (tr) { if (HOVER[tr.type] && !tr.hovertemplate) tr.hovertemplate = HOVER[tr.type]; });
  }

  // "View as table": [head, rows] from the traces handed to Plotly (plot.data).
  function tableOf(c, tr) {
    var zip = function () {
      var a = [].slice.call(arguments);
      return a[0].map(function (_, i) { return a.map(function (col) { return col[i]; }); });
    };
    if (c.kind === "monitor") return [[c.x_label, c.y_label, "7-point mean", "Spike"], c.data.x.map(function (x, i) { return [x, c.data.y[i], c.data.mean[i], c.data.spike.indexOf(i) < 0 ? "" : "spike"]; })];
    if (c.kind === "likert") return [[c.x_label, "Count", "Share (%)"], zip(c.data.levels, c.data.counts, c.data.pct.map(function (p) { return p.toFixed(1); }))];
    if (c.kind === "crosstab") {
      var cells = [];
      c.data.y.forEach(function (yl, i) { c.data.x.forEach(function (xl, j) { cells.push([yl, xl, c.data.z[i][j], c.data.pct[i][j].toFixed(1)]); }); });
      return [[c.y_label, c.x_label, "Count", "Row (%)"], cells];
    }
    if (tr.type === "pie") return [[c.x_label || "Category", c.y_label || "Count"], zip(tr.labels, tr.values)];
    if (tr.type === "heatmap") {
      var rows = [];
      tr.y.forEach(function (yl, i) { tr.x.forEach(function (xl, j) {
        var z = tr.z[i][j]; rows.push([yl, xl, z === null ? "" : z.toFixed(2)]);
      }); });
      return [["Column", "Column", "Correlation"], rows];
    }
    if (tr.type === "scattergeo") {
      var col = tr.marker.color;  // the no-value trace has one colour, not an array
      return [[c.x_label, c.y_label, c.z_label || "Value"], zip(tr.lon, tr.lat, tr.lon.map(function (_, i) { return Array.isArray(col) ? col[i] : null; }))];
    }
    if (tr.type === "choropleth" && tr.geojson) {  // hexagon cells: centre and count
      return [[c.x_label, c.y_label, "Points per cell"], zip(tr.customdata.map(function (p) { return p[0]; }), tr.customdata.map(function (p) { return p[1]; }), tr.z)];
    }
    if (tr.type === "choropleth") return [[c.x_label || "Location", c.y_label || "Value"], zip(tr.locations, tr.z)];
    if (tr.type === "scatter3d") {
      var real = tr.z.some(function (z) { return z !== null && z !== 0; });
      return real ? [[c.x_label, c.y_label, c.z_label], zip(tr.x, tr.y, tr.z)] : [[c.x_label, c.y_label], zip(tr.x, tr.y)];
    }
    return tr.orientation === "h" ? [[c.x_label, c.y_label], zip(tr.y, tr.x)] : [[c.x_label, c.y_label], zip(tr.x, tr.y)];
  }

  function cell(tag, v, scope) {
    var e = document.createElement(tag);
    e.textContent = typeof v === "number" ? v.toLocaleString("en-US") : v === null || v === undefined ? "" : String(v);
    if (scope) e.scope = scope;
    return e;
  }

  // The table is built on first press and kept; a redraw (colour scheme, phone width) drops it and starts over.
  function tableToggle(fig, plot, c) {
    var btn = fig.querySelector(".table-toggle"), wrap = fig.querySelector(".plot-table-wrap");
    if (wrap) wrap.remove();
    plot.hidden = false;
    if (!btn) return;
    btn.setAttribute("aria-pressed", "false");
    btn.onclick = function () {
      var on = btn.getAttribute("aria-pressed") !== "true";
      wrap = fig.querySelector(".plot-table-wrap");
      if (on && !wrap) {
        var made = tableOf(c, plot.data[0]);
        plot.data.slice(c.kind === "monitor" || c.kind === "likert" ? plot.data.length : 1).forEach(function (extra) { made[1] = made[1].concat(tableOf(c, extra)[1]); });
        var table = document.createElement("table"), tr = document.createElement("tr");
        var raw = made[0].map(function (h) { return (c.plain || []).some(function (k) { return c[k + "_label"] === h; }); });
        table.className = "plot-table";
        made[0].forEach(function (h) { tr.appendChild(cell("th", h, "col")); });
        table.appendChild(document.createElement("thead")).appendChild(tr);
        var body = table.appendChild(document.createElement("tbody"));
        made[1].forEach(function (r) {
          var row = body.appendChild(document.createElement("tr"));
          r.forEach(function (v, i) { row.appendChild(cell("td", raw[i] && v != null ? String(v) : v)); });
        });
        wrap = document.createElement("div");
        wrap.className = "plot-table-wrap";
        wrap.tabIndex = 0;
        wrap.setAttribute("role", "region");
        wrap.setAttribute("aria-label", fig.querySelector(".chart-title").textContent + " data");
        wrap.appendChild(table);
        plot.after(wrap);
      }
      btn.setAttribute("aria-pressed", String(on));
      plot.hidden = on;
      if (wrap) wrap.hidden = !on;
      if (!on) Plotly.Plots.resize(plot);  // the plot was laid out while hidden
    };
  }

  function fail(plot) {
    plot.classList.remove("is-loading");
    plot.textContent = "";
    var note = document.createElement("div");
    note.className = "plot-error note note-error";
    note.setAttribute("role", "alert");
    note.textContent = "Chart could not be drawn";
    plot.appendChild(note);
  }

  // Plotly's mode bar buttons are <a> without href: make them tabbable buttons. The observer repeats it whenever
  // Plotly rebuilds the bar (any redraw or relayout); Enter and Space click like a mouse would.
  function keyboardBar(plot) {
    var fix = function () {
      plot.querySelectorAll(".modebar-btn").forEach(function (b) {
        if (b.getAttribute("tabindex") !== "0") b.setAttribute("tabindex", "0");
        if (b.getAttribute("role") !== "button") b.setAttribute("role", "button");
      });
    };
    if (!plot.dataset.kb) {
      plot.dataset.kb = "1";
      new MutationObserver(fix).observe(plot, { childList: true, subtree: true });
      plot.addEventListener("keydown", function (e) {
        var b = e.target.closest && e.target.closest(".modebar-btn");
        if (b && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); b.click(); }
      });
    }
    fix();
  }

  // A bar or donut click filters when the figure may drill (c.drill is not false) and its column has a filter dropdown (<= 50 values).
  function clickable(c) {
    if (c.kind !== "bar" && c.kind !== "donut" || c.drill === false) return false;
    var key = "f." + c.x_label;
    return [].some.call(document.querySelectorAll("form.filters select"), function (s) { return s.name === key; });
  }

  // Bar cursor (Business leaderboard, Explorer and Survey bars). Plotly itself shows no pointer over bars, so the figure gets a class
  // while a bar is hovered: `bar-click` (pointer) over a bar that filters, `no-pointer` (default) over Other.
  function barCursor(plot, c) {
    var ok = clickable(c);
    if (!ok && !(c.kind === "bar" && c.drill === false)) return;  // the last-level leaderboard still needs no-pointer (Plotly's crosshair)
    var fig = plot.closest(".chart");
    plot.on("plotly_hover", function (ev) {
      var click = ok && !(c.other && ev.points[0].curveNumber > 0);
      fig.classList.toggle("bar-click", click);
      fig.classList.toggle("no-pointer", !click);
    });
    plot.on("plotly_unhover", function () { fig.classList.remove("bar-click", "no-pointer"); });
  }

  // Click on a bar or donut slice of a categorical column sets f.<column> to that category (AND with the other
  // filters); clicking the active value again removes it. Only columns with a dropdown (<= 50 values) filter.
  // Leaderboard: no click at the last level (c.drill false), and the Other bar (trace 1) never clicks.
  function crossFilter(plot, c) {
    if (!clickable(c)) return;
    var key = "f." + c.x_label;
    plot.on("plotly_click", function (ev) {
      var pt = ev.points && ev.points[0];
      if (!pt || c.other && pt.curveNumber > 0) return;
      var value = String(c.kind === "donut" ? pt.label : pt.data && pt.data.orientation === "h" ? pt.y : pt.x);
      var p = new URLSearchParams(location.search);
      if (p.get(key) === value) p.delete(key); else p.set(key, value);
      location.assign(location.pathname + (p.toString() ? "?" + p : ""));
    });
  }

  // Map app side panel: the clicked point's row from the payload (no request; numbers are formatted by the server), or a hex cell's count.
  function mapPanel(plot, c) {
    if (c.kind !== "map2d") return;
    var box = document.querySelector(".map-panel .panel-detail");
    if (!box) return;
    plot.on("plotly_click", function (ev) {
      var pt = ev.points && ev.points[0];
      if (!pt) return;
      var n = pt.pointNumber, node;
      if (c.data.mode === "hex") {
        node = document.createElement("div");
        node.textContent = "Points in cell: " + pt.data.z[n].toLocaleString("en-US");
      } else {
        var row = c.rows[pt.data.customdata[n]];
        node = document.createElement("dl");
        c.columns.forEach(function (name, i) {
          node.appendChild(cell("dt", name));
          node.appendChild(cell("dd", row[i]));
        });
      }
      box.textContent = "";
      box.appendChild(node);
    });
  }

  function render(c, el, t) {
    var plot = el && el.querySelector(".plot");
    if (!plot) return;
    try {
      if (c.kind === "crosstab") el.style.setProperty("--plot-w", c.data.x.length * 96 + 140 + "px");  // wide tables scroll inside their card
      var made = build[c.kind](c, t, layout(t, c));
      if (c.kind === "bar" && el.closest(".map-panel")) { made[1].xaxis.nticks = 3; made[1].xaxis.tickangle = 0; }  // 340px box: three ticks fit flat
      globalRules(made[0], made[1], c);
      Plotly.newPlot(plot, made[0], made[1], c.kind === "map2d" ? Object.assign({}, CONFIG, { scrollZoom: false }) : CONFIG).then(function () { keyboardBar(plot); barCursor(plot, c); crossFilter(plot, c); mapPanel(plot, c); tableToggle(el, plot, c); }).catch(function () { fail(plot); });
    } catch (e) { fail(plot); }
  }

  // "3D view" swaps the 2D map for the hidden map3d figure; the 3D chart is drawn on first show (and redrawn on a scheme change only while shown).
  var three = null;
  function drawThree() {
    var fig = document.querySelector('figure[data-kind="map3d"]');
    if (!fig || fig.hidden || !three) return;
    render(three.c, fig, tokens());
    three.drawn = true;
  }
  function swapMaps(c3) {
    var btn = document.getElementById("map3d-toggle"), flat = document.querySelector('figure[data-kind="map2d"]'), fig = document.querySelector('figure[data-kind="map3d"]');
    if (!btn || !fig || !c3) return;
    three = { c: c3, drawn: false };
    btn.onclick = function () {
      var on = btn.getAttribute("aria-pressed") !== "true";
      btn.setAttribute("aria-pressed", String(on));
      if (flat) flat.hidden = on;
      fig.hidden = !on;
      if (on && !three.drawn) drawThree();
      var shown = on ? fig : flat, plot = shown && shown.querySelector(".js-plotly-plot");
      if (plot) Plotly.Plots.resize(plot);  // laid out while hidden
    };
  }

  function draw() {
    var t = tokens();
    charts.forEach(function (c) { render(c, document.getElementById(c.id), t); });
    if (three) { three.drawn = false; drawThree(); }
  }

  plots.forEach(function (p) { p.classList.add("is-loading"); });
  fetch("/api/datasets/" + id + "/app" + location.search)
    .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(function (body) {
      charts = body.charts;
      swapMaps(body.map3d);
      plots.forEach(function (p) { p.classList.remove("is-loading"); });
      draw();
      [phone, dark].forEach(function (m) { m.addEventListener("change", draw); });
    })
    .catch(function () { plots.forEach(fail); });
})();
