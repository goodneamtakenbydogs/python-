# 第十四章示例工程

这是使用虚构数据的本地 pytest 工程。先在仓库根目录执行 `uv sync --group dev`，再进入本目录运行以下命令。`--project ../..` 选择上两级仓库的依赖环境，同时保留当前工作目录，让 pytest 读取本地配置。此目录仅有测试配置，依赖仓库的开发环境，不是单独可发布的发行包。

```text
uv run --project ../.. python -m pytest tests/test_report.py::test_empty_report -v
uv run --project ../.. python -m pytest --collect-only -q
uv run --project ../.. python -m pytest -q -ra
uv run --project ../.. python -m pytest -m smoke -q
uv run --project ../.. python -m pytest "tests/test_report.py::test_render_rows[upper]" -q
uv run --project ../.. python -m pytest --include-extra -q
uv run --project ../.. python -m pytest -q --junitxml=reports/junit.xml
```

默认整组应为 **15 passed、1 skipped**，启用额外测试后为 **16 passed**；收集应为 16 项。跳过的原因是示例选项，不能把该项算作已验证。没有外部系统、网络或并行插件前提；报告输出属于本地运行产物，不提交。

## 1. 需求与文件

`sample_report/core.py` 的 `render_report` 接收精确 list，允许 0～3 条单行非空 str 标签，标题也要求单行非空 str。空白字符串拒绝，合法文本原样保留。返回标题与各标签按换行拼接的文本，最后有换行，输入列表不变。

`write_report` 先渲染、再以 UTF-8 写目标路径。输入拒绝时旧文件保持；它没有承诺磁盘写入中断时的原子替换。`label_title` 调用 `core.read_label` 一次并返回 label 的大写形式，读取失败原样传播。source 中仅有故意拒绝真实读取的接口，测试通过替身供数。

`tests/data/cases.json` 保存输入与独立预期；路径相对测试文件定位，顶层加载失败属于收集问题。`tests/conftest.py` 提供临时路径、路径工厂与 `--include-extra` 开关。`pyproject.toml` 注册标记、开启严格标记与严格 xfail；这里没有 xfail 用例，其实际行为在 Notebook 中观察。

## 2. 自己修改并复盘

先在个人副本中运行一项用例，解释 expected 来自哪条规则。再补一个边界；故意改错断言，读节点和差异后恢复；查看 `--setup-show` 中的准备与清理。完成后运行整组，记录本次选择范围、收集数量和未测内容。

现有测试用于演示组织方式，不宣称覆盖所有组合。请自己分析标题边界、异常字段和写入故障等缺口。不要将“示例整组通过”表述成“报告工具已经具备完整质量保证”。
