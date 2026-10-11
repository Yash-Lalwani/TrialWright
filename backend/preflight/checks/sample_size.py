# ruff: noqa: E501
"""C7: recompute the sample size from the stated alpha, power, effect, allocation and dropout; flag a mismatch.

The LLM never does this arithmetic. `calc_sample_size` is also the calculator the co-author uses for drafts (E3).

Interpretation of graph.stats fields (A's extraction prompt should say the same):
  mean_diff_sd : effect_size = standardised difference (mean difference / SD, Cohen's d)
  proportions  : control_rate = control-arm proportion, effect_size = treatment-arm proportion
  hazard_ratio : effect_size = HR; control_rate = overall event probability (events / N); without it only the
                 required number of events can be computed, so no flag is raised
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from scipy.stats import norm
from statsmodels.stats.power import NormalIndPower, TTestIndPower
from statsmodels.stats.proportion import proportion_effectsize

from preflight.checks.registry import CheckContext, check, issue, where
from preflight.graph.models import ProtocolGraph

TOLERANCE = 0.05


@dataclass
class SampleSize:
    n_per_arm_control: int
    n_total_evaluable: int
    n_total_enrolled: int
    events: int | None
    method: str


def parse_ratio(ratio: str | None) -> float:
    """'2:1' -> 2.0 (experimental : control). Anything unparseable is 1:1."""
    try:
        a, b = (float(x) for x in (ratio or "1:1").split(":"))
        return a / b if a > 0 and b > 0 else 1.0
    except ValueError:
        return 1.0


def calc_sample_size(effect_type: str, effect_size: float, alpha: float = 0.05, power: float = 0.8, sided: int = 2,
                     control_rate: float | None = None, dropout: float | None = None, ratio: float = 1.0) -> SampleSize | None:
    """Total sample size for the stated design, or None if the inputs are not enough to compute one."""
    alt = "two-sided" if sided == 2 else "larger"
    inflate = 1 / (1 - dropout) if dropout and 0 <= dropout < 1 else 1.0
    if effect_type == "mean_diff_sd":
        if effect_size <= 0:
            return None
        n1 = TTestIndPower().solve_power(effect_size=abs(effect_size), alpha=alpha, power=power, ratio=ratio, alternative=alt)
        method = "Two-sample t-test"
        events = None
    elif effect_type == "proportions":
        if control_rate is None or not (0 < control_rate < 1 and 0 < effect_size < 1) or control_rate == effect_size:
            return None
        h = abs(proportion_effectsize(effect_size, control_rate))
        n1 = NormalIndPower().solve_power(effect_size=h, alpha=alpha, power=power, ratio=ratio, alternative=alt)
        method = "Two-proportion z-test (arcsine effect size)"
        events = None
    elif effect_type == "hazard_ratio":
        if effect_size <= 0 or effect_size == 1:
            return None
        za = norm.ppf(1 - alpha / (2 if sided == 2 else 1))
        events = math.ceil((za + norm.ppf(power)) ** 2 * (1 + ratio) ** 2 / (ratio * math.log(effect_size) ** 2))
        if not control_rate or not 0 < control_rate <= 1:
            return None  # events are known but N needs an event probability
        total = events / control_rate
        n1 = total / (1 + ratio)
        method = "Log-rank, Schoenfeld events"
    else:
        return None
    if not math.isfinite(n1) or n1 <= 0:
        return None  # the solver did not converge (extreme extracted inputs): no calculation, no finding
    total_eval = math.ceil(n1) + math.ceil(n1 * ratio)
    return SampleSize(math.ceil(n1), total_eval, math.ceil(total_eval * inflate), events, method)


@check(id="C7", category="consistency", amendment_category="statistics",
       standard_ref="ICH M11 10.11; SPIRIT 2025 item 19", severity="major")
def sample_size_reproducible(graph: ProtocolGraph, ctx: CheckContext):
    s = graph.stats
    if not (s.sample_size and s.power and s.effect_type and s.effect_size is not None):
        return []
    assumed_alpha = s.alpha is None
    calc = calc_sample_size(s.effect_type, s.effect_size, s.alpha or 0.05, s.power, s.sided or 2, s.control_rate, s.dropout,
                            parse_ratio(graph.meta.ratio))
    if calc is None:
        return []
    stated = s.sample_size
    # the protocol may state the evaluable N or the enrolled N (after dropout); either is acceptable
    cands = sorted({calc.n_total_evaluable, calc.n_total_enrolled})
    closest = min(cands, key=lambda c: abs(stated - c))
    if abs(stated - closest) / closest <= TOLERANCE:
        return []
    fact = next((n for n in graph.numbers if n.kind == "sample_size" and float(n.value) == stated), None)
    at = where(graph, fact.span if fact else None, section="10.11 Sample Size Determination")
    wanted = f"{cands[0]}" if len(cands) == 1 else f"{cands[0]} evaluable or {cands[-1]} enrolled"
    inputs = (f"alpha {s.alpha if s.alpha is not None else '0.05 (assumed)'}, {s.sided or 2}-sided, power {s.power}, "
              f"effect {s.effect_size}" + (f", control {s.control_rate}" if s.control_rate is not None else "")
              + (f", dropout {s.dropout}" if s.dropout else "") + f", ratio {graph.meta.ratio or '1:1'}")
    direction = "fewer" if stated < closest else "more"
    return [issue(
        "C7", f"Stated sample size {stated} cannot be reproduced from the stated assumptions (needs {wanted})", at,
        f"{calc.method} with {inputs} requires {wanted} participants, but the protocol states {stated} "
        f"({direction} than needed, {abs(stated - closest) / closest:.0%} off).",
        fix=f"Either change the stated sample size to {cands[-1]} or correct the power, effect size or dropout assumptions.",
        severity="minor" if assumed_alpha else None, confidence=0.7 if assumed_alpha else 0.9)]
