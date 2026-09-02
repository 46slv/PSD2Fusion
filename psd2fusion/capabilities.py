"""Strict compositing capability registry.

Names in Fusion are not proof that Photoshop and Fusion produce the same
pixels.  The registry therefore keeps the four PARITY-003 candidates
``unverified`` until a summary packet contains both Photoshop/reference and
Resolve/Fusion pixel evidence tied to one exact commit.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Mapping, Optional

from .compositing import CORE_BLEND_MODES


REGISTRY_STATUSES = (
    "verified_fusion_native",
    "verified_custom",
    "verified_bake",
    "detected_unsupported",
    "rejected",
    "unverified",
)


@dataclass(frozen=True)
class CapabilityRecord:
    operation: str
    status: str
    backend: str
    fusion_id: Optional[str] = None
    proof_id: Optional[str] = None
    reason: str = ""
    constraints: Mapping[str, Any] = field(default_factory=dict)
    evidence: Optional[str] = None

    def __post_init__(self) -> None:
        if self.status not in REGISTRY_STATUSES:
            raise ValueError("unknown capability status: %s" % self.status)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _unverified_blend(mode: str, fusion_id: str) -> CapabilityRecord:
    return CapabilityRecord(
        operation="blend:%s" % mode,
        status="unverified",
        backend="fusion_native_candidate",
        fusion_id=fusion_id,
        reason=(
            "Fusion ApplyMode name is not Photoshop pixel proof; "
            "PARITY-003 requires a Photoshop oracle and a Resolve/Fusion "
            "host render tied to the exact commit"
        ),
        constraints={
            "color_space": "declared 8-bit RGB profile",
            "alpha": "straight/premult boundary must be recorded",
            "proof_required": ["photoshop_reference_pixels", "fusion_host_render"],
        },
    )


CAPABILITY_REGISTRY: Dict[str, CapabilityRecord] = {
    mode: _unverified_blend(mode, mode.replace(" ", ""))
    for mode in CORE_BLEND_MODES
}
CAPABILITY_REGISTRY.update(
    {
        "ordinary_opacity": CapabilityRecord(
            operation="ordinary_opacity",
            status="unverified",
            backend="fusion_native_candidate",
            reason="Opacity stage needs source/backdrop alpha and host pixel proof",
            constraints={"stages": ["source_alpha", "overall_opacity"]},
        ),
        "isolated_group_opacity": CapabilityRecord(
            operation="isolated_group_opacity",
            status="unverified",
            backend="fusion_native_candidate",
            reason="Isolated subtree boundary needs nested host pixel proof",
            constraints={"boundary": "transparent local backdrop"},
        ),
        "nested_opacity": CapabilityRecord(
            operation="nested_opacity",
            status="unverified",
            backend="fusion_native_candidate",
            reason="Nested group opacity needs boundary-by-boundary host proof",
            constraints={"stages": ["child", "group", "parent"]},
        ),
        "color_space": CapabilityRecord(
            operation="color_space",
            status="unverified",
            backend="explicit_fixture_contract",
            reason="ICC/profile and working-space behavior needs host/reference proof",
            constraints={"profiles": "record exact ICC bytes"},
        ),
    }
)


def capability_for_blend(mode: str) -> CapabilityRecord:
    """Return a registry record, with unknown modes explicitly rejected."""

    record = CAPABILITY_REGISTRY.get(mode)
    if record is not None:
        return record
    return CapabilityRecord(
        operation="blend:%s" % mode,
        status="rejected",
        backend="none",
        reason="blend mode has no declared lowering or proof; strict mode rejects it",
    )


def capability_for(operation: str) -> CapabilityRecord:
    record = CAPABILITY_REGISTRY.get(operation)
    if record is None:
        return CapabilityRecord(
            operation=operation,
            status="unverified",
            backend="none",
            reason="operation is not present in the strict capability registry",
        )
    return record


def registry_snapshot() -> Dict[str, Dict[str, Any]]:
    return {name: record.to_dict() for name, record in sorted(CAPABILITY_REGISTRY.items())}


def proof_fields_complete(evidence: Mapping[str, Any]) -> bool:
    """Check the minimum fields required before a record can be promoted.

    This helper deliberately does not mutate the registry.  Promotion remains
    an evidence/state-transition decision after a fresh verifier pass.
    """

    required = ("candidate_commit", "proof_id", "photoshop", "resolve_fusion", "metrics")
    if any(not evidence.get(field) for field in required):
        return False
    photoshop = evidence.get("photoshop")
    resolve = evidence.get("resolve_fusion")
    metrics = evidence.get("metrics")
    return (
        isinstance(photoshop, Mapping)
        and photoshop.get("version") not in (None, "", "not_run")
        and isinstance(resolve, Mapping)
        and resolve.get("version") not in (None, "", "not_run")
        and isinstance(metrics, Mapping)
        and metrics.get("rgba_error") is not None
        and metrics.get("alpha_error") is not None
    )
