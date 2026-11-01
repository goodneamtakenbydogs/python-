"""第十章逐题检查：核对客观行为，保留学习者原始预测。"""

from __future__ import annotations

import asyncio
import inspect
import json
import os
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Event, Lock
from typing import Any

UNFINISHED = "__未填写__"


class CheckFailure(AssertionError):
    """当前实验的记录或实现尚未符合题意。"""


def run_script(source: str) -> Any:
    """把可见实验源码作为真实主模块运行，返回它唯一的 JSON 输出。"""
    with tempfile.TemporaryDirectory(prefix="python_ch10_") as directory:
        script = Path(directory) / "experiment.py"
        script.write_text(source, encoding="utf-8")
        environment = os.environ.copy()
        environment["PYTHONIOENCODING"] = "utf-8"
        result = subprocess.run(
            [sys.executable, "-X", "utf8", str(script)],
            cwd=directory, env=environment, capture_output=True,
            text=True, encoding="utf-8", timeout=40, check=True,
        )
    return json.loads(result.stdout)


def _unfinished(value: Any) -> bool:
    if isinstance(value, str):
        return value == UNFINISHED
    if isinstance(value, dict):
        return any(_unfinished(item) for item in value.values())
    if isinstance(value, (tuple, list)):
        return any(_unfinished(item) for item in value)
    return False


def _fields(namespace: dict[str, Any], name: str, count: int, phase: str):
    mapping = namespace.get(name)
    if not isinstance(mapping, dict) or len(mapping) != count:
        raise CheckFailure(f"请填写并运行本题全部{phase}字段，保留原编号。")
    result = {}
    for label, value in mapping.items():
        match = re.match(r"^(\d{2})\.\s+", label) if isinstance(label, str) else None
        if match is None or match.group(1) in result:
            raise CheckFailure(f"{phase}字段“{label}”的两位编号缺失或重复。")
        if _unfinished(value):
            raise CheckFailure(f"{phase}字段“{label}”尚未填写；请替换包括引号的整个占位字符串。")
        result[match.group(1)] = (label, value)
    if set(result) != {f"{index:02d}" for index in range(1, count + 1)}:
        raise CheckFailure(f"本题{phase}编号不完整，请保留题面编号。")
    return result


def _matches(actual: Any, expected: Any) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, (tuple, list)):
        return len(actual) == len(expected) and all(
            _matches(left, right) for left, right in zip(actual, expected)
        )
    return actual == expected


OBSERVATIONS = {
    1: [[], ["work"], None, False],
    2: [["written"], ["local only"]],
    3: [1],
    4: [200, False],
    5: [False, True, True],
    6: [False, "cleaned", False],
    7: [[True, True, False], "ValueError"],
    8: ["report", []],
    9: ["Full", [10, 20], None],
    10: [42, "ValueError", True],
    11: [["fast", "slow"], ["slow", "fast"]],
    12: [False, True, "CancelledError", "finished"],
    13: [["parent"], ["parent", "child"], 0],
    14: [[9, 1, 4]],
    15: [[], ["body"], 12],
    16: [["A start", "A end", "B start", "B end"], 2],
    17: [["before", "instant", "after", "other"], 7],
    18: [["fast", "slow"], ["slow", "fast"]],
    19: ["ValueError", False, "finished"],
    20: [["ValueError"], ["released"], True],
    21: [1, 2],
    22: [[10, 20, 30], True, 2],
    23: ["TimeoutError", True, ["released"]],
    24: [True, True, ["released"], False],
}


def _check_observation(namespace: dict[str, Any], number: int) -> None:
    expected = OBSERVATIONS[number]
    _fields(namespace, f"prediction_{number:02d}", len(expected), "预测")
    observed = _fields(namespace, f"observation_{number:02d}", len(expected), "实际观察")
    for index, target in enumerate(expected, 1):
        label, value = observed[f"{index:02d}"]
        try:
            correct = _matches(value, target)
        except (TypeError, ValueError, RecursionError):
            correct = False
        if not correct:
            raise CheckFailure(f"实际观察字段“{label}”与运行结果不一致，请重新观察当前实验。")


def _callable(namespace: dict[str, Any], name: str):
    function = namespace.get(name)
    if not callable(function):
        raise CheckFailure(f"找不到 {name}，请先运行本题定义单元格。")
    return function


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def _check_counter(namespace: dict[str, Any]) -> None:
    cls = _callable(namespace, "LockedCounter")
    first, second = cls(), cls(10)
    _require(first.snapshot() == 0 and second.snapshot() == 10,
             "实验 25 的初值或实例隔离不符合题意。")
    _require(first.add() == 1 and first.add(-3) == -2 and first.add(0) == -2,
             "实验 25 的单次更新返回值不符合接口。")
    _require(second.snapshot() == 10, "实验 25 的实例之间不应共享计数状态。")
    counter = cls()
    barrier = Barrier(6, timeout=5)

    def work():
        barrier.wait()
        return [counter.add() for _ in range(80)]

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: work(), range(6)))
    values = [value for row in results for value in row]
    _require(all(type(value) is int for value in values),
             "实验 25 的 add 返回结果不符合题面接口。")
    _require(counter.snapshot() == 480 and sorted(values) == list(range(1, 481)),
             "实验 25 的并发更新或每次返回值破坏了计数约束。")
    counter = cls(100)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(counter.add, [3, -5, 0, 2] * 30))
    _require(counter.snapshot() == 100, "实验 25 的混合正负更新不符合约束。")


def _check_thread_map(namespace: dict[str, Any]) -> None:
    function = _callable(namespace, "thread_map_ordered")
    for invalid in (0, -1, True, 1.5, "2"):
        try:
            function(abs, [], max_workers=invalid)
        except ValueError:
            pass
        else:
            raise CheckFailure("实验 26 未按题意拒绝无效 max_workers。")
    for values in ([], [3, -1, 3, 0], [9], list(range(-10, 10))):
        before = values.copy()
        result = function(lambda value: value * value, iter(values), max_workers=3)
        _require(type(result) is list and result == [value * value for value in before],
                 "实验 26 未保留输入位置、重复值或空输入约定。")
        _require(values == before, "实验 26 不应自行修改输入。")

    lock = Lock()
    rendezvous = Barrier(3, timeout=5)
    active = peak = 0

    def operation(index):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        try:
            if index < 3:
                rendezvous.wait()
            return index * 7
        finally:
            with lock:
                active -= 1

    result = function(operation, iter(range(9)), max_workers=3)
    _require(result == [index * 7 for index in range(9)] and peak == 3 and active == 0,
             "实验 26 的并发推进、并发上限或结束确认不符合题意。")
    started, failed, ended = Event(), Event(), Event()
    marker = LookupError("check marker")

    def may_fail(index):
        if index == 0:
            try:
                started.set()
                if not failed.wait(timeout=5):
                    raise TimeoutError("没有推进另一个工作")
                return 0
            finally:
                ended.set()
        if not started.wait(timeout=5):
            raise TimeoutError("没有并发启动工作")
        failed.set()
        raise marker

    try:
        function(may_fail, [0, 1], max_workers=2)
    except LookupError as error:
        _require(error is marker, "实验 26 应传播工作中的原始异常。")
    else:
        raise CheckFailure("实验 26 不应吞掉工作异常。")
    finally:
        failed.set()
    _require(ended.is_set(), "实验 26 抛出后仍有自己创建的工作未结束。")
    # 捕获普通异常后返回空结果，同样不是题目允许的结果。
    def always_fail(_):
        raise marker
    try:
        function(always_fail, [1], max_workers=1)
    except LookupError as error:
        _require(error is marker, "实验 26 改变了工作异常。")
    else:
        raise CheckFailure("实验 26 不应吞掉工作异常。")


async def _await_result(function, *args, **kwargs):
    result = function(*args, **kwargs)
    if not inspect.isawaitable(result):
        raise CheckFailure("当前实现应返回可等待对象，请检查异步接口。")
    return await asyncio.wait_for(result, timeout=8)


async def _no_leftovers(before: set[asyncio.Task]) -> None:
    await asyncio.sleep(0)
    pending = {task for task in asyncio.all_tasks() - before if not task.done()}
    if pending:
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        raise CheckFailure("实验 27 结束后遗留了本次实现创建的运行任务，请检查取消与等待。")


def _leaves(error: BaseException):
    if isinstance(error, BaseExceptionGroup):
        for child in error.exceptions:
            yield from _leaves(child)
    else:
        yield error


async def _check_async_map(namespace: dict[str, Any]) -> None:
    function = _callable(namespace, "async_map_limited")

    async def square(value):
        await asyncio.sleep(0)
        return value * value

    for invalid in (0, -1, True, 1.5, "2"):
        try:
            await _await_result(function, square, [], limit=invalid)
        except ValueError:
            pass
        else:
            raise CheckFailure("实验 27 未按题意拒绝无效 limit。")
    for values in ([], [7], [3, -1, 3, 0], list(range(11))):
        before_values = values.copy()
        before_tasks = asyncio.all_tasks()
        result = await _await_result(function, square, iter(values), limit=3)
        _require(type(result) is list and result == [value * value for value in values],
                 "实验 27 的结果位置、重复值或空输入不符合题意。")
        _require(values == before_values, "实验 27 不应自行修改输入。")
        await _no_leftovers(before_tasks)

    for limit in (1, 3):
        baseline = asyncio.all_tasks()
        ready = asyncio.Event()
        active = peak = reached = peak_tasks = 0

        async def operation(value, *, _baseline=baseline, _ready=ready, _limit=limit):
            nonlocal active, peak, reached, peak_tasks
            active += 1
            reached += 1
            peak = max(peak, active)
            peak_tasks = max(peak_tasks, len(asyncio.all_tasks() - _baseline))
            try:
                if reached >= _limit:
                    _ready.set()
                await _ready.wait()
                await asyncio.sleep(0)
                return value + 100
            finally:
                active -= 1

        result = await _await_result(function, operation, iter(range(40)), limit=limit)
        _require(result == list(range(100, 140)) and peak == limit and active == 0,
                 "实验 27 的并发推进或上限不符合题意。")
        _require(peak_tasks <= limit + 2,
                 "实验 27 建立的任务数量随输入增长，请检查工作者组织方式。")
        await _no_leftovers(baseline)

    started = asyncio.Event()
    cleaned = []
    marker = LookupError("check marker")

    async def may_fail(value):
        if value == 0:
            try:
                started.set()
                await asyncio.Event().wait()
            finally:
                cleaned.append(value)
        await started.wait()
        raise marker

    baseline = asyncio.all_tasks()
    try:
        await _await_result(function, may_fail, [0, 1], limit=2)
    except Exception as error:  # noqa: BLE001 - 允许普通异常或异常组，随后检查其成员。
        _require(any(leaf is marker for leaf in _leaves(error)),
                 "实验 27 未保留原始工作失败。")
    else:
        raise CheckFailure("实验 27 不应吞掉普通工作失败。")
    finally:
        await _no_leftovers(baseline)
    _require(cleaned == [0], "实验 27 失败退出前未完成其他工作的清理。")

    active_values, cleaned_values = set(), set()
    both_started = asyncio.Event()

    async def waiting(value):
        active_values.add(value)
        if len(active_values) == 2:
            both_started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleaned_values.add(value)

    baseline = asyncio.all_tasks()
    task = asyncio.create_task(function(waiting, range(8), limit=2))
    try:
        await asyncio.wait_for(both_started.wait(), timeout=5)
        task.cancel()
        try:
            await asyncio.wait_for(task, timeout=5)
        except asyncio.CancelledError:
            pass
        else:
            raise CheckFailure("实验 27 不应把调用方取消转换为普通成功。")
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await _no_leftovers(baseline)
    _require(active_values == cleaned_values,
             "实验 27 传播外部取消前未完成工作清理。")


async def _check_retry(namespace: dict[str, Any]) -> None:
    function = _callable(namespace, "async_retry")

    async def succeeds():
        pass

    for invalid in (0, -1, True, 2.5, "3"):
        try:
            await _await_result(function, succeeds, attempts=invalid)
        except ValueError:
            pass
        else:
            raise CheckFailure("实验 28 未按题意拒绝无效 attempts。")
    calls = 0

    async def eventual():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise TimeoutError("temporary")

    result = await _await_result(function, eventual, attempts=4)
    _require(result is None and calls == 3,
             "实验 28 的尝试次数、成功返回或提前停止不符合题意。")
    for retry_for, failure, attempts, expected_calls in (
        ((TimeoutError,), TimeoutError("last"), 3, 3),
        ((TimeoutError,), LookupError("unexpected"), 3, 1),
        ((), TimeoutError("no retry"), 4, 1),
        ((Exception,), ValueError("one attempt"), 1, 1),
    ):
        calls = 0

        async def fails(_failure=failure):
            nonlocal calls
            calls += 1
            raise _failure

        try:
            await _await_result(function, fails, attempts=attempts, retry_for=retry_for)
        except Exception as error:  # noqa: BLE001 - 检查器核对传出的异常身份。
            _require(error is failure and calls == expected_calls,
                     "实验 28 的异常范围、次数或原始异常身份不符合题意。")
        else:
            raise CheckFailure("实验 28 不应吞掉最终失败。")

    calls = 0

    async def cancelled():
        nonlocal calls
        calls += 1
        raise asyncio.CancelledError()

    try:
        await _await_result(function, cancelled, attempts=4, retry_for=(Exception,))
    except asyncio.CancelledError:
        _require(calls == 1, "实验 28 不应重复执行已取消的工作。")
    else:
        raise CheckFailure("实验 28 必须传播取消。")

    entered = asyncio.Event()
    cleaned = []

    async def waiting():
        try:
            entered.set()
            await asyncio.Event().wait()
        finally:
            cleaned.append(True)

    task = asyncio.create_task(function(waiting, attempts=3, retry_for=(Exception,)))
    try:
        await asyncio.wait_for(entered.wait(), timeout=5)
        task.cancel()
        try:
            await asyncio.wait_for(task, timeout=5)
        except asyncio.CancelledError:
            pass
        else:
            raise CheckFailure("实验 28 不应吞掉外部取消。")
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    _require(cleaned == [True], "实验 28 取消后没有完成当前操作的清理。")


def check_experiment(namespace: dict[str, Any], number: int) -> None:
    """同步入口只检查当前题，不要求其他题先完成。"""
    if type(number) is not int or not 1 <= number <= 28:
        raise ValueError("实验编号应为 1 到 28。")
    if number >= 27:
        raise ValueError("本题请使用 await check_async_experiment(globals(), 编号)。")
    try:
        if number <= 24:
            _check_observation(namespace, number)
        elif number == 25:
            _check_counter(namespace)
        else:
            _check_thread_map(namespace)
    except CheckFailure:
        raise
    except Exception as error:
        raise CheckFailure(f"实验 {number} 运行失败，请检查本题接口、等待关系和输入边界。") from error
    print(f"实验 {number} 客观检查通过；请保留预测并继续解释原因。")


async def check_async_experiment(namespace: dict[str, Any], number: int) -> None:
    """异步实现的单题入口，不创建或嵌套运行事件循环。"""
    if type(number) is not int or number not in (27, 28):
        raise ValueError("异步实现检查入口仅用于实验 27、28。")
    try:
        if number == 27:
            await _check_async_map(namespace)
        else:
            await _check_retry(namespace)
    except CheckFailure:
        raise
    except Exception as error:
        raise CheckFailure(f"实验 {number} 运行失败，请检查异步接口、任务收尾和异常规则。") from error
    print(f"实验 {number} 实现检查通过；请继续解释并发、取消与资源责任。")


async def run_checks(namespace: dict[str, Any]) -> None:
    """全部完成后的复查，不能代替紧随各题的检查。"""
    for number in range(1, 27):
        check_experiment(namespace, number)
    for number in (27, 28):
        await check_async_experiment(namespace, number)
    print("第 10 章 28 道客观检查通过；概念、等待关系和选型仍需口述复盘。")


if __name__ == "__main__":
    print("请在第10章代码实验.ipynb中逐题调用对应检查入口。")
