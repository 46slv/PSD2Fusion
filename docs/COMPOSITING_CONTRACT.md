# PSD2Fusion compositing contract

Status: active design authority for `PSD2FUSION-COMPOSITING-PARITY`. This supersedes FIRST_USABLE assumptions only where this file explicitly differs.

## Pipeline and claim levels

```text
PSD bytes -> Raw extraction -> Semantic IR -> Evaluation IR
          -> Capability planner -> Fusion/custom/bake lowering
          -> Fusion artifact -> Host render -> Reference comparison
```

Raw extraction owns file/header/resource/layer/channel/tag facts. Semantic IR owns Photoshop meaning and provenance. Evaluation IR owns order and backdrop scope and contains no Fusion node IDs. Lowering implements the plan; it does not define Photoshop semantics.

Claims are separate: `parsed`, `planned`, `structural`, `host_loaded`, `pixel_verified`. A lower claim never implies a higher one.

## Capability decisions

Every relevant operation has one explicit state:

```text
verified_fusion_native
verified_custom
verified_bake
detected_unsupported
rejected
unverified
```

Strict mode never maps an unknown blend to Normal, changes opacity, drops a layer, silently flattens, or hides normalization. Fallback order:

1. verified editable Fusion native;
2. verified custom operation;
3. verified self-contained semantic bake;
4. verified backdrop-dependency-closure bake;
5. reject.

A whole-document flatten may be an explicitly labelled preview, not editable parity.

## Blend modes

Preserve the raw four-byte PSD key, including trailing spaces, plus a canonical name. A promoted registry entry must include backend, Fusion ID/custom operation, proof ID, exact host/version, color/depth constraints, alpha contract and measured numerical floor.

Initial verification order:

```text
Normal -> Multiply -> Linear Dodge -> Overlay
```

The existence of a same-named Fusion ApplyMode is capability evidence, not parity evidence.

## Opacity

Never collapse these stages:

```text
source transparency
pixel/vector mask coverage
fill opacity
effects result
overall layer opacity
group opacity
clipping coverage
```

Ordinary overall opacity applies once to the completed layer result. Isolated-group opacity applies once to the completed subtree. Base/member opacity placement inside clipping is fixture-derived, not assumed from current code.

## Groups

- Isolated: render children against transparent local backdrop, then composite the group result once into its parent.
- Pass Through: children consume the incoming parent backdrop.
- Fusion Group/Underlay is organizational unless its internal graph implements this boundary.
- A backdrop-dependent bake includes the smallest verified dependency closure.

## Clipping

A clipping span is `same-parent base + contiguous ordered members + clbl policy`. It is not a per-layer mask shortcut.

Keep separate:

```text
B = base content
M = base coverage
S = local base/member result
D = outer backdrop
```

For absent/default `clbl` and explicit true, the current hypothesis is:

```text
M = evaluated base coverage
S = evaluated base content
for member in bottom-to-top order:
    J = member restricted by M
    S = local_blend(S, J, member mode, member opacity)
    coverage(S) remains M
output = composite(D, S, base mode, base overall opacity)
```

Required invariants:

- every member reuses the same `M`;
- members never expand span alpha;
- member order is stable;
- members do not accidentally see `D`;
- base mode/opacity act only at the verified boundary;
- fractional alpha and transparent RGB do not fringe.

The current fixed-matte `ClipStack` with `ProcessAlpha=0` is a candidate Fusion lowering, not the Photoshop specification.

Treat explicit `clbl=false` as a separate policy. Until Photoshop-backed fixtures establish member backdrop and base mode/opacity behavior, strict mode uses documented bake/reject rather than the grouped graph.

## Color and alpha

Initial strict target: 8-bit RGB with recorded profile. Compare in one named space and evaluate alpha independently.

Record source/profile provenance, every ICC transform, straight/premult state, transparent-RGB policy and the exact pre/post-multiplication boundary. No hidden ICC conversion, alpha discard or double pre/post-multiply. `topil()` is a candidate raster source, not an assumed raw-channel oracle.

## Structural invariants

- raw order and normalized compositing order are distinct and deterministic;
- clipping is same-parent and contiguous; an unclipped sibling terminates it;
- orphan clipping is diagnosed;
- absent/true/false `clbl` are distinct;
- duplicate display names do not define identity;
- hidden and empty layers remain represented;
- overall and fill opacity remain separate;
- own and effective visibility remain separate;
- unsupported semantics receive an explicit decision and provenance.
