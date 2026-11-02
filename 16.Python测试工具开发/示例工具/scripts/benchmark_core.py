"""只测虚构数据的构造与内存汇总，不把结果称作系统性能测试。"""

import argparse
import json
import time
import tracemalloc

from study_results import CaseRecord, summarize
from study_results.config import Config


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", type=int, default=1000)
    args = parser.parse_args(argv)
    if not 1 <= args.records <= 10000:
        parser.error("records must be within 1..10000")
    tracemalloc.start()
    started = time.perf_counter()
    records = (CaseRecord(f"C-{index}", "passed", 0.001) for index in range(args.records))
    summary = summarize(records, Config(max_records=args.records))
    elapsed = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(json.dumps({"records": summary.input_total, "elapsed_seconds": elapsed,
                      "traced_peak_bytes": peak, "scope": "record construction and in-memory summary"}))


if __name__ == "__main__":
    main()
