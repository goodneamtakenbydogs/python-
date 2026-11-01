"""第 9 章的逐题检查：保留预测，只核对实际观察和接口行为。"""

from __future__ import annotations

import gc
import random
import re
import weakref
from typing import Any

UNFINISHED = "__未填写__"


class CheckFailure(AssertionError):
    """当前实验的填写或实现尚未符合题意。"""


def _contains_unfinished(value: Any, seen: set[int] | None = None) -> bool:
    if isinstance(value, str):
        return value == UNFINISHED
    if not isinstance(value, (dict, list, tuple, set)):
        return False
    if seen is None:
        seen = set()
    if id(value) in seen:
        return False
    seen.add(id(value))
    items = value.values() if isinstance(value, dict) else value
    return any(_contains_unfinished(item, seen) for item in items)


def _fields(namespace: dict[str, Any], name: str, count: int, stage: str) -> dict[str, tuple[str, Any]]:
    mapping = namespace.get(name)
    if not isinstance(mapping, dict):
        raise CheckFailure(f"找不到本题的{stage}记录，请先填写并运行相应单元格。")
    if len(mapping) != count:
        raise CheckFailure(f"请保留本题{stage}记录的全部编号与字段。")
    result = {}
    for label, value in mapping.items():
        match = re.match(r"^(\d{2})\.\s+", label) if isinstance(label, str) else None
        if match is None:
            raise CheckFailure(f"{stage}字段“{label}”缺少题面给出的两位编号。")
        field_id = match.group(1)
        if field_id in result:
            raise CheckFailure(f"本题{stage}记录中存在重复编号 {field_id}。")
        if _contains_unfinished(value):
            raise CheckFailure(
                f"{stage}字段“{label}”尚未填写；请替换整个占位字符串，包括引号。"
            )
        result[field_id] = (label, value)
    if set(result) != {f"{index:02d}" for index in range(1, count + 1)}:
        raise CheckFailure(f"本题{stage}字段编号不完整，请保留题面给出的编号。")
    return result


def _matches(actual: Any, expected: Any) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, (list, tuple)):
        return len(actual) == len(expected) and all(
            _matches(left, right) for left, right in zip(actual, expected)
        )
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(
            _matches(actual[key], expected[key]) for key in expected
        )
    return actual == expected


OBSERVATIONS = {
    1: {"01": True, "02": [1, 2, 3], "03": [1, 2, 3], "04": [9]},
    2: {"01": True, "02": True},
    3: {"01": 1, "02": 1, "03": True},
    4: {"01": True, "02": True},
    5: {"01": True, "02": True},
    6: {"01": True, "02": True, "03": True},
    7: {"01": True, "02": True},
    8: {"01": True, "02": True, "03": True},
    9: {"01": False, "02": True, "03": [[1, 9], [2]], "04": [[1, 9], [2]], "05": [[100], [2]]},
    10: {"01": False, "02": [80, 90], "03": [80]},
    11: {"01": [["A"], ["A"], ["A"]], "02": [["A"], [], []], "03": True, "04": False},
    12: {"01": True, "02": False, "03": [[1], [1]], "04": [[1, 2], [1, 2]]},
    13: {"01": False, "02": True, "03": 1},
    14: {"01": True, "02": False, "03": [[1, 2], [1, 2]], "04": [[1, 2], [1]]},
    15: {"01": False, "02": True, "03": False, "04": 6},
    16: {"01": True, "02": True},
    17: {"01": True, "02": False},
    18: {"01": True, "02": True},
    19: {"01": True, "02": True},
    20: {"01": "ready", "02": True, "03": True},
    21: {"01": ["released"], "02": False, "03": ["released"]},
}


def _check_observation(namespace: dict[str, Any], number: int) -> None:
    expected = OBSERVATIONS[number]
    # 预测只要求已填写。预测错误也是应保留的学习记录。
    _fields(namespace, f"prediction_{number:02d}", len(expected), "预测")
    actual = _fields(namespace, f"observation_{number:02d}", len(expected), "实际观察")
    for field_id, expected_value in expected.items():
        label, value = actual[field_id]
        try:
            correct = _matches(value, expected_value)
        except (RecursionError, TypeError, ValueError):
            correct = False
        if not correct:
            raise CheckFailure(f"实际观察字段“{label}”与本题运行结果不一致，请重新观察。")


def _function(namespace: dict[str, Any], name: str, number: int):
    function = namespace.get(name)
    if not callable(function):
        raise CheckFailure(f"实验 {number} 找不到 {name}，请先运行实现定义单元格。")
    return function


def _check_clone_rows(namespace: dict[str, Any]) -> None:
    function = _function(namespace, "clone_rows", 22)
    shared = [3, 4]
    cases = [[], [[]], [[1], [2, 2]], [shared, shared]]
    generator = random.Random(9)
    cases.extend(
        [[generator.randint(-5, 5) for _ in range(generator.randrange(5))]
         for _ in range(generator.randrange(5))]
        for _ in range(12)
    )
    for case_number, rows in enumerate(cases, 1):
        before = [tuple(row) for row in rows]
        result = function(rows)
        if type(result) is not list or len(result) != len(rows):
            raise CheckFailure(f"实验 22 的用例 {case_number} 未按接口返回结果。")
        if result is rows or any(type(row) is not list for row in result):
            raise CheckFailure(f"实验 22 的用例 {case_number} 未建立题意要求的复制边界。")
        if [tuple(row) for row in result] != before:
            raise CheckFailure(f"实验 22 的用例 {case_number} 未保留元素与顺序。")
        if len({id(row) for row in result}) != len(result):
            raise CheckFailure(f"实验 22 的用例 {case_number} 的结果行仍意外共享。")
        if any(copied is original for copied in result for original in rows):
            raise CheckFailure(f"实验 22 的用例 {case_number} 仍与输入共享行对象。")
        if result:
            result[0].append(99)
        if [tuple(row) for row in rows] != before:
            raise CheckFailure(f"实验 22 的用例 {case_number} 修改了输入。")
    if function(iter([[1], []])) != [[1], []]:
        raise CheckFailure("实验 22 还应支持只能遍历一次的输入。")


def _check_snapshot_graph(namespace: dict[str, Any]) -> None:
    function = _function(namespace, "snapshot_graph", 23)
    for original in ([], {}):
        copied = function(original)
        if type(copied) is not type(original) or copied != original or copied is original:
            raise CheckFailure("实验 23 没有按题意复制空容器。")
    for original in (None, 7, "name", (1, "A")):
        copied = function(original)
        if type(copied) is not type(original) or copied != original:
            raise CheckFailure("实验 23 的不可变数据结果不符合题意。")

    shared = [1, {"score": 80}]
    original = {"first": shared, "second": shared}
    original["self"] = original
    copied = function(original)
    if type(copied) is not dict or copied is original:
        raise CheckFailure("实验 23 未正确建立结果外层。")
    if copied.get("self") is not copied:
        raise CheckFailure("实验 23 没有保留结果的循环关系。")
    if copied.get("first") is not copied.get("second"):
        raise CheckFailure("实验 23 没有保留同一次复制中的共享关系。")
    if copied["first"] is shared or copied["first"][1] is shared[1]:
        raise CheckFailure("实验 23 的可变容器仍与输入共享。")
    if copied["first"] != [1, {"score": 80}]:
        raise CheckFailure("实验 23 未保留内容。")
    copied["first"][1]["score"] = 99
    if (
        original["first"] != [1, {"score": 80}]
        or original["first"] is not shared
        or original["second"] is not shared
        or original["self"] is not original
        or set(original) != {"first", "second", "self"}
    ):
        raise CheckFailure("实验 23 改变了原图或没有隔离可变状态。")

    nested = ([{"value": 1}],)
    copied_tuple = function(nested)
    if type(copied_tuple) is not tuple or copied_tuple[0] is nested[0] or copied_tuple[0][0] is nested[0][0]:
        raise CheckFailure("实验 23 的元组内部可变状态没有隔离。")
    if copied_tuple != ([{"value": 1}],):
        raise CheckFailure("实验 23 没有保留元组内部内容。")

    original_list: list[Any] = []
    original_list.append(original_list)
    copied_list = function(original_list)
    if type(copied_list) is not list or copied_list is original_list or copied_list[0] is not copied_list:
        raise CheckFailure("实验 23 的列表自引用没有正确处理。")


def _check_weak_registry(namespace: dict[str, Any]) -> None:
    cls = namespace.get("WeakRegistry")
    if not isinstance(cls, type):
        raise CheckFailure("实验 24 找不到 WeakRegistry 类，请先运行定义单元格。")

    class Item:
        pass

    registry = cls()
    other_registry = cls()
    if len(registry) != 0 or registry.get("missing") is not None:
        raise CheckFailure("实验 24 的空表与缺失读取不符合题意。")
    registry.remove("missing")
    item = Item()
    reference = weakref.ref(item)
    registry.add("A", item)
    if registry.get("A") is not item or len(registry) != 1 or len(other_registry) != 0:
        raise CheckFailure("实验 24 的登记、读取或实例隔离不符合题意。")
    del item
    gc.collect()
    if reference() is not None or registry.get("A") is not None or len(registry) != 0:
        raise CheckFailure("实验 24 的登记表不应独自保留值对象。")

    old = Item()
    new = Item()
    old_reference = weakref.ref(old)
    registry.add("same", old)
    registry.add("same", new)
    if registry.get("same") is not new or len(registry) != 1:
        raise CheckFailure("实验 24 的同名覆盖不符合题意。")
    del old
    gc.collect()
    if old_reference() is not None:
        raise CheckFailure("实验 24 仍保留已经被覆盖的值。")
    registry.remove("same")
    registry.remove("same")
    if len(registry) != 0 or registry.get("same") is not None:
        raise CheckFailure("实验 24 的移除行为不符合题意。")
    try:
        registry.add("unsupported", [])
    except TypeError:
        pass
    else:
        raise CheckFailure("实验 24 应按接口拒绝不支持弱引用的值。")


IMPLEMENTATIONS = {22: _check_clone_rows, 23: _check_snapshot_graph, 24: _check_weak_registry}


def check_experiment(namespace: dict[str, Any], number: int) -> None:
    """独立检查当前实验；不会要求其他实验先填写，也不改写学习记录。"""
    if type(number) is not int or not 1 <= number <= 24:
        raise ValueError("实验编号应在 1 到 24 之间。")
    if number in OBSERVATIONS:
        _check_observation(namespace, number)
        print(f"实验 {number} 的实际观察检查通过；请比较保留的预测并解释差异。")
        return
    try:
        IMPLEMENTATIONS[number](namespace)
    except CheckFailure:
        raise
    except Exception as error:
        raise CheckFailure(f"实验 {number} 的实现运行失败，请检查题面接口和边界输入。") from error
    print(f"实验 {number} 的实现检查通过；请继续解释复制边界或引用所有权。")


def run_checks(namespace: dict[str, Any]) -> None:
    """全部完成后的复查，不能代替每道实验后的即时检查。"""
    for number in range(1, 25):
        check_experiment(namespace, number)
    print("第 9 章的 24 道客观实验与实现检查通过。概念解释仍需口述复盘。")


if __name__ == "__main__":
    print("请在第9章代码实验.ipynb中逐题调用 check_experiment()。")
