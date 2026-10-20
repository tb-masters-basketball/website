// The paper sheet converter (assets/js/paper-entry.js): a paper sheet (points
// per period, free throws made and tried) becomes a game file the rules accept,
// with every player's points, the quarters and the free throws as typed, and a
// game file reads back as the same paper sheet.
// Run: node --test tests/js
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import path from "node:path";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const yaml = require(path.join(ROOT, "assets/js/lib/js-yaml.min.js"));
const SheetRules = require(path.join(ROOT, "assets/js/sheet-rules.js"));
const PaperEntry = require(path.join(ROOT, "assets/js/paper-entry.js"));
const SPEC = JSON.parse(readFileSync(path.join(ROOT, "scripts/scoresheet/spec.json"), "utf8"));
const rules = SheetRules.make(SPEC);
const PE = PaperEntry.make(SPEC);

// A season folder as the rules read it (teams, players, schedule)
function season(dir) {
  const teams = Object.fromEntries(yaml.load(readFileSync(path.join(dir, "teams.yml"), "utf8")).map((t) => [t.id, t]));
  const players = Object.fromEntries(yaml.load(readFileSync(path.join(dir, "players.yml"), "utf8")).map((p) => [p.id, p]));
  const [head, ...lines] = readFileSync(path.join(dir, "schedule.csv"), "utf8").trim().split("\n");
  const cols = head.split(",");
  const schedule = {};
  for (const line of lines) {
    if (!line.trim() || line.startsWith("#")) continue;
    const r = Object.fromEntries(line.split(",").map((v, i) => [cols[i], v]));
    schedule[r.game_id] = { ...r, teams_known: r.home in teams && r.away in teams, cancelled: r.status === "cancelled" };
  }
  return { teams, players, schedule };
}
const FIXTURE = season(path.join(ROOT, "tests/fixtures/sheets/season"));

function check(sheet, ctx, folder = "drafts") {
  return rules.check(sheet, { ...ctx, stem: sheet.game_id, folder });
}
const byPlayer = (game) => Object.fromEntries(game.lines.map((l) => [l.player, [l.pts, l.ftm, l.fta]]));

const META = { game_id: "2026-10-17-g1", status: "draft", home: "aa", away: "bb" };
function row(player, num, pts, extra = {}) { return { player, num, here: true, pts, ...extra }; }

test("splits points into running-score jumps of 1, 2 or 3", () => {
  assert.deepEqual(PE.split(1), [1]);
  assert.deepEqual(PE.split(2), [2]);
  assert.deepEqual(PE.split(3), [3]);
  assert.deepEqual(PE.split(7), [3, 2, 2]);
  assert.deepEqual(PE.split(8), [2, 2, 2, 2]);
});

test("a paper sheet becomes a game file with the points, quarters and free throws as typed", () => {
  const paper = {
    aa: [row("al-a", 4, [2, 0, 3, 4], { ftm: 1, fta: 2, fouls: 2 }), row("amy-b", 10, [3, 2, null, 0]), row("ann-c", 22, [0, 5, 2, 1], { ftm: 1, fta: 1 })],
    bb: [row("bo-c", 5, [4, 2, 2, 0], { tech: 1, fouls: 3 }), row("bev-d", 11, [1, 2, 3, 4], { ftm: 1, fta: 2 }), row("bud-e", 30, [0, 0, 2, 4])],
  };
  const boxes = { aa: { q1: 5, q2: 12, q3: 17, q4: 22, ot: null, final: 22 }, bb: { q1: 5, q2: 9, q3: 16, q4: 24, ot: null, final: 24 } };
  const { sheet, problems } = PE.toGame({ ...META, boxes }, paper);
  assert.deepEqual(problems, []);
  assert.equal(sheet.source, "MBL-PS1");
  assert.deepEqual(sheet.lines, { aa: [5, 12, 17, 22], bb: [5, 9, 16, 24] });
  const [game, probs] = check(sheet, FIXTURE);
  assert.deepEqual(probs.filter((p) => p.level === "error"), []);
  assert.deepEqual(byPlayer(game), {
    "al-a": [9, 1, 2], "amy-b": [5, 0, 0], "ann-c": [8, 1, 1],
    "bo-c": [8, 0, 0], "bev-d": [10, 1, 2], "bud-e": [6, 0, 0],
  });
  assert.deepEqual(game.quarters, { aa: [5, 12, 17, 22], bb: [5, 9, 16, 24] });
  // and back: the same points per period
  const back = PE.fromGame(sheet);
  assert.deepEqual(back.aa.map((r) => r.pts), [[2, null, 3, 4, null], [3, 2, null, null, null], [null, 5, 2, 1, null]]);
  assert.deepEqual([back.aa[0].ftm, back.aa[0].fta, back.bb[0].tech], [1, 2, 1]);
});

test("a player with more free throws made than baskets gets 1-point jumps, not a warning", () => {
  const paper = { aa: [row("al-a", 4, [4, 0, 0, 0], { ftm: 3, fta: 3 })], bb: [row("bo-c", 5, [2, 0, 0, 0])] };
  const boxes = { aa: { q1: 4, q2: 4, q3: 4, q4: 4, ot: null, final: 4 }, bb: { q1: 2, q2: 2, q3: 2, q4: 2, ot: null, final: 2 } };
  const { sheet } = PE.toGame({ ...META, boxes }, paper);
  assert.deepEqual(Object.keys(sheet.running.aa).map(Number), [1, 2, 4]);
  const [, probs] = check(sheet, FIXTURE);
  assert.deepEqual(probs.filter((p) => /free throws made/.test(p.message)), []);
});

test("overtime points come after the Q4 line", () => {
  const paper = { aa: [row("al-a", 4, [2, 2, 2, 2, 3])], bb: [row("bo-c", 5, [2, 2, 2, 2, 2])] };
  const boxes = { aa: { q1: 2, q2: 4, q3: 6, q4: 8, ot: 11, final: 11 }, bb: { q1: 2, q2: 4, q3: 6, q4: 8, ot: 10, final: 10 } };
  const { sheet } = PE.toGame({ ...META, boxes }, paper);
  assert.deepEqual(sheet.lines.aa, [2, 4, 6, 8]);
  const [game, probs] = check(sheet, FIXTURE);
  assert.deepEqual(probs.filter((p) => p.level === "error"), []);
  assert.equal(game.ot, true);
  assert.equal(PE.fromGame(sheet).aa[0].pts[4], 3);
});

test("paper problems and running-score paths point at paper boxes", () => {
  const paper = { aa: [row("al-a", 4, [2]), { player: "amy-b", here: true, pts: [3] }, row("ann-c", 22, [0], { ftm: 2, fta: 1 })], bb: [] };
  const { problems, runMap } = PE.toGame({ ...META, boxes: {} }, paper);
  assert.deepEqual(problems.map((p) => p.at), ["teams.aa.players.2.fta", "teams.aa.players.1.num"]);
  assert.equal(PE.locate("running.aa.2", runMap), "teams.aa.players.0.pts.0");
  assert.equal(PE.locate("lines.aa.1", runMap), "boxes.aa.q2");
  assert.equal(PE.locate("teams.aa.players.0.ft.3", runMap), "teams.aa.players.0.fta");
  assert.equal(PE.locate("boxes.aa.final", runMap), "boxes.aa.final");
});

test("trailing empty rows are left out; a file from the older-sheet prompt reads as paper", () => {
  const doc = yaml.load(`
game_id: 2026-10-17-g1
form: MBL-PS1
home: aa
away: bb
teams:
  aa:
    players:
      - {name: Al A., num: 4, here: true, pts: [2, 0, 3, 4], ftm: 1, fta: 2, fouls: 2}
      - {name: "", here: false, pts: [null, null, null, null]}
  bb:
    players:
      - {name: Bo C., num: 5, here: true, pts: [4, 2, 2, 0]}
boxes:
  aa: {q1: 2, q2: 2, q3: 5, q4: 9, ot: null, final: 9}
  bb: {q1: 4, q2: 6, q3: 8, q4: 8, ot: null, final: 8}
review:
  - {at: teams.aa.players.0.pts.2, note: "3 or 8?"}
`);
  assert.ok(PE.isPaperDoc(doc));
  const { meta, paper } = PE.fromPaperDoc(doc);
  assert.equal(meta.status, "draft");
  assert.equal(paper.aa.length, 1);
  const { sheet } = PE.toGame(meta, paper);
  assert.deepEqual(Object.keys(sheet), ["game_id", "form", "source", "status", "home", "away", "teams", "running", "lines", "boxes", "review"]);
  assert.equal(sheet.teams.aa.players[0].ft, "MX");
  assert.equal(sheet.review[0].at, "teams.aa.players.0.pts.2");
});

// The two Oct 17, 2026 games, typed from the older sheet: read back as paper
// and written out again, every player's points, quarters and free throws match.
const REAL = path.join(ROOT, "data/2026-27");
const REAL_SEASON = season(REAL);
for (const name of readdirSync(path.join(REAL, "games")).filter((f) => f.startsWith("2026-10-17"))) {
  test(`${name}: paper and back gives the same game`, () => {
    const orig = yaml.load(readFileSync(path.join(REAL, "games", name), "utf8"));
    const [g0] = check(orig, REAL_SEASON, "games");
    assert.ok(g0, "the original checks clean");
    const meta = {};
    for (const k of Object.keys(orig)) if (!["teams", "running", "lines"].includes(k)) meta[k] = orig[k];
    const { sheet, problems } = PE.toGame(meta, PE.fromGame(orig));
    assert.deepEqual(problems, []);
    const [g1, probs] = check(sheet, REAL_SEASON, "games");
    assert.deepEqual(probs.filter((p) => p.level === "error"), []);
    assert.deepEqual(byPlayer(g1), byPlayer(g0));
    assert.deepEqual(g1.quarters, g0.quarters);
    assert.deepEqual(g1.final, g0.final);
  });
}
