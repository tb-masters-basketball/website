/* Masters Basketball: Stats page behaviour.
   The page works without this script (a ranked list where each player links
   to their page, plus the full table). This adds: the PPG / Points / FT %
   switch, the team chips, rows that expand, and the sortable table view.
   All the numbers come from data-* attributes the page was built with. */
(function () {
  var app = document.querySelector("[data-stats]");
  if (!app) return;

  var PAGE = 7; // players shown in the ranked list, counting the No. 1 card
  var ftMin = app.getAttribute("data-ft-min");

  var list = app.querySelector("[data-ranked]");
  var items = Array.prototype.slice.call(list.children);
  var top = {
    card: app.querySelector("[data-top]"),
    value: app.querySelector("[data-top-value]"),
    label: app.querySelector("[data-top-label]"),
    name: app.querySelector("[data-top-name]"),
    meta: app.querySelector("[data-top-meta]")
  };
  var emptyMsg = app.querySelector("[data-empty]");
  var count = app.querySelector("[data-count]");
  var ftNote = app.querySelector("[data-ft-note]");
  var ppgNote = app.querySelector("[data-ppg-note]");
  var ftCard = app.querySelector("[data-ft-card]");
  var ftItems = Array.prototype.slice.call(app.querySelectorAll("[data-ft-list] > li"));
  var ftEmpty = app.querySelector("[data-ft-empty]");
  var tableHeading = app.querySelector("#stats-table-title");
  var tableCount = app.querySelector("[data-table-count]");
  var tbody = app.querySelector("[data-table-body]");
  var tableRows = Array.prototype.slice.call(tbody.children);
  var showTable = app.querySelector("[data-show-table]");
  var showList = app.querySelector("[data-show-list]");

  var state = { metric: "ppg", team: "all", view: "list", sort: "ppg", dir: "desc" };

  function cap(s) { return s.charAt(0).toUpperCase() + s.slice(1); }
  function number(value) {
    var n = parseInt(value, 10);
    return isNaN(n) ? Infinity : n;
  }

  /* ---- ranked list ------------------------------------------------- */

  var LABELS = { ppg: "No. 1 · points per game", pts: "No. 1 · total points", ft: "No. 1 · free throw %" };

  function line(d, metric) {
    if (metric === "pts") return d.teamName + " · " + d.ppg + " PPG · " + d.gp + " GP";
    if (metric === "ft") return d.teamName + " · " + d.ftm + "-" + d.fta + " FT · " + d.gp + " GP";
    return d.teamName + " · " + d.pts + " pts · " + d.gp + " GP";
  }

  function topLine(d, metric) {
    var ft = " · FT " + d.ftm + "-" + d.fta;
    if (metric === "pts") return d.teamName + " · " + d.gp + " GP · " + d.ppg + " PPG" + ft;
    if (metric === "ft") return d.teamName + " · " + d.ftm + "-" + d.fta + " FT · " + d.gp + " GP";
    return d.teamName + " · " + d.pts + " pts · " + d.gp + " GP" + ft;
  }

  function figure(d, metric) {
    if (metric === "pts") return d.pts;
    if (metric === "ft") return d.ft + "%";
    return d.ppg;
  }

  // Turn each row's link into a button that opens its details.
  items.forEach(function (item) {
    var link = item.querySelector(".ranked__row");
    var details = item.querySelector(".ranked__details");
    var button = document.createElement("button");
    button.type = "button";
    button.className = link.className;
    button.setAttribute("aria-expanded", "false");
    button.setAttribute("aria-controls", details.id);
    while (link.firstChild) button.appendChild(link.firstChild);
    link.parentNode.replaceChild(button, link);
    item._url = details.querySelector(".details__link").href;
    item._button = button;
    item._details = details;
    details.hidden = true;
    button.addEventListener("click", function () {
      setOpen(item, button.getAttribute("aria-expanded") !== "true");
    });
  });

  function setOpen(item, open) {
    item._button.setAttribute("aria-expanded", open ? "true" : "false");
    item._details.hidden = !open;
    item.classList.toggle("is-open", open);
  }

  function inTeam(el) {
    return state.team === "all" || el.getAttribute("data-team") === state.team;
  }

  function renderList() {
    var metric = state.metric;
    var key = cap(metric);
    var candidates = items
      .filter(function (it) {
        if (!inTeam(it)) return false;
        if (metric === "ft") return it.dataset.ft !== "";
        if (metric === "ppg") return it.dataset.orderPpg !== ""; // has enough games
        return true;
      })
      .sort(function (a, b) { return number(a.dataset["order" + key]) - number(b.dataset["order" + key]); });
    var others = items.filter(function (it) { return candidates.indexOf(it) < 0; });

    // Best first in the page itself, so reading order matches what you see.
    candidates.concat(others).forEach(function (it) { list.appendChild(it); });

    var rank = 0;
    var previous = null;
    candidates.forEach(function (it, i) {
      var tied = dataRank(it, key);
      if (tied !== previous) rank = i + 1; // equal values share a rank
      previous = tied;
      it.querySelector("[data-rank]").textContent = rank;
      it.querySelector("[data-meta]").textContent = line(it.dataset, metric);
      it.querySelector("[data-value]").textContent = figure(it.dataset, metric);
      it.hidden = i === 0 || i >= PAGE; // the first player is the No. 1 card
      setOpen(it, false);
    });
    others.forEach(function (it) { it.hidden = true; setOpen(it, false); });

    var n = candidates.length;
    if (n > 0) {
      var first = candidates[0].dataset;
      top.card.hidden = false;
      top.card.href = candidates[0]._url;
      top.value.textContent = figure(first, metric);
      top.label.textContent = LABELS[metric];
      showName(top.name, first.name, first.number);
      top.meta.textContent = topLine(first, metric);
      emptyMsg.hidden = true;
    } else {
      top.card.hidden = true;
      emptyMsg.hidden = false;
      var who = state.team === "all" ? "No one" : "No one on this team";
      emptyMsg.textContent = metric === "ppg"
        ? who + " has played enough games to be ranked yet."
        : who + " has " + ftMin + " free-throw attempts yet.";
    }
    count.textContent = "Showing " + Math.min(PAGE, n) + " of " + n + (metric === "ft" ? " with " + ftMin + "+ attempts" : "");
    ftNote.hidden = metric !== "ft";
    if (ppgNote) ppgNote.hidden = metric !== "ppg";

    // Free-throw leaders card: top three for the chosen team(s); not needed in the FT % view.
    var shown = 0;
    ftItems.forEach(function (it) {
      var show = inTeam(it) && shown < 3;
      it.hidden = !show;
      if (show) shown++;
    });
    ftEmpty.hidden = shown > 0;
    ftCard.hidden = metric === "ft";
  }

  // "#23 Dave M.", as _includes/player-name.html draws it (no number: just the name).
  function showName(el, name, number) {
    el.textContent = "";
    if (number) {
      var num = document.createElement("span");
      num.className = "player-num";
      num.textContent = "#" + number;
      el.appendChild(num);
      el.appendChild(document.createTextNode(" "));
    }
    el.appendChild(document.createTextNode(name));
  }

  function dataRank(it, key) {
    return it.dataset["rank" + key];
  }

  /* ---- table ------------------------------------------------------- */

  var headers = Array.prototype.slice.call(app.querySelectorAll("th[data-sort]"));
  headers.forEach(function (th) {
    var button = document.createElement("button");
    button.type = "button";
    button.className = "sort-btn";
    while (th.firstChild) button.appendChild(th.firstChild);
    th.appendChild(button);
    button.addEventListener("click", function () {
      var key = th.getAttribute("data-sort");
      if (state.sort === key) {
        state.dir = state.dir === "asc" ? "desc" : "asc";
      } else {
        state.sort = key;
        state.dir = key === "name" ? "asc" : "desc";
      }
      renderTable();
    });
  });

  function renderTable() {
    var key = state.sort;
    var sign = state.dir === "asc" ? 1 : -1;
    var rows = tableRows.slice().sort(function (a, b) {
      var x = a.dataset[key];
      var y = b.dataset[key];
      if (key === "name") {
        var c = x < y ? -1 : x > y ? 1 : 0;
        if (c) return c * sign;
      } else {
        var nx = parseFloat(x);
        var ny = parseFloat(y);
        var gapX = isNaN(nx);
        var gapY = isNaN(ny);
        if (gapX !== gapY) return gapX ? 1 : -1; // players without a number sort last either way
        if (!gapX && nx !== ny) return (nx - ny) * sign;
      }
      return number(a.dataset.order) - number(b.dataset.order);
    });
    var visible = 0;
    rows.forEach(function (row) {
      row.hidden = !inTeam(row);
      if (!row.hidden) visible++;
      tbody.appendChild(row);
    });
    headers.forEach(function (th) {
      if (th.getAttribute("data-sort") === key) {
        th.setAttribute("aria-sort", state.dir === "asc" ? "ascending" : "descending");
      } else {
        th.removeAttribute("aria-sort");
      }
    });
    tableCount.textContent = visible + (visible === 1 ? " player" : " players");
  }

  /* ---- controls ---------------------------------------------------- */

  function press(group, attribute, value) {
    Array.prototype.forEach.call(group.querySelectorAll("button"), function (b) {
      b.setAttribute("aria-pressed", b.getAttribute(attribute) === value ? "true" : "false");
    });
  }

  var metricGroup = app.querySelector("[data-metrics]");
  metricGroup.addEventListener("click", function (event) {
    var button = event.target.closest("button[data-metric]");
    if (!button) return;
    state.metric = button.getAttribute("data-metric");
    press(metricGroup, "data-metric", state.metric);
    renderList();
  });

  var teamGroup = app.querySelector("[data-teams]");
  teamGroup.addEventListener("click", function (event) {
    var button = event.target.closest("button[data-team]");
    if (!button) return;
    state.team = button.getAttribute("data-team");
    press(teamGroup, "data-team", state.team);
    renderList();
    renderTable();
  });

  function setView(view, moveFocus) {
    state.view = view;
    app.setAttribute("data-view", view);
    if (view === "table") {
      renderTable();
      history.replaceState(null, "", "#stats-table");
      if (moveFocus) tableHeading.focus();
    } else {
      history.replaceState(null, "", location.pathname + location.search);
      if (moveFocus) showTable.focus();
    }
  }

  showTable.addEventListener("click", function (event) {
    event.preventDefault();
    setView("table", true);
  });
  showList.addEventListener("click", function (event) {
    event.preventDefault();
    setView("list", true);
  });

  renderList();
  renderTable();
  app.classList.add("is-ready");
  if (location.hash === "#stats-table") setView("table", false);
  // A link or typed address to #stats-table on this page (replaceState above doesn't fire this).
  window.addEventListener("hashchange", function () {
    if (location.hash === "#stats-table" && state.view !== "table") setView("table", false);
  });
})();
