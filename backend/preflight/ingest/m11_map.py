import os
import re
from pathlib import Path

import yaml
from pydantic import BaseModel
from rapidfuzz import fuzz

from preflight.graph.models import Section

TOC_PATH = Path(__file__).resolve().parents[3] / "data" / "standards" / "m11_toc.yaml"

# Used until B's data/standards/m11_toc.yaml lands. Same item shape as the YAML.
STUB_TOC = [
    {"id": "1", "title": "Protocol Summary"},
    {"id": "1.1", "title": "Protocol Synopsis", "synonyms": ["Synopsis"]},
    {"id": "1.2", "title": "Trial Schema", "synonyms": ["Study Schema", "Study Design Schema"]},
    {"id": "1.3", "title": "Schedule of Activities", "synonyms": ["Schedule of Assessments", "Study Flow Chart"]},
    {"id": "2", "title": "Introduction", "synonyms": ["Background"]},
    {"id": "2.1", "title": "Purpose of Trial", "synonyms": ["Study Rationale", "Rationale"]},
    {"id": "2.2", "title": "Assessment of Risks and Benefits", "synonyms": ["Benefit-Risk Assessment"]},
    {"id": "3", "title": "Trial Objectives and Associated Estimands",
     "synonyms": ["Objectives and Endpoints", "Study Objectives", "Objectives"]},
    {"id": "3.1", "title": "Primary Objective", "synonyms": ["Primary Objectives", "Primary Endpoint"]},
    {"id": "3.2", "title": "Secondary Objectives", "synonyms": ["Secondary Endpoints"]},
    {"id": "3.3", "title": "Exploratory Objectives", "synonyms": ["Exploratory Endpoints"]},
    {"id": "4", "title": "Trial Design", "synonyms": ["Study Design", "Investigational Plan"]},
    {"id": "4.1", "title": "Description of Trial Design", "synonyms": ["Overall Design", "Description of Study"]},
    {"id": "4.2", "title": "Rationale for Trial Design", "synonyms": ["Rationale for Study Design"]},
    {"id": "4.4", "title": "Start of Trial and End of Trial", "synonyms": ["End of Study", "End of Study Definition"]},
    {"id": "5", "title": "Trial Population", "synonyms": ["Study Population", "Selection of Patients"]},
    {"id": "5.2", "title": "Inclusion Criteria"},
    {"id": "5.3", "title": "Exclusion Criteria"},
    {"id": "5.5", "title": "Lifestyle Considerations", "synonyms": ["Restrictions During the Study"]},
    {"id": "5.6", "title": "Screen Failure and Rescreening", "synonyms": ["Screen Failures"]},
    {"id": "6", "title": "Trial Intervention and Concomitant Therapy",
     "synonyms": ["Study Treatment", "Study Drug and Other Treatments", "Study Treatments"]},
    {"id": "6.10", "title": "Concomitant Therapy", "synonyms": ["Concomitant Medications", "Concomitant Treatments"]},
    {"id": "7",
     "title": "Participant Discontinuation of Trial Intervention and Discontinuation or Withdrawal from Trial",
     "synonyms": ["Discontinuation", "Withdrawal", "Patient Discontinuation", "Discontinuation of Study Treatment",
                  "Participant Discontinuation or Withdrawal", "Criteria for Discontinuation"]},
    {"id": "8", "title": "Trial Assessments and Procedures",
     "synonyms": ["Study Assessments", "Study Procedures", "Study Evaluations", "Assessment of Efficacy"]},
    {"id": "8.3", "title": "Efficacy Assessments", "synonyms": ["Efficacy Evaluation"]},
    {"id": "8.4", "title": "Safety Assessments", "synonyms": ["Safety Evaluation", "Safety Parameters"]},
    {"id": "9", "title": "Adverse Events, Serious Adverse Events, Product Complaints, Pregnancy",
     "synonyms": ["Adverse Events", "Safety Reporting", "Safety Reports and AE Management"]},
    {"id": "10", "title": "Statistical Considerations",
     "synonyms": ["Statistical Analysis", "Statistical Methods", "Statistical Considerations and Analysis Plan"]},
    {"id": "10.11", "title": "Sample Size Determination",
     "synonyms": ["Determination of Sample Size", "Statistical Hypothesis and Sample Size", "Sample Size"]},
    {"id": "10.2", "title": "Analysis Sets", "synonyms": ["Populations for Analyses", "Definition of Analysis Sets"]},
    {"id": "11", "title": "Trial Oversight and Other General Considerations",
     "synonyms": ["Study Management", "Ethics", "Ethical Considerations", "Quality Assurance and Quality Control",
                  "Regulatory, Ethical, and Study Oversight Considerations"]},
    {"id": "11.1", "title": "Data Monitoring Committee",
     "synonyms": ["Independent Data Monitoring Committee", "IDMC"]},
    {"id": "11.2", "title": "Informed Consent", "synonyms": ["Informed Consent of Subjects"]},
    {"id": "12", "title": "Appendix: Supporting Details", "synonyms": ["Appendices", "Appendix"]},
    {"id": "13", "title": "Appendix: Glossary of Terms and Abbreviations",
     "synonyms": ["List of Abbreviations", "Abbreviations", "Glossary"]},
    {"id": "14", "title": "Appendix: References", "synonyms": ["References"]},
]

THRESHOLD = 85
SCOPED_THRESHOLD = 70
MAX_LEFTOVERS = 60


# Chapter names common in pre-M11 protocols, added to the YAML synonyms (shared with B for the YAML).
EXTRA_SYNONYMS = {
    "2": ["background", "background and rationale"],
    "5": ["study population", "patients", "selection of patients"],
    "6": ["study drug and other treatments", "study treatment", "study treatments"],
    "8": ["study evaluations", "study assessments", "study procedure", "study procedures", "study assessments and "
          "procedures"],
    "9": ["safety reports and ae management", "assessment of safety", "safety reporting", "adverse event reporting"],
    "11": ["ethics", "ethical considerations", "study management", "quality assurance and quality control",
           "study documentation, monitoring, and administration", "data collection and management"],
}


def load_toc() -> list[dict]:
    if not TOC_PATH.exists():
        return STUB_TOC
    data = yaml.safe_load(TOC_PATH.read_text())
    items = data["items"] if isinstance(data, dict) else data
    for item in items:
        if item["id"] in EXTRA_SYNONYMS:
            item["synonyms"] = [*(item.get("synonyms") or []), *EXTRA_SYNONYMS[item["id"]]]
    return items


def _clean(title: str) -> str:
    title = re.sub(r"^(appendix\s+\w+|(\d+\.)*\d+)\.?\s*[:.\-–]?\s*", "", title.strip(), flags=re.I)
    return re.sub(r"\s+", " ", title).lower()


def _score(title: str, item: dict) -> tuple[float, float]:
    """(match score, exact-order score). Multi-word names also match as a subset of a longer heading."""
    best = (0.0, 0.0)
    for name in [item["title"], *item.get("synonyms", [])]:
        name = name.lower()
        exact = fuzz.token_sort_ratio(title, name)
        words = set(re.findall(r"\w+", name))
        subset = 95 if len(words) >= 2 and words <= set(re.findall(r"\w+", title)) else 0
        best = max(best, (max(exact, subset), exact))
    return best


def match(section: Section, toc: list[dict], chapter: str | None = None) -> str | None:
    """Best M11 id for a heading. `chapter` is the M11 id of the enclosing level-1 section, if mapped:
    subsections prefer items inside that chapter and never take the chapter's own id."""
    if re.match(r"^section\s+\d", section.title, re.I):
        return None  # entries in an amendment's summary of changes, not real headings
    title = _clean(section.title)
    if not title:
        return None
    if section.level == 1:
        scope = [i for i in toc if "." not in i["id"]]
    elif chapter:
        scope = [i for i in toc if i["id"].startswith(chapter + ".")]
    else:
        scope = []
    if scope and (hit := _best(title, scope, section.level, SCOPED_THRESHOLD)):
        return hit
    return _best(title, [i for i in toc if i["id"] != chapter], section.level, THRESHOLD)


def _best(title: str, items: list[dict], level: int, threshold: float) -> str | None:
    scored = []
    for item in items:
        score, exact = _score(title, item)
        if item["id"].count(".") + 1 == level:
            score += 3
        scored.append((score, exact, item["id"]))
    if not scored:
        return None
    best, _, best_id = max(scored)
    return best_id if best >= threshold else None


class _Mapping(BaseModel):
    section_id: str
    m11_id: str | None


class _Batch(BaseModel):
    mappings: list[_Mapping]


async def map_sections(sections: list[Section], use_llm: bool = True) -> list[Section]:
    toc = load_toc()
    mapped, chapter = [], None
    for sec in sections:
        m11 = match(sec, toc, chapter)
        if sec.level == 1 and sec.title[:1].isdigit():
            chapter = m11.split(".")[0] if m11 else None
        mapped.append(sec.model_copy(update={"m11_id": m11}))
    leftovers = [s for s in mapped if s.m11_id is None and s.level <= 2 and s.text][:MAX_LEFTOVERS]
    # Off by default: the LLM maps leftovers differently run to run, which made completeness unstable on the bench.
    if use_llm and leftovers and os.getenv("M11_LLM_MAP", "false") == "true":
        mapped = await _llm_map(mapped, leftovers, toc)
    return mapped


async def _llm_map(mapped: list[Section], leftovers: list[Section], toc: list[dict]) -> list[Section]:
    from preflight.llm.client import LLMUnavailable, complete_json

    toc_lines = "\n".join(f'{i["id"]} {i["title"]}' for i in toc)
    rows = "\n".join(f"{s.id} | {s.title} | {s.text[:120].replace(chr(10), ' ')}" for s in leftovers)
    system = ("You map clinical trial protocol section headings to the ICH M11 table of contents. "
              "Return m11_id null when no M11 item fits (front matter, amendment history, signatures). "
              "Only list sections that do map to an M11 item.")
    user = f"M11 items:\n{toc_lines}\n\nSections (id | heading | start of text):\n{rows}"
    try:
        batch = await complete_json("map_sections", system, user, _Batch)
    except LLMUnavailable:
        return mapped
    valid = {i["id"] for i in toc}
    found = {m.section_id: m.m11_id for m in batch.mappings if m.m11_id in valid}
    return [s.model_copy(update={"m11_id": found[s.id]}) if s.id in found else s for s in mapped]
