"""PSD2Fusion semantic intermediate representation.

The IR is deliberately independent of psd-tools and Fusion. It keeps the
information needed to make a graph decision, including information that the
first graph cannot yet render.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple

BBox = Tuple[int, int, int, int]


@dataclass
class ClippingChain:
    """One same-parent PSD clipping chain in canonical bottom-to-top order."""

    base_id: str
    member_ids: List[str] = field(default_factory=list)
    blend_clipped_as_group: bool = True
    blend_clipped_as_group_provenance: str = "photoshop_default_true"


@dataclass
class SemanticLayer:
    id: str
    name: str
    kind: str = "layer"
    parent_id: Optional[str] = None
    sibling_index: int = 0
    raw_index: int = 0
    bbox: BBox = (0, 0, 0, 0)
    visible: bool = True
    effective_visible: bool = True
    opacity: float = 1.0
    fill_opacity: Optional[float] = None
    raw_blend: str = "norm"
    blend: str = "Normal"
    asset_id: Optional[str] = None
    asset_path: Optional[str] = None
    decision: str = "native"
    warnings: List[str] = field(default_factory=list)
    unsupported: List[str] = field(default_factory=list)
    clipping_base_id: Optional[str] = None
    clipping_members: List[str] = field(default_factory=list)
    children: List["SemanticLayer"] = field(default_factory=list)
    pass_through: bool = False
    isolated: bool = False

    @property
    def is_group(self) -> bool:
        return self.kind == "group"


@dataclass
class SemanticGroup(SemanticLayer):
    kind: str = "group"


@dataclass
class SemanticDocument:
    source_path: str
    source_sha256: str
    parser: str
    parser_version: str
    width: int
    height: int
    color_mode: str = "RGB"
    depth: int = 8
    profile: Optional[str] = None
    # Children are normalized to PSD2Fusion's bottom-to-top order.
    children: List[SemanticLayer] = field(default_factory=list)
    clipping_chains: List[ClippingChain] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    capabilities: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def walk_layers(children: Iterable[SemanticLayer]) -> Iterator[SemanticLayer]:
    for layer in children:
        yield layer
        if layer.children:
            yield from walk_layers(layer.children)


def index_layers(children: Iterable[SemanticLayer]) -> Dict[str, SemanticLayer]:
    return {layer.id: layer for layer in walk_layers(children)}
