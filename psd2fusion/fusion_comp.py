"""Pure semantic IR -> deterministic Fusion `.comp` generation."""

from dataclasses import dataclass
import os
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .capabilities import capability_for_blend
from .semantic import SemanticDocument, SemanticLayer, index_layers


# Fusion uses compact FuID names for several PSD modes.
FUSION_BLEND_IDS = {
    "Normal": "Normal",
    "Dissolve": "Dissolve",
    "Darken": "Darken",
    "Multiply": "Multiply",
    "Color Burn": "ColorBurn",
    "Linear Burn": "LinearBurn",
    "Darker Color": "DarkerColor",
    "Lighten": "Lighten",
    "Screen": "Screen",
    "Color Dodge": "ColorDodge",
    "Linear Dodge": "LinearDodge",
    "Lighter Color": "LighterColor",
    "Overlay": "Overlay",
    "Soft Light": "SoftLight",
    "Hard Light": "HardLight",
    "Vivid Light": "VividLight",
    "Linear Light": "LinearLight",
    "Pin Light": "PinLight",
    "Difference": "Difference",
    "Exclusion": "Exclusion",
    "Hue": "Hue",
    "Saturation": "Saturation",
    "Color": "Color",
    "Luminosity": "Luminosity",
}


@dataclass(frozen=True)
class _Source:
    name: str
    port: str = "Output"


@dataclass
class _ItemResult:
    # Actual render source consumed by parent/sibling tools.  For groups this
    # is an internal terminal, never GroupOperator.MainOutput1.
    output: _Source
    # The actual source to reuse as a clipping matte, with the same group
    # boundary rule as output.
    matte: _Source
    # A pass-through group has already consumed the caller's stream.
    consumed_backdrop: bool = False
    # Lowering-only metadata for a pass-through GroupOperator's input proxy.
    # This is the first internal consumer of the caller's backdrop, not a
    # render source exposed by the GroupOperator itself.
    backdrop_consumer: Optional[_Source] = None


@dataclass
class _SequenceResult:
    output: _Source
    tools: List[str]
    # Lowering-only metadata used to declare a pass-through input proxy.
    backdrop_consumer: Optional[_Source] = None


def _quote(value: object) -> str:
    text = str(value)
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"').replace("\r", "\\r").replace("\n", "\\n") + '"'


def _indent(text: str, prefix: str) -> str:
    return "\n".join(prefix + line if line else line for line in text.splitlines())


def _input_connection(name: str, source: Optional[_Source]) -> str:
    if source is None or not source.name:
        return "%s = Input {}," % name
    return "%s = Input { SourceOp = %s, Source = %s, }," % (
        name,
        _quote(source.name),
        _quote(source.port),
    )


def _input_value(name: str, value: str) -> str:
    return "%s = Input { Value = %s, }," % (name, value)


def _operator_info(x: float, y: float) -> str:
    return "OperatorInfo { Pos = { %.3f, %.3f } }" % (x, y)


def _simple_tool(
    name: str,
    klass: str,
    inputs: Sequence[str],
    comment: str,
    x: float,
    y: float,
) -> str:
    lines = [
        "%s = %s {" % (name, klass),
        "\tCtrlWZoom = false,",
        "\tInputs = {",
    ]
    lines.extend("\t\t" + value for value in inputs)
    if comment:
        lines.append("\t\tComments = Input { Value = %s, }," % _quote(comment))
    lines.extend(
        [
            "\t},",
            "\tViewInfo = %s," % _operator_info(x, y),
            "},",
        ]
    )
    return "\n".join(lines)


def _background(name: str, width: int, height: int, comment: str, x: float, y: float) -> str:
    return _simple_tool(
        name,
        "Background",
        [
            _input_value("Width", str(int(width))),
            _input_value("Height", str(int(height))),
            _input_value("TopLeftRed", "0"),
            _input_value("TopLeftGreen", "0"),
            _input_value("TopLeftBlue", "0"),
            _input_value("TopLeftAlpha", "0"),
        ],
        comment,
        x,
        y,
    )


def _loader(
    name: str,
    filename: str,
    comment: str,
    x: float,
    y: float,
) -> str:
    # This Clips/Clip shape is the dialect emitted by Fusion's own comp files
    # and by the inspected prior-art generators; a scalar Clip input is not.
    lines = [
        "%s = Loader {" % name,
        "\tCtrlWZoom = false,",
        "\tClips = {",
        "\t\tClip {",
        "\t\t\tID = \"Clip1\",",
        "\t\t\tFilename = %s," % _quote(filename),
        "\t\t\tFormatID = \"PNGFormat\",",
        "\t\t\tStartFrame = -1,",
        "\t\t\tLengthSetManually = true,",
        "\t\t\tGlobalStart = 0,",
        "\t\t\tGlobalEnd = 0",
        "\t\t}",
        "\t},",
        "\tInputs = {",
        # Keep PNG bytes straight until ChangeDepth promotes the stream to
        # float32.  Resolve/Fusion 21.0.3 premultiplies an int8 Loader with a
        # truncating boundary that loses one RGB LSB for fractional alpha.
        "\t\t[\"Clip1.PNGFormat.PostMultiply\"] = Input { Value = 0, },",
        "\t\tGlobalOut = Input { Value = 1000, },",
        "\t\tComments = Input { Value = %s, }," % _quote(comment),
        "\t},",
        "\tViewInfo = %s," % _operator_info(x, y),
        "},",
    ]
    return "\n".join(lines)


def _change_depth(
    name: str,
    source: _Source,
    comment: str,
    x: float,
    y: float,
) -> str:
    """Promote straight loader bytes to float32 before premultiplication."""

    return _simple_tool(
        name,
        "ChangeDepth",
        [
            _input_connection("Input", source),
            _input_value("Depth", "4"),
            _input_value("Dither", "0"),
        ],
        comment,
        x,
        y,
    )


def _merge(
    name: str,
    background: Optional[_Source],
    foreground: Optional[_Source],
    mode_id: str,
    blend: float,
    comment: str,
    x: float,
    y: float,
    operator: Optional[str] = None,
    process_alpha: Optional[bool] = None,
    effect_mask: Optional[_Source] = None,
) -> str:
    inputs: List[str] = []
    if background is not None:
        inputs.append(_input_connection("Background", background))
    if foreground is not None:
        inputs.append(_input_connection("Foreground", foreground))
    if effect_mask is not None:
        inputs.append(_input_connection("EffectMask", effect_mask))
    inputs.append(
        "ApplyMode = Input { Value = FuID { %s }, }," % _quote(mode_id)
    )
    inputs.append("Blend = Input { Value = %.6f, }," % max(0.0, min(1.0, blend)))
    if operator:
        inputs.append(
            "Operator = Input { Value = FuID { %s }, }," % _quote(operator)
        )
    if process_alpha is not None:
        inputs.append(
            "ProcessAlpha = Input { Value = %d, }," % (1 if process_alpha else 0)
        )
    inputs.append("PerformDepthMerge = Input { Value = 0, },")
    return _simple_tool(name, "Merge", inputs, comment, x, y)


def _alpha_divide(
    name: str,
    source: _Source,
    comment: str,
    x: float,
    y: float,
) -> str:
    """Convert a premultiplied stream to straight RGB while keeping alpha."""

    return _simple_tool(
        name,
        "AlphaDivide",
        [_input_connection("Input", source)],
        comment,
        x,
        y,
    )


def _channel_boolean_copy(
    name: str,
    background: _Source,
    foreground: Optional[_Source],
    to_alpha: int,
    comment: str,
    x: float,
    y: float,
) -> str:
    """Copy RGB from Background and a selected alpha channel.

    Fusion's ChannelBoolean selectors are zero-based in the scripting API:
    ``5/6/7`` are Background RGB, ``3`` is Foreground alpha, and ``16`` is
    white.  Keeping those selectors in one serializer makes the straight/
    opaque island deterministic and auditable.
    """

    inputs = [
        _input_connection("Background", background),
    ]
    if foreground is not None:
        inputs.append(_input_connection("Foreground", foreground))
    inputs.extend(
        [
            _input_value("Operation", "0"),
            _input_value("ToRed", "5"),
            _input_value("ToGreen", "6"),
            _input_value("ToBlue", "7"),
            _input_value("ToAlpha", str(to_alpha)),
            _input_value("Blend", "1"),
            _input_value("ProcessRed", "1"),
            _input_value("ProcessGreen", "1"),
            _input_value("ProcessBlue", "1"),
            _input_value("ProcessAlpha", "1"),
        ]
    )
    return _simple_tool(name, "ChannelBoolean", inputs, comment, x, y)


def _channel_boolean_force_opaque(
    name: str,
    source: _Source,
    comment: str,
    x: float,
    y: float,
) -> str:
    """Keep straight RGB and force alpha to one for a blend function."""

    return _channel_boolean_copy(name, source, None, 16, comment, x, y)


def _channel_boolean_attach_alpha(
    name: str,
    rgb_source: _Source,
    alpha_source: _Source,
    comment: str,
    x: float,
    y: float,
) -> str:
    """Keep RGB from one stream and copy alpha from another stream."""

    return _channel_boolean_copy(
        name, rgb_source, alpha_source, 3, comment, x, y
    )


def _brightness_contrast_clamp(
    name: str,
    source: _Source,
    comment: str,
    x: float,
    y: float,
) -> str:
    """Clamp blend-function RGB before member-opacity interpolation."""

    inputs = [
        _input_connection("Input", source),
        _input_value("ClipBlack", "1"),
        _input_value("ClipWhite", "1"),
        _input_value("ProcessAlpha", "0"),
    ]
    return _simple_tool(name, "BrightnessContrast", inputs, comment, x, y)


def _brightness_contrast_gain(
    name: str,
    source: _Source,
    gain: float,
    comment: str,
    x: float,
    y: float,
) -> str:
    """Scale premultiplied member RGB to its opacity in float32.

    Only the Linear Dodge late-clamp island uses this boundary; every other
    mode keeps member opacity on the local ClipStack Merge Blend control, so
    opacity is still applied exactly once.  No quantization, depth change, or
    alpha processing is added here (ProcessAlpha stays off).
    """

    inputs = [
        _input_connection("Input", source),
        _input_value("Gain", "%.6f" % max(0.0, min(1.0, gain))),
        _input_value("ProcessAlpha", "0"),
    ]
    return _simple_tool(name, "BrightnessContrast", inputs, comment, x, y)


def _alpha_multiply(
    name: str,
    source: _Source,
    comment: str,
    x: float,
    y: float,
) -> str:
    """Premultiply RGB by the attached intersection alpha."""

    return _simple_tool(
        name,
        "AlphaMultiply",
        [_input_connection("Input", source)],
        comment,
        x,
        y,
    )


def _note(name: str, comment: str, x: float, y: float) -> str:
    lines = [
        "%s = Note {" % name,
        "\tInputs = {",
        "\t\tComments = Input { Value = %s, }," % _quote(comment),
        "\t},",
        "\tViewInfo = StickyNoteInfo { Pos = { %.3f, %.3f } }," % (x, y),
        "},",
    ]
    return "\n".join(lines)


def _group_operator(
    name: str,
    inner_tools: Sequence[str],
    proxy_output: _Source,
    comment: str,
    x: float,
    y: float,
    input_target: Optional[_Source] = None,
) -> str:
    lines = [
        "%s = GroupOperator {" % name,
        "\tNameSet = true,",
        "\tInputs = ordered() {",
    ]
    if input_target is not None and input_target.name:
        lines.extend(
            [
                "\t\tMainInput1 = InstanceInput {",
                "\t\t\tSourceOp = %s," % _quote(input_target.name),
                "\t\t\tSource = %s," % _quote(input_target.port),
                "\t\t},",
            ]
        )
    lines.extend(
        [
        "\t},",
        "\tOutputs = {",
        "\t\tMainOutput1 = InstanceOutput {",
        "\t\t\tSourceOp = %s," % _quote(proxy_output.name),
        "\t\t\tSource = %s," % _quote(proxy_output.port),
        "\t\t},",
        "\t},",
        "\tViewInfo = GroupInfo { Pos = { %.3f, %.3f } }," % (x, y),
        "\tTools = ordered() {",
        ]
    )
    for tool in inner_tools:
        lines.append(_indent(tool, "\t\t"))
    lines.extend(
        [
            "\t},",
            "\tUserControls = ordered() {",
            "\t\tPSD2FusionInfo = {",
            "\t\t\tINPID_InputControl = \"LabelControl\",",
            "\t\t\tLINKS_Name = %s," % _quote(comment),
            "\t\t},",
            "\t},",
            "},",
        ]
    )
    return "\n".join(lines)


class _Compiler:
    def __init__(self, doc: SemanticDocument, output_path: str, policy: str = "strict"):
        if policy not in ("strict", "compatibility"):
            raise ValueError("policy must be strict or compatibility")
        self.doc = doc
        self.output_path = os.path.abspath(output_path)
        self.policy = policy
        self.lookup = index_layers(doc.children)
        self.clipping_chains = {
            chain.base_id: chain for chain in doc.clipping_chains
        }
        self.used_names: set[str] = set()
        self.node_count = 0
        self.merge_count = 0
        self.group_count = 0
        self.clip_count = 0
        self.blend_modes: set[str] = set()
        self._x = 0.0
        self._root_background_name: Optional[str] = None
        # Per-member rows keep the fixed-matte path readable in Flow without
        # changing the deterministic PSD evaluation order.
        self._clipping_loader_rows: Dict[str, int] = {}
        self._clipping_clip_rows: Dict[str, int] = {}
        self._clipping_stack_rows: Dict[str, int] = {}
        self._clipping_outer_rows: Dict[str, int] = {}

    def _require_clbl_policy(self) -> None:
        """Fail closed on explicit clbl=false under strict policy.

        PARITY-005 S4 decision is `reject`: the strict Evaluation IR marks a
        clbl=false span `rejected`, so strict lowering must not emit the
        legacy approximate graph. Compatibility policy keeps the explicitly
        labelled H2-characterization fallback.
        """
        false_chains = [
            chain for chain in self.doc.clipping_chains
            if not chain.blend_clipped_as_group
        ]
        if false_chains and self.policy == "strict":
            bases = ", ".join(
                "%s (%s)" % (chain.base_id[:10], chain.blend_clipped_as_group_provenance)
                for chain in false_chains
            )
            raise ValueError(
                "Strict policy rejects explicit clbl=false clipping span(s) "
                "and emits no approximate graph: %s. Use policy="
                "'compatibility' for the explicitly labelled fallback, or an "
                "explicit bake/reject path." % bases
            )

    def name(self, role: str, layer_id: str) -> str:
        base = "%s_%s" % (role, layer_id[:10])
        candidate = base
        suffix = 2
        while candidate in self.used_names:
            candidate = "%s_%d" % (base, suffix)
            suffix += 1
        self.used_names.add(candidate)
        self.node_count += 1
        return candidate

    def position(self, row: int = 0, depth: int = 0) -> Tuple[float, float]:
        self._x += 180.0
        return (self._x + depth * 40.0, float(row) * 110.0)

    def _mode_id(self, mode: str) -> str:
        record = capability_for_blend(mode)
        if record.status == "rejected":
            raise ValueError(
                "Cannot lower a blend mode rejected by the strict capability "
                "registry: %s" % mode
            )
        self.blend_modes.add(mode)
        mode_id = FUSION_BLEND_IDS.get(mode)
        if mode_id is None:
            # A same-named Fusion control is not a Photoshop proof, and an
            # unknown control must never be silently changed to Normal.  The
            # caller can choose an explicit bake/reject path instead.
            raise ValueError(
                "Cannot lower unsupported/unverified blend mode without an "
                "explicit capability decision: %s" % mode
            )
        return mode_id

    def mode_id(self, layer: SemanticLayer) -> str:
        return self._mode_id(layer.blend)

    def leaf(self, layer: SemanticLayer, depth: int, scope: str) -> _ItemResult:
        loader_name = self.name("Loader" + scope, layer.id)
        if not layer.asset_path:
            # CLI rejects this before compilation; keeping a transparent
            # placeholder here makes direct IR compilation deterministic.
            filename = os.path.join(os.path.dirname(self.output_path), "missing.png")
            layer.warnings.append("No materialized asset; graph uses missing.png")
        else:
            filename = os.path.abspath(
                os.path.join(os.path.dirname(self.output_path), layer.asset_path)
            )
        row = self._clipping_loader_rows.get(layer.id, 1)
        x, y = self.position(row, depth)
        self._current_tools.append(
            _loader(loader_name, filename, "PSD layer: %s" % layer.name, x, y)
        )
        depth_name = self.name("MaterializeDepth" + scope, layer.id)
        x, y = self.position(row, depth)
        self._current_tools.append(
            _change_depth(
                depth_name,
                _Source(loader_name),
                "PSD layer float32 materialization: %s" % layer.name
                + " [P4-HOST-PIXEL: preserve straight PNG bytes before premultiply]",
                x,
                y,
            )
        )
        premult_name = self.name("MaterializePremult" + scope, layer.id)
        x, y = self.position(row, depth)
        self._current_tools.append(
            _alpha_multiply(
                premult_name,
                _Source(depth_name),
                "PSD layer premultiply: %s" % layer.name
                + " [P4-HOST-PIXEL: float32 straight-to-premult boundary]",
                x,
                y,
            )
        )
        source = _Source(premult_name)
        return _ItemResult(source, source)

    @staticmethod
    def _group_result(
        render_source: _Source,
        consumed_backdrop: bool = False,
        backdrop_consumer: Optional[_Source] = None,
    ) -> _ItemResult:
        """Return a group result using its internal terminal as the render edge.

        ``GroupOperator.MainOutput1`` is serialized separately as an editable
        Flow proxy.  It must never become the source returned to a parent
        merge, sibling, MediaOut, or clipping matte.
        """

        return _ItemResult(
            output=render_source,
            matte=render_source,
            consumed_backdrop=consumed_backdrop,
            backdrop_consumer=backdrop_consumer,
        )

    def group(self, layer: SemanticLayer, backdrop: _Source, depth: int, scope: str) -> _ItemResult:
        # Pass-through groups retain the parent's backdrop through an exposed
        # GroupOperator input proxy. The wrapper is organizational; child Merge
        # nodes still evaluate against the caller's actual stream.
        if layer.pass_through and layer.opacity < 0.999999:
            raise ValueError(
                "Pass Through group opacity requires a verified host boundary"
            )
        native_pass = layer.pass_through and layer.opacity >= 0.999999
        if native_pass:
            group_name = self.name("Group" + scope, layer.id)
            inner_scope = scope + "P"
            inner_tools: List[str] = []
            previous_tools = self._current_tools
            self._current_tools = inner_tools
            nested = self.sequence(
                layer.children,
                backdrop,
                depth + 1,
                inner_scope,
            )
            self._current_tools = previous_tools
            input_target = nested.backdrop_consumer
            render_source = nested.output
            gx, gy = self.position(2, depth)
            if input_target is None:
                # Empty pass-through groups are kept as a readable marker and
                # leave the caller's stream unchanged.
                note_name = self.name("GroupNote" + scope, layer.id)
                self._current_tools.append(
                    _note(
                        note_name,
                        "PSD Group: %s\\nPass Through (empty)" % layer.name,
                        gx,
                        gy,
                    )
                )
                return self._group_result(backdrop, consumed_backdrop=True)
            self.group_count += 1
            self._current_tools.append(
                _group_operator(
                    group_name,
                    inner_tools,
                    render_source,
                    "PSD Group: %s (pass-through)" % layer.name,
                    gx,
                    gy,
                    input_target=input_target,
                )
            )
            return self._group_result(
                render_source,
                # The actual internal sequence consumes the caller's stream;
                # MainInput1 is retained as an editable proxy declaration.
                # Adding a parent Normal merge would double-composite the
                # pass-through result.
                consumed_backdrop=True,
                backdrop_consumer=input_target,
            )

        # Isolated group: build a self-contained transparent subtree, then let
        # the caller apply the group blend/opacity exactly once.
        group_name = self.name("Group", layer.id)
        inner_scope = scope + "I"
        inner_bg_name = self.name("GroupCanvas" + inner_scope, layer.id)
        inner_tools: List[str] = []
        previous_tools = self._current_tools
        self._current_tools = inner_tools
        bx, by = self.position(0, depth + 1)
        inner_tools.append(
            _background(
                inner_bg_name,
                self.doc.width,
                self.doc.height,
                "Transparent canvas for PSD group: %s" % layer.name,
                bx,
                by,
            )
        )
        nested = self.sequence(layer.children, _Source(inner_bg_name), depth + 1, inner_scope)
        self._current_tools = previous_tools
        render_source = nested.output
        self.group_count += 1
        gx, gy = self.position(0, depth)
        self._current_tools.append(
            _group_operator(
                group_name,
                inner_tools,
                render_source,
                "PSD Group: %s (isolated)" % layer.name,
                gx,
                gy,
            )
        )
        # GroupOperator.MainOutput1 remains the editable Flow proxy. Parent
        # render inputs must consume the internal terminal directly.
        return self._group_result(render_source)

    def item(self, layer: SemanticLayer, backdrop: _Source, depth: int, scope: str) -> _ItemResult:
        if layer.is_group:
            return self.group(layer, backdrop, depth, scope)
        return self.leaf(layer, depth, scope)

    def merge_item(
        self,
        backdrop: _Source,
        result: _ItemResult,
        layer: SemanticLayer,
        depth: int,
        scope: str,
        comment_prefix: str = "PSD layer merge",
        opacity: Optional[float] = None,
        mode: Optional[str] = None,
        backdrop_consumer: Optional[List[Optional[_Source]]] = None,
    ) -> _Source:
        effective_mode = layer.blend if mode is None else mode
        # Loader and subtree streams are premultiplied. Any separable
        # non-Normal blend function must therefore be evaluated on explicit
        # straight, opaque RGB inputs before source coverage is restored.
        # Clipping already used this boundary; ordinary layers and groups must
        # not feed premultiplied RGB directly into a same-named Fusion mode.
        if effective_mode != "Normal":
            return self._merge_non_normal_straight(
                backdrop,
                result,
                layer,
                depth,
                scope,
                opacity,
                effective_mode,
                comment_prefix,
                backdrop_consumer,
            )
        merge_name = self.name("Merge" + scope, layer.id)
        self.merge_count += 1
        row = 0
        if comment_prefix == "PSD clipping chain merge":
            row = self._clipping_outer_rows.get(layer.id, 0)
        x, y = self.position(row, depth)
        mode_id = self._mode_id(effective_mode)
        if backdrop_consumer is not None and backdrop_consumer[0] is None:
            backdrop_consumer[0] = _Source(merge_name, "Background")
        comment = "%s: %s" % (comment_prefix, layer.name)
        if comment_prefix == "PSD clipping chain merge":
            comment += " [P4-01 outer boundary; P4-04 base blend/opacity once]"
        self._current_tools.append(
            _merge(
                merge_name,
                backdrop,
                result.output,
                mode_id,
                layer.opacity if opacity is None else opacity,
                comment,
                x,
                y,
            )
        )
        return _Source(merge_name)

    def _merge_non_normal_straight(
        self,
        backdrop: _Source,
        result: _ItemResult,
        layer: SemanticLayer,
        depth: int,
        scope: str,
        opacity: Optional[float],
        mode: str,
        comment_prefix: str,
        backdrop_consumer: Optional[List[Optional[_Source]]] = None,
    ) -> _Source:
        """Lower one separable non-Normal boundary in straight RGB.

        ``result.output`` and ``backdrop`` are premultiplied streams. The
        helper constructs ``T=(1-D)S+D*B(C_D,S)`` from straight opaque inputs,
        restores ``q=A_s*opacity``, and performs one final Normal source-over.
        The same algebra applies to an ordinary layer/group and to the outer
        boundary of a completed clipping span.
        """

        if self._root_background_name is None:
            raise ValueError("straight blend boundary requires root canvas")
        mode_id = self._mode_id(mode)
        member_opacity = layer.opacity if opacity is None else opacity
        row = self._clipping_outer_rows.get(layer.id, 0)
        clipping_outer = comment_prefix == "PSD clipping chain merge"
        role_prefix = "OuterBlend" if clipping_outer else "LayerBlend"
        boundary_label = "PSD clipping outer" if clipping_outer else "PSD layer"

        def emit_name(role: str) -> str:
            return self.name(role_prefix + role + scope, layer.id)

        if clipping_outer:
            transparent_source = _Source(self._root_background_name)
        else:
            transparent_name = emit_name("Canvas")
            x, y = self.position(row + 4.0, depth)
            self._current_tools.append(
                _background(
                    transparent_name,
                    self.doc.width,
                    self.doc.height,
                    "Transparent canvas for straight blend coverage: %s"
                    % layer.name,
                    x,
                    y,
                )
            )
            transparent_source = _Source(transparent_name)

        backdrop_straight_name = emit_name("BackdropStraight")
        if backdrop_consumer is not None and backdrop_consumer[0] is None:
            backdrop_consumer[0] = _Source(backdrop_straight_name, "Input")
        x, y = self.position(row + 3.0, depth)
        self._current_tools.append(
            _alpha_divide(
                backdrop_straight_name,
                backdrop,
                "%s backdrop straight RGB: %s" % (boundary_label, layer.name)
                + " [P4-HOST-PIXEL: localized fractional-backdrop boundary]",
                x,
                y,
            )
        )

        backdrop_opaque_name = emit_name("BackdropOpaque")
        x, y = self.position(row + 2.5, depth)
        self._current_tools.append(
            _channel_boolean_force_opaque(
                backdrop_opaque_name,
                _Source(backdrop_straight_name),
                "%s backdrop opaque RGB: %s" % (boundary_label, layer.name)
                + " [P4-HOST-PIXEL: force alpha=1 for base function]",
                x,
                y,
            )
        )

        source_straight_name = emit_name("SourceStraight")
        source_kind = "completed clipping span" if clipping_outer else "layer/group stream"
        x, y = self.position(row + 1.5, depth)
        self._current_tools.append(
            _alpha_divide(
                source_straight_name,
                result.output,
                "%s source straight RGB: %s" % (boundary_label, layer.name)
                + " [P4-HOST-PIXEL: %s]" % source_kind,
                x,
                y,
            )
        )

        source_opaque_name = emit_name("SourceOpaque")
        x, y = self.position(row + 1.0, depth)
        self._current_tools.append(
            _channel_boolean_force_opaque(
                source_opaque_name,
                _Source(source_straight_name),
                "%s source opaque RGB: %s" % (boundary_label, layer.name)
                + " [P4-HOST-PIXEL: force alpha=1 for base function]",
                x,
                y,
            )
        )

        function_name = emit_name("Function")
        self.merge_count += 1
        x, y = self.position(row + 0.5, depth)
        self._current_tools.append(
            _merge(
                function_name,
                _Source(backdrop_opaque_name),
                _Source(source_opaque_name),
                mode_id,
                1.0,
                "%s blend function: %s" % (boundary_label, layer.name)
                + " [P4-HOST-PIXEL: straight opaque; Blend=1]",
                x,
                y,
            )
        )

        function_coverage_name = emit_name("FunctionCoverage")
        x, y = self.position(row + 0.0, depth)
        self._current_tools.append(
            _channel_boolean_attach_alpha(
                function_coverage_name,
                _Source(function_name),
                backdrop,
                "%s blend backdrop coverage: %s" % (boundary_label, layer.name)
                + " [P4-HOST-PIXEL: attach backdrop alpha D]",
                x,
                y,
            )
        )

        function_premult_name = emit_name("FunctionPremult")
        x, y = self.position(row - 0.25, depth)
        self._current_tools.append(
            _alpha_multiply(
                function_premult_name,
                _Source(function_coverage_name),
                "%s blend function premultiply: %s" % (boundary_label, layer.name)
                + " [P4-HOST-PIXEL: backdrop alpha * B(C_D,S)]",
                x,
                y,
            )
        )

        source_mix_name = emit_name("SourceMix")
        self.merge_count += 1
        x, y = self.position(row - 0.5, depth)
        self._current_tools.append(
            _merge(
                source_mix_name,
                _Source(source_opaque_name),
                _Source(function_premult_name),
                "Normal",
                1.0,
                "%s straight source mix: %s" % (boundary_label, layer.name)
                + " [P4-HOST-PIXEL: (1-D)S + D*B(C_D,S)]",
                x,
                y,
            )
        )

        source_coverage_name = emit_name("Coverage")
        coverage_kind = (
            "q=M*base opacity"
            if clipping_outer
            else "q=source alpha*layer/group opacity"
        )
        self.merge_count += 1
        x, y = self.position(row - 1.0, depth)
        self._current_tools.append(
            _merge(
                source_coverage_name,
                transparent_source,
                result.output,
                "Normal",
                member_opacity,
                "%s source coverage: %s" % (boundary_label, layer.name)
                + " [P4-HOST-PIXEL: %s]" % coverage_kind,
                x,
                y,
                process_alpha=True,
            )
        )

        coverage_attached_name = emit_name("CoverageAttached")
        x, y = self.position(row - 1.5, depth)
        self._current_tools.append(
            _channel_boolean_attach_alpha(
                coverage_attached_name,
                _Source(source_mix_name),
                _Source(source_coverage_name),
                "%s source mix coverage: %s" % (boundary_label, layer.name)
                + " [P4-HOST-PIXEL: attach q alpha]",
                x,
                y,
            )
        )

        premult_name = emit_name("Premult")
        x, y = self.position(row - 2.0, depth)
        self._current_tools.append(
            _alpha_multiply(
                premult_name,
                _Source(coverage_attached_name),
                "%s premultiply: %s" % (boundary_label, layer.name)
                + " [P4-HOST-PIXEL: q*((1-D)S+D*B)]",
                x,
                y,
            )
        )

        merge_name = self.name("Merge" + scope, layer.id)
        self.merge_count += 1
        x, y = self.position(row - 2.5, depth)
        final_comment = "%s: %s" % (comment_prefix, layer.name)
        if clipping_outer:
            final_comment += (
                " [P4-01 outer boundary; P4-04 base blend/opacity once; "
                "P4-HOST-PIXEL localized straight outer boundary]"
            )
        else:
            final_comment += (
                " [P4-OFFLINE straight/opaque non-Normal boundary; "
                "source alpha and opacity restored once]"
            )
        self._current_tools.append(
            _merge(
                merge_name,
                backdrop,
                _Source(premult_name),
                "Normal",
                1.0,
                final_comment,
                x,
                y,
                process_alpha=True,
            )
        )
        return _Source(merge_name)

    def clipping_merge(
        self,
        matte: _Source,
        member: _ItemResult,
        layer: SemanticLayer,
        depth: int,
        scope: str,
    ) -> _Source:
        clip_name = self.name("ClipIn" + scope, layer.id)
        self.clip_count += 1
        row = self._clipping_clip_rows.get(layer.id, 2)
        x, y = self.position(row, depth)
        self._current_tools.append(
            _merge(
                clip_name,
                matte,
                member.output,
                "Normal",
                1.0,
                "PSD clipping alpha (base=%s): %s"
                % (layer.clipping_base_id or "unknown", layer.name)
                + " [P4-01 fixed matte via Operator=In; P4-02 shared base matte]",
                x,
                y,
                operator="In",
            )
        )
        # Operator=In is deliberately kept as the fixed-matte coverage stage.
        # Its premultiplied RGB and intersection alpha feed the common
        # straight/opaque blend-function island emitted by clipping_subtree.
        return _Source(clip_name)

    def _collect_clipping_members(
        self,
        items: Sequence[SemanticLayer],
        base_index: int,
        ordered_member_ids: Sequence[str],
        *,
        strict: bool = False,
    ) -> Tuple[List[SemanticLayer], int]:
        """Collect one contiguous clipping span in canonical PSD order.

        The child list is the normalized PSD bottom-to-top sequence, while a
        ``ClippingChain`` carries the semantic member order.  First collect
        only the contiguous same-parent span, then map it back to the chain's
        declared order.  This keeps the order deterministic without ever
        using the progressively composited ClipStack as a matte.  Strict true
        clipping chains reject malformed/incomplete spans instead of silently
        dropping a member and claiming a complete local result.
        """

        member_ids = list(ordered_member_ids)
        if strict and len(set(member_ids)) != len(member_ids):
            raise ValueError("Clipping chain contains duplicate member IDs")
        member_id_set = set(member_ids)
        end = base_index + 1
        contiguous: List[SemanticLayer] = []
        while end < len(items) and items[end].id in member_id_set:
            contiguous.append(items[end])
            end += 1

        by_id = {member.id: member for member in contiguous}
        if strict:
            missing = [member_id for member_id in member_ids if member_id not in by_id]
            if missing:
                raise ValueError(
                    "Clipping chain members are not one contiguous same-parent span: %s"
                    % ", ".join(missing)
                )
        return [by_id[member_id] for member_id in member_ids if member_id in by_id], end

    def clipping_subtree(
        self,
        base_result: _ItemResult,
        base: SemanticLayer,
        members: Sequence[SemanticLayer],
        depth: int,
        scope: str,
    ) -> _ItemResult:
        """Evaluate a true/default chain with one fixed matte for every member.

        ``current`` is allowed to advance through the local ClipStack, but
        ``fixed_matte`` is captured once from the base and passed unchanged to
        every Operator=In Merge.  The caller applies the completed local span
        to the parent backdrop exactly once.
        """

        current = base_result.output
        fixed_matte = base_result.matte
        member_total = len(members)
        for member_index, member in enumerate(members, 1):
            if not member.effective_visible:
                continue
            # Put the member loaders on distinct rows above the base.  The
            # corresponding ClipIn sits one row above, while ClipStack stays
            # beside the member so the shared matte and local result are easy
            # to identify in Flow.  These are display-only overrides; the
            # node emission and stream order remain PSD bottom-to-top.
            member_row = member_index - member_total
            self._clipping_loader_rows[member.id] = member_row
            self._clipping_clip_rows[member.id] = member_row - 1
            self._clipping_stack_rows[member.id] = member_row
            member_result = self.item(member, current, depth, scope)
            clipped_source = self.clipping_merge(
                fixed_matte, member_result, member, depth, scope
            )

            # Fusion Merge evaluates non-Normal modes on premultiplied RGB.
            # Separate both streams into straight RGB with opaque alpha before
            # the mode function, then restore the ClipIn intersection coverage
            # and the original member alpha around the final Normal Merge.
            # Linear Dodge members instead use the late-clamp island: the
            # member premultiplied stream is first attenuated to its opacity
            # in float32, the opaque add saturates only once at the clamp,
            # the fixed base coverage M (never M*A) is reattached, and the
            # completed result replaces the local stream with fg alpha 1, so
            # base alpha is applied exactly once and never double-multiplied
            # into the RGB contribution.
            island_row = self._clipping_stack_rows[member.id]
            base_straight_name = self.name("BlendBaseStraight" + scope, member.id)
            base_straight_x, base_straight_y = self.position(island_row + 2.0, depth)
            self._current_tools.append(
                _alpha_divide(
                    base_straight_name,
                    current,
                    "PSD clipping blend base straight RGB (base=%s): %s"
                    % (base.id, member.name)
                    + " [P4-HOST-PIXEL: AlphaDivide current local stream]",
                    base_straight_x,
                    base_straight_y,
                )
            )
            base_opaque_name = self.name("BlendBaseOpaque" + scope, member.id)
            base_opaque_x, base_opaque_y = self.position(island_row + 1.5, depth)
            self._current_tools.append(
                _channel_boolean_force_opaque(
                    base_opaque_name,
                    _Source(base_straight_name),
                    "PSD clipping blend base opaque RGB (base=%s): %s"
                    % (base.id, member.name)
                    + " [P4-HOST-PIXEL: force alpha=1]",
                    base_opaque_x,
                    base_opaque_y,
                )
            )

            member_straight_name = self.name("BlendMemberStraight" + scope, member.id)
            member_straight_x, member_straight_y = self.position(island_row - 3.0, depth)
            self._current_tools.append(
                _alpha_divide(
                    member_straight_name,
                    member_result.output,
                    "PSD clipping blend member straight RGB (base=%s): %s"
                    % (base.id, member.name)
                    + " [P4-HOST-PIXEL: AlphaDivide member stream]",
                    member_straight_x,
                    member_straight_y,
                )
            )
            member_opaque_name = self.name("BlendMemberOpaque" + scope, member.id)
            member_opaque_x, member_opaque_y = self.position(island_row - 2.5, depth)
            is_linear_dodge = member.blend == "Linear Dodge"
            if is_linear_dodge:
                attenuate_name = self.name("BlendMemberAttenuate" + scope, member.id)
                attenuate_x, attenuate_y = self.position(island_row - 2.75, depth)
                self._current_tools.append(
                    _brightness_contrast_gain(
                        attenuate_name,
                        member_result.output,
                        member.opacity,
                        "PSD clipping member premult to opacity (base=%s): %s"
                        % (base.id, member.name)
                        + " [late-clamp Linear Dodge: float32 Gain=opacity, ProcessAlpha=0]",
                        attenuate_x,
                        attenuate_y,
                    )
                )
            self._current_tools.append(
                _channel_boolean_force_opaque(
                    member_opaque_name,
                    _Source(
                        attenuate_name if is_linear_dodge else member_straight_name
                    ),
                    "PSD clipping blend member opaque RGB (base=%s): %s"
                    % (base.id, member.name)
                    + (
                        " [P4-HOST-PIXEL: force alpha=1; late-clamp attenuated input]"
                        if is_linear_dodge
                        else " [P4-HOST-PIXEL: force alpha=1]"
                    ),
                    member_opaque_x,
                    member_opaque_y,
                )
            )

            member_mode_id = self.mode_id(member)
            function_name = self.name("BlendFunction" + scope, member.id)
            function_x, function_y = self.position(island_row - 2.0, depth)
            self.merge_count += 1
            self._current_tools.append(
                _merge(
                    function_name,
                    _Source(base_opaque_name),
                    _Source(member_opaque_name),
                    member_mode_id,
                    1.0,
                    "PSD clipping blend function (base=%s): %s"
                    % (base.id, member.name)
                    + " [P4-HOST-PIXEL: straight opaque; Blend=1]",
                    function_x,
                    function_y,
                )
            )

            clamp_name = self.name("BlendClamp" + scope, member.id)
            clamp_x, clamp_y = self.position(island_row - 1.5, depth)
            self._current_tools.append(
                _brightness_contrast_clamp(
                    clamp_name,
                    _Source(function_name),
                    "PSD clipping blend clamp (base=%s): %s"
                    % (base.id, member.name)
                    + " [P4-HOST-PIXEL: RGB [0,1] before opacity]",
                    clamp_x,
                    clamp_y,
                )
            )

            coverage_name = self.name("BlendCoverage" + scope, member.id)
            coverage_x, coverage_y = self.position(island_row - 1.0, depth)
            self._current_tools.append(
                _channel_boolean_attach_alpha(
                    coverage_name,
                    _Source(clamp_name),
                    fixed_matte if is_linear_dodge else clipped_source,
                    "PSD clipping blend coverage (base=%s): %s"
                    % (base.id, member.name)
                    + (
                        " [late-clamp Linear Dodge: attach fixed base coverage M]"
                        if is_linear_dodge
                        else " [P4-HOST-PIXEL: attach ClipIn M*A alpha]"
                    ),
                    coverage_x,
                    coverage_y,
                )
            )

            premult_name = self.name("BlendPremult" + scope, member.id)
            premult_x, premult_y = self.position(island_row - 0.5, depth)
            self._current_tools.append(
                _alpha_multiply(
                    premult_name,
                    _Source(coverage_name),
                    "PSD clipping blend premultiply (base=%s): %s"
                    % (base.id, member.name)
                    + " [P4-HOST-PIXEL: M*A*B(C,S)]",
                    premult_x,
                    premult_y,
                )
            )

            restore_name = self.name("BlendRestoreAlpha" + scope, member.id)
            restore_x, restore_y = self.position(island_row + 0.0, depth)
            if is_linear_dodge:
                # The late-clamp result is already complete (coverage lives in
                # the attenuated add), so restore opaque alpha instead of the
                # member alpha: the ClipStack replace below then yields T*M
                # over M, i.e. exactly T, with no second coverage multiply.
                self._current_tools.append(
                    _channel_boolean_force_opaque(
                        restore_name,
                        _Source(premult_name),
                        "PSD clipping blend restore alpha (base=%s): %s"
                        % (base.id, member.name)
                        + " [late-clamp Linear Dodge: force opaque T*M]",
                        restore_x,
                        restore_y,
                    )
                )
            else:
                self._current_tools.append(
                    _channel_boolean_attach_alpha(
                        restore_name,
                        _Source(premult_name),
                        member_result.output,
                        "PSD clipping blend restore alpha (base=%s): %s"
                        % (base.id, member.name)
                        + " [P4-HOST-PIXEL: restore original member A]",
                        restore_x,
                        restore_y,
                    )
                )

            merge_name = self.name("ClipStack" + scope, member.id)
            self.merge_count += 1
            x, y = self.position(self._clipping_stack_rows[member.id], depth)
            self._current_tools.append(
                _merge(
                    merge_name,
                    current,
                    _Source(restore_name),
                    "Normal",
                    1.0 if is_linear_dodge else member.opacity,
                    "PSD clipping subtree member (base=%s): %s"
                    % (base.id, member.name)
                    + " [P4-01 local Merge; straight blend island; ProcessAlpha=0 preserves base alpha; "
                    + (
                        "P4-02 shared base matte member %d/%d; "
                        "late-clamp Linear Dodge opacity in attenuate Gain; FunctionMerge carries member mode]"
                        if is_linear_dodge
                        else "P4-02 shared base matte member %d/%d; "
                        "P4-03 member opacity local; FunctionMerge carries member mode]"
                    )
                    % (member_index, member_total),
                    x,
                    y,
                    # Photoshop clipping keeps the base alpha as the chain
                    # boundary while member RGB/blend/opacity are evaluated.
                    process_alpha=False,
                )
            )
            current = _Source(merge_name)
        return _ItemResult(current, fixed_matte)

    def sequence(
        self,
        items: Sequence[SemanticLayer],
        backdrop: _Source,
        depth: int,
        scope: str,
    ) -> _SequenceResult:
        current = backdrop
        # This metadata is consumed only when a pass-through group declares
        # its InstanceInput proxy. Render consumers still use each sequence's
        # actual internal terminal source.
        backdrop_consumer: List[Optional[_Source]] = [None]
        i = 0
        while i < len(items):
            layer = items[i]
            if not layer.effective_visible:
                i += 1
                continue
            # A clipped member is consumed by its base's chain. An orphan is
            # still emitted normally, with the parser warning preserved.
            if layer.clipping_base_id and not layer.clipping_members:
                result = self.item(layer, current, depth, scope)
                if result.consumed_backdrop:
                    if backdrop_consumer[0] is None:
                        backdrop_consumer[0] = result.backdrop_consumer
                    current = result.output
                else:
                    current = self.merge_item(
                        current,
                        result,
                        layer,
                        depth,
                        scope,
                        backdrop_consumer=backdrop_consumer,
                    )
                i += 1
                continue

            base_result = self.item(layer, current, depth, scope)
            if base_result.consumed_backdrop:
                if backdrop_consumer[0] is None:
                    backdrop_consumer[0] = base_result.backdrop_consumer
                current = base_result.output
                i += 1
                continue
            if layer.clipping_members:
                chain = self.clipping_chains.get(layer.id)
                ordered_member_ids = (
                    list(chain.member_ids) if chain is not None else list(layer.clipping_members)
                )
                members, j = self._collect_clipping_members(
                    items,
                    i,
                    ordered_member_ids,
                    strict=chain is not None and chain.blend_clipped_as_group,
                )
                if chain is not None and chain.blend_clipped_as_group:
                    subtree = self.clipping_subtree(
                        base_result, layer, members, depth, scope
                    )
                    self._clipping_outer_rows[layer.id] = 0
                    current = self.merge_item(
                        current,
                        subtree,
                        layer,
                        depth,
                        scope,
                        comment_prefix="PSD clipping chain merge",
                        opacity=layer.opacity,
                        mode=layer.blend,
                        backdrop_consumer=backdrop_consumer,
                    )
                else:
                    # Explicit clbl=false under strict policy is rejected
                    # (PARITY-005 S4). Preserve the named FIRST_USABLE
                    # fallback only under explicit compatibility policy,
                    # never as silent group-scope semantics.
                    if self.policy == "strict":
                        self._require_clbl_policy()
                    current = self.merge_item(
                        current,
                        base_result,
                        layer,
                        depth,
                        scope,
                        backdrop_consumer=backdrop_consumer,
                    )
                    for member in members:
                        if member.effective_visible:
                            member_result = self.item(member, current, depth, scope)
                            clipped_source = self.clipping_merge(
                                base_result.matte, member_result, member, depth, scope
                            )
                            current = self.merge_item(
                                current,
                                _ItemResult(clipped_source, clipped_source),
                                member,
                                depth,
                                scope,
                                comment_prefix="PSD clipped layer fallback (clbl=false)",
                                opacity=member.opacity,
                                mode=member.blend,
                                backdrop_consumer=backdrop_consumer,
                            )
                i = j
            else:
                current = self.merge_item(
                    current,
                    base_result,
                    layer,
                    depth,
                    scope,
                    backdrop_consumer=backdrop_consumer,
                )
                i += 1
        return _SequenceResult(current, self._current_tools, backdrop_consumer[0])

    def compile(self) -> Dict[str, str]:
        self._require_clbl_policy()
        root_bg = self.name("Background", self.doc.source_sha256)
        self._root_background_name = root_bg
        root_tools: List[str] = [
            _background(
                root_bg,
                self.doc.width,
                self.doc.height,
                "PSD2Fusion transparent canvas",
                -220.0,
                0.0,
            )
        ]
        self._current_tools = root_tools
        result = self.sequence(self.doc.children, _Source(root_bg), 0, "R")
        media_name = "MediaOut1"
        root_tools.append(
            _simple_tool(
                media_name,
                "MediaOut",
                [_input_connection("Input", result.output)],
                "PSD2Fusion output",
                self._x + 220.0,
                0.0,
            )
        )
        # Tool IDs in exported comps are monotonically increasing; an exact ID
        # is not semantic, but keeping it deterministic helps diffs and probes.
        composition = [
            "Composition {",
            "\tCurrentTime = 0,",
            "\tRenderRange = { 0, 1000 },",
            "\tGlobalRange = { 0, 1000 },",
            "\tCurrentID = %d," % (self.node_count + 1),
            "\tPlaybackUpdateMode = 0,",
            "\tVersion = \"1.2\",",
            "\tSavedOutputs = 0,",
            "\tHeldTools = 0,",
            "\tDisabledTools = 0,",
            "\tLockedTools = 0,",
            "\tAudioOffset = 0,",
            "\tResX = %d," % int(self.doc.width),
            "\tResY = %d," % int(self.doc.height),
            "\tPlaybackFrames = 0,",
            "\tPlaybackTime = 0,",
            "\tTransportState = 0,",
            "\tCurrentTool = %s," % _quote(media_name),
            "\tTools = {",
            _indent("\n".join(root_tools), "\t\t"),
            "\t},",
            "\tViews = {",
            "\t\t{",
            "\t\t\tFrameTypeID = \"FlowView\",",
            "\t\t\tMode = 0,",
            "\t\t\tViewOffsetX = 0,",
            "\t\t\tViewOffsetY = 0,",
            "\t\t\tViewScale = 1",
            "\t\t}",
            "\t}",
            "}",
        ]
        with open(self.output_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("\n".join(composition) + "\n")
        return {
            "final_tool": result.output.name,
            "tool_count": str(self.node_count + 1),
            "merge_count": str(self.merge_count),
            "group_count": str(self.group_count),
            "clipping_count": str(self.clip_count),
            "blend_modes": ",".join(sorted(self.blend_modes)),
            "clipping_recipe": "operator_in_fixed_matte_local_stack",
        }


def compile_comp(
    doc: SemanticDocument, output_path: str, policy: str = "strict"
) -> Dict[str, str]:
    """Compile a semantic document to a deterministic Fusion composition."""

    return _Compiler(doc, output_path, policy).compile()
