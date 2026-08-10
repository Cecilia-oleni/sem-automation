from __future__ import annotations

import tempfile
import unittest
import json

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from openpyxl import load_workbook

from modules.sitelink_callout_generator import (
    generate_sitelink_callouts,
    validate_payload,
    write_xlsx,
)
from modules.web_reader import read_website
from modules.website_url_extractor import (
    AUTO_GENERATED_MARKER,
    extract_client_website_urls,
    resolve_website_urls_path,
    update_website_urls_file,
)


class WebsiteUrlExtractorTests(unittest.TestCase):
    def test_extracts_customer_site_and_ignores_competitors(self):
        documents = [{
            "source": "客户-Yandex广告信息采集表.docx",
            "content": (
                "公司全称：示例公司\n"
                "推广网站域名：milesight.com | 对接人：张三\n"
                "国内外竞争对手及其网址\n"
                "Hikvision: https://www.hikvision.com/cis/\n"
                "历史广告落地页：https://ads.example.net/landing\n"
            ),
        }]

        records = extract_client_website_urls(documents)

        self.assertEqual([record["url"] for record in records], ["https://milesight.com"])

    def test_preserves_path_and_deduplicates_multiple_official_fields(self):
        documents = [{
            "source": "客户信息采集表.docx",
            "content": (
                "客户官网：www.example.com/ru/products\n"
                "官方网站：https://www.example.com/ru/products\n"
            ),
        }]

        records = extract_client_website_urls(documents)

        self.assertEqual(
            [record["url"] for record in records],
            ["https://www.example.com/ru/products"],
        )

    def test_blank_website_field_returns_no_records(self):
        documents = [{
            "source": "客户信息采集表.docx",
            "content": "推广网站域名： | 对接人：张三\n品牌名称：Example",
        }]

        self.assertEqual(extract_client_website_urls(documents), [])

    def test_generated_file_lifecycle_preserves_manual_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            records = [{
                "url": "https://example.com",
                "source": "信息采集表.docx",
                "label": "推广网站域名",
            }]

            self.assertEqual(update_website_urls_file(output_dir, records), "written")
            generated_path = output_dir / "website_urls.txt"
            self.assertTrue(generated_path.read_text(encoding="utf-8").startswith(AUTO_GENERATED_MARKER))
            self.assertEqual(update_website_urls_file(output_dir, []), "removed_stale")
            self.assertFalse(generated_path.exists())

            generated_path.write_text("https://manual.example.com\n", encoding="utf-8")
            self.assertEqual(update_website_urls_file(output_dir, []), "preserved_manual")
            self.assertTrue(generated_path.exists())

    def test_outputs_path_precedes_legacy_uploads_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_path = root / "outputs" / "项目A" / "website_urls.txt"
            legacy_path = root / "uploads" / "项目A" / "website_urls.txt"
            output_path.parent.mkdir(parents=True)
            legacy_path.parent.mkdir(parents=True)
            output_path.write_text("https://new.example.com\n", encoding="utf-8")
            legacy_path.write_text("https://old.example.com\n", encoding="utf-8")

            resolved, source = resolve_website_urls_path(root, "项目A")
            self.assertEqual(resolved, output_path)
            self.assertEqual(source, "outputs")

            output_path.unlink()
            resolved, source = resolve_website_urls_path(root, "项目A")
            self.assertEqual(resolved, legacy_path)
            self.assertEqual(source, "uploads_legacy")


class WebsiteWorkflowModeTests(unittest.TestCase):
    def test_web_reader_skips_project_without_website(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("modules.web_reader.get_project_root", return_value=Path(temp_dir)):
                with redirect_stdout(StringIO()):
                    result = read_website("无网站项目")

        self.assertEqual(result["status"], "skipped_no_website")
        self.assertEqual(result["pages"], [])

    def test_callout_only_validation_accepts_empty_sitelinks(self):
        callouts = [
            {"text_ru": f"Пункт {index}", "text_zh": f"标注{index}"}
            for index in range(1, 11)
        ]
        payload = {"sitelinks": [], "callouts": callouts}

        errors = validate_payload(
            payload=payload,
            page_map={},
            sitelinks_required=False,
        )

        self.assertEqual(errors, [])

    def test_callout_only_excel_contains_skip_notice(self):
        callouts = [{
            "index": index,
            "text_ru": f"Пункт {index}",
            "text_zh": f"标注{index}",
            "char_count": len(f"Пункт {index}"),
            "char_limit": 25,
            "recommendation": "备用候选" if index > 8 else "桌面端主选",
            "status": "OK",
        } for index in range(1, 11)]
        data = {
            "sitelinks": [],
            "sitelinks_status": "skipped_no_website",
            "callouts": callouts,
            "summary": {
                "desktop_primary_total_chars": sum(item["char_count"] for item in callouts[:8]),
                "mobile_primary_total_chars": sum(item["char_count"] for item in callouts[:4]),
            },
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "result.xlsx"
            write_xlsx(path, data)
            workbook = load_workbook(path, read_only=True)
            sheet = workbook["sitelink+callouts"]
            self.assertIn("Sitelink未生成", sheet["A1"].value)
            workbook.close()

    def test_website_config_without_crawl_result_errors_before_api(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "outputs" / "项目A"
            output_dir.mkdir(parents=True)
            (output_dir / "project_brief.md").write_text("项目资料", encoding="utf-8")
            (output_dir / "website_urls.txt").write_text(
                "https://example.com\n",
                encoding="utf-8",
            )

            with patch(
                "modules.sitelink_callout_generator.get_project_root",
                return_value=root,
            ):
                with self.assertRaisesRegex(FileNotFoundError, "请先运行 modules.web_reader"):
                    generate_sitelink_callouts("项目A")

    def test_callout_only_generation_writes_all_three_outputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "outputs" / "无网站项目"
            output_dir.mkdir(parents=True)
            (output_dir / "project_brief.md").write_text(
                "客户提供企业软件服务，支持项目咨询。",
                encoding="utf-8",
            )
            callouts = [
                {"text_ru": f"Услуга {index}", "text_zh": f"服务{index}"}
                for index in range(1, 11)
            ]
            fake_result = {
                "content": json.dumps(
                    {"callouts": callouts},
                    ensure_ascii=False,
                ),
                "actual_model": "test-model",
                "provider": "test-provider",
                "finish_reason": "stop",
                "usage": {},
            }

            with patch(
                "modules.sitelink_callout_generator.get_project_root",
                return_value=root,
            ), patch(
                "modules.sitelink_callout_generator.call_llm",
                return_value=fake_result,
            ):
                result = generate_sitelink_callouts("无网站项目")

            self.assertEqual(result["sitelinks"], [])
            self.assertEqual(result["sitelinks_status"], "skipped_no_website")
            self.assertEqual(len(result["callouts"]), 10)
            self.assertTrue((output_dir / "sitelink_callouts_raw.md").exists())
            self.assertTrue((output_dir / "sitelink_callouts.json").exists())
            self.assertTrue((output_dir / "sitelink_callouts.xlsx").exists())


if __name__ == "__main__":
    unittest.main()
