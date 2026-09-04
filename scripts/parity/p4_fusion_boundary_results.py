"""Summarize actual-Fusion boundary probe records.

The host probe deliberately writes a small TSV rather than attempting to
serialize JSON from Fusion's Lua runtime.  This module is the offline part of
the contract: it validates the fixture manifest, reads only artifacts named by
the probe, records file/image facts, and compares decoded RGBA pixels between
the ungrouped and isolated case for each mode/boundary.  It has no formula
oracle and does not label either output as correct.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

try:
    from PIL import Image
except ImportError:  # pragma: no cover - exercised by the caller's environment
    Image = None  # type: ignore[assignment]


SCHEMA = "psd2fusion-parity-004-fusion-boundary-results.v1"
FIXTURE_SCHEMA = "psd2fusion-parity-004-fusion-boundary-fixture.v1"
RECORD_FIELDS = (
    "case_id",
    "boundary",
    "status",
    "requested_path",
    "artifact_path",
    "render_ok",
    "render_value",
    "error",
)
BASE_BOUNDARIES = (
    "base_loader",
    "member_loader",
    "clip_in",
    "channel_boolean.base_opaque",
    "channel_boolean.member_opaque",
    "channel_boolean.coverage",
    "channel_boolean.restore_alpha",
    "blend_function",
    "clip_stack",
    "parent_merge",
)


def expected_boundaries(case: Mapping[str, Any]) -> List[str]:
    """Return the required materialization labels for one manifest case."""

    labels = list(BASE_BOUNDARIES)
    group = case.get("boundaries", {}).get("group")
    if group:
        # The GroupOperator proxy itself is useful when the host exposes an
        # output port, but the internal terminal and parent merge are the
        # required group-scope boundaries.
        labels.extend(("group_internal_terminal", "group_parent_merge"))
    return labels


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _path_key(value: str) -> str:
    return value.replace("\\", "/")


def _read_records(path: Path) -> Tuple[Dict[Tuple[str, str], Dict[str, Any]], List[str]]:
    records: Dict[Tuple[str, str], Dict[str, Any]] = {}
    errors: List[str] = []
    if not path.is_file():
        return records, ["records_missing:%s" % path]
    for line_number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not raw or raw.startswith("#"):
            continue
        fields = raw.split("\t")
        if len(fields) != len(RECORD_FIELDS):
            errors.append("record_fields:%d:%d" % (line_number, len(fields)))
            continue
        record = dict(zip(RECORD_FIELDS, fields))
        key = (record["case_id"], record["boundary"])
        if key in records:
            errors.append("duplicate_record:%s:%s" % key)
            continue
        records[key] = record
    return records, errors


def _safe_artifact(path_text: str, artifact_root: Optional[Path]) -> Tuple[Optional[Path], Optional[str]]:
    if not path_text:
        return None, "artifact_path_empty"
    path = Path(path_text)
    try:
        resolved = path.resolve()
    except OSError as exc:
        return None, "artifact_path_resolve:%s" % exc
    if artifact_root is not None:
        try:
            resolved.relative_to(artifact_root.resolve())
        except ValueError:
            return None, "artifact_outside_run_root"
    return resolved, None


def _artifact_fact(path: Path) -> Dict[str, Any]:
    fact: Dict[str, Any] = {
        "path": str(path),
        "path_normalized": _path_key(str(path)),
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }
    if Image is None:
        fact["error"] = "Pillow_unavailable"
        return fact
    try:
        with Image.open(path) as image:
            image.load()
            rgba = image.convert("RGBA")
            width, height = rgba.size
            points = ((0, 0), (width // 2, height // 2), (width - 1, height - 1))
            samples = {
                "%d,%d" % point: list(rgba.getpixel(point))
                for point in points
            }
            fact.update(
                {
                    "format": image.format,
                    "mode": image.mode,
                    "dimensions": [width, height],
                    "rgba_sample": samples["0,0"],
                    "rgba_samples": samples,
                    "alpha_min": min(pixel[3] for pixel in rgba.getdata()),
                    "alpha_max": max(pixel[3] for pixel in rgba.getdata()),
                }
            )
    except Exception as exc:  # Pillow raises several format-specific classes.
        fact["error"] = "image_read:%s" % exc
    return fact


def _rgba_pixels(path: Path) -> Tuple[Optional[Tuple[int, int]], Optional[List[Tuple[int, int, int, int]]], Optional[str]]:
    if Image is None:
        return None, None, "Pillow_unavailable"
    try:
        with Image.open(path) as image:
            image.load()
            rgba = image.convert("RGBA")
            return rgba.size, list(rgba.getdata()), None
    except Exception as exc:
        return None, None, "image_read:%s" % exc


def _compare(left: Path, right: Path) -> Dict[str, Any]:
    left_size, left_pixels, left_error = _rgba_pixels(left)
    right_size, right_pixels, right_error = _rgba_pixels(right)
    result: Dict[str, Any] = {
        "left": str(left),
        "right": str(right),
        "status": "UNAVAILABLE",
        "claim": "difference_only",
    }
    if left_error or right_error:
        result["error"] = {"left": left_error, "right": right_error}
        return result
    assert left_size is not None and right_size is not None
    assert left_pixels is not None and right_pixels is not None
    result["dimensions"] = {"left": list(left_size), "right": list(right_size)}
    if left_size != right_size:
        result["status"] = "DIMENSION_DIFFERENCE"
        return result
    count = min(len(left_pixels), len(right_pixels))
    different = 0
    max_delta = 0
    total_delta = 0
    first_difference: Optional[Dict[str, Any]] = None
    for index in range(count):
        left_pixel = left_pixels[index]
        right_pixel = right_pixels[index]
        deltas = [abs(int(a) - int(b)) for a, b in zip(left_pixel, right_pixel)]
        if any(deltas):
            different += 1
            if first_difference is None:
                width = left_size[0]
                first_difference = {
                    "xy": [index % width, index // width],
                    "left": list(left_pixel),
                    "right": list(right_pixel),
                }
        max_delta = max(max_delta, max(deltas))
        total_delta += sum(deltas)
    result.update(
        {
            "status": "MATCH" if different == 0 else "DIFFERENT",
            "pixel_count": count,
            "different_pixel_count": different,
            "max_channel_abs_delta": max_delta,
            "mean_channel_abs_delta": total_delta / float(max(count * 4, 1)),
            "first_difference": first_difference,
        }
    )
    return result


def _manifest_errors(manifest: Mapping[str, Any]) -> List[str]:
    errors: List[str] = []
    if manifest.get("schema") != FIXTURE_SCHEMA:
        errors.append("fixture_schema:%s" % manifest.get("schema"))
    if manifest.get("task") != "PARITY-004" or manifest.get("item") != "P4-HOST-PIXEL":
        errors.append("fixture_task_or_item")
    if manifest.get("formula_oracle") != "not used":
        errors.append("formula_oracle_not_explicitly_unused")
    if manifest.get("pixel_claim") != "none":
        errors.append("fixture_pixel_claim_not_none")
    cases = manifest.get("cases")
    order = manifest.get("case_order")
    if not isinstance(cases, Mapping) or not isinstance(order, Sequence) or len(order) != 8:
        errors.append("fixture_case_set")
    elif set(order) != set(cases):
        errors.append("fixture_case_order_mismatch")
    return errors


def analyze(manifest_path: Path, records_path: Path, output_path: Path, artifact_root: Optional[Path] = None) -> Dict[str, Any]:
    """Read one host result TSV and write a durable machine summary."""

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors = _manifest_errors(manifest)
    records, record_errors = _read_records(records_path)
    errors.extend(record_errors)
    cases = manifest.get("cases", {})
    case_reports: MutableMapping[str, Dict[str, Any]] = {}
    all_required_ready = True

    for case_id in manifest.get("case_order", []):
        case = cases[case_id]
        boundary_reports: MutableMapping[str, Dict[str, Any]] = {}
        for label in expected_boundaries(case):
            record = records.get((case_id, label))
            report: Dict[str, Any] = {
                "status": "MISSING_RECORD",
                "required": True,
            }
            if record is not None:
                report.update(
                    {
                        "status": record["status"],
                        "render_ok": record["render_ok"],
                        "render_value": record["render_value"],
                    }
                )
                artifact, path_error = _safe_artifact(record["artifact_path"], artifact_root)
                if artifact is not None and artifact.is_file():
                    fact = _artifact_fact(artifact)
                    report["artifact"] = fact
                    if "error" in fact or "dimensions" not in fact:
                        all_required_ready = False
                        report["status"] = "ARTIFACT_INVALID"
                    else:
                        report["status"] = "ARTIFACT_READY"
                else:
                    all_required_ready = False
                    report["status"] = "ARTIFACT_MISSING"
                    report["artifact_error"] = path_error or "artifact_file_missing"
                if record["error"]:
                    report["error"] = record["error"]
            else:
                all_required_ready = False
            boundary_reports[label] = report
        case_reports[case_id] = {
            "id": case_id,
            "mode": case.get("mode"),
            "scope": case.get("scope"),
            "boundaries": boundary_reports,
        }

    comparisons: MutableMapping[str, Dict[str, Any]] = {}
    for mode in manifest.get("modes", []):
        left_id = "%s_ungrouped" % mode.lower().replace(" ", "_")
        right_id = "%s_isolated" % mode.lower().replace(" ", "_")
        left_case = case_reports.get(left_id)
        right_case = case_reports.get(right_id)
        mode_comparisons: MutableMapping[str, Dict[str, Any]] = {}
        if left_case is not None and right_case is not None:
            labels = set(left_case["boundaries"]) | set(right_case["boundaries"])
            for label in sorted(labels):
                left_report = left_case["boundaries"].get(label, {})
                right_report = right_case["boundaries"].get(label, {})
                left_artifact = left_report.get("artifact", {}).get("path")
                right_artifact = right_report.get("artifact", {}).get("path")
                if left_artifact and right_artifact:
                    mode_comparisons[label] = _compare(Path(left_artifact), Path(right_artifact))
                else:
                    mode_comparisons[label] = {
                        "status": "UNAVAILABLE",
                        "claim": "difference_only",
                        "reason": "one_or_both_artifacts_missing",
                    }
        comparisons[mode] = mode_comparisons

    summary: Dict[str, Any] = {
        "schema": SCHEMA,
        "task": "PARITY-004",
        "item": "P4-HOST-PIXEL",
        "status": "PASS" if all_required_ready and not errors else "BLOCKED",
        "ready": bool(all_required_ready and not errors),
        "pixel_claim": "none",
        "formula_oracle": "not used",
        "manifest": str(manifest_path),
        "records": str(records_path),
        "artifact_root": str(artifact_root) if artifact_root else None,
        "errors": errors,
        "cases": case_reports,
        "comparisons": comparisons,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path)
    args = parser.parse_args(argv)
    try:
        summary = analyze(args.manifest, args.records, args.output, args.artifact_root)
    except Exception as exc:
        payload = {
            "schema": SCHEMA,
            "task": "PARITY-004",
            "item": "P4-HOST-PIXEL",
            "status": "BLOCKED",
            "ready": False,
            "pixel_claim": "none",
            "formula_oracle": "not used",
            "errors": ["analyzer_exception:%s" % exc],
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        return 3
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if summary["ready"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
