"use strict";
const test = require("node:test");
const assert = require("node:assert");
const logic = require("../../site/logic.js");

const names = ["17.0.0", "17.1.2", "17.1.3", "17.1.3.1", "17.1.3.3", "17.1.4", "17.5.1"];
const versions = names.map((v) => ({ v, ...logic.releaseParts(v), changes: [], support: { supported: true } }));
const at = (name) => names.indexOf(name);
const families = ["rSeries", "iSeries", "Virtual Edition"];
const familyOf = (model) => ({ "r5900": 0, "i5800": 1, "i7800": 1 })[model] ?? -1;

test("a release reads as branch, train, maintenance and point release", () => {
  assert.deepStrictEqual(logic.releaseParts("17.1.3.3"), { branch: "17.1", train: "17.1.3", r: 3, s: 3 });
  assert.deepStrictEqual(logic.releaseParts("17.5.1"), { branch: "17.5", train: "17.5.1", r: 1, s: 0 });
});

test("a point release fix covers its own train only", () => {
  const point = logic.releaseParts("17.1.3.1");
  assert.ok(logic.covers(point, logic.releaseParts("17.1.3.3")));
  assert.ok(!logic.covers(point, logic.releaseParts("17.1.4")));
  assert.ok(!logic.covers(point, logic.releaseParts("17.1.2")));
  assert.ok(logic.covers(logic.releaseParts("17.1.3"), logic.releaseParts("17.1.4")));
  assert.ok(!logic.covers(logic.releaseParts("17.1.3"), logic.releaseParts("17.5.1")));
});

test("status follows the notes of the branch", () => {
  const bug = { events: [[at("17.1.2"), "k"], [at("17.1.3.1"), "r"], [at("17.1.4"), "r"]] };
  assert.strictEqual(logic.statusAt(bug, at("17.1.2"), versions).key, "affected");
  assert.strictEqual(logic.statusAt(bug, at("17.1.3.3"), versions).key, "fixed");
  assert.strictEqual(logic.statusAt(bug, at("17.1.3"), versions).key, "potential");
  assert.strictEqual(logic.statusAt(bug, at("17.1.4"), versions).key, "fixed");
  assert.strictEqual(logic.statusAt(bug, at("17.5.1"), versions).key, "unknown");
  assert.strictEqual(logic.statusAt(bug, at("17.0.0"), versions).detail.id, "noMention");
});

test("a point release carries the known issues of its release", () => {
  const bug = { events: [[at("17.1.3"), "k"]] };
  const status = logic.statusAt(bug, at("17.1.3.3"), versions);
  assert.strictEqual(status.key, "affected");
  assert.strictEqual(status.detail.id, "openSince");
  assert.strictEqual(logic.statusAt(bug, at("17.1.4"), versions).key, "unknown");
});

test("the first fix of each train is listed once", () => {
  const events = [[at("17.1.3.1"), "r"], [at("17.1.3.3"), "r"], [at("17.1.4"), "r"], [at("17.5.1"), "r"]];
  assert.deepStrictEqual(logic.firstFixes(events, versions).map((i) => names[i]), ["17.5.1", "17.1.4", "17.1.3.1"]);
  const early = [[at("17.1.2"), "r"], [at("17.1.3.1"), "r"]];
  assert.deepStrictEqual(logic.firstFixes(early, versions).map((i) => names[i]), ["17.1.2"]);
});

test("hardware filter keeps the bugs naming no model", () => {
  const cited = { models: ["i5800"], families: [1] };
  const other = { models: ["i7800"], families: [1] };
  const family = { models: [], families: [1] };
  const generic = { models: [], families: [] };
  const elsewhere = { models: [], families: [2] };
  assert.strictEqual(logic.hardwareMatch(cited, "m:i5800", families, familyOf), "cited");
  assert.strictEqual(logic.hardwareMatch(other, "m:i5800", families, familyOf), null);
  assert.strictEqual(logic.hardwareMatch(family, "m:i5800", families, familyOf), "family");
  assert.strictEqual(logic.hardwareMatch(generic, "m:i5800", families, familyOf), "generic");
  assert.strictEqual(logic.hardwareMatch(elsewhere, "m:i5800", families, familyOf), null);
  assert.strictEqual(logic.hardwareMatch(other, "f:iSeries", families, familyOf), "family");
});

test("a bug is found by its number, as the notes and the Bug Tracker write it, and a platform stays a keyword", () => {
  const bug = { id: "2201813", text: "2201813 big-ip enforces maximum concurrent streams r5900" };
  assert.ok(logic.matchesTerms(bug, logic.searchTerms("2201813")));
  assert.ok(logic.matchesTerms(bug, logic.searchTerms("2201813-3, streams")));
  assert.ok(logic.matchesTerms(bug, logic.searchTerms("BT2201813")));
  assert.ok(logic.matchesTerms(bug, logic.searchTerms("r5900")));
  assert.ok(!logic.matchesTerms(bug, logic.searchTerms("2201814")));
});

test("an upgrade crosses the first release of each branch, then the target branch", () => {
  assert.deepStrictEqual(logic.upgradePath(versions, at("17.0.0"), at("17.1.4")).map((i) => names[i]),
    ["17.1.2", "17.1.3", "17.1.3.1", "17.1.3.3", "17.1.4"]);
  assert.deepStrictEqual(logic.upgradePath(versions, at("17.0.0"), at("17.5.1")).map((i) => names[i]), ["17.1.2", "17.5.1"]);
  assert.deepStrictEqual(logic.upgradePath(versions, at("17.5.1"), at("17.0.0")), []);
});

test("the reading list gives the pages of the crossed branches, target first", () => {
  const pages = { "17.1": { changes: 3, limitations: 4 }, "17.5": { changes: 7 } };
  assert.deepStrictEqual(logic.upgradeReading(pages, versions, at("17.0.0"), at("17.5.1")), [
    { branch: "17.5", kind: "changes", page: 7 },
    { branch: "17.1", kind: "changes", page: 3 },
    { branch: "17.1", kind: "limitations", page: 4 },
  ]);
});

test("upgrade groups put new and remaining issues apart from fixes", () => {
  const introduced = { events: [[at("17.1.4"), "k"]] };
  const remaining = { events: [[at("17.1.2"), "k"], [at("17.1.4"), "k"]] };
  const gained = { events: [[at("17.1.2"), "k"], [at("17.1.4"), "r"]] };
  assert.strictEqual(logic.upgradeGroup(introduced, at("17.1.2"), at("17.1.4"), versions), "introduced");
  assert.strictEqual(logic.upgradeGroup(remaining, at("17.1.2"), at("17.1.4"), versions), "remaining");
  assert.strictEqual(logic.upgradeGroup(gained, at("17.1.2"), at("17.1.4"), versions), "gained");
});

test("a branch is supported until its end of technical support", () => {
  const branches = { "17.1": { support: "2027-03-31", extended: null }, "16.1": { support: "2025-07-31", extended: null } };
  assert.ok(logic.branchSupport("17.1", branches, "2026-11-12").supported);
  assert.ok(!logic.branchSupport("16.1", branches, "2026-11-12").supported);
  assert.ok(logic.branchSupport("21.1", branches, "2026-11-12").supported);
  assert.ok(!logic.branchSupport("15.1", branches, "2026-11-12").supported);
});

test("a copied table is tab-separated", () => {
  assert.strictEqual(logic.tableText([["ID", "Text"], ["2201813", "a\nb"]]), "ID\tText\n2201813\ta b");
});

test("a platform K9412 no longer lists in the latest branch is stopped", () => {
  const iseries = { model: "i5800", eol: [[["i5800"], null, "17.5", "2027-01-01", "p"]], suggested: [] };
  assert.strictEqual(logic.hardwareStatus(iseries, "21.1", "2026-11-12").key, "stopped");
  const old = { model: "4000s", eol: [[["4000s"], null, null, "2021-04-01", "p"]], suggested: [] };
  assert.strictEqual(logic.hardwareStatus(old, "21.1", "2026-11-12").key, "stopped");
  const sold = { model: "r5600", eol: [[["r5600"], null, null, "2030-01-01", "p"]], suggested: [] };
  assert.strictEqual(logic.hardwareStatus(sold, "21.1", "2026-11-12").key, "announced");
  assert.strictEqual(logic.hardwareStatus({ model: "r5900", eol: [], suggested: [] }, "21.1", "2026-11-12").key, "none");
});

test("an F5OS Critical Release comes after the Hardened Releases of its patch release", () => {
  assert.deepStrictEqual(logic.releaseParts("1.8.4-HR-2"), { branch: "1.8", train: "1.8.4", r: 4, s: 2 });
  assert.deepStrictEqual(logic.releaseParts("1.8.4-CR"), { branch: "1.8", train: "1.8.4", r: 4, s: 50 });
  assert.ok(logic.covers(logic.releaseParts("1.8.4-HR-1"), logic.releaseParts("1.8.4-CR")));
  assert.ok(!logic.covers(logic.releaseParts("1.8.4-HR-1"), logic.releaseParts("1.8.5")));
});
