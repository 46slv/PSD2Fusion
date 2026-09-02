"""Build and validate member-control placement for the P4-03 graph.

The fixture keeps the selected P4-01/P4-02 topology and varies only clipped
member blend modes and opacity.  It proves that those controls live on each
local ClipStack Merge, while the single outer chain Merge remains the base
boundary.
"""

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

from psd2fusion.fusion_comp import FUSION_BLEND_IDS, compile_comp
from psd2fusion.semantic import ClippingChain, SemanticDocument, SemanticLayer
from scripts.validate_clipping_subtrees import parse_tools


BASE_ID = "p403base01x"
OUTER_ID = "p403outerx1"
MEMBER_CONTROLS = (
    ("Normal", 0.25),
    ("Multiply", 0.50),
    ("Linear Dodge", 0.75),
    ("Overlay", 1.00),
)
MEMBER_IDS = tuple("p403m%03dxx" % index for index in range(1, len(MEMBER_CONTROLS) + 1))
SOURCE_HASH = "p403" + "0" * 60


def fixture_document() -> SemanticDocument:
    """Return a deterministic four-member control-placement document."""

    outer = SemanticLayer(
        id=OUTER_ID,
        name="P4-03 outer backdrop",
        asset_path="assets/outer.png",
        blend="Normal",
    )
    base = SemanticLayer(
        id=BASE_ID,
        name="P4-03 base",
        asset_path="assets/base.png",
        blend="Normal",
        clipping_members=list(MEMBER_IDS),
    )
    members = [
        SemanticLayer(
            id=member_id,
            name="P4-03 %s member %.0f%%" % (mode, opacity * 100.0),
            asset_path="assets/member-%d.png" % index,
            clipping_base_id=BASE_ID,
            blend=mode,
            opacity=opacity,
        )
        for index, (member_id, (mode, opacity)) in enumerate(
            zip(MEMBER_IDS, MEMBER_CONTROLS), 1
        )
    ]
    return SemanticDocument(
        source_path="p4-03-fixture.psd",
        source_sha256=SOURCE_HASH,
        parser="fixture",
        parser_version="1",
        width=8,
        height=8,
        children=[outer, base] + members,
        clipping_chains=[
            ClippingChain(
                base_id=BASE_ID,
                member_ids=list(MEMBER_IDS),
                blend_clipped_as_group=True,
                blend_clipped_as_group_provenance="photoshop_default_true",
            )
        ],
    )


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


def build(output: Path) -> Dict[str, Any]:
    """Compile the fixture and return a machine-readable control proof."""

    output.mkdir(parents=True, exist_ok=True)
    comp_path = output / "p4_03.comp"
    stats = compile_comp(fixture_document(), str(comp_path))
    tools = parse_tools(comp_path)

    base_loaders = _role(tools, "Loader", BASE_ID)
    outer_loaders = _role(tools, "Loader", OUTER_ID)
    member_rows: List[Dict[str, Any]] = []
    previous_stack = base_loaders[0]["name"] if len(base_loaders) == 1 else None
    for index, (member_id, (mode, opacity)) in enumerate(
        zip(MEMBER_IDS, MEMBER_CONTROLS), 1
    ):
        loaders = _role(tools, "Loader", member_id)
        clips = [tool for tool in _role(tools, "ClipIn", member_id) if tool["type"] == "Merge"]
        stacks = [tool for tool in _role(tools, "ClipStack", member_id) if tool["type"] == "Merge"]
        row: Dict[str, Any] = {
            "index": index,
            "id": member_id,
            "expected_mode": mode,
            "expected_blend": "%.6f" % opacity,
            "loader_count": len(loaders),
            "clip_count": len(clips),
            "stack_count": len(stacks),
            "loader": loaders[0]["name"] if len(loaders) == 1 else None,
            "clip": clips[0]["name"] if len(clips) == 1 else None,
            "stack": stacks[0]["name"] if len(stacks) == 1 else None,
            "clip_background": clips[0]["background"] if len(clips) == 1 else None,
            "clip_foreground": clips[0]["foreground"] if len(clips) == 1 else None,
            "clip_apply_mode": clips[0]["apply_mode"] if len(clips) == 1 else None,
            "clip_blend": clips[0]["blend"] if len(clips) == 1 else None,
            "clip_operator": clips[0]["operator"] if len(clips) == 1 else None,
            "stack_background": stacks[0]["background"] if len(stacks) == 1 else None,
            "stack_foreground": stacks[0]["foreground"] if len(stacks) == 1 else None,
            "stack_apply_mode": stacks[0]["apply_mode"] if len(stacks) == 1 else None,
            "stack_blend": stacks[0]["blend"] if len(stacks) == 1 else None,
            "stack_process_alpha": stacks[0]["process_alpha"] if len(stacks) == 1 else None,
            "stack_start": stacks[0]["start"] if len(stacks) == 1 else None,
        }
        row["shape"] = bool(
            len(loaders) == len(clips) == len(stacks) == 1
            and len(base_loaders) == 1
            and row["clip_background"] == base_loaders[0]["name"]
            and row["clip_foreground"] == row["loader"]
            and row["clip_apply_mode"] == 'FuID { "Normal" }'
            and row["clip_blend"] == "1.000000"
            and row["clip_operator"] == 'FuID { "In" }'
            and row["stack_background"] == previous_stack
            and row["stack_foreground"] == row["clip"]
            and row["stack_apply_mode"] == 'FuID { "%s" }' % FUSION_BLEND_IDS[mode]
            and row["stack_blend"] == "%.6f" % opacity
            and row["stack_process_alpha"] == "0"
        )
        if row["stack"] is not None:
            previous_stack = row["stack"]
        member_rows.append(row)

    outer_merges = [
        tool
        for tool in _role(tools, "Merge", BASE_ID)
        if "PSD clipping chain merge:" in tool["comments"]
    ]
    outer = outer_merges[0] if len(outer_merges) == 1 else None
    checks = {
        "one_base_loader": len(base_loaders) == 1,
        "one_outer_loader": len(outer_loaders) == 1,
        "four_members": len(member_rows) == len(MEMBER_CONTROLS),
        "each_member_controls_on_local_stack": all(row["shape"] for row in member_rows),
        "member_modes_are_not_outer_controls": (
            outer is not None
            and all(
                row["stack_apply_mode"] != outer["apply_mode"]
                or row["stack_blend"] != outer["blend"]
                for row in member_rows
            )
        ),
        "member_order_is_bottom_to_top": all(
            member_rows[index]["stack_start"] < member_rows[index + 1]["stack_start"]
            for index in range(len(member_rows) - 1)
        ),
        "one_outer_merge_after_complete_stack": (
            outer is not None
            and outer["foreground"] == member_rows[-1]["stack"]
            and outer["start"] > max(row["stack_start"] for row in member_rows)
        ),
    }
    report: Dict[str, Any] = {
        "schema_version": 1,
        "task": "PARITY-004",
        "item": "P4-03",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "pass": all(checks.values()),
        "recipe": "operator_in_fixed_matte_local_stack",
        "fixture": {
            "base_id": BASE_ID,
            "member_ids": list(MEMBER_IDS),
            "member_order": "PSD bottom-to-top",
            "member_controls": [
                {"mode": mode, "opacity": opacity}
                for mode, opacity in MEMBER_CONTROLS
            ],
        },
        "graph": stats,
        "checks": checks,
        "members": member_rows,
        "outer": outer,
        "artifact": _artifact(comp_path),
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
