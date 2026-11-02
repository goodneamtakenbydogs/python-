from concurrent.futures import Future
from contextlib import closing
from threading import Event, Lock, Thread

import pytest

from study_results.batch import map_bounded
from study_results.errors import Cancelled, ConfigError


def test_batch_association_and_independent_failure():
    def work(value):
        if value == 2:
            raise ValueError("controlled")
        return value * 10
    with closing(map_bounded([3, 2, 1], work, workers=2, max_in_flight=2)) as results:
        rows = sorted(results, key=lambda row: row.index)
    assert [(row.index, row.status, row.value, row.error_type) for row in rows] == [
        (0, "completed", 30, None), (1, "error", None, "ValueError"), (2, "completed", 10, None)]


def test_batch_cancellation_before_input_consumption():
    consumed = []

    def source():
        consumed.append(True)
        yield 1

    with closing(map_bounded(source(), lambda value: value, should_stop=lambda: True)) as results:
        with pytest.raises(Cancelled):
            next(results)
    assert consumed == []


def test_batch_caps_running_and_in_flight_input():
    gate, ready = Event(), Event()
    lock = Lock()
    consumed, finished, failures = [], [], []
    active = peak = 0

    def source():
        for value in range(8):
            consumed.append(value)
            yield value

    def work(value):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
            if active == 2:
                ready.set()
        if not gate.wait(3):
            raise RuntimeError("test gate was not released")
        with lock:
            active -= 1
        return value

    def consume():
        try:
            with closing(map_bounded(source(), work, workers=2, max_in_flight=3)) as rows:
                finished.extend(rows)
        except BaseException as error:
            failures.append(error)

    thread = Thread(target=consume)
    thread.start()
    try:
        assert ready.wait(3)
        assert 2 <= len(consumed) <= 3
        assert peak <= 2
    finally:
        gate.set()
        thread.join(5)
    assert not thread.is_alive() and failures == []
    assert len(finished) == 8 and peak == 2


def test_partial_consumption_closes_input():
    closed = []

    def source():
        try:
            yield from range(5)
        finally:
            closed.append(True)

    with closing(map_bounded(source(), lambda value: value, workers=1, max_in_flight=1)) as results:
        assert next(results).index == 0
    assert closed == [True]


@pytest.mark.parametrize("kwargs", [{"workers": 0}, {"workers": True}, {"max_in_flight": 0},
                                     {"max_in_flight": 33}, {"budget": 0}, {"budget": float("nan")}])
def test_invalid_batch_limits(kwargs):
    with closing(map_bounded([], lambda value: value, **kwargs)) as results, pytest.raises(ConfigError):
        next(results)


def test_budget_rejects_before_submitting(monkeypatch):
    from study_results import batch
    ticks = iter([0.0, 2.0])
    monkeypatch.setattr(batch.time, "monotonic", lambda: next(ticks))
    calls = []
    with closing(map_bounded([1], calls.append, budget=1)) as results, pytest.raises(TimeoutError):
        next(results)
    assert calls == []


def test_pool_exit_error_still_closes_owned_input(monkeypatch):
    from study_results import batch
    closed = []

    class Pool:
        def __init__(self, **kwargs):
            pass

        def submit(self, function, item):
            future = Future()
            future.set_result(function(item))
            return future

        def shutdown(self, **kwargs):
            raise OSError("controlled shutdown failure")

    def source():
        try:
            yield 1
            yield 2
        finally:
            closed.append(True)

    monkeypatch.setattr(batch, "ThreadPoolExecutor", Pool)
    results = batch.map_bounded(source(), lambda value: value, max_in_flight=1)
    assert next(results).index == 0
    with pytest.raises(OSError):
        results.close()
    assert closed == [True]
