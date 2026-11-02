"""逐行读取有长度上限的 UTF-8 JSONL，错误保留物理行号。"""

import json
from pathlib import Path

from .errors import Cancelled, InputError
from .models import CaseRecord

MAX_LINE_BYTES = 65536


def parse_line(text, *, line_number=1):
    try:
        data = json.loads(text)
    except (TypeError, ValueError) as error:
        raise InputError("invalid JSON", line=line_number) from error
    if type(data) is not dict or set(data) != {"case_id", "status", "duration"}:
        raise InputError("record fields must be case_id, status and duration", line=line_number)
    return CaseRecord(**data, line=line_number)


def read_records(source, *, should_stop=None):
    stop = (lambda: False) if should_stop is None else should_stop
    number = 0
    try:
        with Path(source).open("rb") as stream:
            while True:
                if stop():
                    raise Cancelled("input reading cancelled")
                raw = stream.readline(MAX_LINE_BYTES + 1)
                if not raw:
                    return
                number += 1
                if len(raw) > MAX_LINE_BYTES:
                    raise InputError("line exceeds byte limit", line=number)
                try:
                    text = raw.decode("utf-8")
                except UnicodeError as error:
                    raise InputError("input is not UTF-8", line=number) from error
                if not text.strip():
                    continue
                yield parse_line(text, line_number=number)
    except OSError as error:
        raise InputError("input could not be read", line=number or None) from error
