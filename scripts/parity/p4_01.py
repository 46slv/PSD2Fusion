"""Build and compare the two concrete P4-01 clipping lowerings.

This is a graph-recipe fixture, not a renderer or host harness. Candidate A is
the canonical ``Operator=In`` plus local ``ClipStack`` lowering emitted by the
converter. Candidate B is the tempting one-Merge ``EffectMask`` alternative.
The report includes the smallest alpha witness showing why B cannot preserve a
fixed base matte under ordinary Over alpha processing.
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

from psd2fusion.fusion_comp import (
    _Source,
    _background,
    _indent,
    _input_connection,
    _loader,
    _merge,
    _simple_tool,
    compile_comp,
)
from psd2fusion.semantic import ClippingChain, SemanticDocument, SemanticLayer


BASE_ID = "p401base0001"
MEMBER_ID = "p401member01"
OUTER_ID = "p401outer0001"
SOURCE_HASH = "p401" + "0" * 60


def _fixture_document() -> SemanticDocument:
    outer = SemanticLayer(
        id=OUTER_ID,
        name="P4-01 outer backdrop",
        asset_path="assets/outer.png",
        blend="Normal",
    )
    base = SemanticLayer(
        id=BASE_ID,
        name="P4-01 base (fixed matte)",
        asset_path="assets/base.png",
        blend="Normal",
        clipping_members=[MEMBER_ID],
    )
    member = SemanticLayer(
        id=MEMBER_ID,
        name="P4-01 clipped member",
        asset_path="assets/member.png",
        clipping_base_id=BASE_ID,
        blend="Normal",
    )
    return SemanticDocument(
        source_path="p4-01-fixture.psd",
        source_sha256=SOURCE_HASH,
        parser="fixture",
        parser_version="1",
        width=4,
        height=4,
        children=[outer, base, member],
        clipping_chains=[
            ClippingChain(
                base_id=BASE_ID,
                member_ids=[MEMBER_ID],
                blend_clipped_as_group=True,
                blend_clipped_as_group_provenance="photoshop_default_true",
            )
        ],
    )


def _composition(tools: Sequence[str], width: int, height: int) -> str:
    return "\n".join(
        [
            "Composition {",
            "\tCurrentTime = 0,",
            "\tRenderRange = { 0, 1000 },",
            "\tGlobalRange = { 0, 1000 },",
            "\tCurrentID = %d," % (len(tools) + 1),
            "\tPlaybackUpdateMode = 0,",
            "\tVersion = \"1.2\",",
            "\tSavedOutputs = 0,",
            "\tHeldTools = 0,",
            "\tDisabledTools = 0,",
            "\tLockedTools = 0,",
            "\tAudioOffset = 0,",
            "\tResX = %d," % int(width),
            "\tResY = %d," % int(height),
            "\tPlaybackFrames = 0,",
            "\tPlaybackTime = 0,",
            "\tTransportState = 0,",
            "\tCurrentTool = \"MediaOut1\",",
            "\tTools = {",
            _indent("\n".join(tools), "\t\t"),
            "\t},",
            "\tViews = {",
            "\t\t{",
            "\t\t\tFrameTypeID = \"FlowView\",",
            "\t\t\tMode = 0,",
            "\t\t\tViewOffsetX = 0,",
            "\t\t\tViewOffsetY = 0,",
            "\t\t\tViewScale = 1",
            "\t\t}",
            "\t}",
            "}",
        ]
    ) + "\n"


def _write_candidate_b(path: Path) -> Dict[str, str]:
    """Write the direct EffectMask candidate for structural comparison only."""

    root = _Source("BackgroundP401")
    outer = _Source("LoaderP401_outer")
    base = _Source("LoaderP401_base")
    member = _Source("LoaderP401_member")
    tools: List[str] = [
        _background("BackgroundP401", 4, 4, "P4-01 transparent canvas", -220.0, 0.0),
        _loader(
            "LoaderP401_outer",
            str(path.parent / "assets" / "outer.png"),
            "P4-01 outer backdrop",
            0.0,
            0.0,
        ),
        _merge(
            "MergeP401_outer",
            root,
            outer,
            "Normal",
            1.0,
            "P4-01 outer backdrop merge",
            180.0,
            0.0,
        ),
        _loader(
            "LoaderP401_base",
            str(path.parent / "assets" / "base.png"),
            "P4-01 base (fixed matte)",
            360.0,
            110.0,
        ),
        _loader(
            "LoaderP401_member",
            str(path.parent / "assets" / "member.png"),
            "P4-01 clipped member",
            360.0,
            -110.0,
        ),
        _merge(
            "MergeP401_direct_mask",
            base,
            member,
            "Normal",
            1.0,
            "P4-01 candidate B: base alpha as EffectMask (not selected)",
            540.0,
            0.0,
            effect_mask=base,
        ),
        _merge(
            "MergeP401_direct_outer",
            _Source("MergeP401_outer"),
            _Source("MergeP401_direct_mask"),
            "Normal",
            1.0,
            "P4-01 candidate B output",
            720.0,
            0.0,
        ),
        _simple_tool(
            "MediaOut1",
            "MediaOut",
            [_input_connection("Input", _Source("MergeP401_direct_outer"))],
            "P4-01 candidate B output",
            940.0,
            0.0,
        ),
    ]
    path.write_text(_composition(tools, 4, 4), encoding="utf-8")
    return _artifact(path)


def _artifact(path: Path) -> Dict[str, str]:
    data = path.read_bytes()
    return {"path": path.name, "size": str(len(data)), "sha256": hashlib.sha256(data).hexdigest()}


def _candidate_a_checks(text: str) -> Dict[str, bool]:
    return {
        "one_operator_in": text.count('Operator = Input { Value = FuID { "In" }, }') == 1,
        "one_clip_rgb_alpha_boundary": text.count("ChannelBoolean {") == 1
        and text.count("P4-HOST-PIXEL: ClipIn RGB + member alpha") == 1,
        "one_fixed_alpha_stack": text.count("ProcessAlpha = Input { Value = 0, }") == 1,
        "one_outer_chain_merge": text.count("PSD clipping chain merge:") == 1,
        "member_local_merge_comment": "P4-01 local Merge" in text,
        "base_matte_comment": "P4-01 fixed matte via Operator=In" in text,
    }


def _candidate_b_checks(text: str) -> Dict[str, bool]:
    return {
        "effect_mask_connection": "EffectMask = Input { SourceOp = \"LoaderP401_base\"" in text,
        "no_operator_in": 'Operator = Input { Value = FuID { "In" }, }' not in text,
        "single_direct_merge": text.count("MergeP401_direct_mask = Merge") == 1,
    }


def _direct_mask_alpha(base_alpha: float, member_alpha: float) -> float:
    """Ordinary source-over alpha after an ideal alpha EffectMask."""

    masked_member_alpha = base_alpha * member_alpha
    return base_alpha + masked_member_alpha * (1.0 - base_alpha)


def compare_candidates(output: Path) -> Dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    document = _fixture_document()
    candidate_a_path = output / "candidate_a.comp"
    graph = compile_comp(document, str(candidate_a_path))
    candidate_a_text = candidate_a_path.read_text(encoding="utf-8")
    candidate_b_path = output / "candidate_b.comp"
    candidate_b_artifact = _write_candidate_b(candidate_b_path)

    base_alpha = 0.5
    member_alpha = 1.0
    direct_alpha = _direct_mask_alpha(base_alpha, member_alpha)
    witness = {
        "base_alpha": base_alpha,
        "member_alpha": member_alpha,
        "candidate_a_local_alpha": base_alpha,
        "candidate_b_ideal_effect_mask_alpha": direct_alpha,
        "candidate_b_alpha_expands": direct_alpha != base_alpha,
        "transparent_base_alpha": 0.0,
        "transparent_base_candidate_a_alpha": 0.0,
        "candidate_b_transparent_rgb_requires_explicit_alpha": True,
    }
    report: Dict[str, Any] = {
        "schema_version": 1,
        "task": "PARITY-004",
        "item": "P4-01",
        "selected": "A",
        "recipe": "operator_in_fixed_matte_local_stack",
        "decision": {
            "status": "selected",
            "reason": [
                "Candidate B's direct EffectMask is only an effect/foreground limiter; even with an ideal base-alpha mask, ordinary source-over alpha expands a partial matte.",
                "Candidate A makes the alpha intersection explicit with Operator=In, then uses a local Merge with ProcessAlpha=0 to retain the fixed base coverage before the outer boundary.",
                "Candidate B would need an additional alpha-preserving stage or equivalent custom handling, so it is not the smaller 1:1 recipe.",
                "Candidate B's direct EffectMask connection has no explicit alpha-channel extraction, so its transparent-RGB contract is not inspectable; Candidate A consumes the matte alpha at the In boundary.",
                "A zero-alpha base remains canonical transparent in Candidate A; no outer backdrop is connected to ClipIn or ClipStack.",
            ],
            "fusion_manual_basis": "Merge Effect Mask limits the Merge effect, while Operator=In multiplies foreground pixels by the background alpha; the structural candidate is therefore evaluated with ordinary source-over alpha.",
        },
        "witness": witness,
        "candidates": {
            "A": {
                "description": "Loader base -> shared matte / ClipIn Operator=In <- Loader member -> local ClipStack Merge -> one outer chain Merge",
                "artifact": _artifact(candidate_a_path),
                "graph": graph,
                "checks": _candidate_a_checks(candidate_a_text),
            },
            "B": {
                "description": "Loader base -> Merge Background and EffectMask; Loader member -> Merge Foreground",
                "artifact": candidate_b_artifact,
                "checks": _candidate_b_checks(candidate_b_path.read_text(encoding="utf-8")),
            },
        },
    }
    report["pass"] = (
        report["selected"] == "A"
        and all(report["candidates"]["A"]["checks"].values())
        and all(report["candidates"]["B"]["checks"].values())
        and witness["candidate_b_alpha_expands"]
    )
    report_path = output / "comparison.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    result = compare_candidates(args.output)
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
