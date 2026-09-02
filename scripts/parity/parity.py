"""Fail-closed PSD/reference inspection and deterministic image comparison."""

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

from PIL import Image, ImageChops, PngImagePlugin

MAX_THRESHOLD = 32.0
OUTLIER_GUARD = 32


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _channels(mode: str) -> int:
    return {"1": 1, "L": 1, "LA": 2, "P": 1, "RGB": 3, "RGBA": 4,
            "I": 1, "F": 1, "CMYK": 4, "YCbCr": 3}.get(mode, len(mode))


def _alpha_facts(im: Image.Image) -> Dict[str, Any]:
    if "A" not in im.getbands():
        return {"present": False, "min": None, "max": None, "all_opaque": True}
    lo, hi = im.getchannel("A").getextrema()
    return {"present": True, "min": int(lo), "max": int(hi), "all_opaque": lo == 255 and hi == 255}


def inspect_input(path: str | os.PathLike[str], role: str = "input") -> Dict[str, Any]:
    p = Path(path).expanduser().resolve()
    result: Dict[str, Any] = {"path": str(p), "role": role, "exists": p.is_file()}
    if not p.is_file():
        result["error"] = "missing_or_unreadable"
        return result
    result["size_bytes"] = p.stat().st_size
    result["sha256_before"] = _sha256(p)
    try:
        with Image.open(p) as im:
            profile = im.info.get("icc_profile")
            result.update({"format": im.format, "dimensions": {"width": im.width, "height": im.height},
                "mode": im.mode, "channels": _channels(im.mode), "bit_depth": 16 if im.mode.startswith("I;16") else 8,
                "has_alpha": "A" in im.getbands(), "bands": list(im.getbands()), "alpha": _alpha_facts(im),
                "profile": "icc" if profile else "unprofiled", "icc_profile_sha256": hashlib.sha256(profile).hexdigest() if profile else None,
                "metadata_keys": sorted(str(k) for k in im.info.keys()), "icc_profile_bytes": len(profile or b""),
                "orientation": im.getexif().get(274) if hasattr(im, "getexif") else None})
    except Exception as exc:
        result["error"] = f"unreadable:{type(exc).__name__}:{exc}"
    return result


def inspect_psd(path: str | os.PathLike[str]) -> Dict[str, Any]:
    p = Path(path).expanduser().resolve(); result = inspect_input(p, "psd")
    if not result.get("exists"): return result
    try:
        from psd_tools import PSDImage
        from psd_tools.constants import Resource
        psd = PSDImage.open(p); mode = getattr(psd.color_mode, "name", str(psd.color_mode)); mode = str(mode).upper()
        profile_obj = psd.image_resources.get(Resource.ICC_PROFILE); profile = getattr(profile_obj, "data", b"") if profile_obj else b""
        result.update({"format": "PSD", "dimensions": {"width": int(psd.width), "height": int(psd.height)}, "mode": mode,
            "channels": 4 if mode == "RGBA" else 3 if mode == "RGB" else None, "bit_depth": int(getattr(psd, "depth", 8) or 8),
            "has_alpha": mode == "RGBA", "bands": ["R", "G", "B", "A"] if mode == "RGBA" else ["R", "G", "B"],
            "alpha": {"present": mode == "RGBA", "source": "PSD header"}, "profile": "icc" if profile else "unprofiled",
            "icc_profile_sha256": hashlib.sha256(profile).hexdigest() if profile else None, "icc_profile_bytes": len(profile), "layer_count": len(list(psd))})
        try:
            from psd2fusion.parse_psd import parse_psd
            from psd2fusion.semantic import walk_layers
            doc = parse_psd(str(p)); layers = list(walk_layers(doc.children))
            result["structure_counts"] = {"descendants": len(layers), "groups": sum(x.is_group for x in layers), "clipping_chains": len(doc.clipping_chains), "clipped_members": sum(len(x.member_ids) for x in doc.clipping_chains), "source": "recomputed from psd-tools semantic parse"}
        except Exception as exc: result["structure_counts_error"] = f"{type(exc).__name__}:{exc}"
    except Exception as exc: result["error"] = f"psd_unreadable:{type(exc).__name__}:{exc}"
    return result


def _percentile(values: list[float], q: float) -> float:
    if not values: return 0.0
    values = sorted(values); pos = (len(values) - 1) * q; lo, hi = math.floor(pos), math.ceil(pos)
    return float(values[lo] if lo == hi else values[lo] + (values[hi] - values[lo]) * (pos - lo))


def _signed_image(candidate: Image.Image, reference: Image.Image, path: Path) -> None:
    encoded = []
    for c, r in zip(candidate.getdata(), reference.getdata()):
        encoded.append(tuple(max(0, min(255, int(round(128 + (c[i] - r[i]) / 2.0)))) for i in range(4)))
    image = Image.new("RGBA", candidate.size); image.putdata(encoded); info = PngImagePlugin.PngInfo()
    info.add_text("signed_encoding", "candidate_minus_reference"); info.add_text("neutral", "128"); info.add_text("scale", "2.0 encoded units per channel delta"); info.add_text("channels", "RGBA; alpha channel is signed alpha delta")
    path.parent.mkdir(parents=True, exist_ok=True); image.save(path, pnginfo=info)


def _profile_status(c: Image.Image, r: Image.Image) -> str:
    cp, rp = c.info.get("icc_profile"), r.info.get("icc_profile")
    if cp is not None and rp is not None: return "match" if cp == rp else "mismatch"
    return "unverified"


def _edge_pixels(c: Image.Image, r: Image.Image) -> list[int]:
    ca, ra = list(c.getchannel("A").getdata()), list(r.getchannel("A").getdata()); w, h = c.size; out = []
    for i in range(w * h):
        x, y = i % w, i // w; vals = (ca[i], ra[i]); edge = any(0 < v < 255 for v in vals)
        if not edge:
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if 0 <= nx < w and 0 <= ny < h:
                    j = ny * w + nx
                    if any(abs(vals[k] - (ca[j], ra[j])[k]) > 0 for k in range(2)): edge = True; break
        if edge: out.append(i)
    return out


def compare_images(candidate: str | os.PathLike[str] | Image.Image, reference: str | os.PathLike[str] | Image.Image,
                   output_dir: str | os.PathLike[str] | None = None, threshold: float = 0.0) -> Dict[str, Any]:
    def load(value: Any) -> Image.Image:
        return value.copy() if isinstance(value, Image.Image) else Image.open(Path(value)).copy()
    try: c, r = load(candidate), load(reference)
    except Exception as exc: return {"status": "BLOCKED", "hard_failure": "missing_or_unreadable", "reason": str(exc)}
    result: Dict[str, Any] = {"candidate": str(candidate) if not isinstance(candidate, Image.Image) else "<image>", "reference": str(reference) if not isinstance(reference, Image.Image) else "<image>", "candidate_dimensions": [c.width, c.height], "reference_dimensions": [r.width, r.height], "candidate_channels": _channels(c.mode), "reference_channels": _channels(r.mode), "threshold": threshold, "profile_status": _profile_status(c, r)}
    if not math.isfinite(threshold) or threshold < 0 or threshold > MAX_THRESHOLD: result.update({"status": "FAIL", "hard_failure": "invalid_threshold", "reason": f"threshold must be finite and between 0 and {MAX_THRESHOLD}"}); return result
    if c.size != r.size: result.update({"status": "FAIL", "hard_failure": "dimension_mismatch", "reason": "unexplained dimensions; resize/crop is forbidden"}); return result
    if _channels(c.mode) != _channels(r.mode) or ("A" in c.getbands()) != ("A" in r.getbands()): result.update({"status": "FAIL", "hard_failure": "channel_mismatch", "reason": "channel presence differs; normalization is forbidden"}); return result
    profile_mismatch = result["profile_status"] == "mismatch"
    c, r = c.convert("RGBA"), r.convert("RGBA"); cp, rp = list(c.getdata()), list(r.getdata())
    diffs = [[abs(a[i] - b[i]) for i in range(4)] for a, b in zip(cp, rp)]; rgb = [max(d[:3]) for d in diffs]; alpha = [d[3] for d in diffs]; exceed = [d for d in rgb if d > threshold]
    changed = [(i % c.width, i // c.width) for i, d in enumerate(diffs) if any(d)]; bbox = None
    if changed: xs, ys = zip(*changed); bbox = (min(xs), min(ys), max(xs) + 1, max(ys) + 1)
    edge = [max(diffs[i][:3]) for i in _edge_pixels(c, r)]; opaque = [max(d[:3]) for i, d in enumerate(diffs) if cp[i][3] >= 250 and rp[i][3] >= 250]; ti = [i for i in range(len(diffs)) if cp[i][3] == 0 and rp[i][3] == 0]; transparent = [max(diffs[i][:3]) for i in ti]
    # Thresholds are retained as a reporting metric, but never relax parity
    # qualification.  A non-zero channel delta is an explicit mismatch even
    # when it falls below the caller-provided threshold; otherwise a threshold
    # could hide a material one-pixel outlier and produce a false PASS.
    rgb_mismatch = any(rgb)
    alpha_mismatch = any(alpha)
    outlier_count = sum(1 for d in rgb if d >= OUTLIER_GUARD)
    status = "FAIL" if profile_mismatch or rgb_mismatch or alpha_mismatch else ("UNVERIFIED" if result["profile_status"] == "unverified" else "PASS")
    result.update({"status": status, "hard_failure": "profile_mismatch" if profile_mismatch else None, "reason": "ICC profiles differ; hidden conversion is forbidden" if profile_mismatch else ("pixel_mismatch; threshold is reporting-only" if rgb_mismatch or alpha_mismatch else None), "threshold_policy": "strict; threshold reports exceeding pixels but cannot relax nonzero pixel deltas", "outlier_guard": {"threshold": OUTLIER_GUARD, "count": outlier_count}, "rgba_error": {"max": max((max(d) for d in diffs), default=0), "mean": sum(max(d) for d in diffs) / len(diffs), "p99": _percentile([max(d) for d in diffs], .99)}, "rgb_error": {"max": max(rgb, default=0), "mean": sum(rgb) / len(rgb), "p99": _percentile(rgb, .99)}, "alpha_error": {"max": max(alpha, default=0), "mean": sum(alpha) / len(alpha), "p99": _percentile(alpha, .99)}, "threshold_exceeding": {"count": len(exceed), "ratio": len(exceed) / len(rgb) if rgb else 0}, "regions": {"edge_band": {"pixel_count": len(edge), "max": max(edge, default=0), "mean": sum(edge) / len(edge) if edge else 0}, "opaque": {"max": max(opaque, default=0), "mean": sum(opaque) / len(opaque) if opaque else 0}, "transparent": {"max": max(transparent, default=0), "mean": sum(transparent) / len(transparent) if transparent else 0}, "transparent_rgb": {"max": max(transparent, default=0), "mean": sum(transparent) / len(transparent) if transparent else 0}}, "difference_bbox": list(bbox) if bbox else None, "alpha_facts": {"candidate": _alpha_facts(c), "reference": _alpha_facts(r)}})
    if output_dir:
        out = Path(output_dir); out.mkdir(parents=True, exist_ok=True); ImageChops.difference(c, r).save(out / "diff_absolute.png"); _signed_image(c, r, out / "diff_signed.png"); ad = ImageChops.difference(c.getchannel("A"), r.getchannel("A")); Image.merge("RGBA", (Image.new("L", c.size),) * 3 + (ad,)).save(out / "diff_alpha.png"); result["artifacts"] = {k: str(out / v) for k, v in {"absolute": "diff_absolute.png", "signed": "diff_signed.png", "alpha": "diff_alpha.png"}.items()}
    return result


def _environment() -> Dict[str, Any]:
    try: import PIL; pillow = getattr(PIL, "__version__", "unknown")
    except Exception: pillow = "unknown"
    try: import psd_tools; psd_tools_version = getattr(psd_tools, "__version__", "unknown")
    except Exception: psd_tools_version = "unavailable"
    try: git_head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip(); git_branch = subprocess.check_output(["git", "branch", "--show-current"], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception: git_head, git_branch = "unknown", "unknown"
    return {"windows": platform.platform(), "python": platform.python_version(), "psd_tools": psd_tools_version, "pillow": pillow, "git_head": git_head, "git_branch": git_branch}


def _qualification(psd: Dict[str, Any], ref: Dict[str, Any]) -> Dict[str, Any]:
    if not psd.get("exists") or psd.get("error") or not ref.get("exists") or ref.get("error"): return {"classification": "blocked", "reason": "missing_or_unreadable_input", "resize": False, "crop": False, "profile_transform": False}
    dm = psd.get("dimensions") == ref.get("dimensions"); cc = psd.get("channels") == ref.get("channels") or (psd.get("channels") == 3 and ref.get("channels") == 4 and ref.get("alpha", {}).get("all_opaque") is True); pm = psd.get("profile") == "icc" and ref.get("profile") == "icc" and psd.get("icc_profile_sha256") == ref.get("icc_profile_sha256")
    if not dm: cls, reason = "blocked", "dimension_mismatch"
    elif not cc: cls, reason = "blocked", "channel_mismatch"
    elif not pm: cls, reason = "ambiguous", "profile_unverified_or_mismatch"
    else: cls, reason = "exact_canvas", "dimensions_channels_profile_justified"
    return {"classification": cls, "reason": reason, "resize": False, "crop": False, "orient": False, "profile_transform": False, "dimensions_match": dm, "channels_compatible": cc, "profile_match": pm, "channel_note": "PSD RGB gains explicit opaque alpha only when reference alpha is proven all-opaque"}


def _safe_summary(value: Any) -> Any:
    if isinstance(value, dict): return {k: _safe_summary(v) for k, v in value.items() if k != "path"}
    if isinstance(value, list): return [_safe_summary(v) for v in value]
    if isinstance(value, str) and ("Downloads" in value or "\\Users\\" in value): return "<private-input>"
    return value


def run_inspection(psd_path: str, reference_path: str, output: Path) -> Dict[str, Any]:
    before_psd, before_ref = inspect_psd(psd_path), inspect_input(reference_path, "reference"); norm = _qualification(before_psd, before_ref); valid = bool(before_psd.get("exists") and not before_psd.get("error") and before_ref.get("exists") and not before_ref.get("error")); inspection_status = "PASS" if valid and norm.get("classification") == "exact_canvas" else "BLOCKED"; result: Dict[str, Any] = {"schema_version": 2, "status": inspection_status, "inspection_status": inspection_status, "qualification_status": norm.get("classification"), "psd": before_psd, "reference": before_ref, "normalization": norm, "environment": _environment(), "command": " ".join(sys.argv)}
    if valid:
        try:
            from psd_tools import PSDImage
            comp_path = output.parent / "psd_stored_composite.png"; comp_path.parent.mkdir(parents=True, exist_ok=True); PSDImage.open(psd_path).composite().convert("RGBA").save(comp_path); result["psd_stored_composite"] = {"path": str(comp_path), "sha256": _sha256(comp_path), "origin": "psd_stored_composite"}
            if norm.get("classification") == "exact_canvas":
                result["stored_composite_comparison"] = compare_images(comp_path, reference_path, output.parent / "stored-composite-diff")
                result["comparison_status"] = result["stored_composite_comparison"].get("status")
                if result["comparison_status"] != "PASS":
                    # The baseline is not qualified when its stored composite
                    # is FAIL or UNVERIFIED.  Keep inspection/qualification
                    # status separate while making the top-level result and
                    # process exit explicitly fail closed.
                    result["status"] = result["comparison_status"]
                    result["reason"] = "stored_composite_comparison:" + str(result["comparison_status"])
        except Exception as exc: result["status"] = "BLOCKED"; result["psd_stored_composite"] = {"error": str(exc), "origin": "psd_stored_composite"}
    else: result["reason"] = "missing_or_unreadable_input"
    result["after_sha256"] = {"psd": _sha256(Path(psd_path)) if Path(psd_path).is_file() else None, "reference": _sha256(Path(reference_path)) if Path(reference_path).is_file() else None}; result["inputs_unchanged"] = bool(valid and result["after_sha256"].get("psd") == before_psd.get("sha256_before") and result["after_sha256"].get("reference") == before_ref.get("sha256_before")); comparison_status = result.get("comparison_status"); result["exit_codes"] = {"inspect": 0 if result.get("status") == "PASS" and result.get("inputs_unchanged") else (2 if comparison_status in {"FAIL", "UNVERIFIED"} else 3), "stored_composite_compare": (0 if comparison_status == "PASS" else 2 if comparison_status == "UNVERIFIED" or comparison_status == "FAIL" else 3) if "stored_composite_comparison" in result else None}; result["privacy"] = {"private_input_paths_committed": False, "safe_summary": True}; output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(_safe_summary(result), indent=2, ensure_ascii=False), encoding="utf-8"); return result


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest="command", required=True); i = sub.add_parser("inspect"); i.add_argument("--psd", required=True); i.add_argument("--reference", required=True); i.add_argument("--output", required=True); v = sub.add_parser("convert"); v.add_argument("--psd", required=True); v.add_argument("--output", required=True); c = sub.add_parser("compare"); c.add_argument("--candidate", required=True); c.add_argument("--reference", required=True); c.add_argument("--output-dir"); c.add_argument("--threshold", type=float, default=0.0); c.add_argument("--json", required=True); args = parser.parse_args(argv)
    if args.command == "inspect": result = run_inspection(args.psd, args.reference, Path(args.output)); print(json.dumps(result, indent=2, ensure_ascii=False)); return 0 if result.get("status") == "PASS" and result.get("inputs_unchanged") else 3
    if args.command == "convert":
        try:
            from psd_tools import PSDImage
            out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True); PSDImage.open(args.psd).composite().convert("RGBA").save(out); print(json.dumps({"status": "PASS", "origin": "psd_stored_composite", "path": str(out.resolve()), "sha256": _sha256(out)}, indent=2)); return 0
        except Exception as exc: print(json.dumps({"status": "BLOCKED", "error": str(exc)})); return 3
    result = compare_images(args.candidate, args.reference, args.output_dir, args.threshold); Path(args.json).write_text(json.dumps(result, indent=2), encoding="utf-8"); print(json.dumps(result, indent=2)); return 0 if result.get("status") == "PASS" else 2


if __name__ == "__main__": raise SystemExit(main())
