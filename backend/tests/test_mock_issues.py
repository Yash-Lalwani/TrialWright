from preflight.graph.issues import Issue
from preflight.ingest.mock_issues import build
from tests.test_ingest_sections import make_pdf


def test_mock_issues_have_real_bboxes(tmp_path):
    path = str(tmp_path / "p.pdf")
    make_pdf(path)
    data = build(path)
    assert data["total"] == len(data["items"]) >= 1
    for item in data["items"]:
        issue = Issue.model_validate(item)
        assert issue.where.page and len(issue.where.bbox) == 4
