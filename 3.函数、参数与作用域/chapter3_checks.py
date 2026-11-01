"""第 3 章代码实验检查器。

每完成一组实验后立即执行：

    from chapter3_checks import check_experiment
    check_experiment(globals(), 实验编号)

全部完成后可以再调用 ``run_checks(globals())`` 复查。检查器只核对客观
运行结果，不评价作用域解释和口头表达。
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
        raise CheckFailure("实验字段编号不完整，请保留 Notebook 给出的全部字段及编号。")

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
    """返回各实验的内部判定数据，字段顺序对应 Notebook 编号。"""

    return [
        (
            "observation_01",
            {
                "events_after_definition": [],
                "events_after_call": ["called"],
                "call_result": "finished",
            },
        ),
        (
            "observation_02",
            {
                "function_is_callable": True,
                "number_is_callable": False,
                "alias_same_function": True,
                "alias_call_result": 10,
            },
        ),
        (
            "observation_03",
            {
                "implicit_return": None,
                "explicit_empty_return": None,
                "multiple_return": (3, 2),
                "multiple_return_type": "tuple",
            },
        ),
        (
            "observation_04",
            {
                "positional": ("A", 80),
                "keyword": ("B", 90),
                "mixed": ("C", 70),
                "duplicate_error": "TypeError",
            },
        ),
        (
            "observation_05",
            {
                "pos_only": 1,
                "normal": 2,
                "default": 3,
                "args": (4, 5),
                "keyword_only": 6,
                "kwargs": {"extra": 7},
            },
        ),
        (
            "observation_06",
            {
                "sequence_expansion": 24,
                "mapping_expansion": 60,
                "duplicate_expansion_error": "TypeError",
            },
        ),
        (
            "observation_07",
            {
                "events_after_definition": ["default-created"],
                "first_call": 10,
                "second_call": 10,
                "events_after_calls": ["default-created"],
            },
        ),
        (
            "observation_08",
            {
                "first_snapshot": ["A"],
                "second_snapshot": ["A", "B"],
                "same_return_object": True,
                "first_return_final": ["A", "B"],
            },
        ),
        (
            "observation_09",
            {
                "first_default": ["A"],
                "second_default": ["B"],
                "separate_default_objects": True,
                "explicit_list_after_call": ["C"],
            },
        ),
        (
            "observation_10",
            {
                "caller_after_mutation": [1, 2, 3],
                "caller_after_rebinding": [1, 2, 3],
                "replacement_return": [99],
            },
        ),
        (
            "observation_11",
            {
                "local_value": "local",
                "enclosing_value": "enclosing",
                "global_value": "global",
                "builtin_length": 3,
            },
        ),
        (
            "observation_12",
            {
                "error_type": "UnboundLocalError",
                "global_count_after_error": 10,
            },
        ),
        (
            "observation_13",
            {
                "global_count": 11,
                "nonlocal_results": (1, 2),
            },
        ),
        (
            "observation_14",
            {
                "if_name": "inside-if",
                "loop_name": 2,
                "comprehension_outer_name": 100,
                "squares": [0, 1, 4],
            },
        ),
        (
            "observation_15",
            {
                "stored_call": 8,
                "higher_order_result": 5,
                "annotation_keys": ["left", "return", "right"],
                "annotated_string_call": "ab",
            },
        ),
        (
            "observation_16",
            {
                "factorial_result": 6,
                "trace": [
                    ("enter", 3),
                    ("enter", 2),
                    ("enter", 1),
                    ("enter", 0),
                    ("return", 0, 1),
                    ("return", 1, 1),
                    ("return", 2, 2),
                    ("return", 3, 6),
                ],
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

    print("第 3 章的 16 组客观观察结果全部通过。")
    print("请继续检查参数绑定图、作用域解释和面试题口述回答。")


if __name__ == "__main__":
    print("请在第3章代码实验.ipynb中逐题调用 check_experiment()。")
