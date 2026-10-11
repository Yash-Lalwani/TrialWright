import re
from collections import Counter, defaultdict

from preflight.checks.registry import CheckContext, check, issue, where
from preflight.graph.models import NumberFact, ProtocolGraph

LABELS = {"age_min": "Minimum age", "age_max": "Maximum age", "sample_size": "Sample size",
          "ratio": "Randomization ratio", "arms": "Number of arms"}


def _per_arm(fact: NumberFact, total: float, n_arms: int | None) -> bool:
    """A per-arm count: the number itself is followed or preceded by arm/group wording."""
    m = re.search(rf"(?<![\d.]){float(fact.value):g}\b", fact.span.quote)
    if m:
        after = fact.span.quote[m.end():m.end() + 40]
        before = fact.span.quote[max(0, m.start() - 25):m.start()]
        if re.match(r"\s*(participants|patients|subjects)?\s*(per|in each|in the|each)\s+(arm|group|treatment)", after,
                    re.I) or re.search(r"(arm [a-z0-9]+\s*:|each arm|per arm)\s*(approximately\s*)?$", before, re.I):
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
            totals = [f for f in facts if not _per_arm(f, -1, None)] or facts  # pick the total from non-arm counts
            total = Counter(float(f.value) for f in totals).most_common(1)[0][0]
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


DRUG = re.compile(r"\b([A-Za-z]+(?:mab|nib|tinib|platin|taxel|rubicin|parib|ciclib|lisib|olimod|cept|zomib|tide)"
                  r"|[A-Z]{2,5}[- ]?\d{2,5}[A-Za-z]?)\b")
NOT_DOSE = re.compile(r"loading|reduc|escalat|level|up to|maximum|max\.|cumulative|starting|step|total|minimum|"
                      r"from|to\s*$|or\s*$", re.I)
NOT_DOSE_LINE = re.compile(r"weight|\bkg\b|adolescent|child|pediatric|paediatric|dose levels?|cohort|tolerated", re.I)


def _dose_key(fact: NumberFact) -> tuple | None:
    """(drug, unit, kind) for a dose of a named drug; kind is 'loading' or 'dose'. None when not a plain dose."""
    q = fact.span.quote
    m = re.search(rf"(?<![\d.]){float(fact.value):g}\s*{re.escape(fact.unit or '')}", q)
    if not m:
        return None
    before, after = q[:m.start()], q[m.end():m.end() + 20]
    loading = bool(re.search(r"loading dose (of )?\s*$", before[-25:], re.I))
    doses_in_line = len(re.findall(rf"\d+(?:\.\d+)?\s*{re.escape(fact.unit or 'mg')}\b", q))
    if NOT_DOSE_LINE.search(q) or re.match(r"\s*(to|-|–)\s", after):
        return None
    if not loading and (NOT_DOSE.search(before[-30:]) or doses_in_line > 2):
        return None
    window = before[-70:] if loading else before[-40:]
    drugs = list(DRUG.finditer(window))
    gap = window[drugs[-1].end():] if drugs else ""
    if drugs and (loading or not re.search(r"[,;(]| with |\d\s*(mg|g|mcg|µg)\b", gap)):
        drug = drugs[-1].group(1)  # 'alectinib administered orally at 600 mg'
    elif m2 := DRUG.match(q[m.end():m.end() + 25].lstrip(" ,")):
        drug = m2.group(1)  # '400 mg pralsetinib'
    else:
        return None  # e.g. 'CMP-001, prophylaxis with prednisone 25 mg'
    return drug.lower().replace(" ", ""), (fact.unit or "").lower(), "loading" if loading else "dose"


@check(id="C4D", category="consistency", amendment_category="intervention",
       standard_ref="ICH M11 6.1, 6.3; SPIRIT 2025 item 15", severity="major")
def doses_agree(graph: ProtocolGraph, ctx: CheckContext):
    groups: dict[tuple, list[NumberFact]] = defaultdict(list)
    for f in graph.numbers:
        if f.kind == "dose" and (key := _dose_key(f)):
            groups[key].append(f)
    issues = []
    for (drug, unit, kind), facts in groups.items():
        counts = Counter(float(f.value) for f in facts)
        if len(counts) < 2:
            continue
        (main_v, main_n), *rest = counts.most_common()
        main = next(f for f in facts if float(f.value) == main_v)
        for value, n in rest:
            odd = next(f for f in facts if float(f.value) == value)
            label = f"{drug} loading dose" if kind == "loading" else f"{drug} dose"
            issues.append(issue(
                "C4", f"{label.capitalize()} disagrees across sections: {value:g} {unit} vs {main_v:g} {unit}",
                where(graph, odd.span),
                f"The {label} is {main_v:g} {unit} on page {main.span.page} ({main_n} place(s)) but {value:g} {unit} "
                f"on page {odd.span.page}.",
                fix=f"State one {drug} dose throughout, or label the different dose levels explicitly.",
                related=[where(graph, main.span)], severity="major" if main_n > n else "minor", confidence=0.8))
    return issues
