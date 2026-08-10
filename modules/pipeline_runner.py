from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from main import collect_project_data
from modules.ad_copy_generator import generate_ad_copy
from modules.ai_analyzer import analyze_project_brief
from modules.keyword_analyzer import generate_keyword_v1
from modules.keyword_v2_builder import clean_wordstat_results
from modules.negative_keyword_analyzer import generate_negative_keywords
from modules.sitelink_callout_generator import generate_sitelink_callouts
from modules.web_reader import read_website
from modules.website_url_extractor import resolve_website_urls_path
from modules.wordstat_query_exporter import export as export_wordstat_queries


VALID_STATUSES = {
    "pending",
    "running",
    "completed",
    "skipped",
    "failed",
    "waiting_for_human",
}


@dataclass
class PipelineStep:
    name: str
    title: str
    requires: list[Path]
    outputs: list[Path]
    runner: Callable[[], object]


class PipelineRunner:
    """按文件依赖调度现有 SEM 业务模块。"""

    def __init__(
        self,
        project_name: str,
        *,
        project_root: Path | None = None,
        input_func: Callable[[str], str] = input,
        output_func: Callable[[str], None] = print,
        dry_run: bool = False,
    ) -> None:
        self.project_name = (project_name or "").strip()
        if not self.project_name:
            raise ValueError("项目名称不能为空。")

        self.project_root = project_root or Path(__file__).resolve().parent.parent
        self.upload_dir = self.project_root / "uploads" / self.project_name
        self.output_dir = self.project_root / "outputs" / self.project_name
        self.status_path = self.output_dir / "pipeline_status.json"
        self.input = input_func
        self.print = output_func
        self.dry_run = dry_run
        self.stop_requested = False
        self.website_branch_finished = False
        self.state = self._load_state() if not dry_run else self._empty_state()

    def _empty_state(self) -> dict:
        return {
            "project": self.project_name,
            "updated_at": self._now(),
            "steps": {},
        }

    @staticmethod
    def _now() -> str:
        return datetime.now().astimezone().isoformat(timespec="seconds")

    def _load_state(self) -> dict:
        if not self.status_path.exists():
            return self._empty_state()

        try:
            state = json.loads(self.status_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self._empty_state()

        if not isinstance(state, dict) or state.get("project") != self.project_name:
            return self._empty_state()

        state.setdefault("steps", {})
        return state

    def _update_status(self, step_name: str, status: str, message: str) -> None:
        if status not in VALID_STATUSES:
            raise ValueError(f"未知 Pipeline 状态：{status}")
        if self.dry_run:
            return

        self.state["project"] = self.project_name
        self.state["updated_at"] = self._now()
        self.state.setdefault("steps", {})[step_name] = {
            "status": status,
            "message": message,
            "updated_at": self._now(),
        }

        self.output_dir.mkdir(parents=True, exist_ok=True)
        temp_path = self.status_path.with_suffix(".json.tmp")
        temp_path.write_text(
            json.dumps(self.state, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temp_path.replace(self.status_path)

    @staticmethod
    def _valid_file(path: Path) -> bool:
        return path.is_file() and path.stat().st_size > 0

    def _all_outputs_exist(self, step: PipelineStep) -> bool:
        return bool(step.outputs) and all(self._valid_file(path) for path in step.outputs)

    def _missing_requirements(self, step: PipelineStep) -> list[Path]:
        return [path for path in step.requires if not self._valid_file(path)]

    def _ask_choice(self, prompt: str, valid: set[str], default: str) -> str:
        while True:
            try:
                choice = self.input(prompt).strip()
            except EOFError:
                self.print(f"未检测到交互输入，采用默认选项：{default}")
                return default
            if not choice:
                choice = default
            if choice in valid:
                return choice
            self.print(f"请输入以下选项之一：{', '.join(sorted(valid))}")

    def _confirm_existing(self, step: PipelineStep) -> str:
        self.print(f"\n[{step.title}] 已存在输出：")
        for path in step.outputs:
            self.print(f"- {path}")
        self.print("1. 跳过，保留现有结果")
        self.print("2. 重新运行并覆盖")
        self.print("3. 停止 Pipeline")
        return self._ask_choice("请选择 [1/2/3，默认1]：", {"1", "2", "3"}, "1")

    def _run_step(self, step: PipelineStep) -> bool:
        if self.stop_requested:
            return False

        if self._all_outputs_exist(step):
            choice = self._confirm_existing(step)
            if choice == "1":
                self._update_status(step.name, "skipped", "用户选择保留现有输出")
                return True
            if choice == "3":
                self.stop_requested = True
                self.print("Pipeline 已按用户选择停止。")
                return False

        missing = self._missing_requirements(step)
        if missing:
            message = "缺少输入：" + "；".join(str(path) for path in missing)
            self._update_status(step.name, "pending", message)
            self.print(f"\n[{step.title}] 暂不能运行，{message}")
            return False

        self.print(f"\n===== {step.title} =====")
        self._update_status(step.name, "running", "正在运行")
        try:
            step.runner()
            missing_outputs = [path for path in step.outputs if not self._valid_file(path)]
            if missing_outputs:
                missing_text = "；".join(str(path) for path in missing_outputs)
                raise RuntimeError(f"步骤结束后未生成有效输出：{missing_text}")
        except Exception as error:
            self._update_status(step.name, "failed", str(error))
            self.print(f"[{step.title}] 运行失败：{error}")
            return False

        self._update_status(step.name, "completed", "运行完成")
        self.print(f"[{step.title}] 已完成。")
        return True

    def _checkpoint(
        self,
        name: str,
        title: str,
        candidates: list[Path],
        instruction: str,
    ) -> Path | None:
        for path in candidates:
            if self._valid_file(path):
                self._update_status(name, "completed", f"已检测到人工文件：{path.name}")
                return path

        expected = " 或 ".join(str(path) for path in candidates)
        self._update_status(name, "waiting_for_human", f"等待人工文件：{expected}")
        self.print(f"\n===== 人工断点：{title} =====")
        self.print(instruction)
        self.print("请保存为：")
        for path in candidates:
            self.print(f"- {path}")
        return None

    def _offer_independent_branch(self) -> None:
        if self.website_branch_finished or self.stop_requested:
            return

        self.print("\n当前仍可运行的独立分支：")
        self.print("- 网页读取")
        self.print("- Sitelink / Callout 生成")
        self.print("1. 继续运行上述独立分支")
        self.print("2. 现在停止")
        choice = self._ask_choice("请选择 [1/2，默认2]：", {"1", "2"}, "2")
        if choice == "1":
            self._run_website_branch()
        else:
            self.stop_requested = True
            self.print("Pipeline 已停在人工断点，可在准备好文件后重新运行。")

    def _website_steps(self) -> tuple[PipelineStep, PipelineStep]:
        web_step = PipelineStep(
            name="web_reader",
            title="读取客户网站",
            requires=[],
            outputs=[
                self.output_dir / "website_pages.json",
                self.output_dir / "website_content.md",
                self.output_dir / "web_report.csv",
            ],
            runner=lambda: read_website(self.project_name),
        )
        sitelink_step = PipelineStep(
            name="sitelink_callouts",
            title="生成 Sitelink / Callout",
            requires=[self.output_dir / "project_brief.md"],
            outputs=[
                self.output_dir / "sitelink_callouts_raw.md",
                self.output_dir / "sitelink_callouts.json",
                self.output_dir / "sitelink_callouts.xlsx",
            ],
            runner=lambda: generate_sitelink_callouts(self.project_name),
        )
        return web_step, sitelink_step

    def _run_website_branch(self) -> bool:
        if self.website_branch_finished:
            return True

        web_step, sitelink_step = self._website_steps()
        url_path, _ = resolve_website_urls_path(self.project_root, self.project_name)

        if url_path is None:
            self.print("\n客户资料未提供网站，网页读取步骤正常跳过。")
            self._update_status("web_reader", "skipped", "客户资料未提供网站")
            web_ok = True
        else:
            web_ok = self._run_step(web_step)

        if self.stop_requested:
            return False

        if not web_ok and url_path is not None:
            self._update_status(
                "sitelink_callouts",
                "pending",
                "存在客户网站，但网页读取未完成",
            )
            self.website_branch_finished = True
            return False

        sitelink_ok = self._run_step(sitelink_step)
        self.website_branch_finished = True
        return sitelink_ok

    def _automatic_steps(self) -> dict[str, PipelineStep]:
        return {
            "collect_sources": PipelineStep(
                name="collect_sources",
                title="读取客户资料",
                requires=[],
                outputs=[
                    self.output_dir / "raw_text.txt",
                    self.output_dir / "file_report.csv",
                ],
                runner=lambda: collect_project_data(self.project_name),
            ),
            "project_brief": PipelineStep(
                name="project_brief",
                title="生成项目分析",
                requires=[self.output_dir / "raw_text.txt"],
                outputs=[self.output_dir / "project_brief.md"],
                runner=lambda: analyze_project_brief(self.project_name),
            ),
            "keyword_v1": PipelineStep(
                name="keyword_v1",
                title="生成第一版关键词",
                requires=[
                    self.output_dir / "raw_text.txt",
                    self.output_dir / "project_brief.md",
                ],
                outputs=[self.output_dir / "keyword_v1.md"],
                runner=lambda: generate_keyword_v1(self.project_name),
            ),
            "wordstat_export": PipelineStep(
                name="wordstat_export",
                title="导出 Wordstat 查询词",
                requires=[self.output_dir / "keyword_v1_reviewed.md"],
                outputs=[self.output_dir / "wordstat_query_list.txt"],
                runner=lambda: export_wordstat_queries(
                    self.output_dir / "keyword_v1_reviewed.md",
                    self.output_dir / "wordstat_query_list.txt",
                ),
            ),
            "wordstat_clean": PipelineStep(
                name="wordstat_clean",
                title="清洗 Wordstat 查询结果",
                requires=[self.output_dir / "wordstat_results_manual.txt"],
                outputs=[self.output_dir / "wordstat_results_cleaned.tsv"],
                runner=lambda: clean_wordstat_results(
                    self.output_dir / "wordstat_results_manual.txt",
                    self.output_dir / "wordstat_results_cleaned.tsv",
                ),
            ),
            "negative_keywords": PipelineStep(
                name="negative_keywords",
                title="生成否定关键词",
                requires=[
                    self.output_dir / "raw_text.txt",
                    self.output_dir / "project_brief.md",
                ],
                outputs=[self.output_dir / "negative_keywords.md"],
                runner=lambda: generate_negative_keywords(
                    self.project_name,
                    keyword_version=self._find_keyword_v2().name,
                ),
            ),
            "ad_copy": PipelineStep(
                name="ad_copy",
                title="生成广告文案",
                requires=[
                    self.output_dir / "project_brief.md",
                    self.output_dir / "negative_keywords.md",
                ],
                outputs=[
                    self.output_dir / "ad_copy_results.tsv",
                    self.output_dir / "ad_copy_results.xlsx",
                    self.output_dir / "ad_copy_raw.md",
                ],
                runner=lambda: generate_ad_copy(self.project_name),
            ),
        }

    def _find_keyword_v2(self) -> Path | None:
        for name in ("keyword_v2.xlsx", "keywords_v2.xlsx"):
            path = self.output_dir / name
            if self._valid_file(path):
                return path
        return None

    def _preview(self) -> dict:
        self.print(f"\nSEM Pipeline 预览：{self.project_name}")
        self.print("dry-run 不调用 API、不执行网页请求、不写入任何文件。\n")
        rows = [
            ("读取客户资料", "自动", "raw_text.txt / file_report.csv"),
            ("生成项目分析", "自动/API", "project_brief.md"),
            ("生成第一版关键词", "自动/API", "keyword_v1.md"),
            ("关键词初稿审核", "人工", "keyword_v1_reviewed.md"),
            ("导出 Wordstat 查询词", "自动", "wordstat_query_list.txt"),
            ("Wordstat 查询", "人工", "wordstat_results_manual.txt"),
            ("清洗 Wordstat 结果", "自动", "wordstat_results_cleaned.tsv"),
            ("关键词筛选和分组", "人工", "keyword_v2.xlsx / keywords_v2.xlsx"),
            ("生成否定关键词", "自动/API", "negative_keywords.md"),
            ("生成广告文案", "自动/API", "ad_copy_results.*"),
            ("读取客户网站", "条件自动/网络", "website_* / web_report.csv"),
            ("生成 Sitelink / Callout", "自动/API", "sitelink_callouts.*"),
        ]
        for index, (title, kind, output) in enumerate(rows, start=1):
            self.print(f"{index:>2}. [{kind}] {title} → {output}")

        missing_checkpoints = []
        if not self._valid_file(self.output_dir / "keyword_v1_reviewed.md"):
            missing_checkpoints.append("keyword_v1_reviewed.md")
        if not self._valid_file(self.output_dir / "wordstat_results_manual.txt"):
            missing_checkpoints.append("wordstat_results_manual.txt")
        if self._find_keyword_v2() is None:
            missing_checkpoints.append("keyword_v2.xlsx / keywords_v2.xlsx")

        if missing_checkpoints:
            self.print("\n当前缺少的人工文件：")
            for name in missing_checkpoints:
                self.print(f"- {name}")
        else:
            self.print("\n三个主要人工断点文件均已准备。")

        return {"project": self.project_name, "dry_run": True, "missing": missing_checkpoints}

    def run(self) -> dict:
        if not self.upload_dir.exists() or not self.upload_dir.is_dir():
            raise FileNotFoundError(f"项目不存在：{self.upload_dir}")

        if self.dry_run:
            return self._preview()

        self.print(f"\nSEM Pipeline 启动：{self.project_name}")
        steps = self._automatic_steps()

        if not self._run_step(steps["collect_sources"]):
            return self._finish()
        if not self._run_step(steps["project_brief"]):
            self._offer_independent_branch()
            return self._finish()
        if not self._run_step(steps["keyword_v1"]):
            self._offer_independent_branch()
            return self._finish()

        reviewed_path = self._checkpoint(
            "keyword_review",
            "关键词初稿审核",
            [self.output_dir / "keyword_v1_reviewed.md"],
            "请审核 keyword_v1.md，并删除或修改不适合的关键词。",
        )
        if reviewed_path is None:
            self._offer_independent_branch()
            return self._finish()

        if not self._run_step(steps["wordstat_export"]):
            self._offer_independent_branch()
            return self._finish()

        manual_wordstat = self._checkpoint(
            "wordstat_manual",
            "Wordstat 人工查询",
            [self.output_dir / "wordstat_results_manual.txt"],
            "请使用 wordstat_query_list.txt 查询搜索量，并保存人工查询结果。",
        )
        if manual_wordstat is None:
            self._offer_independent_branch()
            return self._finish()

        if not self._run_step(steps["wordstat_clean"]):
            self._offer_independent_branch()
            return self._finish()

        keyword_v2 = self._checkpoint(
            "keyword_v2_review",
            "关键词筛选和广告组划分",
            [
                self.output_dir / "keyword_v2.xlsx",
                self.output_dir / "keywords_v2.xlsx",
            ],
            "请根据 wordstat_results_cleaned.tsv 筛选关键词，并完成人工 Campaign / AdGroup 分组。",
        )
        if keyword_v2 is None:
            self._offer_independent_branch()
            return self._finish()

        if not self._run_step(steps["negative_keywords"]):
            self._offer_independent_branch()
            return self._finish()
        if not self._run_step(steps["ad_copy"]):
            self._offer_independent_branch()
            return self._finish()

        self._run_website_branch()
        return self._finish()

    def _finish(self) -> dict:
        statuses = {
            name: data.get("status", "pending")
            for name, data in self.state.get("steps", {}).items()
        }
        waiting = [name for name, status in statuses.items() if status == "waiting_for_human"]
        failed = [name for name, status in statuses.items() if status == "failed"]

        self.print("\n===== Pipeline 本次运行结束 =====")
        if waiting:
            self.print("等待人工处理：" + "、".join(waiting))
        if failed:
            self.print("运行失败步骤：" + "、".join(failed))
        if not waiting and not failed and not self.stop_requested:
            self.print("当前可执行步骤均已处理完成。")
        self.print(f"状态文件：{self.status_path}")

        return {
            "project": self.project_name,
            "stopped": self.stop_requested,
            "waiting": waiting,
            "failed": failed,
            "statuses": statuses,
            "status_path": self.status_path,
        }


def run_pipeline(
    project_name: str,
    *,
    dry_run: bool = False,
    input_func: Callable[[str], str] = input,
    output_func: Callable[[str], None] = print,
) -> dict:
    runner = PipelineRunner(
        project_name,
        dry_run=dry_run,
        input_func=input_func,
        output_func=output_func,
    )
    return runner.run()
