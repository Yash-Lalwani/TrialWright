# ruff: noqa: E501
"""Generate docs/RESULTS.md from the results JSON in data/bench/results. Numbers are copied, never typed by hand.

    python -m preflight.eval.report [--out docs/RESULTS.md]

Uses the TEST split when results for it exist, otherwise the dev split, and says which at the top. Anything not measured is listed
under "Not measured", never filled with a placeholder.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .bench import RESULTS_DIR, ROOT

CONFIG_ORDER = ("rules_only", "llm_only", "full")
NAMES = {"rules_only": "Rules only", "llm_only": "LLM only (one generic prompt)", "full": "Pre-Flight (rules + LLM + verifier)"}


def latest(split: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for p in sorted(RESULTS_DIR.glob(f"{split}_*.json")):
        d = json.loads(p.read_text())
        if "config" in d and "overall" in d:
            out[d["config"]] = d
    return out


def pick() -> tuple[str, dict[str, dict]]:
    for split in ("test", "dev"):
        r = latest(split)
        if r:
            return split, r
    raise SystemExit("no benchmark results in data/bench/results")


def pct(x: float | None) -> str:
    return "n/a" if x is None else f"{100 * x:.0f}%"


def render() -> str:
    split, res = pick()
    full = res.get("full") or next(iter(res.values()))
    L = ["# Protocol Pre-Flight: results", "",
         f"Generated from `data/bench/results` ({split} split, {full['test_set']['protocols']} protocols, {full['test_set']['injected_errors']} injected errors, seed(s) {full['seeds']}).", ""]
    if split == "dev":
        L += ["> **These are DEV-set numbers.** The rules were tuned on these three protocols, so they are optimistic. The seven test protocols have not been scored yet.", ""]
    L += ["## 1. Detection of injected errors (N1, N3)", "", "| Configuration | Recall | Precision | F1 | Flags per clean protocol (critical+major) |", "|---|---|---|---|---|"]
    for c in CONFIG_ORDER:
        if c in res:
            o = res[c]["overall"]
            L.append(f"| {NAMES[c]} | {pct(o['recall'])} | {pct(o['precision'])} | {o['f1']:.2f} | {res[c]['false_alarms_per_clean_protocol']} |")
    L += ["", "Flags on clean protocols are *unadjudicated*: some may be real problems in the original document. Nobody has labelled them yet (see Not measured).",
          "The LLM-only baseline is scored check-agnostically and strictly: a finding counts only if it is on an injected page AND quotes the edited line or names the new value.", ""]
    L += ["### By error type", "", "| Type | " + " | ".join(NAMES[c] for c in CONFIG_ORDER if c in res) + " |", "|---|" + "---|" * sum(c in res for c in CONFIG_ORDER)]
    types = sorted({r["type"] for d in res.values() for r in d["by_type"]})
    for t in types:
        cells = []
        for c in CONFIG_ORDER:
            if c in res:
                r = next((x for x in res[c]["by_type"] if x["type"] == t), None)
                cells.append("not injected" if r is None else f"{r['found']}/{r['n']}")
        name = next(r["name"] for d in res.values() for r in d["by_type"] if r["type"] == t)
        L.append(f"| {t} {name} | " + " | ".join(cells) + " |")
    L += ["", "T01 (endpoint visit removed) and T03 (orphan procedure) are not implemented as injectors; see the answer keys for why.", ""]
    if "full" in res:
        f = res["full"]
        L += ["## 2. Where the false alarms come from", "", "Pre-Flight, critical+major flags per clean protocol by check: " + ", ".join(f"`{k}` {v}" for k, v in f["clean_flags_by_check"].items()) + ".", ""]
        h = f.get("hallucination")
        if h:
            L += ["## 3. Grounding of AI findings (N4)", "", f"Pre-Flight: {h['ai_findings']} AI findings produced, {h['dropped_ungrounded']} dropped by the verifier as ungrounded, {h['shown']} shown, of which {h['shown_ungrounded']} had a quote not found on the cited page (checked independently of the verifier)."]
            o = res.get("llm_only", {}).get("hallucination")
            if o:
                L.append(f"LLM only (no verifier): {o['ai_findings']} findings, {o['shown_ungrounded']} ({pct(o['shown_ungrounded'] / o['ai_findings'])}) with a quote not on the cited page.")
            L.append("")
        s = f.get("speed_cost") or {}
        L += ["## 4. Speed and cost (N10)", "", f"Median {s.get('median_seconds')} s and ${s.get('median_usd')} per protocol, {s.get('measured')}" + (f" over {s['protocols']} protocols." if s.get("protocols") else ".")
              + " Cost is the provider-reported charge; the model and price are whatever `PREFLIGHT_MODEL` was at measurement time.", ""]
    cs = ROOT / "data" / "bench" / "case_studies.json"
    if cs.exists():
        d = json.loads(cs.read_text())
        L += ["## 5. Retrospective check on registry edits (N7)", "", d["population"], "", d["method"], "", "| Metric | Relaxed trials flagged before the edit | Other trials flagged | Odds ratio | One-sided Fisher p |", "|---|---|---|---|---|"]
        for m, r in d["result"].items():
            L.append(f"| {m} | {r['flagged_before_edit']}/{r['relaxed_trials']} | {r['other_flagged']}/{r['other_trials']} | {r.get('odds_ratio', 'n/a')} | {r.get('fisher_one_sided_p', 'n/a')} |")
        L += ["", "Caveats:", *[f"- {c}" for c in d["caveats"]], "", "Examples:", *[f"- {c['nct_id']}: {c['change']}. {c['summary']}" for c in d["case_studies"]], ""]
    L += ["## 6. Limitations", "",
          "- The corpus has 10 protocols; 3 dev, 7 test. Protocols were kept partly because their Schedule of Activities could be extracted, which favours the tool. Five candidates were dropped for that reason (`data/corpus/soa_assessment.json`).",
          "- Errors are injected by a script, not found in the wild. They test detection, not that real amendments look like them. Real amendment histories are not yet used (N7).",
          "- Absolute burden hours and dollars come from `data/assumptions/procedure_costs.csv`, every row of which is labelled `assumption`. Only relative burden against peers is meaningful. Recurring schedule columns are counted once, so totals are lower bounds.",
          "- Peer schedule percentiles exist only for peer sets we summarised, and only for peers whose schedule extracted plausibly; fewer than 8 such peers means no comparison.",
          "- Drafted protocol text (co-author) can contain general medical statements that are not in the brief. It is a draft for human review, and unsupported sections are left [TBD].",
          "- Pre-Flight assists a reviewer; it does not approve or reject a protocol.", "",
          "## 7. Not measured", "",
          "- Human baseline (N5): the kit exists; no participants were available.",
          "- Precision of real findings with a second labeller and kappa (N6) and false-alarm adjudication (N2).",
          "- Whole-pipeline retrospective test on earlier protocol PDFs: not possible, earlier versions of the PDFs are not posted. Section 5 tests only the peer-outlier signal on registry fields.",
          "- Schedule-of-Activities extraction accuracy against hand-labelled cells.", "",
          "## 8. Reproduce", "", "```", "preflight fetch                      # downloads the PDFs in data/corpus/manifest.csv",
          "python -m preflight.eval.cli bench --set dev --config rules_only --llm-graph",
          "python -m preflight.eval.cli bench --set dev --config full",
          "python -m preflight.eval.cli bench --set dev --config llm_only", "python -m preflight.eval.speed dev      # live timing and cost", "python -m preflight.eval.report", "```", ""]
    return "\n".join(L)


if __name__ == "__main__":
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else ROOT / "docs" / "RESULTS.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render())
    print(f"wrote {out}")
