import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import sample_check as sample


class ManualClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def __call__(self):
        return self.now

    def wait(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def result(state="ready", count=2, *, code=0):
    return sample.CommandResult(("sample",), code, json.dumps({"state": state, "count": count}), "")


@pytest.mark.parametrize("state", ["pending", "ready", "failed"])
def test_parse_states(state):
    assert sample.parse_snapshot(json.dumps({"state": state, "count": 0})) == sample.Snapshot(state, 0)


@pytest.mark.parametrize("text", ["{", "[]", '{"count":2}', '{"state":"unknown","count":2}',
                                  '{"state":"ready","count":true}', '{"state":"ready","count":2.0}',
                                  '{"state":"ready","count":-1}', '{"state":"ready","count":2,"extra":0}'])
def test_invalid_protocol(text):
    with pytest.raises(sample.ProtocolFailure):
        sample.parse_snapshot(text)


def test_settings_precedence_and_preservation():
    file_values = {"budget": 1, "expected_count": 0}
    environment = {"CH15_SAMPLE_BUDGET": "2"}
    overrides = {"budget": 3, "timeout": None}
    before = copy.deepcopy((file_values, environment, overrides))
    settings = sample.resolve_settings(file_values, environment, overrides)
    assert settings["budget"] == 3.0 and settings["expected_count"] == 0
    assert settings["timeout"] == 1.0
    assert (file_values, environment, overrides) == before


@pytest.mark.parametrize("value", [0, -1, True, "1", None, float("nan"), float("inf")])
def test_invalid_time_config(value):
    with pytest.raises(ValueError):
        sample.resolve_settings({"budget": value}, {}, {"budget": 3})


def test_invalid_environment_is_not_hidden_by_cli():
    with pytest.raises(ValueError, match="CH15_SAMPLE_BUDGET"):
        sample.resolve_settings({}, {"CH15_SAMPLE_BUDGET": "bad"}, {"budget": 3})


def test_executor_keeps_nonzero_and_streams():
    calls = []

    def runner(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 4, "partial", "diagnostic")

    arguments = ["sample", "with spaces; literal"]
    observed = sample.execute(arguments, timeout=0.5, runner=runner)
    assert observed == sample.CommandResult(tuple(arguments), 4, "partial", "diagnostic")
    assert calls[0][0] == arguments and calls[0][0] is not arguments
    assert calls[0][1]["shell"] is False and calls[0][1]["check"] is False
    assert calls[0][1]["timeout"] == 0.5 and calls[0][1]["encoding"] == "utf-8"


@pytest.mark.parametrize("original, expected", [
    (FileNotFoundError("missing"), sample.ExecutionFailure),
    (subprocess.TimeoutExpired(["sample"], 1, output=b"partial"), sample.ReadTimeout),
    (UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad"), sample.ProtocolFailure),
])
def test_executor_translates_known_errors_with_cause(original, expected):
    def runner(*args, **kwargs):
        raise original
    with pytest.raises(expected) as info:
        sample.execute(["sample"], timeout=1, runner=runner)
    assert info.value.__cause__ is original


def test_real_child_argument_boundary():
    value = "A B; sample"
    observed = sample.execute([sys.executable, "-X", "utf8", "-c", "import sys; print(sys.argv[1])", value], timeout=5)
    assert observed.returncode == 0 and observed.stdout.strip() == value


def test_real_child_nonzero():
    observed = sample.execute([sys.executable, "-c", "raise SystemExit(4)"], timeout=5)
    assert observed.returncode == 4


def test_real_child_timeout():
    with pytest.raises(sample.ReadTimeout) as info:
        sample.execute([sys.executable, "-c", "import time; time.sleep(3)"], timeout=0.05)
    assert isinstance(info.value.__cause__, subprocess.TimeoutExpired)


def test_poll_pending_then_ready():
    timer = ManualClock()
    values = iter([sample.Snapshot("pending", 0), sample.Snapshot("ready", 2)])
    timeouts = []

    def fetch(remaining):
        timeouts.append(remaining)
        return next(values)

    observed = sample.poll_snapshot(fetch, budget=1, interval=0.25, max_attempts=3,
                                    clock=timer, wait=timer.wait)
    assert observed == (sample.Snapshot("ready", 2), 2)
    assert timer.sleeps == [0.25] and timeouts == [1.0, 0.75]


def test_poll_accepts_retryable_timeout_only():
    timer = ManualClock()
    calls = []

    def fetch(remaining):
        calls.append(remaining)
        if len(calls) == 1:
            timer.now += 0.1
            raise sample.ReadTimeout("controlled")
        return sample.Snapshot("ready", 2)

    assert sample.poll_snapshot(fetch, budget=1, interval=0.2, max_attempts=2,
                                clock=timer, wait=timer.wait)[1] == 2
    assert len(calls) == 2 and timer.sleeps == [0.2]


def test_late_ready_is_not_accepted():
    timer = ManualClock()

    def fetch(remaining):
        timer.now = 1.0
        return sample.Snapshot("ready", 2)

    with pytest.raises(sample.BudgetExpired):
        sample.poll_snapshot(fetch, budget=1, interval=0.1, max_attempts=3, clock=timer, wait=timer.wait)
    assert timer.sleeps == []


def test_wait_is_clipped_and_no_new_query_after_budget():
    timer = ManualClock()
    calls = []

    def fetch(remaining):
        calls.append(remaining)
        return sample.Snapshot("pending", 0)

    with pytest.raises(sample.BudgetExpired):
        sample.poll_snapshot(fetch, budget=1, interval=2, max_attempts=3, clock=timer, wait=timer.wait)
    assert calls == [1.0] and timer.sleeps == [1.0]


def test_attempt_limit_even_if_clock_stops():
    calls, waits = [], []

    def fetch(remaining):
        calls.append(remaining)
        return sample.Snapshot("pending", 0)

    with pytest.raises(sample.AttemptsExhausted):
        sample.poll_snapshot(fetch, budget=1, interval=0.1, max_attempts=3, clock=lambda: 0, wait=waits.append)
    assert len(calls) == 3 and len(waits) == 2


def test_failed_is_terminal_and_no_sleep():
    timer = ManualClock()
    with pytest.raises(sample.TaskFailed):
        sample.poll_snapshot(lambda remaining: sample.Snapshot("failed", 0), budget=1,
                             interval=0.1, max_attempts=3, clock=timer, wait=timer.wait)
    assert timer.sleeps == []


@pytest.mark.parametrize("query, category", [
    (sample.CommandResult(("sample",), 3, "not JSON", "failure"), "execution_error"),
    (sample.CommandResult(("sample",), 0, "not JSON", ""), "protocol_error"),
    (result("ready", 1), "check_failed"), (result("ready", 2), "passed"),
    (result("failed", 0), "task_failed"),
])
def test_flow_categories(query, category):
    timer = ManualClock()
    observed = sample.check_file("unused", executor=lambda *args, **kwargs: query,
                                 clock=timer, wait=timer.wait)
    assert observed.category == category and observed.attempts == 1


def test_each_query_timeout_is_limited_by_remaining_budget():
    timer = ManualClock()
    limits = []

    def executor(argv, *, timeout):
        limits.append(timeout)
        return result("pending" if len(limits) == 1 else "ready", 2)

    observed = sample.check_file("unused", budget=0.5, timeout=1, interval=0.25,
                                 executor=executor, clock=timer, wait=timer.wait)
    assert observed.category == "passed" and limits == [0.5, 0.25]


def test_unexpected_error_is_not_retried():
    original = RuntimeError("bug")
    calls = []

    def executor(*args, **kwargs):
        calls.append("call")
        raise original

    with pytest.raises(RuntimeError) as info:
        sample.check_file("unused", executor=executor)
    assert info.value is original and calls == ["call"]


def test_atomic_replace_failure_preserves_old_report(tmp_path, monkeypatch):
    destination = tmp_path / "report.json"
    destination.write_text("old", encoding="utf-8")

    def fail_replace(*args):
        raise PermissionError("controlled")

    monkeypatch.setattr(sample.os, "replace", fail_replace)
    with pytest.raises(PermissionError):
        sample.atomic_write_json(destination, {"count": 2})
    assert destination.read_text(encoding="utf-8") == "old"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["report.json"]


def test_serialization_failure_does_not_create_temp_file(tmp_path):
    destination = tmp_path / "report.json"
    destination.write_text("old", encoding="utf-8")
    with pytest.raises(TypeError):
        sample.atomic_write_json(destination, {"value": object()})
    assert destination.read_text(encoding="utf-8") == "old"
    assert list(tmp_path.iterdir()) == [destination]


def test_cleanup_error_does_not_replace_original_failure(tmp_path, monkeypatch, caplog):
    destination = tmp_path / "report.json"
    destination.write_text("old", encoding="utf-8")
    original = PermissionError("replace failed")
    original_unlink = Path.unlink

    def fail_replace(*args):
        raise original

    def fail_cleanup(path, *args, **kwargs):
        if path.name.startswith(".sample-check-"):
            raise OSError("cleanup failed")
        return original_unlink(path, *args, **kwargs)

    with monkeypatch.context() as local:
        local.setattr(sample.os, "replace", fail_replace)
        local.setattr(Path, "unlink", fail_cleanup)
        with pytest.raises(PermissionError) as info:
            sample.atomic_write_json(destination, {"count": 2})
    assert info.value is original
    assert destination.read_text(encoding="utf-8") == "old"
    assert "temporary report cleanup failed" in caplog.text
    for pending in tmp_path.glob(".sample-check-*.tmp"):
        pending.unlink()


def test_invalid_config_does_not_call_executor(capsys):
    def forbidden(*args, **kwargs):
        raise AssertionError("must validate first")
    assert sample.main(["unused", "--budget", "0"], environ={}, executor=forbidden) == 2
    assert "budget" in capsys.readouterr().err


def test_report_cannot_overwrite_source(tmp_path, capsys):
    source = tmp_path / "snapshot.json"
    source.write_text('{"state":"ready","count":2}', encoding="utf-8")
    assert sample.main([str(source), "--report", str(source)], environ={}) == 2
    assert "overwrite" in capsys.readouterr().err


def test_report_failure_does_not_reclassify_business_result(monkeypatch, capsys, tmp_path):
    def fail(*args, **kwargs):
        raise PermissionError("controlled")
    monkeypatch.setattr(sample, "atomic_write_json", fail)
    code = sample.main(["unused", "--report", str(tmp_path / "report.json")], environ={},
                       executor=lambda *args, **kwargs: result())
    captured = capsys.readouterr()
    record = json.loads(captured.out)
    assert code == 8 and record["category"] == "passed" and record["report_error"] == "PermissionError"


def test_user_interrupt_is_not_reported_as_passed(capsys):
    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt
    assert sample.main(["unused"], environ={}, executor=interrupted) == 130
    captured = capsys.readouterr()
    assert captured.out == "" and "unknown" in captured.err


def test_real_cli_and_report_with_spaced_paths(tmp_path):
    source = tmp_path / "sample input.json"
    report = tmp_path / "sample report.json"
    source.write_text('{"state":"ready","count":2}', encoding="utf-8")
    environment = os.environ.copy()
    environment.pop("CH15_SAMPLE_BUDGET", None)
    completed = subprocess.run(
        [sys.executable, "-X", "utf8", str(Path(sample.__file__).resolve()), str(source), "--report", str(report)],
        env=environment, capture_output=True, text=True, encoding="utf-8", check=False, timeout=10,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    assert completed.returncode == 0, completed.stderr
    observed = json.loads(completed.stdout)
    assert observed["category"] == "passed" and observed["count"] == 2
    assert json.loads(report.read_text(encoding="utf-8")) == observed
