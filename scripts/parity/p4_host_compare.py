"""Strictly compare PARITY-004 Fusion task artifacts with fixed oracle PNGs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Sequence

from PIL import Image

from scripts.parity.parity import compare_images


SCHEMA = "psd2fusion-parity-004-host-compare.v1"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact(path: Path) -> dict[str, Any]:
    with Image.open(path) as image:
        dimensions = [image.width, image.height]
        mode = image.mode
    return {
        "path": str(path.resolve()),
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "dimensions": dimensions,
        "mode": mode,
    }


def _records(path: Path, boundary: str) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        if not raw or raw.startswith("#"):
            continue
        fields = raw.split("\t")
        fields += [""] * (8 - len(fields))
        case_id, label, status, requested, artifact, render_ok, render_value, error = fields[:8]
        if label != boundary:
            continue
        if case_id in rows:
            raise ValueError("duplicate %s record for %s" % (boundary, case_id))
        rows[case_id] = {
            "boundary": label,
            "status": status,
            "requested": requested,
            "artifact": artifact,
            "render_ok": render_ok,
            "render_value": render_value,
            "error": error,
        }
    return rows


def compare_tasks(
    tasks_path: Path,
    records_path: Path,
    output: Path,
    boundary: str = "final",
) -> dict[str, Any]:
    tasks_path = tasks_path.resolve()
    records_path = records_path.resolve()
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    tasks = json.loads(tasks_path.read_text(encoding="utf-8"))
    cases = tasks.get("cases")
    if not isinstance(cases, dict) or not cases:
        raise ValueError("task manifest has no cases")
    records = _records(records_path, boundary)
    results: dict[str, Any] = {}
    stage_rows: dict[str, list[dict[str, Any]]] = {}
    for case_id, task in cases.items():
        record = records.get(case_id)
        stage = str(task.get("stage", "UNKNOWN"))
        if record is None or record["status"] != "ARTIFACT_READY":
            row = {
                "case": case_id,
                "stage": stage,
                "status": "BLOCKED",
                "strict_rgba_status": "BLOCKED",
                "reason": "missing successful host artifact record",
                "record": record,
            }
        else:
            candidate = Path(record["artifact"])
            reference = Path(str(task["expected"]))
            comparison = compare_images(
                candidate,
                reference,
                output / case_id / "diff",
                threshold=0.0,
            )
            row = {
                "case": case_id,
                "stage": stage,
                "record": record,
                "candidate": _artifact(candidate),
                "reference": _artifact(reference),
                "comparison": comparison,
                "status": comparison.get("status"),
                "strict_rgba_status": comparison.get(
                    "strict_rgba_status", comparison.get("status")
                ),
            }
        results[case_id] = row
        stage_rows.setdefault(stage, []).append(row)

    stages = {
        stage: {
            "case_count": len(rows),
            "strict_pass": sum(
                row["strict_rgba_status"] == "PASS" for row in rows
            ),
            "strict_fail": sum(
                row["strict_rgba_status"] == "FAIL" for row in rows
            ),
            "blocked": sum(
                row["strict_rgba_status"] == "BLOCKED" for row in rows
            ),
            "status": (
                "PASS"
                if all(row["strict_rgba_status"] == "PASS" for row in rows)
                else "FAIL"
            ),
        }
        for stage, rows in sorted(stage_rows.items())
    }
    strict_pass = all(
        row["strict_rgba_status"] == "PASS" for row in results.values()
    )
    report = {
        "schema": SCHEMA,
        "status": "PASS" if strict_pass else "FAIL",
        "strict_rgba_status": "PASS" if strict_pass else "FAIL",
        "threshold": 0,
        "threshold_policy": "strict; no non-zero RGBA delta is accepted",
        "tasks": str(tasks_path),
        "tasks_sha256": _sha256(tasks_path),
        "records": str(records_path),
        "records_sha256": _sha256(records_path),
        "boundary": boundary,
        "case_count": len(results),
        "stages": stages,
        "cases": results,
    }
    summary_path = output / "summary.json"
    summary_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report["summary"] = str(summary_path)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", required=True, type=Path)
    parser.add_argument("--records", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--boundary", default="final")
    args = parser.parse_args(argv)
    try:
        report = compare_tasks(args.tasks, args.records, args.output, args.boundary)
    except Exception as exc:
        print(json.dumps({"schema": SCHEMA, "status": "ERROR", "error": str(exc)}))
        return 2
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
