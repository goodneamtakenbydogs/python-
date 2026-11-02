# 测试结果汇总示例工具

这是第十六章的可安装 Python 工具，使用虚构 JSONL 测试记录。本例把读取、校验、筛选、汇总、报告与命令入口分开，演示自身测试、构建与安装验证，不连接真实系统。

## 1. 建立环境并运行

在本目录使用独立环境；这里有完整项目元数据，不再借用上两级仓库环境。

```text
uv sync --group dev
uv run study-results examples/results.jsonl --run-id sample-all
uv run study-results examples/results.jsonl --status passed --run-id sample-selected
uv run python -m study_results examples/results.jsonl --status skipped
uv run study-results --help
```

完整示例包含 passed、failed、skipped 各一项，汇总成功且所选集合含 failed 时退出 1，这是示例的预期结果；仅选 passed 或 skipped 时退出 0。退出 0 表示本次汇总完成且选中项无 failed，不证明未选测试或产品整体正确。空输入允许汇总为零，明确保留 input_total=0、selected_total=0。

## 2. 输入、配置与输出约定

每个非空物理行是 UTF-8 JSON 对象，恰含 case_id、status、duration。编号为非空文本，去掉首尾空白后不能重复；status 为 passed、failed、skipped 之一；duration 为 0～86400 的有限秒数，不接受 bool。空白行忽略但仍参与物理行号，单行不超过 65536 字节，包含换行字节。输入在读取时按上限处理，不先整文件加载。

配置覆盖为默认、JSON 配置、指定环境变量、显式 CLI。默认选择全部状态、max_records=1000；上限允许 1～10000。环境仅识别 `STUDY_RESULTS_MAX_RECORDS`；CLI `--status` 可重复。文件中 statuses 是无重复的状态数组，空数组明确选择零项。每层已提供值都验证，未知字段拒绝，CLI None 表示没提供，文件 null 不作为有效值。

所有记录先校验、检查重复和总数限制，再按状态筛选，不能用过滤隐藏坏数据。input_total 是读取到的有效记录总数，selected_total 是选中数量，counts 只统计选中记录；duration_seconds 是选中耗时之和。编号集合和选中耗时暂存最多由 max_records 限制，本例不宣称常数内存或无限流处理。

stdout 是一份 JSON 报告，stderr 是带 run_id 的结构化过程记录；不把调试文本混入结果，不输出完整输入内容或环境。schema_version=1 表示报告结构版本，与发行包版本 0.1.0 分开。

## 3. 文件报告与退出码

`--output` 指向已有父目录中的其他路径，不能覆盖输入或配置。先全部读取和汇总，再序列化、写同目录临时文件、关闭并替换；输入或提交失败时不发布半份新报告，旧目标保留。报告保存失败退出 4，不向 stdout 宣称本次报告已提交。取消在协作检查点或用户中断处退出 130。

| 退出码 | 本例含义 |
|---:|---|
| 0 / 1 | 汇总完成且选中项无 failed / 选中项含 failed |
| 2 / 3 / 4 | 配置或使用错误 / 输入错误 / 报告错误 |
| 130 | 协作取消或用户中断 |

结果可见性不等于断电持久性，本例没有多文件事务、并发写入仲裁或远程操作。旧报告的 run_id 也不应被误认为本次执行。

## 4. 自身测试、构建和干净安装

```text
uv run ruff check src tests scripts
uv run pytest -q --junitxml=reports/junit.xml
uv build
uv run python scripts/verify_wheel.py "dist/*.whl"
uv run python scripts/benchmark_core.py --records 1000
```

`uv build` 生成 sdist 与 wheel；验收脚本要求通配模式恰好匹配一个 wheel。它在仓库之外创建新环境，只安装该 wheel，移除 PYTHONPATH 等来源干扰，验证实际导入位置、发行版本、console script 和 `python -m`、空输入与错误退出。构建产物和 reports 是本地生成内容，不提交。

benchmark 只测当前进程的虚构记录构造与内存汇总，包括 tracemalloc 开销，不含文件读取、网络、工具安装或系统压力。测量数值随环境变化，不能用一次时间作通用性能承诺。

## 5. 模块与可选批量组件

models 表达记录与结果，config 解析配置值，reader 管理文件与行协议，engine 做一次遍历，report 组织格式和提交，cli 连接终端。普通导入不读取实参或打开输入，入口适配器可换，核心不反向依赖 CLI。

batch.map_bounded 是独立的有限并发教学组件，主汇总命令没有为了并发而并发。它限制工作线程与在途 Future 数，返回带输入序号的完成或错误记录；输入须有限、worker 须可收尾。部分消费要 close，提前取消时取消未开始项并等待已开始项。budget 约束调度和结果接受，不强制停止线程、输入迭代或任意阻塞函数，收尾可能超过预算。

进一步插件、多任务恢复、大数据存储和项目发布流程不在本例中实现。资料继续按独立 Python 学习目标扩展，不把第十六章视为固定终点。
