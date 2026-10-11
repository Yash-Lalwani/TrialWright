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


def compute(issues: list[Issue], present: int, thin: int, required: int, burden: float) -> Score:
    cfg = load_config()
    w, pts = cfg["weights"], cfg["points"]
    missing = max(0, required - present - thin)
    completeness = 100 * (present + thin + 0.25 * missing) / required if required else 100
    consistency = max(0.0, 100 - _penalty(issues, "consistency", pts))
    amendment_risk = max(0.0, 100 - _penalty(issues, "amendment_risk", pts))
    overall = (w["completeness"] * completeness + w["consistency"] * consistency
               + w["burden"] * burden + w["amendment_risk"] * amendment_risk)
    return Score(overall=round(overall), completeness=round(completeness), consistency=round(consistency),
                 burden=round(burden), amendment_risk=round(amendment_risk), weights=w)
