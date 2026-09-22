# 模块：sem_automation/materials/context/source_context.py；内部模块由统一入口调用。
# VS Code PowerShell 先输入：Set-Location -LiteralPath 'D:\sem自动化 - 副本'
# 终端输入（复制时去掉注释符）：& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' materials run --project '通亚' --dry-run
# 上述为离线预览；生成物料时去掉 --dry-run，按提示完成人工节点。
"""把本地资料和网站抓取结果组装为供下游 AI 使用的统一上下文。"""

from __future__ import annotations

import json
from pathlib import Path

from sem_automation.core.text_utils import get_env_int


LOCAL_SECTION_START = "===== 本地客户资料 ====="
LOCAL_SECTION_END = "===== 本地客户资料结束 ====="
WEBSITE_SECTION_START = "===== 客户网站内容 ====="
WEBSITE_SECTION_END = "===== 客户网站内容结束 ====="


def _clean(value: object) -> str:
    return str(value or "").strip()


def _page_metadata(page: dict, index: int) -> str:
    lines = [
        f"--- 网站页面 {index} ---",
        f"URL：{_clean(page.get('url'))}",
        f"标题：{_clean(page.get('title')) or '无标题'}",
    ]
    description = _clean(page.get("meta_description"))
    if description:
        lines.append(f"页面描述：{description}")

    headings = []
    for heading in page.get("headings") or []:
        if not isinstance(heading, dict):
            continue
        text = _clean(heading.get("text"))
        if text:
            headings.append(f"{_clean(heading.get('level')).upper()}：{text}")
    if headings:
        lines.append("标题结构：" + " | ".join(headings))
    return "\n".join(lines)


def build_website_source(pages: list[dict], max_chars: int) -> str:
    """在总预算内保留每页元数据，并把正文额度尽量均匀分配到各页。"""
    valid_pages = [
        page for page in pages
        if isinstance(page, dict) and _clean(page.get("text"))
    ]
    if not valid_pages:
        return ""

    metadata = [_page_metadata(page, index) for index, page in enumerate(valid_pages, 1)]
    metadata_length = sum(len(item) for item in metadata) + max(0, len(metadata) - 1) * 2

    if max_chars <= 0:
        body_budget = sum(len(_clean(page.get("text"))) for page in valid_pages)
    else:
        body_budget = max(0, max_chars - metadata_length - len(valid_pages) * len("\n正文：\n"))

    bodies = [_clean(page.get("text")) for page in valid_pages]
    allocations = [0] * len(bodies)
    remaining = body_budget
    active = {index for index, body in enumerate(bodies) if body}

    # 分轮均分，短页面未使用的额度会继续转给其他页面。
    while remaining > 0 and active:
        share = max(1, remaining // len(active))
        progressed = False
        for index in list(active):
            available = len(bodies[index]) - allocations[index]
            take = min(available, share, remaining)
            if take > 0:
                allocations[index] += take
                remaining -= take
                progressed = True
            if allocations[index] >= len(bodies[index]):
                active.remove(index)
            if remaining <= 0:
                break
        if not progressed:
            break

    sections = []
    for meta, body, allocation in zip(metadata, bodies, allocations):
        excerpt = body[:allocation]
        if allocation < len(body):
            excerpt += "\n【本页面正文因网站资料预算限制已截断】"
        sections.append(f"{meta}\n正文：\n{excerpt}".rstrip())

    result = "\n\n".join(sections)
    if max_chars > 0 and len(result) > max_chars:
        result = result[:max_chars]
    return result


def load_website_pages(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    pages = payload.get("pages", []) if isinstance(payload, dict) else []
    return pages if isinstance(pages, list) else []


def compose_raw_text(
    output_dir: Path,
    website_max_chars: int | None = None,
    *,
    include_website: bool = True,
) -> dict:
    """生成 raw_text.txt；本地正文和网站正文至少有一项必须有效。"""
    local_path = output_dir / "raw_text_local.txt"
    local_text = local_path.read_text(encoding="utf-8").strip() if local_path.is_file() else ""

    pages = (
        load_website_pages(output_dir / "website_pages.json")
        if include_website
        else []
    )
    if website_max_chars is None:
        website_max_chars = get_env_int("WEBSITE_RAW_TEXT_MAX_CHARS", default=30000)
    website_text = build_website_source(pages, website_max_chars)

    sections = []
    if local_text:
        sections.append(f"{LOCAL_SECTION_START}\n\n{local_text}\n\n{LOCAL_SECTION_END}")
    if website_text:
        sections.append(
            f"{WEBSITE_SECTION_START}\n\n{website_text}\n\n{WEBSITE_SECTION_END}"
        )
    if not sections:
        raise ValueError("没有可用于分析的本地资料或网站正文，无法生成 raw_text.txt。")

    raw_text = "\n\n".join(sections).strip() + "\n"
    raw_path = output_dir / "raw_text.txt"
    raw_path.write_text(raw_text, encoding="utf-8")
    return {
        "path": raw_path,
        "local_available": bool(local_text),
        "website_available": bool(website_text),
        "website_page_count": len([
            page for page in pages
            if isinstance(page, dict) and _clean(page.get("text"))
        ]),
    }


def _extract_section(text: str, start: str, end: str) -> str:
    start_index = text.find(start)
    if start_index < 0:
        return ""
    content_start = start_index + len(start)
    end_index = text.find(end, content_start)
    if end_index < 0:
        end_index = len(text)
    return text[content_start:end_index].strip()


def _allocate_two_sources(first: str, second: str, max_chars: int) -> tuple[str, str]:
    half = max_chars // 2
    first_take = min(len(first), half)
    second_take = min(len(second), max_chars - first_take)
    remaining = max_chars - first_take - second_take
    if remaining > 0:
        first_take += min(len(first) - first_take, remaining)
        remaining = max_chars - first_take - second_take
    if remaining > 0:
        second_take += min(len(second) - second_take, remaining)
    return first[:first_take], second[:second_take]


def limit_source_context(text: str, max_chars: int | None, notice: str | None = None) -> str:
    """按来源公平截断统一 raw_text，保证混合项目的两类资料都被模型看到。"""
    if max_chars is None or max_chars <= 0 or len(text) <= max_chars:
        return text

    local_text = _extract_section(text, LOCAL_SECTION_START, LOCAL_SECTION_END)
    website_text = _extract_section(text, WEBSITE_SECTION_START, WEBSITE_SECTION_END)
    if not local_text or not website_text:
        limited = text[:max_chars]
    else:
        local_limited, website_limited = _allocate_two_sources(
            local_text, website_text, max_chars
        )
        limited = (
            f"{LOCAL_SECTION_START}\n\n{local_limited}\n\n{LOCAL_SECTION_END}\n\n"
            f"{WEBSITE_SECTION_START}\n\n{website_limited}\n\n{WEBSITE_SECTION_END}"
        )

    if notice:
        limited += "\n\n" + notice
    return limited
