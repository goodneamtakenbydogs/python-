"""本地教学查询端：原样输出 UTF-8 文件，让调用方负责协议解析。"""

import argparse
import sys
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description="输出本地虚构快照")
    parser.add_argument("source", type=Path)
    args = parser.parse_args(argv)
    try:
        text = args.source.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        print("sample snapshot could not be read", file=sys.stderr)
        return 3
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
