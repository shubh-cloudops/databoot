// Home portal: Choose files, Choose folder or a drop are sent as POST /upload, one PUT per file, POST /upload/{batch}/done, then /scan.
(function () {
  var portal = document.getElementById("portal");
  if (!portal) return;
  var status = portal.querySelector(".portal-status");
  var msg = document.querySelector(".portal-msg");
  var cap = Number(portal.getAttribute("data-cap"));
  var GB = 1024 * 1024 * 1024;

  function state(s) { portal.setAttribute("data-state", s); }
  function fail(text) { msg.textContent = text; msg.hidden = false; status.textContent = ""; state("idle"); }
  function size(n) { return n >= GB ? (Math.round(n / GB * 10) / 10) + " GB" : n.toLocaleString("en-US") + " bytes"; }  // as upload.cap_message

  // [{file, path}] with the first segment stripped when every path shares one (a picked or dropped folder)
  function relative(items) {
    var parts = items.map(function (it) { return it.path.replace(/^\/+/, "").split("/"); });
    var strip = parts.every(function (p) { return p.length > 1 && p[0] === parts[0][0]; }) ? 1 : 0;
    return items.map(function (it, i) { return { file: it.file, path: parts[i].slice(strip).join("/") }; });
  }

  function send(items) {
    msg.hidden = true;
    if (!items.length) return fail("No files to upload.");
    var total = items.reduce(function (n, it) { return n + it.file.size; }, 0);
    if (total > cap) {
      return fail("This upload is " + size(total) + " and the limit is " + size(cap) +
        ". For larger drives, start DataBoot with the launcher's -Folder option.");
    }
    state("busy");
    var batch, sent = 0;
    function check(r) {
      if (r.ok) return r;
      return r.json().then(function (j) { throw new Error(j.detail || "Upload failed (" + r.status + ")."); },
        function () { throw new Error("Upload failed (" + r.status + ")."); });
    }
    status.textContent = "0 of " + items.length + " files";
    fetch("/upload", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ files: items.map(function (it) { return { path: it.path, size: it.file.size }; }) }) })
      .then(check).then(function (r) { return r.json(); }).then(function (j) {
        batch = j.batch;
        return items.reduce(function (p, it) {
          return p.then(function () {
            return fetch("/upload/" + batch + "?path=" + encodeURIComponent(it.path),
              { method: "PUT", headers: { "Content-Type": "application/octet-stream" }, body: it.file })
              .then(check).then(function () { status.textContent = ++sent + " of " + items.length + " files"; });
          });
        }, Promise.resolve());
      })
      .then(function () { return fetch("/upload/" + batch + "/done", { method: "POST" }); })
      .then(check).then(function (r) { return r.json(); })
      .then(function (j) { location.assign(j.next || "/scan"); })
      .catch(function (e) { fail(e.message); });
  }

  function fromInput(input) {
    var items = Array.prototype.map.call(input.files, function (f) { return { file: f, path: f.webkitRelativePath || f.name }; });
    input.value = "";
    send(relative(items));
  }
  ["pick-files", "pick-folder"].forEach(function (id) {
    var input = document.getElementById(id);
    input.addEventListener("change", function () { fromInput(input); });
  });

  // a dropped folder is walked with webkitGetAsEntry; readEntries returns batches until it returns none
  function walk(entry) {
    return new Promise(function (done) {
      if (entry.isFile) return entry.file(function (f) { done([{ file: f, path: entry.fullPath }]); }, function () { done([]); });
      var reader = entry.createReader(), found = [];
      (function more() {
        reader.readEntries(function (batch) {
          if (!batch.length) return Promise.all(found).then(function (lists) { done([].concat.apply([], lists)); });
          batch.forEach(function (e) { found.push(walk(e)); });
          more();
        }, function () { done([]); });
      })();
    });
  }

  function over(e) { return e.dataTransfer && Array.prototype.indexOf.call(e.dataTransfer.types || [], "Files") >= 0; }
  ["dragenter", "dragover"].forEach(function (t) {
    portal.addEventListener(t, function (e) {
      if (!over(e)) return;
      e.preventDefault();
      if (portal.getAttribute("data-state") === "idle") state("over");
    });
  });
  portal.addEventListener("dragleave", function (e) {
    if (!portal.contains(e.relatedTarget) && portal.getAttribute("data-state") === "over") state("idle");
  });
  portal.addEventListener("drop", function (e) {
    e.preventDefault();
    e.stopPropagation();
    if (portal.getAttribute("data-state") === "busy") return;
    var dt = e.dataTransfer, jobs = [];
    // the item list is emptied after this handler returns, so take every entry and file now
    Array.prototype.forEach.call(dt.items || [], function (it) {
      if (it.kind !== "file") return;
      var entry = it.webkitGetAsEntry && it.webkitGetAsEntry(), file = it.getAsFile();
      jobs.push(entry ? walk(entry) : Promise.resolve(file ? [{ file: file, path: file.name }] : []));
    });
    if (!jobs.length) Array.prototype.forEach.call(dt.files || [], function (f) { jobs.push(Promise.resolve([{ file: f, path: f.name }])); });
    state("busy");
    Promise.all(jobs).then(function (lists) { state("idle"); send(relative([].concat.apply([], lists))); });
  });

  // a drop elsewhere must not make the browser open the file
  ["dragover", "drop"].forEach(function (t) { window.addEventListener(t, function (e) { if (over(e)) e.preventDefault(); }); });
})();
