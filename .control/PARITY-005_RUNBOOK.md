# PARITY-005 autonomous investigation runbook

Status: ACTIVE task-branch execution contract for `PARITY-005`.

Purpose: let a fresh Worker / Coordinator continue `clbl=false` and group-interaction investigation from repository state without chat history, while preserving the PARITY-004 float32/verification contracts and avoiding speculative production edits.

This runbook does not override `AGENTS.md`, `.control/CURRENT_GOAL.md`, `docs/COMPOSITING_CONTRACT.md`, or `docs/PARITY_VALIDATION.md`. When they conflict, follow the higher-authority source and record the conflict.

## Mission

Determine the semantics and safe lowering policy for explicit PSD `clbl=false` plus its interaction with group/backdrop boundaries.

The acceptable terminal outcomes are:

1. a single semantic model survives independent discriminating fixtures and is eligible for bounded production implementation; or
2. semantics remain insufficiently proven and strict mode is made fail-closed through an explicit verified bake/reject path.

Do not guess a production graph merely because a same-named Fusion operation exists.

## Operating model

Use three investigation axes when parallel workers are available. If not, run them sequentially in independent contexts.

### Axis A — Semantic / PSD investigator

Read-only or temp-only by default.

Owns:
- PSD bytes/provenance for absent, explicit true, explicit false `clbl`;
- parser, Semantic IR, Evaluation IR and group/clipping membership facts;
- competing semantic hypotheses and formula oracles independent of production lowering;
- discrimination table showing which fixture separates which hypotheses.

Must not:
- edit production lowering;
- use current Fusion fallback as semantic truth;
- select formulas per pixel;
- fit a reference.

### Axis B — Fixture / host investigator

Read-only or temp-only until Coordinator grants a bounded evidence implementation.

Owns:
- deterministic fixtures;
- actual Fusion micro-renders and internal taps;
- true/default controls before false-path claims;
- machine-readable metrics and artifact provenance;
- classification of each result as supports / contradicts / non-discriminating for each hypothesis.

Must preserve the PARITY-004 Loader/Saver/float32 contract. One-LSB host noise is diagnostic, not semantic evidence.

### Axis C — Critic / Referee

Independent from A/B conclusions.

Owns:
- false-PASS audit;
- oracle-independence audit;
- backdrop/group/alpha/opacity/premultiply/clamp/ICC confound checks;
- determination of the next cheapest discriminating experiment;
- challenge of any proposed semantic promotion.

Axis C does not write production code.

### Coordinator

Only the Coordinator may authorize production implementation after the semantic promotion gate is satisfied.

Do not allow multiple workers to edit the same production file or commit concurrently to the task branch.

## Queue

The machine-readable companion is `.control/PARITY-005_QUEUE.json`. Execute ready items in dependency order. Independent items with the same stage may run in parallel.

### Stage S0 — Re-establish baseline

- P5-00 fresh-read main/task branch/current state/contracts.
- P5-01 provenance census for absent / explicit true / explicit false `clbl` fixtures.
- P5-02 inventory existing tests, fallbacks and capability decisions; explicitly record that strict `rejected` plus emitted FIRST_USABLE fallback is a fail-open debt, not parity proof.

Exit: source facts and implementation debt are recorded without semantic inference.

### Stage S1 — Register rival semantics offline

- P5-03 encode H1-H5 as independent offline oracles.
- P5-04 generate expected RGBA for each fixture/hypothesis.
- P5-05 build pairwise discrimination matrix.

Exit: at least one low-noise fixture distinguishes every still-live hypothesis pair, or STOP `S-NONDISCRIMINATING`.

### Stage S2 — Controls and core false-path host evidence

Run true/default controls first, then false-path fixtures:

- P5-06 absent vs explicit true control;
- P5-07 backdrop swap;
- P5-08 base non-Normal mode scope;
- P5-09 base opacity scope;
- P5-10 two-member chaining/order;
- P5-11 fractional base alpha / alpha-growth check.

Exit: most hypotheses are contradicted, or evidence is explicitly non-discriminating.

### Stage S3 — Group interaction matrix

- P5-12 isolated group;
- P5-13 Pass Through group;
- P5-14 nested group;
- P5-15 group-as-base;
- P5-16 group-as-member;
- P5-17 parent/group span termination and no-cross-parent proof.

Exit: surviving model is stable across required group scopes, or strict bake/reject becomes the preferred outcome.

### Stage S4 — Semantic decision gate

Produce a decision record containing:
- surviving hypotheses;
- rejected hypotheses and decisive fixtures;
- unresolved cases;
- renderer scope/version;
- alpha/opacity/backdrop/group semantics;
- false-PASS risks checked;
- implementation authority: `native_candidate`, `verified_bake_candidate`, or `reject`.

No production implementation before this gate.

### Stage S5 — Capability-gated implementation

Only if S4 grants authority.

Required first repair regardless of final semantic model: strict `rejected` capability decisions must not silently emit the legacy `clbl=false` FIRST_USABLE fallback.

Then implement the smallest verified lowering or explicit bake/reject behavior.

Rules:
- preserve 32-bit float production path;
- no 8-bit quantization solely for byte identity;
- no real-PSD layer-ID special cases;
- no threshold relaxation/reference fitting;
- no unrelated compiler redesign;
- unknown semantics remain fail-closed.

### Stage S6 — Regression and closure

- focused offline tests;
- `scripts/check.ps1`;
- focused actual Fusion host matrix when a Fusion claim is made;
- privacy/evidence audit;
- Worker closeout -> fresh Verifier;
- only fresh Verifier PASS permits task state transition;
- publish -> fresh remote readback -> remote completion guard;
- main merge still requires explicit authority under `AGENTS.md`.

Do not start PARITY-006/007 in this runbook.

## Promotion gates

### Semantic promotion — PASS only when all apply

- one semantic model is supported by more than one independent discriminating fixture;
- competing models are contradicted by actual evidence, not merely less convenient;
- at least one fixture varies outer backdrop;
- at least one fixture exposes alpha/coverage differences;
- base mode and base opacity scope are separately tested;
- member-member chaining/order is tested;
- required group interaction scope is tested or explicitly excluded by capability policy;
- observed differences exceed known host quantization noise;
- oracle implementation is independent from production lowering;
- Referee reports no unresolved false-PASS path capable of changing the semantic conclusion.

### Native lowering promotion — PASS only when all apply

- semantic promotion passed;
- native graph is derived from the semantic decision, not from reference fitting;
- focused host artifacts reproduce the promoted semantics;
- strict capability planning actually gates lowering;
- no silent fallback remains;
- float32 path is preserved unless a separately verified semantic boundary requires otherwise.

### Bake/reject promotion — PASS when

- semantics cannot be uniquely or safely represented by verified native lowering; and
- the supported dependency closure is explicit; and
- strict mode cannot accidentally emit an approximate editable graph; and
- user-visible/provenance reporting makes the fallback explicit.

## Stop conditions

Use these stop codes in reports and queue updates.

### `S-AUTHORITY`
A required action is merge/release/deploy, destructive, credential-changing, force-push/history rewrite, or another operation requiring explicit authority.

Action: stop before the operation and report the exact requested authority.

### `S-INPUT`
Required fixture/reference/PSD bytes are missing, mutable, hash-mismatched, or cannot be safely qualified.

Action: stop semantic promotion; do not substitute a guessed input.

### `S-HOST`
Actual Fusion artifacts cannot be acquired through multiple reasonable routes, or host/version/settings are incompatible with the claimed evidence.

Action: preserve offline evidence but do not make a Fusion pixel claim.

### `S-NONDISCRIMINATING`
Current fixtures do not separate still-live hypotheses beyond host noise.

Action: design the smallest stronger fixture. Do not implement production code.

### `S-CONTRADICTION`
Independent evidence sources disagree materially and no known confound explains the disagreement.

Action: freeze implementation; ask Axis C to isolate the contradiction and propose one new discriminator.

### `S-CONFOUND`
Premultiply/straight RGB, transparent RGB, opacity placement, clamp, ICC/color space, crop/canvas, or quantization can explain the observed distinction.

Action: remove/control the confound before semantic promotion.

### `S-FAILOPEN`
Strict capability decision rejects/unverifies an operation but lowering still emits an approximate/legacy graph.

Action: this is a blocker for strict production use. Do not call the path supported.

### `S-REGRESSION`
A bounded implementation creates a new coherent visual/semantic regression, alpha mismatch, group/clipping scope defect, or material pixel outlier.

Action: revert/bypass only the bounded candidate; return to the last proven boundary. Do not relax thresholds.

### `S-UNSUPPORTED`
Required semantics remain unverified after reasonable discriminating experiments or cannot be represented safely/editably.

Action: prefer explicit verified bake/reject over guessed native parity.

### `S-VERIFIER`
Fresh Verifier returns FAIL/BLOCKED or cannot reproduce the candidate/evidence.

Action: do not self-mark done or advance active task.

### `S-REMOTE`
Publish/readback/remote completion guard fails or remote state does not match the claimed state.

Action: branch-level evidence may remain valid, but canonical completion is blocked.

## Continue-without-human rules

A worker should continue autonomously when:
- the next queue item is ready and reversible;
- required inputs/evidence are available;
- the action is read-only, temp-only, or an in-scope task-branch edit;
- no stop condition is active;
- the result can be checked with an executable test, metric, or independent artifact.

A worker should not stop merely because:
- one fixture fails;
- one hypothesis is contradicted;
- a strict threshold-zero diagnostic reports only known quantization-scale noise;
- an investigation requires a different bounded fixture;
- previous chat context is unavailable.

Instead update the hypothesis/evidence state and continue to the next discriminating action.

## Checkpoint rules

Report a checkpoint when any of these occurs:
- S4 semantic decision gate is reached;
- a stop condition requires human authority/input;
- a production implementation candidate is host-proven and ready for fresh Verifier;
- PARITY-005 reaches branch-level closure;
- approximately 8 completed queue items have accumulated since the last durable checkpoint and a decision changed materially.

Do not checkpoint after every fixture.

## Evidence discipline

Safe summaries belong under `.control/evidence/PARITY-005/<run-id>/`.

Full-size/private artwork and renders stay in ignored local storage. Every committed claim names exact branch/commit, fixture ID, renderer/version/settings when applicable, artifact/hash references, metrics, hypothesis effect, and unresolved confounds.
