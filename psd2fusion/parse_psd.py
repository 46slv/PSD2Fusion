"""Adapter from psd-tools objects to the PSD2Fusion semantic IR."""

import hashlib
import importlib.metadata
import os
from typing import Any, Iterable, List, Optional, Tuple

from .semantic import SemanticDocument, SemanticGroup, SemanticLayer


# PSD four-byte blend keys and their display names. Fusion IDs are selected in
# fusion_comp.py; retaining the PSD key here makes unsupported mappings visible.
BLEND_NAMES = {
    "pass": "Pass Through",
    "norm": "Normal",
    "diss": "Dissolve",
    "dark": "Darken",
    "mul ": "Multiply",
    "idiv": "Color Burn",
    "lbrn": "Linear Burn",
    "dkCl": "Darker Color",
    "lite": "Lighten",
    "scrn": "Screen",
    "div ": "Color Dodge",
    "lddg": "Linear Dodge",
    "lgCl": "Lighter Color",
    "over": "Overlay",
    "sLit": "Soft Light",
    "hLit": "Hard Light",
    "vLit": "Vivid Light",
    "lLit": "Linear Light",
    "pLit": "Pin Light",
    "hMix": "Hard Mix",
    "diff": "Difference",
    "smud": "Exclusion",
    "fsub": "Subtract",
    "fdiv": "Divide",
    "hue ": "Hue",
    "sat ": "Saturation",
    "colr": "Color",
    "lum ": "Luminosity",
}

_ENUM_NAME_TO_KEY = {
    name.replace("_", " ").lower(): key for key, name in BLEND_NAMES.items()
}


def _raw_children(container: Any) -> List[Any]:
    """Return psd-tools children in its native bottom-to-top order."""

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


def _is_group(layer: Any) -> bool:
    marker = getattr(layer, "is_group", False)
    try:
        marker = marker() if callable(marker) else marker
    except Exception:
        marker = False
    return bool(marker)


def _kind(layer: Any) -> str:
    value = getattr(layer, "kind", "pixel")
    if hasattr(value, "value"):
        value = value.value
    if isinstance(value, bytes):
        value = value.decode("latin1", "replace")
    return str(value or "pixel").strip().lower()


def _blend(layer: Any) -> Tuple[str, str]:
    value = getattr(layer, "blend_mode", None) or getattr(layer, "blendMode", None)
    enum_name = str(getattr(value, "name", "") or "").strip().lower()
    if enum_name and enum_name in _ENUM_NAME_TO_KEY:
        key = _ENUM_NAME_TO_KEY[enum_name]
    else:
        if hasattr(value, "value"):
            value = value.value
        if isinstance(value, bytes):
            key = value.decode("latin1", "replace")
        else:
            key = str(value or "norm")
        # PSD raw blend keys are four bytes and may intentionally end in a
        # space (for example ``mul ``). Only human-readable names are trimmed.
        if len(key) != 4:
            key = key.strip()
        if key.lower() in _ENUM_NAME_TO_KEY:
            key = _ENUM_NAME_TO_KEY[key.lower()]
    return key, BLEND_NAMES.get(key, str(key).title())


def _bbox(layer: Any) -> Tuple[int, int, int, int]:
    try:
        box = tuple(int(value) for value in layer.bbox)
        if len(box) == 4:
            return box  # type: ignore[return-value]
    except Exception:
        pass
    return (0, 0, 0, 0)


def _opacity(value: Any, default: float = 1.0) -> float:
    try:
        return max(0.0, min(1.0, float(value) / 255.0))
    except (TypeError, ValueError):
        return default


def _fill_opacity(layer: Any) -> Optional[float]:
    try:
        value = int(getattr(layer, "fill_opacity"))
    except Exception:
        return None
    if value == 255:
        return None
    return max(0.0, min(1.0, value / 255.0))


def _has_mask(layer: Any, attribute: str) -> bool:
    try:
        value = getattr(layer, attribute)
        if callable(value):
            value = value()
        return value is not None and value is not False
    except Exception:
        return False


def _parser_version() -> str:
    try:
        return importlib.metadata.version("psd-tools")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _stable_id(source_hash: str, structural_path: str) -> str:
    return hashlib.sha256(
        (source_hash + ":" + structural_path).encode("utf-8")
    ).hexdigest()[:16]


def _mode_name(psd: Any) -> str:
    value = getattr(psd, "color_mode", "RGB")
    return str(getattr(value, "name", value)).upper()


def parse_psd(path: str) -> SemanticDocument:
    """Read a PSD and return a deterministic semantic document.

    `psd-tools` exposes layer lists in bottom-to-top order (its clipping API
    searches `parent[index + 1:]` for clipped siblings), so this adapter does
    not reverse them. That ordering is the invariant consumed by the compiler.
    """

    try:
        from psd_tools import PSDImage
    except ImportError as exc:
        raise RuntimeError(
            "psd-tools is required; run `python -m pip install -e .`"
        ) from exc

    path = os.path.abspath(path)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    with open(path, "rb") as handle:
        source_hash = hashlib.sha256(handle.read()).hexdigest()
    psd = PSDImage.open(path)
    mode = _mode_name(psd)
    depth = int(getattr(psd, "depth", 8) or 8)
    document = SemanticDocument(
        source_path=path,
        source_sha256=source_hash,
        parser="psd-tools",
        parser_version=_parser_version(),
        width=int(psd.width),
        height=int(psd.height),
        color_mode=mode,
        depth=depth,
        capabilities={
            "ordinary_layers": "native",
            "groups": "reconstructed",
            "clipping": "reconstructed",
            "layer_masks": "unknown",
            "advanced_layers": "selectively-baked",
        },
    )
    if mode != "RGB" or depth != 8:
        document.warnings.append(
            "Source is not 8-bit RGB; derivatives are converted to RGBA when possible"
        )

    def visit(
        raw_items: Iterable[Any],
        parent_id: Optional[str],
        parent_visible: bool,
        structural_prefix: str,
    ) -> List[SemanticLayer]:
        nodes: List[SemanticLayer] = []
        for index, raw in enumerate(raw_items):
            structural_path = structural_prefix + "/" + str(index)
            stable_id = _stable_id(source_hash, structural_path)
            name = str(getattr(raw, "name", "Layer") or "Layer")
            own_visible = bool(getattr(raw, "visible", True))
            effective_visible = parent_visible and own_visible
            raw_blend, blend = _blend(raw)
            kind = "group" if _is_group(raw) else _kind(raw)
            unsupported: List[str] = []
            if kind not in ("pixel", "group"):
                unsupported.append(kind)
            fill_opacity = _fill_opacity(raw)
            if fill_opacity is not None:
                unsupported.append("fill-opacity")
            if _has_mask(raw, "mask"):
                unsupported.append("pixel-mask")
            if _has_mask(raw, "vector_mask") or _has_mask(raw, "has_vector_mask"):
                unsupported.append("vector-mask")
            child_nodes = (
                visit(
                    _raw_children(raw),
                    stable_id,
                    effective_visible,
                    structural_path,
                )
                if kind == "group"
                else []
            )
            if kind == "group":
                node: SemanticLayer = SemanticGroup(
                    id=stable_id,
                    name=name,
                    parent_id=parent_id,
                    sibling_index=index,
                    raw_index=index,
                    bbox=_bbox(raw),
                    visible=own_visible,
                    effective_visible=effective_visible,
                    opacity=_opacity(getattr(raw, "opacity", 255)),
                    fill_opacity=fill_opacity,
                    raw_blend=raw_blend,
                    blend=blend,
                    children=child_nodes,
                    pass_through=raw_blend == "pass",
                    isolated=raw_blend != "pass",
                    decision="reconstructed",
                    unsupported=unsupported,
                )
            else:
                node = SemanticLayer(
                    id=stable_id,
                    name=name,
                    kind=kind,
                    parent_id=parent_id,
                    sibling_index=index,
                    raw_index=index,
                    bbox=_bbox(raw),
                    visible=own_visible,
                    effective_visible=effective_visible,
                    opacity=_opacity(getattr(raw, "opacity", 255)),
                    fill_opacity=fill_opacity,
                    raw_blend=raw_blend,
                    blend=blend,
                    decision="selectively-baked" if unsupported else "native",
                    unsupported=unsupported,
                )
            if unsupported:
                node.warnings.append(
                    "Unsupported PSD semantics are rasterized when psd-tools yields pixels"
                )
            if node.pass_through and node.opacity < 0.999999:
                node.unsupported.append("pass-through-opacity")
                node.warnings.append(
                    "Pass Through group opacity is outside the first-slice native path"
                )
            nodes.append(node)
        return nodes

    raw_roots = _raw_children(psd)
    document.children = visit(raw_roots, None, True, "root")

    def attach_clipping(raw_items: List[Any], nodes: List[SemanticLayer]) -> None:
        base: Optional[SemanticLayer] = None
        member_ids: List[str] = []
        for raw, node in zip(raw_items, nodes):
            try:
                clipped = bool(getattr(raw, "clipping", False))
            except Exception:
                clipped = False
            if clipped:
                if base is None:
                    node.warnings.append("Orphan clipping flag has no preceding base")
                    document.warnings.append(
                        "Layer %s has an orphan clipping flag" % node.id
                    )
                else:
                    node.clipping_base_id = base.id
                    base.clipping_members.append(node.id)
                    member_ids.append(node.id)
            else:
                if base is not None and member_ids:
                    document.clipping_chains.append(
                        {"base_id": base.id, "member_ids": list(member_ids)}
                    )
                base = node
                member_ids = []
            if node.children:
                attach_clipping(_raw_children(raw), node.children)
        if base is not None and member_ids:
            document.clipping_chains.append(
                {"base_id": base.id, "member_ids": list(member_ids)}
            )

    attach_clipping(raw_roots, document.children)
    return document
