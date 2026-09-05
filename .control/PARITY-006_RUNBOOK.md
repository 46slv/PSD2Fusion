# PARITY-006 autonomous convergence runbook

Status: ACTIVE task-branch execution contract for `PARITY-006`.
Branch: `codex/parity-006` from `main@fe98c7abb4ff5627ccee6126781b228ccd17a70f`.
Authority: user PARITY-006 start instruction; `AGENTS.md`; `.control/CURRENT_GOAL.md`; `docs/COMPOSITING_CONTRACT.md`; `docs/PARITY_VALIDATION.md`.

This runbook does not override higher-authority sources. On conflict follow the higher source and record it.

## Mission

Real `D:\Downloads\a.psd` from latest production candidate is reproducibly lowered and actually Fusion-rendered, then compared against qualified `D:\Downloads\20260812.png`. Converge material differences by semantic region. Material differences only.

Canonical inputs (read-only, never commit):
PSD sha256 `574d8a6511b2aabe744835d81ed76c8fc8ffd0c9c5678f3359e8eda10f9174db`
REF sha256 `91ff8daef941b3d9052497190fdc8aa6f4d56ba524c8d912cf011b6818535f54`
Canvas 2304x1296 RGBA, ref ICC 3144 bytes.

PARITY-004 acceptance policy stays in force:
32-bit float pipeline; strict threshold-0 retained as diagnostic; no repair whose only purpose is +-1LSB quantization identity; alpha/group/clipping/blend/opacity semantic diffs, coherent regions, visible divergence, large deltas are blockers; no reference fitting, global grade, resize, blur, flatten, threshold relaxation.

Do not repeat: PARITY-004 Linear Dodge exploration, 1LSB repair loops, PARITY-005 clbl=false semantic investigation.

## Current closure checkpoint

A fresh PARITY-006 verifier has returned PASS on the submitted production candidate. Fresh host evidence from the dedicated Resolve project `PSD2Fusion` shows no material-scale residual; strict threshold-0 remains diagnostic only. The earlier S-HOST incident remains historical evidence; its exact root cause is intentionally unclaimed because the later clean dedicated-project route closed it as a blocker.

From this point, do not re-enter material repair unless a later fresh verifier/post-transition check finds a new real material regression.

Program-level continuation is now owned by:
- `.control/PROGRAM_CLOSEOUT_RUNBOOK.md`
- `.control/PROGRAM_CLOSEOUT_QUEUE.json`
- `.control/PROGRAM_CLOSEOUT_STATE.json`

Muse 1.3 should treat those files as the parent long-run orchestration contract from P6 canonical closure through P7 and program completion. Continue ready reversible items without per-step confirmation. Use the program recovery playbook before raising a stop code.

## Operating model

Three axes when parallel workers exist, else sequential in independent contexts. Only Coordinator edits production code. One material boundary per repair. Never let two workers edit the same production file concurrently.

### Axis A - Difference localizer (read-only production)
Fresh real render/reference diff; RGB/alpha max/mean/p99; counts >1/>2/>8/>16/>32; bbox and connected/coherent regions; semantic mapping to layer/group/clipping-chain/mode/opacity; region ranking by materiality. No production edits.

### Axis B - Minimal fixture / repair investigator (temp-only until granted)
Reduce Axis A material region to smallest fixture; list competing semantic/implementation hypotheses; gather actual Fusion internal boundary / host micro evidence; propose smallest bounded repair with before/after metrics. No production edits before semantic gate.

### Axis C - Referee / regression auditor (no production code)
False-PASS audit; separate quantization class from material difference; check profile/premult/transparent-RGB/crop/canvas confounds; check unrelated-region regression; check repair is not reference fitting; propose next cheapest discriminating experiment.

### Coordinator
Owns queue, gates, production edits, evidence linkage, checkpoints, stop codes. Enforces one-boundary-at-a-time repair and full re-verification after each repair.

## Work queue

Machine companion: `.control/PARITY-006_QUEUE.json`. Execute ready items in dependency order. Same-stage independent items may run in parallel on disjoint scopes.

### Stage S0 - Fresh baseline (no past values as truth)
- P6-00 fresh-read main/task branch/state/contracts/evidence; record exact HEADs.
- P6-01 regen real PSD from latest candidate to temp path; record layers/groups/chains/tools/comp sha.
- P6-02 acquire actual Fusion render via qualified production path; record host/version/settings/artifact hash.
- P6-03 qualified reference compare at threshold 0; record strict metrics + artifacts.
- P6-04 material residual inventory: partition by semantic region, rank by materiality.
- P6-05 Axis C confound + false-PASS audit of baseline.
Exit: fresh baseline recorded, or STOP per codes below. If no material-scale residual, go to S3 closure candidate; do not chase quantization.

### Stage S1 - Region loop (largest/coherent/high-confidence first)
- P6-10 reduce region to minimal fixture.
- P6-11 list competing hypotheses with discriminating fixtures.
- P6-12 host micro/region evidence.
- P6-13 Coordinator bounded repair of one boundary (only after repair authority below).
- P6-14 focused tests + check.ps1 + micro/region gate + full real render/recompare.
One repair improving nothing means change cause classification, never repeat same hypothesis. No global fitting.

### Stage S2 - Regression and closure
- P6-20 Worker closeout with exact HEAD/files/commands/metrics/blockers/evidence path/verifier start.
- P6-21 fresh Verifier PASS/FAIL/BLOCKED; on PASS state transition + publish + fresh remote readback + remote completion guard. Main merge needs explicit authority. Never start PARITY-007 here.

## Repair authority (all required before production edit)
- material region is reproducible;
- semantic owner/boundary is identified;
- competing hypotheses narrowed by fixture/host evidence;
- repair is not global fitting;
- Axis C denies false-PASS.
After repair always: focused tests, scripts/check.ps1, actual Fusion micro/region gate, full real PSD render/reference.

## Promotion gates
- Region repair PASS only with: reproducible material region, identified owner/boundary, fixture/host-narrowed hypothesis, bounded non-fitting repair, Axis C false-PASS denial, focused+full re-compare with no new material regression.
- Closure PASS only with: every material-scale difference resolved or explicitly supported/rejected per capability policy, remainder is acceptance-nonblocking quantization class, strict-0 diagnostic retained, float32 preserved, no fitting nodes.

## Stop codes
- S-AUTHORITY: merge/release/destructive/credential/history action needs explicit authority.
- S-INPUT: PSD/reference/hash/qualification problem; do not substitute guessed input.
- S-HOST: actual Fusion artifact unobtainable via reasonable routes; no pixel claim.
- S-CONFOUND: ICC/premult/transparent-RGB/canvas explains result; control it first.
- S-NONLOCALIZED: material diff cannot be narrowed to a semantic boundary.
- S-CONTRADICTION: independent material evidence conflicts with no resolved confound.
- S-REGRESSION: repair creates new material regression; revert to last proven boundary.
- S-UNSUPPORTED: semantics cannot be safely represented as verified native/bake/reject.
- S-VERIFIER: fresh verifier FAIL/BLOCKED or irreproducible evidence.
- S-REMOTE: publish/readback/guard fails or remote state mismatches.
Local ref invisibility alone is never a stop: check GitHub remote directly, fetch with explicit refspec if needed.

## Continue-without-human
Continue when: next queue item ready and reversible; inputs/evidence available; action is read-only/temp-only/in-scope task-branch edit; no stop active; result checkable by test/metric/artifact.
Do not stop merely for: one fixture failure; one contradicted hypothesis; strict-0 reporting only known quantization noise; need for another bounded fixture; missing chat history. Update state and continue.

## Checkpoint rules
Return to user only on: (1) fresh baseline finds new material blocker with well-narrowed cause boundary; (2) bounded repair is host-proven; (3) branch-level PARITY-006 closure reached; (4) stop code needs human authority/input.
Checkpoint report keeps to: completed queue IDs; fresh real metrics; material residual regions; repaired/rejected boundaries; active stop code; exact HEAD; next ready items.

## Evidence discipline
Safe summaries under `.control/evidence/PARITY-006/<run-id>/summary.json`. Full renders/private files under ignored `.local/`, `artifacts/`, `parity-output/`. Every claim names exact branch/commit, fixture ID, host/version/settings, artifact hashes, metrics, hypothesis effect, unresolved confounds.
