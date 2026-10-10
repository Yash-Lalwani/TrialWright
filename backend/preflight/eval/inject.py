# ruff: noqa: E501  (regex- and table-heavy module)
"""Error injector: edits a real protocol PDF to plant known errors (T01-T18), with an answer key.

Edits are made in place with PyMuPDF redaction (white-out a token, write the replacement at the same spot), so the
benchmark exercises the whole pipeline from PDF. Every injector either returns an error record or a skip reason;
nothing is guessed. Injectors are developed against the dev split only.
"""
from __future__ import annotations

import json
import random
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from .types import TYPES

Rect = pymupdf.Rect
FOOTER_Y = 60  # ignore header/footer bands (points from top / bottom)


@dataclass
class Hit:
    page: int          # 1-indexed
    line: str
    token: str
    start: int
    rect: Rect
    size: float
    line_rect: Rect
    idx: int = -1
    bold: bool = False


@dataclass
class Skip:
    type: str
    reason: str


@dataclass
class Ctx:
    doc: pymupdf.Document
    nct: str
    rng: random.Random
    registry: dict | None = None
    sections: list | None = None
    graph: object = None  # LLM-extracted ProtocolGraph of the CLEAN pdf, for injectors driven by extracted evidence spans
    used: dict[int, list[Rect]] = field(default_factory=dict)
    subs: dict[tuple[int, int], list[tuple[int, int, str]]] = field(default_factory=dict)  # (page, line idx) -> subs
    whites: dict[int, list[Rect]] = field(default_factory=dict)
    _lines: dict[int, list[dict]] = field(default_factory=dict)
    _ttf: object = None
    touched: list = field(default_factory=list)  # [page, original line text] for every line an injection changed

    def lines(self, pno: int) -> list[dict]:
        """Text lines of a page (1-indexed) with spans, in reading order."""
        if not 1 <= pno <= len(self.doc):
            return []  # injectors scan fixed page ranges; short documents just have fewer pages
        if pno not in self._lines:
            page = self.doc[pno - 1]
            out = []
            for b in page.get_text("dict")["blocks"]:
                for ln in b.get("lines", []):
                    spans = [s for s in ln["spans"] if s["text"].strip()]
                    if not spans:
                        continue
                    r = Rect(ln["bbox"])
                    if r.y1 < FOOTER_Y or r.y0 > page.rect.height - FOOTER_Y:
                        continue
                    out.append({"text": "".join(s["text"] for s in ln["spans"]), "spans": ln["spans"], "rect": r})
            self._lines[pno] = out
        return self._lines[pno]

    def renderable(self, text: str) -> bool:
        """Can this line be redrawn character-for-character? Latin-1 via base-14 fonts, other symbols only if an installed
        Unicode font has the glyph. Lines with private-use glyphs (e.g. SymbolMT's U+F0B3 for >=) are not injectable:
        redrawing them would change how they extract, handing the pipeline a signal the original never had."""
        if self._ttf is None:
            path = _font_for(False)
            self._ttf = pymupdf.Font(fontfile=path) if path else False
        return all(ord(c) < 256 or (self._ttf and self._ttf.has_glyph(ord(c))) for c in text)

    def free(self, pno: int, rect: Rect) -> bool:
        return not any(rect.intersects(u) for u in self.used.get(pno, []))

    def claim(self, pno: int, rect: Rect) -> None:
        self.used.setdefault(pno, []).append(Rect(rect))

    def replace(self, hit: Hit, new: str) -> None:
        self.claim(hit.page, hit.rect)
        self.subs.setdefault((hit.page, hit.idx), []).append((hit.start, hit.start + len(hit.token), new))

    def whiteout(self, pno: int, rect: Rect) -> None:
        self.claim(pno, rect)
        self.whites.setdefault(pno, []).append(Rect(rect))

    def new_line(self, hit: Hit) -> str:
        text = hit.line
        for a, b, new in sorted(self.subs[(hit.page, hit.idx)], reverse=True):
            text = text[:a] + new + text[b:]
        return text

    def _band(self, ln: dict) -> Rect:
        """A thin band through the middle of the text height. Redaction removes every glyph whose box touches the
        rectangle, and in tightly spaced text a full-height rectangle also deletes the lines above and below."""
        r, sp = ln["rect"], ln["spans"][0]
        base, size = sp["origin"][1], sp["size"]
        return Rect(r.x0 - 0.3, base - 0.45 * size, r.x1 + 0.3, base - 0.08 * size)

    def _lines_under(self, pno: int, rect: Rect) -> list[dict]:
        """Text lines of a page that mostly lie inside a rectangle."""
        out = []
        for ln in self.lines(pno):
            inter = ln["rect"] & rect
            if not inter.is_empty and inter.height >= 0.5 * ln["rect"].height:
                out.append(ln)
        return out

    def apply(self) -> None:
        """Rewrite each edited line as ONE piece of text so it extracts as a normal sentence (a redaction
        annotation's replacement text would extract as a separate block)."""
        pages = {p for p, _ in self.subs} | set(self.whites)
        for pno in sorted(pages):
            page = self.doc[pno - 1]
            lines = self.lines(pno)
            todo = [(lines[i], self._span_texts(lines[i], subs)) for (p, i), subs in self.subs.items() if p == pno]
            for ln, _ in todo:
                self.touched.append([pno, _norm_line(ln["text"])])
                page.add_redact_annot(self._band(ln), fill=(1, 1, 1))
            for r in self.whites.get(pno, []):
                under = self._lines_under(pno, r)
                for ln in under:
                    self.touched.append([pno, _norm_line(ln["text"])])
                    page.add_redact_annot(self._band(ln), fill=(1, 1, 1))
                if not under:  # no text line found: fall back to the middle of the rectangle
                    page.add_redact_annot(Rect(r.x0, r.y0 + 0.35 * r.height, r.x1, r.y0 + 0.65 * r.height), fill=(1, 1, 1))
            page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)
            for ln, text in todo:
                _draw_line(page, ln, text)

    @staticmethod
    def _span_texts(ln: dict, subs: list[tuple[int, int, str]]) -> list[str]:
        """New text of every span in the line; only spans that hold a replaced token change."""
        out, off = [], 0
        for sp in ln["spans"]:
            t, n = sp["text"], len(sp["text"])
            for a, b, new in sorted((x for x in subs if off <= x[0] < off + n), reverse=True):
                t = t[: a - off] + new + t[b - off:]
            out.append(t)
            off += n
        return out


def _norm_line(t: str) -> str:
    return re.sub(r"\s+", " ", t).strip()


FONT_CANDIDATES = {
    False: ["/System/Library/Fonts/Supplemental/Times New Roman.ttf", "C:/Windows/Fonts/times.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"],
    True: ["/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf", "C:/Windows/Fonts/timesbd.ttf",
           "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
           "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"],
}
ASCII_FALLBACK = {"\u2265": ">=", "\u2264": "<=", "\u2013": "-", "\u2014": "-", "\u2212": "-", "\u2260": "!=", "\u2192": "->"}


def _base14(font: str, bold: bool, italic: bool) -> str:
    """Closest base-14 font so character widths match the original (a width mismatch makes the extractor insert
    spaces between adjacent spans)."""
    f = font.lower()
    fam = "he" if re.search(r"arial|helvet|calibri|verdana|tahoma|sans", f) else "co" if re.search(r"courier|consol|mono", f) else "ti"
    table = {"he": ("helv", "hebo", "heit", "hebi"), "co": ("cour", "cobo", "coit", "cobi"), "ti": ("tiro", "tibo", "tiit", "tibi")}[fam]
    return table[(1 if bold else 0) + (2 if italic else 0)]


def _font_for(bold: bool) -> str | None:
    return next((p for p in FONT_CANDIDATES[bold] if Path(p).exists()), None)


def _draw_line(page: pymupdf.Page, ln: dict, span_texts: list[str]) -> None:
    """Redraw a line span by span, each at its original origin, size and colour, so layout is unchanged and the
    line still extracts as one line. Uses insert_text (no shaping, so no ligatures). Characters Times-Roman can
    encode go through the base-14 font, which extracts exactly (embedded TrueType fonts extract '-' as a soft
    hyphen and ' ' as a non-breaking space, breaking keyword matching). Only symbols outside Latin-1 (>=, <=, en
    dash) use an installed Unicode font; without one they become ASCII stand-ins."""
    for sp, text in zip(ln["spans"], span_texts, strict=True):
        if not text:
            continue
        bold = "bold" in sp["font"].lower() or bool(sp["flags"] & 16)
        size = sp["size"]
        color = tuple(((sp["color"] >> sh) & 255) / 255 for sh in (16, 8, 0))
        base = _base14(sp["font"], bold, "italic" in sp["font"].lower() or "oblique" in sp["font"].lower() or bool(sp["flags"] & 2))
        path = _font_for(bold)
        ttf = pymupdf.Font(fontfile=path) if path else None
        if ttf:
            page.insert_font(fontname="PFSYM", fontfile=path)
        runs: list[tuple[str, str]] = []
        for ch in text:
            if ord(ch) < 256:
                name, ch2 = base, ch
            elif ttf:
                name, ch2 = "PFSYM", ch
            else:
                name, ch2 = base, ASCII_FALLBACK.get(ch, "?")
            if runs and runs[-1][0] == name:
                runs[-1] = (name, runs[-1][1] + ch2)
            else:
                runs.append((name, ch2))
        x, y = sp["origin"]
        for name, run in runs:
            page.insert_text((x, y), run, fontname=name, fontsize=size, color=color)
            x += ttf.text_length(run, fontsize=size) if name == "PFSYM" else pymupdf.get_text_length(run, fontname=name, fontsize=size)


def find(ctx: Ctx, pattern: str, group: int = 1, pages: range | list[int] | None = None, flags: int = re.I) -> list[Hit]:
    """All regex matches (token = the group) with the exact rectangle of the token on the page."""
    rx = re.compile(pattern, flags)
    hits: list[Hit] = []
    for pno in pages or range(1, len(ctx.doc) + 1):
        for idx, ln in enumerate(ctx.lines(pno)):
            if not ctx.renderable(ln["text"]):
                continue
            for m in rx.finditer(ln["text"]):
                tok = m.group(group)
                if tok is None:
                    continue
                s, e = m.span(group)
                off = 0
                for sp in ln["spans"]:
                    n = len(sp["text"])
                    if off <= s and e <= off + n:  # token inside one span
                        k = sp["text"][: s - off].count(tok)  # occurrences of tok before it inside the span
                        cands = ctx.doc[pno - 1].search_for(tok, clip=Rect(sp["bbox"]) + (-1, -1, 1, 1))
                        if len(cands) > k:
                            hits.append(Hit(pno, ln["text"], tok, s, cands[k], sp["size"], ln["rect"], idx))
                        break
                    off += n
    return hits


def short(h: Hit, new: str, pad: int = 14) -> str:
    """Context around the new token, for matching quotes in flags."""
    a = h.line[max(0, h.start - pad):h.start]
    b = h.line[h.start + len(h.token): h.start + len(h.token) + pad]
    return re.sub(r"\s+", " ", f"{a}{new}{b}").strip()


def error(t: str, h: Hit, new: str, desc: str, other_pages: list[int] | None = None, **extra) -> dict:
    spec = TYPES[t]
    return {
        "type": t, "name": spec.name, "page": h.page, "bbox": [round(v, 1) for v in h.rect],
        "original": h.token, "new": new, "context": re.sub(r"\s+", " ", h.line).strip()[:200],
        "new_line": re.sub(r"\s+", " ", h.line[:h.start] + new + h.line[h.start + len(h.token):]).strip()[:200],
        "_line": (h.page, h.idx), "_start": h.start,
        "description": desc, "expected_checks": list(spec.expected_checks),
        "amendment_category": spec.amendment_category, "needs_llm": spec.needs_llm,
        "match": {"pages": sorted({h.page, *(other_pages or [])}), "texts": [short(h, new)], **extra},
    }


def _early(hits: list[Hit], limit: int = 20) -> list[Hit]:
    return [h for h in hits if h.page <= limit]


def _choose_keeping_one(ctx: Ctx, same: list[Hit]) -> Hit | None:
    """Pick one mention of a repeated value to change, but only if at least one OTHER mention stays unchanged;
    otherwise changing every mention would make the document consistent again and plant no error."""
    free = [h for h in same if ctx.free(h.page, h.rect)]
    if len(free) < 2:
        return None
    early = [h for h in free if h.page <= 20] or free
    return min(early, key=lambda h: (h.page, h.rect.y0))


def _choose(ctx: Ctx, hits: list[Hit]) -> Hit | None:
    free = [h for h in hits if ctx.free(h.page, h.rect)]
    return min(free, key=lambda h: (h.page, h.rect.y0)) if free else None


# --------------------------------------------------------------------------------------------- text-change types
AGE = r"(?:≥|>=|aged?|age of|at least|greater than or equal to)\s*(\d{2})\s*(?:years|yrs)|(\d{2})\s*(?:years|yrs)\s*(?:of age|or older|and older)"


def _age_hits(ctx: Ctx) -> list[Hit]:
    return find(ctx, AGE, 1) + find(ctx, AGE, 2)


def t06_age(ctx: Ctx):
    hits = _age_hits(ctx)
    vals = Counter(h.token for h in hits)
    if not vals or vals.most_common(1)[0][1] < 2:
        return Skip("T06", "minimum age is stated only once, so a change cannot create an inconsistency")
    v = vals.most_common(1)[0][0]
    same = [h for h in hits if h.token == v]
    h = _choose_keeping_one(ctx, same)
    if not h:
        return Skip("T06", "no free age mention")
    new = str(int(v) + 3)
    ctx.replace(h, new)
    return error("T06", h, new, f"Minimum age changed {v} -> {new} in one place only",
                 [x.page for x in same if x is not h])


def t07_dose(ctx: Ctx):
    hits = find(ctx, r"(\d+(?:\.\d+)?)\s*mg(?:/kg)?\b")
    # study-drug dosing only: skip thresholds like "corticosteroids > 10 mg/day prednisone" and lab/exclusion lines
    hits = [h for h in hits if re.search(r"dose|dosing|administered|infusion|intravenous|every|once|Q\d+W|mg/kg", h.line, re.I)
            and not re.search(r"prednisone|steroid|exclu|creatinine|ALT|AST", h.line, re.I)]
    counts = Counter((h.token, re.search(r"mg(?:/kg)?", h.line[h.start:]).group(0)) for h in hits)
    common = [(k, n) for k, n in counts.most_common() if n >= 3 and float(k[0]) >= 10]
    if not common:
        return Skip("T07", "no dose value is repeated at least 3 times")
    v = common[0][0][0]
    same = [h for h in hits if h.token == v]
    h = _choose_keeping_one(ctx, same)
    if not h:
        return Skip("T07", "no free dose mention")
    new = str(int(float(v) * 1.25)) if float(v).is_integer() else f"{float(v) * 1.25:.1f}"
    ctx.replace(h, new)
    return error("T07", h, new, f"Dose {v} changed to {new} in one place only", [x.page for x in same if x is not h])


def t08_sample_size(ctx: Ctx):
    pat = r"(?:approximately|up to|total of|enroll(?:ed)?|randomi[sz]ed)\s+(\d{2,4})\s+(?:subjects|patients|participants)"
    hits = find(ctx, pat)
    vals = Counter(h.token for h in hits)
    if not vals or vals.most_common(1)[0][1] < 2:
        return Skip("T08", "sample size is stated only once")
    v = vals.most_common(1)[0][0]
    same = [h for h in hits if h.token == v]
    h = _choose_keeping_one(ctx, same)
    if not h:
        return Skip("T08", "no free sample-size mention")
    new = str(int(v) + max(10, int(v) // 5))
    ctx.replace(h, new)
    return error("T08", h, new, f"Sample size {v} changed to {new} in one place only", [x.page for x in same if x is not h])


def t10_ratio(ctx: Ctx):
    hits = find(ctx, r"(?<![\d:])(\d:\d)(?![\d:])")
    vals = Counter(h.token for h in hits)
    if not vals or vals.most_common(1)[0][1] < 2:
        return Skip("T10", "no randomisation ratio is stated twice")
    v = vals.most_common(1)[0][0]
    same = [h for h in hits if h.token == v]
    h = _choose_keeping_one(ctx, same)
    if not h:
        return Skip("T10", "no free ratio mention")
    new = "2:1" if v == "1:1" else "1:1"
    ctx.replace(h, new)
    return error("T10", h, new, f"Ratio {v} changed to {new} in one place only", [x.page for x in same if x is not h])


def t14_xref(ctx: Ctx):
    hits = find(ctx, r"[Ss]ection\s+(\d{1,2}(?:\.\d{1,2}){1,3})\b", pages=range(8, min(len(ctx.doc), 80) + 1))
    # in-text references only: not table rows / TOC entries such as "Section 7.2.1 Inclusion Criteria"
    hits = [h for h in hits if not re.search(r"\.{4,}", h.line) and not h.line.lstrip().lower().startswith("section")
            and re.search(r"\b(see|refer(?:red)? to|per|in|of|under|described|detailed|outlined|\()\W*(?:also\W+)?Section", h.line, re.I)]
    h = _choose(ctx, hits)
    if not h:
        return Skip("T14", "no in-text section cross-reference found")
    new = "99." + ".".join(h.token.split(".")[1:])
    ctx.replace(h, new)
    return error("T14", h, new, f"Reference to Section {h.token} changed to nonexistent Section {new}")


def t16_windows(ctx: Ctx):
    hits = find(ctx, r"[±\u00b1]\s?(\d+)\s?(?:d\b|days\b)", pages=range(1, min(len(ctx.doc), 40) + 1))
    by_page: dict[int, list[Hit]] = {}
    for h in hits:
        by_page.setdefault(h.page, []).append(h)
    for _pno, hs in sorted(by_page.items(), key=lambda kv: -len(kv[1])):
        rows: dict[int, list[Hit]] = {}
        for h in hs:
            rows.setdefault(round(h.rect.y0 / 4), []).append(h)  # same table row = same y band
        row = max(rows.values(), key=len)
        if len(row) >= 3:
            row = sorted(row, key=lambda h: h.rect.x0)[:3]
            if not all(ctx.free(h.page, h.rect) for h in row):
                continue
            news = [str(max(int(h.token) * 3, 9)) for h in row]
            for h, n in zip(row, news, strict=True):
                ctx.replace(h, n)
            e = error("T16", row[0], news[0], f"Visit windows widened to +/-{news[0]} days on three adjacent visits",
                      None)
            e["match"]["texts"] = [short(h, n) for h, n in zip(row, news, strict=True)]
            return e
    return Skip("T16", "no row of at least 3 visit windows found")


def t17_duration(ctx: Ctx):
    hits = find(ctx, r"(?:for|up to|approximately|of)\s+(\d+)\s+(?:weeks|months)", pages=range(1, 25))
    cand = [h for h in hits if re.search(r"follow|treatment|duration|participation|study", h.line, re.I)]
    if len({h.token for h in hits}) < 1 or len(hits) < 2:
        return Skip("T17", "durations are not stated at least twice")
    h = _choose(ctx, cand or hits)
    if not h:
        return Skip("T17", "no free duration mention")
    new = str(int(h.token) + (12 if "week" in h.line[h.start:h.start + 20] else 6))
    ctx.replace(h, new)
    return error("T17", h, new, f"Duration {h.token} changed to {new} in one place; total no longer adds up",
                 [x.page for x in hits if x is not h])


def t09_power(ctx: Ctx):
    hits = find(ctx, r"(\d{2})\s?%\s*(?:statistical\s*)?power") + find(ctx, r"power of\s*(\d{2})\s?%")
    hits = [h for h in hits if ctx.free(h.page, h.rect)]
    if not hits:
        return Skip("T09", "no stated power")
    v = int(hits[0].token)
    new = "80" if v >= 90 else "95"
    for h in hits:  # every mention, so the document stays self-consistent and only the recomputation breaks
        ctx.replace(h, new)
    e = error("T09", hits[0], new, f"Stated power changed {v}% -> {new}% everywhere, so N is no longer reproducible")
    e["match"]["pages"] = sorted({h.page for h in hits})
    return e


def t13_lab(ctx: Ctx):
    pat = (r"\b(ANC|neutrophil[s]?(?: count)?|platelets?(?: count)?|h(?:a)?emoglobin|creatinine|bilirubin|AST|ALT)\b"
           r"[^.\n]{0,40}?(?:[≥≤<>]|>=|<=)\s*([\d.,]+)")
    hits = find(ctx, pat, 2)
    hits = [h for h in hits if re.fullmatch(r"\d[\d.,]*\d|\d", h.token)]
    names = Counter(re.search(pat, h.line, re.I).group(1).lower().split()[0] for h in hits)
    if not names or names.most_common(1)[0][1] < 2:
        return Skip("T13", "no lab threshold stated at least twice")
    h = _choose(ctx, hits)
    if not h:
        return Skip("T13", "no free lab threshold")
    try:
        new = str(int(float(h.token.replace(",", "")) * 2)) if "." not in h.token else f"{float(h.token) * 2:.1f}"
    except ValueError:
        return Skip("T13", "unparseable threshold")
    ctx.replace(h, new)
    return error("T13", h, new, f"Lab threshold {h.token} changed to {new} in one place only")


def t02_timepoint(ctx: Ctx):
    hits = find(ctx, r"(?:Week|Day|Month)\s+(\d+)", pages=range(1, 20))
    prim = [h for h in hits if re.search(r"primary|endpoint|ORR|response|survival", h.line, re.I)]
    counts = Counter(h.token for h in find(ctx, r"(?:Week|Day|Month)\s+(\d+)"))
    cand = [h for h in prim if counts[h.token] >= 3]
    h = _choose(ctx, cand)
    if not h:
        return Skip("T02", "no endpoint timepoint repeated across sections")
    new = str(int(h.token) + 2)
    ctx.replace(h, new)
    return error("T02", h, new, f"Endpoint timepoint {h.token} -> {new} in one place only")


def t18_registry(ctx: Ctx):
    reg = ((ctx.registry or {}).get("protocolSection", {}).get("eligibilityModule", {}))
    m = re.match(r"(\d+)\s*Years?", reg.get("minimumAge", "") or "")
    if not m:
        return Skip("T18", "no registry minimum age cached for this study")
    hits = [h for h in _age_hits(ctx) if h.token == m.group(1)]
    if not hits or len({h.token for h in _age_hits(ctx)}) != 1:
        return Skip("T18", f"protocol age mentions do not all equal the registry value {m.group(1)}")
    hits = [h for h in hits if ctx.free(h.page, h.rect)]
    if not hits:
        return Skip("T18", "age mentions overlap other injections")
    new = str(int(m.group(1)) + 3)
    for h in hits:
        ctx.replace(h, new)
    e = error("T18", hits[0], new, f"Minimum age changed {m.group(1)} -> {new} everywhere; registry still says {m.group(1)}")
    e["match"]["pages"] = sorted({h.page for h in hits})
    return e


# --------------------------------------------------------------------------------------------- deletion types
UNBLIND = re.compile(r"unblind|break(?:ing)? (?:the )?blind|randomi[sz]ation code|code[- ]break|emergency (?:code|unblinding)", re.I)


def t11_blinding(ctx: Ctx):
    text = " ".join(pg.get_text() for pg in ctx.doc)
    if not re.search(r"double[- ]blind", text, re.I):
        return Skip("T11", "protocol is not double-blind")
    lines = [(p, ln) for p in range(1, len(ctx.doc) + 1) for ln in ctx.lines(p)
             if UNBLIND.search(ln["text"]) and not re.search(r"\.{4,}|\s\d+\s*$", ln["text"])]
    lines = [(p, ln) for p, ln in lines if ctx.free(p, ln["rect"])]
    if len(lines) < 2:
        return Skip("T11", "fewer than 2 blinding/unblinding lines to remove")
    for p, ln in lines:
        ctx.whiteout(p, ln["rect"])
    first = lines[0]
    h = Hit(first[0], first[1]["text"], "", 0, first[1]["rect"], 0, first[1]["rect"])
    e = error("T11", h, "(removed)", f"Removed {len(lines)} lines about unblinding / randomisation codes")
    e["original"] = first[1]["text"][:80]
    e["match"] = {"pages": sorted({p for p, _ in lines}), "texts": [], "titles": ["unblinding procedure", "unblind"]}
    return e


REMOVABLE = ["10.11", "11.4", "10.9", "11.10", "11.6", "7.3", "4.3", "11.12", "11.5", "5.6", "11.8"]


def _norm(t: str) -> str:
    return re.sub(r"\W+", " ", t).lower().strip()


def _heading_at(lines: list, sec, k0: int = 0) -> int | None:
    """Index of a section heading's first line; headings may be split over two lines ('5.1.1.' / 'Study Stopping Rules')."""
    want = _norm(re.sub(r"^[\d.]+\s*", "", sec.title))[:30]
    for k in range(k0, len(lines)):
        p, ln = lines[k]
        if p == sec.page_start and want and want in _norm(ln["text"]):
            return k - 1 if k > k0 and re.fullmatch(r"[\d.\s]+", lines[k - 1][1]["text"]) else k
    return None


def t15_section(ctx: Ctx):
    if ctx.sections is None:
        return Skip("T15", "section map unavailable")
    secs = ctx.sections
    for mid in REMOVABLE:
        for i, s in enumerate(secs):
            if s.m11_id != mid or len(s.text.split()) < 30 or s.page_end - s.page_start > 2:
                continue
            nxt = next((n for n in secs[i + 1:] if n.level <= s.level), None)
            lines = [(p, ln) for p in range(s.page_start, s.page_end + 1) for ln in ctx.lines(p)]
            start = _heading_at(lines, s)
            if start is None:
                continue
            end = len(lines)
            if nxt and nxt.page_start <= s.page_end:
                end = _heading_at(lines, nxt, start + 1) or len(lines)
            span = [(p, ln) for p, ln in lines[start:end] if ctx.free(p, ln["rect"])]
            if len(span) < 2:
                continue
            for p, ln in span:
                ctx.whiteout(p, ln["rect"])
            h = Hit(s.page_start, span[0][1]["text"], "", 0, span[0][1]["rect"], 0, span[0][1]["rect"])
            e = error("T15", h, "(removed)", f"Removed M11 {mid} {s.title} ({len(span)} lines)")
            e["original"] = s.title
            e["m11_id"] = mid
            e["match"] = {"pages": sorted({p for p, _ in span}), "texts": [], "titles": [f"M11 {mid} "]}
            return e
    return Skip("T15", "no removable M11 section of at most 2 pages found")


# --------------------------------------------------------------------------------- graph-driven types
def _span_hit(page: int, bbox: list[float], text: str) -> Hit:
    r = Rect(bbox)
    return Hit(page, text, "", 0, r, 0, r)


def _secondary_endpoint_ids(g) -> set[str]:
    return {e for o in g.objectives if o.level == "secondary" for e in o.endpoint_ids}


def t04_endpoint_deleted(ctx: Ctx):
    g = ctx.graph
    if g is None:
        return Skip("T04", "needs the LLM-extracted objectives and endpoints (no LLM graph available)")
    eps = {e.id: e for e in g.endpoints}
    use = Counter(eid for o in g.objectives for eid in o.endpoint_ids)
    for o in g.objectives:
        if o.level != "secondary" or not o.endpoint_ids:
            continue
        chosen = [eps[e] for e in o.endpoint_ids if e in eps and use[e] == 1 and eps[e].span.bbox]
        if len(chosen) != len(o.endpoint_ids) or not all(ctx.free(e.span.page, Rect(e.span.bbox)) for e in chosen):
            continue
        for e in chosen:
            ctx.whiteout(e.span.page, Rect(e.span.bbox))
        first = chosen[0]
        h = _span_hit(first.span.page, first.span.bbox, first.span.quote)
        err = error("T04", h, "(removed)", f"Removed the endpoint text of secondary objective '{o.text[:60]}'")
        err["original"] = "; ".join(e.text[:60] for e in chosen)
        err["match"] = {"pages": sorted({o.span.page, *(e.span.page for e in chosen)}), "texts": [], "titles": ["objective has no endpoint"]}
        return err
    return Skip("T04", "no secondary objective whose endpoints are used only by it and have a located line")


def t05_analysis_deleted(ctx: Ctx):
    g = ctx.graph
    if g is None:
        return Skip("T05", "needs the LLM-extracted endpoint analyses (no LLM graph available)")
    sec = _secondary_endpoint_ids(g)
    by_ep: dict[str, list[dict]] = {}
    for a in g.stats.analyses:
        if a.get("endpoint_id") in sec and (a.get("span") or {}).get("bbox"):
            by_ep.setdefault(a["endpoint_id"], []).append(a)
    for eid, items in by_ep.items():
        rects = [(a["span"]["page"], Rect(a["span"]["bbox"])) for a in items]
        if not all(ctx.free(p, r) for p, r in rects):
            continue
        for p, r in rects:
            ctx.whiteout(p, r)
        ep = next(e for e in g.endpoints if e.id == eid)
        h = _span_hit(rects[0][0], list(rects[0][1]), items[0]["span"].get("quote", ""))
        err = error("T05", h, "(removed)", f"Removed the analysis of secondary endpoint '{ep.measure}' ({len(rects)} line(s))")
        err["original"] = "; ".join((a.get("method") or "")[:40] for a in items)
        err["match"] = {"pages": sorted({p for p, _ in rects} | {ep.span.page}), "texts": [], "titles": ["no analysis method"]}
        return err
    return Skip("T05", "no secondary endpoint with a located analysis")


def t12_contradiction(ctx: Ctx):
    g = ctx.graph
    if g is None:
        return Skip("T12", "needs the LLM-extracted eligibility criteria (no LLM graph available)")
    inc = [(c, t) for c in g.criteria if c.kind == "inclusion" for t in c.thresholds
           if isinstance(t.get("value"), (int, float)) and t.get("test") and t.get("op") in (">=", ">", "\u2265")]
    if not inc:
        return Skip("T12", "no inclusion criterion with a lower-bound threshold")
    excl = [c for c in g.criteria if c.kind == "exclusion" and c.span.bbox]
    for c, t in inc:
        v = float(t["value"]) * 0.8
        v = round(v) if v >= 5 else round(v, 1)  # natural-looking value: 9 not 9.6, 1200 not 1199.9
        new = f"{t['test'].capitalize()} at or above {v:g}{(' ' + t['unit']) if t.get('unit') else ''}."
        for e in excl:
            page, r = e.span.page, Rect(e.span.bbox)
            # the exclusion line must be a single renderable text line at least as long as the new text (no overflow)
            lines = [(i, ln) for i, ln in enumerate(ctx.lines(page)) if ln["rect"].intersects(r) and ctx.renderable(ln["text"])]
            if len(lines) != 1 or len(lines[0][1]["text"].strip()) < len(new) * 0.8 or not ctx.free(page, lines[0][1]["rect"]):
                continue
            idx, ln = lines[0]
            sp = max(ln["spans"], key=lambda x: len(x["text"]))
            off = ln["text"].index(sp["text"])
            h = Hit(page, ln["text"], sp["text"], off, Rect(sp["bbox"]), sp["size"], ln["rect"], idx)
            ctx.replace(h, new + " " * max(0, len(sp["text"]) - len(new)))
            err = error("T12", h, new, f"Exclusion criterion rewritten to contradict inclusion on {t['test']}")
            err["match"]["pages"] = sorted({page, c.span.page})
            return err
    return Skip("T12", "no exclusion line that can be rewritten faithfully")


INJECTORS = {
    "T02": t02_timepoint, "T06": t06_age, "T07": t07_dose, "T08": t08_sample_size, "T09": t09_power,
    "T10": t10_ratio, "T11": t11_blinding, "T13": t13_lab, "T14": t14_xref, "T15": t15_section,
    "T16": t16_windows, "T17": t17_duration, "T18": t18_registry,
    "T04": t04_endpoint_deleted, "T05": t05_analysis_deleted, "T12": t12_contradiction,
}
NOT_YET = {
    "T01": "endpoint timepoints are not extracted (timepoints_weeks is empty on the dev protocols), so the endpoint visit is unknown",
    "T03": "needs a synthesised SoA row with matching ruling lines; not implemented",
}


def _sections(pdf: str):
    """M11-mapped sections via A's ingest, heading-match only (no LLM, no event loop needed)."""
    from preflight.ingest.m11_map import load_toc, match
    from preflight.ingest.pdf import read_pdf
    from preflight.ingest.sections import split_sections

    toc = load_toc()
    return [s.model_copy(update={"m11_id": match(s, toc)}) for s, _ in split_sections(read_pdf(pdf))]


def inject_file(pdf: str, out_dir: str, seed: int, n_target: tuple[int, int] = (8, 12), registry: dict | None = None,
                types: list[str] | None = None, sections: list | None = None, max_per_type: int = 1, graph=None) -> dict:
    """Plant errors; write {nct}_s{seed}.pdf and its answer key JSON. Returns the key."""
    nct = Path(pdf).name.split("_")[0]
    rng = random.Random(f"{nct}:{seed}")
    doc = pymupdf.open(pdf)
    ctx = Ctx(doc, nct, rng, registry, sections if sections is not None else _sections(pdf), graph=graph)
    order = [t for t in (types or INJECTORS) for _ in range(max_per_type)]  # a type may repeat at a different site
    rng.shuffle(order)
    target = rng.randint(*n_target)
    errors, skipped = [], [{"type": t, "reason": r} for t, r in NOT_YET.items() if not types or t in types]
    for t in order:
        if len(errors) >= target:
            skipped.append({"type": t, "reason": "not sampled (target count reached)"})
            continue
        res = INJECTORS[t](ctx)
        if isinstance(res, Skip):
            if not any(x["type"] == t and x["reason"] == res.reason for x in skipped):
                skipped.append({"type": res.type, "reason": res.reason})
        else:
            res["error_id"] = f"{nct}-s{seed}-{len(errors) + 1:02d}"
            errors.append(res)
    for e in errors:
        _finalize(ctx, e)
    ctx.apply()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stem = f"{nct}_s{seed}"
    doc.save(out / f"{stem}.pdf", garbage=3, deflate=True, no_new_id=True)
    key = {"nct_id": nct, "seed": seed, "source_pdf": Path(pdf).name, "injected_pdf": f"{stem}.pdf",
           "target_errors": target, "errors": errors, "skipped": skipped, "touched": ctx.touched}
    (out / f"{stem}.json").write_text(json.dumps(key, indent=1, ensure_ascii=False))
    return key


def _finalize(ctx: Ctx, e: dict) -> None:
    """Describe the FINAL line (two injections can land on the same line) and refresh the quote hint from it."""
    page_idx, start = e.pop("_line"), e.pop("_start")
    if (page_idx not in ctx.subs) or e["new"] == "(removed)":
        return
    ln = ctx.lines(page_idx[0])[page_idx[1]]
    final = "".join(ctx._span_texts(ln, ctx.subs[page_idx]))
    shift = sum(len(n) - (b - a) for a, b, n in ctx.subs[page_idx] if a < start)
    s0 = start + shift
    e["new_line"] = re.sub(r"\s+", " ", final).strip()[:200]
    if e["type"] != "T16":
        pad = 14
        e["match"]["texts"] = [re.sub(r"\s+", " ", final[max(0, s0 - pad): s0 + len(e["new"]) + pad]).strip()]


def verify_key(pdf_path: str, key: dict, original: str | None = None) -> list[str]:
    """Re-read the injected PDF and confirm (1) each text change is really there and (2) with `original` given, that
    no OTHER line was lost: injection must not delete neighbouring text."""
    doc = pymupdf.open(pdf_path)
    problems = []
    for e in key["errors"]:
        if e["new"] == "(removed)":
            continue
        want = e.get("new_line") or e["new"]
        page_text = re.sub(r"\s+", " ", doc[e["page"] - 1].get_text())
        if unicodedata.normalize("NFKC", want) not in unicodedata.normalize("NFKC", page_text):
            problems.append(f"{e['error_id']} {e['type']}: '{want}' not found on page {e['page']}")
    if original and "touched" in key:
        orig = pymupdf.open(original)
        touched = {(p, t) for p, t in key["touched"]}
        for pno in sorted({p for p, _ in touched}):
            was = [_norm_line(t) for t in _page_line_texts(orig[pno - 1])]
            now = " ".join(_norm_line(t) for t in _page_line_texts(doc[pno - 1]))
            lost = [t for t in was if t and (pno, t) not in touched and t not in now]
            problems += [f"collateral loss on page {pno}: {t[:70]!r}" for t in lost]
    return problems


def _page_line_texts(page: pymupdf.Page) -> list[str]:
    return ["".join(s["text"] for s in ln["spans"]) for b in page.get_text("dict")["blocks"] for ln in b.get("lines", [])]
