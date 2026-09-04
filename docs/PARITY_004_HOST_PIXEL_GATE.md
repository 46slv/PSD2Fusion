# PARITY-004 host and pixel gate

Status: active execution contract for the remaining host/pixel portion of `PARITY-004`.

## Active production acceptance override

The operator policy in `.control/PARITY-004_ACCEPTANCE.md` is authoritative for PARITY-004 production acceptance as of 2026-09-04. It changes acceptance policy without deleting or weakening strict diagnostic evidence.

In particular:

- keep `strict RGBA threshold=0` comparisons as diagnostic/regression evidence;
- preserve the Fusion production graph's 32-bit float pipeline;
- do not add quantization, rounding, depth-reduction, or equivalent nodes solely to reproduce Photoshop-style 8-bit intermediate rounding;
- a residual around one 8-bit LSB is not by itself a production blocker when alpha, structure, group/clipping scope, blend/opacity semantics and visual behavior are otherwise correct;
- material alpha/semantic defects, large deltas, coherent localized outliers and visible real-image differences remain blockers;
- do not relax comparator thresholds to hide a material failure: record the strict metrics, then classify the residual separately for production acceptance.

Complete any already-running micro/strict diagnostic before applying this acceptance classification to closeout. Do not interrupt an in-progress diagnostic merely because its strict result will no longer be an automatic blocker.

## Active pixel truth contract

Operator instruction on 2026-09-04 supersedes any earlier evidence or decision that made a Photoshop actual micro oracle a prerequisite. Do not use Photoshop in this Goal, and do not treat its absence as a blocker or stop condition. Retain the historical evidence rather than deleting it.

Use these three evidence classes:

1. actual Fusion micro artifacts;
2. actual differences between Fusion graph internal boundaries;
3. the real P4-09 comparison against the read-only golden reference.

A formula-only oracle may assist diagnosis but is not absolute pixel truth. The bounded micro diagnostic localizes the first divergent Fusion boundary between otherwise identical ungrouped and isolated-GroupOperator paths. If the internal stages are stable and consistent, proceed to P4-09 without waiting for an external micro oracle.

This document starts from the already-published structural candidate. Do not roll back P4-03 through P4-07 merely because host/pixel proof is still pending. Those items are structural evidence for the candidate graph; they are not pixel proof.

## Current structural baseline

The current grouped/default clipping candidate is:

```text
base Loader
  -> fixed base matte reused by every member
  -> one ClipIn Merge (`Operator=In`) per member
  -> local ClipStack Merge per member (`ProcessAlpha=0`)
  -> one outer chain Merge with base blend/overall opacity
```

The real `a.psd` structural audit covers 23 clipping chains, 59 clipped members, 34 groups, and the current 422-tool generated graph (the 59 additional tools are the explicit RGB/alpha boundary nodes). Preserve this candidate until host/pixel evidence identifies a concrete defect.

## Mandatory execution order

Run the remaining work in this order:

```text
complete any already-running micro/strict diagnostic
-> P4-08 ordinary Fusion load/readback (reuse existing verified evidence when still current)
-> P4-HOST-PIXEL micro fixtures / localized diagnostics
-> regenerate latest candidate from real a.psd
-> P4-09 fresh real PSD Fusion render/reference comparison
-> classify strict residuals as quantization-scale versus material visual/semantic differences
-> smallest evidence-driven repair only for material differences, if needed
-> rerun focused micro fixture then real comparison
```

Do not enter a repair loop whose only purpose is closing +/-1 LSB byte differences. Do not start `PARITY-005`, `PARITY-006`, or a broad compiler/planner redesign before the required PARITY-004 real render/reference classification is complete unless the current graph cannot load/render at all and the blocker is already localized to such a boundary.

## P4-08 — ordinary Fusion load/readback

Use a new Resolve/Fusion launch and a new project when practical. Reusing a known disposable test project is also acceptable. Treat the real PSD/reference as read-only.

Required checks:

- generated `.comp` loads;
- Loader paths resolve;
- MediaOut receives the final stream;
- expected tool count and representative GroupOperator/clipping connections survive load;
- `ApplyMode`, `Blend`, `Operator=In`, `ProcessAlpha=0`, and Loader `PostMultiply` survive readback/reload;
- no invalid/missing tools are introduced;
- save/reload does not silently rewrite the semantic controls;
- record exact Resolve/Fusion version and candidate commit.

Useful product telemetry, when cheaply available:

- load time;
- first Viewer display time;
- basic Flow interaction responsiveness;
- save/reload success;
- existing-comp paste/undo preservation.

P4-08 earns `host_loaded` evidence only. It never earns `pixel_verified`.

## P4-HOST-PIXEL — minimum Fusion pixel gate

Before rendering the full real PSD, render small deterministic RGBA fixtures in actual Fusion. Reuse the existing comparator and fixture semantics; do not create a second comparison standard.

Minimum cases:

### A. Loader alpha boundary

- straight/premult expectation;
- Loader `PostMultiply` behavior;
- transparent and partially transparent pixels.

### B. `Operator=In` coverage

- base alpha: `0, .25, .5, .75, 1`;
- member alpha: `0, .5, 1`;
- verify clipped output cannot expand beyond base coverage.

### C. `ProcessAlpha=0`

- after each local member Merge, span alpha remains the fixed base coverage.

### D. member controls

- Normal;
- Multiply;
- Linear Dodge;
- Overlay;
- member opacity `.25, .5, .75, 1`.

### E. outer boundary

- base opacity `0, .5, 1`;
- at least one non-Normal base mode;
- transparent, black, white, and colored outer backdrops.

For every rendered fixture record candidate commit, host/version, project/color settings, render format, artifact path/hash, RGBA/alpha metrics, and whether the strict comparator passed. Graph text/readback is not a substitute for rendered pixels.

A threshold-zero failure must be retained in evidence. For production acceptance, additionally classify whether the failure is only quantization-scale under `.control/PARITY-004_ACCEPTANCE.md` or indicates a material semantic/visual defect.

## P4-09 — real PSD baseline and acceptance comparison

After the micro pixel gate is usable, regenerate `D:\Downloads\a.psd` from the latest candidate family, render that fresh graph in actual Fusion, and compare it directly with the qualified `D:\Downloads\20260812.png` reference.

Partition the difference before changing compositor math. Report strict metrics even when the final production acceptance treats a small quantization residual as non-blocking.

Classify differences into the smallest useful category, for example:

- non-material host/export/quantization residual;
- global/profile/working-space difference;
- alpha/premultiply edge difference;
- one blend mode family;
- one clipping chain or coverage boundary;
- isolated group only;
- Pass Through group only;
- placement/crop/canvas difference;
- asset materialization difference;
- unsupported PSD semantics.

Prioritize material real-image differences: large pixel deltas, coherent localized regions, visible anomalies, alpha errors and semantic-scope failures. Linear Dodge and any previously localized high-difference regions receive priority over byte-exact closure of 1-LSB fixture residuals.

Do not fit the reference by changing thresholds, grading, resizing, blurring, flattening, or applying a whole-image correction.

## Evidence-driven repair rule

When a material failure is localized:

1. reduce it to the smallest deterministic fixture or bounded real-image diagnostic;
2. repair the smallest responsible semantic/render boundary;
3. preserve the float32 production path unless the repair itself requires a separately verified representation boundary;
4. rerun the focused micro fixture;
5. rerun the real P4-09 comparison;
6. retain before/after strict metrics and acceptance classification.

Do not redesign unrelated architecture around a failure that has not been localized. Do not add quantization/rounding/depth-reduction nodes solely to remove a +/-1 LSB residual.

## Deferred architecture work

Two known design debts remain visible but are not automatic blockers for the first host/pixel baseline:

1. `Evaluation IR` / capability decisions are currently produced after graph compilation and do not yet drive backend selection;
2. asset materialization still needs an explicitly verified ICC/straight-premult/transparent-RGB contract.

Use host/pixel evidence to decide whether either debt is causal. Before adding multiple backends, custom operations, verified bake paths, or broader PSD feature support, connect capability planning to lowering so strict mode cannot silently emit an unverified backend.

## Stop conditions

Stop and report instead of advancing only when:

- actual Fusion artifacts cannot be acquired through multiple reasonable routes;
- actual Fusion internal-boundary evidence plus P4-09 still leaves multiple material implementation hypotheses unresolved by the Orchestrator;
- credentials, additional authority, or a destructive human action is required;
- the deterministic execution path fails closed;
- PARITY-004 reaches verified closure under `.control/PARITY-004_ACCEPTANCE.md`.

Photoshop absence is not a stop condition. A strict threshold-zero mismatch that is only a qualified quantization-scale residual is not by itself a stop condition. Ordinary test, fixture, or localized material implementation failures require a changed diagnostic or localized repair rather than stopping.

`PARITY-004` remains `in_progress` until the required host/pixel evidence is complete, residuals are classified under the active acceptance policy, and fresh verification permits the canonical state transition.
