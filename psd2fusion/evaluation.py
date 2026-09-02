"""Evaluation IR and strict capability planning.

The evaluation plan contains Photoshop compositing order/backdrop scope only;
it deliberately has no Fusion node identifiers.  Raw layer provenance is
carried through every operation so unsupported semantics cannot disappear.
"""
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

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
    # Only modes with an explicit proof entry are native.  This is an IR
    # decision, not a claim that Fusion's same-named control is pixel-correct.
    native = {"Normal", "Multiply", "Linear Dodge", "Overlay"}
    if unsupported:
        status = "rejected" if policy == "strict" else "verified_bake"
        return CapabilityDecision(status, "layer", ",".join(unsupported), policy,
                                  {"raw_blend": getattr(layer, "raw_blend", None), "source_id": layer.id})
    if blend in native:
        return CapabilityDecision("verified_fusion_native", "layer", "fixture registry", policy,
                                  {"raw_blend": getattr(layer, "raw_blend", None), "source_id": layer.id})
    status = "rejected" if policy == "strict" else "unverified"
    return CapabilityDecision(status, "blend", "blend mode lacks promotion proof", policy,
                              {"raw_blend": getattr(layer, "raw_blend", None), "source_id": layer.id})


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
            # Group scope is native only when the parser found no unsupported
            # semantics.  In particular, Pass Through groups with fractional
            # opacity carry ``pass-through-opacity`` provenance and must not be
            # silently treated as a native Fusion group.
            unsupported = list(getattr(layer, "unsupported", []) or [])
            if unsupported:
                status = "rejected" if policy == "strict" else "verified_bake"
                dec = CapabilityDecision(status, kind, ",".join(unsupported), policy,
                                         {"source_id": layer.id, "raw_blend": getattr(layer, "raw_blend", None)})
            else:
                dec = CapabilityDecision("verified_fusion_native", kind, "group scope", policy, {"source_id": layer.id})
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
                od = CapabilityDecision("verified_fusion_native", "opacity_stage", "explicit opacity boundary", policy, {"source_id": layer.id})
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
        status = "verified_fusion_native" if chain.blend_clipped_as_group else ("rejected" if policy == "strict" else "verified_bake")
        plan.decisions.append(CapabilityDecision(status, "clipping_span", "clbl=false requires explicit fallback" if not chain.blend_clipped_as_group else "same-parent local span", policy, span))
    return plan
