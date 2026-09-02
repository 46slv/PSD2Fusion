"""Deterministic grouped/default clipping fixtures and validator.

This is an executable semantic oracle for ``clbl`` absent/default-true and
explicit-true spans.  It does not promote a Fusion capability: Photoshop
pixels and a tied Resolve render remain required for that decision.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from psd2fusion.compositing import CORE_BLEND_MODES, composite_clipping_span


RGBA = Tuple[float, float, float, float]
BACKDROPS: Tuple[Tuple[str, RGBA], ...] = (
    ("transparent", (0.73, 0.31, 0.12, 0.0)),
    ("black", (0.0, 0.0, 0.0, 1.0)),
    ("white", (1.0, 1.0, 1.0, 1.0)),
    ("gray", (0.5, 0.5, 0.5, 1.0)),
    ("saturated", (0.08, 0.86, 0.25, 1.0)),
    ("partial-alpha", (0.18, 0.42, 0.76, 0.5)),
)
BASE_ALPHAS = (0.0, 0.25, 0.5, 0.75, 1.0)
MEMBER_ALPHAS = (0.0, 0.5, 1.0)
OPACITIES = (0.0, 0.5, 1.0)


def _byte(value: float) -> int:
    return int(round(max(0.0, min(1.0, value)) * 255.0))


def _case(backdrop_name: str, backdrop: RGBA, mode: str, base_alpha: float,
          member_alpha: float, opacity: float, order: int) -> Dict[str, Any]:
    base = (0.23, 0.57, 0.91, base_alpha)
    first = ((0.91, 0.19, 0.07, member_alpha), mode, opacity)
    second = ((0.11, 0.83, 0.39, 0.75), "Normal", 0.5)
    members = [first, second] if order == 0 else [second, first]
    expected = composite_clipping_span(backdrop, base, members, base_mode=mode, base_opacity=opacity)
    return {
        "id": "%s-%s-ba%03d-ma%03d-o%03d-r%d" % (
            mode.lower().replace(" ", "_"), backdrop_name,
            round(base_alpha * 1000), round(member_alpha * 1000),
            round(opacity * 1000), order),
        "backdrop": list(backdrop), "base": list(base),
        "members": [[list(pixel), member_mode, member_opacity] for pixel, member_mode, member_opacity in members],
        "base_mode": mode, "base_opacity": opacity, "clbl": True,
        "expected": list(expected), "expected_rgba8": [_byte(v) for v in expected],
    }


def cases() -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for mode in CORE_BLEND_MODES:
        for backdrop_name, backdrop in BACKDROPS:
            for base_alpha in BASE_ALPHAS:
                for member_alpha in MEMBER_ALPHAS:
                    for opacity in OPACITIES:
                        for order in (0, 1):
                            result.append(_case(backdrop_name, backdrop, mode, base_alpha, member_alpha, opacity, order))
    return result


def _evaluate(record: Dict[str, Any]) -> RGBA:
    members = [(tuple(item[0]), item[1], float(item[2])) for item in record["members"]]
    return composite_clipping_span(
        tuple(record["backdrop"]), tuple(record["base"]), members,
        base_mode=record["base_mode"], base_opacity=float(record["base_opacity"]),
    )


def generate(output: Path) -> Dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    manifest = {"schema_version": 1, "task": "PARITY-004", "policy": "clbl-true-only",
                "cases": cases(), "case_count": len(cases()),
                "axes": {"modes": list(CORE_BLEND_MODES), "backdrops": [x[0] for x in BACKDROPS],
                         "base_alpha": list(BASE_ALPHAS), "member_alpha": list(MEMBER_ALPHAS),
                         "opacity": list(OPACITIES), "orders": [0, 1]}}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {"status": "PASS", "output": str(output), "case_count": len(manifest["cases"]),
            "clbl_policy": "absent/default true and explicit true only"}


def validate(fixtures: Path) -> Dict[str, Any]:
    manifest = json.loads((fixtures / "manifest.json").read_text(encoding="utf-8"))
    failures: List[str] = []
    max_error = 0.0
    for record in manifest.get("cases", []):
        actual = _evaluate(record)
        expected = tuple(record["expected"])
        error = max(abs(actual[i] - expected[i]) for i in range(4))
        max_error = max(max_error, error)
        if error > 1e-12:
            failures.append(record["id"] + ":oracle-mismatch")
    # Metamorphic guards for fixed matte and local scope.
    base = (0.2, 0.4, 0.8, 0.5)
    no_member = composite_clipping_span((0.0, 0.0, 0.0, 1.0), base, [((1, 0, 0, 1), "Normal", 0)])
    base_only = composite_clipping_span((0.0, 0.0, 0.0, 1.0), base, [])
    if no_member != base_only:
        failures.append("transparent-or-opacity-zero-member-not-no-op")
    zero = composite_clipping_span((0.1, 0.2, 0.3, 1.0), (1, 0, 0, 0), [((1, 1, 1, 1), "Linear Dodge", 1)])
    if zero != (0.1, 0.2, 0.3, 1.0):
        failures.append("zero-alpha-base-leaks-members")
    return {"status": "PASS" if not failures else "FAIL", "case_count": len(manifest.get("cases", [])),
            "recomputed_cases": len(manifest.get("cases", [])) - len([x for x in failures if x.endswith("oracle-mismatch")]),
            "max_oracle_error": max_error, "metamorphic_failures": failures,
            "clbl_policy": "true only; clbl=false excluded"}


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate"); gen.add_argument("--output", type=Path, required=True)
    val = sub.add_parser("validate"); val.add_argument("--fixtures", type=Path, required=True)
    args = parser.parse_args()
    result = generate(args.output) if args.command == "generate" else validate(args.fixtures)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
