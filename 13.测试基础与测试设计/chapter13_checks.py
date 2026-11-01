"""第十三章客观检查；测试理由、风险和报告仍需人工评审。"""
from __future__ import annotations

import re
from itertools import product
from typing import Any

UNFINISHED = "__未填写__"


class CheckFailure(AssertionError):
    """当前题的记录或实现尚未符合题意。"""


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
    result = {}
    for label, value in mapping.items():
        match = re.match(r"^(\d{2})\.\s+", label) if isinstance(label, str) else None
        _require(match is not None and match.group(1) not in result,
                 f"{phase}字段“{label}”的编号缺失或重复。")
        _require(not _unfinished(value),
                 f"{phase}字段“{label}”尚未填写，请替换包括引号的整个占位字符串。")
        result[match.group(1)] = (label, value)
    _require(set(result) == {f"{index:02d}" for index in range(1, count + 1)},
             f"本题{phase}字段编号不完整。")
    return result


def _matches(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, (tuple, list)):
        return len(actual) == len(expected) and all(_matches(a, e) for a, e in zip(actual, expected))
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(_matches(actual[key], value) for key, value in expected.items())
    return actual == expected


OBSERVATIONS = {
    1: [True, False], 2: [13, True, False],
    3: [["below", "inside", "above", "invalid type", "invalid type"]],
    4: [True, False, False], 5: [[1, 2, 3], [False, True, False]],
    6: [True, "NameError", False], 7: [4, 1, 3], 8: [False, True],
    9: [["draft", "queued", "running", "done"], "done"], 10: ["ValueError", "queued", True],
    11: [6, 5, [("running", "cancel")]], 12: [12, False, 4, 8], 13: [6, 11, 12],
    14: [{"limit": 3, "timeout": 2}, False], 15: [2, 1], 16: [True, 3, False, "pending"],
    17: [0, 2, False], 18: [True, ["A"], False], 19: [False, ["A"], []],
    20: [["false", "true"], [80, 110], 100], 21: [True, False],
    22: [True, 1, ["R-2", "R-3"]], 23: [["B", "A", "C"]], 24: [["zero"], True],
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


def _function(namespace, name):
    function = namespace.get(name)
    _require(callable(function), f"找不到 {name}，请先运行本题定义单元格。")
    return function


def _expect_error(function, args, error_type, message, **kwargs):
    try:
        function(*args, **kwargs)
    except error_type:
        return
    raise CheckFailure(message)


def _check_count_cases(namespace):
    function = _function(namespace, "make_count_cases")
    for lower, upper in ((1, 5), (2, 2), (-2, 1), (0, 1), (0, 30), (10**12, 10**12 + 3)):
        rows = function(lower, upper)
        _require(type(rows) is list and 1 <= len(rows) <= 12,
                 "实验 25 的返回集合不符合题面接口。")
        values = []
        for index, row in enumerate(rows, 1):
            _require(type(row) is dict and set(row) == {"value", "accepted", "purpose"},
                     f"实验 25 的第 {index} 条字段不符合题面。")
            value = row["value"]
            _require(type(value) is int and type(row["accepted"]) is bool,
                     f"实验 25 的第 {index} 条用例类型不符合接口。")
            _require(isinstance(row["purpose"], str) and bool(row["purpose"].strip()),
                     f"实验 25 的第 {index} 条设计理由尚未填写。")
            # 独立检查闭区间分类，不调用学习者的其他函数生成预期。
            expected = not (value < lower or value > upper)
            _require(row["accepted"] is expected,
                     f"实验 25 的第 {index} 条预期与闭区间约定不一致。")
            values.append(value)
        _require(len(set(values)) == len(values), "实验 25 应按题面去掉重复位置。")
        required = {lower - 1, lower, lower + 1, upper - 1, upper, upper + 1}
        _require(required <= set(values), "实验 25 仍遗漏题面要求的边界相邻位置。")
        again = function(lower, upper)
        _require(again is not rows and all(a is not b for a in rows for b in again),
                 "实验 25 每次应建立新的用例记录，不共享可变结果。")
    for lower, upper in ((2, 1), (0, -1)):
        _expect_error(function, (lower, upper), ValueError, "实验 25 未拒绝反向区间。")
    for lower, upper in ((True, 5), (1, False), (1.0, 3), (1, None), ("1", 5)):
        _expect_error(function, (lower, upper), TypeError, "实验 25 未按题意检查上下界类型。")


def _permission(authenticated, owner, admin):
    if not authenticated:
        return False
    if owner:
        return True
    return admin


def _check_permission_cases(namespace):
    function = _function(namespace, "design_permission_cases")
    rows = function()
    _require(type(rows) is list and len(rows) == 8, "实验 26 的表格规模不符合题面。")
    inputs = []
    for index, row in enumerate(rows, 1):
        _require(type(row) is tuple and len(row) == 4 and all(type(value) is bool for value in row),
                 f"实验 26 的第 {index} 行字段不符合接口。")
        _require(row[3] is _permission(*row[:3]),
                 f"实验 26 的第 {index} 行预期与权限约定不一致。")
        inputs.append(row[:3])
    _require(len(set(inputs)) == 8 and set(inputs) == set(product([False, True], repeat=3)),
             "实验 26 存在重复或遗漏的条件组合。")
    _require(function() is not rows, "实验 26 每次应返回新列表。")


STATES = ("draft", "queued", "running", "done", "failed", "cancelled")
TRANSITIONS = {("draft", "submit"): "queued", ("queued", "start"): "running",
               ("queued", "cancel"): "cancelled", ("running", "finish"): "done",
               ("running", "fail"): "failed", ("running", "cancel"): "cancelled"}


def _check_trace(namespace):
    function = _function(namespace, "trace_task")
    for state in STATES:
        result = function(iter([]), initial=state)
        _require(_matches(result, [state]), "实验 27 的空事件或指定初始状态不符合接口。")
        _require(function([], initial=state) is not result, "实验 27 不应共享跨调用轨迹列表。")
        for event in ("submit", "start", "cancel", "finish", "fail", "unknown"):
            target = TRANSITIONS.get((state, event))
            if target is None:
                _expect_error(function, ([event],), ValueError,
                              "实验 27 接受了未声明的状态迁移。", initial=state)
            else:
                _require(_matches(function(iter([event]), initial=state), [state, target]),
                         "实验 27 的某项合法迁移不符合题面。")
    for events, expected in (
        (["submit", "start", "finish"], ["draft", "queued", "running", "done"]),
        (["submit", "start", "fail"], ["draft", "queued", "running", "failed"]),
        (["submit", "cancel"], ["draft", "queued", "cancelled"]),
        (["submit", "start", "cancel"], ["draft", "queued", "running", "cancelled"]),
    ):
        before = events.copy()
        _require(_matches(function(events), expected), "实验 27 的完整合法序列不符合规则。")
        _require(events == before, "实验 27 不应修改输入事件。")
        _require(_matches(function(iter(events)), expected), "实验 27 应支持只能遍历一次的输入。")
    for state in ("unknown", None, [], True):
        _expect_error(function, ([],), ValueError, "实验 27 未拒绝无效初始状态。", initial=state)
    for event in (None, 1, True, []):
        _expect_error(function, ([event],), ValueError, "实验 27 未按题面拒绝非文本事件。")
    _expect_error(function, (["submit", "submit"],), ValueError,
                  "实验 27 应验证中间迁移，不能只看最终事件。")


def _permission_mutants():
    def allow_all(auth, owner, admin):
        return True

    def deny_all(auth, owner, admin):
        return False

    def no_auth(auth, owner, admin):
        return owner or admin

    def owner_only(auth, owner, admin):
        return auth and owner

    def admin_only(auth, owner, admin):
        return auth and admin

    def both_roles(auth, owner, admin):
        return auth and owner and admin

    def integer_result(auth, owner, admin):
        return int(_permission(auth, owner, admin))

    return (allow_all, deny_all, no_auth, owner_only, admin_only, both_roles, integer_result)


def _check_contract(namespace):
    function = _function(namespace, "assert_permission_contract")

    def equivalent(auth, owner, admin):
        return bool(auth and (owner or admin))

    for correct in (_permission, equivalent):
        _require(function(correct) is None, "实验 28 对正确候选应正常结束并返回 None。")
    for mutant in _permission_mutants():
        try:
            function(mutant)
        except Exception:  # noqa: BLE001 - 候选的意外异常也是失败，正确候选已分别验证。
            rejected = True
        else:
            rejected = False
        _require(rejected, "实验 28 放过了某类典型错误，请检查条件组合、预期与返回类型。")
    calls = []

    def recording(auth, owner, admin):
        calls.append((auth, owner, admin))
        return _permission(auth, owner, admin)

    function(recording)
    _require(all(all(type(value) is bool for value in row) for row in calls),
             "实验 28 对候选的调用应遵守本题布尔输入约定。")
    _require(set(calls) == set(product([False, True], repeat=3)),
             "实验 28 实际执行的组合仍有遗漏。")


IMPLEMENTATIONS = {25: _check_count_cases, 26: _check_permission_cases,
                   27: _check_trace, 28: _check_contract}


def check_experiment(namespace: dict[str, Any], number: int) -> None:
    """独立检查当前题，不评价文字理由，也不改写学习记录。"""
    if type(number) is not int or not 1 <= number <= 28:
        raise ValueError("实验编号应为 1 到 28。")
    try:
        if number <= 24:
            _check_observation(namespace, number)
        else:
            IMPLEMENTATIONS[number](namespace)
    except CheckFailure:
        raise
    except Exception as error:
        raise CheckFailure(f"实验 {number} 运行失败，请检查本题数据结构、边界与异常约定。") from error
    print(f"实验 {number} 客观检查通过；选择理由、预期依据和结论范围仍需解释。")


def run_checks(namespace: dict[str, Any]) -> None:
    """全部完成后的补充复查，不包含综合人工设计评审。"""
    for number in range(1, 29):
        check_experiment(namespace, number)
    print("第 13 章 28 道客观检查通过；综合测试方案、缺陷报告和风险判断仍需人工复盘。")


if __name__ == "__main__":
    print("请在第13章代码实验.ipynb中逐题调用 check_experiment()。")
