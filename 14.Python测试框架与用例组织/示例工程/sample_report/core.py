"""明确的小规则，用来观察测试组织，而非实现完整导出工具。"""

import logging
from pathlib import Path

from .source import read_label

logger = logging.getLogger(__name__)


def render_report(labels: list[str], *, title: str = "Report") -> str:
    """接收 0～3 条单行非空标签；输出标题和各标签，始终以换行结尾。"""
    if type(labels) is not list:
        raise TypeError("labels must be a list")
    if not isinstance(title, str):
        raise TypeError("title must be text")
    if not title.strip() or "\n" in title or "\r" in title:
        raise ValueError("title must be a non-empty single line")
    if len(labels) > 3:
        raise ValueError("at most three labels")
    for label in labels:
        if not isinstance(label, str):
            raise TypeError("each label must be text")
        if not label.strip() or "\n" in label or "\r" in label:
            raise ValueError("each label must be a non-empty single line")
    return "\n".join([title, *labels]) + "\n"


def write_report(labels: list[str], path: Path, *, title: str = "Report") -> None:
    """先完成输入验证再写文件；本例不承诺写入中断时的原子替换。"""
    text = render_report(labels, title=title)
    path.write_text(text, encoding="utf-8")


def label_title(case_id: str) -> str:
    """读取一条虚构记录，返回大写标签；读取异常原样传播。"""
    label = read_label(case_id)["label"]
    result = label.upper()
    logger.info("label formatted", extra={"case_id": case_id})
    return result
