import importlib
import logging
import pkgutil
from dataclasses import dataclass, field
from collections.abc import Callable

from preflight.graph.issues import Fix, Issue, Where, Why
from preflight.graph.models import ProtocolGraph, Span


@dataclass
class CheckContext:
    registry_record: dict | None = None
    peers: "PeerSet | None" = None  # noqa: F821  (B's burden.PeerSet)
    settings: dict = field(default_factory=dict)


@dataclass
class CheckSpec:
    id: str
    category: str
    amendment_category: str
    standard_ref: str
    severity: str
    fn: Callable[[ProtocolGraph, CheckContext], list[Issue]]


CHECKS: dict[str, CheckSpec] = {}
log = logging.getLogger(__name__)


def check(id: str, category: str, amendment_category: str, standard_ref: str, severity: str):
    def register(fn):
        CHECKS[id] = CheckSpec(id, category, amendment_category, standard_ref, severity, fn)
        return fn

    return register


def section_title(graph: ProtocolGraph, page: int | None) -> str | None:
    """Deepest section whose page range covers the page."""
    if page is None:
        return None
    hits = [s for s in graph.sections if s.page_start <= page <= s.page_end]
    return max(hits, key=lambda s: (s.level, s.page_start)).title if hits else None


def where(graph: ProtocolGraph, span: Span | None, section: str | None = None) -> Where:
    if span is None:
        return Where(section=section, page=None, bbox=None, quote=None)
    return Where(section=section or section_title(graph, span.page), page=span.page, bbox=span.bbox, quote=span.quote)


def issue(check_id: str, title: str, at: Where, explanation: str, fix: str | None = None,
          related: list[Where] | None = None, severity: str | None = None, patch: dict | None = None,
          confidence: float = 1.0) -> Issue:
    spec = CHECKS[check_id]
    return Issue(
        id="", check_id=check_id, source="rule", category=spec.category, severity=severity or spec.severity,
        title=title, where=at, related=related or [],
        why=Why(explanation=explanation, standard_ref=spec.standard_ref, amendment_category=spec.amendment_category),
        fix=Fix(suggestion=fix, patch=patch) if fix else None, confidence=confidence, verified=True,
    )


def discover() -> dict[str, CheckSpec]:
    import preflight.checks as pkg

    for mod in pkgutil.iter_modules(pkg.__path__):
        importlib.import_module(f"preflight.checks.{mod.name}")
    return CHECKS


def run_checks(graph: ProtocolGraph, ctx: CheckContext) -> list[Issue]:
    """Run every registered check; a check that crashes is logged and skipped so the run still completes."""
    issues = []
    for spec in discover().values():
        try:
            issues.extend(spec.fn(graph, ctx))
        except Exception:
            log.exception("Check %s failed", spec.id)
    return issues
