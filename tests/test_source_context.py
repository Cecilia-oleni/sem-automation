from __future__ import annotations

import json
import tempfile
import unittest

from pathlib import Path

from sem_automation.cli.materials import build_parser
from sem_automation.materials.context.source_context import (
    LOCAL_SECTION_START,
    WEBSITE_SECTION_START,
    compose_raw_text,
    limit_source_context,
)
from sem_automation.materials.context.website import (
    EXPLICIT_CLI_MARKER,
    normalize_explicit_website_urls,
    update_website_urls_file,
    write_explicit_website_urls,
)


class SourceContextTests(unittest.TestCase):
    def test_composes_local_and_multiple_website_pages(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            (output_dir / "raw_text_local.txt").write_text("本地产品资料", encoding="utf-8")
            payload = {
                "pages": [
                    {"url": "https://example.com/a", "title": "产品A", "text": "甲" * 300},
                    {"url": "https://example.com/b", "title": "产品B", "text": "乙" * 300},
                ]
            }
            (output_dir / "website_pages.json").write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )

            result = compose_raw_text(output_dir, website_max_chars=500)
            raw_text = (output_dir / "raw_text.txt").read_text(encoding="utf-8")

            self.assertTrue(result["local_available"])
            self.assertTrue(result["website_available"])
            self.assertIn("本地产品资料", raw_text)
            self.assertIn("https://example.com/a", raw_text)
            self.assertIn("https://example.com/b", raw_text)
            self.assertIn("甲", raw_text)
            self.assertIn("乙", raw_text)

    def test_source_aware_limit_keeps_both_sources(self):
        text = (
            f"{LOCAL_SECTION_START}\n" + "本" * 1000 + "\n===== 本地客户资料结束 =====\n"
            f"{WEBSITE_SECTION_START}\n" + "网" * 1000 + "\n===== 客户网站内容结束 ====="
        )
        limited = limit_source_context(text, 200)
        self.assertIn("本", limited)
        self.assertIn("网", limited)
        self.assertIn(LOCAL_SECTION_START, limited)
        self.assertIn(WEBSITE_SECTION_START, limited)

    def test_compose_rejects_no_effective_sources(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            (output_dir / "raw_text_local.txt").write_text("", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "没有可用于分析"):
                compose_raw_text(output_dir)


class ExplicitWebsiteUrlTests(unittest.TestCase):
    def test_cli_accepts_repeated_website_arguments(self):
        args = build_parser().parse_args([
            "--project", "demo",
            "--website", "https://a.example.com",
            "--website", "https://b.example.com",
        ])
        self.assertEqual(
            args.website,
            ["https://a.example.com", "https://b.example.com"],
        )

    def test_normalizes_and_deduplicates(self):
        self.assertEqual(
            normalize_explicit_website_urls([
                "https://EXAMPLE.com/path#top",
                "https://example.com/path",
            ]),
            ["https://example.com/path"],
        )

    def test_rejects_missing_scheme(self):
        with self.assertRaisesRegex(ValueError, "必须以 http"):
            normalize_explicit_website_urls(["example.com"])

    def test_explicit_file_replaces_existing_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            (output_dir / "website_urls.txt").write_text(
                "https://old.example.com\n", encoding="utf-8"
            )
            path = write_explicit_website_urls(
                output_dir, ["https://new.example.com"]
            )
            content = path.read_text(encoding="utf-8")
            self.assertIn("https://new.example.com", content)
            self.assertNotIn("https://old.example.com", content)

    def test_explicit_file_is_preserved_on_later_collection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            path = output_dir / "website_urls.txt"
            path.write_text(
                f"{EXPLICIT_CLI_MARKER}\nhttps://explicit.example.com\n",
                encoding="utf-8",
            )
            status = update_website_urls_file(output_dir, [{
                "url": "https://auto.example.com",
                "source": "brief.docx",
                "label": "客户官网",
            }])
            self.assertEqual(status, "preserved_explicit")
            self.assertIn("explicit.example.com", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
