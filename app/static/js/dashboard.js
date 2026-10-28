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
    ["--fg", "--bg", "--muted", "--line", "--line-strong", "--surface", "--font", "--seq-lo", "--seq-hi",
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
    bar: function (c, t, l) {
      var wide = c.data.x.some(function (s) { return String(s).length > 12; });
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
      return [[trace], l];
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
    }
  };

  // Global rules (DESIGN.md "Global chart rules" 9, 10): thousands separators in ticks and tooltips on every figure.
  var HOVER = { pie: "%{label}<br>%{value:,}<extra></extra>", choropleth: "%{location}<br>%{z:,}<extra></extra>",
    scatter3d: "%{x:,}, %{y:,}, %{z:,}<extra></extra>" };
  function globalRules(data, l) {
    l.separators = ".,";
    var sc = l.scene || {};
    [l.xaxis, l.yaxis, sc.xaxis, sc.yaxis, sc.zaxis].forEach(function (a) {
      if (a && a.type !== "date" && a.type !== "category") a.hoverformat = ",";
    });
    data.forEach(function (tr) { if (HOVER[tr.type]) tr.hovertemplate = HOVER[tr.type]; });
  }

  // "View as table": [head, rows] from the traces handed to Plotly (plot.data).
  function tableOf(c, tr) {
    var zip = function () {
      var a = [].slice.call(arguments);
      return a[0].map(function (_, i) { return a.map(function (col) { return col[i]; }); });
    };
    if (tr.type === "pie") return [[c.x_label || "Category", c.y_label || "Count"], zip(tr.labels, tr.values)];
    if (tr.type === "heatmap") {
      var rows = [];
      tr.y.forEach(function (yl, i) { tr.x.forEach(function (xl, j) {
        var z = tr.z[i][j]; rows.push([yl, xl, z === null ? "" : z.toFixed(2)]);
      }); });
      return [["Column", "Column", "Correlation"], rows];
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
        var made = tableOf(c, plot.data[0]), table = document.createElement("table"), tr = document.createElement("tr");
        table.className = "plot-table";
        made[0].forEach(function (h) { tr.appendChild(cell("th", h, "col")); });
        table.appendChild(document.createElement("thead")).appendChild(tr);
        var body = table.appendChild(document.createElement("tbody"));
        made[1].forEach(function (r) {
          var row = body.appendChild(document.createElement("tr"));
          r.forEach(function (v, i) { row.appendChild(cell("td", v)); });
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

  // Click on a bar or donut slice of a categorical column sets f.<column> to that category (AND with the other
  // filters); clicking the active value again removes it. Only columns with a dropdown (<= 50 values) filter.
  function crossFilter(plot, c) {
    if (c.kind !== "bar" && c.kind !== "donut") return;
    var key = "f." + c.x_label;
    if (![].some.call(document.querySelectorAll("form.filters select"), function (s) { return s.name === key; })) return;
    plot.on("plotly_click", function (ev) {
      var pt = ev.points && ev.points[0];
      if (!pt) return;
      var value = String(c.kind === "donut" ? pt.label : pt.data && pt.data.orientation === "h" ? pt.y : pt.x);
      var p = new URLSearchParams(location.search);
      if (p.get(key) === value) p.delete(key); else p.set(key, value);
      location.assign(location.pathname + (p.toString() ? "?" + p : ""));
    });
  }

  function draw() {
    var t = tokens();
    charts.forEach(function (c) {
      var el = document.getElementById(c.id);
      var plot = el && el.querySelector(".plot");
      if (!plot) return;
      try {
        var made = build[c.kind](c, t, layout(t, c));
        globalRules(made[0], made[1]);
        Plotly.newPlot(plot, made[0], made[1], CONFIG).then(function () { keyboardBar(plot); crossFilter(plot, c); tableToggle(el, plot, c); }).catch(function () { fail(plot); });
      } catch (e) { fail(plot); }
    });
  }

  plots.forEach(function (p) { p.classList.add("is-loading"); });
  fetch("/api/datasets/" + id + "/app" + location.search)
    .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(function (body) {
      charts = body.charts;
      plots.forEach(function (p) { p.classList.remove("is-loading"); });
      draw();
      [phone, dark].forEach(function (m) { m.addEventListener("change", draw); });
    })
    .catch(function () { plots.forEach(fail); });
})();
