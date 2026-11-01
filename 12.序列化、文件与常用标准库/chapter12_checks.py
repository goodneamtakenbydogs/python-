"""第十二章逐题检查；核对数据、资源和失败约定，不修改学习记录。"""
from __future__ import annotations

import builtins
import copy
import csv
import io
import json
import os
import re
from contextlib import ExitStack, contextmanager
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import patch

UNFINISHED = "__未填写__"


class CheckFailure(AssertionError):
    """当前题的填写或实现尚未符合题意。"""


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
    fields = {}
    for label, value in mapping.items():
        match = re.match(r"^(\d{2})\.\s+", label) if isinstance(label, str) else None
        _require(match is not None and match.group(1) not in fields,
                 f"{phase}字段“{label}”的编号缺失或重复。")
        _require(not _unfinished(value),
                 f"{phase}字段“{label}”尚未填写，请替换包括引号的整个占位字符串。")
        fields[match.group(1)] = (label, value)
    _require(set(fields) == {f"{i:02d}" for i in range(1, count + 1)},
             f"本题{phase}字段编号不完整。")
    return fields


def _matches(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, (list, tuple)):
        return len(actual) == len(expected) and all(_matches(a, e) for a, e in zip(actual, expected))
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(_matches(actual[key], value) for key, value in expected.items())
    return actual == expected


OBSERVATIONS = {
    1: [2, 4, "int", 228], 2: [False, True],
    3: ["UnicodeDecodeError", "AB", "A\ufffdB"],
    4: ["A\nB\nC\n", "A\r\nB\rC\n"], 5: [0, 3, "new"],
    6: ["ABC", "FileExistsError"], 7: [b"AB", 2, b"CDE", b"", b"C"],
    8: ["中", "A", "A", True], 9: [[" A ", "B", ""], ""],
    10: ["result.csv", ".csv", "result", "/other"], 11: [["a.txt", "b.txt"], False],
    12: [{"1": ["A", "B"]}, False, True], 13: [True, False, True],
    14: ["JSONDecodeError", "ValueError", True], 15: [False, True, True],
    16: [True, 'comma, quote "yes"', "line1\nline2"], 17: [None, ["4"], "1"],
    18: [False, "C-12", False, True, False],
    19: [{"prefix": "C", "number": "12"}, [("C", "12"), ("C", "34")], ["C-12", "C-34"]],
    20: ["X and aaab", "ID-12"], 21: ["2024-01-01T00:00:00+00:00", True, 28800.0],
    22: [False, "TypeError", "TypeError"],
    23: ["2023-12-31T18:30:00+00:00", "1970-01-01T00:00:00+00:00"],
    24: [{"A": 3, "B": 1}, False, [("A", 2), ("B", 1), ("A", 1)]],
    25: ["case:A", 1, 2], 26: ["a b; echo data", "中文", 0],
    27: [0, "note", 3, "TimeoutExpired"], 28: [True, True, ["result.txt"], False],
    29: [3, True, True, 2], 30: [True, True, 32, True],
}


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


def _expect_error(function, args, error_type, message):
    try:
        function(*args)
    except error_type:
        return
    raise CheckFailure(message)


class _ObservedStream:
    """仅包住测试自己创建的输入，检测按行读取和关闭。"""
    def __init__(self, stream):
        self.stream = stream
        self.reads = 0

    def __getattr__(self, name):
        return getattr(self.stream, name)

    def __enter__(self):
        self.stream.__enter__()
        return self

    def __exit__(self, *args):
        return self.stream.__exit__(*args)

    def __iter__(self):
        return self

    def __next__(self):
        line = self.readline()
        if line in ("", b""):
            raise StopIteration
        return line

    def readline(self, *args, **kwargs):
        self.reads += 1
        return self.stream.readline(*args, **kwargs)

    def read(self, *args, **kwargs):
        raise CheckFailure("实验 31 请按题面使用逐行迭代或 readline，不调用 read。")

    def readlines(self, *args, **kwargs):
        raise CheckFailure("实验 31 请按需读取，不收集全部输入行。")


@contextmanager
def _patch_bindings(namespace, replacements):
    """只恢复被替换的绑定，保留学习者执行期间产生的其他全局记录。"""
    original = {name: namespace[name] for name in replacements}
    namespace.update(replacements)
    try:
        yield
    finally:
        namespace.update(original)


@contextmanager
def _observe_open(path, function):
    streams = []
    ordinary, path_open = builtins.open, io.open

    def wrap(original):
        def observed(file, *args, **kwargs):
            stream = original(file, *args, **kwargs)
            if isinstance(file, (str, os.PathLike)) and Path(file).resolve() == path.resolve():
                tracked = _ObservedStream(stream)
                streams.append(tracked)
                return tracked
            return stream
        return observed

    aliases = {name: wrap(value) for name, value in list(function.__globals__.items())
               if value is ordinary or value is path_open}
    # IPython 可在用户名字空间安装自己的 open 包装，应观察实际查找的绑定。
    local_open = function.__globals__.get("open")
    if callable(local_open):
        aliases["open"] = wrap(local_open)
    try:
        with ExitStack() as stack:
            stack.enter_context(_patch_bindings(function.__globals__, aliases))
            stack.enter_context(patch("builtins.open", wrap(ordinary)))
            stack.enter_context(patch("io.open", wrap(path_open)))
            yield streams
    finally:
        for stream in streams:
            stream.close()


def _check_jsonl(namespace):
    function = _function(namespace, "iter_jsonl_records")
    with TemporaryDirectory(prefix="check_jsonl_") as directory:
        path = Path(directory) / "records.jsonl"
        for content, expected in (("", []), ('\n{"id":1}\n  \n{"name":"中"}\n', [{"id": 1}, {"name": "中"}])):
            path.write_text(content, encoding="utf-8", newline="")
            before = path.read_bytes()
            with _observe_open(path, function) as streams:
                iterator = function(path)
                _require(iter(iterator) is iterator and callable(getattr(iterator, "close", None)),
                         "实验 31 应返回可显式 close 的迭代器。")
                try:
                    actual = list(iterator)
                    _require(_matches(actual, expected), "实验 31 的空行、记录或内容处理不符合约定。")
                    _require(streams and all(stream.closed for stream in streams),
                             "实验 31 耗尽后没有关闭自己打开的文件。")
                finally:
                    iterator.close()
            _require(path.read_bytes() == before, "实验 31 不应修改输入文件。")

        path.write_text('{"id":1}\n\ninvalid\n', encoding="utf-8")
        with _observe_open(path, function) as streams:
            iterator = function(path)
            try:
                _require(all(stream.reads == 0 for stream in streams), "实验 31 在消费前已读取输入。")
                _require(next(iterator) == {"id": 1}, "实验 31 首条记录不符合输入。")
                _require(sum(stream.reads for stream in streams) == 1,
                         "实验 31 提前读取了后续记录，请检查惰性消费。")
                iterator.close()
                _require(all(stream.closed for stream in streams), "实验 31 显式 close 后文件仍被持有。")
            finally:
                iterator.close()

        for content, line_number, needs_cause in (
            ('{"id":1}\n\ninvalid\n', 3, True), ("[]\n", 1, False), ("null\n", 1, False),
        ):
            path.write_text(content, encoding="utf-8")
            with _observe_open(path, function) as streams:
                iterator = function(path)
                try:
                    try:
                        list(iterator)
                    except ValueError as error:
                        _require(re.search(rf"(?<!\d){line_number}(?!\d)", str(error)) is not None,
                                 "实验 31 的失败记录缺少实际物理行号。")
                        if needs_cause:
                            _require(isinstance(error.__cause__, json.JSONDecodeError),
                                     "实验 31 应保留 JSON 解析失败的直接原因。")
                    else:
                        raise CheckFailure("实验 31 未拒绝题面指定的无效记录。")
                    _require(streams and all(stream.closed for stream in streams),
                             "实验 31 出错后没有结束自己的文件范围。")
                finally:
                    iterator.close()


def _write_csv(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        csv.writer(stream).writerows(rows)


def _check_csv(namespace):
    function = _function(namespace, "load_case_csv")
    header = ["case_id", "enabled", "timeout"]
    with TemporaryDirectory(prefix="check_csv_") as directory:
        path = Path(directory) / "cases.csv"
        rows = [header, [" C,1 ", " false ", " 003 "], ['中\r\n"2"', "true", "300"]]
        _write_csv(path, rows)
        before = path.read_bytes()
        expected = [{"case_id": "C,1", "enabled": False, "timeout": 3},
                    {"case_id": '中\r\n"2"', "enabled": True, "timeout": 300}]
        _require(_matches(function(path), expected), "实验 32 的引号、换行、BOM 或字段转换不符合接口。")
        _require(path.read_bytes() == before, "实验 32 不应改写源文件。")
        _write_csv(path, [header])
        _require(_matches(function(path), []), "实验 32 的只有表头输入不符合约定。")
        _write_csv(path, [["timeout", "case_id", "enabled"], ["1", "A", "true"]])
        _require(_matches(function(path), [{"case_id": "A", "enabled": True, "timeout": 1}]),
                 "实验 32 应按字段名处理允许的列顺序。")
        bad_rows = [[], [["case_id", "enabled"]], [["case_id", "enabled", "enabled", "timeout"]],
                    [header, ["A", "true"]], [header, ["A", "true", "3", "extra"]],
                    [header, [" ", "true", "3"]], [header, ["A", "true", "3"], [" A ", "false", "4"]]]
        bad_rows.extend([header, ["A", enabled, "3"]] for enabled in ("True", "yes", "1", "", "FALSE"))
        bad_rows.extend([header, ["A", "true", value]] for value in ("0", "301", "-1", "+2", "2.0", "２", "", "1_0"))
        for index, rows in enumerate(bad_rows, 1):
            _write_csv(path, rows)
            _expect_error(function, (path,), ValueError, f"实验 32 未拒绝无效数据场景 {index}。")


def _check_utc(namespace):
    function = _function(namespace, "to_utc_iso")
    cases = [
        ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00+00:00"),
        ("2024-01-01T08:00:00+08:00", "2024-01-01T00:00:00+00:00"),
        ("2024-01-01T00:00:00+05:30", "2023-12-31T18:30:00+00:00"),
        ("2024-01-01T23:30:00-02:00", "2024-01-02T01:30:00+00:00"),
        ("2024-01-01T00:00:00.1234+00:00", "2024-01-01T00:00:00.123400+00:00"),
        ("2024-01-01 00:00:00+00:00", "2024-01-01T00:00:00+00:00"),
    ]
    for text, expected in cases:
        result = function(text)
        _require(type(result) is str and result == expected,
                 f"实验 33 对输入 {text!r} 的转换、日期或精度不符合接口。")
        _require(datetime.fromisoformat(result).timestamp() == datetime.fromisoformat(text).timestamp(),
                 "实验 33 改变了原时刻。")
    for text in ("2024-01-01", "2024-01-01T12:00:00", "bad", "2024-02-30T00:00:00Z", ""):
        _expect_error(function, (text,), ValueError, "实验 33 未按约定拒绝无效或 naive 输入。")
    for value in (None, 0, True, b"2024-01-01T00:00:00Z"):
        _expect_error(function, (value,), TypeError, "实验 33 未按约定拒绝输入类型。")


@contextmanager
def _replace_patch(function, replacement):
    original = os.replace
    with ExitStack() as stack:
        aliases = {name: replacement for name, value in list(function.__globals__.items()) if value is original}
        if aliases:
            stack.enter_context(_patch_bindings(function.__globals__, aliases))
        stack.enter_context(patch("os.replace", replacement))
        yield


def _check_report(namespace):
    function = _function(namespace, "write_json_report")
    original_replace = os.replace
    with TemporaryDirectory(prefix="check_report_") as directory:
        root = Path(directory)
        destination = root / "report.json"
        for report in ({}, {"name": "中文", "passed": True, "rows": [1, None, {"value": 2}]},
                       [{"name": "中文"}, 1, False], None):
            before_report = copy.deepcopy(report)
            observed = []

            def replace(source, target, *args, _report=report, _observed=observed, **kwargs):
                if Path(target).resolve() == destination.resolve():
                    source_path = Path(source)
                    _require(source_path.parent.resolve() == root.resolve() and source_path != destination,
                             "实验 34 应使用目标同目录的独立临时文件。")
                    _require(json.loads(source_path.read_text(encoding="utf-8")) == _report,
                             "实验 34 应在替换前完成临时 JSON 内容。")
                    _observed.append(source_path)
                return original_replace(source, target, *args, **kwargs)

            with _replace_patch(function, replace):
                result = function(destination, report)
            _require(result is None and _matches(json.loads(destination.read_text(encoding="utf-8")), report),
                     "实验 34 的成功结果、编码或返回值不符合接口。")
            _require(len(observed) == 1 and set(root.iterdir()) == {destination},
                     "实验 34 未按约定替换，或遗留了本次临时文件。")
            _require(report == before_report, "实验 34 不应修改 report。")
            if isinstance(report, dict) and "name" in report:
                _require("中文" in destination.read_text(encoding="utf-8"), "实验 34 请按题面保留中文可读。")

        old = b"old report\x00"
        for report, error_type in (({"bad": {1}}, (TypeError, ValueError)),
                                   ({"bad": float("nan")}, ValueError),
                                   ({"bad": float("inf")}, ValueError)):
            destination.write_bytes(old)
            _expect_error(function, (destination, report), error_type, "实验 34 不应接受不支持或非标准数值。")
            _require(destination.read_bytes() == old and set(root.iterdir()) == {destination},
                     "实验 34 编码失败时破坏旧目标或遗留临时文件。")

        destination.write_bytes(old)

        def fail_replace(source, target, *args, **kwargs):
            if Path(target).resolve() == destination.resolve():
                raise OSError("simulated replace failure")
            return original_replace(source, target, *args, **kwargs)

        with _replace_patch(function, fail_replace):
            _expect_error(function, (destination, {"ok": True}), OSError,
                          "实验 34 未传播替换失败。")
        _require(destination.read_bytes() == old and set(root.iterdir()) == {destination},
                 "实验 34 替换失败时破坏旧目标或遗漏清理。")


IMPLEMENTATIONS = {31: _check_jsonl, 32: _check_csv, 33: _check_utc, 34: _check_report}


def check_experiment(namespace: dict[str, Any], number: int) -> None:
    """独立检查当前题，不依赖其他题完成，也不修改预测。"""
    if type(number) is not int or not 1 <= number <= 34:
        raise ValueError("实验编号应为 1 到 34。")
    try:
        if number <= 30:
            _check_observation(namespace, number)
        else:
            IMPLEMENTATIONS[number](namespace)
    except CheckFailure:
        raise
    except Exception as error:
        raise CheckFailure(f"实验 {number} 运行失败，请检查当前题接口、数据边界与资源责任。") from error
    print(f"实验 {number} 客观检查通过；请继续解释数据表示、预期与清理。")


def run_checks(namespace: dict[str, Any]) -> None:
    """全部完成后的补充复查，不能代替逐题检查。"""
    for number in range(1, 35):
        check_experiment(namespace, number)
    print("第 12 章 34 道客观检查通过；编码、格式选择、时间和资源边界仍需口述。")


if __name__ == "__main__":
    print("请在第12章代码实验.ipynb中逐题调用 check_experiment()。")
