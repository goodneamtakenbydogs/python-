import copy
import json
from pathlib import Path

import pytest
from sample_report.core import render_report, write_report

DATA_PATH = Path(__file__).parent / "data" / "cases.json"
CASES = json.loads(DATA_PATH.read_text(encoding="utf-8"))
if not isinstance(CASES, list) or not CASES:
    raise ValueError("cases must be a non-empty list")
if any(not isinstance(row, dict) or set(row) != {"id", "labels", "expected"} for row in CASES):
    raise ValueError("case fields do not match the teaching contract")
if any(not isinstance(row["id"], str) or not row["id"] for row in CASES):
    raise ValueError("case IDs must be non-empty text")
if len({row["id"] for row in CASES}) != len(CASES):
    raise ValueError("case IDs must be unique")
if any(type(row["labels"]) is not list or not isinstance(row["expected"], str) for row in CASES):
    raise ValueError("case input and expectation types do not match")


@pytest.mark.smoke
def test_empty_report():
    assert render_report([]) == "Report\n"


@pytest.mark.parametrize(
    "labels, expected",
    [pytest.param(row["labels"], row["expected"], id=row["id"]) for row in CASES],
)
def test_render_rows(labels, expected):
    before = copy.deepcopy(labels)
    assert render_report(labels) == expected
    assert labels == before


@pytest.mark.parametrize("labels", [(), None, "A"], ids=["tuple", "none", "text"])
def test_invalid_container(labels):
    with pytest.raises(TypeError, match="list"):
        render_report(labels)


@pytest.mark.parametrize("labels", [[""], ["A\nB"], ["A", "B", "C", "D"]],
                         ids=["blank", "multiline", "above"])
def test_invalid_values(labels):
    with pytest.raises(ValueError):
        render_report(labels)


def test_write_report(report_path):
    write_report(["A"], report_path, title="Demo")
    assert report_path.read_text(encoding="utf-8") == "Demo\nA\n"


def test_rejected_input_keeps_old_report(report_path):
    report_path.write_text("old", encoding="utf-8")
    with pytest.raises(ValueError):
        write_report([""], report_path)
    assert report_path.read_text(encoding="utf-8") == "old"


def test_factory_creates_separate_paths(report_factory):
    first = report_factory("first")
    second = report_factory("second")
    assert first != second
    assert first.read_text(encoding="utf-8") == "first"
    assert second.read_text(encoding="utf-8") == "second"
