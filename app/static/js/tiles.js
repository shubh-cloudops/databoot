// Tile reorder (I7a): pointer drag from a header or figcaption, Alt+Arrow on the move handle, order kept per dataset and app.
// Expand (I7b): the tile moves into the native #tile-dialog, reopens after a filter reload; pointer glow.
(function () {
  var grid = document.querySelector(".grid[data-dataset]");
  if (!grid) return;
  var storeKey = "databoot.order." + grid.dataset.dataset + "." + grid.dataset.app;
  var live = document.getElementById("ws-live");
  var tiles = function () { return Array.prototype.slice.call(grid.children).filter(function (e) { return e.classList.contains("ws-tile"); }); };

  function save() {
    try { localStorage.setItem(storeKey, JSON.stringify(tiles().map(function (t) { return t.dataset.tile; }))); } catch (e) { /* storage blocked: the order just does not persist */ }
  }

  try {
    var stored = JSON.parse(localStorage.getItem(storeKey) || "[]");
    if (Array.isArray(stored)) {
      var all = tiles();
      var first = stored.map(function (k) { return all.filter(function (t) { return t.dataset.tile === k; })[0]; }).filter(Boolean);
      var rest = all.filter(function (t) { return first.indexOf(t) < 0; });
      grid.append.apply(grid, first.concat(rest));
    }
  } catch (e) { /* bad stored value: keep the default order */ }

  function settle(t) { t.classList.add("is-settled"); }

  // Drag: pointerdown on a header or figcaption (not on a control) of A, pointerup over B puts A in B's place.
  var from = null;
  document.addEventListener("pointerdown", function (e) {
    var a = e.target.closest && e.target.closest(".grid > .ws-tile");
    var grab = e.target.closest && e.target.closest(".ws-head, figcaption");
    var ok = grab && (!e.target.closest("button, a, select, input") || e.target.closest(".ws-move"));
    from = a && a.parentNode === grid && ok && e.button === 0 ? a : null;
  });
  document.addEventListener("pointercancel", function () { from = null; });
  document.addEventListener("pointerup", function (e) {
    var a = from;
    from = null;
    var over = a && document.elementFromPoint(e.clientX, e.clientY);
    var b = over && over.closest(".grid > .ws-tile");
    if (!b || b === a || b.parentNode !== grid) return;
    var later = a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING;  // b comes after a
    if (later) b.after(a); else b.before(a);
    settle(a);
    save();
  });

  // Keyboard: Alt+Arrow on the handle moves its tile one place; focus stays on the handle.
  document.addEventListener("keydown", function (e) {
    var h = e.altKey && e.target.closest && e.target.closest(".ws-move");
    var step = { ArrowLeft: -1, ArrowUp: -1, ArrowRight: 1, ArrowDown: 1 }[e.key];
    var t = h && step && h.closest(".grid > .ws-tile");
    if (!t || t.parentNode !== grid) return;
    e.preventDefault();
    var all = tiles(), i = all.indexOf(t), j = i + step;
    if (j < 0 || j >= all.length) return;
    if (step < 0) all[j].before(t); else all[j].after(t);
    settle(t);
    h.focus();
    save();
    announce(t, j, all.length);
  });

  // Expand: a placeholder comment keeps the tile's place while the tile lives in the dialog.
  var dialog = document.getElementById("tile-dialog");
  var shown = null, holder = null;
  var resize = function (root) {
    if (window.Plotly) Array.prototype.forEach.call(root.querySelectorAll(".js-plotly-plot"), function (p) { Plotly.Plots.resize(p); });
  };

  function expand(t) {
    if (!dialog || shown || t.parentNode !== grid) return;
    holder = document.createComment("tile " + t.dataset.tile);
    t.before(holder);
    dialog.appendChild(t);
    shown = t;
    settle(t);  // the move must not replay the entrance
    t.querySelector(".ws-expand").setAttribute("data-open", "");
    dialog.showModal();
    resize(t);
  }

  if (dialog) {
    document.addEventListener("click", function (e) {
      var b = e.target.closest && e.target.closest(".ws-expand");
      if (e.target === dialog) dialog.close();  // the backdrop
      else if (b && shown) dialog.close();
      else if (b) expand(b.closest(".grid > .ws-tile"));
    });
    dialog.addEventListener("close", function () {  // Esc (native cancel), backdrop or the button
      var t = shown, btn = t.querySelector(".ws-expand");
      shown = null;
      btn.removeAttribute("data-open");
      holder.replaceWith(t);
      resize(t);
      btn.focus();
    });
    window.addEventListener("pagehide", function () {
      if (shown) try { sessionStorage.setItem("databoot.expand", grid.dataset.dataset + ":" + shown.dataset.tile); } catch (e) { /* no storage: no reopen */ }
    });
    try {
      var want = sessionStorage.getItem("databoot.expand");
      sessionStorage.removeItem("databoot.expand");
      var found = want && tiles().filter(function (t) { return grid.dataset.dataset + ":" + t.dataset.tile === want; })[0];
      if (found) expand(found);
    } catch (e) { /* storage blocked */ }
  }

  // Glow: the tile's radial highlight follows the pointer (CSS reads --mx/--my); not wired under reduced motion.
  if (!matchMedia("(prefers-reduced-motion: reduce)").matches) {
    document.addEventListener("pointermove", function (e) {
      var t = e.target.closest && e.target.closest(".ws-tile");
      if (!t) return;
      var r = t.getBoundingClientRect();
      t.style.setProperty("--mx", (e.clientX - r.left) + "px");
      t.style.setProperty("--my", (e.clientY - r.top) + "px");
    });
  }

  function announce(t, i, n) {
    if (live) live.textContent = t.getAttribute("aria-label") + " moved to position " + (i + 1) + " of " + n;
  }
})();
