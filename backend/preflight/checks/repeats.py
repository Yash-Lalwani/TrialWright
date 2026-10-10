import re

from rapidfuzz import fuzz

from preflight.checks.registry import CheckContext, check, issue, where
from preflight.graph.models import ProtocolGraph, Span

NUM = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?![\w.])")
LAB = re.compile(r"neutrophil|\banc\b|platelet|hemoglobin|haemoglobin|bilirubin|\balt\b|\bast\b|creatinine|uln|"
                 r"/mm3|10\^9|g/dl|mg/dl|µmol|umol|ml/min|inr|aptt|lymphocyte|leukocyte|wbc", re.I)
TIMEPOINT = re.compile(r"\b(week|day|month)s?\s+\d", re.I)
SKIP = re.compile(r"\bage\b|years old|years of age|\bmg\b|ratio", re.I)


def _template(text: str) -> str:
    return re.sub(r"[^a-z#]+", " ", NUM.sub("#", text.lower())).strip()


def _clauses(graph: ProtocolGraph):
    """(section, clause, numbers, key): clauses split on bullets, dashes, semicolons and sentence ends; the key is
    the clause template plus the template of the clause before it, so short lab clauses only match in context."""
    split = re.compile(r"(?:^|\s)[•−–-]\s|;\s|(?<=[.])\s+(?=[A-Z])")
    for s in graph.sections:
        sentences = [p.strip() for p in split.split(re.sub(r"\s+", " ", s.text)) if p.strip()]
        lines = [p.strip() for line in s.text.split("\n") for p in split.split(line) if p.strip()]
        for parts in (sentences, lines):
            yield from _keyed(s, parts)


def _keyed(s, parts: list[str]):
    for prev, cur in zip(["", *parts], parts, strict=False):
        nums = NUM.findall(cur)
        key = f"{_template(prev)[-60:]} | {_template(cur)}"
        if 1 <= len(nums) <= 2 and len(cur) < 300 and len(re.findall(r"[a-z]{3,}", key)) >= 4:
            yield s, cur, tuple(nums), key


@check(id="C8R", category="consistency", amendment_category="eligibility",
       standard_ref="ICH M11 1.1, 5; SPIRIT 2025 item 10", severity="major")
def repeated_statements_agree(graph: ProtocolGraph, ctx: CheckContext):
    """The same sentence stated in two places (synopsis vs body) with a different number: lab thresholds go to C8,
    endpoint timepoints to C4. Ages, doses, ratios and sample sizes are handled by C4 already."""
    cands = [(s, clause, nums, key) for s, clause, nums, key in _clauses(graph)
             if (LAB.search(clause) or TIMEPOINT.search(clause))
             and not (SKIP.search(clause) and not LAB.search(clause))]
    issues, seen = [], set()
    for i, (s1, a, n1, k1) in enumerate(cands):
        for s2, b, n2, k2 in cands[i + 1:]:
            if s1.id == s2.id or n1 == n2 or len(n1) != len(n2) or (k1, k2) in seen:
                continue
            if fuzz.token_sort_ratio(k1, k2) < 92:
                continue
            seen.add((k1, k2))
            span_a = Span(page=s1.page_start, bbox=None, quote=a[:200])
            span_b = Span(page=s2.page_start, bbox=None, quote=b[:200])
            check_id, what = ("C8", "Lab threshold") if LAB.search(a) else ("C4", "Timepoint")
            issues.append(issue(
                check_id, f"{what} disagrees between repeated statements: {', '.join(n2)} vs {', '.join(n1)}",
                where(graph, span_b, s2.title),
                f"The same statement appears in {s1.title} with {', '.join(n1)} and in {s2.title} with "
                f"{', '.join(n2)}.",
                fix="Make both statements use the same value.", related=[where(graph, span_a, s1.title)],
                severity="major", confidence=0.75))
    return issues
