"""第 7 章 Notebook 的逐题客观检查。"""

from __future__ import annotations

import inspect
import re
from collections.abc import Callable
from typing import Any

UNFINISHED = "__未填写__"


class CheckFailure(AssertionError):
    """表示某道实验尚未通过。"""


def _contains_unfinished(value: Any) -> bool:
    if value == UNFINISHED:
        return True
    if isinstance(value, dict):
        return any(_contains_unfinished(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_unfinished(item) for item in value)
    return False


def _check_observation(
    namespace: dict[str, Any], name: str, expected: dict[str, Any]
) -> None:
    actual = namespace.get(name)
    if not isinstance(actual, dict):
        raise CheckFailure(f"找不到 {name} 的填写字典，请先运行当前实验单元格。")
    if len(actual) != len(expected):
        raise CheckFailure("请保留当前实验的全部填写项。")

    by_id: dict[str, tuple[str, Any]] = {}
    for label, value in actual.items():
        match = re.match(r"^(\d{2})\.\s+", label)
        if match is None:
            raise CheckFailure(f"字段“{label}”缺少 Notebook 给出的两位编号。")
        field_id = match.group(1)
        if field_id in by_id:
            raise CheckFailure(f"当前实验存在重复字段编号 {field_id}。")
        by_id[field_id] = (label, value)

    required = {f"{index:02d}" for index in range(1, len(expected) + 1)}
    if set(by_id) != required:
        raise CheckFailure("请保留当前实验的全部字段编号。")

    for index, expected_value in enumerate(expected.values(), start=1):
        label, value = by_id[f"{index:02d}"]
        if _contains_unfinished(value):
            raise CheckFailure(
                f"“{label}”尚未填写。请把整个 {UNFINISHED!r}（包括引号）替换成实际 Python 值。"
            )
        if type(value) is not type(expected_value) or value != expected_value:
            raise CheckFailure(f"“{label}”与实际运行结果不一致，请重新观察本题。")


def _require_callable(namespace: dict[str, Any], name: str, number: int) -> Callable[..., Any]:
    value = namespace.get(name)
    if not callable(value):
        raise CheckFailure(f"实验 {number} 找不到可调用的 {name}，请先运行定义单元格。")
    return value


def _check_parse_positive_int(namespace: dict[str, Any]) -> None:
    function = _require_callable(namespace, "parse_positive_int", 16)
    error_type = namespace.get("InputNumberError")
    if not isinstance(error_type, type) or not issubclass(error_type, Exception):
        raise CheckFailure("实验 16 应保留题目给出的 InputNumberError 异常类。")
    for text, expected in (("7", 7), (" 12 ", 12), ("+3", 3)):
        try:
            actual = function(text)
        except Exception as error:
            raise CheckFailure(f"实验 16 的有效输入 {text!r} 不应失败。") from error
        if type(actual) is not int or actual != expected:
            raise CheckFailure(f"实验 16 的有效输入 {text!r} 结果不符合题意。")
    for text in ("0", "-2"):
        try:
            function(text)
        except error_type as error:
            if error.__cause__ is not None:
                raise CheckFailure(f"实验 16 的 {text!r} 是范围错误，不应伪造转换原因。")
        except Exception as error:
            raise CheckFailure(f"实验 16 处理非正输入 {text!r} 时抛出了其他异常。") from error
        else:
            raise CheckFailure(f"实验 16 应拒绝非正整数 {text!r}。")
    for text in ("bad", "1.5", ""):
        try:
            function(text)
        except error_type as error:
            if not isinstance(error.__cause__, ValueError):
                raise CheckFailure(f"实验 16 处理 {text!r} 时应保留原始转换异常。")
        except Exception as error:
            raise CheckFailure(f"实验 16 处理无法转换的输入 {text!r} 时抛出了其他异常。") from error
        else:
            raise CheckFailure(f"实验 16 应拒绝无法转换的输入 {text!r}。")


def _check_transaction(namespace: dict[str, Any]) -> None:
    cls = namespace.get("Transaction")
    if not isinstance(cls, type):
        raise CheckFailure("实验 17 找不到 Transaction 类。")
    events: list[str] = []
    try:
        transaction = cls(events)
        with transaction as active:
            if active is not transaction:
                raise CheckFailure("实验 17 的 __enter__() 应返回当前管理器对象。")
            events.append("work")
    except CheckFailure:
        raise
    except Exception as error:
        raise CheckFailure("实验 17 的正常路径运行失败。") from error
    if events != ["begin", "work", "commit"]:
        raise CheckFailure("实验 17 的正常路径事件顺序不符合题意。")

    events = []
    try:
        with cls(events):
            events.append("work")
            raise ValueError("work failed")
    except ValueError:
        events.append("caller caught")
    except Exception as error:
        raise CheckFailure("实验 17 的异常退出路径运行失败。") from error
    if events != ["begin", "work", "rollback", "caller caught"]:
        raise CheckFailure("实验 17 应在失败时回滚并让原异常继续传播。")


def _check_open_buffer(namespace: dict[str, Any]) -> None:
    function = _require_callable(namespace, "open_buffer", 18)
    wrapped = getattr(function, "__wrapped__", None)
    if not inspect.isgeneratorfunction(wrapped):
        raise CheckFailure("实验 18 要求使用题面指定的生成器式上下文管理器。")

    try:
        with function("abc") as buffer:
            if buffer.read(1) != "a" or buffer.closed:
                raise CheckFailure("实验 18 的正常使用范围不符合题意。")
        if not buffer.closed:
            raise CheckFailure("实验 18 正常离开时应关闭资源。")
    except CheckFailure:
        raise
    except Exception as error:
        raise CheckFailure("实验 18 的正常路径运行失败。") from error

    failed_buffer = None
    try:
        with function("xyz") as failed_buffer:
            raise ValueError("body failed")
    except ValueError:
        if failed_buffer is None:
            raise CheckFailure("实验 18 应先正常进入资源范围，再传播代码块异常。") from None
    except Exception as error:
        raise CheckFailure("实验 18 的异常退出路径运行失败。") from error
    else:
        raise CheckFailure("实验 18 不应吞掉代码块中的异常。")
    if not failed_buffer.closed:
        raise CheckFailure("实验 18 异常退出时也应关闭资源。")


OBSERVATION_CHECKS: dict[int, tuple[str, dict[str, Any]]] = {
    1: ("observation_01", {"syntax_name": "SyntaxError", "runtime_name": "ValueError"}),
    2: ("observation_02", {
        "key_is_lookup": True, "interrupt_is_exception": False,
        "interrupt_is_base": True, "value_is_exception": True,
    }),
    3: ("observation_03", {"events": ["middle before", "inner", "outer caught"]}),
    4: ("observation_04", {"specific_first": "specific", "general_first": "general"}),
    5: ("observation_05", {
        "success": ["try", "else", "finally"],
        "failure": ["try", "except", "finally"],
    }),
    6: ("observation_06", {"result": "body", "events": ["try", "finally"]}),
    7: ("observation_07", {"masked": "hidden", "overridden": "new"}),
    8: ("observation_08", {"events": ["inner caught", "outer caught"]}),
    9: ("observation_09", {
        "cause_is_original": True, "context_is_original": True,
        "suppress_context": True,
    }),
    10: ("observation_10", {"field": "age", "message": "must be non-negative"}),
    11: ("observation_11", {"default_value": 10, "mapping_after": {"timeout": 5}}),
    12: ("observation_12", {"events": ["use", "close", "outer caught"], "closed": True}),
    13: ("observation_13", {"events": ["enter", "body", "exit:none"], "same_object": True}),
    14: ("observation_14", {
        "propagated": ["enter", "body", "exit:ValueError", "outer caught"],
        "suppressed": ["enter", "body", "exit:ValueError", "continued"],
    }),
    15: ("observation_15", {
        "success": ["acquire", "body", "release"],
        "failure": ["acquire", "body", "release", "outer caught"],
    }),
    19: ("observation_19", {
        "bare_names": ["reraised_bare", "fail"],
        "named_names": ["reraised_named", "reraised_named", "fail"],
    }),
    20: ("observation_20", {
        "was_present": True, "value_after_change": "missing at use", "state_after": {},
    }),
    21: ("observation_21", {
        "events": ["first acquired", "second attempted", "first closed", "caller caught"],
        "first_closed": True,
    }),
    22: ("observation_22", {
        "before_consumption": [], "first_line": "A", "closed_after_first": False,
        "events_after_close": ["entered", "leaving with"], "closed_after_close": True,
    }),
}


def check_experiment(namespace: dict[str, Any], number: int) -> None:
    """只检查当前实验，不依赖其他实验的填写状态。"""
    if not 1 <= number <= 22:
        raise ValueError("实验编号应在 1 到 22 之间。")
    if number in OBSERVATION_CHECKS:
        name, expected = OBSERVATION_CHECKS[number]
        _check_observation(namespace, name, expected)
    elif number == 16:
        _check_parse_positive_int(namespace)
    elif number == 17:
        _check_transaction(namespace)
    elif number == 18:
        _check_open_buffer(namespace)
    else:
        raise RuntimeError("检查器缺少当前实验的内部配置。")
    print(f"实验 {number} 检查通过。")


def run_checks(namespace: dict[str, Any]) -> None:
    """整章完成后复查，不替代逐题检查。"""
    for number in range(1, 23):
        check_experiment(namespace, number)
    print("第 7 章的 22 组客观观察和实现任务全部通过。")
    print("请继续核对异常传播图和资源所有权的口头解释。")


if __name__ == "__main__":
    print("请在第7章代码实验.ipynb中逐题调用 check_experiment()。")
