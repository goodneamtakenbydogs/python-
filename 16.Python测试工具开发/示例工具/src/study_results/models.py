"""小型不可变记录；类型标注之外，显式验证运行时约定。"""

import math
from dataclasses import dataclass

from .errors import InputError

STATUSES = ("passed", "failed", "skipped")


@dataclass(frozen=True)
class CaseRecord:
    case_id: str
    status: str
    duration: float
    line: int | None = None

    def __post_init__(self):
        if type(self.case_id) is not str or not self.case_id.strip():
            raise InputError("case_id must be non-empty text", line=self.line)
        if type(self.status) is not str or self.status not in STATUSES:
            raise InputError("unsupported status", line=self.line)
        if type(self.duration) not in (int, float):
            raise InputError("duration must be a number", line=self.line)
        try:
            seconds = float(self.duration)
        except OverflowError as error:
            raise InputError("duration is out of range", line=self.line) from error
        if not math.isfinite(seconds) or not 0 <= seconds <= 86400:
            raise InputError("duration must be within 0..86400 seconds", line=self.line)
        object.__setattr__(self, "case_id", self.case_id.strip())
        object.__setattr__(self, "duration", seconds)


@dataclass(frozen=True)
class Summary:
    input_total: int
    selected_total: int
    passed: int
    failed: int
    skipped: int
    duration_seconds: float
