/* The league's paper score sheet (form MBL-PS1, and the older bilingual sheet
   it copies) as a game file, and back. Used by the paper sheet entry page
   (/enter/paper/) and by /enter/ to open a file typed from that sheet.

   The paper sheet has no running score: each player's points per period
   (P1-P4, and OT), the free throws they made and tried, their fouls, and the
   team's total at the end of each period. A game file (form MBL-SS6) needs a
   running score, so toGame() generates one: period by period, players in
   roster order, each player's points as baskets of 2 (one 3 if the total is
   odd, a 1 for a single point; 2s split into 1s where the player made more
   free throws than that gives baskets). Points per player per period, the
   period totals and the free throws come out exactly as typed; only the order
   of scoring within a period is made up, and the site never shows it. The file
   says so with `source: MBL-PS1`. fromGame() reads the points per period back
   from any game file (the running score and its quarter lines).

   The paper model (also what the older-sheet prompt writes, form MBL-PS1):
     teams.<team>.players: [{player | name, num, here, pts: [p1, p2, p3, p4, ot],
                             ftm, fta, fouls, tech}]
   with the game's boxes, notes, review and checked_by as in a game file.

     const PE = PaperEntry.make(spec);       // spec: scripts/scoresheet/spec.json
     const { sheet, problems, runMap } = PE.toGame(meta, paper);
     const paper = PE.fromGame(sheet);
   Works in the browser (window.PaperEntry) and in Node (require). */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.PaperEntry = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const SOURCE = "MBL-PS1";
  const PERIODS = ["P1", "P2", "P3", "P4", "OT"];
  const META = ["game_id", "form", "source", "status", "home", "away", "scorekeeper"];
  const AFTER = ["boxes", "notes", "review", "checked_by"];

  const isDict = (v) => v !== null && typeof v === "object" && !Array.isArray(v);
  const isCount = (v) => Number.isInteger(v) && v >= 0;
  const has = (v) => v !== undefined && v !== null && v !== "";

  function make(spec) {
    const quarters = spec.quarters.length;          // P1-P4; OT is the period after

    function blankRow() { return { here: false, pts: PERIODS.map(() => null) }; }

    // Is there anything on this paper row?
    function filled(r) {
      return isDict(r) && (has(r.player) || has(r.name) || has(r.num) || r.here === true ||
        (Array.isArray(r.pts) && r.pts.some((p) => has(p) && p !== 0)) || r.ftm > 0 || r.fta > 0 || r.fouls > 0 || r.tech > 0);
    }

    // One paper row from whatever was written: numbers as numbers where they are
    function cleanRow(r) {
      const out = blankRow();
      if (!isDict(r)) return out;
      for (const k of ["player", "name", "num"]) if (has(r[k])) out[k] = r[k];
      out.here = r.here === true;
      const pts = Array.isArray(r.pts) ? r.pts : [];
      out.pts = PERIODS.map((_, k) => (has(pts[k]) ? pts[k] : null));
      for (const k of ["ftm", "fta", "fouls", "tech"]) if (has(r[k]) && r[k] !== 0) out[k] = r[k];
      return out;
    }

    // A player's points in one period as running-score jumps
    function split(p) {
      if (p === 1) return [1];
      const out = [];
      if (p % 2) { out.push(3); p -= 3; }
      while (p > 0) { out.push(2); p -= 2; }
      return out;
    }

    /* The game file for a paper sheet. meta: the file's other fields (game_id,
       status, home, away, scorekeeper, boxes, notes, review, checked_by);
       paper: {team: [rows]}. Returns the sheet, the problems only the paper
       knows (paths name paper boxes: teams.<team>.players.<row>.pts.<period>),
       and runMap: {team: {total: [row, period]}} for pointing a running-score
       problem at the cell it came from. Rows are kept in order; trailing empty
       rows are left out. */
    function toGame(meta, paper) {
      const problems = [];
      const err = (at, message) => problems.push({ level: "error", at, message });
      const sheet = {};
      for (const k of META) if (k in meta && meta[k] !== undefined) sheet[k] = meta[k];
      sheet.form = spec.form;
      sheet.source = SOURCE;
      const sides = [meta.home, meta.away];
      sheet.teams = {}; sheet.running = {}; sheet.lines = {};
      const runMap = {};
      for (const tid of sides) {
        const rows = (Array.isArray(paper[tid]) ? paper[tid] : []).map(cleanRow);
        while (rows.length && !filled(rows[rows.length - 1])) rows.pop();
        sheet.teams[tid] = { players: rows.map((r, i) => {
          const base = `teams.${tid}.players.${i}`;
          const out = {};
          if (has(r.player)) out.player = r.player; else if (has(r.name)) out.name = r.name;
          if (has(r.num)) out.num = r.num;
          out.here = r.here;
          const ftm = r.ftm === undefined ? 0 : r.ftm, fta = r.fta === undefined ? 0 : r.fta;
          if (!isCount(ftm)) err(base + ".ftm", "free throws made should be a whole number");
          else if (!isCount(fta)) err(base + ".fta", "free throws tried should be a whole number");
          else if (ftm > fta) err(base + ".fta", `made ${ftm} free throws but tried only ${fta}`);
          else if (fta) out.ft = "M".repeat(ftm) + "X".repeat(fta - ftm);
          if (r.fouls !== undefined) out.fouls = r.fouls;
          if (r.tech !== undefined) out.tech = r.tech;
          return out;
        }) };

        // the running score: period by period, rows in order
        const jumps = rows.map((r, i) => r.pts.map((p, k) => {
          if (!has(p) || p === 0) return [];
          if (!isCount(p)) { err(`teams.${tid}.players.${i}.pts.${k}`, `${PERIODS[k]} points should be a whole number`); return []; }
          if (!has(r.num)) { err(`teams.${tid}.players.${i}.num`, "has points but no jersey number: the running score needs one"); return []; }
          return split(p);
        }));
        rows.forEach((r, i) => {           // enough baskets for the free throws made
          let count = jumps[i].reduce((n, js) => n + js.length, 0);
          for (let k = 0; count < (isCount(r.ftm) ? r.ftm : 0) && k < 50; k++) {
            const per = jumps[i].findIndex((js) => js.includes(2)) >= 0 ? jumps[i].findIndex((js) => js.includes(2))
              : jumps[i].findIndex((js) => js.includes(3));
            if (per < 0) break;
            const js = jumps[i][per];
            const at = js.includes(2) ? js.indexOf(2) : js.indexOf(3);
            js.splice(at, 1, ...(js[at] === 2 ? [1, 1] : [2, 1]));
            count += 1;
          }
        });
        const run = {}, map = {}, lines = [];
        let total = 0;
        for (let k = 0; k < PERIODS.length; k++) {
          rows.forEach((r, i) => {
            for (const j of jumps[i][k] || []) {
              total += j;
              run[total] = r.num;
              map[total] = [i, k];
            }
          });
          if (k < quarters) lines.push(total);
        }
        sheet.running[tid] = run;
        sheet.lines[tid] = lines;
        runMap[tid] = map;
      }
      for (const k of AFTER) if (k in meta && meta[k] !== undefined) sheet[k] = meta[k];
      if (!isDict(sheet.boxes)) sheet.boxes = {};
      for (const tid of sides) {
        if (!isDict(sheet.boxes[tid])) {
          sheet.boxes[tid] = {};
          for (const b of spec.score_boxes) sheet.boxes[tid][b.key] = null;
        }
      }
      return { sheet, problems, runMap };
    }

    /* The paper rows for a game file: each player's points per period, from
       its running score and quarter lines (or its Q boxes when there are no
       lines), and its free-throw circles as made / tried. */
    function fromGame(sheet) {
      const paper = {};
      if (!isDict(sheet) || !isDict(sheet.teams)) return paper;
      for (const tid of Object.keys(sheet.teams)) {
        const t = sheet.teams[tid];
        const rows = (isDict(t) && Array.isArray(t.players) ? t.players : []).map((r) => {
          const out = blankRow();
          if (!isDict(r)) return out;
          for (const k of ["player", "name", "num"]) if (has(r[k])) out[k] = r[k];
          out.here = r.here === true;
          if (typeof r.ft === "string" && r.ft) {
            out.ftm = (r.ft.match(/M/g) || []).length;
            out.fta = r.ft.length;
          }
          if (r.fouls) out.fouls = r.fouls;
          if (r.tech) out.tech = r.tech;
          return out;
        });
        const lines = isDict(sheet.lines) && Array.isArray(sheet.lines[tid]) ? sheet.lines[tid]
          : isDict(sheet.boxes) && isDict(sheet.boxes[tid]) ? spec.score_boxes.filter((b) => /^q\d$/.test(b.key)).map((b) => sheet.boxes[tid][b.key])
            : [];
        const run = isDict(sheet.running) && isDict(sheet.running[tid]) ? sheet.running[tid] : {};
        let prev = 0;
        for (const total of Object.keys(run).map(Number).filter(Number.isInteger).sort((a, b) => a - b)) {
          const jump = total - prev;
          prev = total;
          const i = rows.findIndex((r) => has(r.num) && String(r.num) === String(run[total]));
          if (i < 0) continue;
          let k = lines.findIndex((x) => Number.isInteger(x) && total <= x);
          if (k < 0) k = quarters;
          rows[i].pts[k] = (rows[i].pts[k] || 0) + jump;
        }
        paper[tid] = rows;
      }
      return paper;
    }

    // A file written by the older-sheet prompt (form MBL-PS1): the game file's
    // other fields, and the paper rows
    function isPaperDoc(doc) { return isDict(doc) && doc.form === SOURCE; }
    function fromPaperDoc(doc) {
      const meta = {};
      for (const k of META.concat(AFTER)) if (k in doc) meta[k] = doc[k];
      meta.form = spec.form;
      meta.source = SOURCE;
      if (!meta.status) meta.status = "draft";
      const paper = {};
      if (isDict(doc.teams)) {
        for (const tid of Object.keys(doc.teams)) {
          const t = doc.teams[tid];
          paper[tid] = (isDict(t) && Array.isArray(t.players) ? t.players : []).map(cleanRow).filter(filled);
        }
      }
      return { meta, paper };
    }

    // A path from the rules (about the game file) as the paper box it's about
    function locate(at, runMap) {
      const p = String(at).split(".");
      if (p[0] === "running" && p.length >= 3 && runMap && runMap[p[1]] && runMap[p[1]][p[2]]) {
        const [i, k] = runMap[p[1]][p[2]];
        return `teams.${p[1]}.players.${i}.pts.${k}`;
      }
      if (p[0] === "running") return p[1] ? `teams.${p[1]}` : "teams";
      if (p[0] === "lines") return p.length >= 3 ? `boxes.${p[1]}.q${+p[2] + 1}` : p[1] ? `boxes.${p[1]}` : "boxes";
      if (p[0] === "teams" && p[4] === "ft") return p.slice(0, 4).join(".") + ".fta";
      return String(at);
    }

    return { PERIODS, SOURCE, blankRow, cleanRow, filled, split, toGame, fromGame, isPaperDoc, fromPaperDoc, locate };
  }

  return { make, SOURCE, PERIODS };
});
