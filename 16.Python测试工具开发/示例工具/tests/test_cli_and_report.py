import json
import os
import subprocess
import sys

import pytest

from study_results import CaseRecord, __version__
from study_results.cli import main
from study_results.errors import ReportError
from study_results.report import write_report


def records():
    yield CaseRecord("C-A", "passed", 0.25)
    yield CaseRecord("C-B", "failed", 0.5)


def test_cli_injected_reader_writer_and_result(capsys, tmp_path):
    saved = []
    code = main(["unused", "--run-id", "test-run", "--output", str(tmp_path / "out.json")], environ={},
                reader=lambda path: records(), writer=lambda path, data: saved.append((path, data)))
    output = capsys.readouterr()
    report = json.loads(output.out)
    assert code == 1 and report["counts"] == {"passed": 1, "failed": 1, "skipped": 0}
    assert saved[0][1] == report and report["duration_seconds"] == 0.75
    assert json.loads(output.err)["run_id"] == "test-run"


def test_input_failure_keeps_old_report_and_closes_reader(tmp_path, capsys):
    target = tmp_path / "report.json"
    target.write_text("old", encoding="utf-8")
    closed = []

    def source(path):
        try:
            yield CaseRecord("C-A", "passed", 0)
            yield CaseRecord("C-A", "failed", 1)
        finally:
            closed.append(True)

    code = main(["unused", "--output", str(target)], environ={}, reader=source)
    captured = capsys.readouterr()
    assert code == 3 and captured.out == "" and closed == [True]
    assert target.read_text(encoding="utf-8") == "old"
    assert json.loads(captured.err)["category"] == "input"


def test_report_failure_does_not_publish_stdout(capsys, tmp_path):
    def fail(path, data):
        raise ReportError("controlled")
    code = main(["unused", "--output", str(tmp_path / "out.json")], environ={},
                reader=lambda path: records(), writer=fail)
    captured = capsys.readouterr()
    assert code == 4 and captured.out == "" and json.loads(captured.err)["category"] == "report"


def test_invalid_config_does_not_start_reader(capsys):
    def forbidden(path):
        raise AssertionError("reader must not be called")
    assert main(["unused", "--max-records", "0"], environ={}, reader=forbidden) == 2
    assert json.loads(capsys.readouterr().err)["category"] == "configuration"


def test_output_cannot_overwrite_input(tmp_path, capsys):
    source = tmp_path / "input.jsonl"
    source.write_text("old", encoding="utf-8")
    assert main([str(source), "--output", str(source)], environ={}) == 2
    assert source.read_text(encoding="utf-8") == "old"
    assert capsys.readouterr().out == ""


def test_replace_failure_preserves_old_and_cleans_temporary(tmp_path):
    destination = tmp_path / "report.json"
    destination.write_text("old", encoding="utf-8")
    original = PermissionError("controlled")

    def fail(*args):
        raise original

    with pytest.raises(ReportError) as info:
        write_report(destination, {"value": 1}, replace=fail)
    assert info.value.__cause__ is original
    assert destination.read_text(encoding="utf-8") == "old"
    assert [path.name for path in tmp_path.iterdir()] == ["report.json"]


def test_serialization_failure_does_not_touch_target(tmp_path):
    target = tmp_path / "report.json"
    target.write_text("old", encoding="utf-8")
    with pytest.raises(ReportError):
        write_report(target, {"bad": object()})
    assert target.read_text(encoding="utf-8") == "old"
    assert list(tmp_path.iterdir()) == [target]


def test_interrupt_closes_source_and_does_not_claim_success(capsys):
    closed = []

    def source(path):
        try:
            raise KeyboardInterrupt
            yield
        finally:
            closed.append(True)

    assert main(["unused"], environ={}, reader=source) == 130
    captured = capsys.readouterr()
    assert captured.out == "" and json.loads(captured.err)["event"] == "summary_cancelled"
    assert closed == [True]


def test_real_module_entry_from_another_directory(tmp_path):
    source = tmp_path / "sample input.jsonl"
    target = tmp_path / "sample report.json"
    source.write_text('{"case_id":"C-demo","status":"passed","duration":0}\n', encoding="utf-8")
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment.pop("STUDY_RESULTS_MAX_RECORDS", None)
    completed = subprocess.run([sys.executable, "-m", "study_results", str(source), "--output", str(target),
                                "--run-id", "module-run"], cwd=tmp_path, env=environment,
                               capture_output=True, text=True, encoding="utf-8", check=False, timeout=10,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == json.loads(target.read_text(encoding="utf-8"))


def test_distribution_version_matches_import():
    from importlib.metadata import version
    assert version("study-results-demo") == __version__


@pytest.mark.parametrize("run_id", ["", "with space", "bad\nline", "x" * 41])
def test_invalid_run_id_is_not_echoed_to_logs(run_id, capsys):
    assert main(["unused", "--run-id", run_id], environ={}) == 2
    assert json.loads(capsys.readouterr().err)["run_id"] is None
