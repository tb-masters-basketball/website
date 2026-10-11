/* The score sheet entry page (/enter/): a working copy of the paper sheet.

   The sheet's shape (rows, circles, foul and T boxes, score boxes, running
   score pages) comes from sheet-spec.json; nothing about it is written here.
   The season (teams, players, schedule) and the list of game files come from
   data/, written by build_stats.py. Drafts and published games are read from
   GitHub's API when it answers, else from the copies in data/ (as of the last
   build). Checks run live through sheet-rules.js, the Python rules ported.

   The page's model is the game file itself (`sheet`), exactly as it will be
   saved; the boxes on screen read from and write to it. Work in progress is
   kept in localStorage under mb-enter:<game_id>. A photo opened beside the
   sheet stays in the browser: it is never uploaded or stored. */
(function () {
  "use strict";

  var app = document.querySelector("[data-enter]");
  if (!app || !window.jsyaml || !window.SheetRules) return;
  var BASE = app.getAttribute("data-base");
  var yaml = window.jsyaml;
  var SR = window.SheetRules;

  var S = {
    spec: null, rules: null, season: null, index: null,
    files: { source: "site", drafts: {}, games: {} },   // game_id -> {flags?, url}
    sheet: null,              // the game file being edited
    origin: null,             // "new" | "draft" | "published" | "file"
    layout: "portrait-letter",
    page2: false,
    result: null,             // the last check
    finalProblems: [],        // what stops it being saved as final
  };

  // ------------------------------------------------------------ small helpers
  function $(sel, el) { return (el || document).querySelector(sel); }
  function $all(sel, el) { return Array.prototype.slice.call((el || document).querySelectorAll(sel)); }
  function el(tag, attrs) {
    var node = document.createElement(tag);
    for (var k in attrs || {}) {
      var v = attrs[k];
      if (v === null || v === undefined || v === false) continue;
      if (k === "text") node.textContent = v;
      else if (k === "class") node.className = v;
      else if (k.slice(0, 2) === "on") node.addEventListener(k.slice(2), v);
      else node.setAttribute(k, v === true ? "" : v);
    }
    for (var i = 2; i < arguments.length; i++) {
      var kid = arguments[i];
      if (kid === null || kid === undefined || kid === false) continue;
      if (Array.isArray(kid)) kid.forEach(function (c) { if (c) node.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
      else node.appendChild(typeof kid === "string" ? document.createTextNode(kid) : kid);
    }
    return node;
  }
  function status(text, isError) {
    var p = $("[data-enter-status]");
    p.textContent = text || "";
    p.hidden = !text;
    p.classList.toggle("enter-msg--error", !!isError);
  }
  function getJSON(url) {
    return fetch(url, { cache: "no-cache" }).then(function (r) {
      if (!r.ok) throw new Error(url + ": " + r.status);
      return r.json();
    });
  }
  function getText(url) {
    return fetch(url, { cache: "no-cache" }).then(function (r) {
      if (!r.ok) throw new Error(url + ": " + r.status);
      return r.text();
    });
  }
  var store = {
    key: function (gid) { return "mb-enter:" + gid; },
    get: function (gid) {
      try { return JSON.parse(localStorage.getItem(this.key(gid)) || "null"); } catch (e) { return null; }
    },
    set: function (gid, value) {
      try { localStorage.setItem(this.key(gid), JSON.stringify(value)); } catch (e) {}
    },
    drop: function (gid) {
      try { localStorage.removeItem(this.key(gid)); } catch (e) {}
    },
    all: function () {
      var out = [];
      try {
        for (var i = 0; i < localStorage.length; i++) {
          var k = localStorage.key(i);
          if (k && k.indexOf("mb-enter:") === 0) {
            var v = JSON.parse(localStorage.getItem(k) || "null");
            if (v && v.sheet) out.push({ game_id: k.slice(9), saved: v.saved });
          }
        }
      } catch (e) {}
      return out.sort(function (a, b) { return a.game_id < b.game_id ? 1 : -1; });
    },
  };
  function pref(name, value) {
    try {
      if (value === undefined) return localStorage.getItem("mb-enter-" + name);
      localStorage.setItem("mb-enter-" + name, value);
    } catch (e) {}
    return null;
  }

  function team(tid) { return (S.season.teams || {})[tid] || { id: tid, name: String(tid), short: String(tid) }; }
  function time12(t) {
    var m = /^(\d{1,2}):(\d{2})$/.exec(t || "");
    if (!m) return t || "";
    var h = +m[1];
    return (h % 12 || 12) + ":" + m[2] + " " + (h < 12 ? "AM" : "PM");
  }
  function gameLabel(gid) {
    var g = S.season.schedule[gid];
    if (!g) return gid;
    return team(g.home).name + " vs " + team(g.away).name;
  }
  function gameWhen(gid) {
    var g = S.season.schedule[gid];
    return g ? g.date_display + (g.time ? " · " + time12(g.time) : "") : "";
  }
  function playerName(pid) {
    var p = S.season.players[pid];
    if (!p) return null;
    return (p.number !== null && p.number !== undefined ? "#" + p.number + " " : "") + p.display;
  }
  function seasonPath(kind, gid) { return "data/" + S.season.season + "/" + kind + "/" + gid + ".yml"; }
  function isDict(v) { return v !== null && typeof v === "object" && !Array.isArray(v); }
  function sides() { return [S.sheet.home, S.sheet.away]; }
  function rowsOf(tid) {
    var t = S.sheet.teams && S.sheet.teams[tid];
    return t && Array.isArray(t.players) ? t.players : [];
  }
  function folderOf(sheet) { return sheet && sheet.status === "final" ? "games" : "drafts"; }

  // A jersey number as typed, as the file should hold it: 23, or "00" kept as text
  function numValue(text) {
    text = String(text).trim();
    if (text === "") return undefined;
    if (/^\d+$/.test(text) && (text === "0" || text[0] !== "0")) return parseInt(text, 10);
    return text;
  }

  // ------------------------------------------------------------ loading
  function init() {
    Promise.all([
      getJSON(BASE + "sheet-spec.json"),
      getJSON(BASE + "data/season.json"),
      getJSON(BASE + "data/index.json"),
    ]).then(function (got) {
      S.spec = got[0];
      S.rules = SR.make(S.spec);
      S.season = got[1];
      S.index = got[2];
      var saved = pref("layout");
      S.layout = saved && S.spec.layouts[saved] ? saved : Object.keys(S.spec.layouts)[0];
      setUpStart();
      setUpWork();
      status("");
      $("[data-start]").hidden = false;
      listFiles();
    }).catch(function (e) {
      status("The score sheet couldn't load (" + e.message + "). The site's build writes sheet-spec.json and data/ next to this page.", true);
    });
  }

  // Which games have a final file, and which have drafts: from GitHub's API
  // (as of now), or the site's copies (as of the last build).
  function listFiles() {
    var s = S.season;
    var api = s.repo ? "https://api.github.com/repos/" + s.repo + "/contents/data/" + s.season + "/" : null;
    function list(kind) {
      return getJSON(api + kind + "?ref=" + encodeURIComponent(s.branch || "main")).catch(function (e) {
        if (/: 404$/.test(e.message)) return [];        // no such folder yet
        throw e;
      });
    }
    var fromGitHub = !api ? Promise.reject(new Error("no repo")) : Promise.all([list("games"), list("drafts")]).then(function (got) {
      var files = { source: "github", games: {}, drafts: {} };
      got[0].forEach(function (f) { if (/\.ya?ml$/.test(f.name)) files.games[f.name.replace(/\.ya?ml$/, "")] = { url: f.download_url }; });
      var drafts = got[1].filter(function (f) { return /\.ya?ml$/.test(f.name); });
      return Promise.all(drafts.map(function (f) {
        var gid = f.name.replace(/\.ya?ml$/, "");
        return getText(f.download_url).then(function (text) {
          var doc = null;
          try { doc = yaml.load(text); } catch (e) {}
          files.drafts[gid] = { url: f.download_url, flags: doc && Array.isArray(doc.review) ? doc.review.length : 0 };
        }).catch(function () { files.drafts[gid] = { url: f.download_url, flags: null }; });
      })).then(function () { return files; });
    });
    fromGitHub.catch(function () {
      var files = { source: "site", games: {}, drafts: {} };
      S.index.games.forEach(function (gid) { files.games[gid] = { url: BASE + "data/" + s.season + "/games/" + gid + ".yml" }; });
      S.index.drafts.forEach(function (d) { files.drafts[d.game_id] = { url: BASE + "data/" + s.season + "/drafts/" + d.game_id + ".yml", flags: d.flags }; });
      return files;
    }).then(function (files) {
      S.files = files;
      renderDrafts();
      renderGamePick();
    });
  }

  function loadFile(kind, gid) {
    var f = S.files[kind][gid];
    var fallback = BASE + "data/" + S.season.season + "/" + kind + "/" + gid + ".yml";
    status("Opening " + gameLabel(gid) + "…");
    return getText(f ? f.url : fallback).catch(function () { return getText(fallback); }).then(function (text) {
      var sheet = yaml.load(text);
      status("");
      open(sheet, kind === "games" ? "published" : "draft");
    }).catch(function (e) {
      status("Couldn't open that file (" + e.message + ").", true);
    });
  }

  // A new sheet for a scheduled game: the two rosters filled in as on the
  // printed sheet (regular players, jersey number order), nothing else.
  function emptySheet(gid) {
    var g = S.season.schedule[gid];
    var sheet = { game_id: gid, form: S.spec.form, status: "draft", home: g.home, away: g.away, teams: {}, running: {}, lines: {}, boxes: {} };
    [g.home, g.away].forEach(function (tid) {
      var players = Object.keys(S.season.players).map(function (k) { return S.season.players[k]; })
        .filter(function (p) { return p.team === tid && !p.sub; })
        .sort(function (a, b) {
          var an = a.number === null || a.number === undefined ? 1000 : +a.number;
          var bn = b.number === null || b.number === undefined ? 1000 : +b.number;
          return an - bn || (a.display < b.display ? -1 : 1);
        }).slice(0, S.spec.roster_rows);
      sheet.teams[tid] = {
        players: players.map(function (p) {
          var row = { player: p.id };
          if (p.number !== null && p.number !== undefined) row.num = numValue(p.number);
          row.here = false;
          return row;
        }),
      };
      sheet.running[tid] = {};
      sheet.lines[tid] = S.spec.quarters.map(function () { return 0; });
      var boxes = {};
      S.spec.score_boxes.forEach(function (b) { boxes[b.key] = null; });
      sheet.boxes[tid] = boxes;
    });
    return sheet;
  }

  function readLocalFile(file) {
    if (!file) return;
    file.text().then(function (text) {
      var sheet;
      try { sheet = yaml.load(text); } catch (e) {
        status("That file isn't valid YAML: " + e.message, true);
        return;
      }
      if (!isDict(sheet) || !S.season.teams[sheet.home] || !S.season.teams[sheet.away] || sheet.home === sheet.away) {
        status("That doesn't look like a game file for this season's teams (it needs home and away from teams.yml).", true);
        return;
      }
      status("");
      open(sheet, "file", file.name);
    });
  }

  // ------------------------------------------------------------ start panel
  function setUpStart() {
    var pick = $("[data-game-pick]");
    pick.addEventListener("change", updateGamePick);
    $("[data-game-open]").addEventListener("click", function () {
      var gid = pick.value;
      if (!gid) return;
      if (S.files.drafts[gid]) loadFile("drafts", gid);
      else if (S.files.games[gid]) loadFile("games", gid);
      else open(emptySheet(gid), "new");
    });
    $("[data-file]").addEventListener("change", function (e) { readLocalFile(e.target.files[0]); e.target.value = ""; });
    var drop = $("[data-drop]");
    ["dragenter", "dragover"].forEach(function (t) {
      document.addEventListener(t, function (e) {
        if (!$("[data-start]").hidden && e.dataTransfer && Array.prototype.indexOf.call(e.dataTransfer.types, "Files") >= 0) {
          e.preventDefault();
          drop.classList.add("is-over");
        }
      });
    });
    ["dragleave", "drop"].forEach(function (t) {
      document.addEventListener(t, function (e) {
        if (t === "dragleave" && e.relatedTarget) return;
        drop.classList.remove("is-over");
      });
    });
    document.addEventListener("drop", function (e) {
      if ($("[data-start]").hidden || !e.dataTransfer || !e.dataTransfer.files.length) return;
      e.preventDefault();
      readLocalFile(e.dataTransfer.files[0]);
    });
    renderGamePick();
    renderLocal();
  }

  function renderDrafts() {
    var list = $("[data-drafts]");
    list.textContent = "";
    var ids = Object.keys(S.files.drafts).filter(function (gid) { return !S.files.games[gid]; }).sort();
    var when = S.files.source === "github" ? "from GitHub, as of now" : "from the site's copy, as of the last build" +
      (S.index.built ? " (" + new Date(S.index.built).toLocaleString("en-CA", { dateStyle: "medium", timeStyle: "short" }) + ")" : "");
    $("[data-drafts-source]").textContent = ids.length ? "Games with a draft and no final file yet, " + when + "."
      : "No drafts waiting (" + when + ").";
    ids.forEach(function (gid) {
      var flags = S.files.drafts[gid].flags;
      var label = gameLabel(gid) + (flags === null ? "" : " · " + flags + " flag" + (flags === 1 ? "" : "s"));
      list.appendChild(el("li", null, el("button", { class: "enter-list__item", type: "button", onclick: function () { loadFile("drafts", gid); } },
        el("span", { class: "enter-list__main", text: label }),
        el("span", { class: "enter-list__sub", text: gameWhen(gid) + " · " + gid }))));
    });
  }

  function renderGamePick() {
    var pick = $("[data-game-pick]");
    var keep = pick.value;
    pick.textContent = "";
    pick.appendChild(el("option", { value: "", text: "Choose a game…" }));
    var groups = {};
    var order = [];
    Object.keys(S.season.schedule).forEach(function (gid) {
      var g = S.season.schedule[gid];
      if (!g.teams_known || g.cancelled) return;
      var key = (g.week ? "Week " + g.week + " · " : "") + g.date_display;
      if (!groups[key]) { groups[key] = el("optgroup", { label: key }); order.push(key); }
      var mark = S.files.games[gid] ? " · published" : S.files.drafts[gid] ? " · draft" : "";
      groups[key].appendChild(el("option", { value: gid, text: (g.time ? time12(g.time) + " · " : "") + gameLabel(gid) + mark }));
    });
    order.forEach(function (k) { pick.appendChild(groups[k]); });
    if (keep) pick.value = keep;
    updateGamePick();
  }

  function updateGamePick() {
    var gid = $("[data-game-pick]").value;
    var btn = $("[data-game-open]");
    var note = $("[data-game-note]");
    btn.disabled = !gid;
    if (!gid) { btn.textContent = "Start an empty sheet"; note.textContent = "Every game with both teams known."; return; }
    if (S.files.drafts[gid]) { btn.textContent = "Open the draft"; note.textContent = "This game has a draft waiting to be checked."; }
    else if (S.files.games[gid]) { btn.textContent = "Reopen the published game"; note.textContent = "This game is on the site. Reopen it to correct it."; }
    else { btn.textContent = "Start an empty sheet"; note.textContent = "A new sheet with both rosters filled in."; }
  }

  function renderLocal() {
    var items = store.all();
    var box = $("[data-local]");
    var list = $("[data-local-list]");
    list.textContent = "";
    box.hidden = !items.length;
    items.forEach(function (item) {
      var gid = item.game_id;
      var when = item.saved ? new Date(item.saved).toLocaleString("en-CA", { dateStyle: "medium", timeStyle: "short" }) : "";
      list.appendChild(el("li", { class: "enter-local__row" },
        el("button", { class: "enter-list__item", type: "button", onclick: function () {
          var saved = store.get(gid);
          if (saved && saved.sheet) open(saved.sheet, saved.origin || "file", null, true);
        } }, el("span", { class: "enter-list__main", text: S.season.schedule[gid] ? gameLabel(gid) : gid }),
          el("span", { class: "enter-list__sub", text: "Last edited " + when + " · " + gid })),
        el("button", { class: "btn btn--quiet", type: "button", "aria-label": "Discard the unsaved work on " + gid, text: "Discard",
          onclick: function () { store.drop(gid); renderLocal(); } })));
    });
  }

  // ------------------------------------------------------------ the work area
  function setUpWork() {
    var layout = $("[data-layout]");
    Object.keys(S.spec.layouts).forEach(function (k) {
      var l = S.spec.layouts[k];
      var name = k.replace("-", " ").replace(/\b\w/g, function (c) { return c.toUpperCase(); });
      layout.appendChild(el("option", { value: k, text: name + " (1-" + l.page1.last + ", " + l.page1.columns + " columns)" }));
    });
    layout.value = S.layout;
    layout.addEventListener("change", function () {
      S.layout = layout.value;
      pref("layout", S.layout);
      renderSheet();
    });
    $("[data-page2]").addEventListener("click", function () {
      S.page2 = !S.page2;
      renderSheet();
    });
    $("[data-change-game]").addEventListener("click", function () {
      $("[data-work]").hidden = true;
      $("[data-start]").hidden = false;
      S.sheet = null;
      renderLocal();
      $("#enter-start-title").focus && $("[data-game-pick]").focus();
    });
    $("[data-checked-by]").addEventListener("input", function (e) {
      var v = e.target.value.trim();
      if (v) S.sheet.checked_by = v; else delete S.sheet.checked_by;
      changed();
    });
    $("[data-save-final]").addEventListener("click", function () { saveDialog("final"); });
    $("[data-save-draft]").addEventListener("click", function () { saveDialog("draft"); });
    $("[data-dialog-close]").addEventListener("click", function () { $("[data-dialog]").close(); });
    setUpPhoto();
  }

  // Show a sheet. resumed: it came from this device's unsaved work.
  function open(sheet, origin, fileName, resumed) {
    S.sheet = sheet;
    S.origin = origin;
    S.fileName = fileName || null;
    S.page2 = needsPage2();
    $("[data-start]").hidden = true;
    $("[data-work]").hidden = false;
    var gid = sheet.game_id;
    var kinds = { "new": "New sheet", draft: "Draft", published: "Published game: correcting it", file: "From " + (fileName || "a file") };
    $("[data-work-title]").textContent = S.season.schedule[gid] ? gameLabel(gid) : team(sheet.home).name + " vs " + team(sheet.away).name;
    $("[data-work-sub]").textContent = [S.season.schedule[gid] ? gameWhen(gid) : null, String(gid), resumed ? "Unsaved work on this device" : kinds[origin]]
      .filter(Boolean).join(" · ");
    $("[data-checked-by]").value = sheet.checked_by || "";
    // Unsaved work from earlier on this device?
    var banner = $("[data-resume]");
    banner.hidden = true;
    var saved = !resumed && store.get(gid);
    if (saved && saved.sheet && SR.dump(saved.sheet) !== SR.dump(sheet)) {
      $("[data-resume-text]").textContent = "You have unsaved work on this game on this device (last edited " +
        new Date(saved.saved).toLocaleString("en-CA", { dateStyle: "medium", timeStyle: "short" }) + ").";
      banner.hidden = false;
      $("[data-resume-use]").onclick = function () { open(saved.sheet, saved.origin || origin, fileName, true); };
      $("[data-resume-drop]").onclick = function () { store.drop(gid); banner.hidden = true; };
    }
    renderSheet();
    window.scrollTo({ top: $("[data-work]").getBoundingClientRect().top + window.scrollY - 8 });
  }

  function needsPage2() {
    var p1 = S.spec.layouts[S.layout].page1.last;
    return sides().some(function (tid) {
      var r = (S.sheet.running || {})[tid];
      var high = isDict(r) && Object.keys(r).some(function (k) { return +k > p1; });
      return high || rowsOf(tid).some(function (row) { return typeof row.ft === "string" && row.ft.length > S.spec.ft_circles_per_page; });
    });
  }

  // ------------------------------------------------------------ the sheet
  function renderSheet(focus) {
    if (focus === undefined) focus = focusKey();
    var root = $("[data-sheet]");
    root.textContent = "";
    if (needsPage2()) S.page2 = true;
    var p2 = $("[data-page2]");
    p2.setAttribute("aria-pressed", String(S.page2));
    p2.textContent = S.page2 ? "Page 2: shown" : "Page 2: hidden";
    root.classList.toggle("sheet--page2", S.page2);
    root.appendChild(renderHeader());
    sides().forEach(function (tid, n) { root.appendChild(renderTeam(tid, n)); });
    root.appendChild(renderNotes());
    root.appendChild(renderRunning());
    changed(true);
    restoreFocus(focus);
  }

  function renderHeader() {
    var sheet = S.sheet;
    var g = S.season.schedule[sheet.game_id];
    function item(label, at, value) {
      return el("div", { class: "sheet-head__item", "data-at": at }, el("span", { class: "sheet-label", text: label }), el("span", { class: "sheet-head__value", text: value }));
    }
    var sk = el("input", { class: "enter-input", type: "text", autocomplete: "off", id: "sheet-scorekeeper", value: sheet.scorekeeper || "",
      oninput: function (e) {
        var v = e.target.value.trim();
        if (v) sheet.scorekeeper = v; else delete sheet.scorekeeper;
        changed();
      } });
    return el("section", { class: "sheet-head", "aria-label": "Game details" },
      el("div", { class: "sheet-head__items" },
        item("Date", "date", g ? g.date_display : "—"),
        item("Start time", "time", g ? time12(g.time) : "—"),
        item("Game ID", "game_id", String(sheet.game_id)),
        item("Form", "form", String(sheet.form)),
        item("Status", "status", String(sheet.status)),
        el("label", { class: "sheet-head__item sheet-head__item--wide", "data-at": "scorekeeper", for: "sheet-scorekeeper" },
          el("span", { class: "sheet-label", text: "Scorekeeper" }), sk)),
      el("ul", { class: "sheet-msgs", "data-msgs": "head" }));
  }

  function renderTeam(tid, n) {
    var t = team(tid);
    var spec = S.spec;
    var sideName = n === 0 ? "Home" : "Away";
    var ftCols = spec.ft_circles_per_page * (S.page2 ? 2 : 1);
    var head = el("tr", null,
      el("th", { scope: "col", class: "roster__num", text: "#" }),
      el("th", { scope: "col", class: "roster__here", text: "Here" }),
      el("th", { scope: "col", class: "roster__player", text: "Player" }),
      el("th", { scope: "col", class: "roster__ft", text: "Free throws" + (S.page2 ? " (1-" + spec.ft_circles + ")" : "") }),
      el("th", { scope: "col", class: "roster__fouls" }, "Fouls · ", el("span", { class: "sheet-t-label", text: "T" })),
      el("th", { scope: "col", class: "roster__tools" }, el("span", { class: "visually-hidden", text: "Row" })));
    var body = el("tbody");
    var rows = rowsOf(tid);
    var count = Math.max(spec.roster_rows, rows.length);
    for (var i = 0; i < count; i++) {
      body.appendChild(renderRow(tid, i, rows[i], ftCols));
      body.appendChild(el("tr", { class: "roster__msgrow", "data-msgrow": "teams." + tid + ".players." + i, hidden: true },
        el("td", { colspan: "6" }, el("ul", { class: "sheet-msgs", "data-msgs": "teams." + tid + ".players." + i }))));
    }
    var table = el("table", { class: "roster", "data-at": "teams." + tid + ".players" },
      el("caption", { class: "visually-hidden", text: sideName + " roster: " + t.name }), el("thead", null, head), body);

    // the score boxes under the roster, and where each quarter's line was drawn
    var boxes = isDict(S.sheet.boxes) && isDict(S.sheet.boxes[tid]) ? S.sheet.boxes[tid] : null;
    var lines = isDict(S.sheet.lines) && Array.isArray(S.sheet.lines[tid]) ? S.sheet.lines[tid] : null;
    var boxCells = spec.score_boxes.map(function (b) {
      var v = boxes ? boxes[b.key] : null;
      return el("label", { class: "sheet-box", "data-at": "boxes." + tid + "." + b.key },
        el("span", { class: "sheet-label", text: b.label }),
        el("input", { class: "sheet-box__input", type: "text", inputmode: "numeric", autocomplete: "off", maxlength: String(b.digits),
          style: "--digits:" + b.digits, value: v === null || v === undefined ? "" : String(v), "data-box": b.key,
          "aria-label": t.name + " " + b.label + " box", oninput: function (e) { setBox(tid, b.key, e.target.value); } }));
    });
    var lineCells = spec.quarters.map(function (q, k) {
      var v = lines ? lines[k] : null;
      return el("label", { class: "sheet-box sheet-box--line", "data-at": "lines." + tid + "." + k },
        el("span", { class: "sheet-label", text: q }),
        el("input", { class: "sheet-box__input", type: "text", inputmode: "numeric", autocomplete: "off", maxlength: "3", style: "--digits:3",
          value: v === null || v === undefined ? "" : String(v), "aria-label": t.name + ": the " + q + " line is under",
          oninput: function (e) { setLine(tid, k, e.target.value); } }));
    });
    return el("section", { class: "sheet-team", "data-at": "teams." + tid, "aria-label": sideName + ": " + t.name },
      el("div", { class: "sheet-team__bar" },
        el("span", { class: "sheet-team__side", text: sideName }),
        el("span", { class: "chip chip--" + (t.slot || 1), "aria-hidden": "true" }),
        el("span", { class: "sheet-team__name", text: t.name })),
      el("div", { class: "sheet-scroll" }, table),
      el("ul", { class: "sheet-msgs", "data-msgs": "teams." + tid }),
      el("div", { class: "sheet-boxes", "data-at": "boxes." + tid },
        el("div", { class: "sheet-boxes__row" }, el("span", { class: "sheet-boxes__label", text: "Score at end of" }), boxCells),
        el("div", { class: "sheet-boxes__row", "data-at": "lines." + tid }, el("span", { class: "sheet-boxes__label", text: "Line drawn under" }), lineCells)),
      el("ul", { class: "sheet-msgs", "data-msgs": "boxes." + tid }));
  }

  function renderRow(tid, i, row, ftCols) {
    var spec = S.spec;
    var base = "teams." + tid + ".players." + i;
    var r = isDict(row) ? row : {};
    var t = team(tid);
    var placeholder = !row;
    var rowLabel = t.short + " row " + (i + 1);

    var num = el("input", { class: "roster__numinput", type: "text", inputmode: "numeric", autocomplete: "off", maxlength: "2",
      value: r.num === undefined || r.num === null ? "" : String(r.num), "aria-label": rowLabel + ": jersey number",
      oninput: function (e) { editRow(tid, i, function (x) { var v = numValue(e.target.value); if (v === undefined) delete x.num; else x.num = v; }); } });

    var here = el("button", { class: "sheet-tick", type: "button", "aria-pressed": String(r.here === true), "aria-label": rowLabel + ": here",
      onclick: function (e) {
        var on = e.currentTarget.getAttribute("aria-pressed") !== "true";
        e.currentTarget.setAttribute("aria-pressed", String(on));
        editRow(tid, i, function (x) { x.here = on; });
      } });

    // the player: a roster id, or a sub's name written in by hand
    var select = el("select", { class: "roster__select", "aria-label": rowLabel + ": player" });
    select.appendChild(el("option", { value: "", text: "—" }));
    var mine = Object.keys(S.season.players).map(function (k) { return S.season.players[k]; })
      .filter(function (p) { return p.team === tid; })
      .sort(function (a, b) { return (a.sub - b.sub) || (a.display < b.display ? -1 : 1); });
    mine.forEach(function (p) { select.appendChild(el("option", { value: p.id, text: playerName(p.id) + (p.sub ? " (sub)" : "") })); });
    if (r.player !== undefined && r.player !== null && !mine.some(function (p) { return p.id === r.player; })) {
      select.appendChild(el("option", { value: String(r.player), text: (playerName(r.player) || String(r.player)) + " (not on " + t.short + ")" }));
    }
    select.appendChild(el("option", { value: "\u0000name", text: "Written in by hand…" }));
    var written = r.player === undefined || r.player === null;
    select.value = !written ? String(r.player) : (r.name ? "\u0000name" : "");
    var name = el("input", { class: "enter-input roster__name", type: "text", autocomplete: "off", placeholder: "First L.", value: r.name || "",
      "aria-label": rowLabel + ": name as written", hidden: !(written && r.name !== undefined) && select.value !== "\u0000name",
      oninput: function (e) { editRow(tid, i, function (x) { delete x.player; x.name = e.target.value; }); } });
    select.addEventListener("change", function () {
      var v = select.value;
      name.hidden = v !== "\u0000name";
      editRow(tid, i, function (x) {
        if (v === "\u0000name") { delete x.player; x.name = name.value; name.focus(); }
        else if (v === "") { delete x.player; delete x.name; }
        else {
          x.player = v;
          delete x.name;
          var p = S.season.players[v];
          if ((x.num === undefined || x.num === null || x.num === "") && p && p.number !== null && p.number !== undefined) {
            x.num = numValue(p.number);
            num.value = String(x.num);
          }
        }
      });
    });

    // free-throw circles, in order: empty -> made -> missed -> empty
    var ft = typeof r.ft === "string" ? r.ft : "";
    var circles = el("div", { class: "sheet-circles", "data-at": base + ".ft" });
    for (var k = 0; k < ftCols; k++) {
      if (k && k % 5 === 0) circles.appendChild(el("span", { class: "sheet-circles__gap", "aria-hidden": "true" }));
      circles.appendChild(el("button", { class: "sheet-circle", type: "button", "data-at": base + ".ft." + k, "data-k": String(k),
        onclick: (function (k) { return function () { cycleFt(tid, i, k); }; })(k) }));
    }
    paintCircles(circles, ft, rowLabel);

    var marks = el("div", { class: "sheet-marks" });
    var fouls = el("div", { class: "sheet-marks__group", "data-at": base + ".fouls", role: "group", "aria-label": rowLabel + ": fouls" });
    for (var f = 0; f < spec.personal_foul_boxes; f++) {
      fouls.appendChild(el("button", { class: "sheet-mark", type: "button", "data-n": String(f), onclick: (function (f) { return function () { setCount(tid, i, "fouls", f); }; })(f) }));
    }
    var techs = el("div", { class: "sheet-marks__group sheet-marks__group--t", "data-at": base + ".tech", role: "group", "aria-label": rowLabel + ": technical fouls" });
    for (var x = 0; x < spec.technical_boxes; x++) {
      techs.appendChild(el("button", { class: "sheet-mark sheet-mark--t", type: "button", "data-n": String(x), onclick: (function (x) { return function () { setCount(tid, i, "tech", x); }; })(x) }));
    }
    marks.appendChild(fouls);
    marks.appendChild(techs);
    paintMarks(fouls, r.fouls, "Foul");
    paintMarks(techs, r.tech, "T");

    var tools = placeholder ? el("span") : el("button", { class: "enter-icon-btn enter-icon-btn--small", type: "button", "aria-label": "Clear " + rowLabel, text: "✕",
      onclick: function () { clearRow(tid, i); } });

    return el("tr", { class: "roster__row" + (placeholder ? " is-blank" : ""), "data-at": base },
      el("td", { class: "roster__num", "data-at": base + ".num" }, num),
      el("td", { class: "roster__here", "data-at": base + ".here" }, here),
      el("td", { class: "roster__player", "data-at": base + ".player" }, el("div", { class: "roster__who" }, select, name)),
      el("td", { class: "roster__ft" }, circles),
      el("td", { class: "roster__fouls" }, marks),
      el("td", { class: "roster__tools" }, tools));
  }

  function paintCircles(box, ft, rowLabel) {
    $all(".sheet-circle", box).forEach(function (c) {
      var k = +c.getAttribute("data-k");
      var v = ft[k] || "";
      c.setAttribute("data-v", v);
      // only the circles already marked and the next one can be changed: ft is the circles in order
      c.disabled = k > ft.length;
      var what = v === "M" ? "made" : v === "X" ? "missed" : "empty";
      c.setAttribute("aria-label", (rowLabel ? rowLabel + ": " : "") + "free throw " + (k + 1) + ", " + what);
      if (rowLabel) c.setAttribute("data-label", rowLabel);
      else if (c.getAttribute("data-label")) c.setAttribute("aria-label", c.getAttribute("data-label") + ": free throw " + (k + 1) + ", " + what);
    });
  }
  function paintMarks(group, n, word) {
    n = typeof n === "number" ? n : 0;
    $all(".sheet-mark", group).forEach(function (b) {
      var k = +b.getAttribute("data-n");
      b.setAttribute("aria-pressed", String(k < n));
      b.setAttribute("aria-label", word + " " + (k + 1) + (k < n ? ", slashed" : ""));
    });
  }

  // Change one roster row, keeping the file's key order. Typing in a blank row
  // adds it to the file as the next row (no empty rows in between).
  function editRow(tid, i, fn) {
    if (!isDict(S.sheet.teams[tid]) || !Array.isArray(S.sheet.teams[tid].players)) S.sheet.teams[tid] = { players: [] };
    var rows = S.sheet.teams[tid].players;
    var fresh = i >= rows.length;
    var focus = fresh ? focusKey() : null;
    if (fresh) {
      if (focus) focus.at = focus.at.replace("teams." + tid + ".players." + i, "teams." + tid + ".players." + rows.length);
      i = rows.length;
      rows.push({ here: false });
    }
    var row = isDict(rows[i]) ? rows[i] : {};
    fn(row);
    var ordered = {};
    ["player", "name", "num", "here", "ft", "fouls", "tech"].forEach(function (k) { if (k in row) ordered[k] = row[k]; });
    Object.keys(row).forEach(function (k) { if (!(k in ordered)) ordered[k] = row[k]; });
    if (ordered.ft === "") delete ordered.ft;
    if (ordered.fouls === 0) delete ordered.fouls;
    if (ordered.tech === 0) delete ordered.tech;
    if (!("here" in ordered)) ordered.here = false;
    rows[i] = ordered;
    if (fresh) {
      renderSheet(focus);
      changed();
      return;
    }
    changed();
  }

  // Where the focus is, so a redraw can put it back
  function focusKey() {
    var a = document.activeElement;
    var holder = a && a.closest && a.closest("[data-sheet] [data-at]");
    if (!holder) return null;
    return { at: holder.getAttribute("data-at"), cls: (a.className || "").split(" ")[0], self: holder === a,
      start: typeof a.selectionStart === "number" ? a.selectionStart : null };
  }
  function restoreFocus(f) {
    if (!f) return;
    var holder = $('[data-sheet] [data-at="' + f.at + '"]');
    if (!holder) return;
    var target = f.self ? holder : (f.cls && holder.querySelector("." + f.cls)) || holder.querySelector("input, select, button");
    if (!target) return;
    target.focus({ preventScroll: true });
    if (f.start !== null && typeof target.setSelectionRange === "function") {
      try { target.setSelectionRange(f.start, f.start); } catch (e) {}
    }
  }

  function cycleFt(tid, i, k) {
    var row = rowsOf(tid)[i] || {};
    var ft = typeof row.ft === "string" ? row.ft : "";
    if (k > ft.length) return;
    var v = ft[k] || "";
    var next = v === "" ? "M" : v === "M" ? "X" : "";
    // an inner circle goes M <-> X; only the last one can be emptied
    if (next === "" && k < ft.length - 1) next = "M";
    var out = ft.slice(0, k) + next + ft.slice(k + 1);
    i = Math.min(i, rowsOf(tid).length);
    editRow(tid, i, function (x) { x.ft = out; });
    var circles = $('[data-at="teams.' + tid + ".players." + i + '.ft"]');
    if (circles) {
      paintCircles(circles, out);
      var again = circles.querySelector('[data-k="' + k + '"]');
      if (again && document.activeElement !== again) again.focus();
    }
  }

  function setCount(tid, i, key, k) {
    var row = rowsOf(tid)[i] || {};
    var n = typeof row[key] === "number" ? row[key] : 0;
    var next = k < n ? k : k + 1;       // tap a slashed box to clear it (and any after it)
    i = Math.min(i, rowsOf(tid).length);
    editRow(tid, i, function (x) { x[key] = next; });
    var group = $('[data-at="teams.' + tid + ".players." + i + "." + key + '"]');
    if (group) {
      paintMarks(group, next, key === "tech" ? "T" : "Foul");
      var again = group.querySelector('[data-n="' + k + '"]');
      if (again && document.activeElement !== again) again.focus();
    }
  }

  function clearRow(tid, i) {
    var rows = rowsOf(tid);
    rows.splice(i, 1);
    // review flags on later rows of this team move up with them
    if (Array.isArray(S.sheet.review)) {
      var prefix = "teams." + tid + ".players.";
      S.sheet.review = S.sheet.review.filter(function (item) {
        var m = isDict(item) && typeof item.at === "string" && item.at.indexOf(prefix) === 0 ? /^(\d+)(.*)$/.exec(item.at.slice(prefix.length)) : null;
        if (!m) return true;
        var j = +m[1];
        if (j === i) return false;
        if (j > i) item.at = prefix + (j - 1) + m[2];
        return true;
      });
      if (!S.sheet.review.length) delete S.sheet.review;
    }
    renderSheet();
  }

  function setBox(tid, key, text) {
    if (!isDict(S.sheet.boxes)) S.sheet.boxes = {};
    if (!isDict(S.sheet.boxes[tid])) S.sheet.boxes[tid] = {};
    text = text.trim();
    S.sheet.boxes[tid][key] = text === "" ? null : /^\d+$/.test(text) ? parseInt(text, 10) : text;
    changed();
  }
  function setLine(tid, k, text) {
    if (!isDict(S.sheet.lines)) S.sheet.lines = {};
    var cur = Array.isArray(S.sheet.lines[tid]) ? S.sheet.lines[tid] : [];
    var lines = S.spec.quarters.map(function (q, n) { return cur[n] === undefined ? 0 : cur[n]; });
    text = text.trim();
    lines[k] = text === "" ? 0 : /^\d+$/.test(text) ? parseInt(text, 10) : text;
    S.sheet.lines[tid] = lines;
    changed();
  }

  // ---- notes
  function renderNotes() {
    var notes = Array.isArray(S.sheet.notes) ? S.sheet.notes : [];
    var list = el("ol", { class: "sheet-notes__list" });
    notes.forEach(function (note, n) { list.appendChild(renderNote(note, n)); });
    return el("section", { class: "sheet-notes", "data-at": "notes", "aria-labelledby": "sheet-notes-title" },
      el("div", { class: "sheet-section-bar" },
        el("h3", { class: "sheet-section-bar__title", id: "sheet-notes-title", text: "Notes · flagrant fouls: team, player #, quarter, what happened" })),
      list,
      el("button", { class: "btn btn--quiet sheet-notes__add", type: "button", text: "Add a note", onclick: function () {
        if (!Array.isArray(S.sheet.notes)) S.sheet.notes = [];
        S.sheet.notes.push({ team: S.sheet.home, num: null, q: 1, kind: "flagrant", text: "" });
        renderSheet();
        var last = $all(".sheet-note");
        if (last.length) $("select", last[last.length - 1]).focus();
      } }),
      el("ul", { class: "sheet-msgs", "data-msgs": "notes" }));
  }

  function renderNote(note, n) {
    var at = "notes." + n;
    var d = isDict(note) ? note : {};
    function set(key, value) {
      var cur = S.sheet.notes[n];
      if (!isDict(cur)) cur = S.sheet.notes[n] = {};
      var next = {};
      ["team", "num", "q", "kind", "text"].forEach(function (k) {
        if (k === key) next[k] = value;
        else if (k in cur) next[k] = cur[k];
      });
      Object.keys(cur).forEach(function (k) { if (!(k in next)) next[k] = cur[k]; });
      S.sheet.notes[n] = next;
      changed();
    }
    var teamSel = el("select", { class: "enter-select enter-select--small", "aria-label": "Note " + (n + 1) + ": team", onchange: function (e) { set("team", e.target.value); } },
      sides().map(function (tid) { return el("option", { value: tid, text: team(tid).short }); }));
    teamSel.value = d.team;
    var qSel = el("select", { class: "enter-select enter-select--small", "aria-label": "Note " + (n + 1) + ": quarter",
      onchange: function (e) { set("q", e.target.value === "OT" ? "OT" : +e.target.value); } },
      S.spec.quarters.map(function (q, k) { return el("option", { value: String(k + 1), text: q }); }).concat([el("option", { value: "OT", text: "OT" })]));
    qSel.value = String(d.q);
    var kindSel = el("select", { class: "enter-select enter-select--small", "aria-label": "Note " + (n + 1) + ": kind", onchange: function (e) { set("kind", e.target.value); } },
      el("option", { value: "flagrant", text: "Flagrant" }), el("option", { value: "note", text: "Note" }));
    kindSel.value = d.kind || "note";
    return el("li", { class: "sheet-note", "data-at": at },
      el("label", { class: "enter-field", "data-at": at + ".team" }, el("span", { text: "Team" }), teamSel),
      el("label", { class: "enter-field", "data-at": at + ".num" }, el("span", { text: "#" }),
        el("input", { class: "enter-input sheet-note__num", type: "text", inputmode: "numeric", maxlength: "2", autocomplete: "off",
          value: d.num === null || d.num === undefined ? "" : String(d.num), oninput: function (e) { var v = numValue(e.target.value); set("num", v === undefined ? null : v); } })),
      el("label", { class: "enter-field", "data-at": at + ".q" }, el("span", { text: "Qtr" }), qSel),
      el("label", { class: "enter-field", "data-at": at + ".kind" }, el("span", { text: "Kind" }), kindSel),
      el("label", { class: "enter-field sheet-note__text" }, el("span", { text: "What happened" }),
        el("input", { class: "enter-input", type: "text", autocomplete: "off", value: d.text || "", oninput: function (e) { set("text", e.target.value); } })),
      el("button", { class: "enter-icon-btn", type: "button", "aria-label": "Remove note " + (n + 1), text: "✕", onclick: function () {
        S.sheet.notes.splice(n, 1);
        if (!S.sheet.notes.length) delete S.sheet.notes;
        renderSheet();
      } }));
  }

  // ---- running score: the totals down the middle, home scorer left, away right
  function renderRunning() {
    var layout = S.spec.layouts[S.layout];
    var pages = [["Page 1", layout.page1]];
    if (S.page2) pages.push(["Page 2", layout.page2]);
    var home = team(S.sheet.home), away = team(S.sheet.away);
    var section = el("section", { class: "sheet-running", "data-at": "running", "aria-labelledby": "sheet-running-title" },
      el("div", { class: "sheet-section-bar" },
        el("h3", { class: "sheet-section-bar__title", id: "sheet-running-title", text: "Running score" }),
        el("span", { class: "sheet-section-bar__hint", text: "Type the scorer's number beside each total. Arrows and Enter move between boxes." })));
    pages.forEach(function (pg) {
      var p = pg[1];
      var grid = el("div", { class: "sheet-running__page", style: "--cols:" + p.columns, role: "group", "aria-label": "Running score, " + pg[0].toLowerCase() + ": " + p.first + " to " + p.last });
      if (S.page2) section.appendChild(el("h4", { class: "sheet-running__pagename", text: pg[0] + " · " + p.first + " to " + p.last }));
      for (var c = 0; c < p.columns; c++) {
        var tbody = el("tbody");
        for (var r = 0; r < p.per_column; r++) {
          var total = p.first + c * p.per_column + r;
          if (total > p.last) break;
          tbody.appendChild(el("tr", null,
            runCell(S.sheet.home, total, home, "home"),
            el("th", { scope: "row", class: "rs__total", text: String(total) }),
            runCell(S.sheet.away, total, away, "away")));
        }
        grid.appendChild(el("table", { class: "rs" },
          el("thead", null, el("tr", null,
            el("th", { scope: "col", class: "rs__head", title: home.name }, home.short, " #"),
            el("th", { scope: "col", class: "rs__head", text: "Pts" }),
            el("th", { scope: "col", class: "rs__head", title: away.name }, away.short, " #"))),
          tbody));
      }
      section.appendChild(grid);
    });
    section.appendChild(el("ul", { class: "sheet-msgs", "data-msgs": "running" }));
    section.addEventListener("keydown", runKeys);
    return section;
  }

  function runCell(tid, total, t, side) {
    var r = isDict(S.sheet.running) && isDict(S.sheet.running[tid]) ? S.sheet.running[tid] : {};
    var v = r[String(total)];
    var input = el("input", { class: "rs__input", type: "text", inputmode: "numeric", autocomplete: "off", maxlength: "2",
      value: v === undefined || v === null ? "" : String(v), placeholder: " ", "data-side": side, "data-total": String(total),
      "aria-label": t.name + " scorer at " + total,
      oninput: function (e) { setRun(tid, total, e.target.value); } });
    return el("td", { class: "rs__cell rs__cell--" + side, "data-at": "running." + tid + "." + total }, input);
  }

  function setRun(tid, total, text) {
    if (!isDict(S.sheet.running)) S.sheet.running = {};
    if (!isDict(S.sheet.running[tid])) S.sheet.running[tid] = {};
    var v = numValue(text);
    if (v === undefined) delete S.sheet.running[tid][String(total)];
    else S.sheet.running[tid][String(total)] = v;
    changed();
  }

  function runKeys(e) {
    var t = e.target;
    if (!t.classList || !t.classList.contains("rs__input")) return;
    var side = t.getAttribute("data-side");
    var total = +t.getAttribute("data-total");
    var layout = S.spec.layouts[S.layout];
    var page = total >= layout.page2.first ? layout.page2 : layout.page1;
    var target = null;
    function at(s, n) { return $('.rs__input[data-side="' + s + '"][data-total="' + n + '"]'); }
    var start = t.selectionStart === 0 && t.selectionEnd === 0;
    var end = t.selectionStart === t.value.length;
    if (e.key === "ArrowDown" || e.key === "Enter") target = at(side, total + 1);
    else if (e.key === "ArrowUp") target = at(side, total - 1);
    else if (e.key === "ArrowRight" && end) target = side === "home" ? at("away", total) : at("home", total + page.per_column);
    else if (e.key === "ArrowLeft" && start) target = side === "away" ? at("home", total) : at("away", total - page.per_column);
    else return;
    if (target) {
      e.preventDefault();
      target.focus();
      target.select();
    } else if (e.key === "Enter") {
      e.preventDefault();
    }
  }

  // ------------------------------------------------------------ checking
  var saveTimer = null;
  function changed(fromRender) {
    var sheet = S.sheet;
    if (!sheet) return;
    var ctx = { stem: sheet.game_id, folder: folderOf(sheet), teams: S.season.teams, players: S.season.players, schedule: S.season.schedule };
    S.result = S.rules.checkFull(sheet, ctx);
    // What would stop it being saved as final: the same file, made final
    var fin = finalSheet(sheet, sheet.checked_by || "x");
    S.finalProblems = S.rules.check(fin, Object.assign({}, ctx, { folder: "games" }))[1]
      .filter(function (p) { return p.level === "error"; });
    paintProblems();
    renderChecks();
    renderSave();
    paintLines();
    if (!fromRender) {
      clearTimeout(saveTimer);
      saveTimer = setTimeout(function () {
        store.set(sheet.game_id, { sheet: sheet, origin: S.origin, saved: new Date().toISOString() });
      }, 400);
    }
  }

  function finalSheet(sheet, checkedBy) {
    var out = {};
    Object.keys(sheet).forEach(function (k) { if (k !== "review" && k !== "checked_by") out[k] = sheet[k]; });
    out.status = "final";
    out.checked_by = checkedBy;
    return out;
  }

  // The box a path names, or the nearest thing on screen that holds it
  function boxFor(at) {
    var parts = String(at).split(".");
    while (parts.length) {
      var found = document.querySelector('[data-sheet] [data-at="' + parts.join(".") + '"], .enter-save [data-at="' + parts.join(".") + '"]');
      if (found) return found;
      parts.pop();
    }
    return $(".sheet-head");
  }
  // Where a path's message is listed: under its roster row, its team, its
  // score boxes, the running score, the notes, or the game details
  function msgsFor(at) {
    var p = String(at).split(".");
    var key = "head";
    if (p[0] === "teams" && p.length >= 4) key = "teams." + p[1] + ".players." + p[3];
    else if (p[0] === "teams" && p.length >= 2) key = "teams." + p[1];
    else if ((p[0] === "boxes" || p[0] === "lines") && p.length >= 2) key = "boxes." + p[1];
    else if (p[0] === "boxes" || p[0] === "lines") key = "boxes." + S.sheet.home;
    else if (p[0] === "running") key = "running";
    else if (p[0] === "notes") key = "notes";
    else if (p[0] === "review" || p[0] === "checked_by") key = "save";
    return key === "save" ? null : $('[data-msgs="' + key + '"]');
  }

  function label(at) {
    var p = String(at).split(".");
    var name = function (tid) { return team(tid).short; };
    if (p[0] === "running" && p.length === 3) return "Running score, " + name(p[1]) + " " + p[2];
    if (p[0] === "running") return "Running score" + (p[1] ? ", " + name(p[1]) : "");
    if (p[0] === "teams" && p.length >= 4) {
      var row = name(p[1]) + " row " + (+p[3] + 1);
      var parts = { num: "#", player: "player", here: "Here", ft: "free throws", fouls: "fouls", tech: "T" };
      if (p[4] === "ft" && p[5] !== undefined) return row + ", free throw " + (+p[5] + 1);
      return p[4] ? row + ", " + (parts[p[4]] || p[4]) : row;
    }
    if (p[0] === "teams") return p[1] ? name(p[1]) + " roster" : "Rosters";
    if (p[0] === "boxes") return p[2] ? name(p[1]) + " " + (S.spec.score_boxes.filter(function (b) { return b.key === p[2]; })[0] || { label: p[2] }).label + " box" : "Score boxes";
    if (p[0] === "lines") return p[2] !== undefined ? name(p[1]) + " " + (S.spec.quarters[+p[2]] || "Q" + (+p[2] + 1)) + " line" : (p[1] ? name(p[1]) + " quarter lines" : "Quarter lines");
    if (p[0] === "notes") return p[1] !== undefined ? "Note " + (+p[1] + 1) : "Notes";
    var fields = { game_id: "Game ID", form: "Form", status: "Status", home: "Home team", away: "Away team", review: "Review list", checked_by: "Checked by", "": "The file" };
    return fields[at] || at;
  }

  function reviewItems() {
    return (Array.isArray(S.sheet.review) ? S.sheet.review : []).map(function (item, n) { return { item: item, n: n }; })
      .filter(function (x) { return isDict(x.item); });
  }

  var tipId = 0;
  function paintProblems() {
    $all(".is-error, .is-warning, .is-flag", app).forEach(function (n) {
      n.classList.remove("is-error", "is-warning", "is-flag");
      n.removeAttribute("data-tip");
      var inner = n.matches("input, select, button") ? n : n.querySelector("input, select, button");
      if (inner) { inner.removeAttribute("aria-invalid"); inner.removeAttribute("aria-describedby"); }
    });
    $all("[data-msgs]", app).forEach(function (ul) { ul.textContent = ""; });
    $all("[data-msgrow]", app).forEach(function (tr) { tr.hidden = true; });
    var flagged = {};
    reviewItems().forEach(function (x) { flagged[String(x.item.at)] = true; });
    var rank = { "is-error": 3, "is-flag": 2, "is-warning": 1 };
    S.result.problems.forEach(function (prob) {
      var isFlag = prob.level === "warning" && /^to review: /.test(prob.message) && flagged[prob.at];
      var cls = prob.level === "error" ? "is-error" : isFlag ? "is-flag" : "is-warning";
      var box = boxFor(prob.at);
      var id = "enter-msg-" + (++tipId);
      var text = isFlag ? prob.message.replace(/^to review: /, "To check: ") : prob.message;
      var current = ["is-error", "is-flag", "is-warning"].filter(function (c) { return box.classList.contains(c); })[0];
      if (!current || rank[cls] > rank[current]) {
        if (current) box.classList.remove(current);
        box.classList.add(cls);
      }
      box.setAttribute("data-tip", (box.getAttribute("data-tip") ? box.getAttribute("data-tip") + " · " : "") + text);
      var inner = box.matches("input, select, button") ? box : box.querySelector("input, select, button");
      if (inner) {
        if (prob.level === "error") inner.setAttribute("aria-invalid", "true");
        inner.setAttribute("aria-describedby", ((inner.getAttribute("aria-describedby") || "") + " " + id).trim());
      }
      var ul = msgsFor(prob.at);
      if (ul) {
        ul.appendChild(el("li", { class: "sheet-msg sheet-msg--" + cls.slice(3), id: id },
          el("span", { class: "sheet-msg__kind", text: cls === "is-error" ? "Error" : isFlag ? "Check" : "Warning" }),
          el("span", { class: "sheet-msg__text" }, el("b", { text: label(prob.at) + ": " }), text)));
        var row = ul.closest("[data-msgrow]");
        if (row) row.hidden = false;
      }
    });
  }

  function paintLines() {
    $all(".rs__cell.is-line", app).forEach(function (c) { c.classList.remove("is-line"); });
    sides().forEach(function (tid) {
      var lines = isDict(S.sheet.lines) && Array.isArray(S.sheet.lines[tid]) ? S.sheet.lines[tid] : [];
      lines.forEach(function (x) {
        var cell = $('[data-sheet] [data-at="running.' + tid + "." + x + '"]');
        if (cell) cell.classList.add("is-line");
      });
    });
  }

  function goTo(at) {
    var box = boxFor(at);
    var target = box.matches("input, select, button") ? box : box.querySelector("input:not([disabled]), select, button:not([disabled])") || box;
    if (!target.hasAttribute("tabindex") && !target.matches("input, select, button")) target.setAttribute("tabindex", "-1");
    target.scrollIntoView({ block: "center", behavior: "smooth" });
    target.focus({ preventScroll: true });
  }

  function renderChecks() {
    var probs = S.result.problems;
    var flags = reviewItems();
    var flaggedAt = {};
    flags.forEach(function (x) { flaggedAt[String(x.item.at)] = true; });
    var errors = probs.filter(function (p) { return p.level === "error"; });
    var warnings = probs.filter(function (p) { return p.level === "warning" && !(/^to review: /.test(p.message) && flaggedAt[p.at]); });
    var sum = $("[data-checks-sum]");
    sum.textContent = "";
    [[errors.length, "error", "errors", "error"], [flags.length, "flag to check", "flags to check", "flag"], [warnings.length, "warning", "warnings", "warning"]]
      .forEach(function (x) {
        sum.appendChild(el("span", { class: "enter-count enter-count--" + x[3] + (x[0] ? "" : " is-zero") }, el("b", { text: String(x[0]) }), " " + (x[0] === 1 ? x[1] : x[2])));
      });

    var box = $("[data-checks]");
    var pts = $(".enter-points");
    if (pts) S.pointsOpen = pts.open;
    box.textContent = "";
    function issue(p, cls) {
      return el("button", { class: "enter-issue enter-issue--" + cls, type: "button", onclick: function () { goTo(p.at); } },
        el("span", { class: "enter-issue__at", text: label(p.at) }),
        el("span", { class: "enter-issue__msg", text: p.message }));
    }
    if (errors.length) {
      box.appendChild(el("h3", { class: "enter-checks__title enter-checks__title--error", text: "Errors" }));
      box.appendChild(el("ul", { class: "enter-issues" }, errors.map(function (p) { return el("li", { class: "enter-issues__item" }, issue(p, "error")); })));
    }
    if (flags.length) {
      box.appendChild(el("h3", { class: "enter-checks__title enter-checks__title--flag", text: "To check against the paper" }));
      box.appendChild(el("ul", { class: "enter-issues" }, flags.map(function (x) {
        var at = String(x.item.at);
        return el("li", { class: "enter-issues__item" },
          issue({ at: at, message: String(x.item.note === undefined || x.item.note === null ? "" : x.item.note) }, "flag"),
          el("button", { class: "btn btn--quiet enter-issues__done", type: "button", text: "Mark as checked", "aria-label": "Mark " + label(at) + " as checked",
            onclick: function () {
              S.sheet.review.splice(x.n, 1);
              if (!S.sheet.review.length) delete S.sheet.review;
              changed();
              var next = $(".enter-issues__done");
              (next || $("[data-checks-sum]")).focus && (next || $("#enter-checks-title")).focus();
            } }));
      })));
    }
    if (warnings.length) {
      box.appendChild(el("h3", { class: "enter-checks__title enter-checks__title--warning", text: "Warnings" }));
      box.appendChild(el("ul", { class: "enter-issues" }, warnings.map(function (p) { return el("li", { class: "enter-issues__item" }, issue(p, "warning")); })));
    }
    if (!errors.length && !flags.length && !warnings.length) {
      box.appendChild(el("p", { class: "enter-ok", text: "Everything checks out." }));
    }
    box.appendChild(renderPoints());
  }

  // Points, FTM and FTA per player, worked out as you type (even with errors)
  function renderPoints() {
    var openNow = S.pointsOpen !== undefined ? S.pointsOpen : window.matchMedia("(min-width: 1100px)").matches;
    var wrap = el("details", { class: "enter-points", open: openNow },
      el("summary", null, el("h3", { class: "enter-checks__title", text: "Points from the sheet" })));
    sides().forEach(function (tid) {
      var t = team(tid);
      var rows = rowsOf(tid);
      var body = el("tbody");
      var sum = { pts: 0, ftm: 0, fta: 0 };
      rows.forEach(function (row, i) {
        if (!isDict(row)) return;
        var tally = S.result.tally[tid + "." + i] || { pts: 0 };
        var ft = typeof row.ft === "string" && /^[MX]*$/.test(row.ft) ? row.ft : "";
        var ftm = (ft.match(/M/g) || []).length;
        if (row.here !== true && !tally.pts) return;
        sum.pts += tally.pts; sum.ftm += ftm; sum.fta += ft.length;
        var who = row.player !== undefined && row.player !== null ? (S.season.players[row.player] || {}).display || String(row.player) : (row.name || "—");
        body.appendChild(el("tr", null,
          el("th", { scope: "row" }, el("span", { class: "player-num", text: row.num === undefined || row.num === null ? "" : "#" + row.num }), " ", who),
          el("td", { text: String(tally.pts) }), el("td", { text: String(ftm) }), el("td", { text: String(ft.length) })));
      });
      var r = isDict(S.sheet.running) && isDict(S.sheet.running[tid]) ? S.sheet.running[tid] : {};
      var last = Object.keys(r).map(Number).filter(function (n) { return Number.isInteger(n); }).sort(function (a, b) { return b - a; })[0] || 0;
      var fin = isDict(S.sheet.boxes) && isDict(S.sheet.boxes[tid]) ? S.sheet.boxes[tid].final : null;
      wrap.appendChild(el("div", { class: "table-card enter-points__card" }, el("table", { class: "table enter-points__table" },
        el("caption", { class: "enter-points__cap" }, el("span", { class: "chip chip--" + (t.slot || 1), "aria-hidden": "true" }), " " + t.name),
        el("thead", null, el("tr", null, el("th", { scope: "col", text: "Player" }), el("th", { scope: "col", text: "Pts" }),
          el("th", { scope: "col", text: "FTM" }), el("th", { scope: "col", text: "FTA" }))),
        body,
        el("tfoot", null, el("tr", null, el("th", { scope: "row", text: "Team" }), el("td", { text: String(sum.pts) }),
          el("td", { text: String(sum.ftm) }), el("td", { text: String(sum.fta) }))))));
      wrap.appendChild(el("p", { class: "enter-hint enter-points__note",
        text: "Running score ends at " + last + " · Final box " + (fin === null || fin === undefined ? "empty" : fin) }));
    });
    return wrap;
  }

  // ------------------------------------------------------------ saving
  function renderSave() {
    var flags = reviewItems().length;
    var errs = S.finalProblems.filter(function (p) { return p.at !== "checked_by" && p.at !== "review" && p.at !== "status"; }).length;
    var who = (S.sheet.checked_by || "").trim();
    var btn = $("[data-save-final]");
    var reason = $("[data-save-reason]");
    var need = [];
    if (errs) need.push("fix " + errs + " error" + (errs === 1 ? "" : "s"));
    if (flags) need.push("check " + flags + " flag" + (flags === 1 ? "" : "s"));
    if (!who) need.push("say who checked it");
    btn.disabled = need.length > 0;
    reason.textContent = need.length ? "To save as final: " + need.join(", ") + ". " +
      (errs && S.result.problems.filter(function (p) { return p.level === "error"; }).length < errs ? "(A final file also needs every row matched to a player and the quarter lines.) " : "") +
      "A draft can be saved any time."
      : "Ready: it will be saved with status: final and the review list removed.";
  }

  function saveDialog(kind) {
    var sheet = S.sheet;
    var gid = String(sheet.game_id);
    var out;
    if (kind === "final") {
      out = finalSheet(sheet, (sheet.checked_by || "").trim());
    } else {
      out = {};
      Object.keys(sheet).forEach(function (k) { out[k] = sheet[k]; });
      out.status = "draft";
    }
    var text = SR.dump(out);
    var folder = kind === "final" ? "games" : "drafts";
    var path = seasonPath(folder, gid);
    var repo = S.season.repo, branch = S.season.branch || "main";
    var exists = !!S.files[folder][gid];
    var draftToo = kind === "final" && !!S.files.drafts[gid];
    var gh = "https://github.com/" + repo;

    $("[data-dialog-title]").textContent = kind === "final" ? "Save the final game file" : "Save as a draft";
    $("[data-dialog-path]").textContent = path;
    $("[data-dialog-yaml]").textContent = text;
    $("[data-dialog-note]").textContent = "";
    var steps = $("[data-dialog-steps]");
    var buttons = $("[data-dialog-buttons]");
    steps.textContent = "";
    buttons.textContent = "";

    function note(t) { $("[data-dialog-note]").textContent = t; }
    function copy() {
      return (navigator.clipboard && navigator.clipboard.writeText ? navigator.clipboard.writeText(text) : Promise.reject())
        .catch(function () {
          var ta = el("textarea", { class: "visually-hidden" });
          ta.value = text;
          document.body.appendChild(ta);
          ta.select();
          var ok = document.execCommand && document.execCommand("copy");
          ta.remove();
          if (!ok) throw new Error("copy");
        }).then(function () { note("Copied the file (" + text.length + " characters)."); }, function () { note("Couldn't copy: use Download, or Show the file below."); });
    }
    function download() {
      var a = el("a", { href: URL.createObjectURL(new Blob([text], { type: "text/yaml" })), download: gid + ".yml" });
      document.body.appendChild(a);
      a.click();
      setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
      note("Downloaded " + gid + ".yml.");
    }
    buttons.appendChild(el("button", { class: "btn btn--quiet", type: "button", text: "Download .yml", onclick: download }));
    buttons.appendChild(el("button", { class: "btn btn--quiet", type: "button", text: "Copy", onclick: copy }));
    function li(nodes) { steps.appendChild(el("li", null, nodes)); }
    function link(href, t) { return el("a", { href: href, target: "_blank", rel: "noopener", text: t }); }

    if (!repo) {
      li(["Put the file at ", el("code", { text: path }), " in the website's repository."]);
    } else if (exists) {
      // GitHub can't fill in an edit from a link: copy, open the editor, paste
      li(["Press ", el("b", { text: "Copy" }), " below."]);
      li(["Open ", link(gh + "/edit/" + branch + "/" + path, "the file in GitHub's editor"), " (sign in if asked)."]);
      li("Select everything in the editor (Ctrl+A, or Cmd+A on a Mac) and paste over it.");
      li(["Press ", el("b", { text: "Commit changes" }), ", say what you changed, choose ", el("b", { text: "Create a new branch and start a pull request" }),
        ", and merge it when the check is green."]);
    } else {
      var url = SR.githubNewFileUrl(repo, branch, path, text);
      var fits = url.length <= SR.MAX_URL;
      if (fits) {
        buttons.insertBefore(el("a", { class: "btn", href: url, target: "_blank", rel: "noopener", text: "Save to GitHub" }), buttons.firstChild);
        li(["Press ", el("b", { text: "Save to GitHub" }), ": GitHub opens a new file with the name and contents filled in (sign in if asked)."]);
      } else {
        var empty = SR.githubNewFileUrl(repo, branch, path, "");
        buttons.insertBefore(el("a", { class: "btn", href: empty, target: "_blank", rel: "noopener", text: "Copy and open GitHub",
          onclick: function () { copy(); } }), buttons.firstChild);
        li(["Press ", el("b", { text: "Copy and open GitHub" }), ": the file is too long to send in a link, so it's copied instead and GitHub opens an empty new file with the name filled in."]);
        li("Paste the file into the editor.");
      }
      li(["Press ", el("b", { text: "Commit changes" }), ", choose ", el("b", { text: "Create a new branch and start a pull request" }),
        ", and merge it when the check is green."]);
    }
    if (draftToo && repo) {
      li(["Then delete the draft: open ", link(gh + "/delete/" + branch + "/" + seasonPath("drafts", gid), "the draft's delete page"),
        " and commit it the same way. (The build ignores drafts, so the game shows either way.)"]);
    }
    if (kind === "final") li("Once it's merged, the site rebuilds itself in a few minutes; the game, standings and stats update then.");
    else li("A draft isn't shown on the site. Open it here again to finish checking it.");
    if (S.season.sample) li("This is the sample season (made-up data), so the file goes in its folder.");
    $("[data-dialog]").showModal();
  }

  // ------------------------------------------------------------ the photo
  function setUpPhoto() {
    var panel = $("[data-photo]");
    var view = $("[data-photo-view]");
    var img = el("img", { alt: "", "data-photo-img": true });   // given a src only when a photo is opened
    view.appendChild(img);
    var st = { s: 1, x: 0, y: 0, r: 0 };
    var url = null;
    function apply() {
      // turn about the photo's middle, then scale and move it
      var w = img.naturalWidth / 2, h = img.naturalHeight / 2;
      img.style.transform = "translate(" + st.x + "px," + st.y + "px) scale(" + st.s + ") translate(" + w + "px," + h + "px) rotate(" + st.r + "deg) translate(" + -w + "px," + -h + "px)";
    }
    function fit() {
      var w = view.clientWidth, h = view.clientHeight;
      var turned = st.r % 180 !== 0;
      var iw = turned ? img.naturalHeight : img.naturalWidth, ih = turned ? img.naturalWidth : img.naturalHeight;
      if (!iw || !ih) return;
      st.s = Math.min(w / iw, h / ih);
      st.x = (w - img.naturalWidth * st.s) / 2;
      st.y = (h - img.naturalHeight * st.s) / 2;
      apply();
    }
    function zoom(f, cx, cy) {
      if (cx === undefined) { cx = view.clientWidth / 2; cy = view.clientHeight / 2; }
      var s = Math.max(0.05, Math.min(8, st.s * f));
      st.x = cx - (cx - st.x) * (s / st.s);
      st.y = cy - (cy - st.y) * (s / st.s);
      st.s = s;
      apply();
    }
    $("[data-photo-file]").addEventListener("change", function (e) {
      var file = e.target.files[0];
      e.target.value = "";
      if (!file) return;
      if (url) URL.revokeObjectURL(url);
      url = URL.createObjectURL(file);           // a local link to the file: nothing is uploaded
      img.onload = function () { st.r = 0; fit(); };
      img.src = url;
      img.alt = "";
      panel.hidden = false;
      document.body.classList.add("enter-has-photo");
      view.focus();
    });
    $("[data-photo-close]").addEventListener("click", function () {
      panel.hidden = true;
      document.body.classList.remove("enter-has-photo");
      img.removeAttribute("src");
      if (url) URL.revokeObjectURL(url);
      url = null;
    });
    $all("[data-zoom]", panel).forEach(function (b) {
      b.addEventListener("click", function () { zoom(b.getAttribute("data-zoom") === "1" ? 1.25 : 0.8); });
    });
    $("[data-zoom-fit]").addEventListener("click", fit);
    $("[data-rotate]").addEventListener("click", function () {
      st.r = (st.r + 90) % 360;
      fit();
    });
    view.addEventListener("wheel", function (e) {
      e.preventDefault();
      var box = view.getBoundingClientRect();
      zoom(e.deltaY < 0 ? 1.1 : 0.9, e.clientX - box.left, e.clientY - box.top);
    }, { passive: false });
    var pointers = {};
    var pinch = null;
    view.addEventListener("pointerdown", function (e) {
      view.setPointerCapture(e.pointerId);
      pointers[e.pointerId] = { x: e.clientX, y: e.clientY };
    });
    view.addEventListener("pointermove", function (e) {
      var p = pointers[e.pointerId];
      if (!p) return;
      var ids = Object.keys(pointers);
      if (ids.length === 2) {
        var a = pointers[ids[0]], b = pointers[ids[1]];
        p.x = e.clientX; p.y = e.clientY;
        var d = Math.hypot(a.x - b.x, a.y - b.y);
        var box = view.getBoundingClientRect();
        if (pinch) zoom(d / pinch, (a.x + b.x) / 2 - box.left, (a.y + b.y) / 2 - box.top);
        pinch = d;
        return;
      }
      st.x += e.clientX - p.x;
      st.y += e.clientY - p.y;
      p.x = e.clientX; p.y = e.clientY;
      apply();
    });
    function up(e) { delete pointers[e.pointerId]; pinch = null; }
    view.addEventListener("pointerup", up);
    view.addEventListener("pointercancel", up);
    view.addEventListener("keydown", function (e) {
      var step = 40;
      var moves = { ArrowLeft: [step, 0], ArrowRight: [-step, 0], ArrowUp: [0, step], ArrowDown: [0, -step] };
      if (moves[e.key]) { st.x += moves[e.key][0]; st.y += moves[e.key][1]; apply(); }
      else if (e.key === "+" || e.key === "=") zoom(1.25);
      else if (e.key === "-" || e.key === "_") zoom(0.8);
      else if (e.key === "0") fit();
      else return;
      e.preventDefault();
    });
    window.addEventListener("resize", function () { if (!panel.hidden && img.naturalWidth) fit(); });
  }

  init();
})();
