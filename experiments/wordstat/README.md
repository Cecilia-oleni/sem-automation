# Wordstat 独立实验（历史）

正式工作流已接入，请使用根目录 `sem.py materials wordstat`；操作与技术说明见 [Wordstat 技术说明](../../docs/Wordstat技术说明.md)。以下为原实验行为和记录，固定14次上限不适用于正式客户端。

人工查看与筛选：`keywords.txt` 保存已查询的 14 个词、搜索量、返回状态、采用与人工备注列；`expanded_keywords.txt` 保存全部热门词与关联词、搜索量及来源。制表符分列，可直接复制到表格。采用列可填写“是/否”，当前不自动影响报告，便于人工挑选后粘贴。脚本只读取 keywords.txt 第一列，跳过 # 开头的说明行。

JSON 是原始数据凭据，报告从中读取。`export_review.py` 只做首次本地导出，已有人工清单时拒绝覆盖，避免丢失筛选备注。重新生成报告不会覆盖人工清单。

仅使用 Python 标准库；无依赖安装，不修改原业务代码或原虚拟环境。此目录位于统一项目的 experiments/wordstat 内，是文件与代码层面的隔离，不是容器或独立云账单；使用现有服务账号计费。

只读 `../../.env` 的 `YANDEX_CLOUD_AI_STUDIO_API_KEY` 与 `YANDEX_CLOUD_FOLDER_ID`。不读取旧 OAuth token，不复制 key。不要提交 .env 或 results。

从唯一项目根目录 `D:\sem自动化` 执行：

```powershell
.\.venv\Scripts\python.exe .\experiments\wordstat\wordstat.py --phrase 'трансплантация костного мозга'
```

默认仅预览。加 `--execute` 才发请求；`--regions-tree` 为地区列表。固定批次脚本已归档到 `experiments/archive/wordstat_batches`，不作为可复用入口。

成功结果按请求参数缓存；相同查询不会重复收费。失败无自动重试。results/attempts.jsonl 在发送前记录尝试；整个实验累计最多允许 14 次付费请求尝试（当前已用完），防止后续误调用。该限制仅覆盖本脚本，不能限制同一云账号的其他使用。公开价可能变化，未来扩展前需重新核价。

results 中保留请求、时间、原始响应与调用记录。空对象响应不强行转换成确定的零搜索量。报告生成器只读取本地结果：

```powershell
.\.venv\Scripts\python.exe .\experiments\wordstat\make_report.py
```

历史结果见 REPORT.md。正式物料工作流使用独立客户端；此实验目录保留历史，不作为正式入口。
