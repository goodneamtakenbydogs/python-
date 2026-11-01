"""第 2 章代码实验检查器。

每完成一组实验后立即执行：

    from chapter2_checks import check_experiment
    check_experiment(globals(), 实验编号)

全部完成后可以再调用 ``run_checks(globals())`` 复查。检查器只核对客观
运行结果，不评价复杂度解释和容器选型理由。
"""

from __future__ import annotations

import re
from typing import Any

UNFINISHED = "__未填写__"


class CheckFailure(AssertionError):
    """表示某一组实验记录尚未通过。"""


def _contains_unfinished(value: Any) -> bool:
    if value == UNFINISHED:
        return True
    if isinstance(value, dict):
        return any(_contains_unfinished(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_unfinished(item) for item in value)
    return False


def _require_mapping(namespace: dict[str, Any], name: str) -> dict[str, Any]:
    if name not in namespace:
        raise CheckFailure(
            f"找不到当前实验的填写结果。请先运行上面的实验单元格（变量 {name}）。"
        )

    value = namespace[name]
    if not isinstance(value, dict):
        raise CheckFailure(f"{name} 必须是字典，请保留 Notebook 给出的结构。")

    for label, item in value.items():
        if _contains_unfinished(item):
            raise CheckFailure(
                f"“{label}”尚未填写。请把整个 {UNFINISHED!r}（包括引号）"
                "替换成题目要求的 Python 值。"
            )

    return value


def _check_exact(
    namespace: dict[str, Any],
    name: str,
    expected: dict[str, Any],
) -> None:
    actual = _require_mapping(namespace, name)

    if len(actual) != len(expected):
        raise CheckFailure(
            f"实验记录应有 {len(expected)} 项，当前有 {len(actual)} 项，"
            "请保留 Notebook 给出的全部填写项。"
        )

    actual_by_id: dict[str, tuple[str, Any]] = {}
    for label, actual_value in actual.items():
        match = re.match(r"^(\d{2})\.\s+", label)
        if match is None:
            raise CheckFailure(f"字段“{label}”缺少 Notebook 提供的两位编号。")
        field_id = match.group(1)
        if field_id in actual_by_id:
            raise CheckFailure(f"实验记录中存在重复字段编号 {field_id}。")
        actual_by_id[field_id] = (label, actual_value)

    expected_ids = {f"{index:02d}" for index in range(1, len(expected) + 1)}
    if set(actual_by_id) != expected_ids:
        raise CheckFailure(
            "实验字段编号不完整，请保留 Notebook 给出的全部字段及编号。"
        )

    for index, expected_value in enumerate(expected.values(), start=1):
        label, actual_value = actual_by_id[f"{index:02d}"]
        if (
            type(actual_value) is not type(expected_value)
            or actual_value != expected_value
        ):
            raise CheckFailure(
                f"“{label}”与实验实际结果不一致，请重新运行当前实验并观察。"
            )


def _get_checks() -> list[tuple[str, dict[str, Any]]]:
    """返回各实验的内部判定数据，顺序与 Notebook 填写项一致。"""

    return [
        (
            "observation_01",
            {
                "after_append": [1, 2, [3, 4]],
                "after_extend": [1, 2, 3, 4],
                "after_insert": [1, 99, 2, 3, 4],
            },
        ),
        (
            "observation_02",
            {
                "after_remove": ["b", "a", "c"],
                "popped_value": "a",
                "after_del": ["c"],
                "after_clear": [],
            },
        ),
        (
            "observation_03",
            {
                "sort_return": None,
                "sorted_in_place": [1, 2, 3],
                "original_unchanged": [3, 1, 2],
                "new_sorted": [1, 2, 3],
                "reversed_values": [2, 1, 3],
            },
        ),
        (
            "observation_04",
            {
                "same_outer_object": False,
                "same_first_inner_object": True,
                "original_after_inner_change": [[1, 9], [2]],
            },
        ),
        (
            "observation_05",
            {
                "single_type": "tuple",
                "parenthesized_type": "int",
                "tuple_assignment_error": "TypeError",
                "tuple_value_after_iadd": (1, 2, 3),
                "tuple_alias_after_iadd": (1, 2),
                "tuple_identity_preserved": False,
                "list_value_after_iadd": [1, 2, 3],
                "list_alias_after_iadd": [1, 2, 3],
                "list_identity_preserved": True,
                "tuple_after_inner_change": (1, ["x"]),
                "plain_tuple_hashable": True,
                "nested_list_tuple_hashable": False,
            },
        ),
        (
            "observation_06",
            {
                "integer": True,
                "text": True,
                "plain_tuple": True,
                "list": False,
                "dictionary": False,
                "set": False,
                "frozen_set": True,
                "integer_equals_float": True,
                "equal_values_have_equal_hash": True,
            },
        ),
        (
            "observation_07",
            {
                "get_missing": 0,
                "contains_before_setdefault": False,
                "setdefault_result": 0,
                "final_mapping": {"A": 95, "B": 0, "C": 70},
            },
        ),
        (
            "observation_08",
            {
                "keys_after_change": ["a", "b"],
                "items_after_change": [("a", 1), ("b", 2)],
                "snapshot_before_change": ["a"],
            },
        ),
        (
            "observation_09",
            {
                "unique_sorted": [1, 2, 3],
                "intersection_sorted": [2, 3],
                "union_sorted": [1, 2, 3, 4],
                "difference_sorted": [1],
                "symmetric_difference_sorted": [1, 4],
            },
        ),
        (
            "observation_10",
            {
                "frozen_set_hashable": True,
                "lookup_result": "admin",
                "set_hashable": False,
            },
        ),
        (
            "observation_11",
            {
                "removed_left": 1,
                "removed_right": 4,
                "remaining": [2, 3],
            },
        ),
        (
            "observation_12",
            {
                "a_count": 3,
                "n_count": 2,
                "missing_count": 0,
                "most_common_one": ("a", 3),
            },
        ),
        (
            "observation_13",
            {
                "group_a": [1, 2],
                "group_b": [],
                "group_keys": ["A", "B"],
                "point_fields": (3, 4),
                "point_sum": 7,
            },
        ),
        (
            "observation_14",
            {
                "top_after_heapify": 1,
                "popped_after_push": 0,
                "new_top": 1,
                "remaining_sorted": [1, 2, 4, 5],
            },
        ),
        (
            "observation_15",
            {
                "kept_after_initial": [4, 5, 8],
                "third_largest_initial": 4,
                "kept_after_ten": [5, 8, 10],
                "third_largest_after_ten": 5,
            },
        ),
        (
            "observation_16",
            {
                "unsafe_result": [1, 2, 3],
                "safe_result": [1, 3],
                "dictionary_error": "RuntimeError",
            },
        ),
    ]

def check_experiment(namespace: dict[str, Any], experiment_number: int) -> None:
    """只检查一道实验，供 Notebook 在每道题后立即调用。"""

    checks = _get_checks()
    if not 1 <= experiment_number <= len(checks):
        raise ValueError(f"实验编号应在 1 到 {len(checks)} 之间。")

    name, expected = checks[experiment_number - 1]
    _check_exact(namespace, name, expected)
    print(f"实验 {experiment_number} 检查通过。")


def run_checks(namespace: dict[str, Any]) -> None:
    """全部完成后，复查 Notebook 中 16 组实验。"""

    for name, expected in _get_checks():
        _check_exact(namespace, name, expected)

    print("第 2 章的 16 组客观观察结果全部通过。")
    print("请继续检查复杂度解释、选型理由和面试题口述回答。")


if __name__ == "__main__":
    print("请在第2章代码实验.ipynb中逐题调用 check_experiment()。")
