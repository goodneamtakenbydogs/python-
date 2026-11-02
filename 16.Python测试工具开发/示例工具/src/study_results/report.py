"""报告结构与文件提交分离；临时文件只由本次写入者负责。"""

import json
import logging
import os
import re
from pathlib import Path
from tempfile import NamedTemporaryFile

from .errors import ConfigError, ReportError

logger = logging.getLogger(__name__)


def validate_run_id(run_id):
    if type(run_id) is not str or re.fullmatch(r"[A-Za-z0-9_-]{1,40}", run_id) is None:
        raise ConfigError("run_id must contain 1..40 letters, digits, underscores or hyphens")
    return run_id


def render_report(summary, run_id):
    validate_run_id(run_id)
    return {"schema_version": 1, "run_id": run_id, "input_total": summary.input_total,
            "selected_total": summary.selected_total,
            "counts": {"passed": summary.passed, "failed": summary.failed, "skipped": summary.skipped},
            "duration_seconds": summary.duration_seconds}


def write_report(destination, report, *, replace=None):
    destination = Path(destination)
    try:
        payload = json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
    except (ValueError, TypeError) as error:
        raise ReportError("report is not serializable") from error
    replace = os.replace if replace is None else replace
    pending = None
    try:
        with NamedTemporaryFile("w", encoding="utf-8", dir=destination.parent,
                                prefix=".study-results-", suffix=".tmp", delete=False) as stream:
            pending = Path(stream.name)
            stream.write(payload)
        replace(pending, destination)
    except BaseException as original:
        if pending is not None:
            try:
                pending.unlink(missing_ok=True)
            except OSError:
                logger.exception("report_cleanup_failed")
        if isinstance(original, OSError):
            raise ReportError("report could not be committed") from original
        raise
