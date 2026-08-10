# web_reader.py 只负责：
# 读取 website_urls.txt
# 访问网站
# 发现同一网站内的链接
# 提取标题、描述、正文、标题标签和链接文字
# 生成结构化文件
# 记录读取成功和失败情况
# 暂时不要让它：
# 调用 AI
# 生成 Sitelink
# 分析竞品
# 修改 project_brief.md
# 把内容混入 raw_text.txt
# 这样网页采集和 AI 生成仍然是两个独立层。




# PowerShell 运行（请先进入项目根目录）：
# 方式一：运行后在终端输入项目名称
# & ".\.venv\Scripts\python.exe" -m modules.web_reader --max-pages 15 --max-depth 1
# 方式二：直接在命令中指定项目名称
# & ".\.venv\Scripts\python.exe" -m modules.web_reader --project 通亚 --max-pages 15 --max-depth 1

from __future__ import annotations

import argparse
import csv
import json
import re
import time

from collections import deque
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

import requests

from modules.website_url_extractor import resolve_website_urls_path


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36 "
    "SEM-Workflow-WebReader/1.0"
)

SKIP_TAGS = {
    "script",
    "style",
    "noscript",
    "svg",
    "canvas",
    "template",
}

REPORT_FIELDS = [
    "请求URL",
    "最终URL",
    "来源URL",
    "深度",
    "读取状态",
    "HTTP状态码",
    "页面标题",
    "页面语言",
    "正文字符数",
    "备注",
]


def get_project_root() -> Path:
    """
    返回项目根目录。

    当前文件位于：
    项目根目录/modules/web_reader.py
    """
    return Path(__file__).resolve().parent.parent


def get_upload_dir(project_name: str) -> Path:
    return get_project_root() / "uploads" / project_name


def get_output_dir(project_name: str) -> Path:
    return get_project_root() / "outputs" / project_name


def clean_text(text: str | None) -> str:
    """
    合并多余的空格、换行和制表符。

    HTMLParser 解析到没有显式值的 HTML 属性时可能返回 None，
    因此这里同时接受字符串和 None。
    """
    return re.sub(r"\s+", " ", text or "").strip()


def normalize_url(url: str) -> str:
    """
    规范化用于抓取的网页 URL。

    页面片段（#contact）不会影响服务器返回的 HTML，
    因此抓取页面时去掉片段，但链接清单中仍会保存完整链接。
    """
    url = url.strip()
    url, _fragment = urldefrag(url)

    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"}:
        return ""

    if not parsed.netloc:
        return ""

    return url


def canonical_hostname(url: str) -> str:
    """
    获取用于比较的域名。

    example.com 和 www.example.com 被视为同一个网站。
    """
    hostname = (urlparse(url).hostname or "").lower()

    if hostname.startswith("www."):
        hostname = hostname[4:]

    return hostname


def is_same_site(url: str, allowed_hostnames: set[str]) -> bool:
    hostname = canonical_hostname(url)
    return bool(hostname and hostname in allowed_hostnames)


def read_seed_urls(path: Path) -> list[str]:
    """
    从 website_urls.txt 读取入口网址。
    """
    if not path.exists():
        raise FileNotFoundError(
            f"找不到网站入口文件：{path}\n"
            f"请先运行 main.py 自动提取，或人工准备 website_urls.txt。"
        )

    raw_text = path.read_text(encoding="utf-8")
    urls = []

    for raw_line in raw_text.splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#"):
            continue

        url = normalize_url(line)

        if not url:
            raise ValueError(
                f"website_urls.txt 中存在无效网址：{line}\n"
                f"网址必须以 http:// 或 https:// 开头。"
            )

        if url not in urls:
            urls.append(url)

    if not urls:
        raise ValueError(f"网站入口文件为空：{path}")

    return urls


class WebsiteHTMLParser(HTMLParser):
    """
    使用 Python 标准库解析 HTML。

    当前版本主要提取：
    - 页面语言
    - title
    - meta description
    - H1/H2/H3
    - 页面可见文字
    - 页面链接及链接文字
    - HTML 元素 ID，用于识别 #contact 之类的锚点
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)

        self.page_language = ""
        self.meta_description = ""

        self.title_parts = []
        self.text_parts = []
        self.headings = []
        self.links = []
        self.element_ids = set()

        self._skip_depth = 0
        self._inside_title = False
        self._heading_tag = None
        self._heading_parts = []

        self._current_href = None
        self._anchor_parts = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attrs_dict = {
            str(key).lower(): value
            for key, value in attrs
            if key
        }

        element_id = attrs_dict.get("id") or attrs_dict.get("name")

        if element_id:
            self.element_ids.add(str(element_id).strip())

        if tag in SKIP_TAGS:
            self._skip_depth += 1
            return

        if self._skip_depth:
            return

        if tag == "html":
            self.page_language = clean_text(attrs_dict.get("lang", ""))

        elif tag == "meta":
            meta_name = clean_text(attrs_dict.get("name", "")).lower()
            meta_property = clean_text(
                attrs_dict.get("property", "")
            ).lower()

            if (
                meta_name == "description"
                or meta_property == "og:description"
            ):
                content = clean_text(attrs_dict.get("content", ""))

                if content and not self.meta_description:
                    self.meta_description = content

        elif tag == "title":
            self._inside_title = True

        elif tag in {"h1", "h2", "h3"}:
            self._heading_tag = tag
            self._heading_parts = []

        elif tag == "a":
            self._current_href = attrs_dict.get("href")
            self._anchor_parts = []

    def handle_endtag(self, tag):
        tag = tag.lower()

        if tag in SKIP_TAGS:
            if self._skip_depth > 0:
                self._skip_depth -= 1
            return

        if self._skip_depth:
            return

        if tag == "title":
            self._inside_title = False

        elif tag in {"h1", "h2", "h3"}:
            heading_text = clean_text(" ".join(self._heading_parts))

            if heading_text:
                self.headings.append({
                    "level": tag,
                    "text": heading_text,
                })

            self._heading_tag = None
            self._heading_parts = []

        elif tag == "a":
            if self._current_href:
                self.links.append({
                    "href": self._current_href,
                    "text": clean_text(" ".join(self._anchor_parts)),
                })

            self._current_href = None
            self._anchor_parts = []

    def handle_data(self, data):
        if self._skip_depth:
            return

        text = clean_text(data)

        if not text:
            return

        self.text_parts.append(text)

        if self._inside_title:
            self.title_parts.append(text)

        if self._heading_tag:
            self._heading_parts.append(text)

        if self._current_href is not None:
            self._anchor_parts.append(text)

    def get_title(self) -> str:
        return clean_text(" ".join(self.title_parts))

    def get_text(self) -> str:
        return clean_text(" ".join(self.text_parts))


def parse_html(html: str) -> WebsiteHTMLParser:
    parser = WebsiteHTMLParser()
    parser.feed(html)
    parser.close()
    return parser


def build_markdown(project_name: str, pages: list[dict]) -> str:
    """
    生成人工和 AI 都比较容易阅读的 Markdown 文件。
    """
    sections = [
        f"# {project_name} 网站内容",
        "",
        f"- 抓取时间：{datetime.now().isoformat(timespec='seconds')}",
        f"- 成功读取页面数：{len(pages)}",
    ]

    for index, page in enumerate(pages, start=1):
        sections.extend([
            "",
            "---",
            "",
            f"## 页面 {index}：{page['title'] or '无标题'}",
            "",
            f"- URL：{page['url']}",
            f"- HTTP状态码：{page['http_status']}",
            f"- 页面语言：{page['language'] or '未知'}",
            f"- 抓取深度：{page['depth']}",
            "",
        ])

        if page["meta_description"]:
            sections.extend([
                "### 页面描述",
                "",
                page["meta_description"],
                "",
            ])

        if page["headings"]:
            sections.extend([
                "### 页面标题结构",
                "",
            ])

            for heading in page["headings"]:
                sections.append(
                    f"- {heading['level'].upper()}：{heading['text']}"
                )

            sections.append("")

        sections.extend([
            "### 页面正文",
            "",
            page["text"],
        ])

    return "\n".join(sections).strip() + "\n"


def write_csv(path: Path, rows: list[dict]) -> None:
    with open(
        path,
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=REPORT_FIELDS,
        )
        writer.writeheader()
        writer.writerows(rows)


def crawl_website(
    seed_urls: list[str],
    max_pages: int = 30,
    max_depth: int = 2,
    delay: float = 0.5,
    timeout: int = 15,
    max_chars_per_page: int = 20000,
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    抓取客户网站。

    返回：
    pages：成功读取的页面
    discovered_links：发现的所有内部链接
    report_rows：读取报告
    """
    allowed_hostnames = {
        canonical_hostname(url)
        for url in seed_urls
        if canonical_hostname(url)
    }

    queue = deque(
        (url, 0, "")
        for url in seed_urls
    )

    visited = set()
    visited_final_urls = set()

    pages = []
    discovered_links = []
    discovered_link_keys = set()
    report_rows = []

    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,*/*;q=0.8"
        ),
        "Accept-Language": "ru,en;q=0.8,zh-CN;q=0.5",
    })

    while queue and len(pages) < max_pages:
        requested_url, depth, source_url = queue.popleft()
        requested_url = normalize_url(requested_url)

        if not requested_url:
            continue

        if requested_url in visited:
            continue

        visited.add(requested_url)

        print(f"\n正在读取：{requested_url}")
        print(f"当前深度：{depth}")

        try:
            response = session.get(
                requested_url,
                timeout=timeout,
                allow_redirects=True,
            )

            final_url = normalize_url(response.url)

            if depth == 0 and final_url:
                # 允许入口网址发生 www/non-www 或正式域名重定向
                allowed_hostnames.add(
                    canonical_hostname(final_url)
                )

            http_status = response.status_code
            content_type = response.headers.get(
                "Content-Type",
                "",
            ).lower()

            if not response.ok:
                report_rows.append({
                    "请求URL": requested_url,
                    "最终URL": final_url,
                    "来源URL": source_url,
                    "深度": depth,
                    "读取状态": "失败",
                    "HTTP状态码": http_status,
                    "页面标题": "",
                    "页面语言": "",
                    "正文字符数": 0,
                    "备注": f"HTTP状态码异常：{http_status}",
                })
                continue

            if "text/html" not in content_type:
                report_rows.append({
                    "请求URL": requested_url,
                    "最终URL": final_url,
                    "来源URL": source_url,
                    "深度": depth,
                    "读取状态": "跳过",
                    "HTTP状态码": http_status,
                    "页面标题": "",
                    "页面语言": "",
                    "正文字符数": 0,
                    "备注": f"不是HTML页面：{content_type}",
                })
                continue

            if final_url in visited_final_urls:
                report_rows.append({
                    "请求URL": requested_url,
                    "最终URL": final_url,
                    "来源URL": source_url,
                    "深度": depth,
                    "读取状态": "跳过",
                    "HTTP状态码": http_status,
                    "页面标题": "",
                    "页面语言": "",
                    "正文字符数": 0,
                    "备注": "重定向后页面已经读取",
                })
                continue

            visited_final_urls.add(final_url)

            if not response.encoding:
                response.encoding = (
                    response.apparent_encoding or "utf-8"
                )

            parser = parse_html(response.text)

            title = parser.get_title()
            page_text = parser.get_text()

            if max_chars_per_page > 0:
                page_text = page_text[:max_chars_per_page]

            normalized_links = []

            for raw_link in parser.links:
                href = clean_text(raw_link.get("href", ""))

                if not href:
                    continue

                absolute_url = urljoin(final_url, href)
                parsed_link = urlparse(absolute_url)

                if parsed_link.scheme not in {"http", "https"}:
                    continue

                if not is_same_site(
                    absolute_url,
                    allowed_hostnames,
                ):
                    continue

                link_without_fragment, fragment = urldefrag(
                    absolute_url
                )
                page_url = normalize_url(link_without_fragment)

                if not page_url:
                    continue

                full_target_url = page_url

                if fragment:
                    full_target_url += f"#{fragment}"

                link_data = {
                    "source_url": final_url,
                    "target_url": full_target_url,
                    "page_url": page_url,
                    "fragment": fragment,
                    "anchor_text": clean_text(
                        raw_link.get("text", "")
                    ),
                }

                link_key = (
                    link_data["source_url"],
                    link_data["target_url"],
                    link_data["anchor_text"],
                )

                if link_key not in discovered_link_keys:
                    discovered_link_keys.add(link_key)
                    discovered_links.append(link_data)

                normalized_links.append(link_data)

                if (
                    depth < max_depth
                    and page_url not in visited
                ):
                    queue.append(
                        (page_url, depth + 1, final_url)
                    )

            page_data = {
                "url": final_url,
                "requested_url": requested_url,
                "source_url": source_url,
                "depth": depth,
                "http_status": http_status,
                "language": parser.page_language,
                "title": title,
                "meta_description": parser.meta_description,
                "headings": parser.headings,
                "text": page_text,
                "text_char_count": len(page_text),
                "element_ids": sorted(parser.element_ids),
                "links": normalized_links,
            }

            pages.append(page_data)

            report_rows.append({
                "请求URL": requested_url,
                "最终URL": final_url,
                "来源URL": source_url,
                "深度": depth,
                "读取状态": "成功",
                "HTTP状态码": http_status,
                "页面标题": title,
                "页面语言": parser.page_language,
                "正文字符数": len(page_text),
                "备注": "正常",
            })

            print(f"读取成功：{title or '无标题'}")
            print(f"提取正文字符数：{len(page_text)}")
            print(f"发现内部链接数：{len(normalized_links)}")

        except requests.RequestException as error:
            report_rows.append({
                "请求URL": requested_url,
                "最终URL": "",
                "来源URL": source_url,
                "深度": depth,
                "读取状态": "失败",
                "HTTP状态码": "",
                "页面标题": "",
                "页面语言": "",
                "正文字符数": 0,
                "备注": str(error),
            })

            print(f"读取失败：{error}")

        if delay > 0:
            time.sleep(delay)

    return pages, discovered_links, report_rows


def read_website(
    project_name: str,
    max_pages: int = 30,
    max_depth: int = 2,
    delay: float = 0.5,
    timeout: int = 15,
    max_chars_per_page: int = 20000,
) -> dict:
    """
    网页读取模块的主业务函数。
    """
    project_root = get_project_root()
    output_dir = get_output_dir(project_name)

    url_file, url_source = resolve_website_urls_path(
        project_root=project_root,
        project_name=project_name,
    )

    if url_file is None:
        print(
            f"客户资料未提供网站，本项目跳过网页读取：{project_name}"
        )
        return {
            "project_name": project_name,
            "status": "skipped_no_website",
            "seed_urls": [],
            "pages": [],
            "links": [],
        }

    if url_source == "uploads_legacy":
        print(
            "提示：正在读取旧路径中的 website_urls.txt。\n"
            f"旧路径：{url_file}\n"
            "后续建议通过 main.py 生成到 outputs/项目名称/。"
        )
    else:
        print(f"网站入口文件：{url_file}")

    seed_urls = read_seed_urls(url_file)

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(f"开始读取项目网站：{project_name}")
    print(f"入口网址数量：{len(seed_urls)}")
    print(f"最大页面数：{max_pages}")
    print(f"最大抓取深度：{max_depth}")

    pages, discovered_links, report_rows = crawl_website(
        seed_urls=seed_urls,
        max_pages=max_pages,
        max_depth=max_depth,
        delay=delay,
        timeout=timeout,
        max_chars_per_page=max_chars_per_page,
    )

    result = {
        "project_name": project_name,
        "generated_at": datetime.now().isoformat(
            timespec="seconds"
        ),
        "seed_urls": seed_urls,
        "settings": {
            "max_pages": max_pages,
            "max_depth": max_depth,
            "delay": delay,
            "timeout": timeout,
            "max_chars_per_page": max_chars_per_page,
        },
        "summary": {
            "successful_pages": len(pages),
            "discovered_links": len(discovered_links),
            "report_rows": len(report_rows),
        },
        "pages": pages,
        "links": discovered_links,
    }

    json_path = output_dir / "website_pages.json"
    markdown_path = output_dir / "website_content.md"
    report_path = output_dir / "web_report.csv"

    json_path.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    markdown_path.write_text(
        build_markdown(project_name, pages),
        encoding="utf-8",
    )

    write_csv(report_path, report_rows)

    print("\n网页读取完成")
    print(f"成功页面数：{len(pages)}")
    print(f"发现内部链接数：{len(discovered_links)}")
    print(f"结构化数据：{json_path}")
    print(f"网页正文：{markdown_path}")
    print(f"读取报告：{report_path}")

    return result


def main():
    parser = argparse.ArgumentParser(
        description="读取客户网站并整理网页内容和内部链接。"
    )

    parser.add_argument(
        "--project",
        help="项目名称，对应 uploads 和 outputs 下的文件夹名称",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=30,
        help="最多成功读取多少个HTML页面，默认30",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=2,
        help="站内链接最大抓取深度，默认2",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="每次请求后的等待秒数，默认0.5",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=15,
        help="单个网页请求超时秒数，默认15",
    )
    parser.add_argument(
        "--max-chars-per-page",
        type=int,
        default=20000,
        help="每个页面最多保留的正文字符数，默认20000",
    )

    args = parser.parse_args()

    project_name = (
        args.project
        or input("请输入项目名称（须与 uploads 下的文件夹名完全一致）：").strip()
    )

    if not project_name:
        raise ValueError("项目名称不能为空。")

    if args.max_pages <= 0:
        raise ValueError("--max-pages 必须大于0。")

    if args.max_depth < 0:
        raise ValueError("--max-depth 不能小于0。")

    read_website(
        project_name=project_name,
        max_pages=args.max_pages,
        max_depth=args.max_depth,
        delay=args.delay,
        timeout=args.timeout,
        max_chars_per_page=args.max_chars_per_page,
    )


if __name__ == "__main__":
    main()
