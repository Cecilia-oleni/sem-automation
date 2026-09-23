# Wordstat 接入与维护

更新：2026-09-22。正式入口是 `sem.py materials run` 或 `sem.py materials wordstat`，不调用实验脚本。API 使用现有 Yandex Cloud Search API 凭据，查询与 AI 整理解耦。

## 模块与依赖

| 模块 | 职责 |
|---|---|
| `integrations/yandex/wordstat/client.py` | 鉴权、HTTP、429/暂时故障处理、持久化配额和操作系统文件锁 |
| `materials/keywords/wordstat_flow.py` | 项目参数、完整查询、任务指纹、AI 批次、公平筛选、来源与排除记录 |
| `materials/keywords/tables.py` | 种子表、统一最终词表读取、旧版兼容、初稿转表、最终审核版本检查 |
| `materials/keywords/table_workbook.mjs` | Excel 表格、筛选、冻结表头与列宽 |
| `prompts/materials/wordstat_enrich.md` | 相关性评分、中文分类和翻译规则 |
| `materials/pipeline.py` / `cli` | 新旧模式选择、人工断点、进度及错误展示 |

模块路径相对于 `sem_automation/`，提示词路径相对于项目根目录。物料不依赖报告业务；Wordstat 客户端不依赖物料。

## 命令

先在 PowerShell 执行 `Set-Location -LiteralPath 'D:\sem自动化'`。

```powershell
# 默认：自动 Wordstat；未配置地区时全部地区
& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' materials run --project '通亚'
# 独立从标准初稿表格生成审核表；已有表默认保留
& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' materials wordstat prepare --project '通亚'
# 只查询，可中断后运行同一命令续跑
& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' materials wordstat query --project '通亚'
# 只用已有完整查询结果调用 AI 并导出
& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' materials wordstat organize --project '通亚'
# 俄罗斯示例；必须在 query 和 organize 使用同一地区，建议写入项目配置
& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' materials wordstat query --project '通亚' --wordstat-region 225
# 旧人工查询流程，仅显式选择时使用
& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' materials run --project '通亚' --wordstat-mode manual
```

`run` 可加 `--review-file` 和 `--keywords-file` 明确选择人工文件；`query/organize` 可加 `--review-file`。路径相对于终端当前目录，推荐使用完整路径。多个候选文件同时存在时停止并要求明确选择。

`query --refresh` 新建一批查询并请求最新数据；使用它会再次调用 API。相同任务的普通续跑复用本批结果，不自动将多日前的数据视为新采集。`prepare/organize --overwrite` 允许重新生成机器表格，使用前先另存人工修改。它们不会覆盖带 `reviewed` 或 `v2` 名称的人工文件。

## 输入、配置与输出

所有人工词表位于 `outputs/materials/<项目>/`。

- 初稿：`keyword_v1.md` 最末包含严格的 `keywords | keywords_CN` 表格，程序生成 `keywords_v1.xlsx` 和 UTF-8 BOM CSV。旧叙述型初稿不会被正则猜测解析；可补标准表格或直接制作审核版。
- 种子审核：`keywords_v1_reviewed.xlsx` 或 `.csv`，第一行为 `keywords, keywords_CN`；一行一个词，只查询第一列。中文不能混入关键词列，英文品牌/型号保留。去重后必须1–600词，重复词中文说明冲突时提示处理。
- Wordstat 输出：`wordstat_results.xlsx` 和 `.csv`，字段固定为 `campaign, adgroup, keywords, volume, keywords_CN`。Excel 方便审核，CSV 方便导入。
- 最终审核：另存 `keywords_v2.xlsx` 或 `.csv`；兼容旧 `keyword_v2` 文件名、`Campaign/AdGroup/Keyword` 表头及旧分块 Excel。新流程最终系列、组和关键词均不能为空。多个格式并存时显式指定。

地区配置放在 `uploads/materials/<项目>/wordstat.json`：

```json
{"regions": []}
```

空列表表示全部；俄罗斯为 `["225"]`，其他地区使用平台地区 ID。最多100个地区。`--wordstat-region` 可重复传入，覆盖项目配置；`--wordstat-region all` 显式覆盖为全部。全部设备固定为 `DEVICE_ALL`。

凭据只从根目录 `.env` 或环境变量读取：`YANDEX_CLOUD_AI_STUDIO_API_KEY`、`YANDEX_CLOUD_FOLDER_ID`。日志不输出密钥。Excel 使用现有 Node / artifact-tool 运行环境。

## 查询、数据口径与续跑

每个种子发一个 `topRequests` 请求，`numPhrases=30`，同时接收热门词及关联词，不递归扩展。无论候选累计多少，都查询完全部种子后才整理。

种子 `volume` 使用自身响应的 `totalCount`；扩展词用返回的 `count`。不是精确匹配人数，各行不能相加。相同词优先采用自身种子查询值；否则取本批最新有效返回，不累加。缺失搜索量保持空白，明确的0保持0。

默认每滚动3600秒最多100次尝试，最短间隔1秒，失败尝试也计入本地配额。状态放在根目录 `cache/wordstat/`，按云文件夹隔离；同一项目根目录下所有项目共用。操作系统锁在进程退出时释放，遗留锁文件本身不代表仍被占用。其他工具在同一云账号上的请求无法由本地记录控制，因此仍处理服务器429和 Retry-After。

网络错误和5xx最多尝试3次；429等待后继续；权限、认证、参数错误停止。等待每段最多60秒，可 Ctrl+C。重复启动同一项目任务会被锁阻止。

内部记录在 `_internal/wordstat/`：

- `current.json` 指向当前参数对应的任务及查询批次。
- 每个批次的 `responses/` 逐词保存原始结果；`status.json` 记录总数、完成数及失败；`collected.json` 仅完整查询后生成。
- 关键词与地区等参数决定查询指纹，中文说明修改不触发重新请求；修改中文仍会使 AI 整理版本变化。
- AI 缓存版本包含项目分析、提示词、模型配置、审核词与原始数据。分组目录先统一生成，再按稳定顺序每20个候选整理。成功批次立即保存，失败批次重试，不重复请求 Wordstat。
- `delivery.json` 记录交付版本、范围、未知搜索量数量及审计位置。`final_review.json` 记录最终审核文件版本；结果更新后必须重新审核保存最终表。

## 筛选算法与 AI 校验

所有种子保留。扩展词先全量去重并保留全部来源，AI 给高/中/低相关性、0–100评分及中文理由，低相关排除。每个种子的热门词与关联词合计最多保留30个扩展候选，不含种子自身。

最终先保留种子，剩余额度最多补到600：先高相关，再中相关；同等级按稳定排序后的种子轮询，每轮每种子最多贡献一个未入选词。每个种子内部按评分、搜索量、关键词稳定排序。候选不足时跳过，不凑数。查询顺序、输入顺序和响应返回顺序不会决定谁先占满额度。

AI 每批返回必须与输入 ID 一一对应，禁止漏词、重复、未知 ID、额外字段或搜索量。分组必须来自同一中文目录。原始俄语文本和搜索量由程序合并，AI 无权改写；人工已有种子中文说明保留。

`audit.json` 保留候选、搜索量来源、AI 理由、每种子候选列表和最终选择。未入选区分低相关、每种子上限、全局上限。

## 测试与限制

```powershell
& '.\.venv\Scripts\python.exe' -X utf8 -m unittest discover -s tests -v
```

`tests/test_wordstat.py` 覆盖完整查询、公平筛选、顺序不变性、限流模拟时间、失败续跑、AI 缓存、搜索量口径和表格读取；物料流程测试覆盖人工断点、旧模式及最终审核衔接。模拟数据测试不会使用真实 API 配额。

真实返回的相关性仍需人工审核。现有实验缓存仅保留追溯，不自动混入正式批次；Direct 自动上传尚未实现。

接口依据：[官方 REST 说明](https://aistudio.yandex.ru/en/docs/search-api/api-ref/Wordstat/getTop)、[配额说明](https://aistudio.yandex.ru/ru/docs/search-api/concepts/limits)。
