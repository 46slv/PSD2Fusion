"""Validate generated clipping-chain boundaries without claiming pixel parity."""

import argparse
import json
import re
from pathlib import Path

from psd2fusion.fusion_comp import FUSION_BLEND_IDS
from psd2fusion.parse_psd import parse_psd
from psd2fusion.semantic import index_layers, walk_layers


TOOL_HEADER = re.compile(
    r"(?m)^([ \t]*)([A-Za-z_][A-Za-z0-9_]*) = "
    r"(Background|Loader|ChangeDepth|Merge|ChannelBoolean|AlphaDivide|BrightnessContrast|AlphaMultiply|MediaOut|GroupOperator|Note) \{"
)


def _balanced(text, start):
    depth = 0
    quote = None
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in ('"', "'"):
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index + 1
    raise ValueError("Unbalanced Fusion composition")


def _value(block, field):
    match = re.search(
        r"(?m)^\s*" + re.escape(field) + r" = Input \{ Value = (.*?), \},",
        block,
    )
    return match.group(1) if match else None


def _connection(block, field):
    match = re.search(
        r'(?m)^\s*'
        + re.escape(field)
        + r' = Input \{ SourceOp = "((?:\\.|[^"\\])*)", Source = "((?:\\.|[^"\\])*)", \},',
        block,
    )
    return match.group(1) if match else None


def _position(block):
    # GroupInfo blocks are multi-line since the native viewport contract
    # (Scale/Offset/PipeStyle/Direction/Flags) is emitted; scan the balanced
    # ViewInfo block instead of assuming Pos sits on one line.
    header = re.search(
        r"ViewInfo = (?:OperatorInfo|GroupInfo|StickyNoteInfo) \{",
        block,
    )
    if not header:
        return None
    try:
        end = _balanced(block, header.end() - 1)
    except ValueError:
        return None
    view = block[header.start():end]
    match = re.search(r"Pos = \{ ([^,]+), ([^}]+) \}", view)
    if not match:
        return None
    return (float(match.group(1)), float(match.group(2)))


def _input_source_op(block, field):
    match = re.search(
        r'(?m)^\s*'
        + re.escape(field)
        + r'\s*=\s*InstanceInput\s*\{\s*'
        r'SourceOp\s*=\s*"((?:\\.|[^"\\])*)",',
        block,
    )
    return match.group(1) if match else None


def parse_tools(path):
    text = Path(path).read_text(encoding="utf-8")
    tools = []
    for match in TOOL_HEADER.finditer(text):
        end = _balanced(text, match.end() - 1)
        block = text[match.start() : end]
        tools.append(
            {
                "name": match.group(2),
                "type": match.group(3),
                "start": match.start(),
                "end": end,
                "background": _connection(block, "Background"),
                "foreground": _connection(block, "Foreground"),
                "input": _connection(block, "Input"),
                "apply_mode": _value(block, "ApplyMode"),
                "blend": _value(block, "Blend"),
                "operator": _value(block, "Operator"),
                "operation": _value(block, "Operation"),
                "to_red": _value(block, "ToRed"),
                "to_green": _value(block, "ToGreen"),
                "to_blue": _value(block, "ToBlue"),
                "to_alpha": _value(block, "ToAlpha"),
                "clip_black": _value(block, "ClipBlack"),
                "clip_white": _value(block, "ClipWhite"),
                "gain": _value(block, "Gain"),
                "process_alpha": _value(block, "ProcessAlpha"),
                "depth": _value(block, "Depth"),
                "dither": _value(block, "Dither"),
                "post_multiply": _value(
                    block, '["Clip1.PNGFormat.PostMultiply"]'
                ),
                "input_target": _input_source_op(block, "MainInput1"),
                "position": _position(block),
                "comments": _value(block, "Comments") or "",
            }
        )
    return tools


def materialization_for(tools, layer_id):
    """Return and validate one straight-PNG to float32 premult source chain."""

    suffix = "_" + layer_id[:10]

    def role(prefix, tool_type):
        return [
            tool
            for tool in tools
            if tool["type"] == tool_type
            and tool["name"].startswith(prefix)
            and (tool["name"].endswith(suffix) or suffix + "_" in tool["name"])
        ]

    loaders = role("Loader", "Loader")
    depths = role("MaterializeDepth", "ChangeDepth")
    premults = role("MaterializePremult", "AlphaMultiply")
    valid = len(loaders) == len(depths) == len(premults) == 1
    if valid:
        valid = all(
            (
                loaders[0]["post_multiply"] == "0",
                depths[0]["input"] == loaders[0]["name"],
                depths[0]["depth"] == "4",
                depths[0]["dither"] == "0",
                premults[0]["input"] == depths[0]["name"],
            )
        )
    return {
        "valid": valid,
        "loader": loaders[0] if len(loaders) == 1 else None,
        "depth": depths[0] if len(depths) == 1 else None,
        "premult": premults[0] if len(premults) == 1 else None,
        "source": premults[0]["name"] if valid else None,
    }


def validate(psd_path, comp_path):
    doc = parse_psd(psd_path)
    layers = index_layers(doc.children)
    tools = parse_tools(comp_path)

    def role(layer_id, prefix, tool_type):
        suffix = "_" + layer_id[:10]
        return [
            tool
            for tool in tools
            if tool["type"] == tool_type
            and tool["name"].startswith(prefix)
            and (tool["name"].endswith(suffix) or suffix + "_" in tool["name"])
        ]

    failures = []
    chain_rows = []
    visible_member_count = 0
    for chain_index, chain in enumerate(doc.clipping_chains, 1):
        base = layers[chain.base_id]
        base_nodes = role(base.id, "Loader", "Loader")
        base_materialization = materialization_for(tools, base.id)
        checks = [
            len(base_nodes) == 1,
            base_materialization["valid"],
            chain.blend_clipped_as_group,
        ]
        previous = base_materialization["source"]
        emitted_members = []
        for member_id in chain.member_ids:
            member = layers[member_id]
            if not member.effective_visible:
                continue
            visible_member_count += 1
            loaders = role(member.id, "Loader", "Loader")
            member_materialization = materialization_for(tools, member.id)
            clips = role(member.id, "ClipIn", "Merge")
            base_straight = role(member.id, "BlendBaseStraight", "AlphaDivide")
            base_opaque = role(member.id, "BlendBaseOpaque", "ChannelBoolean")
            member_straight = role(member.id, "BlendMemberStraight", "AlphaDivide")
            member_attenuate = role(
                member.id, "BlendMemberAttenuate", "BrightnessContrast"
            )
            member_opaque = role(member.id, "BlendMemberOpaque", "ChannelBoolean")
            blend_function = role(member.id, "BlendFunction", "Merge")
            blend_clamp = role(member.id, "BlendClamp", "BrightnessContrast")
            blend_coverage = role(member.id, "BlendCoverage", "ChannelBoolean")
            blend_premult = role(member.id, "BlendPremult", "AlphaMultiply")
            blend_restore = role(member.id, "BlendRestoreAlpha", "ChannelBoolean")
            stacks = role(member.id, "ClipStack", "Merge")
            is_linear_dodge = member.blend == "Linear Dodge"
            node_sets = (
                loaders,
                clips,
                base_straight,
                base_opaque,
                member_straight,
                member_opaque,
                blend_function,
                blend_clamp,
                blend_coverage,
                blend_premult,
                blend_restore,
                stacks,
            )
            member_ok = (
                all(len(nodes) == 1 for nodes in node_sets)
                and member_materialization["valid"]
                and (
                    len(member_attenuate) == 1
                    if is_linear_dodge
                    else len(member_attenuate) == 0
                )
            )
            if member_ok:
                clip = clips[0]
                base_div = base_straight[0]
                base_opaque_node = base_opaque[0]
                member_div = member_straight[0]
                member_opaque_node = member_opaque[0]
                function = blend_function[0]
                clamp = blend_clamp[0]
                coverage = blend_coverage[0]
                premult = blend_premult[0]
                restore = blend_restore[0]
                stack = stacks[0]
                expected_mode_id = FUSION_BLEND_IDS.get(member.blend)
                expected_mode = (
                    'FuID { "%s" }' % expected_mode_id
                    if expected_mode_id
                    else None
                )
                expected_stack_blend = (
                    "1.000000" if is_linear_dodge else "%.6f" % member.opacity
                )
                member_ok = all(
                    (
                        clip["background"] == base_materialization["source"],
                        clip["foreground"] == member_materialization["source"],
                        clip["operator"] == 'FuID { "In" }',
                        base_div["input"] == previous,
                        base_opaque_node["background"] == base_div["name"],
                        base_opaque_node["to_alpha"] == "16",
                        member_div["input"] == member_materialization["source"],
                        member_opaque_node["background"]
                        == (
                            member_attenuate[0]["name"]
                            if is_linear_dodge
                            else member_div["name"]
                        ),
                        member_opaque_node["to_alpha"] == "16",
                        function["background"] == base_opaque_node["name"],
                        function["foreground"] == member_opaque_node["name"],
                        expected_mode is not None
                        and function["apply_mode"] == expected_mode,
                        function["blend"] == "1.000000",
                        clamp["input"] == function["name"],
                        clamp["clip_black"] == "1",
                        clamp["clip_white"] == "1",
                        clamp["process_alpha"] == "0",
                        coverage["background"] == clamp["name"],
                        coverage["foreground"]
                        == (
                            base_materialization["source"]
                            if is_linear_dodge
                            else clip["name"]
                        ),
                        coverage["to_alpha"] == "3",
                        premult["input"] == coverage["name"],
                        restore["background"] == premult["name"],
                        restore["foreground"]
                        == (
                            None
                            if is_linear_dodge
                            else member_materialization["source"]
                        ),
                        restore["to_alpha"] == ("16" if is_linear_dodge else "3"),
                        stack["background"] == previous,
                        stack["foreground"] == restore["name"],
                        stack["apply_mode"] == 'FuID { "Normal" }',
                        stack["blend"] == expected_stack_blend,
                        stack["process_alpha"] == "0",
                    )
                )
                if member_ok and is_linear_dodge:
                    attenuate = member_attenuate[0]
                    member_ok = all(
                        (
                            attenuate["input"]
                            == member_materialization["source"],
                            attenuate["gain"] == "%.6f" % member.opacity,
                            attenuate["process_alpha"] == "0",
                        )
                    )
                previous = stack["name"]
                emitted_members.append(stack["name"])
            checks.append(member_ok)

        outer = [
            tool
            for tool in role(base.id, "Merge", "Merge")
            if "PSD clipping chain merge:" in tool["comments"]
        ]
        outer_ok = (
            len(outer) == 1
            and outer[0]["foreground"] == previous
            and bool(emitted_members)
            and outer[0]["start"]
            > max(tool["start"] for tool in tools if tool["name"] in emitted_members)
        )
        checks.append(outer_ok)
        passed = all(checks)
        if not passed:
            failures.append(chain_index)
        chain_rows.append(
            {
                "chain": chain_index,
                "base_id": base.id,
                "member_ids": list(chain.member_ids),
                "provenance": chain.blend_clipped_as_group_provenance,
                "subtree_complete_before_outer_merge": outer_ok,
                "pass": passed,
            }
        )

    return {
        "pass": not failures,
        "chains": len(doc.clipping_chains),
        "clipped_members": sum(len(chain.member_ids) for chain in doc.clipping_chains),
        "visible_clipped_members": visible_member_count,
        "groups_semantic": sum(1 for layer in walk_layers(doc.children) if layer.is_group),
        "groups_graph": sum(1 for tool in tools if tool["type"] == "GroupOperator"),
        "failed_chains": failures,
        "chain_rows": chain_rows,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("psd")
    parser.add_argument("comp")
    args = parser.parse_args()
    result = validate(args.psd, args.comp)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
