# PSD2Fusion program closeout runbook

Status: ACTIVE long-run roadmap from PARITY-006 verifier PASS to canonical program completion.
Model target: Muse 1.3 autonomous orchestrator + workers with durable repo-local recovery.

This is the parent execution contract. Higher authority remains: current user instruction, `AGENTS.md`, `.control/current.json`, `.control/CURRENT_GOAL.md`, task-specific runbooks, validation/compositing contracts, fresh live Git/GitHub state, and qualified host evidence.

## Mission

Finish the compositing-parity program safely from the current PARITY-006 verifier-PASS checkpoint through:

1. canonical PARITY-006 done/pass on `main`;
2. fresh independent PARITY-007 closeout from canonical main;
3. legal terminal program state on canonical main;
4. final remote readback/guard proof.

Do not reopen closed PARITY-004 Linear Dodge or PARITY-005 `clbl=false` investigations unless a fresh independent verifier finds a real material regression.

## Durable runtime memory

Use these as the long-run memory system:

- `.control/PROGRAM_CLOSEOUT_RUNBOOK.md` — policy/decision playbook;
- `.control/PROGRAM_CLOSEOUT_QUEUE.json` — immutable-ish work definition/dependencies;
- `.control/PROGRAM_CLOSEOUT_STATE.json` — mutable execution ledger/current position;
- task-specific evidence under `.control/evidence/`;
- Git commits/remote refs — durable checkpoints.

Before every new Muse context, worker handoff, or recovery:

1. enter the correct repository (`D:\Documents\PSD2Fusion` on the current host);
2. fresh-read `git status`, branch, HEAD, `origin/main`, active task branch;
3. verify remote refs with GitHub API / `git ls-remote`; local ref absence is not remote absence;
4. read `AGENTS.md`, `.control/current.json`, this runbook, queue, execution state, active task runbook/evidence;
5. reconcile `PROGRAM_CLOSEOUT_STATE.json` against live Git before trusting it;
6. continue the next ready queue item.

If context grows large, do not stop. Update execution state + evidence, commit/push the durable checkpoint, discard old reasoning, fresh-read and continue.

## Muse 1.3 orchestration model

Muse may orchestrate multiple agents/contexts. Prefer this structure whenever parallelism helps:

### Coordinator (Muse-C)

Single owner of:
- queue/state transitions;
- Git commits/pushes/PR updates;
- production writes;
- conflict resolution;
- promotion/stop decisions;
- final synthesis.

Only Coordinator writes shared production/control files unless it explicitly delegates one disjoint file set to one worker.

### Lane A — Repository / evidence auditor

Read-only or evidence-only. Owns:
- Git/GitHub/state/evidence integrity;
- commit reachability;
- privacy/provenance;
- historical proof-chain audit.

### Lane B — Host / artifact executor

Temp-only plus evidence summaries. Owns:
- Resolve/Fusion host sanity;
- disposable comp execution;
- artifact hashes/metrics;
- host recovery routes.

Must use dedicated Resolve project exact name `PSD2Fusion`.

### Lane C — Referee / false-PASS auditor

Independent from A/B conclusions. Owns:
- semantic/capability audit;
- false-PASS/confound analysis;
- challenge of acceptance claims;
- verifier preparation.

### Fresh Verifier lane

Must be a new context/session with no reliance on Coordinator reasoning transcript. It reads only live repo/evidence/qualified artifacts and returns PASS/FAIL/BLOCKED. It never repairs its own candidate.

### Parallel scheduling

Safe parallel groups:
- after P7 clean environment exists: evidence-integrity audit and offline regression may run in parallel;
- after fresh regen: host render and semantic/capability audit may run in parallel;
- while a long host render is running, privacy/evidence/static audits may continue if they do not mutate host inputs or shared production files.

Serialize:
- state transitions;
- production edits;
- commits touching the same file;
- verifier verdict and subsequent correction;
- main promotion.

If parallel workers are unavailable, emulate lanes sequentially in fresh independent contexts. Lack of parallelism is never a stop condition.

## Worker handoff contract

Each delegated worker receives:
- exact branch/HEAD;
- queue item IDs;
- allowed paths/actions;
- input/evidence paths;
- explicit no-write or bounded-write scope;
- done criteria.

Each returns only:
- observed facts;
- commands/results;
- evidence paths/hashes;
- PASS/FAIL/BLOCKED for its assigned item;
- unresolved confound/next discriminator.

Workers do not decide program completion or main merge.

## Phase A — Canonical PARITY-006 closure

### A1 Fresh live-state recovery
Confirm remote P6 branch/main/PR/state/evidence using API + `ls-remote` + explicit fetch when needed.

### A2 Verifier linkage/drift audit
Confirm fresh P6 verifier PASS maps to exact production candidate. Post-verifier control/evidence-only drift is allowed if proven; any production drift requires affected verification rerun.

### A3 Branch state transition
Only after verifier PASS:
- P6 -> `done/pass`;
- advance active task per Goal/schema;
- P7 -> `ready` only if dependencies allow;
- update evidence linkage;
- state/schema validation + `scripts/check.ps1` PASS.

### A4 Publish/readback
Push branch, fresh fetch/readback, confirm state/candidate/verifier/evidence reachability.

### A5 Canonical main promotion
Requires explicit merge authority. If authority exists and fresh checks show expected main, branch `behind=0`, no divergence, and safe FF path: `--ff-only`; no force/rewrite/delete/release/deploy. Then fresh main readback + P6 remote guard PASS.

P7 must not start before canonical main proves P6 done/pass + P7 ready.

## Phase B — PARITY-007 independent closeout

### B1 Bootstrap
Create `codex/parity-007` from exact canonical main. Create P7 RUNBOOK/QUEUE and branch-level in_progress state per rules. Open/update Draft PR.

### B2 Clean environment
Use a fresh clean worktree/checkout from exact canonical main. No stale P6 generated artifact may silently satisfy a fresh P7 proof.

### B3 Evidence/state integrity
Audit P1-P6 done/pass proof chain, evidence reachability, privacy, unsupported/rejected semantics, state transitions. Re-run historical experiments only if proof linkage is insufficient.

### B4 Full offline regression
Fresh `scripts/check.ps1`, all tests/static checks, parser/evaluation/capability/clipping/group/LD/`clbl=false` fail-closed/comparator false-PASS coverage.

### B5 Fresh real PSD regen
Regenerate `D:\Downloads\a.psd` to ignored temp path. Record input hash, layers/groups/chains/members/tools/warnings/comp hash, float32 and forbidden-tool audit. Historical counts are expectations, never fitting targets.

### B6 Final fresh actual Fusion proof
Only project exact name `PSD2Fusion`. Host sanity -> disposable comp -> optional representative smoke -> full graph. Record version/PID/project/comp/tool count/frame range/Saver/result/timing/artifact hash/endpoint health/cleanup/save status.

### B7 Final reference compare
Strict threshold 0. Record dimensions/channels/profile, RGB max/mean/p99, alpha, >1/>2/>8/>16/>32, bbox/coherent components. No threshold relaxation/reference fitting.

Acceptance: no material-scale/coherent visible residual, correct alpha/structure/semantic scope, remainder only acceptance-nonblocking quantization class. Strict-0 may remain diagnostic FAIL.

### B8 Final semantic/capability audit
Audit fail-closed unknowns and `clbl=false`, explicit compatibility behavior, group/clipping/opacity/non-Normal/LD boundaries, capability-lowering gating, unsupported/bake/reject provenance, float32, no 8-bit identity repair, no real-layer-ID special cases.

### B9 False-PASS/privacy/complexity audit
Check wrong dimensions/alpha/profile/crop/premult fringe/local outliers/stale artifact/oracle=SUT/host-load!=render/threshold relaxation. Ensure no real PSD/reference/full render/private artifact is tracked. Ensure no silent legacy/dead duplicate verification path undermines final claim.

### B10 Independent verdict
Fresh Verifier returns exactly PASS/FAIL/BLOCKED and does not repair. PASS requires B2-B9 satisfactory, fresh Fusion proof, no material blocker, no unresolved false-PASS.

### B11 Correction loop
On FAIL/BLOCKED, classify and route using the decision playbook below. Separate Worker performs smallest bounded correction, then launch a new fresh verifier. Never repeat unchanged failure more than once.

## Phase C — Terminal closure

### C1 P7 state transition
Only after fresh P7 PASS. Fresh-read schema/Goal; apply only legal terminal fields. P7 done/pass + program status done only if supported. Update evidence, validate state/checks.

### C2 Publish/readback
Publish P7 branch; fresh remote readback of terminal state/verifier/evidence reachability.

### C3 Canonical final promotion
Explicit merge authority required. Fresh safe-FF checks; `--ff-only`; no force/rewrite/delete. Fresh main readback.

### C4 Final program proof
PROGRAM COMPLETE only when canonical main proves all required P1-P7 done/pass, valid terminal state, final fresh verifier PASS, final fresh Fusion artifact + accepted reference compare, no material/false-PASS blocker, remote guard PASS, check PASS, clean repo, no private leakage.

# Decision / recovery playbook — "if this, then that"

Use these routes before escalating.

## Git / repository

### Wrong cwd/repository
Move to `D:\Documents\PSD2Fusion`, re-run opening sequence. Do not stop.

### Local task branch/ref missing
Query GitHub API + `git ls-remote`; explicit refspec fetch. Do not infer remote absence from local config.

### GitHub connector/API disagrees with `ls-remote`
Use direct remote ref + fresh fetch + commit ancestry as tie-breaker; record discrepancy. Retry once. Continue if exact remote state becomes unambiguous.

### Working tree has unrelated changes
Do not overwrite. Prefer a fresh worktree from the intended exact commit and continue there. Stop only if ownership cannot be separated safely.

### GH007/private-email push rejection
For an unpushed task commit only, reuse the repository's established noreply author identity / reset author without global credential/config changes, then retry. Do not rewrite already-published shared history.

### Main advanced while task branch was running
Fresh fetch + compare.
- If changes are non-overlapping/control-only: merge current `origin/main` into task branch non-destructively, rerun affected state/checks, continue.
- If production-affecting: integrate safely, rerun affected offline/host verification before claiming PASS.
- Never force-rebase/rewrite published branch solely to regain FF.

### PR temporarily non-mergeable/stale
Fresh fetch/compare; update branch non-destructively if needed; rerun affected checks. Do not treat UI mergeability latency as program failure.

## Test / evidence

### One test fails
Re-run once unchanged to classify flake vs deterministic. If deterministic, localize smallest cause and fix/test. Do not stop unless correction paths are exhausted.

### Expected historical count/hash differs
Do not fit to old value. Determine whether path-dependent output, tool/version drift, state drift, or actual semantic regression explains it. Only material regression blocks.

### Evidence file missing but reproducible
Regenerate it from qualified inputs/candidate; record new evidence. Missing reproducible evidence is not S-INPUT.

### Evidence claim conflicts with fresh result
Fresh result wins. Classify stale evidence vs real contradiction. Update superseding evidence; do not erase history.

## Resolve / host

### Resolve process/endpoints absent before required host proof
If launching/reconnecting Resolve is available and safe, start/reconnect, select exact project `PSD2Fusion`, run host sanity, continue. Otherwise S-HOST.

### Wrong current Resolve project
Switch/open exact `PSD2Fusion` by API/readback before mutation. Never use unrelated project as closure evidence.

### Trivial sanity fails
Try one alternate qualified minimal route / fresh disposable comp. If still unavailable, S-HOST; do not attempt full graph.

### Representative smoke fails but trivial passes
Localize tool/range/comp-lifecycle issue. Reduce graph/route. Do not call it pixel parity failure.

### Full render returns nil/no artifact/crashes
Record incident. Relaunch if safe, verify `PSD2Fusion`, trivial sanity, then one changed diagnostic route. Do not repeat identical full route more than once. Split cause into graph size/tool, specific node, Saver/range, memory/resource, lifecycle. S-HOST only after reasonable alternatives fail.

### Artifact hash differs from prior qualified artifact
Not automatically FAIL. Recompute comparator + metadata; if metrics/semantics remain within acceptance, record nondeterministic byte container cause if known. Material pixel drift requires investigation.

### Host succeeds but cleanup readback is uncertain
Do not discard successful artifact automatically. Qualify artifact separately, record cleanup uncertainty, and verify project/host health in a fresh session before next mutation.

## Comparator / image

### Strict threshold-0 FAIL only at known small quantization scale
Retain strict FAIL diagnostically; classify using active acceptance. Do not repair byte identity.

### Mean/p99 low but localized >8/>32 region exists
Treat as material until localized; connected-region audit outranks global mean.

### ICC/profile differs
Do not silently normalize. Determine whether inputs share profile and whether candidate export omits/changes metadata. If pixels materially shift, S-CONFOUND until controlled; metadata-only unverified status stays explicit.

### Alpha differs
Material blocker unless capability policy explicitly rejects the behavior. Do not hide with RGB-only metrics.

## Verifier

### Verifier FAIL — evidence/state only
Separate Worker repairs evidence/state linkage; new fresh verifier. No production/host rerun unless affected.

### Verifier FAIL — offline code/test
Separate Worker applies bounded fix, runs focused + full offline checks; host rerun only if production/render behavior changed; new fresh verifier.

### Verifier FAIL — host proof stale/missing
Acquire fresh host evidence on same production candidate; new fresh verifier.

### Verifier FAIL — actual material semantic defect
Return to localize -> fixture -> hypotheses -> host evidence -> one bounded repair -> focused + full render -> new fresh verifier.

### Verifier BLOCKED because remote/ref is stale
Fresh API/`ls-remote`/explicit fetch; if recoverable, continue. S-REMOTE only after reasonable retries.

## State / closure

### Branch guard fails before main merge
Expected if canonical main has not advanced. Preserve branch proof. Request/use merge authority at canonical-promotion queue item; do not invalidate branch verifier PASS solely for this.

### Remote guard fails after authorized main merge
Fresh read main/state/candidate/evidence. Fix publish/state mismatch if reversible; rerun guard. S-REMOTE only if unresolved.

### Schema does not permit assumed terminal field
Do not invent schema. Fresh-read schema/Goal, choose legal terminal representation, validate.

# Retry budgets

- unchanged test/command failure: max 1 retry;
- same full Resolve route after crash/no-artifact: max 1 unchanged retry, then change diagnostic route;
- API/remote read mismatch: max 2 fresh reads using different mechanisms;
- verifier: unlimited new verifier attempts only when each follows a materially changed candidate/evidence state; never loop unchanged verifier.

# Stop codes

Return for human intervention only when safe autonomous alternatives are exhausted:

- `S-AUTHORITY`: merge/release/deploy/destructive/history/credential action lacks authority.
- `S-INPUT`: required immutable input/qualification is truly unavailable/unrecoverable.
- `S-HOST`: required actual Fusion proof unavailable after reasonable recovery routes.
- `S-CONFOUND`: material conclusion blocked by unresolved ICC/premult/transparentRGB/canvas/export confound and no autonomous control remains.
- `S-NONLOCALIZED`: material defect persists after reasonable diagnostics with no owner boundary.
- `S-CONTRADICTION`: independent material evidence remains contradictory after confound isolation/new discriminator.
- `S-REGRESSION`: bounded repair causes material regression and safe alternatives exhausted.
- `S-UNSUPPORTED`: requirement cannot be safely represented/declared through verified native/custom/bake/reject.
- `S-VERIFIER`: fresh verifier repeatedly fails/blocks after available bounded corrections.
- `S-REMOTE`: push/fetch/readback/guard mismatch unresolved by fresh remote recovery.

Do NOT stop for one test/fixture failure, rejected hypothesis, local ref absence, long context, safe task commit/PR update, Resolve route change, reproducible missing evidence, or known quantization-scale strict diff.

# Checkpoint policy

Update `PROGRAM_CLOSEOUT_STATE.json` after each phase boundary and any material route change. Chat checkpoint only on:
1. genuine human authority/input stop;
2. unexpected material production defect at P7 that requires product-level judgment;
3. branch-level final program closure;
4. canonical PROGRAM DONE.

Everything else belongs in durable repo evidence/state and execution continues.