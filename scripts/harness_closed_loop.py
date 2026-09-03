"""Deterministic PSD2Fusion outer loop over codex-ephemeral-harness.

This is deliberately a thin supervisor.  The existing harness owns the
Manager/Worker/Verifier lifecycle, exact materialized slices, denial probes,
patch application, Runner tests, and durable role evidence.  The supervisor
only reloads PSD2Fusion canonical state between one-cycle calls, records
cross-system trace metadata, and chooses whether another bounded cycle is
permitted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import time
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any


ROLE_ORDER = ("manager-locate", "manager-plan", "worker", "verifier")
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_WORKER_EVIDENCE_PATH_CONTRACT = (
    "Worker result evidence paths are contract fields: emit only repository-relative POSIX paths "
    "exactly matching task.write_paths (for example psd2fusion/fusion_comp.py). Never emit an "
    "absolute path, Windows drive path, or isolated Temp workspace path."
)
_MANAGER_LOCATE_PATH_CONTRACT = (
    "For every EXACT_FILE discovery request, query must be the complete repository-relative filename "
    "and must exactly equal its sole path_scopes entry (for example query AGENTS.md with "
    "path_scopes [AGENTS.md]). Do not put a descriptive sentence in query; keep query non-empty."
)


class _PSD2FusionInvoker:
    """Project-only prompt guard around the generic invoker.

    The generic harness remains responsible for isolation, invocation,
    validation, patching, and evidence.  This wrapper supplies one workload
    contract that a Worker omitted in an observed production run; it does not
    rewrite role results or relax the generic validator.
    """

    def __init__(self, delegate: Any) -> None:
        self._delegate = delegate

    def invoke(self, **kwargs: Any) -> Any:
        role = kwargs.get("role")
        if role == "manager-locate":
            prompt = str(kwargs.get("prompt") or "")
            kwargs["prompt"] = f"{prompt}\n\n{_MANAGER_LOCATE_PATH_CONTRACT}"
        elif role == "worker":
            prompt = str(kwargs.get("prompt") or "")
            kwargs["prompt"] = f"{prompt}\n\n{_WORKER_EVIDENCE_PATH_CONTRACT}"
        return self._delegate.invoke(**kwargs)


def _load_harness(harness_root: Path) -> dict[str, Any]:
    source = harness_root / "src"
    if not source.is_dir():
        raise RuntimeError(f"Harness source directory is missing: {source}")
    value = str(source)
    if value not in sys.path:
        sys.path.insert(0, value)
    from codex_ephemeral_harness.agent import CodexExecInvoker
    from codex_ephemeral_harness.cycle import CycleOptions, run_production_cycle
    from codex_ephemeral_harness.evidence import DurableRoleEvidenceStore
    from codex_ephemeral_harness.isolation import (
        ReadIsolationUnavailable,
        resolve_codex_executable,
        run_windows_acceptance_probe,
    )

    return {
        "CodexExecInvoker": CodexExecInvoker,
        "CycleOptions": CycleOptions,
        "DurableRoleEvidenceStore": DurableRoleEvidenceStore,
        "ReadIsolationUnavailable": ReadIsolationUnavailable,
        "resolve_codex_executable": resolve_codex_executable,
        "run_production_cycle": run_production_cycle,
        "run_windows_acceptance_probe": run_windows_acceptance_probe,
    }


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _atomic_json_write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False
        ) as handle:
            temporary = handle.name
            handle.write(_json_bytes(value))
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


def _safe_id(value: str, label: str) -> str:
    if not isinstance(value, str) or not SAFE_ID.fullmatch(value):
        raise ValueError(f"{label} must be a safe identifier")
    return value


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_cycle_evidence(result: Mapping[str, Any], evidence_root: Path, run_id: str) -> Mapping[str, Any] | None:
    embedded = result.get("evidence")
    if isinstance(embedded, Mapping):
        return embedded
    path = evidence_root / run_id / "cycle-evidence.json"
    if not path.is_file():
        return None
    try:
        value = _read_json(path)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, Mapping) else None


def _harness_contract_defect(
    result: Mapping[str, Any], evidence_root: Path, run_id: str
) -> dict[str, Any] | None:
    """Classify a harness contract rejection separately from PSD2Fusion work.

    The generic Runner is authoritative for accepting a role result.  A role
    can therefore finish its isolated implementation while the cycle is still
    blocked by a serialization/contract error.  Keep that distinction explicit
    so a later adapter hint can repair the integration without treating the
    PSD workload as semantically failed.
    """

    evidence = _read_cycle_evidence(result, evidence_root, run_id)
    if not isinstance(evidence, Mapping):
        return None
    errors = evidence.get("errors")
    if not isinstance(errors, list):
        return None
    messages = [str(item) for item in errors if isinstance(item, str)]
    if not any("not an exact repository path" in item for item in messages):
        return None
    return {
        "kind": "WORKER_EVIDENCE_PATH_CONTRACT",
        "component": "codex-ephemeral-harness",
        "status": "OBSERVED",
        "project_failure": False,
        "details": messages[:8],
        "recovery": "instruct fresh Worker results to use repository-relative POSIX evidence paths; do not modify generic core",
    }


def _existing_in_progress_run(evidence_root: Path) -> str | None:
    """Return the generic journal's current unfinished run for safe recovery."""

    path = evidence_root / "current.json"
    if not path.is_file():
        return None
    try:
        value = _read_json(path)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    run_id = value.get("run_id") if isinstance(value, Mapping) else None
    status = value.get("status") if isinstance(value, Mapping) else None
    if isinstance(run_id, str) and SAFE_ID.fullmatch(run_id) and status == "IN_PROGRESS":
        if (evidence_root / run_id / "cycle.json").is_file():
            return run_id
    return None


def _scrub_exception(value: Any, repo: Path) -> str:
    text = str(value)
    variants = {
        str(repo),
        str(repo).replace("\\", "/"),
        str(repo).replace("/", "\\"),
    }
    for variant in sorted(variants, key=len, reverse=True):
        if variant:
            text = re.sub(re.escape(variant), "<canonical-repo>", text, flags=re.IGNORECASE)
    return text[:4_000]


def _materialized_read_sets(task: Mapping[str, Any] | None) -> dict[str, Any]:
    task_value = task.get("task", task) if isinstance(task, Mapping) else {}
    if not isinstance(task_value, Mapping):
        task_value = {}
    read_paths = [
        item.get("path")
        for item in task_value.get("read_paths", [])
        if isinstance(item, Mapping) and isinstance(item.get("path"), str)
    ]
    handoff_paths = [
        item.get("path")
        for item in task_value.get("handoff_refs", [])
        if isinstance(item, Mapping) and isinstance(item.get("path"), str)
    ]
    worker = sorted(set(read_paths + handoff_paths + [".harness/task.json", ".harness/context-manifest.json"]))
    return {
        "manager-locate": {
            "source": "generic-bundle-contract",
            "files": [
                ".harness/MANAGER_LOCATE.md",
                ".harness/goal.json",
                ".harness/state.json",
                ".harness/repo-map.json",
                ".harness/context-manifest.json",
            ],
        },
        "manager-plan": {
            "source": "generic-bundle-contract",
            "files": [
                ".harness/MANAGER_PLAN.md",
                ".harness/goal.json",
                ".harness/state.json",
                ".harness/discovery.json",
                ".harness/context-manifest.json",
            ],
        },
        "worker": {"source": "Task Packet exact read/handoff paths", "files": worker},
        "verifier": {
            "source": "generic-bundle-contract",
            "files": [
                ".harness/VERIFIER.md",
                ".harness/verifier-bundle.json",
                ".harness/context-manifest.json",
            ],
        },
    }


def _role_metrics(evidence: Mapping[str, Any] | None) -> dict[str, Any]:
    roles = evidence.get("roles", {}) if isinstance(evidence, Mapping) else {}
    if not isinstance(roles, Mapping):
        roles = {}
    result: dict[str, Any] = {}
    for role in ROLE_ORDER:
        value = roles.get(role)
        if not isinstance(value, Mapping):
            result[role] = {"present": False}
            continue
        isolation = value.get("isolation", {})
        if not isinstance(isolation, Mapping):
            isolation = {}
        result[role] = {
            "present": True,
            "role": role,
            "model": "gpt-5.6-luna",
            "reasoning_effort": "max",
            "thread_id": value.get("thread_id"),
            "ephemeral": value.get("ephemeral"),
            "input_tokens": value.get("input_tokens", 0),
            "cached_input_tokens": value.get("cached_input_tokens", 0),
            "uncached_input_tokens": value.get("uncached_input_tokens", 0),
            "output_tokens": value.get("output_tokens", 0),
            "wall_time_ms": value.get("wall_time_ms", 0),
            "model_visible_file_count": value.get("model_visible_file_count", 0),
            "model_visible_bytes": value.get("model_visible_bytes", 0),
            "external_read_denial": {
                "canonical": isolation.get("canonical_external_read"),
                "forbidden": isolation.get("forbidden_external_read"),
                "outside_write": isolation.get("outside_write"),
                "readonly_write": isolation.get("readonly_write"),
                "status": isolation.get("status"),
            },
        }
    return result


def _tests_summary(evidence: Mapping[str, Any] | None) -> dict[str, Any] | None:
    tests = evidence.get("runner_tests") if isinstance(evidence, Mapping) else None
    if not isinstance(tests, Mapping):
        return None
    results = tests.get("results", [])
    clean_results = []
    if isinstance(results, list):
        for item in results:
            if isinstance(item, Mapping):
                clean_results.append(
                    {
                        "command": item.get("command"),
                        "status": item.get("status"),
                        "exit_code": item.get("exit_code"),
                        "wall_time_ms": item.get("wall_time_ms"),
                        "stdout_sha256": item.get("stdout_sha256"),
                        "stderr_sha256": item.get("stderr_sha256"),
                    }
                )
    return {
        "status": tests.get("status"),
        "passed": tests.get("passed"),
        "failed": tests.get("failed"),
        "wall_time_ms": tests.get("wall_time_ms"),
        "results": clean_results,
    }


def _patch_summary(evidence: Mapping[str, Any] | None) -> dict[str, Any] | None:
    patch = evidence.get("patch") if isinstance(evidence, Mapping) else None
    if not isinstance(patch, Mapping):
        return None
    text = patch.get("patch")
    encoded = text.encode("utf-8") if isinstance(text, str) else b""
    changed = patch.get("changed_paths", [])
    return {
        "patch_sha256": patch.get("patch_sha256"),
        "changed_paths": [path for path in changed if isinstance(path, str)] if isinstance(changed, list) else [],
        "patch_bytes": len(encoded),
        "patch_lines": text.count("\n") if isinstance(text, str) else 0,
    }


def _task_packet_summary(task: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(task, Mapping):
        return {"present": False, "bytes": 0, "files": 0}
    payload = _json_bytes(task)
    task_value = task.get("task", task)
    files = 0
    if isinstance(task_value, Mapping):
        for key in ("read_paths", "write_paths", "handoff_refs"):
            value = task_value.get(key)
            if isinstance(value, list):
                files += len(value)
    return {
        "present": True,
        "bytes": len(payload),
        "files": files,
        "sha256": _sha256(payload),
        "task_id": task_value.get("id") if isinstance(task_value, Mapping) else None,
        "goal_item_id": task_value.get("goal_item_id") if isinstance(task_value, Mapping) else None,
    }


def _build_cycle_record(
    *,
    repo: Path,
    evidence_root: Path,
    run_id: str,
    result: Mapping[str, Any],
    devexec_task_id: str,
    supervisor_target: str,
    preflight: Mapping[str, Any],
) -> dict[str, Any]:
    evidence = _read_cycle_evidence(result, evidence_root, run_id)
    task = evidence.get("task") if isinstance(evidence, Mapping) else None
    verifier = evidence.get("verifier") if isinstance(evidence, Mapping) else None
    if not isinstance(verifier, Mapping):
        verifier = {}
    return {
        "schema": "psd2fusion-parity-004.supervisor-cycle.v1",
        "run_id": run_id,
        "devexec_task_id": devexec_task_id,
        "supervisor_target": supervisor_target,
        "project_task": "PARITY-004",
        "adapter": "psd2fusion-parity-004",
        "role_model": "gpt-5.6-luna",
        "reasoning_effort": "max",
        "status": result.get("status"),
        "phase": result.get("phase"),
        "evidence_relpath": f".control/evidence/PARITY-004/harness/{run_id}/cycle-evidence.json",
        "roles": _role_metrics(evidence),
        "metrics": evidence.get("metrics", {}) if isinstance(evidence, Mapping) else {},
        "task_packet": _task_packet_summary(task if isinstance(task, Mapping) else None),
        "materialized_read_sets": _materialized_read_sets(task if isinstance(task, Mapping) else None),
        "preflight_context_firewall": {
            "status": preflight.get("status"),
            "production_roles_launched": preflight.get("production_roles_launched"),
            "probes": preflight.get("probes", []),
        },
        "tests": _tests_summary(evidence),
        "patch": _patch_summary(evidence),
        "verdict": {
            "verifier": verifier.get("verdict"),
            "item_complete": verifier.get("item_complete"),
            "failure_fingerprint": verifier.get("failure_fingerprint"),
            "summary": str(verifier.get("summary", ""))[:2_000],
        },
        "sol_escalation": {"requested": False, "reason": None},
        "cycle_evidence_hash": _sha256(_json_bytes(evidence)) if isinstance(evidence, Mapping) else None,
        "canonical_state_mutation": "adapter marker only; .control/current.json unchanged",
        "repo_head_at_reload": _repo_head(repo),
    }


def _repo_head(repo: Path) -> str | None:
    # Avoid shelling out from the role boundary.  The branch/HEAD is already
    # captured by the Runner's git map; this optional hint is intentionally
    # absent when it cannot be obtained without changing process state.
    head_file = repo / ".git" / "HEAD"
    try:
        value = head_file.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return value[:200] if value else None


def _failure_fingerprint(record: Mapping[str, Any]) -> str | None:
    verdict = record.get("verdict")
    if isinstance(verdict, Mapping):
        value = verdict.get("failure_fingerprint")
        if isinstance(value, str) and value:
            return value
    return None


def _sol_reason(record: Mapping[str, Any], fingerprint_count: int) -> str | None:
    status = str(record.get("status") or "")
    if fingerprint_count >= 2:
        return "same verifier failure fingerprint did not converge in two bounded Luna cycles"
    if status not in {"VERIFIER_FAILED", "RETRY_STOP", "BLOCKED", "TEST_FAILED"}:
        return None
    text = json.dumps(record, ensure_ascii=False, sort_keys=True).casefold()
    markers = (
        "multiple lowerings",
        "conflicting evidence",
        "cannot determine",
        "architecture boundary",
        "fusion behavior",
        "semantic ambiguity",
    )
    if any(marker in text for marker in markers):
        return "focused cycle still leaves multiple semantic/Fusion/architecture explanations"
    return None


def _stop_decision(
    *,
    repo: Path,
    result: Mapping[str, Any],
    record: Mapping[str, Any],
    fingerprints: Mapping[str, int],
) -> tuple[bool, str, str | None]:
    status = str(result.get("status") or "UNKNOWN")
    if status in {"ISOLATION_FAILED", "HARNESS_EXCEPTION"}:
        return True, "HARNESS_FAIL_CLOSED", "generic Context Firewall/role process failed; recovery is required"
    if status in {"SOURCE_DRIFT", "RECOVERY_REQUIRED", "BLOCKED_CONTEXT_BUDGET"}:
        return True, status, str(result.get("error") or "cycle stopped by generic harness")
    current_path = repo / ".control" / "current.json"
    try:
        current = _read_json(current_path)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return True, "CANONICAL_STATE_UNREADABLE", "cannot reload PSD2Fusion current.json"
    if isinstance(current, Mapping):
        active = None
        tasks = current.get("tasks")
        if isinstance(tasks, list):
            for item in tasks:
                if isinstance(item, Mapping) and item.get("id") == current.get("active_task_id"):
                    active = item
                    break
        if current.get("status") == "done" or (
            isinstance(active, Mapping)
            and active.get("status") == "done"
            and active.get("verification") == "pass"
        ):
            return True, "PARITY_004_CLOSED", "canonical state reports verified closure"
    fingerprint = _failure_fingerprint(record)
    count = fingerprints.get(fingerprint, 0) if fingerprint else 0
    sol_reason = _sol_reason(record, count)
    if sol_reason:
        return True, "SOL_ESCALATION_REQUIRED", sol_reason
    if status == "NO_TASK":
        return True, "NO_TASK", "Manager found no active bounded Goal item"
    if status == "DONE":
        return False, "NEXT_CYCLE", "verified tranche recorded; reload canonical state/evidence"
    if status in {"BLOCKED", "VERIFIER_FAILED", "TEST_FAILED"}:
        return False, "NEXT_CYCLE_LOCALIZED", "bounded failure is eligible for a fresh Manager cycle"
    return True, status, str(result.get("error") or "unrecognized cycle status")


def _write_sol_escalation(
    evidence_root: Path,
    run_id: str,
    *,
    reason: str,
    record: Mapping[str, Any],
) -> str:
    path = evidence_root / run_id / "sol-escalation.json"
    value = {
        "schema": "psd2fusion-parity-004.sol-escalation.v1",
        "run_id": run_id,
        "project_task": "PARITY-004",
        "status": "REQUIRED",
        "reason": reason,
        "diagnostic_scope": [
            "semantic lowering alternatives",
            "observed Fusion behavior",
            "architecture boundary only if localized evidence requires it",
        ],
        "write_authority": "none",
        "input_cycle_record_hash": _sha256(_json_bytes(record)),
        "next_action": "obtain a fresh read-only Sol decision, persist it as evidence, then return implementation to fresh Luna Max",
    }
    _atomic_json_write(path, value)
    return path.relative_to(evidence_root.parent.parent.parent).as_posix()


def _make_codex_command(harness: Mapping[str, Any], args: argparse.Namespace, base_env: Mapping[str, str]) -> tuple[str, ...]:
    executable = args.codex_executable
    if executable:
        path = Path(executable).resolve()
    else:
        path = Path(harness["resolve_codex_executable"](base_env=base_env, platform_name=sys.platform))
    if not path.is_file():
        raise RuntimeError(f"Codex executable is missing: {path}")
    return (
        str(path),
        "-m",
        args.model,
        "-c",
        f'model_reasoning_effort="{args.reasoning_effort}"',
    )


def _run_dry(root: Path, harness_root: Path, args: argparse.Namespace) -> dict[str, Any]:
    harness = _load_harness(harness_root)
    from psd2fusion.harness_adapter import PSD2FusionAdapter

    adapter = PSD2FusionAdapter()
    temporary = Path(tempfile.mkdtemp(prefix="psd2fusion-ceh-dry-"))
    try:
        result = harness["run_production_cycle"](
            root,
            adapter,
            options=harness["CycleOptions"](
                evidence_root=temporary,
                run_id="dry-readiness",
                mode="dry",
                timeout_seconds=args.timeout,
                max_discovery_rounds=args.max_discovery_rounds,
                max_retries=args.max_retries,
                base_env=None,
            ),
        )
        return {
            "schema": "psd2fusion-parity-004.supervisor-dry.v1",
            "mode": "dry",
            "adapter": adapter.adapter_id,
            "status": result.get("status"),
            "phase": result.get("phase"),
            "goal_state_loaded": isinstance(result.get("evidence"), Mapping),
            "project_summary": result.get("evidence", {}).get("project_summary") if isinstance(result.get("evidence"), Mapping) else None,
            "mutation": "none in PSD2Fusion; temporary harness evidence removed",
        }
    finally:
        import shutil

        shutil.rmtree(temporary, ignore_errors=True)


def _run_probe(root: Path, harness_root: Path, args: argparse.Namespace) -> dict[str, Any]:
    harness = _load_harness(harness_root)
    base_env = dict(os.environ)
    command = _make_codex_command(harness, args, base_env)
    sentinel: Path | None = None
    if args.unrelated_sentinel:
        sentinel = Path(args.unrelated_sentinel).resolve(strict=True)
    else:
        handle = tempfile.NamedTemporaryFile(prefix="psd2fusion-ceh-sentinel-", suffix=".txt", delete=False)
        handle.write(b"unrelated-sentinel\n")
        handle.close()
        sentinel = Path(handle.name).resolve()
    try:
        result = harness["run_windows_acceptance_probe"](
            root,
            sentinel,
            codex_command=command,
            base_env=base_env,
            timeout_seconds=args.probe_timeout,
        )
        return {
            "schema": "psd2fusion-parity-004.context-firewall-probe.v1",
            "mode": "probe",
            "model": args.model,
            "reasoning_effort": args.reasoning_effort,
            **result,
        }
    finally:
        if not args.unrelated_sentinel and sentinel is not None:
            sentinel.unlink(missing_ok=True)


def _run_production(root: Path, harness_root: Path, args: argparse.Namespace) -> dict[str, Any]:
    harness = _load_harness(harness_root)
    from psd2fusion.harness_adapter import PSD2FusionAdapter

    adapter = PSD2FusionAdapter()
    evidence_root = (root / ".control" / "evidence" / "PARITY-004" / "harness").resolve()
    evidence_root.mkdir(parents=True, exist_ok=True)
    base_env = dict(os.environ)
    command = _make_codex_command(harness, args, base_env)
    preflight = _run_probe(root, harness_root, args)
    supervisor_target = args.supervisor_target
    devexec_task_id = args.devexec_task_id or os.environ.get("DEV_EXEC_RUN_ID") or "standalone-psd2fusion"
    _safe_id(supervisor_target, "supervisor_target")
    _safe_id(devexec_task_id, "devexec_task_id")
    if preflight.get("status") != "PASS":
        stop = {
            "schema": "psd2fusion-parity-004.supervisor-stop.v1",
            "status": "HARNESS_FAIL_CLOSED",
            "reason": "Context Firewall six-probe did not PASS; no production role launched",
            "devexec_task_id": devexec_task_id,
            "supervisor_target": supervisor_target,
            "preflight": preflight,
        }
        _atomic_json_write(evidence_root / "supervisor-stop.json", stop)
        return stop

    fingerprints: dict[str, int] = {}
    cycles: list[dict[str, Any]] = []
    stop_reason = "MAX_CYCLES"
    stop_detail: str | None = None
    # Recovery is opt-in.  A generic cycle journal can contain a completed
    # first-attempt role plus an unfinished later phase; blindly resuming can
    # collide with the harness' attempt store.  Normal closed-loop progress
    # therefore starts a fresh cycle, while an operator may explicitly choose
    # ``--resume-in-progress`` after inspecting the retained journal.
    resume_run_id = _existing_in_progress_run(evidence_root) if args.resume_in_progress else None
    for index in range(1, args.max_cycles + 1):
        run_id = (
            resume_run_id
            if index == 1 and resume_run_id is not None
            else f"p4-harness-{int(time.time())}-{index:03d}-{uuid.uuid4().hex[:8]}"
        )
        resume_run_id = None
        invoker = _PSD2FusionInvoker(harness["CodexExecInvoker"](
            codex_command=command,
            base_env=base_env,
            evidence_store=harness["DurableRoleEvidenceStore"](evidence_root),
        ))
        harness_defect: dict[str, Any] | None = None
        try:
            result = harness["run_production_cycle"](
                root,
                adapter,
                invoker=invoker,
                options=harness["CycleOptions"](
                    evidence_root=evidence_root,
                    run_id=run_id,
                    mode="production",
                    timeout_seconds=args.timeout,
                    max_discovery_rounds=args.max_discovery_rounds,
                    max_retries=args.max_retries,
                    base_env=base_env,
                ),
            )
        except Exception as exc:
            # Current CEH releases let a subprocess TimeoutExpired escape the
            # one-cycle wrapper. Preserve that defect separately and stop
            # closed; the unfinished CEH journal is recoverable by run_id.
            result = {
                "status": "HARNESS_EXCEPTION",
                "phase": "ROLE_PROCESS",
                "error_type": type(exc).__name__,
                "error": _scrub_exception(exc, root),
            }
            harness_defect = {
                "schema": "psd2fusion-parity-004.harness-defect.v1",
                "run_id": run_id,
                "component": "codex-ephemeral-harness",
                "status": "OBSERVED",
                "error_type": type(exc).__name__,
                "error": _scrub_exception(exc, root),
                "project_failure": False,
                "recovery": "re-run the same run_id only after operator review; no blind duplicate role launch",
            }
            _atomic_json_write(evidence_root / run_id / "harness-defect.json", harness_defect)
        if harness_defect is None:
            contract_defect = _harness_contract_defect(result, evidence_root, run_id)
            if contract_defect is not None:
                harness_defect = {
                    "schema": "psd2fusion-parity-004.harness-defect.v1",
                    "run_id": run_id,
                    **contract_defect,
                }
                _atomic_json_write(evidence_root / run_id / "harness-defect.json", harness_defect)
        record = _build_cycle_record(
            repo=root,
            evidence_root=evidence_root,
            run_id=run_id,
            result=result,
            devexec_task_id=devexec_task_id,
            supervisor_target=supervisor_target,
            preflight=preflight,
        )
        if harness_defect is not None:
            record["harness_defect"] = harness_defect
        fingerprint = _failure_fingerprint(record)
        if fingerprint:
            fingerprints[fingerprint] = fingerprints.get(fingerprint, 0) + 1
        record["fingerprint_count"] = fingerprints.get(fingerprint, 0) if fingerprint else 0
        should_stop, decision, detail = _stop_decision(
            repo=root, result=result, record=record, fingerprints=fingerprints
        )
        record["decision"] = decision
        record["decision_detail"] = detail
        cycle_path = evidence_root / run_id / "supervisor-cycle.json"
        _atomic_json_write(cycle_path, record)
        cycles.append({
            "run_id": run_id,
            "status": result.get("status"),
            "decision": decision,
            "evidence_relpath": cycle_path.relative_to(root).as_posix(),
        })
        _atomic_json_write(
            evidence_root / "supervisor-state.json",
            {
                "schema": "psd2fusion-parity-004.supervisor-state.v1",
                "project_task": "PARITY-004",
                "devexec_task_id": devexec_task_id,
                "supervisor_target": supervisor_target,
                "model": args.model,
                "reasoning_effort": args.reasoning_effort,
                "cycle_count": index,
                "last_run_id": run_id,
                "last_status": result.get("status"),
                "last_decision": decision,
                "fingerprints": fingerprints,
                "transcript_forwarded": False,
                "next_cycle_input": "fresh adapter reload of canonical state/evidence only",
            },
        )
        if should_stop:
            stop_reason, stop_detail = decision, detail
            if decision == "SOL_ESCALATION_REQUIRED":
                record["sol_escalation"] = {"requested": True, "reason": detail}
                _write_sol_escalation(evidence_root, run_id, reason=str(detail), record=record)
                _atomic_json_write(cycle_path, record)
            break
        if index == args.max_cycles:
            stop_reason = "MAX_CYCLES"
            stop_detail = detail or "bounded supervisor cycle budget exhausted"
        # Only the compact adapter/evidence files are read on the next pass;
        # no role result or transcript is copied into the next Task Packet.
        preflight = {"status": "PASS", "production_roles_launched": False, "probes": []}

    return {
        "schema": "psd2fusion-parity-004.supervisor-result.v1",
        "status": "STOPPED",
        "stop_reason": stop_reason,
        "stop_detail": stop_detail,
        "project_task": "PARITY-004",
        "adapter": adapter.adapter_id,
        "devexec_task_id": devexec_task_id,
        "supervisor_target": supervisor_target,
        "model": args.model,
        "reasoning_effort": args.reasoning_effort,
        "cycles": cycles,
        "evidence_root_relpath": evidence_root.relative_to(root).as_posix(),
        "transcript_forwarded": False,
    }


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="psd2fusion-harness-loop")
    root.add_argument("--repo", default=str(Path(__file__).resolve().parents[1]))
    root.add_argument("--harness-root", default=r"D:\Documents\codex-ephemeral-harness")
    root.add_argument("--mode", choices=("dry", "probe", "production"), default="dry")
    root.add_argument("--unrelated-sentinel")
    root.add_argument("--probe-timeout", type=int, default=120)
    root.add_argument("--timeout", type=int, default=600)
    root.add_argument("--max-discovery-rounds", type=int, default=2)
    root.add_argument("--max-retries", type=int, default=1)
    root.add_argument("--max-cycles", type=int, default=8)
    root.add_argument("--resume-in-progress", action="store_true")
    root.add_argument("--model", default="gpt-5.6-luna")
    root.add_argument("--reasoning-effort", default="max")
    root.add_argument("--codex-executable")
    root.add_argument("--devexec-task-id")
    root.add_argument("--supervisor-target", default="knotfield-harness-supervisor")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    repo = Path(args.repo).resolve()
    harness_root = Path(args.harness_root).resolve()
    if not repo.is_dir():
        raise SystemExit(f"PSD2Fusion repository is missing: {repo}")
    try:
        if args.mode == "dry":
            result = _run_dry(repo, harness_root, args)
        elif args.mode == "probe":
            result = _run_probe(repo, harness_root, args)
        else:
            result = _run_production(repo, harness_root, args)
    except Exception as exc:
        result = {
            "schema": "psd2fusion-parity-004.supervisor-error.v1",
            "status": "HARNESS_FAIL_CLOSED",
            "error_type": type(exc).__name__,
            "error": str(exc)[:2_000],
            "production_roles_launched": False,
        }
    # The Windows console may still use a legacy code page.  Keep durable JSON
    # UTF-8 above, but make the outer process stdout ASCII-safe for Dev Exec and
    # direct PowerShell invocation.
    print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
    return 0 if result.get("status") in {"DRY_RUN", "PASS", "STOPPED"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
