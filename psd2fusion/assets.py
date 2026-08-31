"""Materialize deterministic full-canvas RGBA derivatives."""

import hashlib
import os
from typing import Any, Dict, Iterable, List

from .semantic import SemanticDocument, SemanticLayer, walk_layers


def _children(container: Any) -> List[Any]:
    for attr in ("_layers", "layers"):
        try:
            value = getattr(container, attr)
        except Exception:
            continue
        if value is not None:
            try:
                return list(value)
            except TypeError:
                pass
    try:
        return list(container)
    except Exception:
        return []


def _raw_by_id(
    nodes: Iterable[SemanticLayer], raw_items: Iterable[Any]
) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for node, raw in zip(nodes, raw_items):
        result[node.id] = raw
        if node.children:
            result.update(_raw_by_id(node.children, _children(raw)))
    return result


def _paste_clipped(canvas: Any, image: Any, left: int, top: int) -> None:
    """Paste an image while safely handling negative/overscan layer bounds."""

    image_width, image_height = image.size
    dst_left = max(0, left)
    dst_top = max(0, top)
    src_left = max(0, -left)
    src_top = max(0, -top)
    width = min(image_width - src_left, canvas.width - dst_left)
    height = min(image_height - src_top, canvas.height - dst_top)
    if width <= 0 or height <= 0:
        return
    cropped = image.crop((src_left, src_top, src_left + width, src_top + height))
    canvas.alpha_composite(cropped, (dst_left, dst_top))


def materialize_assets(
    doc: SemanticDocument, psd_obj: Any, out_dir: str
) -> Dict[str, Dict[str, Any]]:
    """Create one document-sized PNG for every visible non-group layer.

    `topil()` is intentionally used instead of `layer.composite()`: the latter
    can include a PSD clipping chain, while clipping is reconstructed by the
    Fusion compiler. Unsupported kinds are still allowed to use their raster
    pixels, but their decision remains explicitly `selectively-baked`.
    """

    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError(
            "Pillow is required; run `python -m pip install -e .`"
        ) from exc

    output_dir = os.path.abspath(out_dir)
    assets_dir = os.path.join(output_dir, "assets")
    os.makedirs(assets_dir, exist_ok=True)
    raw_by_id = _raw_by_id(doc.children, _children(psd_obj))
    records: Dict[str, Dict[str, Any]] = {}

    for layer in walk_layers(doc.children):
        if layer.is_group or not layer.effective_visible:
            continue
        raw = raw_by_id.get(layer.id)
        if raw is None:
            layer.decision = "rejected"
            layer.warnings.append("PSD layer could not be matched to parser output")
            continue
        try:
            image = raw.topil()
            if image is None:
                raise RuntimeError("psd-tools returned no raster pixels")
            image = image.convert("RGBA")
            canvas = Image.new("RGBA", (doc.width, doc.height), (0, 0, 0, 0))
            left, top, _right, _bottom = layer.bbox
            _paste_clipped(canvas, image, int(left), int(top))
            filename = "layer-" + layer.id + ".png"
            target = os.path.join(assets_dir, filename)
            canvas.save(target, format="PNG", optimize=False, compress_level=9)
            with open(target, "rb") as handle:
                asset_hash = hashlib.sha256(handle.read()).hexdigest()
            layer.asset_id = layer.id
            layer.asset_path = os.path.relpath(target, output_dir).replace("\\", "/")
            records[layer.id] = {
                "path": layer.asset_path,
                "sha256": asset_hash,
                "size": [doc.width, doc.height],
                "bbox": list(layer.bbox),
                "decision": layer.decision,
            }
        except Exception as exc:
            layer.decision = "rejected"
            layer.warnings.append("Unable to rasterize layer: " + str(exc))
            doc.warnings.append(
                "Layer %s (%s) could not be rasterized" % (layer.id, layer.name)
            )
    return records
