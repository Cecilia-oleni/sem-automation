# SEM 自动化工作流：开源项目参考清单

> 文件用途：记录可供本项目借鉴的开源仓库、适用范围、风险和接入优先级，避免重复检索和重复造轮子。
>
> 适用项目：俄语区 Yandex / VK SEM 半自动化辅助投放系统
>
> 当前版本：2026-08-05

---

## 1. 使用原则

本清单不是“推荐直接安装的依赖列表”，而是外部项目的分级参考库。

本项目继续保留以下核心设计：

1. 以 Python 为主要开发语言。
2. 模块之间优先通过固定文件交接，便于人工审核、调试和回滚。
3. 保留 Human-in-the-Loop，不允许系统未经人工确认直接定稿关键词、广告语或批量修改账户。
4. 平台 API、LLM、网页抓取和业务规则相互解耦。
5. 优先复用开源项目中的成熟接口设计、报表结构、错误处理和审计规则，不轻易整体迁移到他人的框架。
6. 任何第三方仓库在正式接入前，都必须重新核对许可证、最近维护状态、官方 API 兼容性和安全边界。

推荐的复用顺序：

```text
参考设计
→ 提取可复用的数据结构或请求模板
→ 用最小测试脚本验证官方 API
→ 封装为本项目独立模块
→ 输出文件供人工审核
→ 再考虑自动上传或批量修改
```

---

## 2. 优先级总览

| 优先级 | 项目 | 主要用途 | 建议动作 | 可直接复用程度 |
|---|---|---|---|---|
| P0 | `elsvv/yandex-direct-skill` | Yandex Direct API v5、报表、关键词、广告及账户操作 | 立即研究，提取接口与请求模板 | 中 |
| P0 | `pavelmaksimov/tapi-yandex-direct` | Python API Client、Reports 轮询、TSV 导出和重试 | 立即研究，但不直接作为长期依赖 | 中低 |
| P1 | `AgriciDaniel/claude-ads` | 投后审计、规则评分、行动建议、Agent 编排 | 在设计投后优化模块前重点研究 | 中，主要复用思想 |
| P1 | `ComposioHQ/awesome-claude-skills/competitive-ads-extractor` | 竞品广告采集与结构化分析 | 复用输出字段和分析流程 | 低，主要复用结构 |
| P2 | `iscale-llc/iscale-facebook-ad-builder` | 竞品研究、文案生成、图片生成、广告管理产品架构 | 只研究产品流程，不迁移技术栈 | 低 |
| P2 | `biplane/yandex-direct` | 较完整的 Yandex Direct API v5 服务建模 | 用于核对服务分层和数据模型 | 低，PHP 技术栈 |
| P3 | `gty77663/YandexWordstatAPI` | 旧版 Wordstat 自动化流程 | 只参考业务步骤，不复用代码 | 极低 |
| P3 | `negezor/vk-io` | VK 通用 API 与旧广告接口类型定义 | 仅用于能力摸底，不作为新版 VK Ads 依据 | 极低 |

---

# 3. P0：立即研究

## 3.1 `elsvv/yandex-direct-skill`

- 仓库：https://github.com/elsvv/yandex-direct-skill
- 类型：面向 Claude Code / Agent 的 Yandex Direct Skill
- 平台：Yandex Direct API v5
- 当前定位：本项目最接近的开源参考实现

### 已覆盖能力

仓库文档和脚本覆盖了以下 Direct API 领域：

- Campaigns
- AdGroups
- Ads
- Keywords
- KeywordBids
- BidModifiers
- Reports
- Search Query Report
- Sitelinks
- Callouts / Ad Extensions
- NegativeKeywordSharedSets
- KeywordsResearch
- Dictionaries
- Sandbox
- OAuth Token
- Agency 账户的 `Client-Login`
- API units、分页和部分错误处理

### 对本项目的直接价值

#### A. Yandex Direct API 服务映射

可以直接用它建立本项目的平台接口清单，减少逐页查阅官方文档的时间。

建议映射为：

```text
modules/providers/yandex_direct/
├── client.py
├── campaigns.py
├── adgroups.py
├── ads.py
├── keywords.py
├── bids.py
├── reports.py
├── extensions.py
├── negative_keywords.py
├── dictionaries.py
└── schemas.py
```

#### B. 投后报表模块

重点研究 Reports 和 Search Query Report 的请求参数，用于未来：

- 拉取 Campaign / Ad Group / Ad / Keyword 级数据；
- 拉取用户实际搜索词；
- 生成排否候选；
- 生成拓词候选；
- 自动整理周报、月报和优化建议。

#### C. 上传模块

重点研究以下对象的请求结构：

- 广告系列；
- 广告组；
- 关键词；
- 广告文案；
- Sitelinks；
- Callouts / Ad Extensions；
- 否词集合。

### 不建议直接照搬的部分

1. 主体脚本是 Bash，与本项目 Python 技术栈不同。
2. 它解决的是平台 API 操作，不包含本项目的客户资料分析、俄语关键词生成、人工分组、广告文案审核等业务流程。
3. Agent Skill 的说明和脚本仍需与 Yandex 官方 API 当前文档逐项核对。
4. 仓库规模较小，不应未经测试直接承担生产账户批量写入。

### 推荐使用方式

```text
阅读 SKILL.md 和 scripts/
→ 整理服务、请求头、请求体和报表字段
→ 使用 Python requests/httpx 重写最小客户端
→ 先接 Sandbox 或只读 Reports
→ 验证后再逐步开放写操作
```

### 对应本项目模块

| 本项目模块 | 可参考内容 |
|---|---|
| `yandex_direct_client.py` | OAuth、Header、Base URL、Sandbox、Client-Login |
| `yandex_report_fetcher.py` | Reports、Search Query Report、TSV 输出 |
| `keyword_uploader.py` | Keywords API 请求结构 |
| `ad_uploader.py` | Ads、Sitelinks、Callouts 请求结构 |
| `negative_keyword_uploader.py` | NegativeKeywordSharedSets |
| `campaign_manager.py` | Campaign suspend/resume/archive 等操作 |

### 结论

**优先级最高。** 立即纳入开发参考，但先做“接口知识库和请求模板来源”，不直接把 Bash 脚本嵌入当前项目。

---

## 3.2 `pavelmaksimov/tapi-yandex-direct`

- 仓库：https://github.com/pavelmaksimov/tapi-yandex-direct
- 类型：Python Yandex Direct API Client
- 许可证：MIT
- 最新公开版本：2021 年

### 已覆盖能力

仓库包含 Campaigns、Ads、Keywords、Reports、KeywordBids、Sitelinks、KeywordsResearch、NegativeKeywordSharedSets 等资源，并提供：

- 统一 client 调用；
- Sandbox；
- Agency login；
- API 限额重试；
- Reports 等待与下载；
- TSV 导出；
- 服务端错误重试。

### 对本项目的直接价值

#### A. Python Client 封装方式

适合参考如何把不同 Direct API Service 统一封装为：

```python
client.campaigns().post(data=body)
client.keywords().post(data=body)
client.reports().post(data=body)
```

本项目可以简化为：

```python
class YandexDirectClient:
    def request(self, service: str, method: str, params: dict) -> dict:
        ...
```

#### B. Reports 处理

重点参考：

- 报告尚未生成时的等待；
- 超过报告数量限制时重试；
- API units 不足时的处理；
- 服务器异常重试；
- TSV 文件输出。

#### C. 错误处理和配置参数

可以帮助本项目建立统一的：

- `timeout`
- `max_retries`
- `retry_backoff`
- `sandbox`
- `client_login`
- `language`
- `processing_mode`

### 风险

1. 最后版本较旧，不能假设与 2026 年全部 Direct API 服务兼容。
2. 如果直接安装为核心依赖，未来可能遇到字段变化、弃用接口或维护中断。
3. 项目提供的资源列表只能作为参考，最终必须以当前官方 API 文档为准。

### 推荐使用方式

- 阅读源码，学习 Client、Resource Mapping、Reports 和重试逻辑；
- 不在 V1.5 中直接依赖整个包；
- 自行实现一个较薄的 Python Client；
- 仅在快速验证阶段考虑临时安装测试。

### 结论

**P0，但定位是“Python 实现教材”，不是推荐长期依赖。**

---

# 4. P1：设计投后优化和竞品模块前重点研究

## 4.1 `AgriciDaniel/claude-ads`

- 仓库：https://github.com/AgriciDaniel/claude-ads
- 类型：广告审计与优化 Skill
- 许可证：MIT
- 当前特点：覆盖多广告平台，包含大量规则、评分、行业模板和创意生成 Agent

### 已覆盖能力

项目面向 Google、Meta、YouTube、LinkedIn、TikTok、Microsoft、Apple、Amazon 等平台，提供：

- 广告账户审计；
- 多项确定性检查；
- 加权评分；
- 风险优先级；
- 行动建议；
- 行业模板；
- 创意审计与生成；
- 多 Agent 编排；
- JSON / PDF 报告。

它目前不直接支持 Yandex 和 VK，也不会自动连接所有广告平台 API；账户分析通常基于用户提供的导出数据、截图或外部 API/MCP。

### 对本项目的直接价值

最值得借鉴的是：

```text
规则引擎负责发现问题
+ LLM 负责解释、归因和提出建议
+ 人工决定是否执行
```

而不是让 LLM 对整张报表自由判断。

### 可转化为本项目的规则示例

```python
if impressions >= 100 and clicks == 0:
    flag = "high_impression_no_click"

if clicks >= 20 and conversions == 0:
    flag = "high_click_no_conversion"

if cost >= cost_threshold and conversions == 0:
    flag = "high_cost_no_conversion"

if search_term_cost >= threshold and conversions == 0:
    flag = "negative_keyword_candidate"
```

随后再由 LLM：

- 结合俄语搜索词语义判断是否排否；
- 区分明显无关词、低意向词、竞品词和信息查询词；
- 给出停词、降价、保留观察或修改匹配方式的建议；
- 输出解释和证据。

### 推荐模块拆分

```text
modules/optimization/
├── rule_engine.py
├── search_term_analyzer.py
├── performance_analyzer.py
├── recommendation_generator.py
├── audit_scorer.py
└── optimization_reporter.py
```

### 不建议直接照搬

- 不要直接沿用 Google / Meta 的指标阈值；
- 不要直接复制其行业 benchmark；
- 不要让 Agent 自动执行账户修改；
- 不要在当前 V1.5 阶段引入大量并行 Agent。

### 结论

**投后模块的最高优先级参考项目。** 主要复用审计思想、规则组织方式、报告结构和安全边界。

---

## 4.2 `competitive-ads-extractor`

- 仓库目录：https://github.com/ComposioHQ/awesome-claude-skills/tree/master/competitive-ads-extractor
- 类型：竞品广告提取与分析 Skill
- 上级仓库：https://github.com/ComposioHQ/awesome-claude-skills

### 已覆盖能力

该 Skill 的目标包括：

- 从 Facebook、LinkedIn 等广告库提取竞品广告；
- 保存截图；
- 提取文案；
- 分析痛点、使用场景和价值主张；
- 按主题、受众或格式分类；
- 识别常见创意模式。

它不直接解决 Yandex 搜索广告和 VK Ads 的数据来源问题。

### 对本项目的直接价值

重点复用**竞品广告的数据结构和分析维度**：

```json
{
  "competitor": "Competitor A",
  "source": "yandex_search",
  "landing_page": "https://...",
  "headline": "...",
  "description": "...",
  "usp": ["..."],
  "pain_points": ["..."],
  "target_audience": ["..."],
  "cta": "...",
  "creative_type": "search_text_ad",
  "evidence": {
    "screenshot": "...",
    "captured_at": "..."
  }
}
```

### 推荐模块拆分

```text
modules/competitor/
├── competitor_site_reader.py
├── competitor_ad_collector.py
├── competitor_normalizer.py
├── competitor_analyzer.py
└── competitor_reporter.py
```

V1.5 只建议实现：

```text
人工输入竞品 URL
→ 抓取网站公开内容
→ 提取产品线、USP、市场定位和 CTA
→ 输出结构化竞品摘要
→ 人工审核
```

以下功能暂缓：

- 自动发现竞品；
- 批量搜索并截图 Yandex 广告；
- 绕过登录、验证码或平台访问限制；
- 根据无法验证的广告频率推断“表现最好”的广告。

### 结论

**竞品模块的首要结构参考。** 不直接复用抓取方式，优先复用字段设计、证据保存和报告结构。

---

# 5. P2：产品和工程架构参考

## 5.1 `iscale-llc/iscale-facebook-ad-builder`

- 仓库：https://github.com/iscale-llc/iscale-facebook-ad-builder
- 类型：AI 驱动的 Facebook 广告自动化平台
- 技术栈：FastAPI、React、LLM、图片生成

### 已知能力

GitHub 项目描述显示其包含：

- 竞品研究；
- 广告文案生成；
- 图片创建；
- Campaign 管理；
- 前后端交互。

### 对本项目的价值

主要用于观察一个完整广告辅助产品如何组织：

```text
输入企业信息
→ 竞品研究
→ 提炼广告策略
→ 生成多版本文案和图片
→ 人工选择
→ 形成 Campaign 素材
→ 平台管理
```

可重点研究：

- 前后端如何传递项目状态；
- 广告版本如何保存；
- 竞品资料如何进入生成流程；
- 生成结果如何人工选择；
- 上传前如何校验。

### 当前不建议迁移的原因

1. 平台是 Facebook，不是 Yandex / VK。
2. React + FastAPI 会显著增加前端、数据库、部署和状态管理成本。
3. 当前项目核心流程尚未完全稳定，过早做产品界面会固化尚未验证的流程。
4. 用户现在更需要可运行的内部工具，而不是完整 SaaS 产品。

### 结论

**只作为产品架构案例。** 等文件式工作流稳定且重复使用后，再考虑用 Streamlit 或 Web UI 包装。

---

## 5.2 `biplane/yandex-direct`

- 仓库：https://github.com/biplane/yandex-direct
- 类型：PHP Yandex Direct API Client
- 许可证：MIT
- 技术栈：PHP、SOAP / Reports HTTP Client

### 价值

该项目对 Yandex Direct API v5 的服务建模较完整，包括：

- Ads
- Campaigns
- AdGroups
- Keywords
- KeywordBids
- KeywordsResearch
- NegativeKeywordSharedSets
- Sitelinks
- Reports
- Leads
- Strategies
- RetargetingLists
- Dictionaries 等

适合用于核对：

- Service 与 Contract 的分层方式；
- 请求与响应对象建模；
- Reports 的独立处理；
- 日志与错误分级；
- API 服务覆盖范围。

### 局限

- PHP 技术栈与当前项目不一致；
- 使用 SOAP 的部分实现不适合直接迁移到当前 Python JSON API Client；
- 引入它不会减少当前项目的 Python 开发量。

### 结论

**作为补充参照。** 当 Python 项目或 Agent Skill 对某个 Yandex Service 描述不清时，用它核对服务建模，不作为依赖。

---

# 6. P3：只保留历史和能力参考

## 6.1 `gty77663/YandexWordstatAPI`

- 仓库：https://github.com/gty77663/YandexWordstatAPI
- 类型：Python Wordstat 报告工具
- 许可证：MIT
- 使用接口：Yandex Direct API v4

### 可参考部分

其业务流程为：

```text
提交关键词
→ 创建 Wordstat 报告
→ 轮询报告状态
→ 获取左栏和右栏关键词
→ 保存结果
→ 删除临时报表
```

### 不可直接采用的原因

- 使用 Direct API v4；
- 依赖旧的 Wordstat Report 方法；
- 不能证明这些接口在当前环境仍可用；
- 代码和文档体量小，维护状态有限。

### 对当前项目的结论

继续采用当前方案：

```text
人工查询 Wordstat
→ 导出或整理搜索量
→ Python 清洗与合并
→ 人工确认
```

只有在官方能力重新确认后，才重新评估自动化。

---

## 6.2 `negezor/vk-io`

- 仓库：https://github.com/negezor/vk-io
- 类型：Node.js / TypeScript VK API SDK

### 已知能力

其类型定义中存在 VK Ads 相关接口，例如：

- `createAds`
- `createCampaigns`
- `getAds`
- `getStatistics`
- `checkLink`
- Retargeting 等

### 风险

VK 广告生态存在历史 VK API、myTarget 和新版 VK Ads 等不同产品与接口阶段。仓库中出现广告方法，并不能证明它完全对应当前实际使用的新版 VK Ads 后台。

同时：

- 技术栈为 TypeScript；
- 它是通用 VK API SDK，不是完整投放工作流；
- 当前未找到足够成熟、专门面向新版 VK Ads 的 Python 开源自动化项目。

### 推荐处理

在真正开发 VK 模块之前先完成：

1. 明确公司账户当前使用的具体 VK 广告平台；
2. 找到对应的当前官方 API 文档；
3. 确认申请权限、Token、账户 ID 和测试环境；
4. 编写只读连接测试；
5. 再决定自己封装还是使用第三方 SDK。

### 结论

**暂不接入，只保留能力线索。**

---

# 7. 与现有工作流的对应关系

## 7.1 投放前

| 现有或规划模块 | 优先参考项目 | 可借鉴内容 |
|---|---|---|
| `web_reader.py` | `competitive-ads-extractor` | 证据保存、字段结构、分析流程 |
| `competitor_analyzer.py` | `competitive-ads-extractor` | USP、痛点、受众、CTA、主题分类 |
| `keyword_analyzer.py` | `yandex-direct-skill` | KeywordsResearch 能力边界 |
| `keyword_formatter.py` | `yandex-direct-skill`、`tapi-yandex-direct` | 上传字段和 TSV / JSON 结构 |
| `ad_copy_analyzer.py` | `claude-ads`、`iscale-facebook-ad-builder` | 多版本生成、规则校验、人工选择 |
| `negative_keyword_analyzer.py` | `claude-ads` | 排否候选规则、风险解释 |

## 7.2 投放中

| 规划模块 | 优先参考项目 | 可借鉴内容 |
|---|---|---|
| `yandex_direct_client.py` | `yandex-direct-skill`、`tapi-yandex-direct` | 认证、请求、Sandbox、重试 |
| `campaign_uploader.py` | `yandex-direct-skill` | Campaign / AdGroup 创建流程 |
| `keyword_uploader.py` | `yandex-direct-skill` | Keywords API |
| `ad_uploader.py` | `yandex-direct-skill` | Ads、Sitelinks、Extensions |
| `upload_validator.py` | `claude-ads` | 写入前检查和风险门禁 |
| `vk_ads_provider.py` | 暂无可靠开源主参考 | 以后以官方 API 为准 |

## 7.3 投放后

| 规划模块 | 优先参考项目 | 可借鉴内容 |
|---|---|---|
| `yandex_report_fetcher.py` | `yandex-direct-skill`、`tapi-yandex-direct` | Reports、Search Query、TSV |
| `optimization_rule_engine.py` | `claude-ads` | 确定性审计规则 |
| `search_term_analyzer.py` | `claude-ads` | 搜索词排否、拓词候选逻辑 |
| `optimization_reporter.py` | `claude-ads` | 评分、优先级、行动建议 |
| `weekly_report.py` | `claude-ads`、Yandex Reports | 结构化报告和证据字段 |

---

# 8. 推荐落地顺序

## 阶段 A：当前可立即执行

1. 阅读并拆解 `yandex-direct-skill`：
   - 认证；
   - Reports；
   - Search Query；
   - Keywords；
   - Ads；
   - Sitelinks；
   - NegativeKeywordSharedSets。
2. 阅读 `tapi-yandex-direct`：
   - client 封装；
   - Reports 等待；
   - TSV 导出；
   - 重试。
3. 在项目中新增本文件，不修改现有业务模块。
4. 建立 `modules/providers/yandex_direct/` 空目录或设计草稿，但暂不一次性开发全部 API。

## 阶段 B：投放前 V1.5

1. 完成指定 URL 的客户网站与竞品网站抓取；
2. 使用结构化 JSON / Markdown 保存竞品信息；
3. 将竞品 USP 和广告信息接入广告文案生成；
4. 不做自动发现竞品，不做高风险广告抓取。

## 阶段 C：Yandex API 最小闭环

建议先只做只读功能：

```text
OAuth 连接测试
→ 拉取 Campaign 列表
→ 拉取最近 7 天 Campaign 报表
→ 拉取 Search Query Report
→ 保存 TSV
```

只读功能稳定后，再做低风险写入：

```text
上传少量测试关键词
→ 上传测试广告
→ 获取上传结果
→ 人工核对
```

最后再考虑：

- 批量上传；
- 修改出价；
- 暂停或恢复对象；
- 自动排否；
- 自动优化。

## 阶段 D：投后审计

1. 先建立规则引擎；
2. 再接 LLM 做语义分析和解释；
3. 输出建议文件；
4. 人工确认；
5. 不直接自动修改账户。

## 阶段 E：VK

Yandex API 跑通后，再单独确认 VK 当前平台和 API，不与 Yandex 模块同时开发。

---

# 9. 建议的统一 Provider 接口

为未来迁移到 VK、Google Ads 或其他平台，可预留统一接口，但 V1 不需要完整实现所有方法。

```python
from pathlib import Path
from typing import Protocol


class AdsPlatformProvider(Protocol):
    def test_connection(self) -> dict:
        ...

    def fetch_campaigns(self) -> Path:
        ...

    def fetch_report(
        self,
        date_from: str,
        date_to: str,
        report_type: str,
    ) -> Path:
        ...

    def upload_keywords(self, input_path: Path) -> Path:
        ...

    def upload_ads(self, input_path: Path) -> Path:
        ...
```

未来实现：

```text
YandexDirectProvider
VKAdsProvider
GoogleAdsProvider
```

当前只实现 `YandexDirectProvider` 的 `test_connection()` 和 `fetch_report()` 即可。

---

# 10. 开源项目引入检查表

任何仓库在正式复用前都要检查：

## 基础状态

- [ ] 仓库是否仍可访问；
- [ ] 最近一次提交时间；
- [ ] 是否有 Release；
- [ ] Issue 是否大量无人处理；
- [ ] 是否有测试；
- [ ] 是否有明确许可证。

## API 兼容性

- [ ] 对应的是当前平台还是历史平台；
- [ ] API 版本是否仍受支持；
- [ ] 请求字段是否与官方文档一致；
- [ ] 是否支持 Agency / Client-Login；
- [ ] 是否支持 Sandbox；
- [ ] 是否正确处理分页、限额和异步报告。

## 安全

- [ ] Token 是否只从 `.env` 或安全配置读取；
- [ ] 日志是否可能打印 Token；
- [ ] 是否会上传客户广告数据到第三方服务器；
- [ ] 是否默认执行写操作；
- [ ] 是否支持 Dry Run；
- [ ] 批量修改前是否有人工作业确认。

## 工程适配

- [ ] 是否符合 Python 技术栈；
- [ ] 能否拆出少量独立代码；
- [ ] 是否会破坏当前文件交接流程；
- [ ] 是否引入不必要的数据库、前端或部署系统；
- [ ] 出错后能否回滚；
- [ ] 输出是否能保存为 JSON、CSV、TSV 或 Markdown。

---

# 11. 当前决策

## 立即纳入参考

- `elsvv/yandex-direct-skill`
- `pavelmaksimov/tapi-yandex-direct`
- `AgriciDaniel/claude-ads`
- `competitive-ads-extractor`

## 只研究，不接入

- `iscale-facebook-ad-builder`
- `biplane/yandex-direct`

## 暂不采用

- `YandexWordstatAPI`
- `vk-io` 的广告接口作为新版 VK Ads 依据
- 其他长期不维护的 Yandex Direct v4 客户端
- 与当前 Python 文件式工作流不兼容的完整 SaaS 框架

## 总体判断

GitHub 上已有项目可以显著减少以下工作的重复劳动：

- Yandex Direct API 服务梳理；
- API Client 封装；
- 报表轮询、下载与 TSV 导出；
- 投后审计规则设计；
- 竞品广告结构化分析；
- 广告生成产品流程设计。

但目前没有发现一套成熟项目可以完整替代本项目。需要保留的核心价值仍然是：

- 俄语区业务知识；
- Yandex / VK 实际投放流程；
- 客户资料读取；
- Wordstat 半人工工作流；
- 关键词审核与广告框架划分；
- 俄语广告文案；
- 否词判断；
- 文件状态管理；
- Human-in-the-Loop；
- 面向其他平台的迁移能力。

因此，正确策略不是推翻现有项目，而是把开源仓库作为“外部组件和设计参考库”，逐步吸收到当前模块体系中。
