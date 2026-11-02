"""第十六章客观检查；设计、兼容策略与交付理由仍需人工评审。"""

from __future__ import annotations

import copy
import importlib
import importlib.util
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

UNFINISHED = "__未填写__"


class CheckFailure(AssertionError):
    pass


class RecordProblem(ValueError):
    """实验 25 已提供的错误容器，line 为输入中的物理位置。"""

    def __init__(self, message, *, line):
        super().__init__(message)
        self.line = line


def example_root():
    return Path(__file__).parent / "示例工具"


def load_example(module="engine"):
    """按独立包名加载本章公开源码，不依赖正式安装；不构成交付验收。"""
    name = "_chapter16_study_results"
    if name not in sys.modules:
        package = example_root() / "src" / "study_results"
        spec = importlib.util.spec_from_file_location(name, package / "__init__.py",
                                                     submodule_search_locations=[str(package)])
        value = importlib.util.module_from_spec(spec)
        sys.modules[name] = value
        try:
            spec.loader.exec_module(value)
        except BaseException:
            sys.modules.pop(name, None)
            raise
    return sys.modules[name] if module is None else importlib.import_module(f"{name}.{module}")


def _require(condition, message):
    if not condition:
        raise CheckFailure(message)


def _unfinished(value):
    if isinstance(value, str):
        return value == UNFINISHED
    if isinstance(value, dict):
        return any(_unfinished(item) for item in value.values())
    if isinstance(value, (list, tuple)):
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
    _require(set(result) == {f"{index:02d}" for index in range(1, count + 1)}, f"本题{phase}编号不完整。")
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
    1: [[], True], 2: ["bool", "ValueError"], 3: [["local"]],
    4: [(), 4, True], 5: ["ConfigError"], 6: ["C-A", 0.0, 5],
    7: [1, 3], 8: [2, 6, True], 9: [2, 1, "failed"],
    10: ["InputError", 3], 11: [3, 1, {"passed": 1, "failed": 0, "skipped": 0}, 0.25],
    12: [1, 0, 0.0], 13: [2, []], 14: ["InputError", 3],
    15: [1, "0.1.0", "R-demo"], 16: [1, 2, "R-demo", "summary_finished"],
    17: [4, "", "report"], 18: [3, ["closed"], ""],
    19: ["ReportError", "old", ["keep.tmp", "report.json"]],
    20: [[(0, "completed", 30, None), (1, "error", None, "ValueError"), (2, "completed", 10, None)]],
    21: [0, [0], ["closed"]], 22: ["Cancelled", []],
    23: ["study-results-demo", "study_results.cli:main", True], 24: [True, True, 100],
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
        raise CheckFailure(f"{label} 的异常接口不符合题面。") from error
    raise CheckFailure(f"{label} 未按题面拒绝或传播错误。")


def _check_lines(namespace):
    function = _function(namespace, "parse_case_lines")
    lines = ["\n", '{"case_id":" C-A ","status":"passed","duration":0}\n',
             '{"case_id":"C-B","status":"skipped","duration":86400}\n']
    original = list(lines)
    expected = [{"case_id": "C-A", "status": "passed", "duration": 0.0, "line": 2},
                {"case_id": "C-B", "status": "skipped", "duration": 86400.0, "line": 3}]
    _require(_matches(function(iter(lines)), expected), "实验 25 的解析、规范化或物理行号不符合接口。")
    _require(lines == original, "实验 25 不应修改输入。")
    first, second = function(lines), function(lines)
    _require(first is not second and all(a is not b for a, b in zip(first, second)),
             "实验 25 每次应建立新的结果记录。")
    _require(function(iter(())) == [] and function([" ", "\n"]) == [], "实验 25 空输入处理不符合约定。")
    invalid = ["{", "[]", "{}", '{"case_id":"","status":"passed","duration":0}',
               '{"case_id":"C-X","status":"unknown","duration":0}',
               '{"case_id":"C-X","status":"passed","duration":true}',
               '{"case_id":"C-X","status":"passed","duration":-1}',
               '{"case_id":"C-X","status":"passed","duration":86401}',
               '{"case_id":"C-X","status":"passed","duration":NaN}',
               '{"case_id":"C-X","status":"passed","duration":1,"extra":0}', None]
    for index, bad in enumerate(invalid, 1):
        error = _expect(lambda bad=bad: function([lines[1], "\n", bad]), RecordProblem,
                        f"实验 25 错误输入组 {index}")
        _require(error.line == 3, "实验 25 应报告物理行号，不能只计算有效条目。")
    duplicate = [lines[1], "\n", '{"case_id":"C-A","status":"failed","duration":1}']
    error = _expect(lambda: function(duplicate), RecordProblem, "实验 25 规范化后重复编号")
    _require(error.line == 3, "实验 25 重复编号的错误位置不符合约定。")


def _check_summary(namespace):
    function = _function(namespace, "summarize_cases")
    rows = [{"case_id": "C-A", "status": "passed", "duration": 0.1},
            {"case_id": "C-B", "status": "failed", "duration": 0.2},
            {"case_id": "C-C", "status": "skipped", "duration": 0.3}]
    for selected in ((), ("passed",), ("failed", "skipped"), ("passed", "failed", "skipped")):
        before = copy.deepcopy(rows)
        actual = function(iter(rows), statuses=selected)
        chosen = [row for row in rows if row["status"] in selected]
        expected = {"input_total": 3, "selected_total": len(chosen),
                    "counts": {name: sum(row["status"] == name for row in chosen)
                               for name in ("passed", "failed", "skipped")},
                    "duration_seconds": 0.0}
        _require(type(actual) is dict and set(actual) == set(expected), "实验 26 返回字段不符合接口。")
        duration = actual["duration_seconds"]
        _require(type(duration) is float and math.isfinite(duration) and
                 math.isclose(duration, math.fsum(row["duration"] for row in chosen), abs_tol=1e-12, rel_tol=1e-12),
                 "实验 26 的选中耗时统计不符合约定。")
        copy_result = dict(actual, duration_seconds=0.0)
        _require(_matches(copy_result, expected), "实验 26 输入总数、筛选数量或分类计数不符。")
        _require(rows == before, "实验 26 不应修改输入记录。")
    empty = function(iter(()))
    _require(_matches(empty, {"input_total": 0, "selected_total": 0,
                             "counts": {"passed": 0, "failed": 0, "skipped": 0}, "duration_seconds": 0.0}),
             "实验 26 空输入的结构不符合约定。")
    again = function(iter(()))
    _require(again is not empty and again["counts"] is not empty["counts"], "实验 26 不能共享可变返回记录。")
    duplicate = [rows[1], dict(rows[1])]
    _expect(lambda: function(duplicate, statuses=("passed",)), ValueError, "实验 26 未选中数据的重复编号")
    for selected in (("unknown",), ("passed", "passed"), "passed", [True]):
        _expect(lambda selected=selected: function([], statuses=selected), ValueError, "实验 26 筛选配置")


def _check_writer(namespace):
    function = _function(namespace, "write_json_report")
    with TemporaryDirectory(prefix="chapter16-writer-") as directory:
        root = Path(directory)
        destination = root / "report.json"
        unrelated = root / "keep.tmp"
        unrelated.write_text("keep", encoding="utf-8")
        record = {"run_id": "R-demo", "text": "虚构", "counts": {"passed": 1}}
        before = copy.deepcopy(record)
        calls = []

        def replace(source, target):
            source, target = Path(source), Path(target)
            _require(source.parent.resolve() == root.resolve() and source != destination,
                     "实验 27 临时文件应位于目标同目录且不能就是目标。")
            _require(target == destination and json.loads(source.read_text(encoding="utf-8")) == record,
                     "实验 27 应在完整写入后才提交到指定目标。")
            calls.append((source, target))
            os.replace(source, target)

        _require(function(destination, record, replace=replace) is None, "实验 27 成功返回值不符合接口。")
        _require(record == before and len(calls) == 1, "实验 27 不能修改报告或重复提交。")
        _require(json.loads(destination.read_text(encoding="utf-8")) == record, "实验 27 提交后内容不符。")
        destination.write_text("old", encoding="utf-8")
        original = PermissionError("controlled")

        def fail(source, target):
            raise original

        _require(_expect(lambda: function(destination, record, replace=fail), PermissionError,
                         "实验 27 提交失败") is original, "实验 27 应保留原异常对象。")
        _require(destination.read_text(encoding="utf-8") == "old", "实验 27 失败后旧报告未保持。")
        _require(sorted(path.name for path in root.iterdir()) == ["keep.tmp", "report.json"],
                 "实验 27 遗漏临时清理或触碰了其他文件。")
        _require(unrelated.read_text(encoding="utf-8") == "keep", "实验 27 不应清理其他文件。")
        for invalid, error_type in (({"bad": object()}, TypeError), ({"bad": float("nan")}, ValueError)):
            _expect(lambda invalid=invalid: function(destination, invalid, replace=replace), error_type,
                    "实验 27 序列化失败")
            _require(destination.read_text(encoding="utf-8") == "old", "实验 27 序列化失败影响了旧报告。")
            _require(sorted(path.name for path in root.iterdir()) == ["keep.tmp", "report.json"],
                     "实验 27 序列化失败后仍遗留临时文件。")


_CANDIDATE = '''
def count_statuses(statuses):
    result = {"passed": 0, "failed": 0, "skipped": 0}
    for status in statuses:
        if type(status) is not str or status not in result:
            raise ValueError("invalid status")
        result[status] += 1
    return result
'''


def _run_candidate(test_source, implementation):
    with TemporaryDirectory(prefix="chapter16-tests-") as directory:
        root = Path(directory)
        (root / "candidate.py").write_text(implementation, encoding="utf-8")
        (root / "test_candidate.py").write_text(test_source, encoding="utf-8")
        (root / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
        environment = os.environ.copy()
        for key in ("PYTHONPATH", "PYTEST_ADDOPTS", "PYTEST_PLUGINS"):
            environment.pop(key, None)
        environment.update(PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
        return subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=root,
                              env=environment, capture_output=True, text=True, encoding="utf-8",
                              check=False, timeout=25, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _check_tests(namespace):
    source = _function(namespace, "make_summary_test_source")()
    _require(isinstance(source, str) and bool(source.strip()), "实验 28 应返回完整测试源码。")
    compile(source, "<exercise28>", "exec")
    correct = _run_candidate(source, _CANDIDATE)
    _require(correct.returncode == 0 and "passed" in correct.stdout and "skipped" not in correct.stdout
             and "xfailed" not in correct.stdout and "xpassed" not in correct.stdout,
             "实验 28 的测试未让正确候选正常通过，请局部运行并定位。")
    mutants = [_CANDIDATE.replace('result[status] += 1', 'result["passed"] += 1'),
               _CANDIDATE.replace('"skipped": 0', '"skipped": False'),
               _CANDIDATE.replace('raise ValueError("invalid status")', 'continue'),
               _CANDIDATE.replace('return result', 'return {key: value for key, value in result.items() if value}'),
               _CANDIDATE.replace('for status in statuses:', 'for status in list(statuses):\n        break\n    for status in statuses:'),
               _CANDIDATE.replace('result[status] += 1', 'result[status] = 1')]
    for index, candidate in enumerate(mutants, 1):
        result = _run_candidate(source, candidate)
        _require(result.returncode == 1 and re.search(r"\b[1-9]\d* failed\b", result.stdout) is not None
                 and re.search(r"\b\d+ errors?\b", result.stdout) is None,
                 f"实验 28 对第 {index} 类错误缺少有效区分，请复查输入和断言。")


IMPLEMENTATIONS = {25: _check_lines, 26: _check_summary, 27: _check_writer, 28: _check_tests}


def check_experiment(namespace, number):
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
    print(f"实验 {number} 客观检查通过；理解、设计和交付复盘仍需自己完成。")


def run_checks(namespace):
    for number in range(1, 29):
        check_experiment(namespace, number)
    print("28 道客观实验复查通过；不代表综合工具设计与口述已完成。")
