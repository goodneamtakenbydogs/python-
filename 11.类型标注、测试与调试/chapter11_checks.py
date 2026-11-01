"""第十一章逐题检查；核对客观结果，不改写原始预测或个人记录。"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, get_type_hints
from unittest.mock import Mock, call

UNFINISHED = "__未填写__"


class CheckFailure(AssertionError):
    """当前题的记录或实现尚未符合题意。"""


def _environment():
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "utf-8"
    return environment


def run_script(source: str) -> Any:
    """在独立脚本运行可见源码，读取其唯一 JSON 输出。"""
    with tempfile.TemporaryDirectory(prefix="python_ch11_") as directory:
        script = Path(directory) / "experiment.py"
        script.write_text(source, encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "-X", "utf8", str(script)], cwd=directory,
            env=_environment(), capture_output=True, text=True,
            encoding="utf-8", timeout=30, check=True,
        )
    return json.loads(result.stdout)


def run_pytest(source: str) -> dict[str, int]:
    """独立、临时的 pytest 运行；返回报告计数，不依赖耗时文本。"""
    with tempfile.TemporaryDirectory(prefix="pytest_ch11_") as directory:
        root = Path(directory)
        test_file = root / "test_subject.py"
        test_file.write_text(source, encoding="utf-8")
        config = root / "pytest.ini"
        config.write_text("[pytest]\n", encoding="utf-8")
        report = root / "result.xml"
        environment = _environment()
        environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        for name in ("PYTEST_ADDOPTS", "PYTEST_PLUGINS", "PYTEST_CURRENT_TEST"):
            environment.pop(name, None)
        result = subprocess.run(
            [sys.executable, "-X", "utf8", "-m", "pytest", str(test_file),
             "-c", str(config), "--rootdir", str(root), "--basetemp", str(root / "scratch"),
             "--junitxml", str(report), "-q", "-p", "no:cacheprovider"],
            cwd=root, env=environment, capture_output=True,
            text=True, encoding="utf-8", timeout=30, check=False,
        )
        if not report.exists():
            raise RuntimeError("pytest 没有生成实验报告，请确认当前内核已安装项目开发依赖。")
        tree = ET.parse(report).getroot()
        suites = [tree] if tree.tag == "testsuite" else list(tree.iter("testsuite"))
        summary = {name: sum(int(suite.get(name, "0")) for suite in suites)
                   for name in ("tests", "failures", "errors", "skipped")}
        summary["returncode"] = result.returncode
        return summary


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
    if not isinstance(mapping, dict) or len(mapping) != count:
        raise CheckFailure(f"请填写并运行本题全部{phase}字段，保留两位编号。")
    result = {}
    for label, value in mapping.items():
        match = re.match(r"^(\d{2})\.\s+", label) if isinstance(label, str) else None
        if match is None or match.group(1) in result:
            raise CheckFailure(f"{phase}字段“{label}”的编号缺失或重复。")
        if _unfinished(value):
            raise CheckFailure(f"{phase}字段“{label}”尚未填写，请替换包括引号的整个占位字符串。")
        result[match.group(1)] = (label, value)
    if set(result) != {f"{index:02d}" for index in range(1, count + 1)}:
        raise CheckFailure(f"本题{phase}字段编号不完整。")
    return result


def _matches(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, (tuple, list)):
        return len(actual) == len(expected) and all(
            _matches(left, right) for left, right in zip(actual, expected)
        )
    return actual == expected


OBSERVATIONS = {
    1: ["haha", 6], 2: ["anonymous", "", "TypeError"], 3: ["str", True, 42],
    4: [6, 0, [1, 2, 3]], 5: [10, "Ada", "StopIteration"], 6: [True, 7],
    7: [True, True, True], 8: ["AssertionError", -1], 9: [2, True, 0, 0],
    10: [2, 1, 1, False], 11: [["prepare", "cleanup"], 1], 12: [3, 0, 0],
    13: [2, 0, 0], 14: [1, 0, 1], 15: [1, 1, 1],
    16: ["ready", "TimeoutError", 2, ["C-1", "C-2"]], 17: ["ready", "TypeError", 1],
    18: [True, 456, True], 19: [0, 1, True], 20: [True, True],
    21: [["WARNING:slow"]], 22: [True, True, True],
    23: [["load", "parse"], "RuntimeError", "ValueError"], 24: [2, 6, True],
    25: [[0, 2, 4, 6], 4], 26: [6, True],
}


def _require(condition, message):
    if not condition:
        raise CheckFailure(message)


def _function(namespace, name):
    function = namespace.get(name)
    _require(callable(function), f"找不到 {name}，请先运行本题定义单元格。")
    return function


def _check_observation(namespace, number):
    expected = OBSERVATIONS[number]
    _fields(namespace, f"prediction_{number:02d}", len(expected), "预测")
    fields = _fields(namespace, f"observation_{number:02d}", len(expected), "实际观察")
    for index, target in enumerate(expected, 1):
        label, value = fields[f"{index:02d}"]
        try:
            correct = _matches(value, target)
        except (TypeError, ValueError, RecursionError):
            correct = False
        _require(correct, f"实际观察字段“{label}”与本题运行结果不一致，请重新观察。")


def _expect_error(function, arguments, expected_type, message):
    try:
        function(*arguments)
    except expected_type:
        return
    raise CheckFailure(message)


def _check_parse_port(namespace):
    function = _function(namespace, "parse_port")
    hints = get_type_hints(function)
    _require(hints.get("text") is str and hints.get("return") is int,
             "实验 27 请保留题面类型标注，并区分标注与运行时校验。")
    for text, expected in (("1", 1), ("65535", 65535), (" 8080\t", 8080),
                           ("00080", 80), ("\n42\r", 42)):
        result = function(text)
        _require(type(result) is int and result == expected,
                 f"实验 27 对输入 {text!r} 的解析不符合接口。")
    for text in ("", " ", "0", "000", "65536", "-1", "+80", "8.0", "8_0", "１２", "²", "1 2", "abc"):
        _expect_error(function, (text,), ValueError, f"实验 27 未按约定拒绝格式或范围输入 {text!r}。")
    for value in (None, True, 80, 80.0, b"80", ["80"]):
        _expect_error(function, (value,), TypeError, "实验 27 未按约定拒绝输入类型。")
    class TextSubclass(str):
        pass
    _expect_error(function, (TextSubclass("80"),), TypeError,
                  "实验 27 请核对精确输入类型的约定。")


def _check_collect_labels(namespace):
    function = _function(namespace, "collect_labels")
    hints = get_type_hints(function)
    _require({"case_ids", "reader", "return"} <= hints.keys() and hints["return"] == list[str],
             "实验 28 请保留题面接口标注。")
    reader = Mock()
    result = function(iter([]), reader)
    _require(type(result) is list and result == [] and not reader.called,
             "实验 28 的空输入行为不符合接口。")
    source = [{"label": " login "}, {"label": "order"}, {"label": ""}]
    before = [item.copy() for item in source]
    reader = Mock(side_effect=source)
    ids = ["A", "B", "A"]
    result = function(iter(ids), reader)
    _require(type(result) is list and result == ["LOGIN", "ORDER", ""],
             "实验 28 的转换、位置或重复输入处理不符合接口。")
    _require(reader.call_args_list == [call("A"), call("B"), call("A")],
             "实验 28 的依赖调用次序或次数不符合接口。")
    _require(source == before and ids == ["A", "B", "A"], "实验 28 不应自行修改输入或依赖数据。")
    _expect_error(function, (["A"], Mock(return_value={})), KeyError,
                  "实验 28 不应吞掉缺失 label。")
    for value in (None, 7, True, [], b"text"):
        _expect_error(function, (["A"], Mock(return_value={"label": value})), TypeError,
                      "实验 28 未校验实际 label 类型。")
    marker = TimeoutError("dependency marker")
    reader = Mock(side_effect=marker)
    try:
        function(["A", "B"], reader)
    except TimeoutError as error:
        _require(error is marker and reader.call_args_list == [call("A")],
                 "实验 28 未保留原始依赖异常或失败后继续读取。")
    else:
        raise CheckFailure("实验 28 不应吞掉依赖失败。")


def _clamp(value, lower, upper):
    if lower > upper:
        raise ValueError("invalid range")
    if value < lower:
        return lower
    if value > upper:
        return upper
    return value


def _mutations():
    def identity(value, lower, upper):
        return value

    def lower_only(value, lower, upper):
        return max(lower, value)

    def upper_only(value, lower, upper):
        return min(upper, value)

    def fixed_bounds(value, lower, upper):
        return min(10, max(0, value))

    def equal_range(value, lower, upper):
        return value if lower == upper else _clamp(value, lower, upper)

    def inside_changed(value, lower, upper):
        result = _clamp(value, lower, upper)
        return result + 1 if lower < value < upper else result

    def no_invalid_error(value, lower, upper):
        return min(upper, max(lower, value))

    def float_result(value, lower, upper):
        return float(_clamp(value, lower, upper))

    return [identity, lower_only, upper_only, fixed_bounds, equal_range, inside_changed,
            no_invalid_error, float_result]


def _check_cases(namespace):
    function = _function(namespace, "clamp_cases")
    cases = function()
    _require(type(cases) is list and 1 <= len(cases) <= 64,
             "实验 29 的返回集合不符合题面接口。")
    _require(function() is not cases, "实验 29 每次应返回新列表。")
    for index, row in enumerate(cases, 1):
        _require(type(row) is tuple and len(row) == 4 and all(type(value) is int for value in row),
                 f"实验 29 的第 {index} 条用例字段不符合接口。")
        value, lower, upper, expected = row
        _require(lower <= upper and expected == _clamp(value, lower, upper),
                 f"实验 29 的第 {index} 条预期与声明的约定不一致。")
    predicates = [
        lambda v, lo, hi: v < lo, lambda v, lo, hi: v == lo,
        lambda v, lo, hi: lo < v < hi, lambda v, lo, hi: v == hi,
        lambda v, lo, hi: v > hi, lambda v, lo, hi: lo == hi,
        lambda v, lo, hi: lo < 0 < hi,
    ]
    _require(all(any(predicate(*row[:3]) for row in cases) for predicate in predicates),
             "实验 29 仍缺少题面要求的某类正常或边界场景。")
    for mutant in _mutations()[:6]:
        _require(any(mutant(*row[:3]) != row[3] for row in cases),
                 "实验 29 的用例还不能区分某类典型错误，请重新检查输入与预期选择。")


def _check_contract_test(namespace):
    function = _function(namespace, "assert_clamp_contract")

    def equivalent(value, lower, upper):
        if lower > upper:
            raise ValueError("range")
        return min(upper, max(lower, value))

    for correct in (_clamp, equivalent):
        result = function(correct)
        _require(result is None, "实验 30 对正确候选应正常完成并返回 None。")
    for mutant in _mutations():
        try:
            function(mutant)
        except Exception:  # noqa: BLE001 - 候选的意外异常也是测试失败，正确候选已另行验证。
            rejected = True
        else:
            rejected = False
        _require(rejected, "实验 30 放过了某类典型错误；请检查返回、边界和异常断言。")
    calls = []

    def recording(value, lower, upper):
        calls.append((value, lower, upper))
        return _clamp(value, lower, upper)

    function(recording)
    _require(bool(calls) and all(all(type(value) is int for value in row) for row in calls),
             "实验 30 必须实际执行候选，并遵守题面输入类型。")
    coverage = [
        lambda v, lo, hi: lo < hi and v == lo,
        lambda v, lo, hi: lo < hi and v == hi,
        lambda v, lo, hi: lo < 0 < hi,
        lambda v, lo, hi: lo > hi,
    ]
    _require(all(any(predicate(*row) for row in calls) for predicate in coverage),
             "实验 30 的实际调用还缺少题面指定场景。")


IMPLEMENTATIONS = {27: _check_parse_port, 28: _check_collect_labels,
                   29: _check_cases, 30: _check_contract_test}


def check_experiment(namespace: dict[str, Any], number: int) -> None:
    """单题检查；不依赖其他题是否完成，也不修改记录。"""
    if type(number) is not int or not 1 <= number <= 30:
        raise ValueError("实验编号应为 1 到 30。")
    try:
        if number <= 26:
            _check_observation(namespace, number)
        else:
            IMPLEMENTATIONS[number](namespace)
    except CheckFailure:
        raise
    except Exception as error:
        raise CheckFailure(f"实验 {number} 运行失败，请检查当前题的接口、边界和异常约定。") from error
    print(f"实验 {number} 客观检查通过；请继续解释预期依据和工具边界。")


def run_checks(namespace: dict[str, Any]) -> None:
    """全部完成后的补充复查，不能代替逐题即时检查。"""
    for number in range(1, 31):
        check_experiment(namespace, number)
    print("第 11 章 30 道客观检查通过；类型关系、测试设计与诊断过程仍需口述。")


if __name__ == "__main__":
    print("请在第11章代码实验.ipynb中逐题调用 check_experiment()。")
