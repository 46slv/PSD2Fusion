# PSD2Fusion program closeout runbook

Status: ACTIVE long-run roadmap from PARITY-006 verifier PASS to canonical program completion.
Model target: Muse 1.3 autonomous worker/coordinator with durable repo-local recovery.

This file is a parent roadmap. Task-specific `AGENTS.md`, `.control/current.json`, `.control/CURRENT_GOAL.md`, PARITY-006/007 runbooks, validation/compositing contracts, and fresh live Git state remain higher authority for task details.

## Mission

Finish the compositing-parity program safely from the current PARITY-006 closure checkpoint through:

1. canonical PARITY-006 done/pass on `main`;
2. fresh independent PARITY-007 closeout from canonical main;
3. final program terminal state on canonical main;
4. final remote readback/guard proof.

Do not reopen already-closed PARITY-004 Linear Dodge or PARITY-005 `clbl=false` investigations unless a fresh independent verifier discovers a real material regression.

## Long-run operating rule for Muse 1.3

Treat repository state as memory. Before each phase/context restart, fresh-read:
- correct repo/cwd;
- current branch/exact HEAD;
- `origin/main` and active task branch via remote/API, not local refs alone;
- `AGENTS.md`;
- `.control/current.json`;
- this runbook + `.control/PROGRAM_CLOSEOUT_QUEUE.json`;
- active task runbook/queue;
- relevant evidence/verifier.

When context becomes large, do not stop. Write a durable checkpoint (queue/evidence/HEAD), commit/push on the task branch, discard old reasoning, fresh-read the durable state, and continue.

Do not ask for per-step confirmation while a ready reversible queue item exists and no stop code is active.

## Phase A — Canonical PARITY-006 closure

### A1 Fresh live-state recovery
Confirm remote P6 branch/main/PR/state/evidence. Local ref absence is not remote absence; use `gh api`, `git ls-remote`, and explicit refspec fetch when needed.

### A2 Verifier linkage/drift audit
Confirm the fresh P6 verifier PASS is tied to the exact production candidate. Any later branch commits must be control/evidence-only or otherwise re-verified. Confirm no production drift invalidates the successful actual Fusion render.

### A3 Branch state transition
Only after verifier PASS:
- PARITY-006 -> `done/pass`;
- advance active task according to Goal/schema;
- PARITY-007 -> `ready` only if dependencies permit;
- add verifier/evidence linkage;
- state/schema validation + `scripts/check.ps1` PASS.

### A4 Publish/readback/branch guard
Push task branch. Fresh fetch/readback. Confirm branch state/evidence/candidate reachability.

### A5 Canonical main promotion
Merge requires explicit authority under AGENTS. If authority exists and fresh checks show `behind=0`, no divergence, expected HEAD, and safe fast-forward path, use `--ff-only`; no force, rewrite, branch deletion, release, or deploy. After merge: fresh `origin/main` readback and PARITY-006 remote completion guard PASS.

PARITY-007 must not start before canonical main shows PARITY-006 done/pass and P7 ready.

## Phase B — PARITY-007 independent closeout

### B1 Bootstrap from canonical main
Create `codex/parity-007` from exact canonical main. Add/update `.control/PARITY-007_RUNBOOK.md` and `.control/PARITY-007_QUEUE.json`. Mark branch-level P7 in_progress only according to Worker/state rules.

### B2 Fresh clean verification environment
Use a fresh clean checkout/worktree, not stale P6 working state. No old generated comp/artifact may silently substitute for required final fresh proof.

### B3 Source/state/evidence integrity audit
Audit all P1-P6 done/pass claims, evidence paths, commit reachability, privacy, input provenance, current contracts, unsupported/rejected semantics, and state-transition consistency. Do not rerun every historical experiment unless needed; verify the proof chain is intact.

### B4 Full offline regression
Fresh run of `scripts/check.ps1`, all tests/static checks, parser/evaluation/capability/clipping/group/Linear-Dodge/`clbl=false` fail-closed/comparator false-PASS coverage. Fix only real regressions; do not reopen closed semantic research without evidence.

### B5 Fresh real PSD regeneration
Regenerate `D:\Downloads\a.psd` to a fresh ignored temp path from exact P7 candidate. Record input hash, layers/groups/chains/members/tool count/warnings/comp hash, float32 materialization and forbidden-tool audit. Historical counts are expectations, not fitting targets.

### B6 Final fresh actual Fusion proof
Use only dedicated Resolve project exact name `PSD2Fusion`. Fresh host sanity before mutation. Use disposable comp. If needed use trivial sanity -> representative smoke -> full graph. Record Resolve Studio version/PID/project/comp/tool count/frame range/Saver settings/result/timing/artifact hash/endpoint health/cleanup/save status. Past artifacts may be comparison evidence but not the sole final fresh proof.

### B7 Final real-reference comparison
Fresh Fusion render vs qualified `D:\Downloads\20260812.png` with strict threshold 0. Record dimensions/channels/profile, RGB max/mean/p99, alpha, >1/>2/>8/>16/>32, bbox/coherent components. Threshold relaxation/reference fitting is prohibited.

Final acceptance requires no material-scale/coherent visible residual; alpha/structure/semantic scope correct; remaining difference acceptance-nonblocking quantization class only. Strict-0 may remain diagnostic FAIL.

### B8 Final semantic/capability audit
Independently audit:
- unknown/unsupported operations never silently Normal/default;
- strict `clbl=false` fail-closed and compatibility behavior explicit;
- group isolation/Pass Through/nesting boundaries;
- clipping fixed matte/order/base/member opacity/modes;
- non-Normal straight/premult boundaries;
- Linear Dodge verified behavior;
- capability decisions actually gate lowering;
- unsupported/bake/reject provenance explicit;
- float32 preserved; no 8-bit identity repair; no real-layer-ID special cases.

### B9 False-PASS/privacy/complexity audit
Check wrong dimensions/alpha/profile/crop/premult fringe/localized outliers/stale artifact/oracle mirrors SUT/host-load mistaken for pixel proof/threshold relaxation. Ensure PSD/reference/full renders/private artifacts are not tracked. Ensure no dead silent legacy path or duplicate verification standard undermines maintainability.

### B10 Independent verdict
A fresh independent Verifier returns exactly PASS/FAIL/BLOCKED. Verifier does not self-repair. PASS requires B2-B9 satisfactory, fresh actual Fusion proof, no material blocker, no unresolved false-PASS path.

### B11 Correction loop
If FAIL/BLOCKED, classify as evidence-only, test/infra, host, state/remote, confound, or actual production semantic defect. A separate Worker performs the smallest bounded correction. Then launch a new fresh verifier. Do not repeat an unchanged failed hypothesis more than once.

## Phase C — Program terminal closure

### C1 P7 state transition
Only after fresh P7 PASS, fresh-read schema/Goal and apply the defined terminal state. Do not invent `active_task_id=null` or other terminal fields without schema/contract support. Set P7 done/pass and program status done only as allowed. Update evidence linkage. Run state validator/checks.

### C2 Publish/readback
Publish P7 branch, fresh remote readback, verify candidate/verifier/evidence reachability.

### C3 Canonical final promotion
Requires explicit merge authority. Fresh-check main unchanged/divergence/behind=0/fast-forward. `--ff-only`, no branch deletion/force/rewrite. Fresh fetch/readback after merge.

### C4 Final program proof
Program is COMPLETE only when canonical `origin/main` proves:
- P1-P7 done/pass as required;
- valid terminal program state;
- final fresh verifier PASS;
- final fresh actual Fusion artifact qualified;
- real reference comparison accepted under active policy;
- no material blocker/unresolved false-PASS;
- remote completion guard PASS;
- `scripts/check.ps1` PASS;
- repo clean and no private-artifact leakage.

## Stop codes

Use only these as reasons to return for human intervention:

- `S-AUTHORITY`: required merge/release/deploy/destructive/history/credential action lacks explicit authority.
- `S-INPUT`: required PSD/reference/fixture hash/qualification is missing or unrecoverable.
- `S-HOST`: actual Fusion proof cannot be acquired safely through multiple reasonable routes.
- `S-CONFOUND`: ICC/premult/transparent RGB/canvas/export etc. prevents a material conclusion and cannot be autonomously controlled.
- `S-NONLOCALIZED`: a real material defect persists after reasonable diagnostics without an owner boundary.
- `S-CONTRADICTION`: independent material evidence remains contradictory after confound isolation.
- `S-REGRESSION`: bounded repair causes material regression and safe bounded alternatives are exhausted.
- `S-UNSUPPORTED`: required semantics cannot be safely represented/declared using verified native/custom/bake/reject.
- `S-VERIFIER`: fresh verifier repeatedly FAIL/BLOCKED after available bounded corrections.
- `S-REMOTE`: push/fetch/readback/guard mismatch cannot be resolved by reasonable retries/fresh remote reads.

Do NOT stop merely because: one test/fixture fails, one hypothesis is rejected, local ref is missing/stale, context is long, a safe task-branch commit/PR update is needed, Resolve route needs changing, another bounded diagnostic is needed, or strict comparator reports known quantization-scale residuals.

## Completion/checkpoint policy

Continue until one of:
1. human authority/input is genuinely required by a stop code;
2. unexpected material production defect is discovered at P7;
3. branch-level P7/program closure is reached;
4. canonical PROGRAM DONE is proven.

Minor progress belongs in repo evidence/queue, not chat.
