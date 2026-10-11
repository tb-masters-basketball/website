/* The score sheet rules, in JavaScript: a line-for-line port of
   scripts/sheet_rules.py for the entry page (/enter/). Same checks, same box
   paths, same messages; tests/js/sheet_rules.test.mjs runs both against
   tests/fixtures/sheets/ so they can't drift apart. Change the Python first,
   then this.

     const rules = SheetRules.make(spec);   // spec: scripts/scoresheet/spec.json
     const [game, problems] = rules.check(sheet, ctx);
     rules.dump(sheet)                     // compact YAML, as sheet_rules.dump

   A sheet is the game file as js-yaml reads it. One difference from Python:
   js-yaml gives mapping keys as strings, so running-score totals ("27") are
   read back as numbers here. Works in the browser (window.SheetRules) and in
   Node (require). */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.SheetRules = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const STATUSES = ["draft", "final"];
  const NOTE_KINDS = ["flagrant", "note"];
  const FT_RE = /^[MX]*$/;
  const JERSEY_RE = /^\d{1,2}$/;
  const FIELDS = ["game_id", "form", "status", "home", "away", "scorekeeper", "teams", "running", "lines",
    "boxes", "notes", "review", "checked_by"];
  const ROW_FIELDS = ["player", "name", "num", "here", "ft", "fouls", "tech"];

  // ---- Python's view of values, so messages read exactly as sheet_rules.py writes them
  const isDict = (v) => v !== null && typeof v === "object" && !Array.isArray(v) && !(v instanceof Date);
  const isInt = (v) => typeof v === "number" && Number.isInteger(v);
  const has = (obj, k) => isDict(obj) && typeof k === "string" && Object.prototype.hasOwnProperty.call(obj, k);
  const get = (obj, k, dflt) => (isDict(obj) && Object.prototype.hasOwnProperty.call(obj, k) ? obj[k] : dflt);
  const truthy = (v) => !(v === undefined || v === null || v === false || v === 0 || v === "" ||
    (Array.isArray(v) && !v.length) || (isDict(v) && !Object.keys(v).length));
  const or = (v, d) => (truthy(v) ? v : d);
  const count = (v) => isInt(v) && v >= 0;          // _count: a whole number, 0 or more

  function repr(v) {                                 // Python's repr()
    if (v === undefined || v === null) return "None";
    if (v === true) return "True";
    if (v === false) return "False";
    if (typeof v === "number") return String(v);
    if (typeof v === "string") {
      const q = v.includes("'") && !v.includes('"') ? '"' : "'";
      return q + v.replace(/\\/g, "\\\\").replace(q === "'" ? /'/g : /(?!)/g, "\\'").replace(/\n/g, "\\n") + q;
    }
    if (Array.isArray(v)) return "[" + v.map(repr).join(", ") + "]";
    if (v instanceof Date) return v.toISOString().slice(0, 10);
    return "{" + Object.keys(v).map((k) => repr(k) + ": " + repr(v[k])).join(", ") + "}";
  }
  function str(v) {                                  // Python's str(), as in an f-string
    return typeof v === "string" ? v : repr(v);
  }
  const sameSet = (keys, want) => keys.length === want.length && want.every((k) => keys.includes(k));

  function jersey(num) {
    // A jersey number as text ("4", "00"), or null if it isn't one.
    if (typeof num === "boolean") return null;
    if (isInt(num)) num = String(num);
    if (typeof num === "string" && JERSEY_RE.test(num.trim())) return num.trim();
    return null;
  }

  // A running-score key as Python's YAML reader gives it: an int when it's one.
  const totalKey = (k) => (/^-?\d+$/.test(k) ? Number(k) : k);

  function make(SPEC) {
    const FORM = SPEC.form;
    const ROSTER_ROWS = SPEC.roster_rows;
    const FT_CIRCLES = SPEC.ft_circles_per_page * 2;
    const MAX_FOULS = SPEC.personal_foul_boxes;
    const MAX_TECH = SPEC.technical_boxes;
    const MAX_TOTAL = SPEC.max_running_total;
    const QUARTER_BOXES = SPEC.score_boxes.map((b) => b.key).filter((k) => k.startsWith("q"));

    /* check(sheet, ctx) -> {game, problems, tally}
       tally: "team.row" -> {pts, scores} from the running score, worked out
       even when there are errors (the page shows it as you type). */
    function checkFull(sheet, ctx) {
      const out = [];
      const tally = {};
      const err = (at, message) => out.push({ level: "error", at, message });
      const warn = (at, message) => out.push({ level: "warning", at, message });
      const done = (game) => ({ game, problems: out, tally });

      if (!isDict(sheet)) {
        err("", "the file should be a game sheet (game_id, status, home, away, teams, running, ...)");
        return done(null);
      }
      for (const key of Object.keys(sheet).filter((k) => !FIELDS.includes(k)).sort()) {
        err(key, `'${key}' isn't part of a game sheet`);
      }

      // ---- the header ------------------------------------------------------
      const status = get(sheet, "status");
      const finalFile = ctx.folder === "games";
      if (!STATUSES.includes(status)) {
        err("status", `status should be draft or final, not ${repr(status)}`);
      } else if (finalFile && status !== "final") {
        err("status", "a file in games/ must be status: final (drafts go in drafts/)");
      } else if (!finalFile && status !== "draft") {
        err("status", "a file in drafts/ must be status: draft (finished games go in games/)");
      }
      const isFinal = status === "final";

      if (get(sheet, "form") !== FORM) {
        err("form", `form ${repr(get(sheet, "form"))} isn't ${FORM}, the sheet this format describes`);
      }

      const gid = get(sheet, "game_id");
      let row = null;
      if (gid !== ctx.stem) {
        err("game_id", `game_id ${repr(gid)} doesn't match the file name '${str(ctx.stem)}'`);
      } else {
        row = has(ctx.schedule, gid) ? ctx.schedule[gid] : null;
        if (row === null) {
          err("game_id", `game_id '${gid}' has no row in schedule.csv`);
        } else if (!row.teams_known) {
          err("game_id", `schedule.csv still lists this game as ${row.home} vs ${row.away}. ` +
            "Put the two teams' ids in its home and away cells first");
          row = null;
        } else if (row.cancelled) {
          err("game_id", `game '${gid}' is marked cancelled in schedule.csv. ` +
            "Delete this file, or clear the status if the game was played");
          row = null;
        }
      }

      const home = get(sheet, "home"), away = get(sheet, "away");
      for (const [side, tid] of [["home", home], ["away", away]]) {
        if (!has(ctx.teams, tid)) err(side, `${side} team ${repr(tid)} is not in teams.yml`);
      }
      if (row !== null && (home !== row.home || away !== row.away)) {
        err("home", `home/away ${str(home)}/${str(away)} doesn't match schedule.csv (${row.home}/${row.away})`);
      }
      if (home === away || !has(ctx.teams, home) || !has(ctx.teams, away)) return done(null);
      const sides = [home, away];

      // ---- rosters ------------------------------------------------------------
      const teams = get(sheet, "teams");
      if (!isDict(teams) || !sameSet(Object.keys(teams), sides)) {
        err("teams", `teams should list exactly ${home} and ${away}`);
        return done(null);
      }
      const rows = {};          // team -> [[index, row]] that are well formed
      const byNum = {};         // team -> jersey -> index
      const seenPlayers = {};
      for (const tid of sides) {
        const base = `teams.${tid}.players`;
        let listed = isDict(teams[tid]) ? get(or(teams[tid], {}), "players") : null;
        if (!Array.isArray(listed) || !listed.length) {
          err(base, `list ${tid}'s players, one per roster row`);
          listed = [];
        }
        if (listed.length > ROSTER_ROWS) err(base, `${tid} has ${listed.length} rows; the sheet has ${ROSTER_ROWS}`);
        rows[tid] = [];
        byNum[tid] = {};
        listed.forEach((r, i) => {
          const at = `${base}.${i}`;
          if (!isDict(r)) {
            err(at, "a row looks like {player: dave-m, num: 4, here: true, ft: MMX, fouls: 2}");
            return;
          }
          for (const key of Object.keys(r).filter((k) => !ROW_FIELDS.includes(k)).sort()) {
            err(`${at}.${key}`, `'${key}' isn't part of a roster row`);
          }
          const num = jersey(get(r, "num"));
          if (num === null) {
            err(`${at}.num`, `jersey number ${repr(get(r, "num"))} should be 0 to 99 (or "00")`);
          } else if (has(byNum[tid], num)) {
            err(`${at}.num`, `#${num} is on two ${tid} rows (rows ${byNum[tid][num] + 1} and ${i + 1}); ` +
              "the running score can't tell them apart");
          } else {
            byNum[tid][num] = i;
          }
          const pid = get(r, "player", null);
          if (pid === null) {
            const who = truthy(get(r, "name")) ? str(r.name) : `#${str(num)}`;
            const msg = `${who} isn't matched to a player id yet. Pick one from players.yml, or add them ` +
              "there (a sub: sub: true, with this team and number)";
            (isFinal ? err : warn)(`${at}.player`, msg);
          } else if (!has(ctx.players, pid)) {
            err(`${at}.player`, `player ${repr(pid)} is not in players.yml`);
          } else if (has(seenPlayers, pid)) {
            err(`${at}.player`, `${pid} is listed twice in this game (${seenPlayers[pid]})`);
          } else {
            seenPlayers[pid] = at;
          }
          if (typeof get(r, "here") !== "boolean") err(`${at}.here`, "here should be true (ticked) or false");
          let ft = get(r, "ft", "");
          if (typeof ft !== "string" || !FT_RE.test(ft)) {
            err(`${at}.ft`, `ft ${repr(ft)} should be the circles in order: M for made (filled), ` +
              "X for missed (slashed), e.g. MMXM");
            ft = "";
          } else if (ft.length > FT_CIRCLES) {
            err(`${at}.ft.${FT_CIRCLES}`, `${ft.length} free throws; the sheet has ${FT_CIRCLES} circles`);
          }
          for (const [key, most] of [["fouls", MAX_FOULS], ["tech", MAX_TECH]]) {
            const v = get(r, key, 0);
            if (!count(v) || v > most) err(`${at}.${key}`, `${key} ${repr(v)} should be a whole number from 0 to ${most}`);
          }
          rows[tid].push([i, Object.assign({}, r, { _num: num, _ft: ft })]);
        });
        if (ROSTER_ROWS && !rows[tid].some(([, rr]) => get(rr, "here") === true)) {
          err(base, `nobody on ${tid} is ticked Here`);
        }
      }

      // ---- running score ------------------------------------------------------
      const running = get(sheet, "running");
      if (!isDict(running) || !sameSet(Object.keys(running), sides)) {
        err("running", `running should list both teams' boxes: {${home}: {2: 4, ...}, ${away}: {...}}`);
        return done(null);
      }
      const pts = {}, jumps = {}, last = {}, totalsSeen = {};
      for (const tid of sides) {
        pts[tid] = {};
        jumps[tid] = {};
        let boxes = or(running[tid], {});
        if (!isDict(boxes)) {
          err(`running.${tid}`, "the running score is total: jersey number, e.g. {2: 4, 5: 10}");
          boxes = {};
        }
        let prev = 0;
        const totals = [];
        const keys = Object.keys(boxes).map((k) => [totalKey(k), k]);
        const ints = keys.filter(([t]) => isInt(t)).sort((a, b) => a[0] - b[0]);
        for (const [total, key] of ints.concat(keys.filter(([t]) => !isInt(t)))) {
          const at = `running.${tid}.${total}`;
          if (!isInt(total) || total < 1 || total > MAX_TOTAL) {
            err(at, `${repr(total)} isn't a running-score box (1 to ${MAX_TOTAL})`);
            continue;
          }
          const jump = total - prev;
          if (jump < 1 || jump > 3) err(at, `${tid} goes from ${prev} to ${total}, a jump of ${jump}; a score is 1, 2 or 3`);
          const num = jersey(boxes[key]);
          if (num === null) {
            err(at, `${repr(boxes[key])} isn't a jersey number`);
          } else if (!has(byNum[tid], num)) {
            err(at, `#${num} scored for ${tid}, but no ${tid} row has #${num}`);
          } else {
            const i = byNum[tid][num];
            const r = rows[tid].find(([j]) => j === i)[1];
            if (get(r, "here") !== true) {
              const who = truthy(get(r, "player")) ? str(r.player) : truthy(get(r, "name")) ? str(r.name) : "#" + num;
              err(at, `#${num} scored, but row ${i + 1} (${who}) isn't ticked Here`);
            }
            if (jump >= 1 && jump <= 3) {
              pts[tid][i] = (pts[tid][i] || 0) + jump;
              jumps[tid][i] = (jumps[tid][i] || 0) + 1;
            }
          }
          totals.push(total);
          prev = total;
        }
        last[tid] = prev;
        totalsSeen[tid] = new Set(totals.concat([0]));
        for (const [i] of rows[tid]) tally[`${tid}.${i}`] = { pts: pts[tid][i] || 0, scores: jumps[tid][i] || 0 };
      }

      // free throws: made circles can't outnumber the player's scores
      for (const tid of sides) {
        for (const [i, r] of rows[tid]) {
          const made = (r._ft.match(/M/g) || []).length;
          const n = jumps[tid][i] || 0;
          if (made > n) {
            warn(`teams.${tid}.players.${i}.ft`,
              `${made} free throws made, but the running score has ${n} score${n !== 1 ? "s" : ""} for #${str(r._num)}`);
          }
        }
      }

      // ---- quarter lines and score boxes ----------------------------------------
      const lines = or(get(sheet, "lines"), {});
      const boxes = get(sheet, "boxes");
      const ends = {};
      if (!isDict(boxes) || !sameSet(Object.keys(boxes), sides)) {
        err("boxes", `boxes should list both teams' score boxes: {${home}: {q1: .., q2: .., q3: .., ` +
          `q4: .., ot: null, final: ..}, ${away}: {...}}`);
        return done(null);
      }
      for (const tid of sides) {
        const b = isDict(boxes[tid]) ? boxes[tid] : {};
        let tl = isDict(lines) ? get(lines, tid, null) : null;
        if (tl === null) {
          (isFinal ? err : warn)(`lines.${tid}`, `where were ${tid}'s end-of-quarter lines drawn? ` +
            "Give the running total at each: [Q1, Q2, Q3, Q4]");
          tl = [];
        } else if (!Array.isArray(tl) || tl.length !== QUARTER_BOXES.length || !tl.every(count)) {
          err(`lines.${tid}`, `lines for ${tid} should be ${QUARTER_BOXES.length} running totals, one per quarter`);
          tl = [];
        }
        tl.forEach((x, q) => {
          if (!totalsSeen[tid].has(x)) err(`lines.${tid}.${q}`, `the Q${q + 1} line is under ${x}, but ${tid} has no box with that total`);
          if (q && x < tl[q - 1]) err(`lines.${tid}.${q}`, `the Q${q + 1} line (${x}) is above the Q${q} line (${tl[q - 1]})`);
        });
        const qs = [];
        QUARTER_BOXES.forEach((key, q) => {
          const v = get(b, key, null);
          const K = key.toUpperCase();
          if (!count(v)) {
            err(`boxes.${tid}.${key}`, `the ${K} box should hold ${tid}'s running total at the end ` +
              `of that quarter, not ${repr(v)}`);
            qs.push(null);
            return;
          }
          qs.push(v);
          if (q < tl.length && v !== tl[q]) err(`boxes.${tid}.${key}`, `the ${K} box says ${v}, but the Q${q + 1} line is under ${tl[q]}`);
          if (q && qs[q - 1] !== null && v < qs[q - 1]) {
            err(`boxes.${tid}.${key}`, `the ${K} box (${v}) is less than ${QUARTER_BOXES[q - 1].toUpperCase()} (${qs[q - 1]})`);
          }
        });
        const final = get(b, "final", null);
        if (!count(final)) err(`boxes.${tid}.final`, `the Final box should hold ${tid}'s final score, not ${repr(final)}`);
        else if (final !== last[tid]) err(`boxes.${tid}.final`, `the Final box says ${final}, but the running score ends at ${last[tid]}`);
        // From here on the running score is the final: a wrong Final box is one problem, not several
        ends[tid] = { q: qs, ot: get(b, "ot", null), final: last[tid] };
      }

      if (sides.some((tid) => ends[tid].q.some((v) => v === null))) return done(null);
      const q4 = {}, final = {};
      for (const tid of sides) {
        q4[tid] = ends[tid].q[ends[tid].q.length - 1];
        final[tid] = ends[tid].final;
      }
      const wentOt = sides.some((t) => q4[t] !== final[t]);
      for (const tid of sides) {
        if (q4[tid] > final[tid]) err(`boxes.${tid}.q4`, `the Q4 box (${q4[tid]}) is more than the Final box (${final[tid]})`);
        const ot = ends[tid].ot;
        if (wentOt) {
          if (ot !== final[tid]) err(`boxes.${tid}.ot`, `after overtime the OT box should hold ${tid}'s total, ${final[tid]}`);
        } else if (ot !== null) {
          err(`boxes.${tid}.ot`, "the OT box is filled in, but Q4 already equals the final score");
        }
      }
      if (wentOt && q4[home] !== q4[away]) {
        err(`boxes.${home}.q4`, `Q4 (${home} ${q4[home]}, ${away} ${q4[away]}) isn't tied, so there was no ` +
          "overtime: Q4 should equal the final score");
      }
      if (final[home] === final[away]) err(`boxes.${home}.final`, `the final score is tied ${final[home]}-${final[away]}`);

      // ---- notes: flagrant fouls ------------------------------------------------
      const flagrants = {};
      for (const tid of sides) flagrants[tid] = {};
      let notes = or(get(sheet, "notes"), []);
      if (!Array.isArray(notes)) {
        err("notes", "notes should be a list, e.g. - {team: lh, num: 11, q: 3, kind: flagrant, text: ...}");
        notes = [];
      }
      notes.forEach((note, n) => {
        const at = `notes.${n}`;
        if (!isDict(note)) {
          err(at, "a note looks like {team: lh, num: 11, q: 3, kind: flagrant, text: ...}");
          return;
        }
        const kind = get(note, "kind", "note");
        if (!NOTE_KINDS.includes(kind)) err(`${at}.kind`, `kind should be flagrant or note, not ${repr(kind)}`);
        if (kind !== "flagrant") return;
        const tid = get(note, "team"), num = jersey(get(note, "num"));
        if (!sides.includes(tid)) {
          err(`${at}.team`, `team ${repr(tid)} isn't playing in this game`);
        } else if (!has(byNum[tid], num)) {
          err(`${at}.num`, `no ${tid} row has #${str(get(note, "num"))}`);
        } else {
          const i = byNum[tid][num];
          flagrants[tid][i] = (flagrants[tid][i] || 0) + 1;
        }
        if (![1, 2, 3, 4, "OT"].includes(get(note, "q"))) {
          err(`${at}.q`, `q should be the quarter, 1 to 4 (or OT), not ${repr(get(note, "q"))}`);
        }
      });
      for (const tid of sides) {
        for (const [i, r] of rows[tid]) {
          const f = flagrants[tid][i] || 0;
          const fouls = get(r, "fouls", 0);
          if (f && count(fouls) && f > fouls) {
            err(`teams.${tid}.players.${i}.fouls`, `${f} flagrant foul${f > 1 ? "s" : ""} in Notes, but only ` +
              `${fouls} foul box${fouls !== 1 ? "es" : ""} slashed; a flagrant is also a personal foul`);
          }
        }
      }

      // ---- review and sign-off --------------------------------------------------
      const review = or(get(sheet, "review"), []);
      if (truthy(review) && isFinal) {
        err("review", "a final sheet can't have review notes left; settle them, then remove the list");
      }
      for (const item of Array.isArray(review) ? review : []) {
        if (isDict(item)) warn(str(get(item, "at", "review")), `to review: ${str(get(item, "note", ""))}`);
      }
      if (isFinal && !truthy(get(sheet, "checked_by"))) {
        err("checked_by", "a final sheet needs checked_by: who checked it against the paper (\"First L.\")");
      }

      if (out.some((p) => p.level === "error")) return done(null);

      // ---- the game ---------------------------------------------------------------
      const gameLines = [];
      for (const tid of sides) {
        for (const [i, r] of rows[tid]) {
          if (get(r, "here") !== true || !truthy(get(r, "player"))) continue;
          const ft = r._ft;
          gameLines.push({
            player: r.player, team: tid, num: r._num,
            pts: pts[tid][i] || 0, ftm: (ft.match(/M/g) || []).length, fta: ft.length,
            pf: get(r, "fouls", 0), tech: get(r, "tech", 0), flagrant: flagrants[tid][i] || 0,
          });
        }
      }
      const quarters = {};
      for (const tid of sides) quarters[tid] = ends[tid].q.slice();
      return done({
        game_id: gid,
        date: row ? row.date : null,
        type: row ? row.type : null,
        home, away, final, quarters,
        ot: wentOt,
        lines: gameLines,
        scorekeeper: get(sheet, "scorekeeper", null),
        checked_by: get(sheet, "checked_by", null),
      });
    }

    function check(sheet, ctx) {
      const r = checkFull(sheet, ctx);
      return [r.game, r.problems];
    }

    return { FORM, ROSTER_ROWS, FT_CIRCLES, MAX_FOULS, MAX_TECH, MAX_TOTAL, QUARTER_BOXES, check, checkFull, dump };
  }

  // ---- dump: the sheet as compact YAML, in the documented key order (sheet_rules.dump)
  function scalar(v) {
    if (v === null || v === undefined) return "null";
    if (typeof v === "boolean") return v ? "true" : "false";
    if (isInt(v)) return String(v);
    const s = String(v);
    if (/^[A-Za-z][\p{L}\p{N}_ .'-]*$/u.test(s) && !["null", "true", "false", "yes", "no", "on", "off"].includes(s)) return s;
    return JSON.stringify(s);
  }
  const flow = (d) => "{" + Object.keys(d).map((k) => `${k}: ${scalar(d[k])}`).join(", ") + "}";

  function dump(sheet) {
    const out = [];
    for (const key of ["game_id", "form", "status", "home", "away", "scorekeeper"]) {
      if (key in sheet) out.push(`${key}: ${scalar(sheet[key])}`);
    }
    out.push("teams:");
    for (const tid of Object.keys(sheet.teams)) {
      out.push(`  ${tid}:`, "    players:");
      for (const r of sheet.teams[tid].players) out.push(`      - ${flow(r)}`);
    }
    for (const key of ["running", "lines", "boxes"]) {
      if (!(key in sheet)) continue;
      out.push(`${key}:`);
      for (const tid of Object.keys(sheet[key])) {
        const v = sheet[key][tid];
        out.push(Array.isArray(v) ? `  ${tid}: [${v.join(", ")}]` : `  ${tid}: ${flow(v)}`);
      }
    }
    for (const key of ["notes", "review"]) {
      if (truthy(sheet[key])) {
        out.push(`${key}:`);
        for (const n of sheet[key]) out.push(`  - ${flow(n)}`);
      }
    }
    if ("checked_by" in sheet) out.push(`checked_by: ${scalar(sheet.checked_by)}`);
    return out.join("\n") + "\n";
  }

  /* GitHub's "new file" page, with the file's name and contents filled in.
     Too long a link fails, so the page checks it against MAX_URL first and
     falls back to Copy + an empty editor. */
  const MAX_URL = 8000;
  function githubNewFileUrl(repo, branch, filePath, text) {
    const slash = filePath.lastIndexOf("/");
    const dir = filePath.slice(0, slash).split("/").map(encodeURIComponent).join("/");
    return `https://github.com/${repo}/new/${encodeURIComponent(branch)}/${dir}` +
      `?filename=${encodeURIComponent(filePath.slice(slash + 1))}&value=${encodeURIComponent(text)}`;
  }

  return { make, jersey, dump, repr, githubNewFileUrl, MAX_URL };
});
