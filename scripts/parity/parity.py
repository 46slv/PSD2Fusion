"""Deterministic PSD/reference inspection and image comparison.

The module intentionally keeps source identity, normalization, and comparison
separate.  It is usable from PowerShell (``python scripts/parity/parity.py``)
and from unit tests without requiring a Resolve/Photoshop installation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from PIL import Image, ImageChops


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _channels(mode: str) -> int:
    return {"1": 1, "L": 1, "LA": 2, "P": 1, "RGB": 3, "RGBA": 4,
            "I": 1, "F": 1, "CMYK": 4, "YCbCr": 3}.get(mode, len(mode))


def inspect_input(path: str | os.PathLike[str], role: str = "input") -> Dict[str, Any]:
    """Inspect a PNG/raster input, preserving identity and metadata facts."""
    p = Path(path).expanduser().resolve()
    result: Dict[str, Any] = {"path": str(p), "role": role, "exists": p.is_file()}
    if not p.is_file():
        result["error"] = "missing_or_unreadable"
        return result
    result["size_bytes"] = p.stat().st_size
    result["sha256_before"] = _sha256(p)
    try:
        with Image.open(p) as im:
            result.update({
                "format": im.format,
                "dimensions": {"width": im.width, "height": im.height},
                "mode": im.mode,
                "channels": _channels(im.mode),
                "bit_depth": 16 if im.mode in ("I;16", "I;16B", "I;16L") else 8,
                "has_alpha": "A" in im.getbands(),
                "bands": list(im.getbands()),
                "profile": "icc" if im.info.get("icc_profile") else "unprofiled",
                "metadata_keys": sorted(str(k) for k in im.info.keys()),
                "icc_profile_bytes": len(im.info.get("icc_profile", b"")),
            })
    except Exception as exc:  # pragma: no cover - depends on malformed files
        result["error"] = f"unreadable:{type(exc).__name__}:{exc}"
    return result


def inspect_psd(path: str | os.PathLike[str]) -> Dict[str, Any]:
    """Inspect PSD header/profile and save the stored composite as a distinct origin."""
    p = Path(path).expanduser().resolve()
    result = inspect_input(p, "psd")
    if not result.get("exists"):
        return result
    try:
        from psd_tools import PSDImage
        from psd_tools.constants import Resource

        psd = PSDImage.open(p)
        mode = getattr(psd.color_mode, "name", str(psd.color_mode))
        profile = psd.image_resources.get(Resource.ICC_PROFILE)
        profile_bytes = getattr(profile, "data", b"") if profile else b""
        result.update({
            "format": "PSD",
            "dimensions": {"width": int(psd.width), "height": int(psd.height)},
            "mode": str(mode).upper(),
            "channels": 4 if str(mode).upper() == "RGBA" else 3 if str(mode).upper() == "RGB" else None,
            "bit_depth": int(getattr(psd, "depth", 8) or 8),
            "profile": "icc" if profile_bytes else "unprofiled",
            "icc_profile_bytes": len(profile_bytes),
            "layer_count": len(list(psd)),
        })
    except Exception as exc:
        result["error"] = f"psd_unreadable:{type(exc).__name__}:{exc}"
    return result


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    pos = (len(values) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    if lo == hi:
        return float(values[lo])
    return values[lo] + (values[hi] - values[lo]) * (pos - lo)


def _save_diff(images: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    images.save(path)


def compare_images(candidate: str | os.PathLike[str] | Image.Image,
                   reference: str | os.PathLike[str] | Image.Image,
                   output_dir: str | os.PathLike[str] | None = None,
                   threshold: float = 0.0) -> Dict[str, Any]:
    """Compare RGBA images and emit machine-readable metrics/artifacts.

    Dimensions and channel presence are hard failures; no resize/crop/profile
    conversion is performed implicitly.
    """
    def load(value: Any) -> Image.Image:
        if isinstance(value, Image.Image):
            return value.copy()
        return Image.open(Path(value)).copy()

    c = load(candidate)
    r = load(reference)
    result: Dict[str, Any] = {
        "candidate": str(candidate) if not isinstance(candidate, Image.Image) else "<image>",
        "reference": str(reference) if not isinstance(reference, Image.Image) else "<image>",
        "candidate_dimensions": [c.width, c.height],
        "reference_dimensions": [r.width, r.height],
        "candidate_channels": _channels(c.mode),
        "reference_channels": _channels(r.mode),
        "threshold": threshold,
    }
    if c.size != r.size:
        result.update({"status": "FAIL", "hard_failure": "dimension_mismatch", "reason": "unexplained dimensions; resize/crop is forbidden"})
        return result
    if _channels(c.mode) != _channels(r.mode) or ("A" in c.getbands()) != ("A" in r.getbands()):
        result.update({"status": "FAIL", "hard_failure": "channel_mismatch"})
        return result
    c = c.convert("RGBA")
    r = r.convert("RGBA")
    cp, rp = list(c.getdata()), list(r.getdata())
    diffs = [[abs(a[i] - b[i]) for i in range(4)] for a, b in zip(cp, rp)]
    rgb = [max(d[:3]) for d in diffs]
    alpha = [d[3] for d in diffs]
    exceed = [d for d in rgb if d > threshold]
    # Pillow's RGBA getbbox can ignore RGB-only differences when alpha is zero;
    # compute the union explicitly so RGB and alpha outliers are both visible.
    changed = [(i % c.width, i // c.width) for i, d in enumerate(diffs) if any(d)]
    if changed:
        xs, ys = zip(*changed); bbox = (min(xs), min(ys), max(xs) + 1, max(ys) + 1)
    else:
        bbox = None
    # Region metrics make alpha/edge failures visible instead of hiding them in means.
    edge = []
    opaque = []
    transparent = []
    transparent_rgb = []
    for i, (a, b) in enumerate(zip(cp, rp)):
        x, y = i % c.width, i // c.width
        is_edge = x == 0 or y == 0 or x == c.width - 1 or y == c.height - 1
        if is_edge: edge.append(max(diffs[i][:3]))
        if a[3] >= 250 and b[3] >= 250: opaque.append(max(diffs[i][:3]))
        if a[3] == 0 and b[3] == 0:
            transparent.append(max(diffs[i][:3])); transparent_rgb.append(max(diffs[i][:3]))
    result.update({
        "status": "PASS" if not exceed and not any(alpha) else "FAIL",
        "hard_failure": None,
        "rgba_error": {"max": max((max(d) for d in diffs), default=0), "mean": sum(max(d) for d in diffs) / len(diffs), "p99": _percentile([max(d) for d in diffs], .99)},
        "rgb_error": {"max": max(rgb, default=0), "mean": sum(rgb) / len(rgb), "p99": _percentile(rgb, .99)},
        "alpha_error": {"max": max(alpha, default=0), "mean": sum(alpha) / len(alpha), "p99": _percentile(alpha, .99)},
        "threshold_exceeding": {"count": len(exceed), "ratio": len(exceed) / len(rgb)},
        "regions": {"edge_band": {"max": max(edge, default=0), "mean": sum(edge) / len(edge) if edge else 0}, "opaque": {"max": max(opaque, default=0), "mean": sum(opaque) / len(opaque) if opaque else 0}, "transparent": {"max": max(transparent, default=0), "mean": sum(transparent) / len(transparent) if transparent else 0}, "transparent_rgb": {"max": max(transparent_rgb, default=0), "mean": sum(transparent_rgb) / len(transparent_rgb) if transparent_rgb else 0}},
        "difference_bbox": list(bbox) if bbox else None,
    })
    if output_dir:
        out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
        _save_diff(ImageChops.difference(c, r), out / "diff_absolute.png")
        _save_diff(ImageChops.multiply(ImageChops.invert(r), c), out / "diff_signed.png")
        _save_diff(Image.merge("RGBA", (Image.new("L", c.size),) * 3 + (ImageChops.difference(c.getchannel("A"), r.getchannel("A")),)), out / "diff_alpha.png")
        result["artifacts"] = {k: str(out / v) for k, v in {"absolute": "diff_absolute.png", "signed": "diff_signed.png", "alpha": "diff_alpha.png"}.items()}
    return result


def run_inspection(psd_path: str, reference_path: str, output: Path) -> Dict[str, Any]:
    before_psd = inspect_psd(psd_path); before_ref = inspect_input(reference_path, "reference")
    result: Dict[str, Any] = {"schema_version": 1, "psd": before_psd, "reference": before_ref, "normalization": {}}
    if before_psd.get("exists") and before_ref.get("exists"):
        pd, rd = before_psd.get("dimensions"), before_ref.get("dimensions")
        result["normalization"] = {"classification": "exact_canvas" if pd == rd else "unexplained_dimension_mismatch", "resize": False, "crop": False, "profile_transform": False, "dimensions_match": pd == rd, "channels_match": before_psd.get("channels") == before_ref.get("channels"), "channel_note": "PSD stored RGB is compared as RGBA with explicit opaque alpha"}
        # psd-tools stored composite is explicitly a third origin.
        try:
            from psd_tools import PSDImage
            comp_path = output.parent / "psd_stored_composite.png"; comp_path.parent.mkdir(parents=True, exist_ok=True)
            PSDImage.open(psd_path).composite().convert("RGBA").save(comp_path)
            result["psd_stored_composite"] = {"path": str(comp_path), "sha256": _sha256(comp_path), "origin": "psd_stored_composite"}
            result["stored_composite_comparison"] = compare_images(comp_path, reference_path, output.parent / "stored-composite-diff")
        except Exception as exc:
            result["psd_stored_composite"] = {"error": str(exc), "origin": "psd_stored_composite"}
    result["after_sha256"] = {"psd": _sha256(Path(psd_path)) if Path(psd_path).is_file() else None, "reference": _sha256(Path(reference_path)) if Path(reference_path).is_file() else None}
    result["inputs_unchanged"] = result["after_sha256"].get("psd") == before_psd.get("sha256_before") and result["after_sha256"].get("reference") == before_ref.get("sha256_before")
    output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    i = sub.add_parser("inspect"); i.add_argument("--psd", required=True); i.add_argument("--reference", required=True); i.add_argument("--output", required=True)
    v = sub.add_parser("convert"); v.add_argument("--psd", required=True); v.add_argument("--output", required=True)
    c = sub.add_parser("compare"); c.add_argument("--candidate", required=True); c.add_argument("--reference", required=True); c.add_argument("--output-dir"); c.add_argument("--threshold", type=float, default=0.0); c.add_argument("--json", required=True)
    args = parser.parse_args(argv)
    if args.command == "inspect":
        result = run_inspection(args.psd, args.reference, Path(args.output)); print(json.dumps(result, indent=2, ensure_ascii=False)); return 0 if result.get("inputs_unchanged") else 2
    if args.command == "convert":
        try:
            from psd_tools import PSDImage
            out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True)
            PSDImage.open(args.psd).composite().convert("RGBA").save(out)
            print(json.dumps({"origin": "psd_stored_composite", "path": str(out.resolve()), "sha256": _sha256(out)}, indent=2)); return 0
        except Exception as exc:
            print(json.dumps({"status": "BLOCKED", "error": str(exc)})); return 3
    result = compare_images(args.candidate, args.reference, args.output_dir, args.threshold); Path(args.json).write_text(json.dumps(result, indent=2), encoding="utf-8"); print(json.dumps(result, indent=2)); return 0 if result.get("status") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
