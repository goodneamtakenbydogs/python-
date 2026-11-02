"""公开的最小汇总接口；导入不读取文件、不解析命令行。"""

from .engine import summarize
from .models import CaseRecord, Summary

__version__ = "0.1.0"
__all__ = ["CaseRecord", "Summary", "summarize"]
