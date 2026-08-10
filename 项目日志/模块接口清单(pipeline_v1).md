# SEM自动化工作流——模块接口清单（Pipeline v1）

> 更新日期：2026-08-08  
> 用途：记录投放前工作流、Pipeline v1 的调度规则、模块职责、文件接口和人工节点。

---

## 一、当前阶段

SEM 投放前的资料分析、关键词处理和广告物料模块已经分别跑通，并已接入可选择、可跳过、可恢复的 Pipeline v1。

当前四个业务阶段：

1. **投放前**：资料读取、项目分析、关键词、否词、广告语、网页读取、Sitelink、Callout——主体功能已完成；
2. **投放中**：上传广告物料——尚未集成；
3. **投放后**：数据分析、搜索词优化、周报月报、询盘登记——尚未开发；
4. **投放结束**：结案报告——尚未开发。

---

## 二、架构分层

```text
用户 / pipeline.py
│
├─ 工作流调度层
│  └─ modules/pipeline_runner.py
│
├─ 资料采集层
│  ├─ main.py
│  ├─ file_reader.py + doc/excel/pdf/image_reader.py
│  ├─ website_url_extractor.py
│  └─ web_reader.py
│
├─ AI业务层
│  ├─ ai_analyzer.py
│  ├─ keyword_analyzer.py
│  ├─ negative_keyword_analyzer.py
│  ├─ ad_copy_generator.py
│  └─ sitelink_callout_generator.py
│
├─ 数据整理与人工衔接层
│  ├─ wordstat_query_exporter.py
│  └─ keyword_v2_builder.py
│
├─ AI核心层
│  ├─ prompt_loader.py
│  ├─ ai_task_runner.py
│  └─ llm_client.py
│
└─ 文件数据层
   ├─ uploads/{project_name}/
   ├─ outputs/{project_name}/
   ├─ prompts/
   └─ .env
```

---

## 三、核心设计约定

1. **模块通过固定文件交接，不依赖跨模块内存状态。** Pipeline 负责按依赖顺序调用模块，业务模块仍可单独运行。
2. **项目数据按项目名隔离。** 原始资料位于 `uploads/{project_name}/`，派生文件统一位于 `outputs/{project_name}/`。
3. **确定性任务不调用 AI。** 文件读取、客户官网提取、字符数校验、URL映射、Wordstat格式清洗均由 Python 完成。
4. **AI不得编造确定性数据。** Sitelink URL 只能从 `website_pages.json` 中映射；客户官网只从资料中的明确官网字段提取。
5. **Prompt 使用 `{{key}}` 占位符。** 通用 AI 任务优先通过 `ai_task_runner.py`；需要解析、校验和多格式输出的模块可直接调用 `call_llm()`。
6. **模型配置集中在 `.env`。** 业务模块不硬编码 API Key、Base URL 和默认模型。
7. **人工步骤继续使用文件作为状态标记。** Wordstat查询、关键词审阅和 Campaign/AdGroup 分组暂不自动化。
8. **阶段性输出优先保留。** 广告语按广告组逐步写入文件，避免长任务中断后完全丢失。
9. **无网站项目不得阻塞主流程。** 无官网时跳过网页读取和 Sitelink，但仍可生成 Callout。
10. **长文本目前采用按任务截断。** 分块、检索和跨文档去重仍是技术债。

---

## 四、当前完整业务流程

```text
uploads/{project}/PDF、DOCX、XLSX
        │
        ▼
main.py
        ├─ raw_text.txt
        ├─ file_report.csv
        └─ website_urls.txt（仅资料明确提供客户官网时生成）
        │
        ├──────────────────────────────┐
        ▼                              ▼
ai_analyzer.py                    web_reader.py（条件分支）
        │                              │
        ▼                              ├─ website_pages.json
project_brief.md                       ├─ website_content.md
        │                              └─ web_report.csv
        ▼
keyword_analyzer.py
        │
        ▼
keyword_v1.md
        │
        ▼
人工审阅 → keyword_v1_reviewed.md
        │
        ▼
wordstat_query_exporter.py
        │
        ▼
wordstat_query_list.txt
        │
        ▼
人工查询 Wordstat → wordstat_results_manual.txt
        │
        ▼
keyword_v2_builder.py
        │
        ▼
wordstat_results_cleaned.tsv
        │
        ▼
人工筛选、分 Campaign/AdGroup → keyword_v2.xlsx
        │
        ├──────────────────────────┐
        ▼                          ▼
negative_keyword_analyzer.py   ad_copy_generator.py
        │                          │
        ▼                          ├─ ad_copy_results.tsv
negative_keywords.md              ├─ ad_copy_results.xlsx
                                   └─ ad_copy_raw.md

project_brief.md + 网站条件分支
        │
        ▼
sitelink_callout_generator.py
        ├─ 有网站：8条 Sitelink + 10条 Callout
        └─ 无网站：Sitelink跳过，仅生成10条 Callout
        │
        ├─ sitelink_callouts.json
        ├─ sitelink_callouts.xlsx
        └─ sitelink_callouts_raw.md
```

说明：`ad_copy_generator.py` 依赖 `negative_keywords.md` 和人工分组后的 `keyword_v2.xlsx`，因此应在否词与人工分组完成后运行。

---

## 五、模块接口清单

| 模块 | 主要入口 | 输入 | 输出 | 当前状态 |
|---|---|---|---|---|
| `pipeline.py` | CLI入口；`--project`、`--dry-run` | 项目名及现有项目文件 | 调度结果；非dry-run时维护 `pipeline_status.json` | ✅ v1已完成 |
| `pipeline_runner.py` | `run_pipeline(project_name, ...)` / `PipelineRunner` | 模块文件契约、人工文件、用户选择 | 步骤状态、断点续跑和汇总结果 | ✅ v1已完成 |
| `main.py` | `collect_project_data(project_name)`；保留交互式入口 | `uploads/{project}/` 下的 PDF、DOCX、XLSX | `raw_text.txt`、`file_report.csv`，有官网时生成 `website_urls.txt` | ✅ 已跑通 |
| `file_reader.py` | `read_file(file_path)` | 单个本地文件 | `(content, status, note)` | ✅ 已跑通 |
| `website_url_extractor.py` | `extract_client_website_urls(documents)` | 已成功读取的源文件名与文本 | 客户官网记录列表 | ✅ 已跑通 |
| `website_url_extractor.py` | `update_website_urls_file(output_dir, records)` | 官网记录 | 自动生成或清理 `website_urls.txt` | ✅ 已跑通 |
| `ai_analyzer.py` | `analyze_project_brief(project_name, ...)` | `raw_text.txt` | `project_brief.md` | ✅ 已跑通 |
| `keyword_analyzer.py` | `generate_keyword_v1(project_name, ...)` | `raw_text.txt`、`project_brief.md` | `keyword_v1.md` | ✅ 已跑通 |
| 人工审阅 | 人工处理 | `keyword_v1.md` | `keyword_v1_reviewed.md` | 🟨 人工节点 |
| `wordstat_query_exporter.py` | `export(input_path, output_path)` | `keyword_v1_reviewed.md` | `wordstat_query_list.txt` | ✅ 已跑通 |
| Wordstat查询 | 人工查询 | `wordstat_query_list.txt` | `wordstat_results_manual.txt` | 🟨 人工节点 |
| `keyword_v2_builder.py` | `clean_wordstat_results(...)` | `wordstat_results_manual.txt` | `wordstat_results_cleaned.tsv` | ✅ 已跑通 |
| 关键词分组 | 人工筛选与分组 | 清洗后的Wordstat结果 | `keyword_v2.xlsx` / `keywords_v2.xlsx` | 🟨 人工节点 |
| `negative_keyword_analyzer.py` | `generate_negative_keywords(...)` | `raw_text.txt`、`project_brief.md`、优先 `keyword_v2.xlsx`，否则回退关键词MD | `negative_keywords.md` | ✅ 已跑通 |
| `ad_copy_generator.py` | `generate_ad_copy(...)` | `project_brief.md`、`negative_keywords.md`、`keyword_v2.xlsx` | 广告语TSV、XLSX、原始MD | ✅ 已跑通 |
| `web_reader.py` | `read_website(project_name, ...)` | 优先 `outputs/{project}/website_urls.txt`，兼容 `uploads/{project}/website_urls.txt` | 网页JSON、网页正文MD、读取报告CSV | ✅ 已跑通 |
| `sitelink_callout_generator.py` | `generate_sitelink_callouts(...)` | `project_brief.md`；有网站时另需 `website_pages.json` | Sitelink/Callout JSON、XLSX、原始MD | ✅ 已跑通 |
| `prompt_loader.py` | `load_prompt(prompt_name)` | `prompts/{name}.md/.txt` | Prompt字符串 | ✅ 已跑通 |
| `ai_task_runner.py` | `run_ai_task(...)` | Prompt名、替换变量、模型参数 | 指定项目输出文件 | ✅ 已跑通 |
| `llm_client.py` | `call_llm(...)` | Prompt、provider/model等参数 | 标准结果字典 | ✅ 已跑通 |

---

## 六、关键文件契约与条件分支

### 6.1 客户官网提取

- `main.py` 从已成功读取的客户资料中识别“推广网站域名、客户官网、官方网站、网站地址、Website”等明确字段。
- “官网/website”等弱标签只在疑似信息采集表前部启用；“竞争对手、竞品、论坛/网站、历史广告、参考网站”等上下文明确排除。
- 支持完整URL、`www.example.com/path` 和裸域名；裸域名补为 `https://`。
- 有官网时生成 `outputs/{project}/website_urls.txt`，文件含自动生成标记、来源注释和逐行URL。
- 无官网时不创建该文件；只自动删除带自动生成标记的旧文件，人工文件保留并提示复核。

### 6.2 网页读取

- URL文件优先级：`outputs/{project}/website_urls.txt` > `uploads/{project}/website_urls.txt`。
- 两处均无有效URL时返回 `status = skipped_no_website`，不报错、不创建空网页结果。
- 当前仅抓取静态HTML；同域名、限定深度和页面数；不执行JavaScript。
- `website_pages.json` 是后续 Sitelink URL 的唯一可信来源，AI只选择 `page_id`，Python负责映射真实URL。

### 6.3 Sitelink与Callout

- 有有效 `website_urls.txt` 但缺少 `website_pages.json`：生成器在调用API前报错，提示先运行 `web_reader.py`。
- 有网站：生成正好8条Sitelink和10条Callout。
- 无网站：使用 `callout_only.md`，输出 `sitelinks = []`、`sitelinks_status = skipped_no_website`，并继续生成10条Callout。
- 字符限制由Python二次校验：Sitelink标题≤30、描述≤60、Callout单条≤25、桌面前8条合计≤132、移动前4条合计≤66。
- 中文翻译仅供人工审核，不参与俄语字符限制。

### 6.4 关键词与广告语

- `keyword_v1.md` 是AI初稿；正式下游优先使用人工确认并分组的 `keyword_v2.xlsx`。
- `negative_keyword_analyzer.py` 默认 `auto`：优先读取 `keyword_v2.xlsx` / `keywords_v2.xlsx`，缺失时回退到 `keyword_v1.md`。
- `ad_copy_generator.py` 必须读取分组Excel，按 Campaign + AdGroup 逐组生成7条标题和3条正文及中文翻译。

---

## 七、AI核心接口

```python
# llm_client.py
call_llm(
    prompt,
    provider=None,
    model=None,
    system_prompt=None,
    temperature=None,
    max_tokens=None,
    use_premium=None,
)
# 返回：platform、provider、requested_model、actual_model、content、usage、finish_reason、raw

# prompt_loader.py
load_prompt(prompt_name)
# 按 .md > .txt 的优先级读取 prompts/{prompt_name}

# ai_task_runner.py
run_ai_task(
    project_name,
    prompt_name,
    output_filename,
    replacements,
    provider=None,
    model=None,
    temperature=None,
    max_tokens=None,
    use_premium=None,
)
# 替换 {{key}} → 调用LLM → 写入 outputs/{project}/{output_filename}
```

使用 `ai_task_runner.py` 的模块：项目简报、关键词v1、否词。  
直接调用 `call_llm()` 并自行解析/校验的模块：广告语、Sitelink/Callout。

---

## 八、Pipeline v1 调度接口

### 8.1 启动方式

```powershell
# 交互输入项目名
& ".\.venv\Scripts\python.exe" pipeline.py

# 指定项目
& ".\.venv\Scripts\python.exe" pipeline.py --project 通亚

# 只预览，不调用API、不请求网页、不写文件
& ".\.venv\Scripts\python.exe" pipeline.py --project 通亚 --dry-run
```

### 8.2 调度规则

1. 自动步骤已有全部有效输出时，询问“保留、重跑或停止”；文件存在且非空是v1有效性标准。
2. `keyword_v1_reviewed.md`、`wordstat_results_manual.txt`、`keyword_v2.xlsx / keywords_v2.xlsx` 是三个人工断点。
3. 缺少人工文件时先显示处理说明，再由用户选择继续网站独立分支或停止。
4. Pipeline中的否词固定等待最终关键词Excel；模块单独运行时仍保留V1回退能力。
5. 无官网时 `web_reader` 记录为 `skipped`，Sitelink/Callout进入Callout-only模式。
6. 有官网但网页读取失败时记录为 `failed`，Sitelink/Callout不运行。
7. 单步异常不会删除已生成文件；依赖该步骤的下游不运行，仍可选择处理独立分支。
8. `outputs/{project}/pipeline_status.json` 在每次状态变化后立即更新；真实文件仍是主要状态依据。

### 8.3 状态值

`pending / running / completed / skipped / failed / waiting_for_human`

状态文件记录项目名、更新时间以及各步骤的状态、说明和更新时间。Pipeline v1不使用数据库、不并发运行，也不提供批量项目功能。

---

## 九、已知技术债与暂不处理项

- 图片OCR尚未启用；
- 长文档仍是简单截断，尚未分块与检索；
- 网页读取不支持JavaScript动态渲染、验证码和复杂反爬；
- 网页正文仍可能包含重复导航、页脚和大量链接；
- 竞品自动搜索、竞品网站分析Prompt尚未完成；
- Wordstat查询、关键词筛选和Campaign/AdGroup分组仍需人工操作；
- 尚未接入Yandex Direct上传、预算预测和投放后数据；
- 尚未实现网站诊断、Metrika检测、周月报和结案报告。

---

## 十、新会话或后续Pipeline开发时的最小上下文

后续继续开发时，优先提供：

1. 本文件；
2. 计划修改的业务模块；
3. 对应Prompt；
4. 一个不含敏感信息的项目输出目录结构示例；
5. 希望新增的调度能力，例如强制单步重跑、批量项目或非交互模式。

本文件描述的是当前实际接口；后续若修改文件名、输入优先级或条件分支，应同步更新本清单。
