"""Validate the deterministic Flow layout used by clipping lowering."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from psd2fusion.fusion_comp import compile_comp
from scripts.parity.p4_03 import BASE_ID, MEMBER_IDS, fixture_document
from scripts.parity.p4_05 import fixture_documents
from scripts.validate_clipping_subtrees import parse_tools


def _artifact(path: Path) -> Dict[str, Any]:
    data = path.read_bytes()
    return {"path": str(path), "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def _role(tools: Sequence[Dict[str, Any]], prefix: str, layer_id: str) -> List[Dict[str, Any]]:
    suffix = "_" + layer_id[:10]
    return [
        tool
        for tool in tools
        if tool["name"].startswith(prefix)
        and (tool["name"].endswith(suffix) or suffix + "_" in tool["name"])
    ]


def _one(tools: Sequence[Dict[str, Any]], prefix: str, layer_id: str) -> Dict[str, Any] | None:
    rows = _role(tools, prefix, layer_id)
    return rows[0] if len(rows) == 1 else None


def build(output: Path) -> Dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    clip_path = output / "p4_06_clip.comp"
    group_path = output / "p4_06_group.comp"
    clip_stats = compile_comp(fixture_document(), str(clip_path))
    group_stats = compile_comp(
        fixture_documents()["nested_isolated"], str(group_path)
    )
    clip_tools = parse_tools(clip_path)
    group_tools = parse_tools(group_path)

    base = _one(clip_tools, "Loader", BASE_ID)
    members = [_one(clip_tools, "Loader", member_id) for member_id in MEMBER_IDS]
    clips = [_one(clip_tools, "ClipIn", member_id) for member_id in MEMBER_IDS]
    stacks = [_one(clip_tools, "ClipStack", member_id) for member_id in MEMBER_IDS]
    outer_rows = [
        tool
        for tool in _role(clip_tools, "Merge", BASE_ID)
        if "PSD clipping chain merge:" in tool["comments"]
    ]
    outer = outer_rows[0] if len(outer_rows) == 1 else None
    chain_nodes = [tool for tool in clip_tools if tool["type"] in ("Loader", "Merge")]
    chain_nodes = [tool for tool in chain_nodes if tool["name"] != "LoaderR_%s" % "unused"]

    group_outer_rows = [
        tool
        for tool in group_tools
        if tool["type"] == "Merge" and "PSD clipping chain merge:" in tool["comments"]
    ]
    group_outer = group_outer_rows[0] if len(group_outer_rows) == 1 else None
    groups = [tool for tool in group_tools if tool["type"] == "GroupOperator"]
    containing_groups = [
        group
        for group in groups
        if group_outer is not None
        and group["start"] < group_outer["start"] < group["end"]
    ]

    member_positions = [row["position"] if row is not None else None for row in members]
    clip_positions = [row["position"] if row is not None else None for row in clips]
    stack_positions = [row["position"] if row is not None else None for row in stacks]
    x_order = [tool["position"][0] for tool in sorted(chain_nodes, key=lambda item: item["start"]) if tool["position"]]
    checks = {
        "all_chain_positions_present": (
            base is not None
            and outer is not None
            and all(position is not None for position in member_positions + clip_positions + stack_positions)
        ),
        "flow_is_left_to_right": all(
            x_order[index] < x_order[index + 1] for index in range(len(x_order) - 1)
        ),
        "base_is_below_member_loader_band": (
            base is not None
            and base["position"] is not None
            and all(position is not None and position[1] < base["position"][1] for position in member_positions)
        ),
        "member_loaders_have_distinct_rows": len({position[1] for position in member_positions if position is not None}) == len(MEMBER_IDS),
        "clipin_and_stack_are_clustered": all(
            clip_position is not None
            and stack_position is not None
            and clip_position[0] < stack_position[0]
            and clip_position[1] == stack_position[1] - 110.0
            for clip_position, stack_position in zip(clip_positions, stack_positions)
        ),
        "fixed_matte_connection_remains_obvious": (
            base is not None
            and all(
                clip is not None
                and clip["background"] == base["name"]
                and clip["operator"] == 'FuID { "In" }'
                for clip in clips
            )
        ),
        "one_outer_merge_exits_cluster": (
            outer is not None
            and all(stack is not None for stack in stacks)
            and outer["foreground"] == stacks[-1]["name"]
            and outer["position"][0] > max(stack["position"][0] for stack in stacks)
            and outer["position"][1] == 0.0
        ),
        "group_boundaries_remain_distinct": (
            len(groups) == 2
            and len(containing_groups) == 2
            and all(group["position"] is not None for group in groups)
            and len({group["position"] for group in groups}) == len(groups)
        ),
    }
    report: Dict[str, Any] = {
        "schema_version": 1,
        "task": "PARITY-004",
        "item": "P4-06",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "pass": all(checks.values()),
        "recipe": "operator_in_fixed_matte_local_stack",
        "checks": checks,
        "layout": {
            "base": base,
            "members": members,
            "clips": clips,
            "stacks": stacks,
            "outer": outer,
            "group_boundaries": groups,
            "groups_containing_nested_chain": [group["name"] for group in containing_groups],
        },
        "graph": clip_stats,
        "group_graph": group_stats,
        "artifacts": {
            "clipping": _artifact(clip_path),
            "groups": _artifact(group_path),
        },
    }
    (output / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    report = build(args.output)
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
