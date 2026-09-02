"""Strict compositing capability registry.

Names in Fusion are not proof that the renderer produces the required pixels.
The registry therefore keeps the four PARITY-003 candidates ``unverified``
until a summary packet contains deterministic semantic-fixture evidence, PSD
provenance, an actual Fusion pixel artifact, and a golden-reference comparison
tied to one exact commit. Photoshop is optional historical/additional evidence.
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
            "Fusion ApplyMode name is not pixel proof; PARITY-004 requires "
            "deterministic semantic fixtures, PSD provenance, and an actual "
            "Fusion render/reference comparison tied to the exact commit"
        ),
        constraints={
            "color_space": "declared 8-bit RGB profile",
            "alpha": "straight/premult boundary must be recorded",
            "proof_required": [
                "deterministic_fixture_evidence",
                "psd_semantic_provenance",
                "fusion_render_artifact",
                "reference_png_comparison",
            ],
            "optional_evidence": ["gimp_cross_renderer", "photoshop_historical"],
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

    required = (
        "candidate_commit",
        "proof_id",
        "deterministic_fixtures",
        "psd_provenance",
        "resolve_fusion",
        "reference_comparison",
        "metrics",
    )
    if any(not evidence.get(field) for field in required):
        return False
    fixtures = evidence.get("deterministic_fixtures")
    provenance = evidence.get("psd_provenance")
    resolve = evidence.get("resolve_fusion")
    comparison = evidence.get("reference_comparison")
    metrics = evidence.get("metrics")
    artifact = resolve.get("render_artifact") if isinstance(resolve, Mapping) else None
    artifact_complete = (
        isinstance(artifact, Mapping)
        and artifact.get("path") not in (None, "", "not_run")
        and artifact.get("sha256") not in (None, "", "not_run")
    )
    return (
        isinstance(fixtures, Mapping)
        and fixtures.get("status") == "PASS"
        and isinstance(provenance, Mapping)
        and provenance.get("status") == "PASS"
        and provenance.get("source_sha256") not in (None, "", "not_run")
        and isinstance(resolve, Mapping)
        and resolve.get("version") not in (None, "", "not_run")
        and artifact_complete
        and isinstance(comparison, Mapping)
        and comparison.get("status") == "PASS"
        and isinstance(metrics, Mapping)
        and metrics.get("rgba_error") is not None
        and metrics.get("alpha_error") is not None
    )
