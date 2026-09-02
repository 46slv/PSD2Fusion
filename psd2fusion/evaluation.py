"""Evaluation IR and strict capability planning.

The evaluation plan contains Photoshop compositing order/backdrop scope only;
it deliberately has no Fusion node identifiers.  Raw layer provenance is
carried through every operation so unsupported semantics cannot disappear.
"""
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from .capabilities import capability_for, capability_for_blend

CAPABILITIES = (
    "verified_fusion_native", "verified_custom", "verified_bake",
    "detected_unsupported", "rejected", "unverified",
)

@dataclass
class CapabilityDecision:
    status: str
    operation: str
    reason: str = ""
    policy: str = "strict"
    provenance: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.status not in CAPABILITIES:
            raise ValueError("unknown capability status: %s" % self.status)

@dataclass
class EvaluationNode:
    id: str
    kind: str
    source_ids: List[str] = field(default_factory=list)
    parent_id: Optional[str] = None
    order: int = 0
    backdrop_scope: str = "parent"
    blend: str = "Normal"
    raw_blend: str = "norm"
    opacity: float = 1.0
    fill_opacity: Optional[float] = None
    visible: bool = True
    decision: Optional[CapabilityDecision] = None
    provenance: Dict[str, Any] = field(default_factory=dict)
    children: List[str] = field(default_factory=list)

@dataclass
class EvaluationPlan:
    schema_version: int = 1
    policy: str = "strict"
    nodes: List[EvaluationNode] = field(default_factory=list)
    decisions: List[CapabilityDecision] = field(default_factory=list)
    clipping_spans: List[Dict[str, Any]] = field(default_factory=list)
    source_sha256: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def counts(self) -> Dict[str, int]:
        return {
            "nodes": len(self.nodes),
            "decisions": len(self.decisions),
            "clipping_spans": len(self.clipping_spans),
            "clipped_members": sum(len(s.get("member_ids", [])) for s in self.clipping_spans),
        }


def _decision(layer: Any, policy: str) -> CapabilityDecision:
    unsupported = list(getattr(layer, "unsupported", []) or [])
    blend = getattr(layer, "blend", "Normal")
    if unsupported:
        status = "rejected" if policy == "strict" else "verified_bake"
        return CapabilityDecision(status, "layer", ",".join(unsupported), policy,
                                  {"raw_blend": getattr(layer, "raw_blend", None), "source_id": layer.id})
    record = capability_for_blend(blend)
    # A same-named Fusion ApplyMode is only a candidate lowering.  Until the
    # PARITY-003 proof packet has both Photoshop/reference pixels and a tied
    # Resolve render, preserve the explicit ``unverified`` state in strict IR.
    status = record.status
    if policy == "compatibility" and status == "rejected":
        status = "verified_bake"
    return CapabilityDecision(
        status,
        "blend",
        record.reason,
        policy,
        {
            "raw_blend": getattr(layer, "raw_blend", None),
            "source_id": layer.id,
            "capability": record.operation,
            "backend": record.backend,
            "fusion_id": record.fusion_id,
            "proof_id": record.proof_id,
        },
    )


def evaluate_document(document: Any, policy: str = "strict") -> EvaluationPlan:
    """Build a deterministic Evaluation IR from a SemanticDocument."""
    if policy not in ("strict", "compatibility"):
        raise ValueError("policy must be strict or compatibility")
    plan = EvaluationPlan(policy=policy, source_sha256=getattr(document, "source_sha256", None))
    counter = 0
    def visit(layer: Any, parent: Optional[str], order: int) -> str:
        nonlocal counter
        counter += 1
        kind = "transparent_subtree" if layer.is_group and not layer.effective_visible else ("pass_through" if layer.is_group and layer.pass_through else ("isolated_group" if layer.is_group else "composition"))
        if layer.is_group:
            # Group scope stays explicit in the Evaluation IR.  The strict
            # registry, rather than a same-named Fusion operator, decides
            # whether that boundary has a reproducible proof packet.
            unsupported = list(getattr(layer, "unsupported", []) or [])
            if unsupported:
                status = "rejected" if policy == "strict" else "verified_bake"
                dec = CapabilityDecision(status, kind, ",".join(unsupported), policy,
                                         {"source_id": layer.id, "raw_blend": getattr(layer, "raw_blend", None)})
            else:
                operation = (
                    "isolated_group_opacity"
                    if kind == "isolated_group"
                    else kind
                )
                record = capability_for(operation)
                dec = CapabilityDecision(
                    record.status,
                    kind,
                    record.reason or "group scope",
                    policy,
                    {
                        "source_id": layer.id,
                        "capability": record.operation,
                        "backend": record.backend,
                        "proof_id": record.proof_id,
                    },
                )
        else:
            dec = _decision(layer, policy)
        node = EvaluationNode("eval-%04d" % counter, kind, [layer.id], parent, order,
                              "parent" if layer.is_group and layer.pass_through else ("isolated" if layer.is_group else "parent"),
                              layer.blend, layer.raw_blend, layer.opacity, layer.fill_opacity,
                              layer.effective_visible, dec,
                              {"source_id": layer.id, "name": layer.name, "parent_id": layer.parent_id,
                               "raw_index": layer.raw_index, "sibling_index": layer.sibling_index,
                               "visible": layer.visible, "effective_visible": layer.effective_visible,
                               "raw_blend": layer.raw_blend, "blend": layer.blend,
                               "opacity": layer.opacity, "fill_opacity": layer.fill_opacity,
                               "clipping_base_id": layer.clipping_base_id})
        plan.nodes.append(node); plan.decisions.append(dec)
        if layer.opacity < 0.999999 or layer.fill_opacity is not None:
            counter += 1
            unsupported = list(getattr(layer, "unsupported", []) or [])
            if unsupported:
                status = "rejected" if policy == "strict" else "verified_bake"
                od = CapabilityDecision(status, "opacity_stage", ",".join(unsupported), policy,
                                        {"source_id": layer.id, "overall_opacity": layer.opacity,
                                         "fill_opacity": layer.fill_opacity})
            else:
                operation = "nested_opacity" if layer.is_group else "ordinary_opacity"
                record = capability_for(operation)
                od = CapabilityDecision(
                    record.status,
                    "opacity_stage",
                    record.reason or "explicit opacity boundary",
                    policy,
                    {
                        "source_id": layer.id,
                        "overall_opacity": layer.opacity,
                        "fill_opacity": layer.fill_opacity,
                        "capability": record.operation,
                    },
                )
            on = EvaluationNode("eval-%04d" % counter, "opacity_stage", [layer.id], node.id, order,
                                "local" if layer.is_group else "parent", layer.blend, layer.raw_blend,
                                layer.opacity, layer.fill_opacity, layer.effective_visible, od,
                                {"source_id": layer.id, "overall_opacity": layer.opacity, "fill_opacity": layer.fill_opacity})
            plan.nodes.append(on); plan.decisions.append(od)
        for idx, child in enumerate(layer.children):
            node.children.append(visit(child, node.id, idx))
        return node.id
    for idx, layer in enumerate(document.children):
        visit(layer, None, idx)
    for chain in document.clipping_chains:
        span = {"base_id": chain.base_id, "member_ids": list(chain.member_ids),
                "clbl": bool(chain.blend_clipped_as_group),
                "clbl_provenance": chain.blend_clipped_as_group_provenance,
                "backdrop_scope": "local_span", "coverage": "base_evaluated_coverage"}
        plan.clipping_spans.append(span)
        status = (
            "unverified"
            if chain.blend_clipped_as_group
            else ("rejected" if policy == "strict" else "verified_bake")
        )
        reason = (
            "clbl=false requires explicit fallback"
            if not chain.blend_clipped_as_group
            else "same-parent local span requires core blend and alpha proof"
        )
        plan.decisions.append(CapabilityDecision(status, "clipping_span", reason, policy, span))
    return plan
