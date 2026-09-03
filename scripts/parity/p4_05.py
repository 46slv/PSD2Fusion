"""Exercise clipping boundaries at existing group/nesting boundaries.

Each case uses the same fixed-matte clipping recipe.  The checks focus on
where the local chain and its one outer Merge live relative to GroupOperator,
not on host render behavior.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from psd2fusion.fusion_comp import compile_comp
from psd2fusion.semantic import ClippingChain, SemanticDocument, SemanticLayer
from scripts.validate_clipping_subtrees import parse_tools


SOURCE_HASH = "p405" + "0" * 60
CASES = ("isolated", "pass_through", "nested_isolated", "adjacent")


def _chain(base_id: str, member_ids: Sequence[str], label: str) -> Tuple[List[SemanticLayer], ClippingChain]:
    base = SemanticLayer(
        id=base_id,
        name="P4-05 %s base" % label,
        asset_path="assets/%s-base.png" % label,
        clipping_members=list(member_ids),
    )
    members = [
        SemanticLayer(
            id=member_id,
            name="P4-05 %s member %d" % (label, index),
            asset_path="assets/%s-member-%d.png" % (label, index),
            clipping_base_id=base_id,
            blend="Multiply" if index == 2 else "Normal",
            opacity=0.75 if index == 2 else 1.0,
        )
        for index, member_id in enumerate(member_ids, 1)
    ]
    return [base] + members, ClippingChain(
        base_id=base_id,
        member_ids=list(member_ids),
        blend_clipped_as_group=True,
        blend_clipped_as_group_provenance="photoshop_default_true",
    )


def _group(group_id: str, name: str, children: Sequence[SemanticLayer], pass_through: bool = False) -> SemanticLayer:
    return SemanticLayer(
        id=group_id,
        name=name,
        kind="group",
        children=list(children),
        pass_through=pass_through,
        isolated=not pass_through,
        blend="Normal",
        opacity=1.0,
    )


def fixture_documents() -> Dict[str, SemanticDocument]:
    docs: Dict[str, SemanticDocument] = {}

    isolated_layers, isolated_chain = _chain(
        "p405isobas", ("p405isom01", "p405isom02"), "isolated"
    )
    docs["isolated"] = SemanticDocument(
        source_path="p4-05-isolated.psd",
        source_sha256=SOURCE_HASH,
        parser="fixture",
        parser_version="1",
        width=8,
        height=8,
        children=[
            SemanticLayer(
                id="p405isoout",
                name="P4-05 isolated outer",
                asset_path="assets/isolated-outer.png",
            ),
            _group("p405isogrp", "P4-05 isolated group", isolated_layers),
        ],
        clipping_chains=[isolated_chain],
    )

    pass_layers, pass_chain = _chain(
        "p405ptbase", ("p405ptm001", "p405ptm002"), "pass-through"
    )
    docs["pass_through"] = SemanticDocument(
        source_path="p4-05-pass-through.psd",
        source_sha256=SOURCE_HASH,
        parser="fixture",
        parser_version="1",
        width=8,
        height=8,
        children=[
            SemanticLayer(
                id="p405ptout",
                name="P4-05 pass-through outer",
                asset_path="assets/pass-through-outer.png",
            ),
            _group("p405ptgrp", "P4-05 pass-through group", pass_layers, True),
        ],
        clipping_chains=[pass_chain],
    )

    nested_layers, nested_chain = _chain(
        "p405nbase1", ("p405nm001x", "p405nm002x"), "nested"
    )
    inner = _group("p405nestin", "P4-05 inner isolated", nested_layers)
    outer_group = _group("p405nestout", "P4-05 outer isolated", [inner])
    docs["nested_isolated"] = SemanticDocument(
        source_path="p4-05-nested.psd",
        source_sha256=SOURCE_HASH,
        parser="fixture",
        parser_version="1",
        width=8,
        height=8,
        children=[
            SemanticLayer(
                id="p405nestback",
                name="P4-05 nested outer",
                asset_path="assets/nested-outer.png",
            ),
            outer_group,
        ],
        clipping_chains=[nested_chain],
    )

    adjacent_layers, adjacent_chain = _chain(
        "p405abase1", ("p405am001x", "p405am002x"), "adjacent"
    )
    lower_leaf = SemanticLayer(
        id="p405adjlowleaf",
        name="P4-05 lower boundary leaf",
        asset_path="assets/adjacent-lower.png",
    )
    upper_leaf = SemanticLayer(
        id="p405adjhighleaf",
        name="P4-05 upper boundary leaf",
        asset_path="assets/adjacent-upper.png",
    )
    docs["adjacent"] = SemanticDocument(
        source_path="p4-05-adjacent.psd",
        source_sha256=SOURCE_HASH,
        parser="fixture",
        parser_version="1",
        width=8,
        height=8,
        children=[
            SemanticLayer(
                id="p405adjout",
                name="P4-05 adjacent outer",
                asset_path="assets/adjacent-backdrop.png",
            ),
            _group("p405adjlow", "P4-05 lower boundary group", [lower_leaf]),
            *adjacent_layers,
            _group("p405adjhigh", "P4-05 upper boundary group", [upper_leaf]),
        ],
        clipping_chains=[adjacent_chain],
    )
    return docs


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


def _chain_shape(tools: Sequence[Dict[str, Any]], base_id: str, member_ids: Sequence[str]) -> Dict[str, Any]:
    base_loaders = _role(tools, "Loader", base_id)
    outer_merges = [
        tool
        for tool in _role(tools, "Merge", base_id)
        if "PSD clipping chain merge:" in tool["comments"]
    ]
    previous = base_loaders[0]["name"] if len(base_loaders) == 1 else None
    rows: List[Dict[str, Any]] = []
    for member_id in member_ids:
        loaders = _role(tools, "Loader", member_id)
        clips = [tool for tool in _role(tools, "ClipIn", member_id) if tool["type"] == "Merge"]
        base_straights = [tool for tool in _role(tools, "BlendBaseStraight", member_id) if tool["type"] == "AlphaDivide"]
        base_opaques = [tool for tool in _role(tools, "BlendBaseOpaque", member_id) if tool["type"] == "ChannelBoolean"]
        member_straights = [tool for tool in _role(tools, "BlendMemberStraight", member_id) if tool["type"] == "AlphaDivide"]
        member_opaques = [tool for tool in _role(tools, "BlendMemberOpaque", member_id) if tool["type"] == "ChannelBoolean"]
        blend_functions = [tool for tool in _role(tools, "BlendFunction", member_id) if tool["type"] == "Merge"]
        blend_clamps = [tool for tool in _role(tools, "BlendClamp", member_id) if tool["type"] == "BrightnessContrast"]
        blend_coverages = [tool for tool in _role(tools, "BlendCoverage", member_id) if tool["type"] == "ChannelBoolean"]
        blend_premults = [tool for tool in _role(tools, "BlendPremult", member_id) if tool["type"] == "AlphaMultiply"]
        blend_restores = [tool for tool in _role(tools, "BlendRestoreAlpha", member_id) if tool["type"] == "ChannelBoolean"]
        stacks = [tool for tool in _role(tools, "ClipStack", member_id) if tool["type"] == "Merge"]
        row = {
            "loader": loaders[0] if len(loaders) == 1 else None,
            "clip": clips[0] if len(clips) == 1 else None,
            "base_straight": base_straights[0] if len(base_straights) == 1 else None,
            "base_opaque": base_opaques[0] if len(base_opaques) == 1 else None,
            "member_straight": member_straights[0] if len(member_straights) == 1 else None,
            "member_opaque": member_opaques[0] if len(member_opaques) == 1 else None,
            "blend_function": blend_functions[0] if len(blend_functions) == 1 else None,
            "blend_clamp": blend_clamps[0] if len(blend_clamps) == 1 else None,
            "blend_coverage": blend_coverages[0] if len(blend_coverages) == 1 else None,
            "blend_premult": blend_premults[0] if len(blend_premults) == 1 else None,
            "blend_restore": blend_restores[0] if len(blend_restores) == 1 else None,
            "stack": stacks[0] if len(stacks) == 1 else None,
        }
        row["pass"] = bool(
            len(base_loaders) == 1
            and row["loader"] is not None
            and row["clip"] is not None
            and row["base_straight"] is not None
            and row["base_opaque"] is not None
            and row["member_straight"] is not None
            and row["member_opaque"] is not None
            and row["blend_function"] is not None
            and row["blend_clamp"] is not None
            and row["blend_coverage"] is not None
            and row["blend_premult"] is not None
            and row["blend_restore"] is not None
            and row["stack"] is not None
            and row["clip"]["background"] == base_loaders[0]["name"]
            and row["clip"]["foreground"] == row["loader"]["name"]
            and row["clip"]["operator"] == 'FuID { "In" }'
            and row["base_straight"]["input"] == previous
            and row["base_opaque"]["background"] == row["base_straight"]["name"]
            and row["base_opaque"]["to_alpha"] == "16"
            and row["member_straight"]["input"] == row["loader"]["name"]
            and row["member_opaque"]["background"] == row["member_straight"]["name"]
            and row["member_opaque"]["to_alpha"] == "16"
            and row["blend_function"]["background"] == row["base_opaque"]["name"]
            and row["blend_function"]["foreground"] == row["member_opaque"]["name"]
            and row["blend_function"]["blend"] == "1.000000"
            and row["blend_clamp"]["input"] == row["blend_function"]["name"]
            and row["blend_clamp"]["clip_black"] == "1"
            and row["blend_clamp"]["clip_white"] == "1"
            and row["blend_clamp"]["process_alpha"] == "0"
            and row["blend_coverage"]["background"] == row["blend_clamp"]["name"]
            and row["blend_coverage"]["foreground"] == row["clip"]["name"]
            and row["blend_coverage"]["to_alpha"] == "3"
            and row["blend_premult"]["input"] == row["blend_coverage"]["name"]
            and row["blend_restore"]["background"] == row["blend_premult"]["name"]
            and row["blend_restore"]["foreground"] == row["loader"]["name"]
            and row["blend_restore"]["to_alpha"] == "3"
            and row["stack"]["background"] == previous
            and row["stack"]["foreground"] == row["blend_restore"]["name"]
            and row["stack"]["apply_mode"] == 'FuID { "Normal" }'
            and row["stack"]["process_alpha"] == "0"
        )
        if row["stack"] is not None:
            previous = row["stack"]["name"]
        rows.append(row)
    outer = outer_merges[0] if len(outer_merges) == 1 else None
    chain_pass = bool(
        len(base_loaders) == 1
        and len(outer_merges) == 1
        and rows
        and all(row["pass"] for row in rows)
        and outer["foreground"] == rows[-1]["stack"]["name"]
        and outer["start"] > max(row["stack"]["start"] for row in rows)
    )
    return {
        "base_loader": base_loaders[0] if len(base_loaders) == 1 else None,
        "members": rows,
        "outer": outer,
        "pass": chain_pass,
    }


def build(output: Path) -> Dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    case_reports: Dict[str, Any] = {}
    for case, document in fixture_documents().items():
        comp_path = output / ("p4_05_%s.comp" % case)
        stats = compile_comp(document, str(comp_path))
        tools = parse_tools(comp_path)
        chain = document.clipping_chains[0]
        shape = _chain_shape(tools, chain.base_id, chain.member_ids)
        groups = [tool for tool in tools if tool["type"] == "GroupOperator"]
        outer = shape["outer"]
        containing_groups = [
            group
            for group in groups
            if outer is not None and group["start"] < outer["start"] < group["end"]
        ]
        case_checks = {
            "clipping_recipe_inside_existing_stream": shape["pass"],
            "expected_group_count": len(groups)
            == (2 if case in ("nested_isolated", "adjacent") else 1),
            "isolated_chain_is_inside_group": case != "isolated"
            or len(containing_groups) == 1,
            "pass_through_chain_is_inside_group_and_consumes_input": case
            == "pass_through"
            and len(containing_groups) == 1
            and containing_groups[0]["input_target"] == outer["name"]
            if case == "pass_through" and outer is not None and containing_groups
            else case != "pass_through",
            "nested_chain_is_inside_both_group_boundaries": case != "nested_isolated"
            or len(containing_groups) == 2,
            "adjacent_chain_stays_between_group_boundaries": case != "adjacent"
            or (
                len(containing_groups) == 0
                and len(groups) == 2
                and outer is not None
                and groups[0]["end"] < outer["start"] < groups[1]["start"]
            ),
        }
        case_reports[case] = {
            "status": "PASS" if all(case_checks.values()) else "FAIL",
            "pass": all(case_checks.values()),
            "stats": stats,
            "checks": case_checks,
            "groups": groups,
            "containing_groups": [group["name"] for group in containing_groups],
            "chain": shape,
            "artifact": _artifact(comp_path),
        }

    checks = {
        "all_cases_pass": all(case_report["pass"] for case_report in case_reports.values()),
        "all_cases_keep_fixed_matte_recipe": all(
            case_report["checks"]["clipping_recipe_inside_existing_stream"]
            for case_report in case_reports.values()
        ),
    }
    report: Dict[str, Any] = {
        "schema_version": 1,
        "task": "PARITY-004",
        "item": "P4-05",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "pass": all(checks.values()),
        "recipe": "operator_in_fixed_matte_local_stack",
        "cases": case_reports,
        "checks": checks,
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
