import re
from pathlib import Path

import yaml
from pydantic import BaseModel

from preflight.checks.registry import CheckContext, check, issue
from preflight.graph.issues import Where
from preflight.graph.models import ProtocolGraph, Section
from preflight.ingest.m11_map import load_toc

SPIRIT_PATH = Path(__file__).resolve().parents[3] / "data" / "standards" / "spirit2025.yaml"
WORD_FLOOR = 40
# Used while the M11 YAML has no 'required' flags: the items every interventional protocol needs.
STUB_REQUIRED = {"1", "1.1", "1.3", "2", "3", "4", "4.1", "5", "5.2", "5.3", "6", "7", "8", "9", "10", "10.11", "11"}


class CompletenessItem(BaseModel):
    framework: str
    item_id: str
    title: str
    status: str
    pages: list[int]
    note: str | None


class CompletenessSummary(BaseModel):
    present: int
    thin: int
    missing: int
    required: int


class Completeness(BaseModel):
    summary: CompletenessSummary
    items: list[CompletenessItem]


def _with_children(sections: list[Section], i: int) -> list[Section]:
    out = [sections[i]]
    for s in sections[i + 1:]:
        if s.level <= sections[i].level:
            break
        out.append(s)
    return out


def _patterns(item: dict) -> list[tuple[str, str]]:
    """(label, regex) for each required sub-element; plain strings are treated as keywords."""
    out = []
    for sub in item.get("sub_elements", []) or []:
        if isinstance(sub, str):
            out.append((sub, re.escape(sub)))
        else:
            name = sub.get("name") or sub.get("id") or "sub-element"
            pats = sub.get("patterns") or sub.get("keywords") or [name]
            out.append((name, "|".join(pats if sub.get("patterns") else map(re.escape, pats))))
    return out


def _status(text: str, item: dict) -> tuple[str, str | None]:
    missing = [label for label, pat in _patterns(item) if not re.search(pat, text, re.I)]
    if missing:
        return "thin", f"Missing: {', '.join(missing)}"
    floor = item.get("word_floor", WORD_FLOOR)
    if len(text.split()) < floor:
        return "thin", f"Under {floor} words"
    return "present", None


def _covered(graph: ProtocolGraph, item_id: str) -> list[Section]:
    """Sections mapped to the item or to any item below it, with their child sections."""
    hits = [i for i, s in enumerate(graph.sections)
            if s.m11_id == item_id or (s.m11_id or "").startswith(item_id + ".")]
    return [s for i in hits for s in _with_children(graph.sections, i)]


def _found_in(sections: list[Section], item: dict, by_name_only: bool) -> Section | None:
    """First section whose text names the item (title or synonym) or, inside its parent, has all its patterns."""
    names = [item["title"], *(item.get("synonyms") or [])]
    name_re = "|".join(re.escape(n.lower()) for n in names if len(n) > 4)
    patterns = [pat for _, pat in _patterns(item)]
    for s in sections:
        low = f"{s.title}\n{s.text}".lower()
        if name_re and re.search(name_re, low):
            return s
        if not by_name_only and patterns and all(re.search(p, low, re.I) for p in patterns):
            return s
    return None


def _m11_items(graph: ProtocolGraph) -> list[CompletenessItem]:
    toc = load_toc()
    has_flags = any("required" in i for i in toc)
    items = []
    for item in toc:
        if not (item.get("required") if has_flags else item["id"] in STUB_REQUIRED):
            continue

        def add(status, pages=(), note=None, item=item):
            items.append(CompletenessItem(framework="M11", item_id=item["id"], title=item["title"], status=status,
                                          pages=sorted(set(pages))[:20], note=note))

        if item["id"] == "1.3" and graph.soa and graph.soa.span:
            add("present", [graph.soa.span.page])
            continue
        covered = _covered(graph, item["id"])
        if covered:
            status, note = _status("\n".join(s.text for s in covered), item)
            add(status, [p for s in covered for p in range(s.page_start, s.page_end + 1)], note)
            continue
        # No heading for this item: look for its content inside the nearest present ancestor (pre-M11 protocols
        # rarely have a heading per sub-item), or by name anywhere in the document.
        parts = item["id"].split(".")
        scope = next((c for k in range(len(parts) - 1, 0, -1) if (c := _covered(graph, ".".join(parts[:k])))), None)
        hit = _found_in(scope, item, by_name_only=False) if scope else None
        hit = hit or _found_in(graph.sections, item, by_name_only=True)
        if hit is None:
            add("missing")
            continue
        status, note = _status(hit.text, item)
        where = f"No own section; covered in {hit.title}"
        add(status, range(hit.page_start, hit.page_end + 1), f"{where}. {note}" if note else where)
    return items


def _spirit_items(graph: ProtocolGraph) -> list[CompletenessItem]:
    if not SPIRIT_PATH.exists():
        return []
    data = yaml.safe_load(SPIRIT_PATH.read_text())
    items = []
    for item in data["items"] if isinstance(data, dict) else data:
        if item.get("required") is False:
            continue
        pats = item.get("patterns") or item.get("keywords") or [item["title"]]
        regex = "|".join(pats) if item.get("patterns") else "|".join(map(re.escape, pats))
        hits = [s for s in graph.sections if re.search(regex, f"{s.title}\n{s.text}", re.I)]
        if not hits:
            items.append(CompletenessItem(framework="SPIRIT", item_id=str(item["id"]), title=item["title"],
                                          status="missing", pages=[], note=None))
            continue
        status, note = _status("\n".join(s.text for s in hits), {**item, "word_floor": item.get("word_floor", 0)})
        pages = sorted({s.page_start for s in hits})
        items.append(CompletenessItem(framework="SPIRIT", item_id=str(item["id"]), title=item["title"],
                                      status=status, pages=pages[:20], note=note))
    return items


def compute_completeness(graph: ProtocolGraph) -> Completeness:
    items = _m11_items(graph) + _spirit_items(graph)
    count = {s: sum(i.status == s for i in items) for s in ("present", "thin", "missing")}
    return Completeness(summary=CompletenessSummary(**count, required=len(items)), items=items)


def _issues(graph: ProtocolGraph, framework: str, check_id: str):
    issues = []
    for item in compute_completeness(graph).items:
        if item.framework != framework or item.status == "present":
            continue
        page = item.pages[0] if item.pages else None
        at = Where(section=f"{item.item_id} {item.title}", page=page, bbox=None, quote=None)
        if item.status == "missing":
            issues.append(issue(check_id, f"{framework} {item.item_id} {item.title} is missing", at,
                                f"The protocol has no section or content for {framework} item {item.item_id} "
                                f"({item.title}).", fix=f"Add {item.title}."))
        else:
            issues.append(issue("B3", f"{framework} {item.item_id} {item.title} is thin", at,
                                f"{item.title} is present but incomplete. {item.note}.",
                                fix=f"Complete {item.title}: {item.note}."))
    return issues


@check(id="B1", category="completeness", amendment_category="completeness", standard_ref="ICH M11 template",
       severity="major")
def m11_completeness(graph: ProtocolGraph, ctx: CheckContext):
    return _issues(graph, "M11", "B1")


@check(id="B2", category="completeness", amendment_category="completeness", standard_ref="SPIRIT 2025",
       severity="major")
def spirit_completeness(graph: ProtocolGraph, ctx: CheckContext):
    return _issues(graph, "SPIRIT", "B2")


@check(id="B3", category="completeness", amendment_category="completeness",
       standard_ref="ICH M11 template; SPIRIT 2025", severity="minor")
def thin_sections(graph: ProtocolGraph, ctx: CheckContext):
    return []  # thin items are reported by B1 and B2 under check id B3
