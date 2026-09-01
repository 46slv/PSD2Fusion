# PSD2Fusion architecture (FIRST_USABLE)

Status: **FROZEN for the FIRST_USABLE slice** (2026-09-01)

This document is the design authority for the first implementation. It is a
deliberately small architecture, not a framework. A runtime observation may
change an implementation detail, but it must not reopen the boundaries below
unless the current contract cannot be met or the host rejects the artifact.

## Product contract

The first product contract is a readable, editable-enough Fusion composition
for ordinary raster layers, PSD groups, and the common clipping-mask case. It
optimizes for a user being able to select a PSD, generate an artifact, open it
in Resolve/Fusion, and inspect/adjust the resulting graph. Photoshop pixel
parity, every layer kind, every blend mode, and every Resolve release are not
part of this contract.

The supported first slice is:

- 8-bit RGB/RGBA PSD documents (other depth/mode is converted with a manifest
  warning when `psd-tools` can provide pixels);
- visible pixel layers, their document-space placement, overall opacity, and
  the common Fusion/PSD blend names;
- nested PSD groups, with a distinct pass-through path and isolated path;
- contiguous clipping chains represented as explicit alpha-matte graph logic;
- full-canvas PNG derivatives and a text `.comp` artifact that Resolve/Fusion
  can import.

Adjustment layers, smart objects, effects, fill opacity, vector masks,
advanced blending, and editable Photoshop text/shape are detected. If a layer
can be rasterized by `psd-tools`, it is emitted as `selectively-baked` with a
warning; otherwise conversion fails with an actionable diagnostic. No
unsupported feature is silently changed to Normal/100%/visible.

## Boundaries and source of truth

```text
PSD file
  -> parser adapter (psd-tools)
  -> PSD semantic IR (the only semantic source of truth)
  -> asset materializer (full-canvas RGBA PNG + provenance)
  -> pure Fusion graph compiler/serializer (.comp)
  -> optional Resolve host adapter (ImportFusionComp smoke only)
```

The parser, asset materializer, compiler, serializer, and host adapter are
separate boundaries. The compiler consumes IR and asset paths; it never sees a
`psd-tools` object. The host adapter is optional and must not be imported by
offline conversion code.

### Minimal modules

| Module | Responsibility | Must not own |
|---|---|---|
| `psd2fusion/semantic.py` | dataclasses for document, layer/group, clipping, capability and provenance | PSD parsing or Fusion field names |
| `psd2fusion/parse_psd.py` | `psd-tools` API/raw-tag adapter; tree/order/visibility/clipping extraction | graph serialization, host calls |
| `psd2fusion/assets.py` | deterministic full-canvas RGBA derivatives, source hash, mask/raster fallback notes | PSD tree policy, Fusion syntax |
| `psd2fusion/fusion_comp.py` | IR -> graph nodes, group/clipping evaluation, `.comp` Lua-like serialization | `psd-tools`, PIL, Resolve |
| `psd2fusion/manifest.py` | JSON provenance, capability decisions, warnings and generated files | pixel compositing |
| `psd2fusion/cli.py` | `python -m psd2fusion` entrypoint and user-facing errors | semantic rules and host automation |
| `psd2fusion/host_smoke.py` | optional in-host `ImportFusionComp` probe/handoff | conversion and asset generation |

These are direct modules, not plugin interfaces. A new abstraction is added
only when one of these responsibilities needs it.

## PSD semantic IR

The IR retains semantics that affect the first graph even when the compiler
does not yet support the feature. IDs are deterministic for a source hash and
the layer's structural path, never based on a display name alone.

### Document

- `source_path`, `source_sha256`, parser name/version;
- canvas `width`, `height`, origin `(0, 0)`, color mode/depth/profile metadata;
- root children in normalized **bottom-to-top** order;
- warnings and a capability summary.

### Layer and group

- stable `id`, display `name`, `kind`, parent ID, sibling index, and raw PSD
  order;
- `bbox = (left, top, right, bottom)` in document pixels, even when it is
  outside the canvas;
- own visibility and effective visibility;
- overall opacity in `[0, 1]`, optional fill opacity, raw PSD blend key and
  canonical blend name;
- asset reference (when materialized), mask descriptors, and unsupported
  semantic inventory;
- for a group: `pass_through`/isolation, group opacity/blend, and children;
- for a clipping base: ordered clipped-member IDs and raw
  `Blend Clipped Layers As Group` provenance when present.

The IR is intentionally document-space. It does not contain normalized Fusion
coordinates, node names, `SourceOp`, or serialization details.

## `psd-tools` responsibility boundary

`psd-tools` is used as the pinned parser/raster source, not as a Photoshop
render oracle. The adapter may use its public tree/layer/mask APIs and the raw
tags needed to expose clipping/group metadata. It must preserve parser
version/provenance in the manifest.

For FIRST_USABLE, a leaf is materialized with `layer.topil()` and placed at its
PSD bbox on a transparent, document-sized RGBA canvas. This is the deliberate
**full-canvas derivative** choice: it makes negative/irregular bounds and
Fusion placement deterministic and keeps the first serializer small. The bbox
is still retained in the IR/manifest for later migration to cropped assets.

`psd-tools` compositor output is never used as an unlabelled Photoshop
reference. A rasterized unsupported layer is explicitly marked
`selectively-baked`; a source that cannot yield pixels is `rejected` rather
than silently dropped.

## Semantic-to-Fusion conversion

The compiler accepts only the IR and emits a graph plus a list of decisions.
The graph is built over a transparent `Background` with the PSD canvas
resolution. Every visible leaf has a `Loader` for its full-canvas PNG and is
composited in normalized bottom-to-top order. Since assets are full-canvas,
the first slice does not need a Transform node for placement; `Center =
{0.5, 0.5}` is the invariant placement.

The serializer is a small, deterministic Lua-like writer adapted from the
proven `.comp` shapes observed in `bixcl/PSDconverter` and the Loader/Merge
templates in `NUROKU/DaVinciResolve_PSDFusionGenerator`. No source file from a
license-unclear sample is copied. Paths are escaped in one function and every
tool name is unique and stable.

## Group compositing versus visual grouping

Fusion `GroupOperator` is used as the visual and reusable boundary; it is not
treated as Photoshop semantics by itself.

### Isolated group

For a PSD group whose blend mode is not Pass Through, the compiler creates a
transparent internal canvas, composes children there, and exposes the result
through the `GroupOperator`. The parent stream then receives one explicit
Merge applying the group's canonical blend and opacity. Thus group opacity is
applied once to the subtree result, not once per child.

### Pass-through group

For a Pass Through group at full opacity, the `GroupOperator` exposes a
`Background` instance input. Its internal child Merge chain starts from that
input, so children evaluate against the parent's existing backdrop. The group
operator output is connected directly into the parent stream. The wrapper is
there for human-readable graph organization; the exposed backdrop input is the
semantic behavior.

Pass Through with non-default opacity or other unsupported group flags is
compiled using the nearest explicit isolated fallback and recorded as
`unknown`/`selectively-baked` with a warning. This is intentionally visible in
the manifest and node comments.

Nested groups recurse through the same rule. A pass-through group inside an
isolated parent sees the parent's transparent internal backdrop, which keeps
the two boundaries distinct.

## Clipping representation and graph algorithm

Clipping is an IR relationship, never a per-layer boolean mask shortcut. The
parser normalizes each same-parent contiguous chain to one base ID plus ordered
members. The chain also retains `Blend Clipped Layers As Group` and whether it
came from an explicit PSD `clbl` value or Photoshop's default-true behavior.
For the supported true/default case, the compiler processes a sibling sequence
bottom-to-top:

1. materialize the base without consuming the current parent stream;
2. retain that base output as both the initial subtree and fixed alpha matte;
3. for each clipped member, create a `Merge` with `Operator = FuID { "In" }`,
   `Background = base matte`, and the member image as `Foreground`;
4. merge that clipped result into the preceding subtree with the member's
   canonical blend and opacity and `ProcessAlpha = 0`, preserving base alpha;
5. after all ordered members are complete, merge the subtree into the parent
   stream exactly once using the base layer's blend and opacity.

This keeps member pixels inside the base alpha and prevents non-Normal member
blends from evaluating against the outer backdrop. Explicit `clbl=false`,
advanced masks, adjustment layers, and Fill Opacity behavior are not claimed
as parity; they remain explicit warnings/fallback decisions.

## Asset strategy and fallback policy

The fixed first-slice strategy is **semantic reconstruction + full-canvas PNG
derivatives**. PSD direct Loader references are not used because layer-channel
indexing and importer behavior are version-sensitive and no current host probe
established a stable contract. Selective subtree baking is reserved for
unsupported layer kinds only when a raster is available; a Photoshop-driven
parity renderer is not a FIRST_USABLE dependency.

Each semantic item receives one of:

`native`, `reconstructed`, `selectively-baked`, `flattened`, `rejected`, or
`unknown`.

The output manifest contains the decision, reason, source ID, derived asset,
and warning. Conversion errors identify the layer/group and the next safe
choice. Hidden items remain in the manifest even when no graph tool is emitted.

## Artifact and host boundary

An output directory contains:

```text
<name>_fusion/
  PSD2Fusion.comp       # deterministic Fusion composition
  manifest.json         # source hash, IR summary, decisions, warnings, assets
  assets/
    layer-<stable-id>.png
```

The `.comp` is the primary artifact because it is diffable/offline and the
current Resolve scripting README documents `TimelineItem.ImportFusionComp`.
The optional host smoke adapter is the only place allowed to import Resolve's
scripting module. It must report the exact host version/edition when known;
offline generation never claims that the host loaded the file.

## Explicit non-goals for this freeze

- native PSD Loader channel references as the primary path;
- full-canvas compositing as a claim of Photoshop parity;
- adjustment/effect/Blend-If/knockout/Smart Object editability;
- all blend-mode math, color profiles, 16/32-bit/HDR parity;
- `.setting`/Generator packaging, release installers, or broad regression
  suites;
- redesigning these boundaries during routine implementation.

## Evidence and provenance

The research baseline is committed in `docs/research/`. Code-level patterns
were checked against:

- `NUROKU/DaVinciResolve_PSDFusionGenerator`, commit
  `0b2181699ee4406fcf1e4971f289b2a0ea9066e1` (MIT): bbox/center and
  Loader/Merge serialization;
- `bixcl/PSDconverter`, commit
  `5645c270d725357513604037d23185cefc654b58` (README claims MIT but no
  LICENSE file): full-canvas PNG and `.comp` template shape only; no code
  copied;
- `34j/DaVinciResolve.PSDGeneratorBuilder`, commit
  `85fd7386f8dc9ae4c6a3c4ff38636f513632385c` (MIT): serializer limitations
  were treated as a warning, not a product dependency;
- `psd-tools` source commit `8d44ed0c4c2d43d935b35dff642bbc4e4f767f6d`
  (MIT): semantic API and clipping/raw-tag boundary.

The unresolved host facts remain version-scoped. A successful FIRST_USABLE
smoke is required before this Goal is closed; a host-unavailable run must leave
an exact handoff with the artifact path and the host procedure.
