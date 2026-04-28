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


def merged_review_result(findings: list[dict[str, object]]) -> dict[str, object]:
    return {
        "approved": len(findings) == 0,
        "summary": "Round 1/10: 3 reviewers completed, 1 blocking findings, 0 advisory findings.",
        "phase": "implement",
        "artifact_type": "implementation-task",
        "artifact_path": "artifact.md",
        "task_file_path": "artifact.md",
        "review_round": 1,
        "max_review_turns": 10,
        "parallel_reviews": 3,
        "blocking_severities": ["critical", "major"],
        "findings": findings,
        "advisory_findings": [],
        "reviewers": [{"reviewer_index": 1}, {"reviewer_index": 2}, {"reviewer_index": 3}],
        "raw_log_paths": ["r1.json", "r2.json", "r3.json"],
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
                    'output_schema = ".workflow/review/codex-review-schema.json"',
                    'prompt_transport = "stdin"',
                    'document_review_mode = "inline-artifact"',
                    'parallel_reviews = 3',
                    'max_review_turns = 10',
                    'blocking_severities = ["critical", "major"]',
                    '',
                    '[[reviewer_profiles]]',
                    'label = "baseline-high"',
                    'model_reasoning_effort = "high"',
                    '',
                    '[[reviewer_profiles]]',
                    'label = "baseline-xhigh"',
                    'model_reasoning_effort = "xhigh"',
                    '',
                    '[[reviewer_profiles]]',
                    'label = "edge-state-verify-high"',
                    'model_reasoning_effort = "high"',
                    'document_prompt_lens = "Prioritize edge-case workflow violations and verify completeness first."',
                    'implementation_prompt_lens = "Prioritize invalid state transitions and done-condition evidence first."',
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
    def test_load_review_config_reads_parallel_settings_and_profiles(self) -> None:
        config = review_driver.load_review_config(self.root)

        self.assertEqual(config["parallel_reviews"], 3)
        self.assertEqual(config["max_review_turns"], 10)
        self.assertEqual(config["blocking_severities"], ["critical", "major"])
        self.assertEqual(
            [profile["label"] for profile in config["reviewer_profiles"]],
            ["baseline-high", "baseline-xhigh", "edge-state-verify-high"],
        )
        self.assertEqual(
            [profile["model_reasoning_effort"] for profile in config["reviewer_profiles"]],
            ["high", "xhigh", "high"],
        )

    def test_load_review_config_falls_back_to_top_level_effort(self) -> None:
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
                    '',
                ]
            ),
        )

        config = review_driver.load_review_config(self.root)

        self.assertEqual(config["model_reasoning_effort"], "xhigh")
        self.assertEqual(len(config["reviewer_profiles"]), 3)
        self.assertEqual(
            [profile["label"] for profile in config["reviewer_profiles"]],
            ["reviewer-1", "reviewer-2", "reviewer-3"],
        )
        self.assertTrue(all(profile["model_reasoning_effort"] == "xhigh" for profile in config["reviewer_profiles"]))

    def test_load_review_config_rejects_profile_count_mismatch(self) -> None:
        write_file(
            self.root / ".workflow" / "config" / "codex-review.toml",
            "\n".join(
                [
                    'model = "gpt-5.4"',
                    'sandbox = "read-only"',
                    'output_schema = ".workflow/review/codex-review-schema.json"',
                    'prompt_transport = "stdin"',
                    'document_review_mode = "inline-artifact"',
                    'parallel_reviews = 3',
                    'max_review_turns = 10',
                    'blocking_severities = ["critical", "major"]',
                    '',
                    '[[reviewer_profiles]]',
                    'label = "baseline-high"',
                    'model_reasoning_effort = "high"',
                    '',
                    '[[reviewer_profiles]]',
                    'label = "baseline-xhigh"',
                    'model_reasoning_effort = "xhigh"',
                    '',
                ]
            ),
        )

        with self.assertRaisesRegex(ValueError, "parallel_reviews"):
            review_driver.load_review_config(self.root)


class BuildCodexCommandTests(ReviewDriverTestCase):
    def test_build_codex_command_uses_reviewer_profile_effort(self) -> None:
        config = review_driver.load_review_config(self.root)
        commands = [
            review_driver.build_codex_command("codex", config, Path("review.json"), profile)
            for profile in config["reviewer_profiles"]
        ]

        self.assertIn('model_reasoning_effort="high"', commands[0])
        self.assertIn('model_reasoning_effort="xhigh"', commands[1])
        self.assertIn('model_reasoning_effort="high"', commands[2])


class MergeReviewResultsTests(unittest.TestCase):
    def test_merge_review_results_keeps_blocking_and_advisory_separate(self) -> None:
        config = {
            "parallel_reviews": 3,
            "max_review_turns": 10,
            "blocking_severities": ["critical", "major"],
        }
        reviewer_profiles = [
            {
                "label": "baseline-high",
                "model_reasoning_effort": "high",
                "document_prompt_lens": None,
                "implementation_prompt_lens": None,
            },
            {
                "label": "baseline-xhigh",
                "model_reasoning_effort": "xhigh",
                "document_prompt_lens": None,
                "implementation_prompt_lens": None,
            },
            {
                "label": "edge-state-verify-high",
                "model_reasoning_effort": "high",
                "document_prompt_lens": "document lens",
                "implementation_prompt_lens": "implementation lens",
            },
        ]
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
            reviewer_profiles=reviewer_profiles,
        )

        self.assertFalse(result["approved"])
        self.assertEqual(len(result["findings"]), 1)
        self.assertEqual(result["findings"][0]["severity"], "major")
        self.assertEqual(result["findings"][0]["support_count"], 2)
        self.assertEqual(result["findings"][0]["reviewer_indexes"], [1, 2])
        self.assertEqual(len(result["advisory_findings"]), 1)
        self.assertEqual(result["advisory_findings"][0]["severity"], "minor")
        self.assertEqual(result["reviewers"][1]["label"], "baseline-xhigh")
        self.assertEqual(result["reviewers"][1]["model_reasoning_effort"], "xhigh")
        self.assertEqual(result["reviewers"][2]["document_prompt_lens"], "document lens")
        self.assertEqual(result["reviewers"][2]["implementation_prompt_lens"], "implementation lens")


class PromptConstructionTests(ReviewDriverTestCase):
    def test_specify_design_prompt_includes_draft_status_rules(self) -> None:
        cycle_doc, _, _ = create_cycle_artifacts(self.root)

        config = review_driver.load_review_config(self.root)
        reviewer_requests = review_driver.build_document_reviewer_requests(self.root, "specify-design", cycle_doc, config, 1)
        prompt = reviewer_requests[0]["prompt"]

        self.assertIn("Status transition rules:", prompt)
        self.assertIn(
            "During specify-design content review, `CYCLE.md` and the matching `manifest.md` row are expected to remain `DRAFT` until explicit user approval.",
            prompt,
        )
        self.assertIn(
            "The post-approval `DRAFT` to `FINALIZED` change is validated separately and is not part of the normal content review-gate loop.",
            prompt,
        )

    def test_plan_tasks_prompt_includes_cycle_doc_docs_first_rules_and_document_lens(self) -> None:
        cycle_doc, _, _ = create_cycle_artifacts(self.root)
        artifact_path = self.root / ".workflow" / "project_context.md"
        write_file(artifact_path, "# Project Context\n")

        config = review_driver.load_review_config(self.root)
        reviewer_requests = review_driver.build_document_reviewer_requests(self.root, "plan-tasks", artifact_path, config, 1)
        prompt = reviewer_requests[2]["prompt"]

        self.assertIn(review_driver.read_text_file(cycle_doc), prompt)
        self.assertIn("Review order:", prompt)
        self.assertIn(
            "First, verify compliance with the active cycle CYCLE.md and the other provided workflow references.",
            prompt,
        )
        self.assertIn(
            "During planning review, newly generated task files and `dependencies.md` rows are expected to remain `PENDING` until `/implement` starts.",
            prompt,
        )
        self.assertIn(
            "Do not require `ACTIVE` or `DONE` during `plan-tasks` or `fix-tasks` review just because the artifacts appear complete.",
            prompt,
        )
        self.assertIn("Do not report findings or suggested fixes that conflict with the provided documents.", prompt)
        self.assertIn("The artifact complies with the active cycle design and requirements in CYCLE.md.", prompt)
        self.assertNotIn("Priority review lens:", reviewer_requests[0]["prompt"])
        self.assertNotIn("Priority review lens:", reviewer_requests[1]["prompt"])
        self.assertIn("Priority review lens:", prompt)
        self.assertIn(config["reviewer_profiles"][2]["document_prompt_lens"], prompt)

    def test_implementation_prompt_uses_task_file_as_source_of_truth_and_implementation_lens(self) -> None:
        task_path = self.root / ".spec" / "cycles" / "c01-demo" / "tasks" / "impl-001-demo.md"
        write_file(task_path, "# Task\n\n## Done\n\n- done\n")

        config = review_driver.load_review_config(self.root)
        reviewer_requests = review_driver.build_implementation_reviewer_requests(self.root, task_path, config, 1)
        prompt = reviewer_requests[2]["prompt"]

        self.assertIn("Treat the task file as the source of truth for task-specific requirements in this review.", prompt)
        self.assertIn(
            "First, verify compliance with the task file and the provided workflow references.",
            prompt,
        )
        self.assertIn(
            "If a general review instinct conflicts with the task file, treat the task file as authoritative",
            prompt,
        )
        self.assertIn("During `review-task`, the task file and its matching `dependencies.md` row are expected to remain `ACTIVE`.", prompt)
        self.assertIn("Do not require `DONE` before review passes and the relevant verification is rerun.", prompt)
        self.assertIn("Reference: .workflow/procedures/implement.md", prompt)
        self.assertIn(review_driver.read_text_file(task_path), prompt)
        self.assertNotIn("Priority review lens:", reviewer_requests[0]["prompt"])
        self.assertNotIn("Priority review lens:", reviewer_requests[1]["prompt"])
        self.assertIn("Priority review lens:", prompt)
        self.assertIn(config["reviewer_profiles"][2]["implementation_prompt_lens"], prompt)


class PrematureStatusFindingSuppressionTests(ReviewDriverTestCase):
    def test_suppresses_premature_specify_design_finalization_finding(self) -> None:
        cycle_doc, _, _ = create_cycle_artifacts(self.root)
        result = merged_review_result(
            [
                {
                    "severity": "major",
                    "title": "Finalize the draft",
                    "details": "The status should be FINALIZED before the review can pass.",
                    "location": cycle_doc.as_posix(),
                    "suggested_fix": "Set the document status to FINALIZED.",
                }
            ]
        )

        updated = review_driver.suppress_premature_status_findings(result, "specify-design", "document", cycle_doc)

        self.assertTrue(updated["approved"])
        self.assertEqual(updated["findings"], [])
        self.assertIn("0 blocking findings", updated["summary"])

    def test_suppresses_premature_done_finding_during_implementation_review(self) -> None:
        task_path = self.root / ".spec" / "cycles" / "c01-demo" / "tasks" / "impl-001-demo.md"
        write_file(task_path, "Status: `ACTIVE`\n\n# Task\n")
        result = merged_review_result(
            [
                {
                    "severity": "major",
                    "title": "Mark task done now",
                    "details": "The task should be DONE before this review passes.",
                    "location": task_path.as_posix(),
                    "suggested_fix": "Mark the task DONE.",
                }
            ]
        )

        updated = review_driver.suppress_premature_status_findings(result, "implement", "implementation-task", task_path)

        self.assertTrue(updated["approved"])
        self.assertEqual(updated["findings"], [])
        self.assertIn("0 blocking findings", updated["summary"])

    def test_keeps_real_status_mismatch_finding(self) -> None:
        task_path = self.root / ".spec" / "cycles" / "c01-demo" / "tasks" / "impl-001-demo.md"
        write_file(task_path, "Status: `PENDING`\n\n# Task\n")
        result = merged_review_result(
            [
                {
                    "severity": "major",
                    "title": "Task never entered active state",
                    "details": "The task should be ACTIVE before implementation review starts.",
                    "location": task_path.as_posix(),
                    "suggested_fix": "Set the task status to ACTIVE before review.",
                }
            ]
        )

        updated = review_driver.suppress_premature_status_findings(result, "implement", "implementation-task", task_path)

        self.assertFalse(updated["approved"])
        self.assertEqual(len(updated["findings"]), 1)


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
                "interface": "opencode",
                "phase": "implement",
                "arguments": "wave 1",
                "rounds": {"task.md": 7},
                "approved_hashes": {"artifact.md": "abc123"},
                "approved_snapshots": {"artifact.md": "snapshot"},
                "awaiting_user_approval": True,
            },
        )

        args = argparse.Namespace(interface="opencode", phase="implement", session_id=None, arguments="wave 1")
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
            args = argparse.Namespace(interface="opencode", phase="specify-design", session_id=None, hook_event=None)
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
            args = argparse.Namespace(interface="opencode", phase="specify-design", session_id=None, hook_event=None)
            first_result = review_driver.handle_finish(args)

        write_file(cycle_doc, review_driver.read_text_file(cycle_doc).replace("**Status**: DRAFT", "**Status**: FINALIZED"))
        write_file(manifest, review_driver.read_text_file(manifest).replace("| DRAFT |", "| FINALIZED |"))

        with mock.patch.object(review_driver, "run_codex_parallel") as run_codex_parallel:
            args = argparse.Namespace(interface="opencode", phase="specify-design", session_id=None, hook_event=None)
            second_result = review_driver.handle_finish(args)

        self.assertEqual(first_result, 0)
        self.assertEqual(second_result, 0)
        self.assertFalse(state_path.exists())
        run_codex_parallel.assert_not_called()

    def test_specify_design_finalization_rejects_non_status_changes(self) -> None:
        cycle_doc, manifest, _, state_path = self.prepare_specify_design_state()

        with mock.patch.object(review_driver, "run_codex_parallel", return_value=(True, approved_review_result(), "")):
            args = argparse.Namespace(interface="opencode", phase="specify-design", session_id=None, hook_event=None)
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
            args = argparse.Namespace(interface="opencode", phase="specify-design", session_id=None, hook_event=None)
            second_result = review_driver.handle_finish(args)

        self.assertEqual(first_result, 0)
        self.assertEqual(second_result, 1)
        self.assertTrue(state_path.exists())
        self.assertIn("manual feedback", stderr.getvalue())
        run_codex_parallel.assert_not_called()

    def test_investigate_status_only_finalization_skips_codex_review(self) -> None:
        investigation, state_path = self.prepare_investigate_state()

        with mock.patch.object(review_driver, "run_codex_parallel", return_value=(True, approved_review_result(), "")):
            args = argparse.Namespace(interface="opencode", phase="investigate", session_id=None, hook_event=None)
            first_result = review_driver.handle_finish(args)

        write_file(
            investigation,
            review_driver.read_text_file(investigation).replace("**Status**: DRAFT", "**Status**: FINALIZED"),
        )

        with mock.patch.object(review_driver, "run_codex_parallel") as run_codex_parallel:
            args = argparse.Namespace(interface="opencode", phase="investigate", session_id=None, hook_event=None)
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
            args = argparse.Namespace(interface="opencode", phase="plan-tasks", session_id=None, hook_event=None)
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
            args = argparse.Namespace(interface="claude", task_file=task_path.as_posix(), session_id="session-1")
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
