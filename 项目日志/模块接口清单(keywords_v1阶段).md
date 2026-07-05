# SEM自动化工作流 —— 模块接口清单

> 用途：本文档用于记录项目当前进度、架构约定和模块接口。当需要在新的AI对话（或换用其他AI工具）中继续开发时，把本文档 + 相关代码文件贴给AI，即可快速同步上下文，无需重新解释整个项目。

---

## 一、项目目标

为投流（SEM广告投放）工作搭建自动化工作流，整体分四个阶段：

1. **投放前**：市场调研、广告物料制作 ← **当前开发阶段**
2. **投放中**：上传广告物料
3. **投放后**：数据分析、广告优化、否词排查/拓词、周报月报、询盘登记
4. **投放完成**：结案报告PPT

---

## 二、架构分层

```
用户
│
main.py / cli.py
│
Workflow（流程层）：读取资料 → AI分析 → 关键词生成 → 广告文案生成 → 报告生成
│
Service（业务层）：ai_analyzer / keyword_analyzer / (待建：copy_analyzer / negative_keyword_analyzer / report_service)
│
AI Core（AI核心）：prompt_loader / llm_client / ai_task_runner
│
Infrastructure（基础层）：config / text_utils / .env
│
Data（数据）：prompts/ outputs/ uploads/
```

---

## 三、核心设计约定（重要，新模块必须遵守）

1. **模块间通过"文件"交接，不直接传递内存数据**。任何新功能（网页读取、竞品搜索、Wordstat接入等）应新建模块，读写固定命名的文件，**不修改已跑通的旧模块内部逻辑**。
2. **人工介入环节用文件名/版本号标记状态**，不额外开发状态跟踪系统。例如：
   - AI生成 `keyword_v1.md`
   - 人工审核删减后另存为 `keyword_v1_reviewed.md`
   - 下一步模块读取 `keyword_v1_reviewed.md`；若文件不存在，代码应报错提示"请先完成人工审核"
3. **Prompt变量替换使用 `{{key}}` 占位符**（`ai_task_runner.py`里实现），避免和Python字符串格式化语法冲突。
4. **模型选择通过 `.env` 控制**，业务代码通过 `use_premium=True/False` 切换，不硬编码模型名：
   - `OPENROUTER_CHEAP_MODEL`（如 deepseek-v4-pro）
   - `OPENROUTER_PREMIUM_MODEL`（如 gpt-5.5）
5. **`call_llm` 返回字典**（非纯字符串），包含 `content`、`actual_model`、`usage`、`cost`、`raw` 等字段，便于以后做成本统计/模型效果对比。
6. **长文本截断**：各任务用独立的 `.env` 变量控制截断长度（如 `PROJECT_BRIEF_MAX_CHARS`、`KEYWORD_RAW_TEXT_MAX_CHARS`），目前是简单截断前N字符+提示语，**分块处理长文档是已知技术债，尚未实现**。

---

## 四、目录结构（现状）

```
SEM自动化/
├── 开发日志.md
├── modules/
│   ├── ai_analyzer.py        # 业务层：project_brief分析
│   ├── ai_task_runner.py     # 通用AI任务编排器
│   ├── keyword_analyzer.py   # 业务层：关键词v1生成
│   ├── llm_client.py         # 只负责调用AI API（当前仅OpenRouter）
│   ├── prompt_loader.py      # 只负责读取prompts目录下的文件
│   ├── text_utils.py         # 文本截断、.env读取等工具函数
│   ├── doc_reader.py / excel_reader.py / pdf_reader.py / image_reader.py
│   ├── file_reader.py        # 统一入口，分发给上面几个reader
│   └── web_reader.py         # 已建文件，网页读取功能待开发
│   └── negative_keyword_analyzer.py  # 业务层：否词生成
├── prompts/
│   ├── project_brief.md
│   ├── keyword_extract.md
│   ├── negative_keyword.md
│   └── ad_copy.md            # 已建文件，内容/调用待开发
├── outputs/{project_name}/   # 每个项目独立输出目录
├── uploads/
└── main.py
```

---

## 五、模块接口清单（输入 → 输出）

| 模块 | 函数 | 输入 | 输出 | 状态 |
|---|---|---|---|---|
| file_reader | `read_file()` | `uploads/*.pdf/docx/xlsx` | `outputs/{project}/raw_text.txt` | ✅ 已跑通 |
| ai_analyzer | `analyze_project_brief()` | `raw_text.txt` | `outputs/{project}/project_brief.md` | ✅ 已跑通 |
| keyword_analyzer | `generate_keyword_v1()` | `raw_text.txt` + `project_brief.md` | `outputs/{project}/keyword_v1.md` | ✅ 已跑通 |
| （人工审核） | 人工打开 `keyword_v1.md` 删减确认 | `keyword_v1.md` | `keyword_v1_reviewed.md`（或`wordstat_query_list`人工另存） | 🔲 流程约定，无需代码 |
| negative_keyword_analyzer | ✅ 已跑通 | `raw_text.txt` + `project_brief.md` + `keyword_v1.md`  | `negative_keywords.md` | 🔲 下一步要做 |
| ad_copy_analyzer | 待建 | `raw_text.txt` + `project_brief.md` | `ad_copy.md` | 🔲 下一步要做 |
| wordstat数据合并 | 待建 | `wordstat_query_list` + 人工整理的Wordstat搜索量（Excel/表格） | 最终关键词Excel表（含否词sheet） | 🔲 先做半人工版本 |

---

## 六、AI核心组件接口

```python
# llm_client.py
call_llm(prompt, provider=None, model=None, system_prompt=None,
         temperature=None, max_tokens=None, use_premium=None)
→ 返回 dict: {platform, provider, requested_model, actual_model,
              content, usage, finish_reason, raw}

# prompt_loader.py
load_prompt(prompt_name)  # 自动找 prompts/{prompt_name}.md 或 .txt
→ 返回 str（prompt模板原文）

# ai_task_runner.py
run_ai_task(project_name, prompt_name, output_filename, replacements,
            provider=None, model=None, temperature=None,
            max_tokens=None, use_premium=None)
→ 读取prompt模板 → 用{{key}}替换replacements里的变量 → 调call_llm
→ 结果写入 outputs/{project_name}/{output_filename}
→ 返回 str（AI生成正文）
```

新业务模块（如`ad_copy_analyzer.py`）只需模仿`keyword_analyzer.py`的写法：读输入文件 → 校验非空 → 截断 → 调`run_ai_task`即可，无需关心底层AI调用细节。

---

## 七、当前进度总结（截至2026.7.4）

**已完成并跑通：**
- 本地文件读取（pdf/docx/excel）→ raw_text.txt
- AI项目简报分析 → project_brief.md
- 关键词v1生成 → keyword_v1.md
- 否词清单模块（`negative_keyword_analyzer.py`）

**下一步计划（按优先级）：**
1. 广告文案模块（`ad_copy_analyzer.py`）
2. Wordstat数据"半人工"合并脚本（人工查数据，脚本合并成Excel）

**暂不做（留待后期迭代）：**
- 网页读取（客户网站/竞品网站自动抓取）
- 竞品网站自动查找
- Wordstat API自动化查询
- 长文档分块处理（替代当前的简单截断）

---

## 八、如何在新对话中使用本文档

把本文档，连同以下文件一起提供给新的AI会话，即可快速同步：
- 本文档（模块接口清单.md）
- 想要修改/参考的具体代码文件（如要新建否词模块，可参考`keyword_analyzer.py`）
- 如涉及新prompt，可附上现有的prompt文件作为格式参考（如`project_brief.md`、`keyword_extract.md`）
