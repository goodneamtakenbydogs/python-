"""小范围共享条件与公开 pytest 扩展。"""

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--include-extra", action="store_true", default=False,
        help="执行 extra 标记的附加教学检查",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--include-extra"):
        return
    marker = pytest.mark.skip(reason="使用 --include-extra 执行附加教学检查")
    for item in items:
        if "extra" in item.keywords:
            item.add_marker(marker)


@pytest.fixture
def report_path(tmp_path):
    return tmp_path / "report.txt"


@pytest.fixture
def report_factory(tmp_path):
    created = []

    def create(name):
        path = tmp_path / f"report-{len(created)}.txt"
        path.write_text(name, encoding="utf-8")
        created.append(path)
        return path

    # pytest 按临时目录保留策略管理文件；不是“退出就删除”的承诺。
    return create
