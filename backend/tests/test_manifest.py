import csv
from collections import Counter

from preflight.ctgov import corpus

ROWS = list(csv.DictReader(open(corpus.MANIFEST)))


def test_manifest_columns_and_split():
    assert list(ROWS[0].keys()) == corpus.COLUMNS
    assert Counter(r["split"] for r in ROWS) == {"dev": 3, "test": 7}


def test_manifest_rows_complete_and_unique():
    ids = [r["nct_id"] for r in ROWS]
    assert len(ids) == len(set(ids))
    for r in ROWS:
        assert all(r[c] for c in corpus.COLUMNS), r["nct_id"]
        assert r["source_url"].endswith(".pdf") and r["nct_id"] in r["source_url"]
