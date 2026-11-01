"""第 4 章代码实验检查器。

每完成一组实验后立即执行：

    from chapter4_checks import check_experiment
    check_experiment(globals(), 实验编号)

全部完成后可以再调用 ``run_checks(globals())`` 复查。检查器只核对客观
结果，不评价闭包绑定图和装饰器阶段解释。
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
                "alias_same_function": True,
                "stored_results": [4, 6],
                "higher_order_result": 8,
                "returned_function_is_double": True,
                "returned_function_call": 10,
            },
        ),
        (
            "observation_02",
            {
                "double_result": 20,
                "triple_result": 30,
                "different_function_objects": True,
            },
        ),
        (
            "observation_03",
            {
                "first_box": ["A", "B"],
                "second_box": ["X"],
                "first_box_unchanged_by_second": ["A", "B"],
            },
        ),
        (
            "observation_04",
            {
                "counter_results": (1, 2),
                "collector_results": (["A"], ["A", "B"]),
            },
        ),
        (
            "observation_05",
            {
                "free_variable_names": ("factor",),
                "closure_cell_count": 1,
                "captured_value": 4,
                "plain_function_closure": None,
            },
        ),
        (
            "observation_06",
            {"late_bound_results": [2, 2, 2]},
        ),
        (
            "observation_07",
            {
                "default_fixed_results": [0, 1, 2],
                "factory_fixed_results": [0, 1, 2],
            },
        ),
        (
            "observation_08",
            {
                "events_after_definition": ["decorate"],
                "call_result": "Hello, Ming",
                "events_after_call": ["decorate", "before", "function", "after"],
            },
        ),
        (
            "observation_09",
            {
                "result": 5,
                "seen_args": (2,),
                "seen_kwargs": {"right": 3},
            },
        ),
        (
            "observation_10",
            {
                "plain_name": "wrapper",
                "plain_doc": None,
                "wrapped_name": "documented",
                "wrapped_doc": "保留这段文档。",
                "has_wrapped_reference": True,
            },
        ),
        (
            "observation_11",
            {
                "result": "Hello, Ming",
                "call_count": 3,
            },
        ),
        (
            "observation_12",
            {
                "definition_events": [
                    ("decorate", "inner"),
                    ("decorate", "outer"),
                ],
                "call_events": [
                    ("enter", "outer"),
                    ("enter", "inner"),
                    ("work", None),
                    ("leave", "inner"),
                    ("leave", "outer"),
                ],
            },
        ),
        (
            "observation_13",
            {
                "registry": ["Report"],
                "class_name": "Report",
                "instance_matches_class": True,
            },
        ),
        (
            "observation_14",
            {
                "lambda_result": 25,
                "mapped": [2, 4, 6, 8],
                "filtered": [2, 4],
                "comprehension": [4, 8],
            },
        ),
        (
            "observation_15",
            {
                "reduced_total": 10,
                "empty_total": 0,
                "partial_result": 25,
            },
        ),
        (
            "observation_16",
            {
                "initial_value": 4,
                "same_cached_object": True,
                "real_calls": [2],
                "hits": 1,
                "misses": 1,
                "cached_after_mutation": {"value": 4, "changed": True},
                "unhashable_error": "TypeError",
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

    print("第 4 章的 16 组客观观察结果全部通过。")
    print("请继续检查自由变量绑定、装饰阶段和调用阶段的文字解释。")


if __name__ == "__main__":
    print("请在第4章代码实验.ipynb中逐题调用 check_experiment()。")
