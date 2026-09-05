# PARITY-006 autonomous convergence runbook

Status: ACTIVE task-branch execution contract for `PARITY-006`.
Branch: `codex/parity-006` from canonical PARITY-005-complete main.
Authority: user PARITY-006 start instruction; `AGENTS.md`; `.control/CURRENT_GOAL.md`; `docs/COMPOSITING_CONTRACT.md`; `docs/PARITY_VALIDATION.md`.

This runbook does not override higher-authority sources. On conflict follow the higher source and record it.

## Mission

Real `D:\Downloads\a.psd` from latest production candidate is reproducibly lowered and actually Fusion-rendered, then compared against qualified `D:\Downloads\20260812.png`. Converge material differences by semantic region. Material differences only.

Canonical inputs are read-only and must never be committed.

PARITY-004 acceptance policy stays in force: preserve the 32-bit float pipeline; keep strict threshold-0 as diagnostic; do not repair solely for +/-1 LSB identity; material alpha/group/clipping/blend/opacity differences, coherent visible regions, and large deltas remain blockers; no reference fitting, global grade, resize, blur, flatten, or threshold relaxation.

Do not repeat PARITY-004 Linear Dodge exploration, 1LSB repair loops, or PARITY-005 `clbl=false` semantic investigation.

## Current closure checkpoint

A fresh PARITY-006 verifier has reached PASS on the submitted candidate after a dedicated-project actual Fusion run. The verifier independently reproduced repository checks, input identity, artifact hash, strict comparator metrics, and false-PASS/confound audits. Remaining residuals are classified as non-material quantization-scale differences; no material region remains. The earlier S-HOST incident remains recorded but is no longer a closure blocker after successful dedicated-project runs. The exact historical crash mechanism is intentionally left unclaimed/unisolated.

The next PARITY-006 work is therefore canonical closure only: state transition, publish/readback, remote guard, and main promotion if explicitly authorized. Do not re-enter the material-repair loop unless a fresh verifier or post-transition check reveals a real material regression.

## Dedicated Resolve project

All PARITY-006 host work uses the dedicated Resolve project named exactly `PSD2Fusion`. Historical `PSD2Fusion P4-08 20260902` is not an allowed host target for PARITY-006.

## Operating model

Use three axes when parallel workers exist, else sequential independent contexts. Only Coordinator edits production code. One material boundary per repair. Never let two workers edit the same production file concurrently.

Axis A: Difference localizer (read-only production).
Axis B: Minimal fixture / repair investigator (temp-only until granted).
Axis C: Referee / regression auditor (no production code).
Coordinator owns queue, gates, production edits, evidence linkage, checkpoints, and stop codes.

## Work queue

Machine companion: `.control/PARITY-006_QUEUE.json`. Execute ready items in dependency order. Same-stage independent items may run in parallel on disjoint scopes.

### Stage S0 - Fresh baseline
P6-00 through P6-05 establish fresh repository/input/host/reference evidence and confound audit. These have reached a closure-quality result in the submitted candidate.

### Stage S1 - Region loop
P6-10 through P6-14 are conditional only when a material residual exists. Do not execute them for known quantization-only residuals.

### Stage S2 - Regression and closure
P6-20 Worker closeout.
P6-21 fresh Verifier PASS/FAIL/BLOCKED.
P6-22 branch-level state transition + publish + fresh readback + remote completion guard after PASS.
P6-23 canonical main promotion only with explicit merge authority, followed by fresh readback and canonical remote guard.
Never start PARITY-007 before canonical PARITY-006 completion on main.

## Completion gate

PARITY-006 may become done/pass only when all apply:
- fresh Verifier PASS on the exact submitted candidate;
- no material-scale residual remains;
- strict threshold-0 diagnostic retained without relaxation;
- remaining differences are acceptance-nonblocking quantization class;
- alpha/dimensions/canvas/profile qualification are correct;
- actual Fusion artifact is qualified and tied to exact candidate/host/project/settings;
- dedicated `PSD2Fusion` host route is healthy enough for closure evidence;
- no production drift invalidates the render evidence;
- `scripts/check.ps1` and state/schema validation pass;
- evidence is committed and reachable.

After branch-level PASS, publish and fresh remote readback are mandatory. Canonical main completion additionally requires an authorized safe merge and remote completion guard PASS.

## Stop codes

- S-AUTHORITY: merge/release/destructive/credential/history action needs explicit authority.
- S-INPUT: required input/hash/qualification cannot be recovered.
- S-HOST: actual Fusion artifact cannot be acquired through multiple reasonable safe routes.
- S-CONFOUND: ICC/premult/transparent-RGB/canvas/export behavior prevents causal classification and cannot be controlled autonomously.
- S-NONLOCALIZED: a material defect exists but cannot be narrowed after reasonable diagnostics.
- S-CONTRADICTION: independent material evidence conflicts without resolved confound.
- S-REGRESSION: bounded repair creates new material regression and no safe bounded alternative remains.
- S-UNSUPPORTED: required semantics cannot be safely represented as verified native/custom/bake/reject.
- S-VERIFIER: fresh verifier repeatedly FAIL/BLOCKED after available bounded corrections.
- S-REMOTE: publish/readback/guard mismatch cannot be resolved by reasonable fetch/retry.

Local ref invisibility, long context, one test failure, one failed fixture, one rejected hypothesis, need for another safe diagnostic, or known 1LSB noise are not stop conditions.

## Continue without human

Continue autonomously when the next queue item is ready/reversible, inputs/evidence exist, operation is read-only/temp-only/task-branch-safe, no stop code is active, and result is testable by artifact/metric/test.

## Checkpoint rules

Return to user only on: canonical merge authority requirement; unexpected fresh material defect; branch-level closure; canonical PARITY-006 closure; or an actual stop code requiring human action.

## Evidence discipline

Safe summaries under `.control/evidence/PARITY-006/<run-id>/`. Full renders/private files stay ignored/local. Every claim names exact branch/commit, host/version/project/settings, artifact hashes, metrics, and unresolved confounds.
