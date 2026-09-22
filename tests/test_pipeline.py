from __future__ import annotations

import json
import tempfile
import unittest

from pathlib import Path
from unittest.mock import patch

from sem_automation.materials.context import collect as main_module
from sem_automation.materials.pipeline import PipelineRunner


def write_nonempty(path: Path, content: str = "test") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class ProjectCollectionTests(unittest.TestCase):
    def test_collect_project_data_is_callable_and_returns_outputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "uploads" / "materials" / "项目A" / "客户资料.txt"
            write_nonempty(source, "官方网站：example.com")

            with patch.object(main_module, "PROJECT_ROOT", root), patch.object(
                main_module,
                "read_file",
                return_value=("官方网站：example.com", "成功", ""),
            ):
                result = main_module.collect_project_data("项目A")

            output_dir = root / "outputs" / "materials" / "项目A"
            self.assertEqual(result["project_name"], "项目A")
            self.assertTrue((output_dir / "raw_text_local.txt").exists())
            self.assertFalse((output_dir / "raw_text.txt").exists())
            self.assertTrue((output_dir / "file_report.csv").exists())
            self.assertTrue((output_dir / "website_urls.txt").exists())

    def test_collect_project_data_rejects_empty_project_name(self):
        with self.assertRaisesRegex(ValueError, "项目名称不能为空"):
            main_module.collect_project_data("  ")


class PipelineRunnerTests(unittest.TestCase):
    def make_project(self, root: Path, project: str = "项目A") -> Path:
        (root / "uploads" / "materials" / project).mkdir(parents=True)
        output_dir = root / "outputs" / "materials" / project
        output_dir.mkdir(parents=True)
        return output_dir

    def prepare_initial_outputs(self, output_dir: Path) -> None:
        write_nonempty(output_dir / "raw_text_local.txt", "本地资料")
        write_nonempty(output_dir / "raw_text.txt")
        write_nonempty(output_dir / "file_report.csv")
        write_nonempty(output_dir / "project_brief.md")
        write_nonempty(output_dir / "keyword_v1.md")

    def test_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "uploads" / "materials" / "项目A").mkdir(parents=True)
            messages = []
            runner = PipelineRunner(
                "项目A",
                project_root=root,
                dry_run=True,
                output_func=messages.append,
            )

            result = runner.run()

            self.assertTrue(result["dry_run"])
            self.assertFalse((root / "outputs").exists())
            self.assertTrue(any("dry-run" in message for message in messages))

    def test_missing_review_checkpoint_can_stop_cleanly(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = self.make_project(root)
            self.prepare_initial_outputs(output_dir)
            answers = iter(["1", "1", "1", "2"])

            runner = PipelineRunner(
                "项目A",
                project_root=root,
                input_func=lambda _: next(answers),
                output_func=lambda _: None,
            )
            result = runner.run()

            self.assertTrue(result["stopped"])
            self.assertIn("keyword_review", result["waiting"])
            state = json.loads(
                (output_dir / "pipeline_status.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                state["steps"]["keyword_review"]["status"],
                "waiting_for_human",
            )

    def test_missing_review_can_continue_no_website_branch(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = self.make_project(root)
            self.prepare_initial_outputs(output_dir)
            for name in (
                "sitelink_callouts_raw.md",
                "sitelink_callouts.json",
                "sitelink_callouts.xlsx",
            ):
                write_nonempty(output_dir / name)

            answers = iter(["1", "1", "1", "1", "1"])
            runner = PipelineRunner(
                "项目A",
                project_root=root,
                input_func=lambda _: next(answers),
                output_func=lambda _: None,
            )
            result = runner.run()

            self.assertFalse(result["stopped"])
            self.assertIn("keyword_review", result["waiting"])
            self.assertEqual(result["statuses"]["web_reader"], "skipped")
            self.assertEqual(result["statuses"]["sitelink_callouts"], "skipped")

    def test_existing_output_can_be_rerun(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = self.make_project(root)
            self.prepare_initial_outputs(output_dir)
            answers = iter(["1", "2", "1", "2"])

            def fake_brief(project_name: str, *, project_root) -> str:
                self.assertEqual(project_name, "项目A")
                write_nonempty(output_dir / "project_brief.md", "new brief")
                return "new brief"

            with patch(
                "sem_automation.materials.pipeline.analyze_project_brief",
                side_effect=fake_brief,
            ) as mocked:
                runner = PipelineRunner(
                    "项目A",
                    project_root=root,
                    input_func=lambda _: next(answers),
                    output_func=lambda _: None,
                )
                runner.run()

            mocked.assert_called_once_with("项目A", project_root=root)
            self.assertEqual(
                json.loads(
                    (output_dir / "pipeline_status.json").read_text(encoding="utf-8")
                )["steps"]["project_brief"]["status"],
                "completed",
            )

    def test_website_failure_with_local_source_degrades_to_warning(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = self.make_project(root)
            self.prepare_initial_outputs(output_dir)
            write_nonempty(output_dir / "website_urls.txt", "https://example.com\n")
            answers = iter(["1", "1", "1", "2"])

            with patch(
                "sem_automation.materials.pipeline.read_website",
                side_effect=RuntimeError("抓取失败"),
            ):
                runner = PipelineRunner(
                    "项目A",
                    project_root=root,
                    input_func=lambda _: next(answers),
                    output_func=lambda _: None,
                )
                result = runner.run()

            self.assertEqual(result["statuses"]["web_reader"], "warning")
            self.assertIn("web_reader", result["warnings"])
            self.assertNotIn("web_reader", result["failed"])

    def test_website_only_failure_stops_before_llm(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "uploads" / "materials" / "项目A").mkdir(parents=True)
            output_dir = root / "outputs" / "materials" / "项目A"
            write_nonempty(output_dir / "website_urls.txt", "https://example.com\n")

            with patch(
                "sem_automation.materials.pipeline.read_website",
                side_effect=RuntimeError("抓取失败"),
            ), patch(
                "sem_automation.materials.pipeline.analyze_project_brief",
            ) as brief_mock:
                result = PipelineRunner(
                    "项目A",
                    project_root=root,
                    output_func=lambda _: None,
                ).run()

            self.assertEqual(result["statuses"]["web_reader"], "failed")
            self.assertEqual(result["statuses"]["sitelink_callouts"], "pending")
            self.assertIn("web_reader", result["failed"])
            brief_mock.assert_not_called()

    def test_no_local_or_website_source_stops_before_llm(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "uploads" / "materials" / "空项目").mkdir(parents=True)

            with patch(
                "sem_automation.materials.pipeline.analyze_project_brief",
            ) as brief_mock:
                result = PipelineRunner(
                    "空项目",
                    project_root=root,
                    output_func=lambda _: None,
                ).run()

            self.assertEqual(result["statuses"]["web_reader"], "skipped")
            self.assertEqual(result["statuses"]["compose_sources"], "failed")
            self.assertIn("compose_sources", result["failed"])
            brief_mock.assert_not_called()

    def test_zero_page_result_with_local_source_degrades_to_warning(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = self.make_project(root)
            self.prepare_initial_outputs(output_dir)
            write_nonempty(output_dir / "website_urls.txt", "https://example.com\n")

            def fake_empty_web(_project_name: str, **_kwargs):
                write_nonempty(
                    output_dir / "website_pages.json",
                    json.dumps({"pages": []}),
                )
                write_nonempty(output_dir / "website_content.md", "成功页面数：0")
                write_nonempty(output_dir / "web_report.csv", "状态\n失败")
                return {"pages": []}

            answers = iter(["1", "1", "1", "2"])
            with patch(
                "sem_automation.materials.pipeline.read_website", side_effect=fake_empty_web
            ):
                result = PipelineRunner(
                    "项目A",
                    project_root=root,
                    input_func=lambda _: next(answers),
                    output_func=lambda _: None,
                ).run()

            self.assertEqual(result["statuses"]["web_reader"], "warning")
            self.assertIn("web_reader", result["warnings"])

    def test_explicit_website_can_create_project_and_reaches_keyword(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "outputs" / "materials" / "售前项目"

            def fake_web(project_name: str, **_kwargs):
                output_dir.mkdir(parents=True, exist_ok=True)
                payload = {
                    "pages": [{
                        "url": "https://example.com/product",
                        "title": "工业相机",
                        "meta_description": "机器视觉产品",
                        "headings": [{"level": "h1", "text": "工业相机"}],
                        "text": "面向制造业的工业相机产品。",
                    }],
                }
                write_nonempty(
                    output_dir / "website_pages.json",
                    json.dumps(payload, ensure_ascii=False),
                )
                write_nonempty(output_dir / "website_content.md", "网站正文")
                write_nonempty(output_dir / "web_report.csv", "状态\n成功")
                return payload

            def fake_brief(_project_name: str, *, project_root):
                write_nonempty(output_dir / "project_brief.md", "项目分析")

            def fake_keyword(_project_name: str, *, project_root):
                write_nonempty(output_dir / "keyword_v1.md", "关键词")

            def fake_sitelink(_project_name: str, *, project_root):
                write_nonempty(output_dir / "sitelink_callouts_raw.md", "原始响应")
                write_nonempty(output_dir / "sitelink_callouts.json", "{}")
                write_nonempty(output_dir / "sitelink_callouts.xlsx", "xlsx")

            with patch(
                "sem_automation.materials.pipeline.read_website", side_effect=fake_web
            ) as web_mock, patch(
                "sem_automation.materials.pipeline.analyze_project_brief", side_effect=fake_brief
            ), patch(
                "sem_automation.materials.pipeline.generate_keyword_v1", side_effect=fake_keyword
            ), patch(
                "sem_automation.materials.pipeline.generate_sitelink_callouts",
                side_effect=fake_sitelink,
            ):
                result = PipelineRunner(
                    "售前项目",
                    project_root=root,
                    website_urls=["https://EXAMPLE.com", "https://example.com"],
                    input_func=lambda _: "1",
                    output_func=lambda _: None,
                ).run()

            self.assertTrue((root / "uploads" / "materials" / "售前项目").is_dir())
            self.assertIn("https://example.com", (output_dir / "website_urls.txt").read_text(encoding="utf-8"))
            raw_text = (output_dir / "raw_text.txt").read_text(encoding="utf-8")
            self.assertIn("客户网站内容", raw_text)
            self.assertIn("工业相机", raw_text)
            self.assertEqual(result["statuses"]["keyword_v1"], "completed")
            self.assertEqual(result["statuses"]["sitelink_callouts"], "completed")
            web_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
