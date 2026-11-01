"""第 1 章代码实验检查器。

每完成一组实验后立即执行：

    from chapter1_checks import check_experiment
    check_experiment(globals(), 实验编号)

全部完成后可以再调用 ``run_checks(globals())`` 复查。检查器只核对可以
客观判断的观察结果，不评价文字解释是否充分。
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
    """返回 16 组实验的内部判定数据。"""

    return [
        (
            "observation_01",
            {
                "integer_type": "int",
                "decimal_type": "float",
                "text_type": "str",
                "converted_integer": 42,
            },
        ),
        (
            "observation_02",
            {
                "same_identity_before": True,
                "same_value_before": True,
                "first_after_append": [10, 20, 30],
            },
        ),
        (
            "observation_03",
            {
                "equal_values": True,
                "same_identity": False,
                "alias_same_identity": True,
            },
        ),
        (
            "observation_04",
            {
                "original_after_mutation": [1, 2, 3],
                "original_after_rebinding": [1, 2, 3],
                "alias_after_rebinding": [99],
            },
        ),
        (
            "observation_05",
            {
                "list_identity_preserved": True,
                "text_identity_preserved": False,
                "list_value": [1, 2, 3],
                "text_value": "abc",
            },
        ),
        (
            "observation_06",
            {
                "none_truth": False,
                "zero_truth": False,
                "empty_text_truth": False,
                "nonempty_list_truth": True,
                "none_is_none": True,
            },
        ),
        (
            "observation_07",
            {
                "and_result": "",
                "or_result": "fallback",
                "short_circuit_result": True,
            },
        ),
        (
            "observation_08",
            {
                "true_division": 2.5,
                "floor_division": 2,
                "negative_floor_division": -3,
                "negative_remainder": 1,
            },
        ),
        (
            "observation_09",
            {
                "directly_equal": False,
                "close_enough": True,
            },
        ),
        (
            "observation_10",
            {
                "first_character": "p",
                "last_character": "n",
                "middle_slice": "yth",
                "reversed_text": "nohtyp",
            },
        ),
        (
            "observation_11",
            {
                "membership": True,
                "comparison_chain": True,
                "precedence_result": True,
            },
        ),
        (
            "observation_12",
            {
                "break_has_else": False,
                "complete_has_else": True,
                "continued_values": [1, 3],
            },
        ),
        (
            "observation_13",
            {
                "range_values": [1, 2, 3],
                "enumerated": [(0, "a"), (1, "b")],
                "zipped": [(1, "a"), (2, "b")],
            },
        ),
        (
            "observation_14",
            {
                "first": 10,
                "middle": [20, 30],
                "last": 40,
                "even_squares": [4, 16],
                "shared_rows": [["x"], ["x"], ["x"]],
            },
        ),
        (
            "observation_15",
            {
                "custom_equals_none": True,
                "custom_is_none": False,
                "none_equals_none": True,
                "none_is_none": True,
            },
        ),
        (
            "observation_16",
            {
                "not_empty_text": True,
                "not_nonempty_list": False,
                "arithmetic_precedence": 14,
                "arithmetic_parenthesized": 20,
                "logic_precedence": True,
                "comparison_before_not": True,
                "membership_not_in": True,
                "identity_is_not": False,
                "evaluation_order": ["first", "second", "third"],
                "evaluation_result": 7,
                "short_circuit_order": ["left"],
                "short_circuit_result": True,
            },
        ),
    ]

def check_experiment(namespace: dict[str, Any], experiment_number: int) -> None:
    """只检查一道主实验，供 Notebook 在每道题后立即调用。"""

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

    print("第 1 章的 16 组客观观察结果全部通过。")
    print("请继续检查 Notebook 中的原因解释，并进行面试题口述练习。")


def run_equality_protocol_check(namespace: dict[str, Any]) -> None:
    """兼容旧 Notebook：只检查第 15 个实验。"""

    name, expected = _get_checks()[14]
    _check_exact(namespace, name, expected)
    print("补充实验：相等性协议与 None 的客观结果通过。")


def run_logic_precedence_check(namespace: dict[str, Any]) -> None:
    """兼容旧 Notebook：只检查第 16 个实验。"""

    name, expected = _get_checks()[15]
    _check_exact(namespace, name, expected)
    print("补充实验：逻辑运算、优先级和求值顺序的客观结果通过。")


if __name__ == "__main__":
    print("请在第1章代码实验.ipynb中逐题调用 check_experiment()。")
