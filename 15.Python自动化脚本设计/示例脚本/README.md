# 第十五章示例脚本

这是只读查询本地虚构快照的小脚本，用于学习输入、执行、解析、等待、判断和报告责任，不是远程系统工具。只使用标准库，测试使用仓库已声明的 pytest。

先在仓库根目录 `uv sync --group dev`，再进入本目录执行。`--project ../..` 明确使用仓库环境并保留当前工作目录。

```text
uv run --project ../.. python -X utf8 sample_check.py snapshot.json
uv run --project ../.. python -X utf8 sample_check.py snapshot.json --expected-count 3
uv run --project ../.. python -X utf8 sample_check.py missing-snapshot.json
uv run --project ../.. python -X utf8 sample_check.py snapshot.json --budget 0
uv run --project ../.. python -m pytest test_sample_check.py -q
```

前四条分别演示通过、检查不匹配、查询执行失败与配置错误，退出码依次为 0、1、3、2。后两种非零是要观察的结果，不应反复运行到碰巧通过。脚本成功启动检查后，stdout 输出一条 JSON 记录，stderr 用于简要诊断；帮助和参数错误仍按 argparse 约定输出。

## 1. 文件与执行过程

`sample_check.py` 保存配置解析、执行器、快照解析、有限轮询、数量判断和入口。`sample_probe.py` 是明确的本地子进程，只将指定 UTF-8 文件原样写入 stdout；因此退出 0 仍可能包含不合法输出，调用方必须解析与校验。`snapshot.json` 是虚构 ready/count 快照，测试在临时目录构造其他状态与故障。

`test_sample_check.py` 用可控执行器、时钟和等待函数验证 pending、超时、迟到结果、终止失败、非零退出与坏输出，同时真实运行小型本地子进程检查实参、非零退出、超时及完整 CLI。所有真实进程都有限时，查询端不创建后代。

## 2. 配置与停止约定

默认 expected_count=2、timeout=1 秒、budget=3 秒、interval=0.1 秒、max_attempts=3。覆盖顺序为默认、JSON 配置、指定环境变量 `CH15_SAMPLE_BUDGET`、显式 CLI；每层提供的值均先验证，不让后层掩盖无效配置。数量是非负精确整数，次数是正精确整数，三个时间是有限正数。CLI 未提供用 None 表示，文件 null 不是有效数值。

查询输出严格为含 state、count 的对象；state 允许 pending、ready、failed，count 为非负精确整数，布尔值不作为数量。ready 后才比较数量，failed 立即结束，未知状态或结构错误不重试；只读查询的 ReadTimeout 允许在次数和预算内再次观察。每次 timeout 不大于当前剩余预算，最后一次失败后不等待，恰在截止点返回的结果也拒绝。

预算约束决策，并依赖底层执行器遵守 timeout；启动和清理可增加实际耗时，不承诺硬实时截止、任意后代进程停止或外部业务回滚。查询超时不能证明业务尚未发生。

## 3. 报告与退出状态

先自行建立目标父目录，再通过 `--report` 指定输出路径。例如在已有个人临时目录保存 `report.json`，不将运行产物写入资料文件。报告目标不得与输入或配置相同。报告先序列化、同目录写临时文件、关闭后替换，失败保护旧目标并清理自身临时文件；不承诺断电持久性、多文件事务或并发仲裁。

| 退出码 | 本例约定 |
|---:|---|
| 0 / 1 / 2 | 检查通过 / 数量不匹配 / 配置或命令错误 |
| 3 / 4 / 5 | 执行错误 / 协议错误 / 终止失败状态 |
| 6 / 7 | 总预算耗尽 / 尝试次数耗尽 |
| 8 / 130 | 显式报告未保存 / 接收到用户中断 |

若检查通过而报告失败，退出 8，stdout 仍保留原 category 并增加 report_error，让调用方同时看到业务与保存结果。这些码值属于本脚本约定，不能套用 pytest 的码表。

## 4. 自己的修改与复盘

先解释一次正常调用的各层结果，再在个人副本或临时目录中构造一种坏输出、一种 pending 序列和一个截止边界。保留第一次失败、调用次数和传给执行器的 timeout，说明哪个阶段结束、哪些状态仍未知。

自动检查不评价测试方案是否完整。并行批量、远程调用、海量输出与工具打包均未在这个小脚本中实现；相关概念在讲义说明，进一步实现需另外定义接口与验证范围。
