from pathlib import Path

import yaml

STD = Path(__file__).resolve().parents[2] / "data" / "standards"
M11 = yaml.safe_load((STD / "m11_toc.yaml").read_text())["items"]
SPIRIT = yaml.safe_load((STD / "spirit2025.yaml").read_text())["items"]
M11_IDS = {i["id"] for i in M11}


def test_m11_ids_unique_strings_and_parents_exist():
    ids = [i["id"] for i in M11]
    assert all(isinstance(x, str) for x in ids) and len(ids) == len(set(ids))
    for i in M11:
        assert i["parent"] is None or i["parent"] in M11_IDS, i["id"]
        assert i["level"] == len(i["id"].split("."))


def test_m11_template_l1_sections_present():
    assert [i["id"] for i in M11 if i["level"] == 1] == [str(n) for n in range(1, 15)]


def test_m11_required_rules():
    for i in M11:
        assert i["required"] == (i["applicability"] == "universal")
        if i["container"]:
            assert i["min_words"] == 0
    # no required content item may be uncheckable except general-considerations style ones
    bare = [i["id"] for i in M11 if i["required"] and not i["container"] and not i["required_subelements"]]
    assert set(bare) <= {"5.5", "8.1"}


def test_spirit_has_34_items_and_valid_m11_links():
    assert [i["id"] for i in SPIRIT] == [str(n) for n in range(1, 35)]
    for i in SPIRIT:
        assert i["sub_items"] and i["required_subelements"], i["id"]
        assert set(i["m11_ids"]) <= M11_IDS, (i["id"], set(i["m11_ids"]) - M11_IDS)


def test_spirit_sample_size_and_blinding_content():
    by = {i["id"]: i for i in SPIRIT}
    assert [s["id"] for s in by["24"]["sub_items"]] == ["24a", "24b", "24c"]
    assert any("power" in s for s in by["19"]["required_subelements"])
