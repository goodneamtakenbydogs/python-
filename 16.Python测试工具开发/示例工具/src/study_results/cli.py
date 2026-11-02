"""终端适配层；仅此处读取实参、环境并安排结果输出。"""

import argparse
import json
import os
import sys
import uuid
from contextlib import ExitStack
from pathlib import Path

from . import __version__
from .config import resolve_config
from .engine import summarize
from .errors import Cancelled, ConfigError, InputError, ReportError
from .models import STATUSES
from .reader import read_records
from .report import render_report, validate_run_id, write_report


def build_parser():
    parser = argparse.ArgumentParser(description="汇总本地虚构测试结果 JSONL")
    parser.add_argument("source", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--status", choices=STATUSES, action="append", default=None)
    parser.add_argument("--max-records", type=int, default=None)
    parser.add_argument("--output", type=Path, help="可选 JSON 报告，父目录必须存在")
    parser.add_argument("--run-id", default=None, help="可选本次运行编号")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _event(event, run_id, **fields):
    print(json.dumps({"event": event, "run_id": run_id, **fields}, ensure_ascii=False), file=sys.stderr)


def main(argv=None, *, environ=None, reader=None, writer=None):
    args = build_parser().parse_args(argv)
    run_id = args.run_id if args.run_id is not None else uuid.uuid4().hex
    try:
        validate_run_id(run_id)
        protected = {args.source.resolve()}
        if args.config is not None:
            protected.add(args.config.resolve())
        if args.output is not None and args.output.resolve() in protected:
            raise ConfigError("output must not overwrite input or configuration")
        try:
            file_values = {} if args.config is None else json.loads(args.config.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError) as error:
            raise ConfigError("configuration could not be loaded") from error
        if type(file_values) is not dict:
            raise ConfigError("configuration must be an object")
        config = resolve_config(file_values, os.environ if environ is None else environ,
                                {"statuses": args.status, "max_records": args.max_records})
        read = read_records if reader is None else reader
        with ExitStack() as stack:
            records = read(args.source)
            close = getattr(records, "close", None)
            if close is not None:
                stack.callback(close)
            summary = summarize(records, config)
        report = render_report(summary, run_id)
        if args.output is not None:
            save = write_report if writer is None else writer
            save(args.output, report)
        print(json.dumps(report, ensure_ascii=False, allow_nan=False))
        _event("summary_finished", run_id, input_total=summary.input_total, selected_total=summary.selected_total)
        return 1 if summary.failed else 0
    except ConfigError as error:
        _event("summary_failed", None, category="configuration", message=str(error))
        return 2
    except InputError as error:
        _event("summary_failed", run_id, category="input", message=str(error), line=error.line)
        return 3
    except ReportError as error:
        _event("summary_failed", run_id, category="report", message=str(error))
        return 4
    except (Cancelled, KeyboardInterrupt):
        _event("summary_cancelled", run_id)
        return 130
