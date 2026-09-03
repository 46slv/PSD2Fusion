# PARITY-004 host and pixel gate

Status: active execution contract for the remaining host/pixel portion of `PARITY-004`.

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
P4-08 ordinary Fusion load/readback
-> P4-HOST-PIXEL micro fixtures
-> P4-09 real PSD render/reference comparison
-> smallest evidence-driven repair, if needed
-> rerun micro fixture then real comparison
```

Do not start `PARITY-005`, `PARITY-006`, or a broad compiler/planner redesign before the first P4-09 baseline unless the current graph cannot load/render at all and the blocker is already localized to such a boundary.

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

For every rendered fixture record candidate commit, host/version, project/color settings, render format, artifact path/hash, RGBA/alpha metrics, and whether the case passed. Graph text/readback is not a substitute for rendered pixels.

## P4-09 — real PSD baseline

After the micro pixel gate is usable, render the current real 422-tool graph from the same candidate family and compare it directly with the qualified `D:\Downloads\20260812.png` reference.

The first P4-09 run is a diagnostic baseline, not a requirement to pass immediately. Partition the difference before changing compositor math.

Classify material differences into the smallest useful category, for example:

- global/profile/working-space difference;
- alpha/premultiply edge difference;
- one blend mode family;
- one clipping chain or coverage boundary;
- isolated group only;
- Pass Through group only;
- placement/crop/canvas difference;
- asset materialization difference;
- unsupported PSD semantics.

Do not fit the reference by changing thresholds, grading, resizing, blurring, flattening, or applying a whole-image correction.

## Evidence-driven repair rule

When a material failure is localized:

1. reduce it to the smallest deterministic fixture;
2. repair the smallest responsible boundary;
3. rerun the focused micro fixture;
4. rerun the real P4-09 comparison;
5. retain before/after metrics.

Do not redesign unrelated architecture around a failure that has not been localized.

## Deferred architecture work

Two known design debts remain visible but are not automatic blockers for the first host/pixel baseline:

1. `Evaluation IR` / capability decisions are currently produced after graph compilation and do not yet drive backend selection;
2. asset materialization still needs an explicitly verified ICC/straight-premult/transparent-RGB contract.

Use host/pixel evidence to decide whether either debt is causal. Before adding multiple backends, custom operations, verified bake paths, or broader PSD feature support, connect capability planning to lowering so strict mode cannot silently emit an unverified backend.

## Stop conditions

Stop and report instead of advancing when:

- P4-08 cannot load the current artifact and the blocker is not yet localized;
- the micro pixel gate exposes an unresolved Loader/alpha/color contract;
- the real baseline shows a material failure that has not yet been reduced to a fixture;
- required host/reference evidence is unavailable.

`PARITY-004` remains `in_progress` until the required host/pixel evidence is complete and fresh verification permits the canonical state transition.
