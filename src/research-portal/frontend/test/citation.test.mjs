import assert from "node:assert/strict";
import test from "node:test";
import { isSourceArchive } from "../src/citation.ts";

test("source-partition ZIP links are distinguished from individual record pages", () => {
  assert.equal(isSourceArchive("https://download.open.fda.gov/drug/event/partition.json.zip"), true);
  assert.equal(isSourceArchive("https://example.test/partition.ZIP?download=1#source"), true);
  assert.equal(isSourceArchive("https://clinicaltrials.gov/study/NCT01234567"), false);
  assert.equal(isSourceArchive("https://example.test/record?attachment=partition.zip"), false);
});
