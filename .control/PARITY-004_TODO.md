# PARITY-004 Fusion-first implementation TODO

Purpose: finish grouped/default PSD clipping as a readable Fusion graph. The main work is node lowering: where layers enter, where masks are taken, where Merge happens, and where group/opacity boundaries live. Host render/reference work is validation after the graph recipe is stable.

## Working rule

Work these items in order. One item at a time. Prefer ordinary Fusion Loader / Merge / mask connections and readable Flow structure. Do not add new abstraction layers unless the existing Fusion nodes cannot express the required boundary.

## P4-01 — Simplest 1:1 clipping recipe

Status: COMPLETE (selected candidate A; P4-02 and later items remain not started)

Goal: represent one PSD base + one clipped member with the smallest readable Fusion graph.

Compare two concrete lowerings:

A. current lowering

```text
Base -----------------------> local base/current
  \-> fixed matte -> ClipIn(In) <- Clipped
                         |
                         v
                    ClipStack Merge
```

B. direct mask lowering candidate

```text
Base --------------------------> Merge Background
  \-> base alpha/mask ---------> Merge Effect Mask
Clipped -----------------------> Merge Foreground
```

Determine whether B reproduces the same required boundary as A for Normal, partial base alpha and transparent pixels. If yes, prefer B because it is closer to how a Fusion user would manually build clipping. If not, retain A and document the exact reason.

Done when:
- one canonical 1:1 recipe is selected;
- generated `.comp` shows the relationship clearly;
- no outer backdrop participates in the local clipping operation.

## P4-02 — Multiple clipped members share one base matte

Status: COMPLETE (three-member fixture verifies the selected recipe; P4-03
and later items remain not started)

Goal: base + N clipped members.

Required shape:

```text
                 Clip 1
                   |
Base alpha --------+---- mask
                   v
Base ----------> local Merge 1
                   |
                 Clip 2
                   |
Base alpha --------+---- mask
                   v
              local Merge 2
                   |
                  ...
```

All members reuse the same base coverage. Member order follows PSD bottom-to-top order. Do not derive the mask from the progressively composited local result.

Done when one base with 2+ members lowers deterministically and remains readable.

Implementation evidence:

- `scripts/parity/p4_02.py` emits a deterministic three-member graph and checks
  shared base matte, per-member `Operator=In`, PSD bottom-to-top order, local
  `ProcessAlpha=0` stacks, and one outer Merge.
- `psd2fusion/fusion_comp.py` captures the base matte once for the local span,
  reuses it for every member, and rejects an incomplete true chain instead of
  silently dropping a non-contiguous member.
- `tests/test_parity004_p402_graph.py` covers the graph shape and malformed-span
  guard.

## P4-03 — Member blend and opacity placement

Goal: establish which local Merge owns each clipped member's blend mode and overall opacity.

Test at least:
- Normal
- Multiply
- Linear Dodge
- Overlay
- 25/50/75% member opacity

The member blend/opacity belongs to the local member Merge, not to the final outer Merge.

Done when generated node controls match the PSD member semantics for the existing supported subset.

## P4-04 — Base blend and opacity boundary

Goal: keep base-local clipping construction separate from how the completed chain enters the lower PSD backdrop.

Target:

```text
outer backdrop D ----------> Outer Merge Background
local clipping result S ---> Outer Merge Foreground
base blend / opacity ------> Outer Merge controls
```

Base blend/overall opacity is applied once at this outer boundary.

Done when changing base opacity/blend changes only the chain-to-parent boundary, not each clipped member individually.

## P4-05 — Groups and nesting

Goal: make the same clipping recipe work inside existing group lowering.

Cover:
- clipping inside isolated group;
- clipping inside Pass Through group;
- nested isolated groups;
- clipping base or member adjacent to group boundaries.

Do not redesign GroupOperator. Fix only where clipping's local/outer Merge boundaries attach to the existing group stream.

Done when the same clipping recipe composes correctly at each existing group boundary.

## P4-06 — Fusion Flow layout

Goal: make generated graphs understandable without reading the manifest.

Layout conventions:
- PSD flow continues primarily left-to-right;
- base Loader is visually below/near its clipping chain;
- clipped member Loaders stack visibly around the base;
- mask connection is visually obvious;
- local clipping Merges are clustered;
- one outer Merge exits the clipping cluster;
- GroupOperator boundaries remain visually distinct.

Prefer stable deterministic positions over automatic layout heuristics.

Done when a user can identify base, clipped members, local chain and outer Merge by looking at Flow.

## P4-07 — Apply the recipe to the real PSD

Input: `D:\Downloads\a.psd` read-only.

Apply the selected graph recipe to all existing default/true clipping chains.

Expected current structure:
- 23 clipping chains;
- 59 clipped members.

Inspect representative chains of different sizes and nesting depths, not only aggregate counts.

Done when all 23 chains use the same explicit recipe and no special-case graph is introduced without a PSD-semantic reason.

## P4-08 — Ordinary Fusion load/readback sanity

Goal: confirm the generated `.comp` is usable in Fusion/Resolve.

Only check what is needed for the product artifact:
- `.comp` loads;
- expected tools/connections exist;
- Loader paths resolve;
- MediaOut receives the final stream;
- no missing/invalid tools introduced by the new lowering.

Do not turn this item into render-harness development.

## P4-09 — Pixel/reference validation after graph stabilization

After P4-01 through P4-08 are stable, render the resulting Fusion graph and compare with the existing golden reference. Use pixel differences to identify a specific graph-boundary defect, then return to the smallest relevant P4 item.

Pixel validation is feedback for the lowering recipe, not the design driver.

## Out of scope for this queue

- explicit `clbl=false` semantics: PARITY-005;
- new PSD importer mechanism;
- Photoshop automation;
- new render framework;
- global visual fitting/grade/resize/blur/flatten;
- unrelated PSD feature expansion.

## Immediate next item

P4-02 is complete. The next queued item is P4-03; do not start it in the
current run.
