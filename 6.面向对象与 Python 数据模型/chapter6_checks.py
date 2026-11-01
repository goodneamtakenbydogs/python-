"""第 6 章 Notebook 的逐题客观检查，不评价文字解释。"""

from __future__ import annotations

import re
from typing import Any

UNFINISHED = "__未填写__"


class CheckFailure(AssertionError):
    """表示实验尚未通过。"""


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
            raise CheckFailure(f"“{label}”与运行结果不一致，请重新观察本题。")


def _require_class(namespace: dict[str, Any], name: str, number: int) -> type:
    value = namespace.get(name)
    if not isinstance(value, type):
        raise CheckFailure(f"实验 {number} 找不到类 {name}，请先运行定义单元格。")
    return value


def _check_bounded_counter(namespace: dict[str, Any]) -> None:
    cls = _require_class(namespace, "BoundedCounter", 14)
    try:
        first = cls(2, 5)
        second = cls(0, 2)
        results = [first.value, first.advance(), first.advance(10), second.value]
    except Exception as error:
        raise CheckFailure("实验 14 在正常创建或推进时失败。") from error
    if results != [2, 3, 5, 0]:
        raise CheckFailure("实验 14 的初始值、推进结果或上限处理不符合题意。")
    if first.value != 5 or second.value != 0:
        raise CheckFailure("实验 14 的对象状态不应跨实例共享。")

    for start, limit in ((-1, 3), (4, 3)):
        try:
            cls(start, limit)
        except ValueError:
            pass
        else:
            raise CheckFailure(f"实验 14 应拒绝 start={start}, limit={limit}。")
    try:
        first.advance(-1)
    except ValueError:
        pass
    else:
        raise CheckFailure("实验 14 应拒绝负的推进量。")
    if first.value != 5:
        raise CheckFailure("实验 14 失败的推进不应改变原状态。")
    try:
        first.value = 0
    except AttributeError:
        pass
    else:
        raise CheckFailure("实验 14 的 value 应为只读属性。")


def _check_grid_cell(namespace: dict[str, Any]) -> None:
    cls = _require_class(namespace, "GridCell", 15)
    try:
        first = cls(1, 2)
        equal = cls(1, 2)
        different = cls(2, 1)
        values = (first.row, first.column, first == equal, first == different)
        first_hash = hash(first)
        equal_hash = hash(equal)
        lookup = {first: "found"}
        from_equal = lookup[equal]
    except Exception as error:
        raise CheckFailure("实验 15 的创建、比较、哈希或字典查找失败。") from error
    if values != (1, 2, True, False) or first_hash != equal_hash or from_equal != "found":
        raise CheckFailure("实验 15 的坐标、值相等或哈希约束不符合题意。")
    if first is equal or first == (1, 2):
        raise CheckFailure("实验 15 应区分对象身份、同类值相等和其他类型。")
    if cls.__eq__(first, object()) is not NotImplemented:
        raise CheckFailure("实验 15 的 __eq__() 应按题意处理不支持的类型。")
    try:
        first.row = 9
    except (AttributeError, TypeError):
        pass
    else:
        raise CheckFailure("实验 15 创建后的公开坐标不应被重新赋值。")
    if (first.row, first.column) != (1, 2):
        raise CheckFailure("实验 15 失败的赋值不应改变坐标。")


def _check_snapshot_shelf(namespace: dict[str, Any]) -> None:
    cls = _require_class(namespace, "SnapshotShelf", 16)
    source = [1, 2, 2]
    try:
        shelf = cls(source)
        if source != [1, 2, 2]:
            raise CheckFailure("实验 16 创建对象时不应修改输入列表。")
        source.append(9)
        actual = (len(shelf), shelf[0], shelf[-1], shelf[1:3], 2 in shelf, 9 in shelf)
        items = list(shelf)
        empty = cls([])
        empty_result = (len(empty), list(empty), 1 in empty)
    except CheckFailure:
        raise
    except Exception as error:
        raise CheckFailure("实验 16 的长度、索引、切片、成员判断或遍历失败。") from error
    if actual != (3, 1, 2, [2, 2], True, False) or items != [1, 2, 2]:
        raise CheckFailure("实验 16 的快照或容器操作不符合题意。")
    if empty_result != (0, [], False):
        raise CheckFailure("实验 16 应正确处理空输入。")
    if list(cls(iter([4, 5]))) != [4, 5]:
        raise CheckFailure("实验 16 还应支持只能遍历一次的输入迭代器。")
    for method in ("__len__", "__getitem__", "__contains__"):
        if not callable(getattr(cls, method, None)):
            raise CheckFailure(f"实验 16 应按题意实现 {method}()。")


OBSERVATION_CHECKS: dict[int, tuple[str, dict[str, Any]]] = {
    1: ("observation_01", {
        "same_object": False, "first_name": "Ada", "second_name": "Ada", "type_matches": True,
    }),
    2: ("observation_02", {
        "class_category": "member", "first_category": "admin", "second_category": "member",
        "first_attributes": {"name": "Ada", "category": "admin"},
    }),
    3: ("observation_03", {
        "shared_before_shadow": ["Ada"], "first_after_shadow": ["Lin"],
        "second_after_shadow": ["Ada"], "class_members": ["Ada"],
    }),
    4: ("observation_04", {
        "base_label": "T-2", "subclass_type": True, "subclass_label": "S-7",
        "invalid_number": False,
    }),
    5: ("observation_05", {
        "events": ["new", "init"], "saved_value": 4,
        "other_events": ["new"], "other_type": True,
    }),
    6: ("observation_06", {
        "descriptions": ["message", "email", "report"],
        "email_is_message": True, "report_is_message": False,
    }),
    7: ("observation_07", {
        "mro": ["Combined", "Left", "Right", "Root", "object"],
        "route": ["Combined", "Left", "Right", "Root"],
        "left_route": ["Left", "Root"],
    }),
    8: ("observation_08", {
        "revealed": "A", "attributes": {"_Vault__code": "A"}, "plain_name_exists": False,
    }),
    9: ("observation_09", {
        "balance_after_update": 20, "balance_after_error": 20,
        "before_manual_entry": {"_balance": 20},
        "after_manual_entry": {"_balance": 20, "balance": 999},
        "read_after_manual_entry": 20,
    }),
    10: ("observation_10", {
        "changed_x": 3, "has_instance_dict": False, "error_name": "AttributeError",
    }),
    11: ("observation_11", {
        "equal_before": True, "equal_after": False, "second_scores": [],
        "separate_scores": True, "class_hash_is_none": True,
    }),
    12: ("observation_12", {
        "display": "x3", "debug": "Multiplier(factor=3)", "call_result": 12,
        "is_callable": True,
    }),
    13: ("observation_13", {
        "equal_values": True, "same_identity": False, "other_comparison": False,
        "class_hash_is_none": True, "hash_error_name": "TypeError",
        "hash_changed": True, "mapping_length": 1,
    }),
    17: ("observation_17", {
        "name_result": "Ada", "timeout_result": 5,
        "events": ["getattribute", "getattr:timeout"],
    }),
    18: ("observation_18", {
        "descriptor_value": 10, "shadowed_method": "shadow",
        "instance_attributes": {"_value": 10, "value": 999, "method": "shadow"},
    }),
}


def check_experiment(namespace: dict[str, Any], number: int) -> None:
    """只检查当前实验，其他题尚未完成时也可调用。"""
    if not 1 <= number <= 18:
        raise ValueError("实验编号应在 1 到 18 之间。")
    if number in OBSERVATION_CHECKS:
        name, expected = OBSERVATION_CHECKS[number]
        _check_observation(namespace, name, expected)
    elif number == 14:
        _check_bounded_counter(namespace)
    elif number == 15:
        _check_grid_cell(namespace)
    elif number == 16:
        _check_snapshot_shelf(namespace)
    else:
        raise RuntimeError("检查器缺少当前实验的配置。")
    print(f"实验 {number} 检查通过。")


def run_checks(namespace: dict[str, Any]) -> None:
    """整章完成后复查，不替代逐题检查。"""
    for number in range(1, 19):
        check_experiment(namespace, number)
    print("第 6 章的 18 组客观观察和实现任务全部通过。")
    print("请继续核对属性查找图、MRO 过程和相等与哈希的口头解释。")


if __name__ == "__main__":
    print("请在第6章代码实验.ipynb中逐题调用 check_experiment()。")
