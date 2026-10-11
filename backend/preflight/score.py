from pathlib import Path

import yaml
from pydantic import BaseModel

from preflight.graph.issues import Issue

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "score.yaml"
DEFAULTS = {
    "weights": {"completeness": 0.25, "consistency": 0.35, "burden": 0.20, "amendment_risk": 0.20},
    "points": {"critical": 15, "major": 8, "minor": 3, "advisory": 0},
}


class Score(BaseModel):
    overall: int
    completeness: int
    consistency: int
    burden: int
    amendment_risk: int
    weights: dict[str, float]


_LEGACY = object()
NEUTRAL = 50.0


def load_config() -> dict:
    cfg = {k: dict(v) for k, v in DEFAULTS.items()}
    if CONFIG_PATH.exists():
        for key, value in (yaml.safe_load(CONFIG_PATH.read_text()) or {}).items():
            if isinstance(value, dict) and key in cfg:
                cfg[key].update(value)
            else:
                cfg[key] = value
    return cfg


def _penalty(issues: list[Issue], category: str, points: dict) -> float:
    """Accepted issues stop counting; rejected ones keep their points (CONTRACTS 4.4)."""
    return sum(points.get(i.severity, 0) for i in issues if i.category == category and i.status != "accepted")


def compute(issues: list[Issue], present: int, thin: int, required: int, burden: float,
            amendment_risk=_LEGACY) -> Score:
    """amendment_risk: a 0-100 value from burden.risk (peer-based); None = not assessed (weight 0 in the returned
    weights, the others rescaled to sum to 1); omitted = the old rule (100 minus the points of issues tagged
    amendment_risk)."""
    cfg = load_config()
    w, pts = dict(cfg["weights"]), cfg["points"]
    completeness = 100 * (present + 0.5 * thin) / required if required else 100
    consistency = max(0.0, 100 - _penalty(issues, "consistency", pts))
    if amendment_risk is _LEGACY:
        risk = max(0.0, 100 - _penalty(issues, "amendment_risk", pts))
    elif amendment_risk is None:
        risk = NEUTRAL      # shown at a neutral 50; weight 0 tells consumers it was not assessed
        total = sum(v for k, v in w.items() if k != "amendment_risk")
        w = {k: (0.0 if k == "amendment_risk" else round(v / total, 4)) for k, v in w.items()}
    else:
        risk = float(amendment_risk)
    overall = (w["completeness"] * completeness + w["consistency"] * consistency
               + w["burden"] * burden + w["amendment_risk"] * risk)
    return Score(overall=round(overall), completeness=round(completeness), consistency=round(consistency),
                 burden=round(burden), amendment_risk=round(risk), weights=w)
