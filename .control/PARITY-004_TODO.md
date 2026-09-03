# PARITY-004 Fusion-first implementation TODO

Purpose: finish grouped/default PSD clipping as a readable Fusion graph, then verify that the exact graph produces the required pixels in actual Fusion. Graph structure is a prerequisite, not pixel proof.

Detailed remaining host/pixel procedure: `docs/PARITY_004_HOST_PIXEL_GATE.md`.

## Working rule

Work the remaining gates in order. Preserve the already-published P4-03 through P4-07 structural candidate unless host/pixel evidence identifies a concrete defect. Prefer ordinary Fusion Loader / Merge / mask connections and readable Flow structure. Do not add a new abstraction layer merely because a proof gate is pending.

Do not start `PARITY-005`, `PARITY-006`, or a broad compiler/planner redesign before the first P4-09 baseline unless the current graph cannot load/render and the blocker is already localized to that architecture boundary.

## Current recipe

Canonical grouped/default `clbl=true` candidate:

```text
base Loader
  -> fixed base matte reused by every member
  -> one ClipIn Merge (`Operator=In`) per member
  -> local ClipStack Merge per member (`ProcessAlpha=0`)
  -> one outer chain Merge with base blend/overall opacity
```

The direct Effect Mask candidate was rejected for partial base alpha because ordinary source-over would expand coverage without an additional alpha-preserving stage.

## P4-01 — Simplest 1:1 clipping recipe

Status: `STRUCTURAL_COMPLETE / HOST_PIXEL_PENDING`

Selected candidate: explicit fixed-matte `Operator=In` lowering.

Structural evidence proves one base + one member lowers with no outer backdrop inside the local clipping operation. Pixel truth remains subject to P4-HOST-PIXEL.

Evidence: `scripts/parity/p4_01.py`, `tests/test_parity004_p401_graph.py` and committed P4-01 evidence.

## P4-02 — Multiple clipped members share one base matte

Status: `STRUCTURAL_COMPLETE / HOST_PIXEL_PENDING`

All members reuse the exact same base coverage. Member order follows PSD bottom-to-top order. The progressively composited local result is never used as the next member matte.

Evidence:

- `scripts/parity/p4_02.py`;
- `psd2fusion/fusion_comp.py` strict contiguous-span handling;
- `tests/test_parity004_p402_graph.py`.

## P4-03 — Member blend and opacity placement

Status: `STRUCTURAL_COMPLETE / HOST_PIXEL_PENDING`

Member `ApplyMode` and `Blend` controls live on each local ClipStack Merge. The fixed ClipIn remains `Operator=In`, Normal, Blend 1. Structural fixtures cover Normal, Multiply, Linear Dodge, Overlay and 25/50/75/100% member opacity.

Evidence: `scripts/parity/p4_03.py`, `tests/test_parity004_p403_graph.py`.

## P4-04 — Base blend and opacity boundary

Status: `STRUCTURAL_COMPLETE / HOST_PIXEL_PENDING`

The completed local stack enters exactly one outer chain Merge. That Merge owns the base blend and overall opacity once.

Evidence: `scripts/parity/p4_04.py`, `tests/test_parity004_p404_graph.py`.

## P4-05 — Groups and nesting

Status: `STRUCTURAL_COMPLETE / HOST_PIXEL_PENDING`

The same clipping recipe is structurally covered inside isolated and Pass Through groups, nested isolated groups, and clipping spans adjacent to group boundaries. Existing GroupOperator stream attachment remains unchanged.

Evidence: `scripts/parity/p4_05.py`, `tests/test_parity004_p405_graph.py`.

## P4-06 — Fusion Flow layout

Status: `COMPLETE`

Clipping member Loaders use deterministic rows above the base; ClipIn/ClipStack pairs are clustered; the fixed matte connection is visible; one outer Merge exits the cluster; GroupOperator boundaries remain visually distinct.

Evidence: `scripts/parity/p4_06.py`, `tests/test_parity004_p406_layout.py`.

## P4-07 — Apply the recipe to the real PSD

Status: `STRUCTURAL_COMPLETE / HOST_PIXEL_PENDING`

The read-only `D:\Downloads\a.psd` currently expands to:

- 23 default/true clipping chains;
- 59 clipped members;
- 34 groups;
- 363 generated Fusion tools.

All chains pass structural fixed-matte, `Operator=In`, `ProcessAlpha=0`, member-control and one-outer-boundary checks. Representative chains span one-to-six members and nesting depths 2-4.

Evidence: `scripts/parity/p4_07.py`, committed P4-07/P4-03-through-P4-07 evidence, with full outputs kept under ignored `.local/`.

## P4-08 — Ordinary Fusion load/readback sanity

Status: `PASS — HOST_LOADED`

Use a new Resolve/Fusion launch and new project when practical; a known disposable test project is also acceptable.

Required checks:

- `.comp` loads;
- Loader paths resolve;
- MediaOut receives the final stream;
- representative GroupOperator and clipping connections survive;
- `ApplyMode`, `Blend`, `Operator=In`, `ProcessAlpha=0`, and Loader `PostMultiply` survive readback/reload;
- no missing/invalid tools are introduced;
- record exact candidate commit and Resolve/Fusion version.

P4-08 may establish `host_loaded`. It cannot establish `pixel_verified`.

Current evidence: `.control/evidence/PARITY-004/20260903-p408-96112d5/summary.json` records successful ordinary load/readback for candidate `96112d5`. Do not rerun P4-08 unless a later implementation changes the candidate graph materially.

## P4-HOST-PIXEL — Minimum actual-Fusion pixel gate

Status: `IN_PROGRESS — FUSION-ONLY BOUNDED DIAGNOSTIC NEXT`

Render deterministic micro fixtures in actual Fusion before diagnosing the full real PSD. At minimum cover:

- Loader straight/premult and `PostMultiply` boundary;
- `Operator=In` with fractional base/member alpha;
- `ProcessAlpha=0` fixed-alpha invariant;
- Normal / Multiply / Linear Dodge / Overlay member modes;
- 25/50/75/100% member opacity;
- base opacity and at least one non-Normal base mode;
- transparent / black / white / colored outer backdrops.

Use the existing comparator. Record actual rendered artifact hashes and RGBA/alpha metrics. Graph text or host readback alone is not pixel evidence.

The physical artifact route is established by `.control/evidence/PARITY-004/20260904-fusion-artifact-acquisition/summary.json`. Photoshop is not used and is not a prerequisite. The next bounded diagnostic compares actual Fusion boundaries for Normal, Multiply, Linear Dodge and Overlay across identical ungrouped and isolated-GroupOperator inputs. A formula oracle is diagnostic only.

Full procedure: `docs/PARITY_004_HOST_PIXEL_GATE.md`.

## P4-09 — Real Fusion render / golden-reference baseline

Status: `PENDING`

After P4-08 and a usable micro pixel gate, render the current real graph and compare it directly with `D:\Downloads\20260812.png`.

The first run is a diagnostic baseline, not a requirement to pass immediately. Classify material differences before editing compositor math. Possible categories include color/profile, alpha/premult edge, blend family, one clipping chain, isolated/Pass Through group scope, placement/canvas, asset materialization, or unsupported semantics.

For a material failure:

1. reduce it to the smallest deterministic fixture;
2. repair the smallest responsible boundary;
3. rerun that focused fixture;
4. rerun the real comparison;
5. retain before/after metrics.

Do not fit the reference by threshold relaxation, global grade, resize, blur, flatten, or whole-image correction.

## Known architecture debt — observe, do not preemptively redesign

Two known debts remain visible:

1. Evaluation IR / capability decisions currently do not drive backend selection before graph compilation;
2. asset materialization still needs an explicitly verified ICC / straight-premult / transparent-RGB contract.

Do not ignore these. Also do not perform a broad rewrite before the first host/pixel baseline merely because they exist. Use actual Fusion evidence to determine whether either is causal. Before adding multiple backends, custom operations, verified bake paths or broader PSD feature support, capability planning must be connected to lowering so strict mode cannot silently emit an unverified backend.

## Out of scope until PARITY-004 closes

- explicit `clbl=false` semantics (`PARITY-005`);
- broad real-PSD convergence work before the first P4-09 baseline (`PARITY-006`);
- new PSD importer mechanism;
- Photoshop automation as a dependency;
- blind reference fitting;
- unrelated PSD feature expansion.

## Immediate next action

Prepare the deterministic Fusion-only boundary fixture offline. When DaVinci/Fusion use resumes, materialize the ungrouped and isolated-GroupOperator boundaries, then take the first P4-09 real baseline if the graph is stable. Keep `PARITY-004` `in_progress` until required host/pixel evidence is complete and a fresh verifier permits state transition.
