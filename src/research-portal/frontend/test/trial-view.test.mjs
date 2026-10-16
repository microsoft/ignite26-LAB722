import assert from "node:assert/strict";
import test from "node:test";
import { filterTrials, summarizeTrials } from "../src/trial-view.ts";

const trials = [
  { trial_id: "one", phase: "PHASE2", status: "COMPLETED" },
  { trial_id: "two", phase: "PHASE3", status: "RECRUITING" },
  { trial_id: "three", phase: "PHASE3", status: "COMPLETED" },
];

test("phase/status filters intersect without changing complete source records", () => {
  assert.deepEqual(filterTrials(trials, "PHASE3", "COMPLETED"), [trials[2]]);
  assert.deepEqual(filterTrials(trials, "", "RECRUITING"), [trials[1]]);
  assert.equal(filterTrials(trials, "", "").length, 3);
  assert.deepEqual(filterTrials(trials, "PHASE1", ""), []);
  assert.equal(trials.length, 3);
});

test("summaries count the selected source collection with deterministic labels", () => {
  assert.deepEqual(summarizeTrials(trials), {
    phases: [["PHASE2", 1], ["PHASE3", 2]],
    statuses: [["COMPLETED", 2], ["RECRUITING", 1]],
  });
  assert.deepEqual(summarizeTrials([]), { phases: [], statuses: [] });
});
