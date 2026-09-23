# SEM 工作流


## 版本区分

此分支是 **Codex 重构版**，于 2026-09-22 单独保存，与原版并行保留。

| 版本 | GitHub 入口 | 说明 |
|---|---|---|
| 自建原版 | [main](https://github.com/Cecilia-oleni/sem-automation/tree/main) | 保留原来的架构，仍为仓库默认分支 |
| Codex 重构版 | [codex/refactor-2026-09-22](https://github.com/Cecilia-oleni/sem-automation/tree/codex/refactor-2026-09-22) | 当前代码，包含物料流程、月报和分层模块 |

本次上传仅保存到重构版分支，不合并至 `main`。上传时原版最新提交为 [`7a5cbd3`](https://github.com/Cecilia-oleni/sem-automation/commit/7a5cbd31ac13df51eb14e058d1f5a082a9800604)。

本仓库保存代码、配置和模板；`.env`、客户上传资料、运行输出、虚拟环境及本机运行配置留在本地，不随代码上传。

这个项目做两件事：**准备投放物料**和**生成月报**，两条流程可以分别运行。

**第一次看项目，先读 [工作流操作指南](docs/工作流操作指南.md)**：用浅显的语言集中说明架构、模块用途、文件如何交接、人工节点，以及整套和单模块运行命令。

## 文档导航

| 想了解什么 | 看这里 |
|---|---|
| 整体流程、文件交接、单独运行、去哪里取结果 | [工作流操作指南](docs/工作流操作指南.md) |
| 月报换月、联网采集、离线复用、宇通历史表同步 | [月报操作说明](docs/月报操作说明.md) |
| 后续改代码或扩展功能 | [架构与后续扩展](docs/架构与后续扩展.md) |
| Wordstat 参数、缓存、限流续跑、筛选算法 | [Wordstat 技术说明](docs/Wordstat技术说明.md) |
| 本次 Wordstat 接入验证了什么 | [Wordstat 接入验收记录](docs/Wordstat接入验收记录.md) |
| 具体函数接口、详细交接约定 | [模块接口与交接清单](<experiments/archive/项目日志/模块接口清单(pipeline_v1).md>) |
| 之前重构验证了什么 | [改造验收记录](docs/改造验收记录.md) |

## 打开项目

唯一项目目录：`D:\sem自动化`。在 VS Code 中打开此目录，选择“终端 → 新建终端”（PowerShell）。不需要进入第二层同名目录，也不需要先激活虚拟环境。

```powershell
Set-Location -LiteralPath 'D:\sem自动化'
& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' --help
```

## 常用命令

物料资料放到 `uploads/materials/项目名/`；中间结果、人工审核文件和最终物料在 `outputs/materials/项目名/`。已有物料项目已归入这两个目录，人工文件保留。

```powershell
& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' materials run --project '通亚' --dry-run
& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' materials run --project '通亚'
```

`--dry-run` 不联网、不写文件。正式运行保留已有结果处理、人工断点和网站分支。Wordstat 已自动接入：审核种子 Excel/CSV → 全量查询与限流续跑 → AI 筛选分组翻译 → 人工最终审核 → 否词和广告语。默认全部地区，每种子最多30个扩展候选，最终最多600词。补齐人工文件后运行同一命令续跑。

操作步骤见 [工作流操作指南](docs/工作流操作指南.md)，独立查询、地区配置、缓存与筛选规则见 [Wordstat 技术说明](docs/Wordstat技术说明.md)。

宇通八月 Yandex 月报（本地数据）：

```powershell
& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' reports yutong --config '.\config\reports\yutong\2026-08.json' --month 2026-08 --check-only
& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' reports yutong --config '.\config\reports\yutong\2026-08.json' --month 2026-08
```

安琪八月离线复用（保留已有译文，不调用翻译）：

```powershell
& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' reports angel-yeast --config '.\config\angel_yeast_direct_monthly.json' --month 2026-08 --reuse-raw '.\outputs\_archive\angel_yeast\2026-08\_internal\direct_monthly_data.json' --skip-translation
```

通用报告离线复用：

```powershell
& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' reports standard --client '.\config\clients\lingyu.json' --month 2026-07 --source existing --data-dir '.\outputs\_archive\lingyu\2026-07'
```

换月、联网采集、宇通历史表同步的完整步骤见 [月报操作说明](docs/月报操作说明.md)。

## 结果在哪里

每次报告运行打印新目录：

```text
outputs/reports/<客户>/<报告类型>/<月份>/runs/<运行编号>/
├── deliverables/          正式 Excel
├── _internal/             原始数据、核对、运行清单和预览
└── history_candidates/    宇通历史表候选副本
```

宇通通过核对后才将报告放入 `deliverables`；失败信息见 `_internal/status.json`。默认生成不会覆盖真实历史表，`sync` 是独立命令。

## 目录说明

| 目录 | 用途 |
|---|---|
| `sem_automation/materials/` | 物料业务与人工断点 |
| `sem_automation/reporting/` | 三类报告及各自 Excel 渲染 |
| `sem_automation/integrations/yandex/` | Direct / Metrika / Wordstat 客户端；安琪适配器独立 |
| `sem_automation/ai/`、`readers/`、`core/` | 模型、读取、路径和运行记录 |
| `config/`、`prompts/`、`templates/` | 配置、提示词和模板 |
| `experiments/wordstat/` | 旧 Wordstat 实验与缓存；正式流程不导入 |
| `experiments/archive/` | 旧脚本、记录和迁移工具，不参与日常运行 |
| `outputs/_archive/` | 旧报告、原始 JSON 和回归参照 |
| `outputs/_migration/` | 改造前代码快照、Git 状态、迁移和验收记录 |

模块职责、接口与人工断点见 [模块接口与交接清单](<experiments/archive/项目日志/模块接口清单(pipeline_v1).md>)。该清单保留原项目日志位置，已更新为当前分层版本。

未来 Direct 上传的边界见 [架构与后续扩展](docs/架构与后续扩展.md)。本次未实现上传。

## 环境与测试

当前虚拟环境及 VS Code 路径已统一。新机器首次准备环境时运行：

```powershell
python -m venv .venv
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
```

Excel 渲染需要 Node.js 和 `@oai/artifact-tool`。本机运行路径在 `config/runtime.local.json`，`node_modules` 指向已安装依赖。`.env` 留在根目录，勿提交密钥。

```powershell
& '.\.venv\Scripts\python.exe' -X utf8 -m unittest discover -s tests -v
```

日常使用统一入口，无需逐个点击“运行 Python 文件”。部分物料模块支持单独运行，所需文件和命令见[操作指南](docs/工作流操作指南.md)；单跑可能直接覆盖该模块结果，不经过总流程的覆盖确认。
