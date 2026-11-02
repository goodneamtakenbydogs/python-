import copy
import json
from contextlib import closing

import pytest

from study_results import CaseRecord, summarize
from study_results.config import Config, resolve_config
from study_results.errors import Cancelled, ConfigError, InputError
from study_results.reader import MAX_LINE_BYTES, parse_line, read_records


def test_one_pass_filter_and_totals():
    records = iter([CaseRecord("C-A", "passed", 0.25), CaseRecord("C-B", "failed", 0.5),
                    CaseRecord("C-C", "skipped", 0)])
    summary = summarize(records, Config(statuses=("passed", "skipped")))
    assert (summary.input_total, summary.selected_total) == (3, 2)
    assert (summary.passed, summary.failed, summary.skipped) == (1, 0, 1)
    assert summary.duration_seconds == 0.25
    assert list(records) == []


def test_empty_and_explicit_empty_selection():
    assert summarize(iter(())).selected_total == 0
    summary = summarize([CaseRecord("C-A", "failed", 1)], Config(statuses=()))
    assert summary.input_total == 1 and summary.selected_total == 0 and summary.failed == 0


def test_canonical_id_and_immutable_record():
    record = CaseRecord(" C-A ", "passed", 0)
    assert record.case_id == "C-A" and type(record.duration) is float
    with pytest.raises(AttributeError):
        record.status = "failed"


@pytest.mark.parametrize("duration", [True, -1, 86401, float("inf"), float("nan"), "1", 10**400])
def test_invalid_durations(duration):
    with pytest.raises(InputError):
        CaseRecord("C-A", "passed", duration)


@pytest.mark.parametrize("record", [
    {"case_id": "", "status": "passed", "duration": 1},
    {"case_id": "C-A", "status": "unknown", "duration": 1},
    {"case_id": True, "status": "passed", "duration": 1},
    {"case_id": "C-A", "status": [], "duration": 1},
])
def test_invalid_record_fields(record):
    with pytest.raises(InputError):
        CaseRecord(**record)


@pytest.mark.parametrize("text", ["{", "[]", "{}", '{"case_id":"C-A","status":"passed","duration":1,"extra":0}'])
def test_parser_has_physical_line(text):
    with pytest.raises(InputError) as info:
        parse_line(text, line_number=7)
    assert info.value.line == 7


def test_reader_blank_lines_and_utf8(tmp_path):
    source = tmp_path / "input.jsonl"
    source.write_text('\n{"case_id":"虚构","status":"passed","duration":0}\n\n', encoding="utf-8")
    with closing(read_records(source)) as records:
        record, = list(records)
    assert record.case_id == "虚构" and record.line == 2


def test_reader_rejects_long_line_before_whole_input_load(tmp_path):
    source = tmp_path / "input.jsonl"
    source.write_bytes(b" " * (MAX_LINE_BYTES + 1))
    with closing(read_records(source)) as records, pytest.raises(InputError) as info:
        next(records)
    assert info.value.line == 1


def test_reader_rejects_invalid_utf8(tmp_path):
    source = tmp_path / "input.jsonl"
    source.write_bytes(b"\xff\n")
    with closing(read_records(source)) as records, pytest.raises(InputError) as info:
        next(records)
    assert info.value.line == 1 and isinstance(info.value.__cause__, UnicodeError)


def test_duplicate_is_rejected_even_when_filtered_out():
    records = [CaseRecord(" C-A ", "failed", 1, line=1), CaseRecord("C-A", "skipped", 0, line=3)]
    with pytest.raises(InputError) as info:
        summarize(records, Config(statuses=("passed",)))
    assert info.value.line == 3


def test_limit_counts_unselected_input_and_stops_consumption():
    consumed = []

    def source():
        for index in range(10):
            consumed.append(index)
            yield CaseRecord(f"C-{index}", "skipped", 0)

    with closing(source()) as records, pytest.raises(InputError):
        summarize(records, Config(statuses=(), max_records=2))
    assert consumed == [0, 1, 2]


def test_cancellation_does_not_return_partial_summary():
    with pytest.raises(Cancelled):
        summarize([CaseRecord("C-A", "passed", 1)], should_stop=lambda: True)


def test_empty_input_also_checks_cancellation():
    with pytest.raises(Cancelled):
        summarize([], should_stop=lambda: True)


def test_config_precedence_and_preservation():
    file_values = {"max_records": 2, "statuses": ["skipped", "passed"]}
    environment = {"STUDY_RESULTS_MAX_RECORDS": "3"}
    overrides = {"max_records": 4, "statuses": []}
    original = copy.deepcopy((file_values, environment, overrides))
    assert resolve_config(file_values, environment, overrides) == Config(statuses=(), max_records=4)
    assert (file_values, environment, overrides) == original
    assert resolve_config(file_values, {}, {}) == Config(statuses=("passed", "skipped"), max_records=2)


@pytest.mark.parametrize("value", [True, 0, 10001, 2.0, None, "2"])
def test_config_invalid_maximum_not_hidden(value):
    with pytest.raises(ConfigError):
        resolve_config({"max_records": value}, {}, {"max_records": 2})


@pytest.mark.parametrize("values", [{"unknown": None}, {"statuses": None}, {"statuses": "passed"},
                                     {"statuses": ["passed", "passed"]}, {"statuses": ["unknown"]}])
def test_config_invalid_fields(values):
    with pytest.raises(ConfigError):
        resolve_config(values)


def test_environment_must_be_valid_even_when_cli_overrides():
    with pytest.raises(ConfigError):
        resolve_config({}, {"STUDY_RESULTS_MAX_RECORDS": "bad"}, {"max_records": 2})


def test_line_byte_limit_includes_newline(tmp_path):
    prefix = json.dumps({"case_id": "C-A", "status": "passed", "duration": 0}).encode("utf-8")
    source = tmp_path / "input.jsonl"
    source.write_bytes(prefix + b" " * (MAX_LINE_BYTES - len(prefix) - 1) + b"\n")
    with closing(read_records(source)) as records:
        assert len(list(records)) == 1
