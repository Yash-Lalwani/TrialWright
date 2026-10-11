// Mock fixture integrity. Run: npm test (generates the sample PDF first).
//
// 1. Every `where` / `related` quote in mocks/issues.json is found inside its bbox
//    on its page of public/sample-protocol.pdf, read back with PDF.js. This is the
//    guarantee that highlights in the workspace sit on the quoted text.
// 2. Mock counts and cross-references agree with each other.

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { getDocument } from "pdfjs-dist/legacy/build/pdf.mjs";

const ROOT = join(fileURLToPath(new URL(".", import.meta.url)), "..");
const json = async (name) => JSON.parse(await readFile(join(ROOT, "mocks", name), "utf8"));
const normalize = (s) => s.replace(/\s+/g, " ").trim();

const issues = await json("issues.json");
const pdfData = new Uint8Array(await readFile(join(ROOT, "public", "sample-protocol.pdf")));
const standardFontDataUrl =
  join(dirname(createRequire(import.meta.url).resolve("pdfjs-dist/package.json")), "standard_fonts") + "/";
const pdf = await getDocument({ data: pdfData, standardFontDataUrl, isEvalSupported: false }).promise;

/** Text items per page with their centre point in top-left PDF coordinates. */
const pageItems = new Map();
async function itemsOn(pageNumber) {
  if (!pageItems.has(pageNumber)) {
    const page = await pdf.getPage(pageNumber);
    const height = page.getViewport({ scale: 1 }).height;
    const { items } = await page.getTextContent();
    pageItems.set(
      pageNumber,
      items
        .filter((it) => it.str.trim())
        .map((it) => ({
          str: it.str,
          x: it.transform[4],
          right: it.transform[4] + it.width,
          cy: height - it.transform[5] - it.height * 0.3,
        })),
    );
  }
  return pageItems.get(pageNumber);
}

/** Text whose vertical centre is in the bbox and that overlaps it horizontally. */
async function textInBox(pageNumber, [x0, y0, x1, y1]) {
  const items = await itemsOn(pageNumber);
  return normalize(
    items
      .filter((it) => it.cy >= y0 && it.cy <= y1 && it.x < x1 && it.right > x0)
      .sort((a, b) => a.cy - b.cy || a.x - b.x)
      .map((it) => it.str)
      .join(" "),
  );
}

test("issues.json has 20 issues and a matching total", () => {
  assert.equal(issues.items.length, 20);
  assert.equal(issues.total, issues.items.length);
  assert.equal(new Set(issues.items.map((i) => i.id)).size, issues.items.length);
});

test("every evidence quote lies inside its bbox on the sample PDF", async () => {
  const protocol = await json("protocol.json");
  assert.equal(pdf.numPages, protocol.pages, "protocol.json pages must match the PDF");

  for (const issue of issues.items) {
    for (const [label, where] of [["where", issue.where], ...issue.related.map((r, i) => [`related[${i}]`, r])]) {
      const at = `${issue.id} ${label}`;
      assert.ok(where.page >= 1 && where.page <= pdf.numPages, `${at}: page out of range`);
      const [x0, y0, x1, y1] = where.bbox;
      assert.ok(x0 < x1 && y0 < y1, `${at}: degenerate bbox`);
      const page = await pdf.getPage(where.page);
      const { width, height } = page.getViewport({ scale: 1 });
      assert.ok(x0 >= 0 && y0 >= 0 && x1 <= width && y1 <= height, `${at}: bbox outside page`);

      const found = await textInBox(where.page, where.bbox);
      for (const part of where.quote.split("...").map(normalize).filter(Boolean)) {
        assert.ok(found.includes(part), `${at}: "${part}" not inside bbox on p.${where.page}; found "${found}"`);
      }
    }
  }
});

test("run counts match the issue list", async () => {
  const run = await json("run.json");
  const count = (key, value) => issues.items.filter((i) => i[key] === value).length;
  for (const s of ["critical", "major", "minor", "advisory"]) assert.equal(run.counts[s], count("severity", s), s);
  for (const s of ["open", "accepted", "rejected"]) assert.equal(run.counts[s], count("status", s), s);
});

test("issue mix covers every severity, category and source", () => {
  const values = (key) => new Set(issues.items.map((i) => i[key]));
  assert.deepEqual([...values("severity")].sort(), ["advisory", "critical", "major", "minor"]);
  assert.deepEqual(
    [...values("category")].sort(),
    ["advisory", "amendment_risk", "burden", "completeness", "consistency"],
  );
  assert.deepEqual(
    [...values("source")].sort(),
    ["ai:biostatistician", "ai:clinical_ops", "ai:clinical_scientist", "ai:medical_writer", "rule"],
  );
});

test("completeness summary and pages agree with items and the PDF", async () => {
  const c = await json("completeness.json");
  for (const s of ["present", "thin", "missing"]) {
    assert.equal(c.summary[s], c.items.filter((i) => i.status === s).length, s);
  }
  assert.equal(c.summary.required, c.items.length);
  for (const item of c.items) {
    for (const p of item.pages) assert.ok(p >= 1 && p <= pdf.numPages, `${item.item_id} page ${p}`);
    if (item.status === "missing") assert.equal(item.pages.length, 0, `${item.item_id} missing but has pages`);
  }
});

test("cross-references point at existing issues", async () => {
  const ids = new Set(issues.items.map((i) => i.id));
  const peers = await json("peers.json");
  for (const id of peers.hotspot_issue_ids) {
    assert.ok(ids.has(id), id);
    assert.equal(issues.items.find((i) => i.id === id).category, "amendment_risk");
  }
  const trace = await json("trace.json");
  for (const a of trace.audit) {
    assert.equal(issues.items.find((i) => i.id === a.issue_id)?.status, a.decision, a.issue_id);
  }
  const shownAi = issues.items.filter((i) => i.source !== "rule").length;
  assert.equal(trace.verifier.shown, shownAi, "verifier.shown must equal AI issues in the list");
  const diff = await json("diff.json");
  assert.equal(diff.resolved.length + diff.unchanged.length + diff.new.length, issues.items.length);
});
