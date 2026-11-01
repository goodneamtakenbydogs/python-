"""第 8 章 Notebook 的逐题客观检查。"""

from __future__ import annotations

import types
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


def _check_observation(namespace: dict[str, Any], name: str, expected: dict[str, Any]) -> None:
    import re

    actual = namespace.get(name)
    if not isinstance(actual, dict):
        raise CheckFailure(f"找不到 {name} 的填写字典，请先运行当前实验。")
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
            raise CheckFailure(f"“{label}”尚未填写。请替换完整占位字符串。")
        if type(value) is not type(expected_value) or value != expected_value:
            raise CheckFailure(f"“{label}”与实际运行结果不一致，请重新观察本题。")


def _require_function(namespace: dict[str, Any], name: str, number: int) -> Callable[..., Any]:
    value = namespace.get(name)
    if not callable(value):
        raise CheckFailure(f"实验 {number} 找不到可调用的 {name}。")
    return value


def _check_module_report(namespace: dict[str, Any]) -> None:
    function = _require_function(namespace, "module_report", 16)
    module = types.ModuleType("demo_pkg.tools")
    module.__package__ = "demo_pkg"
    module.__file__ = "C:/study/demo_pkg/tools.py"
    module.__spec__ = None
    expected = {
        "name": "demo_pkg.tools",
        "package": "demo_pkg",
        "origin": "C:/study/demo_pkg/tools.py",
        "is_package": False,
    }
    try:
        actual = function(module)
    except Exception as error:
        raise CheckFailure("实验 16 生成普通模块报告时失败。") from error
    if actual != expected:
        raise CheckFailure("实验 16 的普通模块报告字段或值不符合题意。")

    package = types.ModuleType("demo_pkg")
    package.__package__ = "demo_pkg"
    package.__path__ = ["C:/study/demo_pkg"]
    package.__spec__ = None
    package_report = function(package)
    if package_report != {
        "name": "demo_pkg",
        "package": "demo_pkg",
        "origin": None,
        "is_package": True,
    }:
        raise CheckFailure("实验 16 应正确处理没有 __file__ 的包对象。")


def _check_dependency_order(namespace: dict[str, Any]) -> None:
    function = _require_function(namespace, "dependency_order", 17)
    graph = {
        "app": {"service", "config"},
        "service": {"model"},
        "config": set(),
        "model": set(),
    }
    snapshot = {name: set(dependencies) for name, dependencies in graph.items()}
    try:
        order = function(graph)
    except Exception as error:
        raise CheckFailure("实验 17 处理无环依赖图时失败。") from error
    if not isinstance(order, list) or set(order) != set(graph) or len(order) != len(graph):
        raise CheckFailure("实验 17 应让每个模块恰好出现一次。")
    positions = {name: index for index, name in enumerate(order)}
    for module, dependencies in graph.items():
        for dependency in dependencies:
            if positions[dependency] > positions[module]:
                raise CheckFailure("实验 17 的依赖模块必须排在使用者之前。")
    if graph != snapshot:
        raise CheckFailure("实验 17 不应修改输入依赖图。")
    if function({}) != []:
        raise CheckFailure("实验 17 的空依赖图应返回空列表。")
    try:
        function({"a": {"b"}, "b": {"a"}})
    except ValueError:
        pass
    except Exception as error:
        raise CheckFailure("实验 17 检测循环时应抛出 ValueError。") from error
    else:
        raise CheckFailure("实验 17 应检测循环依赖。")


def _check_audit_dependencies(namespace: dict[str, Any]) -> None:
    function = _require_function(namespace, "audit_dependencies", 18)
    imports = ["yaml", "requests", "json", "company_tool", "requests"]
    mapping = {"yaml": "PyYAML", "requests": "requests", "json": None}
    declared = {"requests", "pytest"}
    snapshots = (imports.copy(), mapping.copy(), declared.copy())
    try:
        result = function(imports, mapping, declared)
    except Exception as error:
        raise CheckFailure("实验 18 审计依赖时运行失败。") from error
    if result != {
        "missing_distributions": ["PyYAML"],
        "unknown_imports": ["company_tool"],
    }:
        raise CheckFailure("实验 18 的缺失发行包或未知导入名结果不符合题意。")
    if (imports, mapping, declared) != snapshots:
        raise CheckFailure("实验 18 不应修改输入对象。")
    empty = function([], {}, set())
    if empty != {"missing_distributions": [], "unknown_imports": []}:
        raise CheckFailure("实验 18 应正确处理空输入。")


OBSERVATION_CHECKS: dict[int, tuple[str, dict[str, Any]]] = {
    1: ("observation_01", {
        "is_module": True, "module_name": "math", "has_sqrt": True,
    }),
    2: ("observation_02", {
        "after_exec": ["module body"],
        "after_call": ["module body", "function body"],
    }),
    3: ("observation_03", {
        "module_current": "prod", "imported_old": "dev", "shared_items": ["A"],
    }),
    4: ("observation_04", {"same_object": True, "cache_same": True}),
    5: ("observation_05", {
        "imported_events": [], "main_events": ["ran main"],
    }),
    6: ("observation_06", {
        "alias_name": "math", "alias_same": True, "sqrt_result": 4.0,
    }),
    7: ("observation_07", {
        "spec_found": True, "spec_name": "json", "has_loader": True,
    }),
    8: ("observation_08", {"path_is_list": True, "all_strings": True}),
    9: ("observation_09", {
        "public_value": 1, "internal_value": 2, "all_names": ["public"],
    }),
    10: ("observation_10", {
        "events": ["package", "submodule"], "answer": 42,
        "parent_has_child": True,
    }),
    11: ("observation_11", {"relative_result": 15, "package_name": "chapter8_relative_pkg"}),
    12: ("observation_12", {"error_name": "RuntimeError", "left_in_cache": False}),
    13: ("observation_13", {
        "error_name": "AttributeError", "mentions_partial": True,
    }),
    14: ("observation_14", {
        "prefix_is_text": True, "base_is_text": True, "venv_flag_is_bool": True,
    }),
    15: ("observation_15", {
        "project_name": "python-interview-study", "python_requirement": ">=3.11",
        "runtime_dependencies": [], "has_dev_group": True,
    }),
}


def check_experiment(namespace: dict[str, Any], number: int) -> None:
    """只检查当前实验。"""
    if not 1 <= number <= 18:
        raise ValueError("实验编号应在 1 到 18 之间。")
    if number in OBSERVATION_CHECKS:
        name, expected = OBSERVATION_CHECKS[number]
        _check_observation(namespace, name, expected)
    elif number == 16:
        _check_module_report(namespace)
    elif number == 17:
        _check_dependency_order(namespace)
    else:
        _check_audit_dependencies(namespace)
    print(f"实验 {number} 检查通过。")


def run_checks(namespace: dict[str, Any]) -> None:
    """整章完成后复查。"""
    for number in range(1, 19):
        check_experiment(namespace, number)
    print("第 8 章的 18 组客观观察和实现任务全部通过。")
    print("请继续口述导入时间线、循环依赖和环境复现过程。")


if __name__ == "__main__":
    print("请在第8章代码实验.ipynb中逐题调用 check_experiment()。")
