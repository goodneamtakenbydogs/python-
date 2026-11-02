"""可选的有限批量执行组件；汇总命令本身保持顺序读取。"""

import math
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass

from .errors import Cancelled, ConfigError


@dataclass(frozen=True)
class TaskResult:
    index: int
    status: str
    value: object = None
    error_type: str | None = None


def map_bounded(items, worker, *, workers=2, max_in_flight=4, budget=None, should_stop=None):
    """按完成消费，保留输入序号；提前关闭时取消未开始项并等待运行项收尾。

    budget 限制调度和接受结果，不强制停止线程、输入迭代或任意阻塞函数。
    调用方须使用有限输入和可收尾的 worker；部分消费时负责 close()。
    """
    if type(workers) is not int or not 1 <= workers <= 8:
        raise ConfigError("workers must be within 1..8")
    if type(max_in_flight) is not int or not 1 <= max_in_flight <= 32:
        raise ConfigError("max_in_flight must be within 1..32")
    if budget is not None:
        if type(budget) not in (int, float) or not math.isfinite(budget) or budget <= 0:
            raise ConfigError("budget must be finite and positive")
    stop = (lambda: False) if should_stop is None else should_stop
    deadline = None if budget is None else time.monotonic() + budget

    def remaining():
        if stop():
            raise Cancelled("batch cancelled")
        if deadline is None:
            return None
        value = deadline - time.monotonic()
        if value <= 0:
            raise TimeoutError("batch observation budget exhausted")
        return value

    remaining()
    source = iter(items)
    pending = {}
    exhausted = False
    index = 0
    pool = ThreadPoolExecutor(max_workers=workers)
    try:
        while True:
            while not exhausted and len(pending) < max_in_flight:
                remaining()
                try:
                    item = next(source)
                except StopIteration:
                    exhausted = True
                    break
                remaining()
                pending[pool.submit(worker, item)] = index
                index += 1
            if not pending:
                return
            done, _ = wait(pending, timeout=remaining(), return_when=FIRST_COMPLETED)
            remaining()
            if not done:
                raise TimeoutError("batch observation budget exhausted")
            for future in sorted(done, key=pending.__getitem__):
                remaining()
                position = pending.pop(future)
                try:
                    result = TaskResult(position, "completed", value=future.result())
                except Exception as error:
                    result = TaskResult(position, "error", error_type=type(error).__name__)
                yield result
    finally:
        for future in pending:
            future.cancel()
        try:
            pool.shutdown(wait=True, cancel_futures=True)
        finally:
            close = getattr(source, "close", None)
            if close is not None:
                close()
