from __future__ import annotations

import argparse
import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import review_driver


def write_file(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")


def create_cycle_artifacts(root: Path) -> tuple[Path, Path, Path]:
    cycle_doc = root / ".spec" / "cycles" / "c01-demo" / "CYCLE.md"
    manifest = root / ".spec" / "cycles" / "manifest.md"
    cycle_index = root / ".spec" / "cycle_index.md"
    write_file(
        cycle_doc,
        "\n".join(
            [
                "# Cycle: Demo",
                "",
                "**Cycle ID**: c01-demo",
                "**Branch**: feat/demo",
                "**Base Branch**: main",
                "**Status**: DRAFT",
                "",
                "## Problem Statement",
                "",
                "Document the feature.",
                "",
            ]
        ),
    )
    write_file(
        manifest,
        "\n".join(
            [
                "# Cycle Manifest",
                "",
                "| Cycle ID | Directory | Branch | Base Branch | Summary | Status |",
                "|---|---|---|---|---|---|",
                "| c01-demo | `.spec/cycles/c01-demo/` | `feat/demo` | `main` | Demo summary | DRAFT |",
                "",
            ]
        ),
    )
    write_file(
        cycle_index,
        "\n".join(
            [
                "# Cycle Index",
                "",
                "| Directory | Status |",
                "|---|---|",
                "| `.spec/cycles/c01-demo/` | DRAFT |",
                "",
            ]
        ),
    )
    return cycle_doc, manifest, cycle_index


def create_investigation_artifact(root: Path) -> Path:
    investigation = root / ".spec" / "bugs" / "b001-demo" / "INVESTIGATION.md"
    write_file(
        investigation,
        "\n".join(
            [
                "# Bug Investigation: Demo",
                "",
                "**Bug ID**: b001-demo",
                "**Status**: DRAFT",
                "**Date**: 2026-04-18",
                "**Target Branch**: main",
                "**Fix Branch**: fix/demo",
                "",
                "## Report",
                "",
                "Initial investigation details.",
                "",
            ]
        ),
    )
    return investigation


def approved_review_result() -> dict[str, object]:
    return {
        "approved": True,
        "summary": "ok",
        "findings": [],
        "advisory_findings": [],
    }


class ReviewDriverTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.previous_cwd = Path.cwd()
        os.chdir(self.root)

        write_file(
            self.root / ".workflow" / "config" / "codex-review.toml",
            "\n".join(
                [
                    'model = "gpt-5.4"',
                    'sandbox = "read-only"',
                    'model_reasoning_effort = "xhigh"',
                    'output_schema = ".workflow/review/codex-review-schema.json"',
                    'prompt_transport = "stdin"',
                    'document_review_mode = "inline-artifact"',
                    'parallel_reviews = 3',
                    'max_review_turns = 10',
                    'blocking_severities = ["critical", "major"]',
                    "",
                ]
            ),
        )
        write_file(self.root / ".workflow" / "review" / "codex-review-schema.json", "{}\n")
        write_file(self.root / "AGENTS.md", "# AGENTS\n")
        write_file(self.root / ".workflow" / "procedures" / "review-loop.md", "# Review Loop\n")
        write_file(self.root / ".workflow" / "procedures" / "plan-tasks.md", "# Plan Tasks Procedure\n")
        write_file(self.root / ".workflow" / "procedures" / "implement.md", "# Implement Procedure\n")

    def tearDown(self) -> None:
        os.chdir(self.previous_cwd)
        self.temp_dir.cleanup()


class LoadReviewConfigTests(ReviewDriverTestCase):
    def test_load_review_config_reads_parallel_settings(self) -> None:
        config = review_driver.load_review_config(self.root)

        self.assertEqual(config["parallel_reviews"], 3)
        self.assertEqual(config["max_review_turns"], 10)
        self.assertEqual(config["blocking_severities"], ["critical", "major"])


class MergeReviewResultsTests(unittest.TestCase):
    def test_merge_review_results_keeps_blocking_and_advisory_separate(self) -> None:
        config = {
            "parallel_reviews": 3,
            "max_review_turns": 10,
            "blocking_severities": ["critical", "major"],
        }
        raw_results = [
            {
                "approved": False,
                "summary": "reviewer one",
                "findings": [
                    {
                        "severity": "major",
                        "title": "Task rule mismatch",
                        "details": "Violates the task requirement.",
                        "location": "task.md:10",
                        "suggested_fix": "Update the implementation.",
                    },
                    {
                        "severity": "minor",
                        "title": "Tiny typo",
                        "details": "Spelling is off.",
                        "location": "task.md:22",
                        "suggested_fix": "Fix the typo.",
                    },
                ],
            },
            {
                "approved": False,
                "summary": "reviewer two",
                "findings": [
                    {
                        "severity": "middle",
                        "title": "Task rule mismatch",
                        "details": "Same underlying issue.",
                        "location": "task.md:10",
                        "suggested_fix": "Update the implementation.",
                    }
                ],
            },
            {"approved": True, "summary": "reviewer three", "findings": []},
        ]

        result = review_driver.merge_review_results(
            raw_results,
            phase="implement",
            artifact_type="implementation-task",
            artifact_path="task.md",
            task_file_path="task.md",
            review_round=1,
            config=config,
            raw_log_paths=[Path("r1.json"), Path("r2.json"), Path("r3.json")],
        )

        self.assertFalse(result["approved"])
        self.assertEqual(len(result["findings"]), 1)
        self.assertEqual(result["findings"][0]["severity"], "major")
        self.assertEqual(result["findings"][0]["support_count"], 2)
        self.assertEqual(result["findings"][0]["reviewer_indexes"], [1, 2])
        self.assertEqual(len(result["advisory_findings"]), 1)
        self.assertEqual(result["advisory_findings"][0]["severity"], "minor")


class PromptConstructionTests(ReviewDriverTestCase):
    def test_plan_tasks_prompt_includes_cycle_doc_and_docs_first_rules(self) -> None:
        cycle_doc, _, _ = create_cycle_artifacts(self.root)
        artifact_path = self.root / ".workflow" / "project_context.md"
        write_file(artifact_path, "# Project Context\n")

        config = review_driver.load_review_config(self.root)
        prompt = review_driver.document_prompt(self.root, "plan-tasks", artifact_path, config, 1)

        self.assertIn(review_driver.read_text_file(cycle_doc), prompt)
        self.assertIn("Review order:", prompt)
        self.assertIn(
            "First, verify compliance with the active cycle CYCLE.md and the other provided workflow references.",
            prompt,
        )
        self.assertIn("Do not report findings or suggested fixes that conflict with the provided documents.", prompt)
        self.assertIn("The artifact complies with the active cycle design and requirements in CYCLE.md.", prompt)

    def test_implementation_prompt_uses_task_file_as_source_of_truth(self) -> None:
        task_path = self.root / ".spec" / "cycles" / "c01-demo" / "tasks" / "impl-001-demo.md"
        write_file(task_path, "# Task\n\n## Done\n\n- done\n")

        config = review_driver.load_review_config(self.root)
        prompt = review_driver.implementation_prompt(self.root, task_path, config, 1)

        self.assertIn("Treat the task file as the source of truth for task-specific requirements in this review.", prompt)
        self.assertIn(
            "First, verify compliance with the task file and the provided workflow references.",
            prompt,
        )
        self.assertIn(
            "If a general review instinct conflicts with the task file, treat the task file as authoritative",
            prompt,
        )
        self.assertIn("Reference: .workflow/procedures/implement.md", prompt)
        self.assertIn(review_driver.read_text_file(task_path), prompt)


class RoundTrackingTests(ReviewDriverTestCase):
    def test_peek_next_round_stops_after_limit(self) -> None:
        payload = {"rounds": {"artifact.md": 9}}

        can_review, next_round, message = review_driver.peek_next_round(payload, "artifact.md", 10)
        self.assertTrue(can_review)
        self.assertEqual(next_round, 10)
        self.assertEqual(message, "")

        review_driver.mark_round_used(payload, "artifact.md", next_round)
        can_review, current_round, message = review_driver.peek_next_round(payload, "artifact.md", 10)
        self.assertFalse(can_review)
        self.assertEqual(current_round, 10)
        self.assertIn("Review turn limit reached", message)

    def test_prepare_resets_existing_review_rounds(self) -> None:
        stale_state = review_driver.state_path(self.root, "opencode", "implement", None)
        review_driver.write_state(
            stale_state,
            {
                "tool": "opencode",
                "phase": "implement",
                "arguments": "wave 1",
                "rounds": {"task.md": 7},
                "approved_hashes": {"artifact.md": "abc123"},
                "approved_snapshots": {"artifact.md": "snapshot"},
                "awaiting_user_approval": True,
            },
        )

        args = argparse.Namespace(tool="opencode", phase="implement", session_id=None, arguments="wave 1")
        with contextlib.redirect_stdout(io.StringIO()):
            result = review_driver.handle_prepare(args)
        payload = review_driver.read_state(stale_state)

        self.assertEqual(result, 0)
        self.assertIsNotNone(payload)
        if payload is None:
            self.fail("prepare did not write state")
        self.assertEqual(payload["rounds"], {})
        self.assertEqual(payload["approved_hashes"], {})
        self.assertEqual(payload["approved_snapshots"], {})
        self.assertFalse(payload["awaiting_user_approval"])


class ApprovalAwareFinishTests(ReviewDriverTestCase):
    def prepare_specify_design_state(self) -> tuple[Path, Path, Path, Path]:
        cycle_doc, manifest, cycle_index = create_cycle_artifacts(self.root)
        state_path = review_driver.state_path(self.root, "opencode", "specify-design", None)
        payload = review_driver.fresh_state_payload(
            self.root,
            "opencode",
            "specify-design",
            None,
            "demo feature",
            self.root / ".workflow" / "config" / "codex-review.toml",
        )
        review_driver.write_state(state_path, payload)
        return cycle_doc, manifest, cycle_index, state_path

    def prepare_investigate_state(self) -> tuple[Path, Path]:
        investigation = create_investigation_artifact(self.root)
        state_path = review_driver.state_path(self.root, "opencode", "investigate", None)
        payload = review_driver.fresh_state_payload(
            self.root,
            "opencode",
            "investigate",
            None,
            "b001-demo",
            self.root / ".workflow" / "config" / "codex-review.toml",
        )
        review_driver.write_state(state_path, payload)
        return investigation, state_path

    def test_specify_design_approved_draft_keeps_state_for_user_approval(self) -> None:
        cycle_doc, manifest, cycle_index, state_path = self.prepare_specify_design_state()

        with mock.patch.object(review_driver, "run_codex_parallel", return_value=(True, approved_review_result(), "")):
            args = argparse.Namespace(tool="opencode", phase="specify-design", session_id=None, hook_event=None)
            result = review_driver.handle_finish(args)

        state = review_driver.read_state(state_path)
        self.assertEqual(result, 0)
        self.assertIsNotNone(state)
        if state is None:
            self.fail("finish did not preserve approval state")
        self.assertTrue(state["awaiting_user_approval"])
        self.assertIn(cycle_doc.as_posix(), state["approved_snapshots"])
        self.assertIn(manifest.as_posix(), state["approved_snapshots"])
        self.assertIn(cycle_index.as_posix(), state["approved_snapshots"])

    def test_specify_design_status_only_finalization_skips_codex_review(self) -> None:
        cycle_doc, manifest, _, state_path = self.prepare_specify_design_state()

        with mock.patch.object(review_driver, "run_codex_parallel", return_value=(True, approved_review_result(), "")):
            args = argparse.Namespace(tool="opencode", phase="specify-design", session_id=None, hook_event=None)
            first_result = review_driver.handle_finish(args)

        write_file(cycle_doc, review_driver.read_text_file(cycle_doc).replace("**Status**: DRAFT", "**Status**: FINALIZED"))
        write_file(manifest, review_driver.read_text_file(manifest).replace("| DRAFT |", "| FINALIZED |"))

        with mock.patch.object(review_driver, "run_codex_parallel") as run_codex_parallel:
            args = argparse.Namespace(tool="opencode", phase="specify-design", session_id=None, hook_event=None)
            second_result = review_driver.handle_finish(args)

        self.assertEqual(first_result, 0)
        self.assertEqual(second_result, 0)
        self.assertFalse(state_path.exists())
        run_codex_parallel.assert_not_called()

    def test_specify_design_finalization_rejects_non_status_changes(self) -> None:
        cycle_doc, manifest, _, state_path = self.prepare_specify_design_state()

        with mock.patch.object(review_driver, "run_codex_parallel", return_value=(True, approved_review_result(), "")):
            args = argparse.Namespace(tool="opencode", phase="specify-design", session_id=None, hook_event=None)
            first_result = review_driver.handle_finish(args)

        write_file(
            cycle_doc,
            review_driver.read_text_file(cycle_doc).replace(
                "Document the feature.",
                "Document the feature with an extra change.",
            ).replace("**Status**: DRAFT", "**Status**: FINALIZED"),
        )
        write_file(manifest, review_driver.read_text_file(manifest).replace("| DRAFT |", "| FINALIZED |"))

        stderr = io.StringIO()
        with mock.patch.object(review_driver, "run_codex_parallel") as run_codex_parallel, contextlib.redirect_stderr(stderr):
            args = argparse.Namespace(tool="opencode", phase="specify-design", session_id=None, hook_event=None)
            second_result = review_driver.handle_finish(args)

        self.assertEqual(first_result, 0)
        self.assertEqual(second_result, 1)
        self.assertTrue(state_path.exists())
        self.assertIn("manual feedback", stderr.getvalue())
        run_codex_parallel.assert_not_called()

    def test_investigate_status_only_finalization_skips_codex_review(self) -> None:
        investigation, state_path = self.prepare_investigate_state()

        with mock.patch.object(review_driver, "run_codex_parallel", return_value=(True, approved_review_result(), "")):
            args = argparse.Namespace(tool="opencode", phase="investigate", session_id=None, hook_event=None)
            first_result = review_driver.handle_finish(args)

        write_file(
            investigation,
            review_driver.read_text_file(investigation).replace("**Status**: DRAFT", "**Status**: FINALIZED"),
        )

        with mock.patch.object(review_driver, "run_codex_parallel") as run_codex_parallel:
            args = argparse.Namespace(tool="opencode", phase="investigate", session_id=None, hook_event=None)
            second_result = review_driver.handle_finish(args)

        self.assertEqual(first_result, 0)
        self.assertEqual(second_result, 0)
        self.assertFalse(state_path.exists())
        run_codex_parallel.assert_not_called()

    def test_plan_tasks_finish_rejects_review_without_cycle_doc_reference(self) -> None:
        cycle_dir = self.root / ".spec" / "cycles" / "c01-demo"
        cycle_dir.mkdir(parents=True, exist_ok=True)
        write_file(
            self.root / ".spec" / "cycle_index.md",
            "\n".join(
                [
                    "# Cycle Index",
                    "",
                    "| Directory | Status |",
                    "|---|---|",
                    "| `.spec/cycles/c01-demo/` | ACTIVE |",
                    "",
                ]
            ),
        )
        write_file(self.root / ".workflow" / "project_context.md", "# Project Context\n")

        state_path = review_driver.state_path(self.root, "opencode", "plan-tasks", None)
        payload = review_driver.fresh_state_payload(
            self.root,
            "opencode",
            "plan-tasks",
            None,
            "plan tasks",
            self.root / ".workflow" / "config" / "codex-review.toml",
        )
        review_driver.write_state(state_path, payload)

        stderr = io.StringIO()
        with mock.patch.object(review_driver, "run_codex_parallel") as run_codex_parallel, contextlib.redirect_stderr(stderr):
            args = argparse.Namespace(tool="opencode", phase="plan-tasks", session_id=None, hook_event=None)
            result = review_driver.handle_finish(args)

        self.assertEqual(result, 1)
        self.assertTrue(state_path.exists())
        self.assertIn("CYCLE.md", stderr.getvalue())
        run_codex_parallel.assert_not_called()


class ReviewTaskTests(ReviewDriverTestCase):
    def test_review_task_uses_session_state_and_records_round(self) -> None:
        task_path = self.root / ".spec" / "cycles" / "c01-demo" / "tasks" / "impl-001-demo.md"
        write_file(task_path, "# Task\n")
        payload = review_driver.fresh_state_payload(
            self.root,
            "claude",
            "implement",
            "session-1",
            task_path.as_posix(),
            self.root / ".workflow" / "config" / "codex-review.toml",
        )
        review_driver.write_state(review_driver.state_path(self.root, "claude", "implement", "session-1"), payload)

        merged_result = {
            "approved": True,
            "summary": "ok",
            "findings": [],
            "advisory_findings": [],
        }

        with mock.patch.object(review_driver, "run_codex_parallel", return_value=(True, merged_result, "")):
            args = argparse.Namespace(tool="claude", task_file=task_path.as_posix(), session_id="session-1")
            with contextlib.redirect_stdout(io.StringIO()):
                result = review_driver.handle_review_task(args)

        state = review_driver.read_state(review_driver.state_path(self.root, "claude", "implement", "session-1"))
        self.assertEqual(result, 0)
        self.assertIsNotNone(state)
        if state is None:
            self.fail("review task did not persist state")
        self.assertEqual(state["rounds"][task_path.as_posix()], 1)


if __name__ == "__main__":
    unittest.main()
