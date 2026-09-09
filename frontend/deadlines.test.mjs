import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import ts from "typescript";

const source = readFileSync(new URL("./src/app/deadlines.ts", import.meta.url), "utf8")
  .replace("import.meta.env.VITE_BUSINESS_TIME_ZONE", "undefined");
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 },
});
const { isDeadlineOverdue } = await import(
  "data:text/javascript;base64," + Buffer.from(outputText).toString("base64")
);

test("calendar deadlines use the business day even after midnight UTC", () => {
  const now = new Date("2026-09-09T01:00:00Z");
  assert.equal(isDeadlineOverdue("2026-09-08", "pending", now), false);
  assert.equal(isDeadlineOverdue("2026-09-07", "pending", now), true);
  assert.equal(isDeadlineOverdue("2026-09-09", "pending", now), false);
});

test("finished records and missing or invalid dates are not overdue", () => {
  for (const status of ["completed", "closed", "cancelled", "effective", "resolved"]) {
    assert.equal(isDeadlineOverdue("2000-01-01", status), false);
  }
  assert.equal(isDeadlineOverdue(null, "pending"), false);
  assert.equal(isDeadlineOverdue("invalid", "pending"), false);
});
