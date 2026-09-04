"""Validate the base blend/opacity boundary for P4-04.

Two otherwise identical clipping documents vary only the base's blend and
overall opacity.  The member-local controls must remain unchanged, while the
single outer chain Merge tracks the changed base controls.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from psd2fusion.fusion_comp import FUSION_BLEND_IDS, compile_comp
from psd2fusion.semantic import ClippingChain, SemanticDocument, SemanticLayer
from scripts.validate_clipping_subtrees import materialization_for, parse_tools


BASE_ID = "p404base01x"
OUTER_ID = "p404outerx1"
MEMBER_IDS = ("p404m001xx", "p404m002xx")
MEMBER_CONTROLS = (("Normal", 0.75), ("Overlay", 0.25))
SOURCE_HASH = "p404" + "0" * 60


def fixture_document(base_mode: str, base_opacity: float) -> SemanticDocument:
    outer = SemanticLayer(
        id=OUTER_ID,
        name="P4-04 outer backdrop",
        asset_path="assets/outer.png",
        blend="Normal",
    )
    base = SemanticLayer(
        id=BASE_ID,
        name="P4-04 base (%s %.0f%%)" % (base_mode, base_opacity * 100.0),
        asset_path="assets/base.png",
        blend=base_mode,
        opacity=base_opacity,
        clipping_members=list(MEMBER_IDS),
    )
    members = [
        SemanticLayer(
            id=member_id,
            name="P4-04 member %d" % index,
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
        source_path="p4-04-fixture.psd",
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


def _graph(comp_path: Path) -> Dict[str, Any]:
    tools = parse_tools(comp_path)
    base_loaders = _role(tools, "Loader", BASE_ID)
    outer_merges = [
        tool
        for tool in _role(tools, "Merge", BASE_ID)
        if "PSD clipping chain merge:" in tool["comments"]
    ]
    outer_functions = [
        tool
        for tool in _role(tools, "OuterBlendFunction", BASE_ID)
        if tool["type"] == "Merge"
    ]
    outer_premults = [
        tool
        for tool in _role(tools, "OuterBlendPremult", BASE_ID)
        if tool["type"] == "AlphaMultiply"
    ]
    outer_coverages = [
        tool
        for tool in _role(tools, "OuterBlendCoverage", BASE_ID)
        if tool["type"] == "Merge"
    ]
    stacks = [
        tool
        for member_id in MEMBER_IDS
        for tool in _role(tools, "ClipStack", member_id)
        if tool["type"] == "Merge"
    ]
    blend_functions = [
        tool
        for member_id in MEMBER_IDS
        for tool in _role(tools, "BlendFunction", member_id)
        if tool["type"] == "Merge"
    ]
    outer = outer_merges[0] if len(outer_merges) == 1 else None
    local_controls: List[Tuple[str | None, str | None]] = [
        (tool["apply_mode"], tool["blend"]) for tool in blend_functions
    ]
    return {
        "tools": tools,
        "base_loaders": base_loaders,
        "stacks": stacks,
        "outer": outer,
        "outer_function": outer_functions[0] if len(outer_functions) == 1 else None,
        "outer_premult": outer_premults[0] if len(outer_premults) == 1 else None,
        "outer_coverage": outer_coverages[0] if len(outer_coverages) == 1 else None,
        "local_controls": local_controls,
        "pass": (
            len(base_loaders) == 1
            and materialization_for(tools, BASE_ID)["valid"]
            and len(stacks) == len(MEMBER_IDS)
            and len(blend_functions) == len(MEMBER_IDS)
            and outer is not None
        ),
    }


def build(output: Path) -> Dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    primary_path = output / "p4_04.comp"
    alternate_path = output / "p4_04_base_changed.comp"
    primary_stats = compile_comp(
        fixture_document("Multiply", 0.50), str(primary_path)
    )
    alternate_stats = compile_comp(
        fixture_document("Screen", 0.25), str(alternate_path)
    )
    primary = _graph(primary_path)
    alternate = _graph(alternate_path)

    expected_primary = ('FuID { "Multiply" }', "1.000000")
    expected_alternate = ('FuID { "Screen" }', "1.000000")
    expected_members = [
        ('FuID { "%s" }' % FUSION_BLEND_IDS[mode], "1.000000")
        for mode, _opacity in MEMBER_CONTROLS
    ]
    outer = primary["outer"]
    alternate_outer = alternate["outer"]
    outer_function = primary["outer_function"]
    alternate_outer_function = alternate["outer_function"]
    outer_premult = primary["outer_premult"]
    primary_outer_coverage = primary.get("outer_coverage")
    alternate_outer_coverage = alternate.get("outer_coverage")
    checks = {
        "primary_graph_shape": primary["pass"],
        "alternate_graph_shape": alternate["pass"],
        "primary_outer_owns_base_controls": (
            outer_function is not None
            and (outer_function["apply_mode"], outer_function["blend"]) == expected_primary
        ),
        "alternate_outer_tracks_changed_base_controls": (
            alternate_outer_function is not None
            and (alternate_outer_function["apply_mode"], alternate_outer_function["blend"])
            == expected_alternate
        ),
        "primary_outer_opacity_isolated": (
            primary_outer_coverage is not None
            and primary_outer_coverage["blend"] == "0.500000"
        ),
        "alternate_outer_opacity_tracks_changed_base": (
            alternate_outer_coverage is not None
            and alternate_outer_coverage["blend"] == "0.250000"
        ),
        "local_member_controls_do_not_change_with_base": (
            primary["local_controls"] == alternate["local_controls"] == expected_members
        ),
        "outer_boundary_is_after_complete_local_stack": (
            outer is not None
            and outer_premult is not None
            and outer["foreground"] == outer_premult["name"]
            and outer["start"] > max(tool["start"] for tool in primary["stacks"])
        ),
        "outer_boundary_is_explicit": (
            outer is not None
            and "P4-04 base blend/opacity once" in outer["comments"]
            and outer_function is not None
            and "P4-HOST-PIXEL: straight opaque; Blend=1" in outer_function["comments"]
        ),
    }
    report: Dict[str, Any] = {
        "schema_version": 1,
        "task": "PARITY-004",
        "item": "P4-04",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "pass": all(checks.values()),
        "recipe": "operator_in_fixed_matte_local_stack",
        "fixture": {
            "base_id": BASE_ID,
            "member_ids": list(MEMBER_IDS),
            "member_order": "PSD bottom-to-top",
            "primary_base": {"blend": "Multiply", "opacity": 0.50},
            "alternate_base": {"blend": "Screen", "opacity": 0.25},
            "member_controls": [
                {"mode": mode, "opacity": opacity}
                for mode, opacity in MEMBER_CONTROLS
            ],
        },
        "graph": primary_stats,
        "alternate_graph": alternate_stats,
        "checks": checks,
        "primary_outer": outer,
        "alternate_outer": alternate_outer,
        "primary_outer_function": outer_function,
        "alternate_outer_function": alternate_outer_function,
        "primary_outer_coverage": primary_outer_coverage,
        "alternate_outer_coverage": alternate_outer_coverage,
        "primary_local_controls": primary["local_controls"],
        "alternate_local_controls": alternate["local_controls"],
        "artifacts": {
            "primary": _artifact(primary_path),
            "alternate": _artifact(alternate_path),
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
