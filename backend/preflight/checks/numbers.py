import re
from collections import Counter, defaultdict

from preflight.checks.registry import CheckContext, check, issue, where
from preflight.graph.models import NumberFact, ProtocolGraph

LABELS = {"age_min": "Minimum age", "age_max": "Maximum age", "sample_size": "Sample size",
          "ratio": "Randomization ratio", "arms": "Number of arms"}


def _per_arm(fact: NumberFact, total: float, n_arms: int | None) -> bool:
    if re.search(r"\b(arm|group|each|per)\b", fact.span.quote, re.I):
        return True
    return bool(n_arms) and abs(float(fact.value) * n_arms - total) < 1


@check(id="C4", category="consistency", amendment_category="clerical",
       standard_ref="ICH M11 1.1; SPIRIT 2025 items 10, 18", severity="major")
def numbers_agree(graph: ProtocolGraph, ctx: CheckContext):
    by_kind: dict[str, list[NumberFact]] = defaultdict(list)
    for f in graph.numbers:
        if f.kind in LABELS:
            by_kind[f.kind].append(f)

    issues = []
    for kind, facts in by_kind.items():
        if kind == "sample_size" and facts:
            total = Counter(float(f.value) for f in facts).most_common(1)[0][0]
            facts = [f for f in facts if float(f.value) == total or not _per_arm(f, total, graph.meta.n_arms)]
        counts = Counter(str(f.value) for f in facts)
        if len(counts) < 2:
            continue
        majority, _ = counts.most_common(1)[0]
        main = next(f for f in facts if str(f.value) == majority)
        for value in counts:
            if value == majority:
                continue
            odd = next(f for f in facts if str(f.value) == value)
            unit = f" {odd.unit}" if odd.unit else ""
            issues.append(issue(
                "C4", f"{LABELS[kind]} disagrees across sections: {value}{unit} vs {majority}{unit}",
                where(graph, odd.span),
                f"{LABELS[kind]} is stated as {majority}{unit} on page {main.span.page} "
                f"({counts[majority]} place(s)) but as {value}{unit} on page {odd.span.page}.",
                fix=f"Use one {LABELS[kind].lower()} throughout the protocol.",
                related=[where(graph, main.span)],
                severity="critical" if kind in ("sample_size", "ratio") else "major"))
    return issues
