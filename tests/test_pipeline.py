from __future__ import annotations

import json
import tempfile
import unittest

from pathlib import Path
from unittest.mock import patch

import main as main_module
from modules.pipeline_runner import PipelineRunner


def write_nonempty(path: Path, content: str = "test") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class ProjectCollectionTests(unittest.TestCase):
    def test_collect_project_data_is_callable_and_returns_outputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "uploads" / "项目A" / "客户资料.txt"
            write_nonempty(source, "官方网站：example.com")

            with patch.object(main_module, "PROJECT_ROOT", root), patch.object(
                main_module,
                "read_file",
                return_value=("官方网站：example.com", "成功", ""),
            ):
                result = main_module.collect_project_data("项目A")

            output_dir = root / "outputs" / "项目A"
            self.assertEqual(result["project_name"], "项目A")
            self.assertTrue((output_dir / "raw_text.txt").exists())
            self.assertTrue((output_dir / "file_report.csv").exists())
            self.assertTrue((output_dir / "website_urls.txt").exists())

    def test_collect_project_data_rejects_empty_project_name(self):
        with self.assertRaisesRegex(ValueError, "项目名称不能为空"):
            main_module.collect_project_data("  ")


class PipelineRunnerTests(unittest.TestCase):
    def make_project(self, root: Path, project: str = "项目A") -> Path:
        (root / "uploads" / project).mkdir(parents=True)
        output_dir = root / "outputs" / project
        output_dir.mkdir(parents=True)
        return output_dir

    def prepare_initial_outputs(self, output_dir: Path) -> None:
        write_nonempty(output_dir / "raw_text.txt")
        write_nonempty(output_dir / "file_report.csv")
        write_nonempty(output_dir / "project_brief.md")
        write_nonempty(output_dir / "keyword_v1.md")

    def test_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "uploads" / "项目A").mkdir(parents=True)
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

            def fake_brief(project_name: str) -> str:
                self.assertEqual(project_name, "项目A")
                write_nonempty(output_dir / "project_brief.md", "new brief")
                return "new brief"

            with patch(
                "modules.pipeline_runner.analyze_project_brief",
                side_effect=fake_brief,
            ) as mocked:
                runner = PipelineRunner(
                    "项目A",
                    project_root=root,
                    input_func=lambda _: next(answers),
                    output_func=lambda _: None,
                )
                runner.run()

            mocked.assert_called_once_with("项目A")
            self.assertEqual(
                json.loads(
                    (output_dir / "pipeline_status.json").read_text(encoding="utf-8")
                )["steps"]["project_brief"]["status"],
                "completed",
            )

    def test_website_failure_is_not_treated_as_no_website(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = self.make_project(root)
            self.prepare_initial_outputs(output_dir)
            write_nonempty(output_dir / "website_urls.txt", "https://example.com\n")
            answers = iter(["1", "1", "1", "1"])

            with patch(
                "modules.pipeline_runner.read_website",
                side_effect=RuntimeError("抓取失败"),
            ):
                runner = PipelineRunner(
                    "项目A",
                    project_root=root,
                    input_func=lambda _: next(answers),
                    output_func=lambda _: None,
                )
                result = runner.run()

            self.assertEqual(result["statuses"]["web_reader"], "failed")
            self.assertEqual(result["statuses"]["sitelink_callouts"], "pending")
            self.assertIn("web_reader", result["failed"])


if __name__ == "__main__":
    unittest.main()
