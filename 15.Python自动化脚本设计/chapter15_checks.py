"""第十五章客观检查；设计理由、范围与故障解释仍需人工评审。"""

from __future__ import annotations

import copy
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

UNFINISHED = "__未填写__"


class CheckFailure(AssertionError):
    """当前题的记录或实现不符合题面。"""


def load_example():
    """从本章固定位置加载公开示例；不依赖 Notebook 的工作目录或 sys.path 修改。"""
    name = "_chapter15_sample_check"
    if name not in sys.modules:
        path = Path(__file__).parent / "示例脚本" / "sample_check.py"
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            sys.modules.pop(name, None)
            raise
    return sys.modules[name]


def _require(condition, message):
    if not condition:
        raise CheckFailure(message)


def _unfinished(value):
    if isinstance(value, str):
        return value == UNFINISHED
    if isinstance(value, dict):
        return any(_unfinished(item) for item in value.values())
    if isinstance(value, (tuple, list)):
        return any(_unfinished(item) for item in value)
    return False


def _fields(namespace, name, count, phase):
    mapping = namespace.get(name)
    _require(isinstance(mapping, dict) and len(mapping) == count,
             f"请填写并运行本题全部{phase}字段，保留两位编号。")
    result = {}
    for label, value in mapping.items():
        match = re.match(r"^(\d{2})\.\s+", label) if isinstance(label, str) else None
        _require(match is not None and match.group(1) not in result,
                 f"{phase}字段“{label}”的编号缺失或重复。")
        _require(not _unfinished(value), f"{phase}字段“{label}”尚未填写，请替换整个占位字符串。")
        result[match.group(1)] = (label, value)
    _require(set(result) == {f"{index:02d}" for index in range(1, count + 1)},
             f"本题{phase}字段编号不完整。")
    return result


def _matches(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, (tuple, list)):
        return len(actual) == len(expected) and all(_matches(a, e) for a, e in zip(actual, expected))
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(_matches(actual[key], value)
                                                      for key, value in expected.items())
    return actual == expected


OBSERVATIONS = {
    1: [["A B", "; literal"], 0], 2: [0, "中文 SAMPLE", "note"],
    3: [4, False], 4: [0, "JSONDecodeError"],
    5: [[True, False, False, False]], 6: [0, 3, True],
    7: [[False, False, False, False, True]], 8: ["sample", True],
    9: ["inner", "outer", False], 10: ["bytes", '{"count":', False],
    11: [2, False], 12: [1, True], 13: [6, False],
    14: [2, [1.0, 0.75], [0.25]], 15: ["BudgetExpired", []],
    16: ["BudgetExpired", [1.0], 1], 17: ["AttemptsExhausted", 3, 2],
    18: ["protocol_error", 1], 19: ["passed", 2, [1.0, 0.5]],
    20: [True, 1], 21: ["ValueError", ["A+", "B+", "B-", "A-"]],
    22: ["PermissionError", "old", ["report.json"]],
    23: [[("C-B", 40), ("C-D", 30)]], 24: [True, False, "done"],
}


def _check_observation(namespace, number):
    expected = OBSERVATIONS[number]
    _fields(namespace, f"prediction_{number:02d}", len(expected), "预测")
    observed = _fields(namespace, f"observation_{number:02d}", len(expected), "实际观察")
    for index, target in enumerate(expected, 1):
        label, value = observed[f"{index:02d}"]
        try:
            correct = _matches(value, target)
        except (TypeError, ValueError, RecursionError):
            correct = False
        _require(correct, f"实际观察字段“{label}”与本题运行结果不一致，请重新观察。")


def _function(namespace, name):
    function = namespace.get(name)
    _require(callable(function), f"请先定义并运行本题的 {name}。")
    return function


def _expect(function, error_type, label):
    try:
        function()
    except error_type as error:
        return error
    except Exception as error:
        raise CheckFailure(f"{label} 的异常处理不符合题面。") from error
    raise CheckFailure(f"{label} 未按题面拒绝输入或结束等待。")


def _check_config(namespace):
    function = _function(namespace, "resolve_check_config")
    rows = [({}, {}, {}, {"limit": 3, "timeout": 1.0}),
            ({"limit": 0, "timeout": 2}, {}, {}, {"limit": 0, "timeout": 2.0}),
            ({"limit": 1}, {"CH15_LIMIT": "2", "CH15_TIMEOUT": "0.5"}, {"limit": 4},
             {"limit": 4, "timeout": 0.5}),
            ({"limit": 1, "timeout": 2}, {}, {"limit": None, "timeout": None}, {"limit": 1, "timeout": 2.0}),
            ({}, {"UNRELATED": "ignored", "CH15_LIMIT": " 0 "}, {}, {"limit": 0, "timeout": 1.0})]
    for index, (file_values, environment, cli, expected) in enumerate(rows, 1):
        before = copy.deepcopy((file_values, environment, cli))
        actual = function(file_values, environment, cli)
        _require(_matches(actual, expected), f"实验 25 第 {index} 组覆盖关系或返回接口不符。")
        _require((file_values, environment, cli) == before, "实验 25 不应修改输入配置。")
        again = function(file_values, environment, cli)
        _require(again is not actual, "实验 25 每次应返回新字典。")
    invalid = [({"other": 1}, {}, {}), ({}, {}, {"other": None}),
               ({"limit": True}, {}, {}), ({"limit": -1}, {}, {}), ({"limit": 1.0}, {}, {}),
               ({"timeout": None}, {}, {}), ({"timeout": "1"}, {}, {}),
               ({"timeout": float("nan")}, {}, {}), ({"timeout": float("inf")}, {}, {}),
               ({}, {"CH15_TIMEOUT": "0"}, {}), ({}, {"CH15_LIMIT": "2.5"}, {}),
               ({}, {"CH15_LIMIT": 2}, {}), ({"limit": -1}, {}, {"limit": 2}),
               ({}, {"CH15_TIMEOUT": "bad"}, {"timeout": 2}), ({}, {}, {"timeout": False})]
    for index, args in enumerate(invalid, 1):
        _expect(lambda args=args: function(*args), ValueError, f"实验 25 非法配置组 {index}")


def _check_classification(namespace):
    function = _function(namespace, "classify_probe_result")
    cases = [
        (3, "not JSON", 2, "execution_error"), (-1, '{"count":2}', 2, "execution_error"),
        (0, '{"count":2}', 2, "passed"), (0, '{"count":0}', 0, "passed"),
        (0, '{"count":1}', 2, "check_failed"), (0, '{"count":9}', 2, "check_failed"),
        (0, "{", 2, "protocol_error"), (0, "[]", 2, "protocol_error"),
        (0, "{}", 2, "protocol_error"), (0, '{"count":true}', 1, "protocol_error"),
        (0, '{"count":2.0}', 2, "protocol_error"), (0, '{"count":-1}', 2, "protocol_error"),
        (0, '{"count":NaN}', 2, "protocol_error"),
        (0, '{"count":2,"extra":0}', 2, "protocol_error"),
    ]
    for index, (code, text, expected_count, category) in enumerate(cases, 1):
        _require(function(code, text, expected_count) == category,
                 f"实验 26 第 {index} 组的阶段或结果类别不符合约定。")
    for value in (True, 1.0, "0"):
        _expect(lambda value=value: function(value, "{}", 0), TypeError, "实验 26 退出状态类型")
    for value in (True, "2", 2.0):
        _expect(lambda value=value: function(0, "{}", value), TypeError, "实验 26 预期数量类型")
    _expect(lambda: function(0, "{}", -1), ValueError, "实验 26 负预期数量")


class _Clock:
    def __init__(self, *, frozen=False, oversleep=0):
        self.now = 0.0
        self.sleeps = []
        self.frozen = frozen
        self.oversleep = oversleep

    def __call__(self):
        return self.now

    def wait(self, seconds):
        _require(type(seconds) in (int, float) and seconds > 0, "实验 27 等待值不符合题面。")
        self.sleeps.append(seconds)
        _require(len(self.sleeps) <= 8, "实验 27 仍未按次数或预算停止等待。")
        if not self.frozen:
            self.now += seconds + self.oversleep


def _check_wait(namespace):
    function = _function(namespace, "wait_until_ready")

    def run(sequence, *, budget=1.0, interval=0.25, max_attempts=3, timer=None, cost=0):
        timer = _Clock() if timer is None else timer
        states = iter(sequence)
        limits = []

        def fetch(remaining):
            limits.append(remaining)
            _require(len(limits) <= max_attempts + 1, "实验 27 查询没有在次数上限结束。")
            _require(type(remaining) in (int, float) and 0 < remaining <= budget - timer.now,
                     "实验 27 没有传递正确的剩余预算。")
            timer.now += cost
            value = next(states, "pending")
            if isinstance(value, BaseException):
                raise value
            return value

        kwargs = {"budget": budget, "interval": interval, "max_attempts": max_attempts,
                  "clock": timer, "wait": timer.wait}
        return lambda: function(fetch, **kwargs), timer, limits

    call, timer, limits = run(["ready"])
    _require(_matches(call(), ("ready", 1)) and not timer.sleeps and limits == [1.0],
             "实验 27 首次就绪路径不符合约定。")
    call, timer, limits = run(["pending", "ready"])
    _require(_matches(call(), ("ready", 2)) and timer.sleeps == [0.25] and limits == [1.0, 0.75],
             "实验 27 正常轮询、计数或间隔不符合约定。")
    call, timer, limits = run([TimeoutError("controlled"), "ready"], cost=0.125)
    _require(_matches(call(), ("ready", 2)) and limits == [1.0, 0.625],
             "实验 27 可重试读取超时路径不符合约定。")
    call, timer, limits = run(["pending"], interval=2)
    _expect(call, TimeoutError, "实验 27 截断等待")
    _require(timer.sleeps == [1.0] and len(limits) == 1, "实验 27 到期后不应再启动查询。")
    call, timer, limits = run(["ready"], cost=1)
    _expect(call, TimeoutError, "实验 27 截止点的迟到结果")
    _require(len(limits) == 1 and not timer.sleeps, "实验 27 迟到结果后不应继续等待。")
    call, timer, limits = run(["pending"], timer=_Clock(frozen=True), max_attempts=3)
    _expect(call, TimeoutError, "实验 27 时钟不前进")
    _require(len(limits) == 3 and len(timer.sleeps) == 2, "实验 27 最后一次尝试后仍有多余动作。")
    call, timer, limits = run(["pending"], timer=_Clock(oversleep=2))
    _expect(call, TimeoutError, "实验 27 等待晚返回")
    _require(len(limits) == 1, "实验 27 等待后已经超时，不能再查询。")
    for value, error_type in (("failed", RuntimeError), ("unknown", ValueError)):
        call, timer, limits = run([value])
        _expect(call, error_type, "实验 27 终止状态")
        _require(len(limits) == 1 and not timer.sleeps, "实验 27 终止状态不应重试。")
    original = LookupError("unexpected")
    call, timer, limits = run([original])
    _require(_expect(call, LookupError, "实验 27 未预期错误") is original,
             "实验 27 应原样传播未预期错误。")
    _require(len(limits) == 1 and not timer.sleeps, "实验 27 不应重试未预期错误。")
    invalid = [(0, 0.1, 2), (1, 0, 2), (float("nan"), 0.1, 2),
               (1, float("inf"), 2), (True, 0.1, 2), (1, 0.1, 0), (1, 0.1, True)]
    for budget, interval, attempts in invalid:
        def forbidden(*args, **kwargs):
            raise CheckFailure("实验 27 应在调用任何协作者前验证配置。")
        _expect(lambda budget=budget, interval=interval, attempts=attempts: function(forbidden, budget=budget, interval=interval,
                                 max_attempts=attempts, clock=forbidden, wait=forbidden),
                ValueError, "实验 27 参数校验")


def _check_executor(namespace):
    function = _function(namespace, "execute_command")
    for code, stdout, stderr in ((0, "中文\n", "note"), (4, "partial", "error"), (0, "", "")):
        argv = ["sample", "a b; literal"]
        calls = []

        def runner(arguments, *, _calls=calls, _code=code, _stdout=stdout, _stderr=stderr, **kwargs):
            _calls.append((arguments, kwargs))
            return subprocess.CompletedProcess(arguments, _code, _stdout, _stderr)

        result = function(argv, timeout=0.5, runner=runner)
        _require(_matches(result, {"argv": tuple(argv), "returncode": code, "stdout": stdout, "stderr": stderr}),
                 "实验 28 执行记录丢失字段、类型或非零退出信息。")
        _require(len(calls) == 1 and calls[0][0] == argv and calls[0][0] is not argv,
                 "实验 28 应只调用一次，并用新的实参列表。")
        _require(argv == ["sample", "a b; literal"], "实验 28 不应修改调用方实参。")
        required = {"capture_output": True, "text": True, "encoding": "utf-8", "check": False,
                    "shell": False, "timeout": 0.5}
        _require(_matches(calls[0][1], required), "实验 28 的执行选项不符合题面接口。")
    for original in (subprocess.TimeoutExpired(["sample"], 0.5, output=b"partial"),
                     FileNotFoundError("missing"), RuntimeError("unexpected")):
        calls = []

        def runner(*args, _calls=calls, _original=original, **kwargs):
            _calls.append("call")
            raise _original

        caught = _expect(lambda: function(["sample"], timeout=1, runner=runner), type(original),
                         "实验 28 异常传播")
        _require(caught is original and calls == ["call"], "实验 28 不应吞错、重试或替换原异常。")
    for argv, timeout in (([], 1), ("sample", 1), ([""], 1), (["sample", 2], 1),
                          (["sample"], 0), (["sample"], True), (["sample"], float("nan"))):
        def forbidden(*args, **kwargs):
            raise CheckFailure("实验 28 无效输入不应启动执行器。")
        _expect(lambda argv=argv, timeout=timeout: function(argv, timeout=timeout, runner=forbidden), ValueError, "实验 28 参数校验")
    actual = function([sys.executable, "-X", "utf8", "-c", "print('sample')"], timeout=5,
                      runner=subprocess.run)
    _require(actual["returncode"] == 0 and actual["stdout"].strip() == "sample",
             "实验 28 在真实本地子进程上的接口不一致。")


IMPLEMENTATIONS = {25: _check_config, 26: _check_classification, 27: _check_wait, 28: _check_executor}


def check_experiment(namespace, number):
    """只检查当前题，不改写学习记录。"""
    if type(number) is not int or not 1 <= number <= 28:
        raise ValueError("实验编号应在 1～28 之间")
    try:
        if number <= 24:
            _check_observation(namespace, number)
        else:
            IMPLEMENTATIONS[number](namespace)
    except CheckFailure:
        raise
    except Exception as error:
        raise CheckFailure(f"实验 {number} 检查未完成（{type(error).__name__}），请复查本题接口与运行。") from error
    print(f"实验 {number} 客观检查通过；原因解释与设计评审仍需自己完成。")


def run_checks(namespace):
    for number in range(1, 29):
        check_experiment(namespace, number)
    print("28 道客观实验复查通过；不代表综合方案与口述已完成。")
