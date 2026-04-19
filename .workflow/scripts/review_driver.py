#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any, cast


PHASES = {
    "specify-design",
    "plan-tasks",
    "implement",
    "investigate",
    "fix-tasks",
}

FINISH_PHASES = ["specify-design", "plan-tasks", "investigate", "fix-tasks"]
REVIEW_CONFIG_PATH = Path(".workflow") / "config" / "codex-review.toml"
SUPPORTED_PROMPT_TRANSPORTS = {"stdin"}
SUPPORTED_DOCUMENT_REVIEW_MODES = {"inline-artifact"}
DEFAULT_PARALLEL_REVIEWS = 3
DEFAULT_MAX_REVIEW_TURNS = 10
DEFAULT_BLOCKING_SEVERITIES = ["critical", "major"]
SEVERITY_ORDER = {
    "critical": 0,
    "major": 1,
    "middle": 2,
    "minor": 3,
}
APPROVAL_GATED_PHASES = {"specify-design", "investigate"}
DOCUMENT_DRAFT_STATUS_RE = re.compile(
    r"^(?P<prefix>\*\*Status\*\*:[ \t]*)(?P<quote>`?)(?P<status>DRAFT)(?P=quote)[ \t]*$",
    re.MULTILINE,
)


def eprint(message: str) -> None:
    print(message, file=sys.stderr)


def read_stdin_json() -> dict[str, Any]:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def find_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".workflow").exists():
            return candidate
    raise SystemExit("Could not locate repository root containing .workflow/")


def ensure_logs_dir(root: Path) -> Path:
    path = root / "logs" / "reviews"
    path.mkdir(parents=True, exist_ok=True)
    return path


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    return cleaned.strip("-") or "default"


def state_path(root: Path, tool: str, phase: str, session_id: str | None) -> Path:
    suffix = f"-{slugify(session_id)}" if session_id else ""
    return ensure_logs_dir(root) / f"{tool}-{phase}{suffix}.state.json"


def log_path(root: Path, tool: str, phase: str, session_id: str | None) -> Path:
    suffix = f"-{slugify(session_id)}" if session_id else ""
    return ensure_logs_dir(root) / f"{tool}-{phase}{suffix}.json"


def reviewer_output_path(output_path: Path, reviewer_index: int) -> Path:
    return output_path.parent / f"{output_path.stem}.reviewer-{reviewer_index}.json"


def read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def read_bytes_file(path: Path) -> bytes:
    return path.read_bytes()


def write_json_file(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def require_string(config: dict[str, Any], key: str) -> str:
    value = config.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Review config key '{key}' must be a non-empty string.")
    return value.strip()


def require_positive_int(config: dict[str, Any], key: str, default: int) -> int:
    value = config.get(key, default)
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"Review config key '{key}' must be a positive integer.")
    return value


def require_severity_list(config: dict[str, Any], key: str, default: list[str]) -> list[str]:
    value = config.get(key, default)
    if not isinstance(value, list) or not value:
        raise ValueError(f"Review config key '{key}' must be a non-empty list of severities.")

    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"Review config key '{key}' must contain only non-empty strings.")
        severity = item.strip().lower()
        if severity not in SEVERITY_ORDER:
            raise ValueError(
                f"Review config key '{key}' contains unsupported severity '{item}'. "
                f"Supported values: {sorted(SEVERITY_ORDER)}"
            )
        if severity not in normalized:
            normalized.append(severity)
    return normalized


def load_review_config(root: Path) -> dict[str, Any]:
    config_path = root / REVIEW_CONFIG_PATH
    if not config_path.exists():
        raise ValueError(f"Review config file not found: {config_path.as_posix()}")

    try:
        raw = tomllib.loads(read_text_file(config_path))
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"Could not parse review config: {exc}") from exc

    model = raw.get("model")
    if model is not None and (not isinstance(model, str) or not model.strip()):
        raise ValueError("Review config key 'model' must be a non-empty string when present.")

    sandbox = require_string(raw, "sandbox")
    model_reasoning_effort = require_string(raw, "model_reasoning_effort")
    output_schema = require_string(raw, "output_schema")
    prompt_transport = require_string(raw, "prompt_transport")
    document_review_mode = require_string(raw, "document_review_mode")
    parallel_reviews = require_positive_int(raw, "parallel_reviews", DEFAULT_PARALLEL_REVIEWS)
    max_review_turns = require_positive_int(raw, "max_review_turns", DEFAULT_MAX_REVIEW_TURNS)
    blocking_severities = require_severity_list(raw, "blocking_severities", DEFAULT_BLOCKING_SEVERITIES)

    if prompt_transport not in SUPPORTED_PROMPT_TRANSPORTS:
        raise ValueError(
            f"Unsupported prompt_transport '{prompt_transport}'. Supported values: {sorted(SUPPORTED_PROMPT_TRANSPORTS)}"
        )

    if document_review_mode not in SUPPORTED_DOCUMENT_REVIEW_MODES:
        raise ValueError(
            "Unsupported document_review_mode "
            f"'{document_review_mode}'. Supported values: {sorted(SUPPORTED_DOCUMENT_REVIEW_MODES)}"
        )

    schema_path = (root / output_schema).resolve()

    return {
        "model": model.strip() if isinstance(model, str) else None,
        "sandbox": sandbox,
        "model_reasoning_effort": model_reasoning_effort,
        "output_schema": output_schema,
        "output_schema_path": schema_path,
        "prompt_transport": prompt_transport,
        "document_review_mode": document_review_mode,
        "parallel_reviews": parallel_reviews,
        "max_review_turns": max_review_turns,
        "blocking_severities": blocking_severities,
        "config_path": config_path.resolve(),
    }


def parse_markdown_table(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    lines = read_text_file(path).splitlines()
    header: list[str] | None = None
    rows: list[dict[str, str]] = []
    for line in lines:
        if not line.startswith("|"):
            continue
        parts = [part.strip() for part in line.strip().strip("|").split("|")]
        if not header:
            header = parts
            continue
        if all(re.fullmatch(r"-+", part.replace(":", "").replace(" ", "")) for part in parts):
            continue
        if len(parts) != len(header):
            continue
        rows.append(dict(zip(header, parts)))
    return rows


def unquote_md(value: str) -> str:
    value = value.strip()
    if value.startswith("`") and value.endswith("`"):
        return value[1:-1]
    return value


def active_cycle_dir(root: Path) -> Path | None:
    rows = parse_markdown_table(root / ".spec" / "cycle_index.md")
    for row in rows:
        status = row.get("Status", "").strip().upper()
        directory = row.get("Directory", "")
        if not directory:
            continue
        if status in {"ACTIVE", "DONE", "DRAFT", "FINALIZED"}:
            candidate = root / unquote_md(directory)
            if candidate.exists():
                return candidate
    return None


def newest_file(root: Path, pattern: str) -> Path | None:
    matches = list(root.glob(pattern))
    if not matches:
        return None
    return max(matches, key=lambda item: item.stat().st_mtime)


def bug_id_from_arguments(arguments: str) -> str | None:
    match = re.search(r"\b(b\d{3,}-[a-z0-9-]+)\b", arguments)
    return match.group(1) if match else None


def bug_dir_from_arguments(root: Path, arguments: str) -> Path | None:
    bug_id = bug_id_from_arguments(arguments)
    if bug_id:
        candidate = root / ".spec" / "bugs" / bug_id
        if candidate.exists():
            return candidate
    investigation_path = re.search(r"(\.spec/bugs/[^\s]+/INVESTIGATION\.md)", arguments.replace("\\", "/"))
    if investigation_path:
        candidate = root / investigation_path.group(1)
        if candidate.exists():
            return candidate.parent
    return None


def latest_bug_dir(root: Path) -> Path | None:
    bug_root = root / ".spec" / "bugs"
    candidates = [path for path in bug_root.iterdir()] if bug_root.exists() else []
    candidates = [path for path in candidates if path.is_dir()]
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.stat().st_mtime)


def task_files_from_dependencies(dependencies_path: Path, wave: str) -> list[Path]:
    rows = parse_markdown_table(dependencies_path)
    resolved: list[Path] = []
    for row in rows:
        if row.get("Wave", "").strip() != wave:
            continue
        file_name = unquote_md(row.get("File", "").strip())
        if not file_name:
            continue
        resolved.append(dependencies_path.parent / file_name)
    return resolved


def resolve_task_targets(root: Path, arguments: str) -> list[Path]:
    normalized = arguments.strip().replace("\\", "/")
    direct_task = re.search(r"(\.spec/(?:cycles|bugs)/[^\s]+\.md)", normalized)
    if direct_task:
        candidate = root / direct_task.group(1)
        if candidate.exists():
            return [candidate]

    wave_match = re.fullmatch(r"wave\s+(\d+)", normalized)
    if wave_match:
        cycle_dir = active_cycle_dir(root)
        if not cycle_dir:
            return []
        return task_files_from_dependencies(cycle_dir / "tasks" / "dependencies.md", wave_match.group(1))

    bug_wave_match = re.fullmatch(r"bug\s+(b\d{3,}-[a-z0-9-]+)\s+wave\s+(\d+)", normalized)
    if bug_wave_match:
        bug_dir = root / ".spec" / "bugs" / bug_wave_match.group(1)
        return task_files_from_dependencies(bug_dir / "tasks" / "dependencies.md", bug_wave_match.group(2))

    return []


def collect_phase_artifacts(root: Path, phase: str, arguments: str) -> list[Path]:
    artifacts: list[Path] = []

    if phase == "specify-design":
        cycle_dir = active_cycle_dir(root)
        cycle_doc = cycle_dir / "CYCLE.md" if cycle_dir else newest_file(root, ".spec/cycles/*/CYCLE.md")
        for candidate in [cycle_doc, root / ".spec" / "cycles" / "manifest.md", root / ".spec" / "cycle_index.md"]:
            if candidate and candidate.exists():
                artifacts.append(candidate)

    elif phase == "plan-tasks":
        cycle_dir = active_cycle_dir(root)
        if cycle_dir:
            task_dir = cycle_dir / "tasks"
            artifacts.append(root / ".workflow" / "project_context.md")
            ci_file = root / ".github" / "workflows" / "ci.yml"
            if ci_file.exists():
                artifacts.append(ci_file)
            if task_dir.exists():
                artifacts.extend(sorted(path for path in task_dir.glob("*.md") if path.name != "dependencies.md"))
                dependencies = task_dir / "dependencies.md"
                if dependencies.exists():
                    artifacts.append(dependencies)

    elif phase == "investigate":
        bug_dir = bug_dir_from_arguments(root, arguments) or latest_bug_dir(root)
        if bug_dir:
            investigation = bug_dir / "INVESTIGATION.md"
            if investigation.exists():
                artifacts.append(investigation)

    elif phase == "fix-tasks":
        bug_dir = bug_dir_from_arguments(root, arguments) or latest_bug_dir(root)
        if bug_dir:
            task_dir = bug_dir / "tasks"
            if task_dir.exists():
                artifacts.extend(sorted(path for path in task_dir.glob("*.md") if path.name != "dependencies.md"))
                dependencies = task_dir / "dependencies.md"
                if dependencies.exists():
                    artifacts.append(dependencies)

    return [artifact for artifact in artifacts if artifact.exists()]


def is_approval_gated_phase(phase: str) -> bool:
    return phase in APPROVAL_GATED_PHASES


def finalized_document_contents(approved_contents: str) -> str | None:
    def replace(match: re.Match[str]) -> str:
        return f"{match.group('prefix')}{match.group('quote')}FINALIZED{match.group('quote')}"

    finalized_contents, replacements = DOCUMENT_DRAFT_STATUS_RE.subn(replace, approved_contents, count=1)
    if replacements != 1:
        return None
    return finalized_contents


def finalized_manifest_contents(approved_contents: str, cycle_directory: str) -> str | None:
    lines = approved_contents.splitlines()
    normalized_cycle_directory = cycle_directory.replace("\\", "/").rstrip("/")
    updated = False

    for index, line in enumerate(lines):
        if not line.startswith("|"):
            continue
        parts = line.split("|")
        if len(parts) < 3:
            continue
        cells = [part.strip() for part in parts[1:-1]]
        if len(cells) != 6:
            continue
        directory_cell = unquote_md(cells[1]).strip().replace("\\", "/").rstrip("/")
        if directory_cell != normalized_cycle_directory:
            continue
        if unquote_md(cells[-1]).strip() != "DRAFT":
            return None
        replaced_status, replacements = re.subn(r"\bDRAFT\b", "FINALIZED", parts[-2], count=1)
        if replacements != 1:
            return None
        parts[-2] = replaced_status
        lines[index] = "|".join(parts)
        updated = True
        break

    if not updated:
        return None

    finalized_contents = "\n".join(lines)
    if approved_contents.endswith("\n"):
        finalized_contents += "\n"
    return finalized_contents


def finalization_change_error(artifact_path: Path, current_contents: str, approved_contents: str, expected_contents: str | None) -> str | None:
    artifact_key = artifact_path.as_posix()
    if expected_contents is None:
        return (
            f"Approved snapshot for {artifact_key} does not contain a clean DRAFT status to finalize. "
            "Run prepare and rerun the document review loop."
        )
    if current_contents == expected_contents:
        return None
    if current_contents == approved_contents:
        return (
            f"{artifact_key} is still in its approved DRAFT form. After explicit user approval, apply only the "
            "status-only finalization change and run finish again."
        )
    return (
        f"{artifact_key} changed beyond the allowed status-only finalization. Treat this as manual feedback, "
        "run prepare, and rerun the document review loop."
    )


def validate_specify_design_finalization(root: Path, artifacts: list[Path], payload: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    artifact_map = {artifact.name: artifact for artifact in artifacts}
    cycle_doc = artifact_map.get("CYCLE.md")
    manifest = artifact_map.get("manifest.md")
    cycle_index = artifact_map.get("cycle_index.md")

    if not cycle_doc:
        issues.append("Missing CYCLE.md during approval-only finalization. Run prepare and rerun the document review loop.")
        return issues
    if not manifest:
        issues.append("Missing manifest.md during approval-only finalization. Run prepare and rerun the document review loop.")
        return issues
    if not cycle_index:
        issues.append("Missing cycle_index.md during approval-only finalization. Run prepare and rerun the document review loop.")
        return issues

    approved_snapshots = approved_snapshots_map(payload)
    cycle_snapshot = approved_snapshots.get(cycle_doc.as_posix())
    manifest_snapshot = approved_snapshots.get(manifest.as_posix())
    cycle_index_snapshot = approved_snapshots.get(cycle_index.as_posix())

    if not isinstance(cycle_snapshot, str):
        issues.append(f"Missing approved snapshot for {cycle_doc.as_posix()}. Run prepare and rerun the document review loop.")
    if not isinstance(manifest_snapshot, str):
        issues.append(f"Missing approved snapshot for {manifest.as_posix()}. Run prepare and rerun the document review loop.")
    if not isinstance(cycle_index_snapshot, str):
        issues.append(f"Missing approved snapshot for {cycle_index.as_posix()}. Run prepare and rerun the document review loop.")
    if issues:
        return issues

    cycle_snapshot_text = cast(str, cycle_snapshot)
    manifest_snapshot_text = cast(str, manifest_snapshot)
    cycle_index_snapshot_text = cast(str, cycle_index_snapshot)

    cycle_error = finalization_change_error(
        cycle_doc,
        read_text_file(cycle_doc),
        cycle_snapshot_text,
        finalized_document_contents(cycle_snapshot_text),
    )
    if cycle_error:
        issues.append(cycle_error)

    cycle_directory = cycle_doc.parent.relative_to(root).as_posix()
    manifest_error = finalization_change_error(
        manifest,
        read_text_file(manifest),
        manifest_snapshot_text,
        finalized_manifest_contents(manifest_snapshot_text, cycle_directory),
    )
    if manifest_error:
        issues.append(manifest_error)

    current_cycle_index = read_text_file(cycle_index)
    if current_cycle_index != cycle_index_snapshot_text:
        issues.append(
            f"{cycle_index.as_posix()} changed after approval. Approval-only finalization must keep cycle_index.md unchanged. "
            "Treat this as manual feedback, run prepare, and rerun the document review loop."
        )

    return issues


def validate_investigate_finalization(artifacts: list[Path], payload: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    artifact_map = {artifact.name: artifact for artifact in artifacts}
    investigation = artifact_map.get("INVESTIGATION.md")
    if not investigation:
        issues.append(
            "Missing INVESTIGATION.md during approval-only finalization. Run prepare and rerun the document review loop."
        )
        return issues

    approved_snapshots = approved_snapshots_map(payload)
    investigation_snapshot = approved_snapshots.get(investigation.as_posix())
    if not isinstance(investigation_snapshot, str):
        issues.append(
            f"Missing approved snapshot for {investigation.as_posix()}. Run prepare and rerun the document review loop."
        )
        return issues

    investigation_snapshot_text = cast(str, investigation_snapshot)

    investigation_error = finalization_change_error(
        investigation,
        read_text_file(investigation),
        investigation_snapshot_text,
        finalized_document_contents(investigation_snapshot_text),
    )
    if investigation_error:
        issues.append(investigation_error)
    return issues


def validate_approval_finalization(root: Path, phase: str, artifacts: list[Path], payload: dict[str, Any]) -> list[str]:
    if phase == "specify-design":
        return validate_specify_design_finalization(root, artifacts, payload)
    if phase == "investigate":
        return validate_investigate_finalization(artifacts, payload)
    return [f"Phase {phase} does not support approval-only finalization."]


def reference_block(label: str, contents: str) -> str:
    marker = re.sub(r"[^A-Za-z0-9]+", "_", label).strip("_").upper() or "REFERENCE"
    return "\n".join([f"<<<{marker} START>>>", contents, f"<<<{marker} END>>>"])


def severity_guidance_lines(config: dict[str, Any], round_number: int) -> list[str]:
    blocking = ", ".join(severity.upper() for severity in config["blocking_severities"])
    return [
        f"Current review round: {round_number}/{config['max_review_turns']}",
        "",
        "Severity definitions:",
        "- critical: must be fixed before the artifact or task can be treated as complete.",
        "- major: violates workflow/spec/task requirements or is inappropriate for release quality.",
        "- middle: acceptable for release, but meaningfully undesirable.",
        "- minor: acceptable for release and only lightly undesirable.",
        "",
        "Classification rules:",
        f"- Set approved to true only when there are no {blocking} findings.",
        "- Use critical only for clear ship blockers or correctness issues that must be fixed before completion.",
        "- Use major only when you can point to a concrete violated rule, task requirement, or release-quality risk.",
        "- If you are unsure whether something is major or middle, choose middle.",
        "- Use middle or minor for non-blocking improvements that are still concrete and worthwhile.",
        "- Do not report speculation, stylistic preferences, or generic alternative ideas as findings.",
        "- For every critical or major finding, explain the concrete evidence, violated rule, or release risk in details.",
    ]


def docs_first_review_lines(primary_source: str) -> list[str]:
    return [
        "Review order:",
        f"- First, verify compliance with {primary_source}. Treat the provided documents as the source of truth for this review.",
        "- Second, perform normal review for concrete issues that do not conflict with those documents.",
        "",
        "Document precedence rules:",
        "- Do not report findings or suggested fixes that conflict with the provided documents.",
        "- Do not prefer generic best practices over an explicit documented requirement in the provided documents.",
        "- If a provided document explicitly requires, permits, or constrains a choice, respect that document instead of challenging the choice.",
        "- If the provided documents conflict with each other, report that document conflict as the finding instead of inventing a resolution.",
    ]


def plan_tasks_cycle_doc_path(root: Path, artifact_path: Path) -> Path | None:
    try:
        relative_artifact = artifact_path.resolve().relative_to(root.resolve())
    except ValueError:
        relative_artifact = artifact_path

    parts = relative_artifact.parts
    if len(parts) >= 3 and parts[0] == ".spec" and parts[1] == "cycles":
        candidate = root / parts[0] / parts[1] / parts[2] / "CYCLE.md"
        if candidate.exists():
            return candidate

    cycle_dir = active_cycle_dir(root)
    if not cycle_dir:
        return None

    candidate = cycle_dir / "CYCLE.md"
    return candidate if candidate.exists() else None


def document_prompt(root: Path, phase: str, artifact_path: Path, config: dict[str, Any], round_number: int) -> str:
    if config["document_review_mode"] != "inline-artifact":
        raise ValueError(
            "Document review mode must be 'inline-artifact' for workflow document reviews. "
            f"Configured value: {config['document_review_mode']}"
        )

    references: list[tuple[str, Path]] = [
        ("AGENTS.md", root / "AGENTS.md"),
        (".workflow/procedures/review-loop.md", root / ".workflow" / "procedures" / "review-loop.md"),
    ]
    primary_source = "the provided workflow references"
    if phase == "plan-tasks":
        cycle_doc = plan_tasks_cycle_doc_path(root, artifact_path)
        if not cycle_doc:
            raise ValueError(
                "Plan-tasks review requires the active cycle CYCLE.md as a provided reference before review can start."
            )
        references.append((cycle_doc.as_posix(), cycle_doc))
        primary_source = "the active cycle CYCLE.md and the other provided workflow references"

    phase_procedure = root / ".workflow" / "procedures" / f"{phase}.md"
    if phase_procedure.exists():
        references.append((phase_procedure.as_posix(), phase_procedure))

    prompt_lines = [
        "Review the workflow artifact shown below.",
        "",
        f"Phase: {phase}",
        "Artifact type: document",
        f"Artifact path: {artifact_path.as_posix()}",
        "",
        f"Review settings source: {Path(config['config_path']).as_posix()}",
        "",
        "Instructions:",
        "- Stay read-only.",
        "- Do not run tools, shell commands, or file reads.",
        "- Use only the workflow references and artifact contents provided in this prompt.",
        "- Return only concrete findings that are actionable.",
        "- If evidence is incomplete or uncertain, do not guess.",
    ]
    prompt_lines.extend(["", *docs_first_review_lines(primary_source)])
    prompt_lines.extend(
        [
            "",
            "Acceptance requirements:",
            "- The artifact is concrete, internally consistent, and free of placeholder or example text.",
            "- File references, statuses, dependencies, and branch names are consistent with the workflow rules.",
            f"- The artifact complies with the provided workflow references for phase `{phase}`.",
        ]
    )
    if phase == "plan-tasks":
        prompt_lines.append("- The artifact complies with the active cycle design and requirements in CYCLE.md.")

    prompt_lines.extend(["", *severity_guidance_lines(config, round_number)])

    for label, path in references:
        prompt_lines.extend(["", f"Reference: {label}", reference_block(label, read_text_file(path))])

    prompt_lines.extend(
        [
            "",
            "Artifact contents:",
            reference_block(artifact_path.as_posix(), read_text_file(artifact_path)),
        ]
    )

    return "\n".join(prompt_lines)


def implementation_prompt(root: Path, task_path: Path, config: dict[str, Any], round_number: int) -> str:
    prompt_lines = [
        f"Review the implementation associated with task file {task_path.as_posix()}.",
        "",
        "Phase: implement",
        "Artifact type: implementation-task",
        f"Artifact path: {task_path.as_posix()}",
        "",
        f"Review settings source: {Path(config['config_path']).as_posix()}",
        "",
        "Acceptance requirements:",
        "- Review the current repository changes relevant to this task in read-only mode.",
        "- Treat the task file as the source of truth for task-specific requirements in this review.",
        "- Verify the tests, implementation, refactor, verification commands, and done condition comply with the task file.",
        "- Flag only concrete findings that should affect completion of this task.",
        "",
        "Rules:",
        "- Stay read-only.",
        "- Use the supplied JSON schema.",
        "- You may inspect the repository in read-only mode if needed.",
        "- Do not invent missing evidence. If the repository state does not support a claim, do not report it.",
        "- If a general review instinct conflicts with the task file, treat the task file as authoritative and do not emit that conflicting finding.",
    ]
    prompt_lines.extend(["", *docs_first_review_lines("the task file and the provided workflow references")])
    prompt_lines.extend(["", *severity_guidance_lines(config, round_number)])
    prompt_lines.extend(
        [
            "",
            "Reference: AGENTS.md",
            reference_block("AGENTS.md", read_text_file(root / "AGENTS.md")),
            "",
            "Reference: .workflow/procedures/review-loop.md",
            reference_block(
                ".workflow/procedures/review-loop.md",
                read_text_file(root / ".workflow" / "procedures" / "review-loop.md"),
            ),
            "",
            "Reference: .workflow/procedures/implement.md",
            reference_block(
                ".workflow/procedures/implement.md",
                read_text_file(root / ".workflow" / "procedures" / "implement.md"),
            ),
            "",
            "Task file contents:",
            reference_block(task_path.as_posix(), read_text_file(task_path)),
        ]
    )
    return "\n".join(prompt_lines)


def write_failure_logs(output_path: Path, stdout_text: str, stderr_text: str) -> tuple[Path, Path]:
    stdout_log = output_path.parent / f"{output_path.stem}.stdout.log"
    stderr_log = output_path.parent / f"{output_path.stem}.stderr.log"
    stdout_log.write_text(stdout_text, encoding="utf-8")
    stderr_log.write_text(stderr_text, encoding="utf-8")
    return stdout_log, stderr_log


def clear_failure_logs(output_path: Path) -> None:
    for suffix in ["stdout.log", "stderr.log"]:
        candidate = output_path.parent / f"{output_path.stem}.{suffix}"
        candidate.unlink(missing_ok=True)


def resolve_codex_binary() -> str | None:
    return shutil.which("codex") or shutil.which("codex.cmd") or shutil.which("codex.exe")


def build_codex_command(codex_bin: str, config: dict[str, Any], output_path: Path) -> list[str]:
    cmd = [codex_bin, "exec"]
    if config["model"]:
        cmd.extend(["--model", config["model"]])
    cmd.extend(
        [
            "--skip-git-repo-check",
            "--sandbox",
            config["sandbox"],
            "-c",
            f'model_reasoning_effort="{config["model_reasoning_effort"]}"',
            "--output-schema",
            str(config["output_schema_path"]),
            "-o",
            str(output_path),
        ]
    )

    if config["prompt_transport"] != "stdin":
        raise ValueError(f"Unsupported prompt transport: {config['prompt_transport']}")

    cmd.append("-")
    return cmd


def run_codex_once(
    root: Path,
    prompt: str,
    output_path: Path,
    config: dict[str, Any],
    codex_bin: str,
    reviewer_index: int,
    reviewer_count: int,
) -> tuple[bool, dict[str, Any] | None, str]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()

    try:
        cmd = build_codex_command(codex_bin, config, output_path)
    except ValueError as exc:
        return False, None, str(exc)

    eprint(f"[review] reviewer {reviewer_index}/{reviewer_count}: starting")
    result = subprocess.run(
        cmd,
        cwd=root,
        env=env,
        input=prompt,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    if result.returncode != 0:
        stdout_log, stderr_log = write_failure_logs(output_path, result.stdout or "", result.stderr or "")
        stderr = (result.stderr or result.stdout or "codex exec failed").strip()
        return (
            False,
            None,
            f"reviewer {reviewer_index} failed: {stderr}\nFailure logs: {stdout_log.as_posix()}, {stderr_log.as_posix()}",
        )

    if not output_path.exists():
        stdout_log, stderr_log = write_failure_logs(output_path, result.stdout or "", result.stderr or "")
        return (
            False,
            None,
            "reviewer "
            f"{reviewer_index} completed without producing a review log. Failure logs: "
            f"{stdout_log.as_posix()}, {stderr_log.as_posix()}",
        )

    try:
        data = json.loads(read_text_file(output_path))
    except json.JSONDecodeError as exc:
        stdout_log, stderr_log = write_failure_logs(output_path, result.stdout or "", result.stderr or "")
        return (
            False,
            None,
            f"reviewer {reviewer_index} returned invalid JSON: {exc}. Failure logs: {stdout_log.as_posix()}, {stderr_log.as_posix()}",
        )
    if not isinstance(data, dict):
        stdout_log, stderr_log = write_failure_logs(output_path, result.stdout or "", result.stderr or "")
        return (
            False,
            None,
            "reviewer "
            f"{reviewer_index} review log did not contain an object. Failure logs: "
            f"{stdout_log.as_posix()}, {stderr_log.as_posix()}",
        )

    clear_failure_logs(output_path)
    eprint(f"[review] reviewer {reviewer_index}/{reviewer_count}: completed")
    return True, data, ""


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalize_severity(value: Any) -> str:
    candidate = str(value).strip().lower()
    return candidate if candidate in SEVERITY_ORDER else "minor"


def severity_rank(value: str) -> int:
    return SEVERITY_ORDER.get(normalize_severity(value), len(SEVERITY_ORDER))


def finding_key(finding: dict[str, Any]) -> tuple[str, str, str]:
    title = normalize_space(str(finding.get("title", ""))).lower()
    location = normalize_space(str(finding.get("location", "") or "")).lower()
    details = ""
    if not title:
        details = normalize_space(str(finding.get("details", ""))).lower()[:160]
    return title, location, details


def normalized_finding(finding: dict[str, Any]) -> dict[str, Any]:
    title = normalize_space(str(finding.get("title", ""))) or "Untitled finding"
    details = normalize_space(str(finding.get("details", "")))
    location_text = normalize_space(str(finding.get("location", "") or ""))
    suggested_fix = normalize_space(str(finding.get("suggested_fix", "")))
    return {
        "severity": normalize_severity(finding.get("severity", "minor")),
        "title": title,
        "details": details,
        "location": location_text or None,
        "suggested_fix": suggested_fix,
    }


def sort_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        findings,
        key=lambda item: (
            severity_rank(str(item.get("severity", "minor"))),
            normalize_space(str(item.get("title", ""))).lower(),
            normalize_space(str(item.get("location", "") or "")).lower(),
        ),
    )


def merge_review_results(
    raw_results: list[dict[str, Any]],
    phase: str,
    artifact_type: str,
    artifact_path: str,
    task_file_path: str | None,
    review_round: int,
    config: dict[str, Any],
    raw_log_paths: list[Path],
) -> dict[str, Any]:
    merged_findings: dict[tuple[str, str, str], dict[str, Any]] = {}
    reviewers: list[dict[str, Any]] = []

    for reviewer_index, result in enumerate(raw_results, start=1):
        reviewer_findings = result.get("findings", [])
        reviewers.append(
            {
                "reviewer_index": reviewer_index,
                "approved": bool(result.get("approved", False)),
                "summary": str(result.get("summary", "")).strip(),
                "raw_log_path": raw_log_paths[reviewer_index - 1].as_posix(),
                "finding_count": len(reviewer_findings) if isinstance(reviewer_findings, list) else 0,
            }
        )

        if not isinstance(reviewer_findings, list):
            continue

        for raw_finding in reviewer_findings:
            if not isinstance(raw_finding, dict):
                continue

            finding = normalized_finding(raw_finding)
            key = finding_key(finding)
            current = merged_findings.get(key)
            if not current:
                merged_findings[key] = {
                    **finding,
                    "support_count": 1,
                    "reviewer_indexes": [reviewer_index],
                }
                continue

            if severity_rank(finding["severity"]) < severity_rank(str(current.get("severity", "minor"))):
                current.update(
                    {
                        "severity": finding["severity"],
                        "title": finding["title"],
                        "details": finding["details"],
                        "location": finding["location"],
                        "suggested_fix": finding["suggested_fix"],
                    }
                )
            current["support_count"] = int(current.get("support_count", 0)) + 1
            reviewer_indexes = current.get("reviewer_indexes", [])
            if isinstance(reviewer_indexes, list) and reviewer_index not in reviewer_indexes:
                reviewer_indexes.append(reviewer_index)

    blocking_severities = set(config["blocking_severities"])
    all_findings = sort_findings(list(merged_findings.values()))
    blocking_findings = [{**finding, "blocking": True} for finding in all_findings if finding["severity"] in blocking_severities]
    advisory_findings = [{**finding, "blocking": False} for finding in all_findings if finding["severity"] not in blocking_severities]

    summary = (
        f"Round {review_round}/{config['max_review_turns']}: "
        f"{len(reviewers)} reviewers completed, "
        f"{len(blocking_findings)} blocking findings, "
        f"{len(advisory_findings)} advisory findings."
    )

    return {
        "approved": len(blocking_findings) == 0,
        "summary": summary,
        "phase": phase,
        "artifact_type": artifact_type,
        "artifact_path": artifact_path,
        "task_file_path": task_file_path,
        "review_round": review_round,
        "max_review_turns": config["max_review_turns"],
        "parallel_reviews": config["parallel_reviews"],
        "blocking_severities": list(config["blocking_severities"]),
        "findings": blocking_findings,
        "advisory_findings": advisory_findings,
        "reviewers": reviewers,
        "raw_log_paths": [path.as_posix() for path in raw_log_paths],
    }


def run_codex_parallel(
    root: Path,
    prompt: str,
    output_path: Path,
    config: dict[str, Any],
    phase: str,
    artifact_type: str,
    artifact_path: str,
    task_file_path: str | None,
    review_round: int,
) -> tuple[bool, dict[str, Any] | None, str]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    codex_bin = resolve_codex_binary()
    if not codex_bin:
        return False, None, "codex executable was not found in PATH"

    raw_log_paths = [reviewer_output_path(output_path, index) for index in range(1, config["parallel_reviews"] + 1)]
    raw_results: list[dict[str, Any] | None] = [None] * config["parallel_reviews"]
    errors: list[str] = []

    eprint(
        f"[review] round {review_round}/{config['max_review_turns']}: "
        f"launching {config['parallel_reviews']} parallel reviewers for {artifact_path}"
    )

    with concurrent.futures.ThreadPoolExecutor(max_workers=config["parallel_reviews"]) as executor:
        futures = {
            executor.submit(
                run_codex_once,
                root,
                prompt,
                raw_log_paths[index - 1],
                config,
                codex_bin,
                index,
                config["parallel_reviews"],
            ): index
            for index in range(1, config["parallel_reviews"] + 1)
        }

        for future in concurrent.futures.as_completed(futures):
            reviewer_index = futures[future]
            try:
                ok, result, error_message = future.result()
            except Exception as exc:  # pragma: no cover - defensive guard
                errors.append(f"reviewer {reviewer_index} raised an unexpected exception: {exc}")
                continue

            if not ok or not result:
                errors.append(error_message or f"reviewer {reviewer_index} failed")
                continue

            raw_results[reviewer_index - 1] = result

    if errors:
        return False, None, "\n".join(errors)

    merged = merge_review_results(
        [result for result in raw_results if isinstance(result, dict)],
        phase=phase,
        artifact_type=artifact_type,
        artifact_path=artifact_path,
        task_file_path=task_file_path,
        review_round=review_round,
        config=config,
        raw_log_paths=raw_log_paths,
    )
    write_json_file(output_path, merged)
    return True, merged, ""


def findings_lines(findings: list[dict[str, Any]], limit: int = 5) -> str:
    if not findings:
        return ""
    lines: list[str] = []
    for finding in findings[:limit]:
        severity = str(finding.get("severity", "minor")).upper()
        title = str(finding.get("title", "Untitled finding")).strip()
        details = str(finding.get("details", "")).strip()
        location = str(finding.get("location", "") or "").strip()
        line = f"- [{severity}] {title}"
        if location:
            line += f" ({location})"
        if details:
            line += f": {details}"
        lines.append(line)
    return "\n".join(lines)


def blocking_summary(result: dict[str, Any]) -> str:
    findings = result.get("findings", [])
    return findings_lines(findings if isinstance(findings, list) else [])


def advisory_summary(result: dict[str, Any]) -> str:
    findings = result.get("advisory_findings", [])
    return findings_lines(findings if isinstance(findings, list) else [])


def build_failure_message(artifact_path: str, result: dict[str, Any]) -> str:
    sections = [f"Codex review found blocking issues in {artifact_path}."]
    blocking = blocking_summary(result)
    if blocking:
        sections.append(blocking)
    advisory = advisory_summary(result)
    if advisory:
        sections.append("Advisory findings:")
        sections.append(advisory)
    return "\n".join(section for section in sections if section)


def build_success_message(prefix: str, artifact_path: str, result: dict[str, Any]) -> str:
    advisory = advisory_summary(result)
    if advisory:
        return f"{prefix} passed for {artifact_path} with advisory findings.\nAdvisory findings:\n{advisory}"
    return f"{prefix} passed for {artifact_path}."


def write_state(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def read_state(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(read_text_file(path))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def coerce_non_negative_int(value: Any) -> int:
    if isinstance(value, int):
        return value if value >= 0 else 0
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return 0


def fresh_state_payload(
    root: Path,
    tool: str,
    phase: str,
    session_id: str | None,
    arguments: str,
    review_config_path: Path,
) -> dict[str, Any]:
    return {
        "tool": tool,
        "phase": phase,
        "session_id": session_id,
        "arguments": arguments,
        "state_path": str(state_path(root, tool, phase, session_id)),
        "review_log_path": str(log_path(root, tool, phase, session_id)),
        "review_config_path": str(review_config_path),
        "targets": [path.as_posix() for path in resolve_task_targets(root, arguments)] if phase == "implement" else [],
        "rounds": {},
        "approved_hashes": {},
        "approved_snapshots": {},
        "awaiting_user_approval": False,
        "state_version": 3,
    }


def hydrate_state_payload(
    root: Path,
    tool: str,
    phase: str,
    session_id: str | None,
    arguments: str,
    review_config_path: Path,
    payload: dict[str, Any] | None,
) -> dict[str, Any]:
    state = fresh_state_payload(root, tool, phase, session_id, arguments, review_config_path)
    if not payload:
        return state

    saved_arguments = payload.get("arguments")
    if isinstance(saved_arguments, str) and saved_arguments.strip():
        state["arguments"] = saved_arguments

    targets = payload.get("targets")
    if isinstance(targets, list):
        state["targets"] = [str(item) for item in targets if isinstance(item, str) and item.strip()]

    rounds = payload.get("rounds")
    if isinstance(rounds, dict):
        state["rounds"] = {str(key): coerce_non_negative_int(value) for key, value in rounds.items()}

    approved_hashes = payload.get("approved_hashes")
    if isinstance(approved_hashes, dict):
        state["approved_hashes"] = {
            str(key): str(value)
            for key, value in approved_hashes.items()
            if isinstance(key, str) and isinstance(value, str) and value
        }

    approved_snapshots = payload.get("approved_snapshots")
    if isinstance(approved_snapshots, dict):
        state["approved_snapshots"] = {
            str(key): str(value)
            for key, value in approved_snapshots.items()
            if isinstance(key, str) and isinstance(value, str)
        }

    state["awaiting_user_approval"] = bool(payload.get("awaiting_user_approval", False))

    return state


def rounds_map(payload: dict[str, Any]) -> dict[str, int]:
    rounds = payload.get("rounds")
    if not isinstance(rounds, dict):
        rounds = {}
        payload["rounds"] = rounds
    return rounds


def approved_hashes_map(payload: dict[str, Any]) -> dict[str, str]:
    approved_hashes = payload.get("approved_hashes")
    if not isinstance(approved_hashes, dict):
        approved_hashes = {}
        payload["approved_hashes"] = approved_hashes
    return approved_hashes


def approved_snapshots_map(payload: dict[str, Any]) -> dict[str, str]:
    approved_snapshots = payload.get("approved_snapshots")
    if not isinstance(approved_snapshots, dict):
        approved_snapshots = {}
        payload["approved_snapshots"] = approved_snapshots
    return approved_snapshots


def ensure_target_registered(payload: dict[str, Any], target: str) -> None:
    targets = payload.get("targets")
    if not isinstance(targets, list):
        targets = []
        payload["targets"] = targets
    if target not in targets:
        targets.append(target)


def peek_next_round(payload: dict[str, Any], target: str, max_review_turns: int) -> tuple[bool, int, str]:
    current_round = coerce_non_negative_int(rounds_map(payload).get(target, 0))
    next_round = current_round + 1
    if next_round > max_review_turns:
        message = (
            f"Review turn limit reached for {target}. "
            f"Completed {current_round}/{max_review_turns} rounds in the current review session. "
            "Wait for new user input or explicitly reset the review rounds before reviewing this target again."
        )
        return False, current_round, message
    return True, next_round, ""


def mark_round_used(payload: dict[str, Any], target: str, round_number: int) -> None:
    rounds_map(payload)[target] = round_number


def file_sha256(path: Path) -> str:
    return hashlib.sha256(read_bytes_file(path)).hexdigest()


def handle_prepare(args: argparse.Namespace) -> int:
    root = find_repo_root(Path.cwd())
    try:
        config = load_review_config(root)
    except ValueError as exc:
        eprint(str(exc))
        return 1

    payload = fresh_state_payload(root, args.tool, args.phase, args.session_id, args.arguments, config["config_path"])
    write_state(state_path(root, args.tool, args.phase, args.session_id), payload)
    print(f"Prepared review state for {args.tool}:{args.phase}.")
    return 0


def finish_decision(reason: str) -> str:
    return json.dumps({"decision": "block", "reason": reason}, ensure_ascii=True)


def return_finish_result(message: str, hook_event: str | None) -> int:
    if hook_event:
        print(finish_decision(message))
        return 0
    eprint(message)
    return 1


def handle_finish(args: argparse.Namespace) -> int:
    hook_input = read_stdin_json() if args.hook_event else {}
    session_id = args.session_id or str(hook_input.get("session_id", "") or "") or None
    root = find_repo_root(Path(hook_input.get("cwd", os.getcwd())))
    current_state_path = state_path(root, args.tool, args.phase, session_id)
    raw_payload = read_state(current_state_path)
    if not raw_payload:
        return 0

    try:
        config = load_review_config(root)
    except ValueError as exc:
        message = str(exc)
        return return_finish_result(message, args.hook_event)

    payload = hydrate_state_payload(
        root,
        args.tool,
        args.phase,
        session_id,
        str(raw_payload.get("arguments", "")),
        config["config_path"],
        raw_payload,
    )
    arguments = str(payload.get("arguments", ""))
    artifacts = collect_phase_artifacts(root, args.phase, arguments)
    if is_approval_gated_phase(args.phase) and bool(payload.get("awaiting_user_approval", False)):
        issues = validate_approval_finalization(root, args.phase, artifacts, payload)
        if issues:
            return return_finish_result("\n".join(issues), args.hook_event)
        current_state_path.unlink(missing_ok=True)
        return 0

    if not artifacts:
        current_state_path.unlink(missing_ok=True)
        return 0

    review_log = log_path(root, args.tool, args.phase, session_id)
    approved_hashes = approved_hashes_map(payload)
    approved_snapshots = approved_snapshots_map(payload)
    for artifact in artifacts:
        artifact_key = artifact.as_posix()
        artifact_hash = file_sha256(artifact)
        if approved_hashes.get(artifact_key) == artifact_hash:
            eprint(f"[review] skipping unchanged approved artifact {artifact_key}")
            continue

        can_review, next_round, limit_message = peek_next_round(payload, artifact_key, config["max_review_turns"])
        if not can_review:
            return return_finish_result(limit_message, args.hook_event)

        try:
            prompt = document_prompt(root, args.phase, artifact, config, next_round)
        except ValueError as exc:
            message = str(exc)
            return return_finish_result(message, args.hook_event)

        ok, result, error_message = run_codex_parallel(
            root,
            prompt,
            review_log,
            config,
            phase=args.phase,
            artifact_type="document",
            artifact_path=artifact_key,
            task_file_path=None,
            review_round=next_round,
        )
        if not ok or not result:
            message = f"Codex review failed for {artifact_key}: {error_message}"
            return return_finish_result(message, args.hook_event)

        mark_round_used(payload, artifact_key, next_round)
        if not result.get("approved", False) or result.get("findings"):
            approved_hashes.pop(artifact_key, None)
            approved_snapshots.pop(artifact_key, None)
            payload["awaiting_user_approval"] = False
            write_state(current_state_path, payload)
            message = build_failure_message(artifact_key, result)
            return return_finish_result(message, args.hook_event)

        approved_hashes[artifact_key] = artifact_hash
        approved_snapshots[artifact_key] = read_text_file(artifact)
        write_state(current_state_path, payload)

    if is_approval_gated_phase(args.phase):
        payload["awaiting_user_approval"] = True
        write_state(current_state_path, payload)
        return 0

    current_state_path.unlink(missing_ok=True)
    return 0


def handle_review_task(args: argparse.Namespace) -> int:
    root = find_repo_root(Path.cwd())
    try:
        config = load_review_config(root)
    except ValueError as exc:
        eprint(str(exc))
        return 1

    task_path = (root / args.task_file).resolve() if not Path(args.task_file).is_absolute() else Path(args.task_file)
    if not task_path.exists():
        eprint(f"Task file not found: {task_path}")
        return 1

    current_state_path = state_path(root, args.tool, "implement", args.session_id)
    payload = hydrate_state_payload(
        root,
        args.tool,
        "implement",
        args.session_id,
        "",
        config["config_path"],
        read_state(current_state_path),
    )
    task_key = task_path.as_posix()
    ensure_target_registered(payload, task_key)

    can_review, next_round, limit_message = peek_next_round(payload, task_key, config["max_review_turns"])
    if not can_review:
        write_state(current_state_path, payload)
        eprint(limit_message)
        return 1

    review_log = log_path(root, args.tool, "implement", args.session_id)
    prompt = implementation_prompt(root, task_path, config, next_round)
    ok, result, error_message = run_codex_parallel(
        root,
        prompt,
        review_log,
        config,
        phase="implement",
        artifact_type="implementation-task",
        artifact_path=task_key,
        task_file_path=task_key,
        review_round=next_round,
    )
    if not ok or not result:
        eprint(f"Codex implementation review failed for {task_key}: {error_message}")
        return 1

    mark_round_used(payload, task_key, next_round)
    write_state(current_state_path, payload)

    if not result.get("approved", False) or result.get("findings"):
        eprint(build_failure_message(task_key, result))
        return 1

    print(build_success_message("Codex implementation review", task_key, result))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare and run workflow Codex reviews.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--tool", required=True)
    prepare.add_argument("--phase", required=True, choices=sorted(PHASES))
    prepare.add_argument("--session-id")
    prepare.add_argument("--arguments", default="")
    prepare.set_defaults(handler=handle_prepare)

    finish = subparsers.add_parser("finish")
    finish.add_argument("--tool", required=True)
    finish.add_argument("--phase", required=True, choices=FINISH_PHASES)
    finish.add_argument("--session-id")
    finish.add_argument("--hook-event")
    finish.set_defaults(handler=handle_finish)

    review_task = subparsers.add_parser("review-task")
    review_task.add_argument("--tool", required=True)
    review_task.add_argument("--task-file", required=True)
    review_task.add_argument("--session-id")
    review_task.set_defaults(handler=handle_review_task)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
