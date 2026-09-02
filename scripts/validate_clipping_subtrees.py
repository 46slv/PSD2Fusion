"""Validate generated clipping-chain boundaries without claiming pixel parity."""

import argparse
import json
import re
from pathlib import Path

from psd2fusion.parse_psd import parse_psd
from psd2fusion.semantic import index_layers, walk_layers


TOOL_HEADER = re.compile(
    r"(?m)^([ \t]*)([A-Za-z_][A-Za-z0-9_]*) = "
    r"(Background|Loader|Merge|MediaOut|GroupOperator|Note) \{"
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
    match = re.search(
        r"ViewInfo = (?:OperatorInfo|GroupInfo|StickyNoteInfo) "
        r"\{ Pos = \{ ([^,]+), ([^}]+) \} \}",
        block,
    )
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
                "apply_mode": _value(block, "ApplyMode"),
                "blend": _value(block, "Blend"),
                "operator": _value(block, "Operator"),
                "process_alpha": _value(block, "ProcessAlpha"),
                "input_target": _input_source_op(block, "MainInput1"),
                "position": _position(block),
                "comments": _value(block, "Comments") or "",
            }
        )
    return tools


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
        checks = [len(base_nodes) == 1, chain.blend_clipped_as_group]
        previous = base_nodes[0]["name"] if len(base_nodes) == 1 else None
        emitted_members = []
        for member_id in chain.member_ids:
            member = layers[member_id]
            if not member.effective_visible:
                continue
            visible_member_count += 1
            loaders = role(member.id, "Loader", "Loader")
            clips = role(member.id, "ClipIn", "Merge")
            stacks = role(member.id, "ClipStack", "Merge")
            member_ok = len(loaders) == len(clips) == len(stacks) == 1
            if member_ok:
                clip = clips[0]
                stack = stacks[0]
                member_ok = all(
                    (
                        clip["background"] == (base_nodes[0]["name"] if base_nodes else None),
                        clip["foreground"] == loaders[0]["name"],
                        clip["operator"] == 'FuID { "In" }',
                        stack["background"] == previous,
                        stack["foreground"] == clip["name"],
                        stack["process_alpha"] == "0",
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
