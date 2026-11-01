"""第十四章客观检查和临时 pytest 工程运行器；理解与设计理由仍需人工评审。"""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory

UNFINISHED = "__未填写__"


class CheckFailure(AssertionError):
    """当前题的记录或实现不符合题面。"""


_REPORT_PLUGIN = r'''
import json
from pathlib import Path

data = {"nodeids": [], "counts": {key: 0 for key in
        ("passed", "failed", "skipped", "xfailed", "xpassed", "errors")}}

def pytest_collection_finish(session):
    data["nodeids"] = [item.nodeid for item in session.items]

def pytest_collectreport(report):
    if report.failed:
        data["counts"]["errors"] += 1

def pytest_runtest_logreport(report):
    counts = data["counts"]
    if report.failed:
        counts["failed" if report.when == "call" else "errors"] += 1
    elif report.skipped:
        counts["xfailed" if hasattr(report, "wasxfail") else "skipped"] += 1
    elif report.when == "call" and report.passed:
        counts["xpassed" if hasattr(report, "wasxfail") else "passed"] += 1

def pytest_sessionfinish(session, exitstatus):
    data["session_exit"] = int(exitstatus)
    Path("_ch14_results.json").write_text(json.dumps(data), encoding="utf-8")
'''


def run_pytest_project(files, args=(), *, artifacts=(), timeout=25):
    """创建独立临时工程并运行当前 Python 的 pytest，返回阶段统计与指定文本文件。

    files 为相对 POSIX 路径到源码文本的映射；不向正式学习文件写入结果。
    counts 按报告阶段累加，同一测试体通过又清理失败可同时贡献 passed、errors。
    为保持实验可重复，子进程关闭第三方插件自动加载并排除外部 pytest 选项。
    这是教学辅助接口，不是 pytest 自带 API；不会隔离任意测试代码的所有外部副作用。
    """
    with TemporaryDirectory(prefix="chapter14-") as directory:
        root = Path(directory)

        def target(relative):
            path = PurePosixPath(relative)
            if path.is_absolute() or ".." in path.parts or "\\" in relative or ":" in relative:
                raise ValueError("请使用工程内的相对路径")
            return root.joinpath(*path.parts)

        for relative, source in files.items():
            if relative in {"_ch14_report.py", "_ch14_results.json"}:
                raise ValueError("文件名被实验运行器保留")
            path = target(relative)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(textwrap.dedent(source).strip() + "\n", encoding="utf-8")
        if not any((root / name).exists() for name in
                   ("pytest.ini", ".pytest.ini", "pyproject.toml", "tox.ini", "setup.cfg")):
            (root / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
        (root / "_ch14_report.py").write_text(_REPORT_PLUGIN, encoding="utf-8")
        environment = os.environ.copy()
        for key in ("PYTEST_ADDOPTS", "PYTEST_PLUGINS", "PYTHONPATH"):
            environment.pop(key, None)
        environment.update(PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", PYTHONPATH=str(root),
                           PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
        completed = subprocess.run(
            [sys.executable, "-m", "pytest", "-p", "_ch14_report", "-p", "no:cacheprovider",
             "-q", "--tb=short", "--color=no", *args],
            cwd=root, env=environment, capture_output=True, text=True, check=False,
            encoding="utf-8", errors="replace", timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        report_path = root / "_ch14_results.json"
        report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {
            "nodeids": [], "counts": {name: 0 for name in
            ("passed", "failed", "skipped", "xfailed", "xpassed", "errors")}}
        report.update(exit_code=completed.returncode, output=completed.stdout + completed.stderr)
        report["artifacts"] = {
            name: target(name).read_text(encoding="utf-8") if target(name).is_file() else None
            for name in artifacts
        }
        return report


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
    if isinstance(expected, (list, tuple)):
        return len(actual) == len(expected) and all(_matches(a, e) for a, e in zip(actual, expected))
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(_matches(actual[key], value)
                                                      for key, value in expected.items())
    return actual == expected


OBSERVATIONS = {
    1: [2, 2, 0], 2: [["test_sample.py::test_double[two]"], 1],
    3: [["test_sample.py::test_fast"], 1], 4: [["test_sample.py::test_first"], 1],
    5: [1, 0, ["import"]], 6: [1, 3, ["1", "0"]], 7: [6, 6],
    8: [["create", "same"]], 9: [2, 0], 10: [1, 1],
    11: [["base+", "child+", "test", "child-", "base-"]],
    12: [0, 1, ["acquire", "configure"]], 13: [1, ["acquire", "release"]],
    14: [1, ["first", "second"]], 15: [2, 2],
    16: [1, 1, 1, 1, 1], 17: [[7, 31]], 18: [["outer", "inner", "outer"]],
    19: ["READY", "TimeoutError", 2], 20: [2, True, True],
    21: [["alpha\n", "beta\n"]], 22: [[["INFO", "begin"], ["WARNING", "late"]]],
    23: [1, 1, 2, 0], 24: [1, 1, 1],
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


def _source(namespace, name):
    function = namespace.get(name)
    _require(callable(function), f"请先定义并运行本题的 {name}。")
    source = function()
    _require(isinstance(source, str) and bool(source.strip()), "本题应返回完整源码文本。")
    _require(not _unfinished(source), "本题源码仍有未填写位置。")
    ast.parse(source)
    return source


def _healthy(report, label):
    _require(report["exit_code"] == 0 and report["counts"]["passed"] > 0 and
             not any(report["counts"][key] for key in
                     ("failed", "errors", "skipped", "xfailed", "xpassed")),
             f"{label}未完成预期的正常执行，请单独运行临时工程定位。")


def _check_range_tests(namespace):
    source = _source(namespace, "make_range_test_source")
    _require(any(isinstance(node, ast.Attribute) and node.attr == "parametrize"
                 for node in ast.walk(ast.parse(source))), "实验 25 需要按题面使用参数化。")
    correct = '''
def accept_count(value):
    if type(value) is not int:
        raise TypeError("count must be an exact integer")
    return 0 <= value <= 4
'''
    _healthy(run_pytest_project({"subject.py": correct, "test_contract.py": source}), "实验 25 正确候选")
    mutants = [
        correct.replace("0 <= value", "0 < value"),
        correct.replace("value <= 4", "value < 4"),
        correct.replace("return 0 <= value <= 4", "return True"),
        correct.replace("return 0 <= value <= 4", "return False"),
        correct.replace("type(value) is not int", "not isinstance(value, int)"),
        correct.replace("raise TypeError", "raise ValueError"),
        correct.replace("return 0 <= value <= 4", "return int(0 <= value <= 4)"),
    ]
    for index, candidate in enumerate(mutants, 1):
        report = run_pytest_project({"subject.py": candidate, "test_contract.py": source})
        _require(report["exit_code"] == 1 and report["counts"]["failed"] > 0 and
                 report["counts"]["errors"] == 0,
                 f"实验 25 对第 {index} 类故意错误尚无有效区分，请复查输入与断言。")


_ISOLATION_TESTS = '''
import pytest

@pytest.fixture(scope="session")
def base_settings():
    return {"limit": 2, "tags": ["base"]}

@pytest.fixture
def alias(case_settings):
    return case_settings

def test_first(case_settings, alias, base_settings):
    assert case_settings is alias
    assert case_settings == {"limit": 2, "tags": ["base"]}
    assert case_settings is not base_settings
    assert case_settings["tags"] is not base_settings["tags"]
    case_settings["tags"].append("local")
    case_settings["limit"] = 99
    assert base_settings == {"limit": 2, "tags": ["base"]}

def test_second(case_settings, base_settings):
    assert case_settings == {"limit": 2, "tags": ["base"]}
    assert base_settings == {"limit": 2, "tags": ["base"]}
'''


def _check_isolated_fixture(namespace):
    source = _source(namespace, "make_isolated_fixture_source")
    _require(not any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and
                     node.name == "base_settings" for node in ast.walk(ast.parse(source))),
             "实验 26 不应重新定义题面已提供的 base_settings。")
    report = run_pytest_project({"conftest.py": source, "test_isolation.py": _ISOLATION_TESTS})
    _healthy(report, "实验 26 的两项独立测试")
    _require(report["counts"]["passed"] == 2, "实验 26 的测试项数量不符合接口。")
    # 反转节点顺序，确认不靠一次偶然的执行顺序满足约定。
    report = run_pytest_project({"conftest.py": source, "test_isolation.py": _ISOLATION_TESTS},
                               ["test_isolation.py::test_second", "test_isolation.py::test_first"])
    _healthy(report, "实验 26 反向顺序")


_CLIENT = '''
from provider import read_label

def format_label(case_id):
    return read_label(case_id)["label"].upper()
'''
_PROVIDER = '''
def read_label(case_id):
    raise RuntimeError("real reader must not be called in this exercise")
'''


def _check_client_tests(namespace):
    source = _source(namespace, "make_client_test_source")

    def run(candidate):
        return run_pytest_project({"client.py": candidate, "provider.py": _PROVIDER,
                                   "test_client.py": source,
                                   "test_zz_restored.py": (
                                       "import client\nimport provider\n"
                                       "def test_dependency_restored():\n"
                                       "    assert client.read_label is provider.read_label\n")})

    _healthy(run(_CLIENT), "实验 27 正确候选")
    mutants = [
        _CLIENT.replace('.upper()', ''),
        _CLIENT.replace('read_label(case_id)', 'read_label("wrong-id")'),
        _CLIENT + '\ndef format_label(case_id):\n    return "DEMO"\n',
        _CLIENT + '\ndef format_label(case_id):\n    try:\n        return read_label(case_id)["label"].upper()\n    except TimeoutError:\n        return "fallback"\n',
        _CLIENT.replace('return read_label(case_id)', 'read_label(case_id)\n    return read_label(case_id)'),
    ]
    for index, candidate in enumerate(mutants, 1):
        report = run(candidate)
        _require(report["exit_code"] == 1 and report["counts"]["failed"] > 0 and
                 report["counts"]["errors"] == 0,
                 f"实验 27 对第 {index} 类故意错误尚无有效区分，请检查行为与交互。")


def _check_option_plugin(namespace):
    source = _source(namespace, "make_option_plugin_source")
    tests = '''
def test_value(sample_size):
    assert type(sample_size) is int
    assert sample_size == EXPECTED
'''
    for args, expected in (([], 2), (["--sample-size=1"], 1), (["--sample-size=5"], 5)):
        report = run_pytest_project({"conftest.py": source,
                                    "test_option.py": tests.replace("EXPECTED", str(expected))}, args)
        _healthy(report, "实验 28 默认值或有效覆盖")
    for value in ("0", "6", "wrong"):
        report = run_pytest_project({"conftest.py": source, "test_option.py": "def test_body():\n    assert True"},
                                   [f"--sample-size={value}"])
        _require(report["exit_code"] == 4 and report["counts"]["passed"] == 0,
                 "实验 28 应在配置阶段拒绝题面列出的非法选项。")
        _require("sample-size" in report["output"], "实验 28 的配置错误应指出选项名。")


IMPLEMENTATIONS = {25: _check_range_tests, 26: _check_isolated_fixture,
                   27: _check_client_tests, 28: _check_option_plugin}


def check_experiment(namespace, number):
    """只检查当前题；不改写预测、观察、源码或其他题状态。"""
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
    print("28 道客观实验复查通过；不代表综合设计与口述已完成。")
