"""Prepare the fixed PARITY-004 matrix for actual Resolve/Fusion probes.

The PSDFixtureForge production matrix remains the immutable oracle input.  For
the H1 cases only, this helper moves ``canvas.background`` to an explicit
bottom pixel layer with the same RGBA bytes and resets the implicit canvas to
transparent.  The transformation is intentionally mechanical: a fixed-oracle
render before and after it must be byte-identical.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCHEMA = "psd2fusion-parity-004-actual-matrix.v1"
H1_CASES = (
    "basic-pixel",
    "fractional-alpha-opacity",
    "multiply",
    "screen",
)
H3_CONTROL_SOURCES = (
    "nested-isolated-group",
    "pass-through-group",
)
CASE_STAGE = {
    "basic-pixel": "H1",
    "fractional-alpha-opacity": "H1",
    "multiply": "H1",
    "screen": "H1",
    "clipping-one-member": "H2",
    "clipping-multi-member": "H2",
    "group-clipping": "H2",
    "nested-isolated-group": "H3",
    "pass-through-group": "H3",
    "nested-isolated-group--ungrouped-control": "H3",
    "pass-through-group--ungrouped-control": "H3",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _background(spec: Mapping[str, Any]) -> list[int]:
    canvas = spec.get("canvas", {})
    value = canvas.get("background", [0, 0, 0, 0])
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError("canvas.background must be four RGBA integers")
    channels = [int(channel) for channel in value]
    if any(channel < 0 or channel > 255 for channel in channels):
        raise ValueError("canvas.background channels must be in [0, 255]")
    return channels


def _flatten_groups(layers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return the same leaf inputs without group scope.

    The two fixed H3 fixtures have no group offsets.  Failing closed here
    avoids silently changing geometry if the fixed matrix ever evolves.
    """

    flattened: list[dict[str, Any]] = []
    for layer in layers:
        if layer.get("type") != "group":
            flattened.append(copy.deepcopy(layer))
            continue
        if int(layer.get("x", 0)) != 0 or int(layer.get("y", 0)) != 0:
            raise ValueError("H3 control cannot flatten a positioned group")
        children = layer.get("layers")
        if not isinstance(children, list):
            raise ValueError("H3 group has no layers array")
        flattened.extend(_flatten_groups(children))
    return flattened


def prepare(source: Path, output_directory: Path) -> dict[str, Any]:
    source = source.resolve()
    output_directory = output_directory.resolve()
    raw = json.loads(source.read_text(encoding="utf-8"))
    cases = raw.get("cases")
    if not isinstance(cases, list) or len(cases) != 9:
        raise ValueError("the fixed production matrix must contain nine cases")

    derived = copy.deepcopy(raw)
    source_by_name = {
        str(entry.get("name", "")): entry for entry in raw["cases"]
    }
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in derived["cases"]:
        name = str(entry.get("name", ""))
        if not name or name in seen:
            raise ValueError("matrix case names must be non-empty and unique")
        seen.add(name)
        if name not in H1_CASES:
            continue

        spec = entry.get("spec")
        if not isinstance(spec, dict):
            raise ValueError("case %s has no spec object" % name)
        canvas = spec.get("canvas")
        layers = spec.get("layers")
        if not isinstance(canvas, dict) or not isinstance(layers, list):
            raise ValueError("case %s must have canvas and layers" % name)
        width = int(canvas["width"])
        height = int(canvas["height"])
        rgba = _background(spec)
        explicit_name = "P4 explicit canvas backdrop: %s" % name
        canvas["background"] = [0, 0, 0, 0]
        layers.insert(
            0,
            {
                "type": "pixel",
                "name": explicit_name,
                "width": width,
                "height": height,
                "primitive": {"type": "solid", "color": rgba},
            },
        )
        records.append(
            {
                "case": name,
                "explicit_layer_name": explicit_name,
                "rgba8": rgba,
                "dimensions": [width, height],
                "implicit_background_after": [0, 0, 0, 0],
            }
        )

    if tuple(record["case"] for record in records) != H1_CASES:
        raise ValueError("fixed H1 case set/order changed")

    output_directory.mkdir(parents=True, exist_ok=True)
    matrix_path = output_directory / "matrix-explicit-background.json"
    matrix_path.write_text(
        json.dumps(derived, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    control_cases: list[dict[str, Any]] = []
    for source_name in H3_CONTROL_SOURCES:
        source_entry = source_by_name.get(source_name)
        if source_entry is None:
            raise ValueError("fixed H3 source case missing: %s" % source_name)
        control_spec = copy.deepcopy(source_entry["spec"])
        control_spec["layers"] = _flatten_groups(control_spec["layers"])
        control_cases.append(
            {
                "name": source_name + "--ungrouped-control",
                "spec": control_spec,
            }
        )
    controls_path = output_directory / "matrix-h3-ungrouped-controls.json"
    controls_path.write_text(
        json.dumps(
            {"cases": control_cases},
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    report = {
        "schema": SCHEMA,
        "status": "PASS",
        "source_matrix": str(source),
        "source_matrix_sha256": _sha256(source),
        "derived_matrix": str(matrix_path),
        "derived_matrix_sha256": _sha256(matrix_path),
        "h3_controls_matrix": str(controls_path),
        "h3_controls_matrix_sha256": _sha256(controls_path),
        "h3_controls": [entry["name"] for entry in control_cases],
        "case_count": len(cases),
        "h1_cases": list(H1_CASES),
        "transformations": records,
        "oracle_equivalence": "PENDING_FIXED_ORACLE_RENDER_COMPARISON",
    }
    report_path = output_directory / "preparation.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report["report"] = str(report_path)
    return report


def build_final_tasks(
    fixture_roots: Sequence[Path], tasks_path: Path
) -> dict[str, Any]:
    """Write sync-probe tasks for every fixed/derived final render."""

    tasks_path = tasks_path.resolve()
    artifact_root = tasks_path.parent / "artifacts"
    cases: dict[str, dict[str, Any]] = {}
    for fixture_root in fixture_roots:
        for case_root in sorted(fixture_root.resolve().iterdir()):
            if not case_root.is_dir():
                continue
            manifest_path = case_root / "psd2fusion" / "manifest.json"
            expected_path = case_root / "expected.png"
            if not manifest_path.is_file() or not expected_path.is_file():
                continue
            case_id = case_root.name
            if case_id in cases:
                raise ValueError("duplicate discovered case: %s" % case_id)
            if case_id not in CASE_STAGE:
                raise ValueError("unexpected discovered case: %s" % case_id)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            final_tool = manifest.get("graph", {}).get("final_tool")
            comp_path = case_root / "psd2fusion" / "PSD2Fusion.comp"
            if not isinstance(final_tool, str) or not comp_path.is_file():
                raise ValueError("case %s lacks a renderable final tool" % case_id)
            try:
                comp_argument = comp_path.resolve().relative_to(ROOT).as_posix()
            except ValueError:
                comp_argument = str(comp_path.resolve())
            cases[case_id] = {
                "id": case_id,
                "stage": CASE_STAGE[case_id],
                "comp": str(comp_path.resolve()),
                "comp_argument": comp_argument,
                "expected": str(expected_path.resolve()),
                "final_tool": final_tool,
                "output": str((artifact_root / case_id).resolve()),
            }

    if set(cases) != set(CASE_STAGE):
        missing = sorted(set(CASE_STAGE) - set(cases))
        extra = sorted(set(cases) - set(CASE_STAGE))
        raise ValueError("actual matrix case set mismatch; missing=%s extra=%s" % (missing, extra))

    artifact_root.mkdir(parents=True, exist_ok=True)
    for case in cases.values():
        Path(case["output"]).mkdir(parents=True, exist_ok=True)
    lines = [
        "\t".join(
            (
                case_id,
                cases[case_id]["stage"],
                cases[case_id]["comp_argument"],
                cases[case_id]["output"],
                "final=" + cases[case_id]["final_tool"],
            )
        )
        for case_id in CASE_STAGE
    ]
    tasks_path.parent.mkdir(parents=True, exist_ok=True)
    tasks_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report = {
        "schema": SCHEMA,
        "status": "PASS",
        "kind": "final-render-tasks",
        "tasks": str(tasks_path),
        "tasks_sha256": _sha256(tasks_path),
        "artifact_root": str(artifact_root.resolve()),
        "case_count": len(cases),
        "cases": cases,
    }
    report_path = tasks_path.parent / "tasks.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report["report"] = str(report_path)
    return report


def build_boundary_tasks(
    tasks_manifest: Path,
    tasks_path: Path,
    only_cases: Sequence[str] = (),
) -> dict[str, Any]:
    """Select the minimum H2/H3 render taps required by the closure gate."""

    from scripts.parity.p4_fusion_boundary_fixture import _group_block, _instance_source
    from scripts.validate_clipping_subtrees import parse_tools

    source = json.loads(tasks_manifest.resolve().read_text(encoding="utf-8"))
    source_cases = source.get("cases", {})
    tasks_path = tasks_path.resolve()
    artifact_root = tasks_path.parent / "artifacts"
    artifact_root.mkdir(parents=True, exist_ok=True)

    def tool_names(tools: list[Mapping[str, Any]], prefix: str) -> list[str]:
        return [str(tool["name"]) for tool in tools if str(tool.get("name", "")).startswith(prefix)]

    def comment_tool(tools: list[Mapping[str, Any]], text: str, tool_type: str | None = None) -> str:
        matches = [
            str(tool["name"])
            for tool in tools
            if text in str(tool.get("comments", ""))
            and (tool_type is None or tool.get("type") == tool_type)
        ]
        if len(matches) != 1:
            raise ValueError("expected one %s tool, found %s" % (text, matches))
        return matches[0]

    selected: dict[str, dict[str, Any]] = {}
    ordered_cases = (
        "clipping-one-member",
        "clipping-multi-member",
        "group-clipping",
        "nested-isolated-group",
        "pass-through-group",
    )
    selected_filter = set(only_cases)
    unknown_filter = selected_filter - set(ordered_cases)
    if unknown_filter:
        raise ValueError("unknown boundary case filter: %s" % sorted(unknown_filter))
    for case_id in ordered_cases:
        if selected_filter and case_id not in selected_filter:
            continue
        case = source_cases.get(case_id)
        if not isinstance(case, dict):
            raise ValueError("tasks manifest lacks case %s" % case_id)
        comp_path = Path(case["comp"])
        tools = [dict(tool) for tool in parse_tools(comp_path)]
        boundaries: list[tuple[str, str]] = []

        if case_id == "clipping-one-member":
            boundaries.extend(
                (
                    ("base_loader_straight", comment_tool(tools, "PSD layer: clip-base", "Loader")),
                    ("base_float32", comment_tool(tools, "PSD layer float32 materialization: clip-base", "ChangeDepth")),
                    ("fixed_base_matte", comment_tool(tools, "PSD layer premultiply: clip-base", "AlphaMultiply")),
                    ("clip_in", tool_names(tools, "ClipIn")[0]),
                    ("blend_function", tool_names(tools, "BlendFunction")[0]),
                    ("process_alpha_stack", tool_names(tools, "ClipStack")[0]),
                )
            )
        elif case_id == "clipping-multi-member":
            boundaries.extend(
                (
                    ("base_loader_straight", comment_tool(tools, "PSD layer: multi-base", "Loader")),
                    ("base_float32", comment_tool(tools, "PSD layer float32 materialization: multi-base", "ChangeDepth")),
                    ("fixed_base_matte", comment_tool(tools, "PSD layer premultiply: multi-base", "AlphaMultiply")),
                )
            )
            clips = tool_names(tools, "ClipIn")
            functions = tool_names(tools, "BlendFunction")
            stacks = tool_names(tools, "ClipStack")
            if not (len(clips) == len(functions) == len(stacks) == 2):
                raise ValueError("multi-member boundary cardinality changed")
            for index in range(2):
                member = index + 1
                boundaries.extend(
                    (
                        ("member_%d_clip_in" % member, clips[index]),
                        ("member_%d_blend_function" % member, functions[index]),
                        ("member_%d_process_alpha_stack" % member, stacks[index]),
                    )
                )
        elif case_id == "group-clipping":
            boundaries.extend(
                (
                    ("actual_parent_backdrop", comment_tool(tools, "PSD layer merge: group-clip-bottom", "Merge")),
                    ("base_loader_straight", comment_tool(tools, "PSD layer: group-clip-base", "Loader")),
                    ("base_float32", comment_tool(tools, "PSD layer float32 materialization: group-clip-base", "ChangeDepth")),
                    ("fixed_base_matte", comment_tool(tools, "PSD layer premultiply: group-clip-base", "AlphaMultiply")),
                    ("clip_in", tool_names(tools, "ClipIn")[0]),
                    ("blend_function", tool_names(tools, "BlendFunction")[0]),
                    ("process_alpha_stack", tool_names(tools, "ClipStack")[0]),
                )
            )
        elif case_id == "nested-isolated-group":
            boundaries.append(
                ("actual_parent_backdrop", comment_tool(tools, "PSD layer merge: nested-bottom", "Merge"))
            )
        elif case_id == "pass-through-group":
            boundaries.append(
                ("actual_parent_backdrop", comment_tool(tools, "PSD layer merge: pass-bottom", "Merge"))
            )

        groups = [tool for tool in tools if tool.get("type") == "GroupOperator"]
        comp_text = comp_path.read_text(encoding="utf-8")
        for index, group in enumerate(groups, 1):
            group_name = str(group["name"])
            proxy = _instance_source(_group_block(comp_text, group_name), "MainOutput1", "InstanceOutput")
            if proxy is None or not proxy.get("source_op"):
                raise ValueError("GroupOperator %s lacks InstanceOutput readback" % group_name)
            boundaries.append(("group_proxy_%d" % index, group_name))
            boundaries.append(("group_internal_terminal_%d" % index, proxy["source_op"]))

        boundaries.append(("external_render_consumer", str(case["final_tool"])))
        labels = [label for label, _ in boundaries]
        if len(labels) != len(set(labels)):
            raise ValueError("duplicate boundary label in %s" % case_id)
        output = (artifact_root / case_id).resolve()
        output.mkdir(parents=True, exist_ok=True)
        selected[case_id] = {
            "id": case_id,
            "stage": case["stage"],
            "comp": str(comp_path.resolve()),
            "comp_argument": case["comp_argument"],
            "output": str(output),
            "boundaries": [{"label": label, "tool": tool} for label, tool in boundaries],
        }

    lines = [
        "\t".join(
            (
                case_id,
                selected[case_id]["stage"],
                selected[case_id]["comp_argument"],
                selected[case_id]["output"],
                "|".join(
                    item["label"] + "=" + item["tool"]
                    for item in selected[case_id]["boundaries"]
                ),
            )
        )
        for case_id in selected
    ]
    tasks_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report = {
        "schema": SCHEMA,
        "status": "PASS",
        "kind": "boundary-render-tasks",
        "source_tasks_manifest": str(tasks_manifest.resolve()),
        "tasks": str(tasks_path),
        "tasks_sha256": _sha256(tasks_path),
        "artifact_root": str(artifact_root),
        "case_count": len(selected),
        "boundary_count": sum(len(case["boundaries"]) for case in selected.values()),
        "cases": selected,
    }
    report_path = tasks_path.parent / "tasks.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report["report"] = str(report_path)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fixture-root", action="append", type=Path, default=[])
    parser.add_argument("--tasks-output", type=Path)
    parser.add_argument("--boundary-source", type=Path)
    parser.add_argument("--boundary-output", type=Path)
    parser.add_argument("--only-boundary-case", action="append", default=[])
    args = parser.parse_args(argv)
    try:
        if args.boundary_source or args.boundary_output:
            if args.boundary_source is None or args.boundary_output is None:
                parser.error("--boundary-source and --boundary-output are required together")
            report = build_boundary_tasks(
                args.boundary_source,
                args.boundary_output,
                args.only_boundary_case,
            )
        elif args.fixture_root or args.tasks_output:
            if not args.fixture_root or args.tasks_output is None:
                parser.error("--fixture-root and --tasks-output are required together")
            report = build_final_tasks(args.fixture_root, args.tasks_output)
        else:
            if args.matrix is None or args.output is None:
                parser.error("--matrix and --output are required for preparation")
            report = prepare(args.matrix, args.output)
    except Exception as exc:
        print(json.dumps({"schema": SCHEMA, "status": "ERROR", "error": str(exc)}))
        return 2
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
