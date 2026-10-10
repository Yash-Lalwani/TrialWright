import re
from collections import Counter

from preflight.checks.registry import CheckContext, check, issue, where
from preflight.graph.models import ProtocolGraph, Span

MAX_ABBR_ISSUES = 15


def _beyond_outline(target: str, numbers: set[str]) -> bool:
    """True when the section cannot exist: its parent is missing, or it is past the parent's last child.
    Missing headings in the middle of a detected range are not flagged (heading detection can miss them)."""
    if target in numbers or not re.fullmatch(r"\d+(\.\d+)*", target):
        return False
    parts = target.split(".")
    parent = ".".join(parts[:-1])
    if parent and parent not in numbers:
        return _beyond_outline(parent, numbers)
    if parent:
        siblings = [int(n.rsplit(".", 1)[1]) for n in numbers if n.count(".") == target.count(".")
                    and n.rsplit(".", 1)[0] == parent]
    else:
        siblings = [int(n) for n in numbers if "." not in n]
    return bool(siblings) and int(parts[-1]) > max(siblings)


@check(id="C9", category="consistency", amendment_category="clerical",
       standard_ref="ICH M11 general; SPIRIT 2025 item 1", severity="minor")
def xrefs_and_abbreviations(graph: ProtocolGraph, ctx: CheckContext):
    numbers = {m.group(1) for s in graph.sections if (m := re.match(r"^(\d+(?:\.\d+)*)\s", s.title))}
    appendices = [int(m.group(1)) for s in graph.sections if (m := re.match(r"^appendix\s+(\d+)", s.title, re.I))]
    issues = []
    reported = set()
    if numbers:
        for x in graph.xrefs:
            kind, target = x["target"].split(" ", 1)
            if kind == "Section":
                missing = _beyond_outline(target, numbers)
            else:
                missing = bool(appendices) and target.isdigit() and int(target) > max(appendices)
            if missing and x["target"] not in reported:
                reported.add(x["target"])
                issues.append(issue(
                    "C9", f"Cross-reference to {x['target']}, which does not exist", where(graph, Span(**x["span"])),
                    f"The text says '{x['text']}', but the protocol has no {x['target']}.",
                    fix=f"Point the reference at the correct section, or add {x['target']}."))

    defined = graph.abbreviations.get("defined", {})
    undefined = [a for a in graph.abbreviations.get("used", []) if a not in defined]
    if undefined:
        text = "\n".join(s.text for s in graph.sections)
        counts = Counter({a: len(re.findall(rf"\b{re.escape(a)}\b", text)) for a in undefined})
        for abbr, n in counts.most_common(MAX_ABBR_ISSUES):
            if n < 3:
                break
            first = next((s for s in graph.sections if re.search(rf"\b{re.escape(abbr)}\b", s.text)), None)
            line = next((ln for ln in first.text.split("\n") if re.search(rf"\b{re.escape(abbr)}\b", ln)), "")
            span = Span(page=first.page_start, bbox=None, quote=line.strip()[:200]) if first else None
            issues.append(issue(
                "C9", f"Abbreviation '{abbr}' is used {n} times but never defined", where(graph, span),
                f"'{abbr}' appears {n} times but is not in the list of abbreviations and is never spelled out.",
                fix=f"Define '{abbr}' at first use and add it to the list of abbreviations.",
                severity="advisory", confidence=0.8))
    return issues
