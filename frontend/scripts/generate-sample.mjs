// Generates the synthetic sample protocol PDF and the mock issues that point into it.
//
//   public/sample-protocol.pdf   (gitignored; PDFs are never committed, CONTRACTS.md §6.1)
//   mocks/issues.json            (committed; CONTRACTS.md §4.4 shape)
//
// Bounding boxes are computed from the exact positions the text is drawn at, in
// PDF points with a top-left origin (CONTRACTS.md §2), so highlights always line
// up with the rendered document. Output is deterministic; re-running it produces
// byte-identical files. Run: npm run sample

import { mkdir, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { PDFDocument, StandardFonts, rgb } from "pdf-lib";

import { pages, PROTOCOL_NUMBER, TITLE } from "./sample-protocol/document.mjs";
import { issues } from "./sample-protocol/issues.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const PDF_OUT = join(ROOT, "public", "sample-protocol.pdf");
const ISSUES_OUT = join(ROOT, "mocks", "issues.json");

const W = 612;
const H = 792;
const ML = 72;
const MR = 540;
const CONTENT_TOP = 72;
const CONTENT_BOTTOM = 740;
const INK = rgb(0.1, 0.1, 0.12);
const GREY = rgb(0.42, 0.44, 0.48);
const RULE = rgb(0.72, 0.74, 0.78);
const FIXED_DATE = new Date("2026-09-01T00:00:00Z");

const doc = await PDFDocument.create();
doc.setTitle(`${PROTOCOL_NUMBER}: ${TITLE} (synthetic sample)`);
doc.setAuthor("Protocol Pre-Flight (synthetic test document)");
doc.setProducer("Protocol Pre-Flight sample generator");
doc.setCreator("Protocol Pre-Flight sample generator");
doc.setCreationDate(FIXED_DATE);
doc.setModificationDate(FIXED_DATE);

const regular = await doc.embedFont(StandardFonts.Helvetica);
const bold = await doc.embedFont(StandardFonts.HelveticaBold);

/** anchors[id] = { page, text, lines: [...] } or { page, text, rect } */
const anchors = {};

const round = (n) => Math.round(n * 10) / 10;

/** Greedy word wrap. Returns lines with char offsets into the space-joined text. */
function wrap(text, font, size, maxWidth) {
  const words = text.split(/\s+/).filter(Boolean);
  const lines = [];
  let current = [];
  let start = 0;
  let offset = 0;
  for (const word of words) {
    const candidate = [...current, word].join(" ");
    if (current.length && font.widthOfTextAtSize(candidate, size) > maxWidth) {
      const lineText = current.join(" ");
      lines.push({ text: lineText, start, end: start + lineText.length });
      start = offset;
      current = [word];
    } else {
      current.push(word);
    }
    offset += word.length + 1;
  }
  if (current.length) {
    const lineText = current.join(" ");
    lines.push({ text: lineText, start, end: start + lineText.length });
  }
  return { text: words.join(" "), lines };
}

function makePageWriter(page, pageNumber) {
  let y = CONTENT_TOP;
  let first = true;

  /** Draw wrapped text with its top at the current y. Returns line geometry. */
  function drawWrapped(text, { font = regular, size = 10, leading = 14, x = ML, width = MR - ML, color = INK }) {
    const wrapped = wrap(text, font, size, width);
    const lines = wrapped.lines.map((line) => {
      const baseline = y + size * 0.8;
      page.drawText(line.text, { x, y: H - baseline, size, font, color });
      const geometry = {
        ...line,
        x,
        font,
        size,
        top: baseline - size * 0.78,
        bottom: baseline + size * 0.24,
      };
      y += leading;
      return geometry;
    });
    return { text: wrapped.text, lines };
  }

  function before(gap) {
    if (!first) y += gap;
    first = false;
  }

  function record(id, value) {
    if (!id) return;
    if (anchors[id]) throw new Error(`Duplicate anchor ${id}`);
    anchors[id] = { page: pageNumber, ...value };
  }

  const handlers = {
    label(b) {
      before(0);
      drawWrapped(b.text, { font: bold, size: 9, leading: 13, color: GREY });
    },
    title(b) {
      before(0);
      drawWrapped(b.text, { font: bold, size: 16, leading: 21 });
    },
    h1(b) {
      before(10);
      drawWrapped(b.text, { font: bold, size: 14, leading: 18 });
      y += 6;
    },
    h2(b) {
      before(6);
      drawWrapped(b.text, { font: bold, size: 11, leading: 15 });
      y += 3;
    },
    p(b) {
      before(0);
      record(b.id, drawWrapped(b.text, {}));
      y += 8;
    },
    small(b) {
      before(0);
      record(b.id, drawWrapped(b.text, { size: 8.5, leading: 11.5, color: rgb(0.2, 0.21, 0.24) }));
      y += 4;
    },
    li(b) {
      before(0);
      const top = y;
      page.drawText(b.label, { x: ML, y: H - (y + 10 * 0.8), size: 10, font: regular, color: INK });
      y = top;
      record(b.id, drawWrapped(b.text, { x: ML + 22, width: MR - ML - 22 }));
      y += 4;
    },
    kv(b) {
      before(0);
      const top = y;
      const leading = b.compact ? 13 : 14;
      drawWrapped(b.key, { font: bold, size: 10, leading, width: 128 });
      const afterKey = y;
      y = top;
      record(b.id, drawWrapped(b.value, { x: ML + 138, width: MR - ML - 138, leading }));
      y = Math.max(y, afterKey) + (b.compact ? 1 : 6);
    },
    toc(b) {
      before(0);
      const top = y;
      drawWrapped(b.key, { size: 10, leading: 16, width: 400 });
      const width = regular.widthOfTextAtSize(b.value, 10);
      page.drawText(b.value, { x: MR - width, y: H - (top + 8), size: 10, font: regular, color: INK });
    },
    space(b) {
      y += b.h;
    },
    table(b) {
      before(0);
      const labelWidth = 150;
      const colWidth = (MR - ML - labelWidth) / b.columns.length;
      const size = 7.5;
      const hline = (yy, weight = 0.5) =>
        page.drawLine({ start: { x: ML, y: H - yy }, end: { x: MR, y: H - yy }, thickness: weight, color: RULE });
      const centered = (text, font, colIndex, rowTop, rowHeight) => {
        const width = font.widthOfTextAtSize(text, size);
        const x = ML + labelWidth + colIndex * colWidth + (colWidth - width) / 2;
        page.drawText(text, { x, y: H - (rowTop + rowHeight / 2 + size * 0.35), size, font, color: INK });
      };

      const tableTop = y;
      hline(y, 0.8);
      const headerHeight = 16;
      page.drawText("Procedure", { x: ML + 3, y: H - (y + headerHeight / 2 + size * 0.35), size, font: bold, color: INK });
      b.columns.forEach((c, i) => centered(c, bold, i, y, headerHeight));
      y += headerHeight;
      hline(y);

      const subHeight = 13;
      page.drawText(b.subheader.label, { x: ML + 3, y: H - (y + subHeight / 2 + size * 0.35), size, font: regular, color: GREY });
      b.subheader.cells.forEach((c, i) => c && centered(c, regular, i, y, subHeight));
      y += subHeight;
      hline(y, 0.8);

      const rowHeight = 15;
      for (const r of b.rows) {
        const rowTop = y;
        page.drawText(r.label, { x: ML + 3, y: H - (rowTop + rowHeight / 2 + size * 0.35), size, font: regular, color: INK });
        r.cells.forEach((c, i) => c && centered(c, bold, i, rowTop, rowHeight));
        y += rowHeight;
        hline(y, 0.4);
        record(r.id, {
          text: [r.label, ...r.cells.filter(Boolean)].join(" "),
          rect: [ML, rowTop, MR, y],
        });
      }
      for (let i = 0; i <= b.columns.length; i++) {
        const x = ML + labelWidth + i * colWidth;
        page.drawLine({ start: { x, y: H - tableTop }, end: { x, y: H - y }, thickness: 0.4, color: RULE });
      }
      page.drawLine({ start: { x: ML, y: H - tableTop }, end: { x: ML, y: H - y }, thickness: 0.4, color: RULE });
    },
  };

  return {
    write(block) {
      const handler = handlers[block.t];
      if (!handler) throw new Error(`Unknown block type ${block.t}`);
      handler(block);
      if (y > CONTENT_BOTTOM) throw new Error(`Page ${pageNumber} overflows (y=${round(y)})`);
    },
  };
}

pages.forEach((blocks, index) => {
  const pageNumber = index + 1;
  const page = doc.addPage([W, H]);
  // Running header and footer, so nobody mistakes the document for a real protocol.
  page.drawText(`${PROTOCOL_NUMBER}  |  Version 1.0`, { x: ML, y: H - 40, size: 7.5, font: regular, color: GREY });
  const notice = "SYNTHETIC SAMPLE - NOT A REAL STUDY";
  page.drawText(notice, { x: MR - bold.widthOfTextAtSize(notice, 7.5), y: H - 40, size: 7.5, font: bold, color: GREY });
  page.drawLine({ start: { x: ML, y: H - 48 }, end: { x: MR, y: H - 48 }, thickness: 0.5, color: RULE });
  const footer = `Page ${pageNumber} of ${pages.length}`;
  page.drawText(footer, { x: (W - regular.widthOfTextAtSize(footer, 8)) / 2, y: H - 760, size: 8, font: regular, color: GREY });

  const writer = makePageWriter(page, pageNumber);
  blocks.forEach((block) => writer.write(block));
});

/** Tightest box around `quote` inside an anchor, [x0, y0, x1, y1] with a small pad. */
function locate(ref, issueId) {
  const anchor = anchors[ref.anchor];
  if (!anchor) throw new Error(`${issueId}: unknown anchor ${ref.anchor}`);
  const idx = anchor.text.indexOf(ref.quote);
  if (idx < 0) throw new Error(`${issueId}: quote not found in ${ref.anchor}: "${ref.quote}"`);

  let box;
  if (anchor.rect) {
    box = anchor.rect;
  } else {
    const end = idx + ref.quote.length;
    const hit = anchor.lines.filter((l) => l.start < end && l.end > idx);
    const xs = hit.flatMap((l) => {
      const a = Math.max(l.start, idx) - l.start;
      const b = Math.min(l.end, end) - l.start;
      return [
        l.x + l.font.widthOfTextAtSize(l.text.slice(0, a), l.size),
        l.x + l.font.widthOfTextAtSize(l.text.slice(0, b), l.size),
      ];
    });
    box = [
      Math.min(...xs) - 2,
      Math.min(...hit.map((l) => l.top)) - 1.5,
      Math.max(...xs) + 2,
      Math.max(...hit.map((l) => l.bottom)) + 1.5,
    ];
  }
  return {
    section: ref.section,
    page: anchor.page,
    bbox: box.map(round),
    quote: ref.quote,
  };
}

const items = issues.map((issue) => ({
  id: issue.id,
  check_id: issue.check_id,
  source: issue.source,
  category: issue.category,
  severity: issue.severity,
  title: issue.title,
  where: locate(issue.where, issue.id),
  related: issue.related.map((r) => locate(r, issue.id)),
  why: issue.why,
  fix: issue.fix,
  confidence: issue.confidence,
  verified: issue.verified,
  status: issue.status,
}));

// CONTRACTS.md §4.6: v1 (run_31c9) vs a hypothetical v2 (run_52aa). Scores are the
// contract example; issue objects are the generated ones so locations stay valid.
const RESOLVED_IN_V2 = new Set(["iss_01", "iss_02", "iss_03", "iss_04", "iss_05", "iss_06", "iss_08", "iss_10", "iss_11", "iss_12"]);
const diff = {
  from_run: "run_31c9",
  to_run: "run_52aa",
  score_from: { overall: 62, completeness: 81, consistency: 44, burden: 58, amendment_risk: 70 },
  score_to: { overall: 91, completeness: 96, consistency: 92, burden: 74, amendment_risk: 88 },
  resolved: items.filter((i) => RESOLVED_IN_V2.has(i.id)),
  new: [],
  unchanged: items.filter((i) => !RESOLVED_IN_V2.has(i.id)),
};

await mkdir(dirname(PDF_OUT), { recursive: true });
await writeFile(PDF_OUT, await doc.save({ useObjectStreams: false }));
await writeFile(ISSUES_OUT, JSON.stringify({ total: items.length, items }, null, 2) + "\n");
await writeFile(join(ROOT, "mocks", "diff.json"), JSON.stringify(diff, null, 2) + "\n");

console.log(`sample-protocol.pdf: ${pages.length} pages, ${Object.keys(anchors).length} anchors`);
console.log(`issues.json: ${items.length} issues`);
