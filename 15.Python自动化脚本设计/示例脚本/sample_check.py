"""只读查询本地虚构快照，演示执行、解析、轮询与结果责任。"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

logger = logging.getLogger(__name__)
DEFAULTS = {"expected_count": 2, "timeout": 1.0, "budget": 3.0,
            "interval": 0.1, "max_attempts": 3}
EXIT_CODES = {"passed": 0, "check_failed": 1, "execution_error": 3,
              "protocol_error": 4, "task_failed": 5, "budget_exhausted": 6,
              "attempts_exhausted": 7}


class ExecutionFailure(RuntimeError):
    """进程无法启动或退出状态不符合查询协议。"""


class ProtocolFailure(ValueError):
    """输出无法解释为约定的快照。"""


class ReadTimeout(TimeoutError):
    """只读查询超时，不能据此推断外部业务已停止。"""


class BudgetExpired(TimeoutError):
    pass


class AttemptsExhausted(TimeoutError):
    pass


class TaskFailed(RuntimeError):
    pass


@dataclass(frozen=True)
class CommandResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class Snapshot:
    state: str
    count: int


@dataclass(frozen=True)
class Outcome:
    category: str
    stage: str
    attempts: int
    count: int | None
    detail: str


def positive_number(value, field):
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{field} must be a finite positive number")
    return float(value)


def resolve_settings(file_values=None, environ=None, overrides=None):
    """默认→文件→指定环境变量→显式 CLI；每层已提供的值均须合法。"""
    environment = os.environ if environ is None else environ
    settings = DEFAULTS.copy()

    def merge(values):
        if not isinstance(values, dict) or not values.keys() <= DEFAULTS.keys():
            raise ValueError("configuration contains unknown fields or is not an object")
        for name, value in values.items():
            if name in {"expected_count", "max_attempts"}:
                minimum = 0 if name == "expected_count" else 1
                if type(value) is not int or value < minimum:
                    raise ValueError(f"{name} must be an integer >= {minimum}")
            else:
                value = positive_number(value, name)
            settings[name] = value

    merge({} if file_values is None else file_values)
    if "CH15_SAMPLE_BUDGET" in environment:
        try:
            value = float(environment["CH15_SAMPLE_BUDGET"])
        except (TypeError, ValueError) as error:
            raise ValueError("CH15_SAMPLE_BUDGET must be numeric text") from error
        merge({"budget": value})
    if overrides is not None:
        merge({key: value for key, value in overrides.items() if value is not None})
    return settings


def parse_snapshot(text):
    try:
        data = json.loads(text)
    except (TypeError, ValueError) as error:
        raise ProtocolFailure("query output is not a valid snapshot") from error
    if type(data) is not dict or set(data) != {"state", "count"}:
        raise ProtocolFailure("snapshot fields must be state and count")
    if type(data["state"]) is not str or data["state"] not in {"pending", "ready", "failed"}:
        raise ProtocolFailure("snapshot state is not supported")
    if type(data["count"]) is not int or data["count"] < 0:
        raise ProtocolFailure("snapshot count must be a non-negative exact integer")
    return Snapshot(data["state"], data["count"])


def execute(argv, *, timeout, runner=None):
    """有限输出的直接子进程；非零退出结果保留给上层解释。"""
    timeout = positive_number(timeout, "timeout")
    if not isinstance(argv, (list, tuple)) or not argv or any(type(arg) is not str for arg in argv):
        raise ValueError("argv must be a non-empty sequence of text arguments")
    run = subprocess.run if runner is None else runner
    try:
        completed = run(
            list(argv), capture_output=True, text=True, encoding="utf-8",
            errors="strict", check=False, shell=False, timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired as error:
        raise ReadTimeout("query timed out; final business state is unknown") from error
    except OSError as error:
        raise ExecutionFailure("query process could not start") from error
    except UnicodeError as error:
        raise ProtocolFailure("query output could not be decoded as UTF-8") from error
    return CommandResult(tuple(argv), completed.returncode, completed.stdout, completed.stderr)


def poll_snapshot(fetch, *, budget, interval, max_attempts, clock=None, wait=None):
    """返回 (快照, 调用数)。截止点本身不接受结果；预算依赖协作者遵守超时。"""
    budget = positive_number(budget, "budget")
    interval = positive_number(interval, "interval")
    if type(max_attempts) is not int or max_attempts < 1:
        raise ValueError("max_attempts must be a positive exact integer")
    clock = time.monotonic if clock is None else clock
    wait = time.sleep if wait is None else wait
    deadline = clock() + budget
    for attempt in range(1, max_attempts + 1):
        remaining = deadline - clock()
        if remaining <= 0:
            raise BudgetExpired("overall budget exhausted before a new query")
        try:
            snapshot = fetch(remaining)
        except ReadTimeout as error:
            if clock() >= deadline:
                raise BudgetExpired("overall budget exhausted during query") from error
            if attempt == max_attempts:
                raise AttemptsExhausted("read attempts exhausted") from error
        else:
            if clock() >= deadline:
                raise BudgetExpired("query result arrived at or after deadline")
            if snapshot.state == "failed":
                raise TaskFailed("query reported a terminal failed state")
            if snapshot.state == "ready":
                return snapshot, attempt
            if attempt == max_attempts:
                raise AttemptsExhausted("pending state did not finish within attempt limit")
        remaining = deadline - clock()
        if remaining <= 0:
            raise BudgetExpired("overall budget exhausted before waiting")
        wait(min(interval, remaining))
    raise AssertionError("positive attempt limit must return or raise")


def check_file(source, *, expected_count=2, timeout=1.0, budget=3.0, interval=0.1,
               max_attempts=3, executor=None, clock=None, wait=None):
    settings = resolve_settings({}, {}, {
        "expected_count": expected_count, "timeout": timeout, "budget": budget,
        "interval": interval, "max_attempts": max_attempts,
    })
    execute_command = execute if executor is None else executor
    probe = Path(__file__).with_name("sample_probe.py")
    argv = [sys.executable, "-X", "utf8", str(probe), str(Path(source).resolve())]
    attempts = 0

    def fetch(remaining):
        nonlocal attempts
        attempts += 1
        result = execute_command(argv, timeout=min(settings["timeout"], remaining))
        if result.returncode != 0:
            raise ExecutionFailure(f"query exited with code {result.returncode}")
        return parse_snapshot(result.stdout)

    try:
        snapshot, attempts = poll_snapshot(
            fetch, budget=settings["budget"], interval=settings["interval"],
            max_attempts=settings["max_attempts"], clock=clock, wait=wait,
        )
    except ExecutionFailure as error:
        return Outcome("execution_error", "execution", attempts, None, str(error))
    except ProtocolFailure as error:
        return Outcome("protocol_error", "parse", attempts, None, str(error))
    except TaskFailed as error:
        return Outcome("task_failed", "state", attempts, None, str(error))
    except BudgetExpired as error:
        return Outcome("budget_exhausted", "wait", attempts, None, str(error))
    except AttemptsExhausted as error:
        return Outcome("attempts_exhausted", "wait", attempts, None, str(error))
    matched = snapshot.count == settings["expected_count"]
    return Outcome("passed" if matched else "check_failed", "check", attempts,
                   snapshot.count, "count matched" if matched else "count did not match")


def atomic_write_json(destination, record):
    """同目录写完关闭后替换；不承诺断电持久性、并发仲裁或多文件事务。"""
    destination = Path(destination)
    payload = json.dumps(record, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
    pending = None
    try:
        with NamedTemporaryFile("w", encoding="utf-8", dir=destination.parent,
                                prefix=".sample-check-", suffix=".tmp", delete=False) as stream:
            pending = Path(stream.name)
            stream.write(payload)
        os.replace(pending, destination)
    except BaseException:
        if pending is not None:
            try:
                pending.unlink(missing_ok=True)
            except OSError:
                logger.exception("temporary report cleanup failed")
        raise


def build_parser():
    parser = argparse.ArgumentParser(description="查询本地虚构快照并检查数量")
    parser.add_argument("source", type=Path, help="UTF-8 快照文件，供本地查询子进程读取")
    parser.add_argument("--config", type=Path, help="JSON 配置文件；配置中的路径不参与本例覆盖")
    parser.add_argument("--expected-count", type=int, default=None)
    parser.add_argument("--timeout", type=float, default=None)
    parser.add_argument("--budget", type=float, default=None)
    parser.add_argument("--interval", type=float, default=None)
    parser.add_argument("--max-attempts", type=int, default=None)
    parser.add_argument("--report", type=Path, help="可选报告目标，父目录必须存在")
    return parser


def main(argv=None, *, environ=None, executor=None, clock=None, wait=None):
    args = build_parser().parse_args(argv)
    try:
        protected = {args.source.resolve()}
        if args.config is not None:
            protected.add(args.config.resolve())
        if args.report is not None and args.report.resolve() in protected:
            raise ValueError("report must not overwrite source or configuration")
        file_values = {} if args.config is None else json.loads(args.config.read_text(encoding="utf-8"))
        if type(file_values) is not dict:
            raise ValueError("configuration file must contain an object")
        overrides = {key: getattr(args, key) for key in DEFAULTS}
        settings = resolve_settings(file_values, environ, overrides)
    except (OSError, UnicodeError, ValueError) as error:
        print(f"configuration error: {error}", file=sys.stderr)
        return 2
    try:
        outcome = check_file(args.source, **settings, executor=executor, clock=clock, wait=wait)
    except KeyboardInterrupt:
        print("check interrupted; business state may be unknown", file=sys.stderr)
        return 130
    record = asdict(outcome)
    code = EXIT_CODES[outcome.category]
    if args.report is not None:
        try:
            atomic_write_json(args.report, record)
        except (OSError, ValueError, TypeError) as error:
            record["report_error"] = type(error).__name__
            print("report could not be saved", file=sys.stderr)
            code = 8
    print(json.dumps(record, ensure_ascii=False, allow_nan=False))
    if code and "report_error" not in record:
        print(f"check ended at stage {outcome.stage}: {outcome.category}", file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
