// Scan screen: the log is already complete in the HTML; show it one line at a time, then open the first workspace.
(function () {
  var lines = Array.prototype.slice.call(document.querySelectorAll(".scan-log li"));
  var open = document.getElementById("open-workspace");
  if (!lines.length) return;
  var step = Math.min(350, 2500 / lines.length);
  lines.forEach(function (li) { li.hidden = true; });
  lines.forEach(function (li, i) { setTimeout(function () { li.hidden = false; }, i * step); });
  setTimeout(function () {
    var href = open && open.getAttribute("href");
    if (href && href !== "/") location.assign(href);
  }, lines.length * step);
})();
