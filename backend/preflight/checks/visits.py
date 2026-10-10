import re
from collections import Counter, defaultdict

from preflight.checks.registry import CheckContext, check, issue, where
from preflight.graph.models import NumberFact, ProtocolGraph


@check(id="C6", category="consistency", amendment_category="visit_schedule",
       standard_ref="ICH M11 1.3; SPIRIT 2025 item 13", severity="major")
def visit_windows(graph: ProtocolGraph, ctx: CheckContext):
    if not graph.soa:
        return []
    dated = sorted((v for v in graph.soa.visits if v.study_day is not None), key=lambda v: v.study_day)
    pairs = []
    for a, b in zip(dated, dated[1:], strict=False):
        a_end = a.study_day + (a.window_plus or 0)
        b_start = b.study_day - (b.window_minus or 0)
        back_to_back = b.study_day - a.study_day <= 2  # e.g. W6D1 and W6D2 PK visits
        if a.study_day != b.study_day and a_end >= b_start and (a.window_plus or b.window_minus) and not back_to_back:
            pairs.append(f"{a.name} (Day {a.study_day:g}, to Day {a_end:g}) and {b.name} (Day {b.study_day:g}, "
                         f"from Day {b_start:g})")
    if not pairs:
        return []
    return [issue(
        "C6", f"Visit windows overlap for {len(pairs)} visit pair(s)", where(graph, graph.soa.span),
        "Windows overlap: " + "; ".join(pairs) + ". A visit on the overlap days can be counted as either visit.",
        fix="Narrow the windows so each visit ends before the next one begins.")]


STOP = {"of", "the", "a", "an", "after", "before", "from", "to", "for", "and", "or", "in", "on", "at", "up", "last",
        "first", "follow", "dose", "with", "will", "be"}
DURATION = re.compile(r"\b(\d+(?:\.\d+)?)\s*(week|month|year)s?\b((?:\s+[A-Za-z]+){1,4})", re.I)


@check(id="C6D", category="consistency", amendment_category="design",
       standard_ref="ICH M11 4.1, 4.4; SPIRIT 2025 item 13", severity="major")
def durations_agree(graph: ProtocolGraph, ctx: CheckContext):
    """The same duration phrase ('3 months after PFS primary analysis') stated with different numbers."""
    groups: dict[str, list[tuple[str, NumberFact]]] = defaultdict(list)
    seen = set()
    for f in graph.numbers:
        if f.kind != "duration_weeks" or (f.span.page, f.span.quote) in seen:
            continue
        seen.add((f.span.page, f.span.quote))
        for m in DURATION.finditer(f.span.quote):
            words = m.group(3).split()
            content = [w for w in words if w.lower() not in STOP]
            distinctive = len(content) >= 3 or any(re.fullmatch(r"[A-Z]{2,}", w) for w in words)
            if distinctive:
                groups[f"{m.group(2).lower()} {' '.join(words).lower()}"].append((m.group(1), f))
    issues = []
    for phrase, items in groups.items():
        counts = Counter(v for v, _ in items)
        if len(counts) < 2:
            continue
        (main_v, main_n), *rest = counts.most_common()
        main = next(f for v, f in items if v == main_v)
        for value, n in rest:
            odd = next(f for v, f in items if v == value)
            unit, words = phrase.split(" ", 1)
            issues.append(issue(
                "C6", f"Duration disagrees across sections: {value} vs {main_v} {unit}s {words}",
                where(graph, odd.span),
                f"'{main_v} {unit}s {words}' on page {main.span.page} but '{value} {unit}s {words}' on page "
                f"{odd.span.page}. Treatment, follow-up and total durations no longer add up.",
                fix="Use the same duration everywhere it is stated.", related=[where(graph, main.span)],
                severity="major" if main_n > n else "minor", confidence=0.8))
    return issues
