"""PSD2Fusion adapter for the generic codex-ephemeral-harness cycle.

The harness remains the owner of role isolation, discovery, patch authority,
Runner tests, and Verifier gating.  This module only projects PSD2Fusion's
repo-local canonical state into that contract and records an opaque evidence
marker after a verified tranche.  In particular, it never edits
``.control/current.json``: PARITY-004 state transitions remain an explicit
project-verifier operation.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any


_CURRENT = Path(".control/current.json")
_GOAL = Path(".control/CURRENT_GOAL.md")
_TODO = Path(".control/PARITY-004_TODO.md")
_EVIDENCE = Path(".control/evidence/PARITY-004")
_HARNESS_EVIDENCE = _EVIDENCE / "harness"
_CHECK = Path("scripts/check.ps1")
_REMOTE_GUARD = Path("scripts/remote_completion_guard.ps1")
_REMOTE_GUARD_PY = Path("scripts/remote_completion_guard.py")
_MAX_TEXT = 9_000
_MAX_EVIDENCE_FILES = 10
_MAX_EVIDENCE_ITEM = 6_000
_DROP_KEYS = {
    "conversation",
    "transcript",
    "chain_of_thought",
    "reasoning_trace",
    "prompt",
    "stdout_tail",
    "stderr_tail",
}


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"PSD2Fusion canonical JSON is unreadable: {path.as_posix()}") from exc


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"PSD2Fusion canonical text is unreadable: {path.as_posix()}") from exc


def _parity004_section(text: str) -> str:
    """Project only the active Goal section, not unrelated future tasks."""

    marker = "### PARITY-004"
    start = text.find(marker)
    if start < 0:
        return text
    end = text.find("### PARITY-005", start)
    if end < 0:
        end = len(text)
    return text[start:end]


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_record(repo: Path, relative: Path) -> dict[str, Any]:
    path = repo / relative
    try:
        data = path.read_bytes()
    except OSError:
        return {"path": relative.as_posix(), "present": False, "sha256": None}
    return {
        "path": relative.as_posix(),
        "present": True,
        "bytes": len(data),
        "sha256": _sha256_bytes(data),
    }


def _scrub_string(value: str, repo: Path) -> str:
    """Keep useful evidence text while removing the canonical absolute root."""

    result = str(value)
    variants = {
        str(repo),
        str(repo).replace("\\", "/"),
        str(repo).replace("/", "\\"),
    }
    for variant in sorted(variants, key=len, reverse=True):
        if variant:
            result = re.sub(re.escape(variant), "<canonical-repo>", result, flags=re.IGNORECASE)
    if len(result) > _MAX_TEXT:
        result = result[:_MAX_TEXT] + "...[bounded]"
    # The generic PowerShell entrypoint may inherit a legacy cp932 stdout
    # encoding.  Keep the projection lossless enough for evidence review while
    # making every emitted byte representable there; the canonical markdown
    # remains untouched on disk.
    return result.encode("ascii", "backslashreplace").decode("ascii")


def _safe_value(value: Any, repo: Path, *, depth: int = 0) -> Any:
    """Bound and scrub a value before it enters a Manager/Verifier bundle."""

    if depth > 7:
        return "<depth-bounded>"
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for index, (raw_key, raw_value) in enumerate(value.items()):
            if index >= 96:
                result["<additional-keys>"] = "<bounded>"
                break
            key = str(raw_key)
            folded = key.casefold()
            if folded in _DROP_KEYS or any(marker in folded for marker in ("transcript", "reasoning_trace", "chain_of_thought")):
                continue
            result[key] = _safe_value(raw_value, repo, depth=depth + 1)
        return result
    if isinstance(value, list):
        values = [_safe_value(item, repo, depth=depth + 1) for item in value[:48]]
        if len(value) > 48:
            values.append("<items-bounded>")
        return values
    if isinstance(value, tuple):
        return _safe_value(list(value), repo, depth=depth + 1)
    if isinstance(value, str):
        return _scrub_string(value, repo)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _scrub_string(str(value), repo)


def _compact_evidence(value: Any, repo: Path) -> Any:
    safe = _safe_value(value, repo)
    try:
        encoded = json.dumps(safe, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        return {"summary": "evidence is not JSON serializable"}
    if len(encoded.encode("utf-8")) <= _MAX_EVIDENCE_ITEM:
        return safe
    if isinstance(safe, Mapping):
        preferred = (
            "schema",
            "schema_version",
            "run_id",
            "task",
            "status",
            "phase",
            "verification",
            "verdict",
            "item_complete",
            "summary",
            "next_action",
            "scope",
            "host",
            "checks",
            "localized_boundary",
            "candidate_commit",
            "failure_fingerprint",
            "stop_condition",
        )
        compact = {key: safe[key] for key in preferred if key in safe}
        compact["bounded"] = True
        return compact
    return {"bounded": True, "summary": str(encoded[:4_000])}


def _latest_evidence(repo: Path) -> list[dict[str, Any]]:
    root = repo / _EVIDENCE
    if not root.is_dir():
        return []
    candidates = [path for path in root.rglob("*.json") if path.is_file()]
    candidates.sort(key=lambda item: (item.stat().st_mtime_ns, item.as_posix()), reverse=True)
    result: list[dict[str, Any]] = []
    for path in candidates[:_MAX_EVIDENCE_FILES]:
        relative = path.relative_to(repo).as_posix()
        try:
            raw = path.read_bytes()
            parsed = json.loads(raw.decode("utf-8"))
            data: Any = _compact_evidence(parsed, repo)
        except (OSError, UnicodeError, json.JSONDecodeError):
            raw = b""
            data = {"parse": "unavailable"}
        result.append(
            {
                "path": relative,
                "bytes": len(raw),
                "sha256": _sha256_bytes(raw) if raw else None,
                "data": data,
            }
        )
    return result


def _active_task(canonical: Mapping[str, Any]) -> dict[str, Any] | None:
    active_id = canonical.get("active_task_id")
    tasks = canonical.get("tasks")
    if not isinstance(active_id, str) or not isinstance(tasks, list):
        return None
    for item in tasks:
        if isinstance(item, Mapping) and item.get("id") == active_id:
            return dict(item)
    return None


def _orchestration_hint(latest: list[dict[str, Any]]) -> dict[str, Any]:
    """A bounded sequence hint; it is not a substitute for host evidence."""

    return {
        "sequence": [
            "preserve_and_publish_candidate",
            "groupoperator_proxy_render_source_split",
            "nested_group_actual_fusion_micro_proof",
            "clipping_regression",
            "p4_09_real_fusion_reference_baseline",
            "difference_classification",
            "smallest_evidence_driven_repair",
        ],
        "next_workload": "GroupOperator proxy/render-source split implementation after the published clipping-island candidate",
        "gate_order": ["P4-08", "P4-HOST-PIXEL", "P4-09", "localized_repair"],
        "blocked_until_parity004_closure": ["PARITY-005", "PARITY-006"],
        "manager_packet_guard": "Every exact path belongs to exactly one of read_paths or write_paths; put only files intended to change in write_paths and use handoff_refs for immutable evidence. Worker context_budget.max_files must cover all exact read/write/handoff files plus the generated WORKER.md, task.json, and context-manifest.json (at least that total). Use repository-supported unittest/check.ps1 commands rather than assuming pytest is installed.",
        "manager_locate_guard": "EXACT_FILE requests must use the complete repository-relative filename (for example AGENTS.md, not AGENTS); every query must be non-empty and every path scope must exist in the repo map.",
        "coordinator_selection": {
            "goal_item_id": "PARITY-004",
            "workload": "GroupOperator proxy/render-source split",
            "immutable_read_paths": [
                ".control/PARITY-004_TODO.md",
                "docs/PARITY_004_HOST_PIXEL_GATE.md",
            ],
            "implementation_write_paths": [
                "psd2fusion/fusion_comp.py",
                "scripts/parity/p4_05.py",
                "tests/test_parity004_p405_graph.py",
            ],
            "minimum_worker_context_files": 9,
        },
        "latest_evidence_count": len(latest),
        "source": "repo-local canonical state plus current user workload instruction",
    }


def _atomic_json_write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as handle:
            temporary = handle.name
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary:
            try:
                Path(temporary).unlink()
            except OSError:
                pass


class PSD2FusionAdapter:
    """Minimal project adapter; generic orchestration remains in the harness."""

    adapter_id = "psd2fusion-parity-004"

    def load_goal_state(self, repo: Path) -> Mapping[str, Any]:
        root = Path(repo).resolve()
        canonical_raw = _read_json(root / _CURRENT)
        if not isinstance(canonical_raw, Mapping):
            raise ValueError(".control/current.json must contain an object")
        goal_text = _parity004_section(_read_text(root / _GOAL))
        todo_text = _read_text(root / _TODO)
        latest = _latest_evidence(root)
        active = _active_task(canonical_raw)
        validation = {
            "offline_check": _file_record(root, _CHECK),
            "remote_completion_guard": _file_record(root, _REMOTE_GUARD),
            "remote_completion_guard_python": _file_record(root, _REMOTE_GUARD_PY),
        }
        orchestration = _orchestration_hint(latest)
        goal = {
            "program_id": canonical_raw.get("program_id"),
            "active_task_id": canonical_raw.get("active_task_id"),
            "objective": "Advance PSD2Fusion PARITY-004 through the ordered Fusion host/pixel gates with fresh isolated roles and durable evidence.",
            "current_goal_path": _GOAL.as_posix(),
            "current_goal_markdown": _scrub_string(goal_text, root),
            "parity_todo_path": _TODO.as_posix(),
            "parity_todo_markdown": _scrub_string(todo_text, root),
            "validation": validation,
            "orchestration": orchestration,
            "read_only_reference_inputs": {
                "psd": "read-only external PSD; never materialize to a Worker",
                "reference_png": "read-only external reference PNG; never materialize to a Worker",
            },
        }
        state = {
            "canonical": _safe_value(canonical_raw, root),
            "active_task": _safe_value(active, root) if active is not None else None,
            "todo": _scrub_string(todo_text, root),
            "latest_evidence": latest,
            "validation": validation,
            "orchestration": orchestration,
        }
        return {"goal": goal, "state": state}

    def build_manager_goal_bundle(self, goal_state: Mapping[str, Any]) -> Mapping[str, Any]:
        if not isinstance(goal_state, Mapping):
            raise ValueError("goal_state must be an object")
        return {"goal": dict(goal_state.get("goal", {})), "state": dict(goal_state.get("state", {}))}

    def select_recover_active_task(
        self,
        goal_state: Mapping[str, Any],
        *,
        checkpoint: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any] | None:
        if isinstance(checkpoint, Mapping) and isinstance(checkpoint.get("task"), Mapping):
            return dict(checkpoint["task"])
        state = goal_state.get("state") if isinstance(goal_state, Mapping) else None
        if isinstance(state, Mapping) and isinstance(state.get("active_task"), Mapping):
            return dict(state["active_task"])
        return None

    def provide_project_test_env(self, task_packet: Mapping[str, Any]) -> Mapping[str, str]:
        del task_packet
        return {"PYTHONIOENCODING": "utf-8"}

    def reconcile_verified_result(
        self,
        repo: Path,
        *,
        goal_state: Mapping[str, Any],
        task_packet: Mapping[str, Any],
        patch: Mapping[str, Any],
        runner_tests: Mapping[str, Any],
        verifier_result: Mapping[str, Any],
        evidence: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        del repo, evidence
        task = task_packet.get("task", task_packet)
        if not isinstance(task, Mapping):
            raise ValueError("Task Packet task must be an object")
        run_id = task_packet.get("run_id")
        task_id = task.get("id")
        goal_item_id = task.get("goal_item_id")
        if not all(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value) for value in (run_id, task_id, goal_item_id)):
            raise ValueError("verified Task Packet identifiers are invalid")
        state = goal_state.get("state", {}) if isinstance(goal_state, Mapping) else {}
        orchestration = state.get("orchestration", {}) if isinstance(state, Mapping) else {}
        changed = patch.get("changed_paths", []) if isinstance(patch, Mapping) else []
        changed_paths = [str(path) for path in changed if isinstance(path, str)][:64]
        return {
            "schema": "psd2fusion-parity-004.harness-transition.v1",
            "status": "RECORDED",
            "run_id": run_id,
            "task_id": task_id,
            "goal_item_id": goal_item_id,
            "completion_scope": task.get("completion_scope"),
            "verifier_verdict": verifier_result.get("verdict"),
            "verifier_summary": _scrub_string(str(verifier_result.get("summary", "")), Path(repo).resolve())[:2_000],
            "runner_status": runner_tests.get("status"),
            "patch_sha256": patch.get("patch_sha256"),
            "changed_paths": changed_paths,
            "next_workload": orchestration.get("next_workload") if isinstance(orchestration, Mapping) else None,
            "evidence_relpath": f"{_HARNESS_EVIDENCE.as_posix()}/{run_id}/cycle-evidence.json",
            "canonical_state_mutation": "none; current.json remains the project verifier authority",
        }

    def apply_canonical_transition(self, repo: Path, transition: Mapping[str, Any]) -> Mapping[str, Any]:
        if transition.get("status") != "RECORDED":
            raise ValueError("PSD2Fusion adapter accepts only RECORDED transitions")
        run_id = transition.get("run_id")
        if not isinstance(run_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", run_id):
            raise ValueError("transition run_id is invalid")
        root = Path(repo).resolve()
        marker = root / _HARNESS_EVIDENCE / run_id / "adapter-transition.json"
        value = {
            "schema": "psd2fusion-parity-004.harness-transition-record.v1",
            "run_id": run_id,
            "status": "RECORDED",
            "transition": _safe_value(dict(transition), root),
            "canonical_state": {
                "path": _CURRENT.as_posix(),
                "mutation": "none",
                "active_task_remains": True,
            },
        }
        if marker.exists():
            try:
                existing = json.loads(marker.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise ValueError("existing adapter transition marker is unreadable") from exc
            if existing != value:
                raise ValueError("adapter transition marker conflicts with retained evidence")
        else:
            _atomic_json_write(marker, value)
        return {
            "status": "RECORDED",
            "run_id": run_id,
            "marker_relpath": marker.relative_to(root).as_posix(),
            "canonical_state_mutation": "none",
        }

    def summarize_project_state(self, repo: Path) -> Mapping[str, Any]:
        root = Path(repo).resolve()
        canonical = _read_json(root / _CURRENT)
        active = _active_task(canonical) if isinstance(canonical, Mapping) else None
        harness_current = root / _HARNESS_EVIDENCE / "current.json"
        current_cycle: dict[str, Any] = {}
        if harness_current.is_file():
            raw = _read_json(harness_current)
            if isinstance(raw, Mapping):
                current_cycle = {
                    key: raw.get(key)
                    for key in ("run_id", "status", "phase", "updated_at")
                    if key in raw
                }
        return {
            "adapter": self.adapter_id,
            "program_id": canonical.get("program_id") if isinstance(canonical, Mapping) else None,
            "active_task_id": canonical.get("active_task_id") if isinstance(canonical, Mapping) else None,
            "active_task_status": active.get("status") if isinstance(active, Mapping) else None,
            "active_task_verification": active.get("verification") if isinstance(active, Mapping) else None,
            "harness_current_cycle": current_cycle,
            "canonical_state_mutation_by_adapter": "none",
        }


__all__ = ["PSD2FusionAdapter"]
