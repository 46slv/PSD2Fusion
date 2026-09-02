"""Validate PSD2Fusion's canonical compositing-parity state."""

from __future__ import annotations

import json
from pathlib import Path, PureWindowsPath
from typing import Any


ALLOWED_TASK_STATUS = {
    "blocked", "ready", "in_progress", "awaiting_verification", "done",
    "blocked_host", "blocked_authority", "deferred",
}
ALLOWED_VERIFICATION = {"pending", "pass", "fail", "blocked"}


def _load(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"missing file: {path}")
        return {}
    except json.JSONDecodeError as exc:
        errors.append(f"invalid JSON in {path}: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"expected JSON object: {path}")
        return {}
    return value


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    state_path = root / ".control" / "current.json"
    schema_path = root / ".control" / "state.schema.json"
    state = _load(state_path, errors)
    schema = _load(schema_path, errors)
    if not state or not schema:
        return errors

    required = {
        "schema_version", "program_id", "status", "baseline", "reference_case",
        "active_task_id", "task_contract", "tasks", "transition_rule",
    }
    missing = sorted(required.difference(state))
    if missing:
        errors.append("state missing keys: " + ", ".join(missing))
    if state.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if state.get("program_id") != "PSD2FUSION-COMPOSITING-PARITY":
        errors.append("unexpected program_id")

    contract_value = state.get("task_contract")
    if not isinstance(contract_value, str) or not contract_value:
        errors.append("task_contract must be a repo-relative path")
        contract_text = ""
    else:
        contract_path = root / contract_value
        if not contract_path.is_file():
            errors.append(f"missing task contract: {contract_value}")
            contract_text = ""
        else:
            contract_text = contract_path.read_text(encoding="utf-8")

    reference = state.get("reference_case")
    if not isinstance(reference, dict):
        errors.append("reference_case must be an object")
    else:
        for key in ("psd_path_windows", "reference_png_path_windows"):
            value = reference.get(key)
            if not isinstance(value, str) or not PureWindowsPath(value).is_absolute():
                errors.append(f"reference_case.{key} must be an absolute Windows path")
        if reference.get("read_only") is not True:
            errors.append("reference inputs must be read_only=true")
        if reference.get("commit_inputs_or_full_renders") is not False:
            errors.append("real inputs/full renders must not be committed")

    tasks = state.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        errors.append("tasks must be a non-empty array")
        return errors

    by_id: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(tasks):
        if not isinstance(raw, dict):
            errors.append(f"tasks[{index}] must be an object")
            continue
        task_id = raw.get("id")
        if not isinstance(task_id, str) or not task_id:
            errors.append(f"tasks[{index}].id must be a non-empty string")
            continue
        if task_id in by_id:
            errors.append(f"duplicate task id: {task_id}")
        by_id[task_id] = raw
        if f"### {task_id} " not in contract_text:
            errors.append(f"task contract has no section for {task_id}")
        if raw.get("status") not in ALLOWED_TASK_STATUS:
            errors.append(f"{task_id}: invalid status {raw.get('status')!r}")
        if raw.get("verification") not in ALLOWED_VERIFICATION:
            errors.append(f"{task_id}: invalid verification {raw.get('verification')!r}")
        if raw.get("status") == "done" and raw.get("verification") != "pass":
            errors.append(f"{task_id}: done requires verification=pass")

    active_id = state.get("active_task_id")
    if active_id not in by_id:
        errors.append(f"active_task_id does not identify a task: {active_id!r}")
    elif by_id[active_id].get("status") in {"done", "deferred"}:
        errors.append("active task cannot be done or deferred")

    for task_id, task in by_id.items():
        requires = task.get("requires")
        if not isinstance(requires, list):
            errors.append(f"{task_id}: requires must be an array")
            continue
        for dependency in requires:
            if dependency not in by_id:
                errors.append(f"{task_id}: unknown dependency {dependency!r}")
            if dependency == task_id:
                errors.append(f"{task_id}: task cannot depend on itself")

    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    errors = validate(root)
    print(json.dumps({
        "ok": not errors,
        "state": str(root / ".control" / "current.json"),
        "errors": errors,
    }, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
