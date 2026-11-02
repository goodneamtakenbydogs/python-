"""一次遍历验证、筛选与汇总；不解析终端实参，不写报告。"""

import math

from .config import Config
from .errors import Cancelled, InputError
from .models import CaseRecord, Summary


def summarize(records, config=None, *, should_stop=None):
    config = Config() if config is None else config
    stop = (lambda: False) if should_stop is None else should_stop
    counts = dict.fromkeys(("passed", "failed", "skipped"), 0)
    seen = set()
    input_total = selected_total = 0
    durations = []
    for record in records:
        if stop():
            raise Cancelled("summary cancelled")
        if not isinstance(record, CaseRecord):
            raise InputError("summary input must contain CaseRecord objects")
        input_total += 1
        if input_total > config.max_records:
            raise InputError("record limit exceeded", line=record.line)
        if record.case_id in seen:
            raise InputError("duplicate case_id", line=record.line)
        seen.add(record.case_id)
        if record.status in config.statuses:
            selected_total += 1
            counts[record.status] += 1
            durations.append(record.duration)
    if stop():
        raise Cancelled("summary cancelled before completion")
    return Summary(input_total, selected_total, counts["passed"], counts["failed"],
                   counts["skipped"], math.fsum(durations))
