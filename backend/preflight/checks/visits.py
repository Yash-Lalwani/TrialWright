from preflight.checks.registry import CheckContext, check, issue, where
from preflight.graph.models import ProtocolGraph


@check(id="C6", category="consistency", amendment_category="visit_schedule",
       standard_ref="ICH M11 1.3; SPIRIT 2025 item 13", severity="major")
def visit_windows(graph: ProtocolGraph, ctx: CheckContext):
    if not graph.soa:
        return []
    dated = sorted((v for v in graph.soa.visits if v.study_day is not None), key=lambda v: v.study_day)
    issues = []
    for a, b in zip(dated, dated[1:], strict=False):
        if a.study_day == b.study_day:
            continue
        a_end = a.study_day + (a.window_plus or 0)
        b_start = b.study_day - (b.window_minus or 0)
        if a_end >= b_start and (a.window_plus or b.window_minus):
            issues.append(issue(
                "C6", f"Visit windows overlap: {a.name} and {b.name}", where(graph, graph.soa.span),
                f"{a.name} (Day {a.study_day:g}, up to Day {a_end:g}) overlaps {b.name} "
                f"(Day {b.study_day:g}, from Day {b_start:g}). A visit on the overlap days can be counted as either.",
                fix=f"Narrow the windows so {a.name} ends before {b.name} begins."))
    return issues
