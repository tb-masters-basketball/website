// The score sheet rules in JavaScript (assets/js/sheet-rules.js, used by the
// entry page) against the same fixtures as tests/test_sheet_rules.py: every
// case must give exactly the problems and game in its expected.json.
// Run: node --test tests/js
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import path from "node:path";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const yaml = require(path.join(ROOT, "assets/js/lib/js-yaml.min.js"));
const SheetRules = require(path.join(ROOT, "assets/js/sheet-rules.js"));
const SPEC = JSON.parse(readFileSync(path.join(ROOT, "scripts/scoresheet/spec.json"), "utf8"));
const rules = SheetRules.make(SPEC);

const FIXTURES = path.join(ROOT, "tests/fixtures/sheets");
const CASES = readdirSync(FIXTURES).filter((c) => existsSync(path.join(FIXTURES, c, "sheet.yml"))).sort();

// The fixture season, as build_stats.load_* would give it (only what the rules read)
function season() {
  const dir = path.join(FIXTURES, "season");
  const teams = Object.fromEntries(yaml.load(readFileSync(path.join(dir, "teams.yml"), "utf8")).map((t) => [t.id, t]));
  const players = Object.fromEntries(yaml.load(readFileSync(path.join(dir, "players.yml"), "utf8")).map((p) => [p.id, p]));
  const [head, ...lines] = readFileSync(path.join(dir, "schedule.csv"), "utf8").trim().split("\n");
  const cols = head.split(",");
  const schedule = {};
  for (const line of lines) {
    const r = Object.fromEntries(line.split(",").map((v, i) => [cols[i], v]));
    schedule[r.game_id] = { ...r, teams_known: r.home in teams && r.away in teams, cancelled: r.status === "cancelled" };
  }
  return { teams, players, schedule };
}
const SEASON = season();

function run(c) {
  const sheet = yaml.load(readFileSync(path.join(FIXTURES, c, "sheet.yml"), "utf8"));
  const expected = JSON.parse(readFileSync(path.join(FIXTURES, c, "expected.json"), "utf8"));
  const ctx = { ...SEASON, stem: sheet.game_id, folder: expected.folder || "games" };
  return { sheet, expected, result: rules.check(sheet, ctx), ctx };
}

test("the required cases are all there", () => {
  for (const c of ["clean", "bad-final", "ft-mismatch", "and-one", "unknown-jersey", "overtime", "page-two", "draft-with-sub"]) {
    assert.ok(CASES.includes(c), c);
  }
});

for (const c of CASES) {
  test(`fixture ${c} matches expected.json`, () => {
    const { expected, result: [game, problems] } = run(c);
    assert.deepEqual(problems, expected.problems);
    if (expected.game === null) {
      assert.equal(game, null);
    } else {
      assert.ok(game);
      for (const key of ["final", "quarters", "ot", "lines"]) assert.deepEqual(game[key], expected.game[key], key);
    }
  });

  test(`fixture ${c} survives dump and reload`, () => {
    const { sheet, expected, ctx } = run(c);
    const again = yaml.load(rules.dump(sheet));
    assert.deepEqual(rules.check(again, ctx)[1], expected.problems);
  });
}

test("a jump that isn't 1, 2 or 3 is an error on its box", () => {
  const { sheet, ctx } = run("clean");
  delete sheet.running.aa["20"];
  delete sheet.running.aa["19"];
  const [, problems] = rules.check(sheet, ctx);
  assert.deepEqual(problems.find((p) => p.at === "running.aa.22"),
    { level: "error", at: "running.aa.22", message: "aa goes from 17 to 22, a jump of 5; a score is 1, 2 or 3" });
});

test("a final sheet needs ids, checked_by and no review", () => {
  const { sheet, ctx } = run("draft-with-sub");
  sheet.status = "final";
  const [, problems] = rules.check(sheet, { ...ctx, folder: "games" });
  const errors = new Set(problems.filter((p) => p.level === "error").map((p) => p.at));
  for (const at of ["teams.bb.players.3.player", "review", "checked_by"]) assert.ok(errors.has(at), at);
});

test("the tally works out points even when there are errors", () => {
  const { sheet, ctx } = run("bad-final");
  const { game, tally } = rules.checkFull(sheet, ctx);
  assert.equal(game, null);
  assert.ok(Object.values(tally).some((t) => t.pts > 0));
});

// A full 100-point game a side, every score a 1 or a 2 (the most boxes), every
// row filled: the "Save to GitHub" link must still fit.
function bigSheet() {
  const team = (tid, start) => {
    const players = [], running = {};
    for (let i = 0; i < SPEC.roster_rows; i++) {
      players.push({ player: `${tid}-player-${i}`, num: start + i, here: true, ft: "MXMMXMXMMM", fouls: 4, tech: 1 });
    }
    let total = 0, k = 0;
    while (total < 100) {
      total += total + 2 <= 100 && k % 3 ? 2 : 1;
      running[total] = start + (k++ % SPEC.roster_rows);
    }
    return { players: { players }, running };
  };
  const a = team("aa", 10), b = team("bb", 40);
  return {
    game_id: "2026-10-17-g1", form: SPEC.form, status: "final", home: "aa", away: "bb", scorekeeper: "Pat S.",
    teams: { aa: a.players, bb: b.players }, running: { aa: a.running, bb: b.running },
    lines: { aa: [25, 50, 75, 100], bb: [25, 50, 75, 99] },
    boxes: { aa: { q1: 25, q2: 50, q3: 75, q4: 100, ot: null, final: 100 },
             bb: { q1: 25, q2: 50, q3: 75, q4: 99, ot: null, final: 100 } },
    checked_by: "Lee M.",
  };
}

test("a 100-point game fits in a Save to GitHub link", () => {
  const text = rules.dump(bigSheet());
  const url = SheetRules.githubNewFileUrl("tb-masters-basketball/website", "main", "data/2026-27/games/2026-10-17-g1.yml", text);
  console.log(`100-point game: ${text.length} bytes of YAML, ${url.length} characters of link`);
  assert.ok(url.length <= SheetRules.MAX_URL, `${url.length} > ${SheetRules.MAX_URL}`);
});
