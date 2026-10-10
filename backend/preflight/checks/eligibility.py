import re

import pint

from preflight.checks.registry import CheckContext, check, issue, where
from preflight.graph.models import Criterion, ProtocolGraph

ureg = pint.UnitRegistry()
ureg.define("ULN = [uln]")
ureg.define("x_ULN = ULN")


def _unit(unit: str | None):
    if not unit:
        return None
    u = unit.replace("10^9", "1e9").replace("×", "*").replace("x ULN", "ULN").replace("µ", "u").strip()
    u = re.sub(r"^\*\s*", "", u)
    try:
        return ureg.parse_expression(u)
    except Exception:
        return None


def _to(value: float, unit: str | None, target: str | None) -> float | None:
    """Value converted into the target unit, or None when the units are not comparable."""
    if (unit or "") == (target or ""):
        return value
    src, dst = _unit(unit), _unit(target)
    if src is None or dst is None:
        return None
    try:
        return float((value * src).to(dst.units).magnitude / dst.magnitude)
    except Exception:
        return None


def _interval(op: str, value: float) -> tuple[float, float]:
    inf = float("inf")
    return {">=": (value, inf), ">": (value, inf), "≥": (value, inf),
            "<=": (-inf, value), "<": (-inf, value), "≤": (-inf, value)}.get(op, (value, value))


def _test_key(test: str) -> str:
    return re.sub(r"[^a-z0-9]", "", test.lower())


@check(id="C8", category="consistency", amendment_category="eligibility",
       standard_ref="ICH M11 5.1, 5.2; SPIRIT 2025 item 10", severity="major")
def eligibility_conflicts(graph: ProtocolGraph, ctx: CheckContext):
    rows: list[tuple[Criterion, dict]] = [(c, t) for c in graph.criteria for t in c.thresholds
                                          if isinstance(t.get("value"), (int, float)) and t.get("test")]
    issues = []
    seen = set()
    for i, (c1, t1) in enumerate(rows):
        for c2, t2 in rows[i + 1:]:
            if c1.id == c2.id or _test_key(t1["test"]) != _test_key(t2["test"]):
                continue
            pair = tuple(sorted((c1.id, c2.id)))
            if pair in seen:
                continue
            v2 = _to(float(t2["value"]), t2.get("unit"), t1.get("unit"))
            test = t1["test"]
            if v2 is None:
                seen.add(pair)
                issues.append(issue(
                    "C8", f"{test} uses different units in two criteria", where(graph, c1.span),
                    f"{test} is given in {t1.get('unit')} in {c1.id} and in {t2.get('unit')} in {c2.id}; the "
                    f"thresholds cannot be compared and sites may apply the wrong limit.",
                    fix=f"State {test} in one unit in every criterion.", related=[where(graph, c2.span)],
                    severity="minor"))
                continue
            a = _interval(t1["op"], float(t1["value"]))
            b = _interval(t2["op"], v2)
            if c1.kind == c2.kind == "inclusion" and a != b and (a[0] == -float("inf")) == (b[0] == -float("inf")):
                seen.add(pair)
                issues.append(issue(
                    "C8", f"Two inclusion criteria set different {test} thresholds", where(graph, c1.span),
                    f"{c1.id} requires {test} {t1['op']} {t1['value']} {t1.get('unit') or ''} but {c2.id} requires "
                    f"{test} {t2['op']} {t2['value']} {t2.get('unit') or ''}.",
                    fix=f"Keep one {test} threshold.", related=[where(graph, c2.span)]))
            elif {c1.kind, c2.kind} == {"inclusion", "exclusion"}:
                inc, exc = (a, b) if c1.kind == "inclusion" else (b, a)
                lo, hi = max(inc[0], exc[0]), min(inc[1], exc[1])
                if lo < hi:
                    seen.add(pair)
                    issues.append(issue(
                        "C8", f"Inclusion and exclusion criteria conflict on {test}", where(graph, c1.span),
                        f"Patients with {test} between {lo:g} and {hi:g} {t1.get('unit') or ''} meet inclusion "
                        f"criterion {c1.id if c1.kind == 'inclusion' else c2.id} and are also excluded by "
                        f"{c2.id if c2.kind == 'exclusion' else c1.id}.",
                        fix=f"Align the {test} thresholds so the inclusion and exclusion ranges do not overlap.",
                        related=[where(graph, c2.span)], severity="critical"))
    return issues
