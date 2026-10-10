import importlib
import pkgutil
from dataclasses import dataclass, field
from collections.abc import Callable

from preflight.graph.issues import Issue
from preflight.graph.models import ProtocolGraph


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


def check(id: str, category: str, amendment_category: str, standard_ref: str, severity: str):
    def register(fn):
        CHECKS[id] = CheckSpec(id, category, amendment_category, standard_ref, severity, fn)
        return fn

    return register


def discover() -> dict[str, CheckSpec]:
    import preflight.checks as pkg

    for mod in pkgutil.iter_modules(pkg.__path__):
        importlib.import_module(f"preflight.checks.{mod.name}")
    return CHECKS


def run_checks(graph: ProtocolGraph, ctx: CheckContext) -> list[Issue]:
    issues = []
    for spec in discover().values():
        issues.extend(spec.fn(graph, ctx))
    return issues
