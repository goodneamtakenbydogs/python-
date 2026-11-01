"""第 5 章代码实验检查器。

每完成一组实验后立即执行：

    from chapter5_checks import check_experiment
    check_experiment(globals(), 实验编号)

全部完成后可以再调用 ``run_checks(globals())`` 复查。检查器只核对客观
运行结果和函数行为，不评价学习者对状态变化的文字解释。
"""

from __future__ import annotations

import inspect
import re
from collections.abc import Callable
from typing import Any

UNFINISHED = "__未填写__"


class CheckFailure(AssertionError):
    """表示某一组实验尚未通过。"""


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


def _require_function(
    namespace: dict[str, Any],
    name: str,
    experiment_number: int,
) -> Callable[..., Any]:
    value = namespace.get(name)
    if value is None:
        raise CheckFailure(
            f"实验 {experiment_number} 找不到 {name}。请先运行函数定义单元格。"
        )
    if not callable(value):
        raise CheckFailure(f"实验 {experiment_number} 中的 {name} 必须可以调用。")
    return value


def _check_generator_function(
    function: Callable[..., Any],
    name: str,
    experiment_number: int,
) -> None:
    if not inspect.isgeneratorfunction(function):
        raise CheckFailure(
            f"实验 {experiment_number} 的 {name} 应按题意写成生成器函数，"
            "请检查是否通过 yield 逐项产出。"
        )


def _check_countdown(namespace: dict[str, Any]) -> None:
    function = _require_function(namespace, "countdown", 11)
    _check_generator_function(function, "countdown", 11)

    cases = [
        (4, [4, 3, 2, 1]),
        (1, [1]),
        (0, []),
        (-3, []),
    ]
    for start, expected in cases:
        try:
            actual = list(function(start))
        except Exception as error:
            raise CheckFailure(
                f"实验 11 在 start={start!r} 时运行失败，请检查边界和停止条件。"
            ) from error
        if actual != expected:
            raise CheckFailure(
                f"实验 11 在 start={start!r} 时产出顺序不符合题意，请逐次检查状态。"
            )

    first = function(3)
    second = function(3)
    if first is second:
        raise CheckFailure("实验 11 每次调用都应建立一次新的生成器状态。")


def _check_flatten_once(namespace: dict[str, Any]) -> None:
    function = _require_function(namespace, "flatten_once", 12)
    _check_generator_function(function, "flatten_once", 12)

    cases = [
        ([[1, 2], (), [3]], [1, 2, 3]),
        ([], []),
        (["ab", "c"], ["a", "b", "c"]),
        ((iter([1, 2]), iter([3])), [1, 2, 3]),
    ]
    for groups, expected in cases:
        try:
            actual = list(function(groups))
        except Exception as error:
            raise CheckFailure(
                "实验 12 处理某组可迭代输入时运行失败，请检查逐层委托过程。"
            ) from error
        if actual != expected:
            raise CheckFailure(
                "实验 12 的逐项产出结果不符合题意，请确认只展开一层并保持顺序。"
            )


def _check_matching_lines(namespace: dict[str, Any]) -> None:
    function = _require_function(namespace, "matching_lines", 16)
    _check_generator_function(function, "matching_lines", 16)

    lines = ["INFO start\n", "ERROR failed\r\n", "ERROR keep spaces  \n", "done"]
    snapshot = lines.copy()
    result = function(lines, "ERROR")
    if not inspect.isgenerator(result):
        raise CheckFailure(
            "实验 16 调用后应得到按需产出的生成器对象，不应直接建立完整结果。"
        )

    try:
        actual = list(result)
    except Exception as error:
        raise CheckFailure("实验 16 在消费结果时运行失败，请检查每一行的处理。") from error

    if actual != ["ERROR failed", "ERROR keep spaces  "]:
        raise CheckFailure(
            "实验 16 的过滤或行尾处理不符合题意，请区分换行符和其他尾部空格。"
        )
    if lines != snapshot:
        raise CheckFailure("实验 16 不应修改传入的行列表。")

    one_shot = iter(["x\n", "target\n", "target end"])
    if list(function(one_shot, "target")) != ["target", "target end"]:
        raise CheckFailure("实验 16 还应支持只能向前消费一次的输入迭代器。")


OBSERVATION_CHECKS: dict[int, tuple[str, dict[str, Any]]] = {
    1: (
        "observation_01",
        {
            "new_iterator_is_list": False,
            "iterator_returns_self": True,
            "list_has_next": False,
            "iterator_has_next": True,
        },
    ),
    2: (
        "observation_02",
        {
            "first": 10,
            "second": 20,
            "end_signal_name": "StopIteration",
            "default_after_end": "结束",
        },
    ),
    3: (
        "observation_03",
        {
            "collected": ["A", "B", "C"],
            "after_loop": "没有下一项",
        },
    ),
    4: (
        "observation_04",
        {
            "first_one": 1,
            "first_two": 2,
            "second_one": 1,
            "first_remaining": [3],
            "second_remaining": [2, 3],
        },
    ),
    5: (
        "observation_05",
        {
            "first_via_alias": 0,
            "remaining_via_original": [2, 4],
            "after_exhaustion": [],
        },
    ),
    6: (
        "observation_06",
        {
            "events_after_creation": [],
            "first_value": 10,
            "events_after_first": ["start"],
            "second_value": 20,
            "events_after_second": ["start", "resume"],
        },
    ),
    7: (
        "observation_07",
        {
            "first": 1,
            "second": 2,
            "remaining": [3],
            "after_end": "结束",
        },
    ),
    8: (
        "observation_08",
        {
            "yielded": "A",
            "return_value": "done",
            "after_end": "结束",
        },
    ),
    9: (
        "observation_09",
        {
            "events_after_creation": [],
            "first_value": 0,
            "events_after_first": [0],
            "remaining_values": [10, 20],
            "events_after_all": [0, 1, 2],
        },
    ),
    10: (
        "observation_10",
        {
            "eager_events_after_creation": [0, 1, 2],
            "lazy_events_after_creation": [],
            "eager_values": [0, 1, 4],
            "lazy_first": 0,
            "lazy_events_after_first": [0],
        },
    ),
    13: (
        "observation_13",
        {
            "initial": 0,
            "after_sending_five": 5,
            "after_sending_two": 7,
        },
    ),
    14: (
        "observation_14",
        {
            "first": "ready",
            "after_throw": "ready",
            "events_after_throw": ["handled"],
            "events_after_close": ["handled", "closed"],
            "after_close": "结束",
        },
    ),
    15: (
        "observation_15",
        {
            "chained": [1, 2, 3, 4],
            "first_four": [10, 13, 16, 19],
            "next_after_slice": 22,
            "taken": [1, 3],
            "dropped": [5, 2],
            "first_progress": (0, 1),
            "second_first": 0,
            "second_remaining": [1, 2, 3, 4],
            "first_remaining": [2, 3, 4],
        },
    ),
}


def check_experiment(namespace: dict[str, Any], experiment_number: int) -> None:
    """只检查一道实验，供 Notebook 在每道题后立即调用。"""

    if not 1 <= experiment_number <= 16:
        raise ValueError("实验编号应在 1 到 16 之间。")

    if experiment_number in OBSERVATION_CHECKS:
        name, expected = OBSERVATION_CHECKS[experiment_number]
        _check_exact(namespace, name, expected)
    elif experiment_number == 11:
        _check_countdown(namespace)
    elif experiment_number == 12:
        _check_flatten_once(namespace)
    elif experiment_number == 16:
        _check_matching_lines(namespace)
    else:
        raise RuntimeError("检查器缺少当前实验的内部配置。")

    print(f"实验 {experiment_number} 检查通过。")


def run_checks(namespace: dict[str, Any]) -> None:
    """全部完成后，复查 Notebook 中 16 组实验。"""

    for experiment_number in range(1, 17):
        check_experiment(namespace, experiment_number)

    print("第 5 章的 16 组客观观察和实现任务全部通过。")
    print("请继续用自己的话解释每次消费如何推进状态，以及惰性计算的取舍。")


if __name__ == "__main__":
    print("请在第5章代码实验.ipynb中逐题调用 check_experiment()。")
