# Muse 1.3 long-run orchestration pattern

Purpose: reusable instruction pattern for letting Muse 1.3 run a repository task for a long time with minimal human interruption, durable recovery, parallel investigation, explicit stop conditions, and fresh-verifier boundaries.

This is a design note, not a task-specific source of truth. Task-local `AGENTS.md`, canonical state, Goal, RUNBOOK, QUEUE, live Git/GitHub state, and qualified runtime evidence remain authoritative.

## Core idea

Do not drive Muse with a sequence of short chat prompts. Put the execution contract into the repository, then tell Muse to fresh-read and consume it until a genuine stop condition or completion.

Preferred control-plane files:

- `RUNBOOK.md` — policies, gates, authority, recovery playbooks;
- `QUEUE.json` — machine-readable work items, dependencies, lanes, done criteria;
- `STATE.json` — mutable current position, completed/blocked items, lane ownership, active stop code;
- evidence directories — durable facts/artifacts/metrics;
- Git commits/remote refs — durable checkpoints.

Treat the repository as long-term memory. Chat context is disposable.

## First write the remaining-work map

Before asking Muse to continue, write the remaining work from the current checkpoint to the final intended outcome.

Good queue items contain:

- stable ID;
- phase;
- owner/lane;
- dependencies;
- action;
- `done_when` conditions;
- `on_fail` recovery route;
- optional `parallel_group`;
- optional stop condition.

Prefer an end-to-end queue over repeated "do the next thing" prompts.

Example progression:

`fresh state -> evidence audit -> implementation/host proof -> fresh verifier -> state transition -> publish/readback -> canonical promotion -> next task -> final verifier -> terminal state`

## Muse orchestration model

Assume Muse can orchestrate multiple workers/contexts.

Recommended lanes:

### Coordinator

Single shared writer. Owns:

- queue/state transitions;
- Git commit/push/PR updates;
- production edits;
- conflict resolution;
- promotion/stop decisions;
- final synthesis.

### Audit worker

Read-only or evidence-only:

- repository/Git/state/evidence integrity;
- provenance/reachability;
- privacy and stale-state detection.

### Host/experiment worker

Temp-only plus evidence summaries:

- runtime/host experiments;
- artifact hashes and metrics;
- route/stability diagnostics.

### Referee worker

Independent critic:

- false-PASS checks;
- semantic/capability/confound audit;
- challenge of promotion/acceptance claims.

### Fresh verifier

A new context/session. It:

- reads live repo/evidence/artifacts;
- returns PASS/FAIL/BLOCKED;
- does not repair its own candidate.

If parallelism is unavailable, run these lanes sequentially in independent fresh contexts. Lack of parallelism is not a stop condition.

## Shared-write rule

Only the Coordinator writes shared production/control files unless it explicitly delegates one disjoint path set to exactly one worker.

Never let parallel workers edit the same production file or canonical state concurrently.

## Fresh-read opening sequence

At every long-run start, context restart, worker handoff, or suspicious state mismatch:

1. enter/confirm the correct repository;
2. read `git status`, branch, exact HEAD;
3. fresh-read `origin/main` and task branch;
4. verify remote refs via API / `git ls-remote` when local refs may be stale;
5. read `AGENTS.md`, canonical state, Goal, RUNBOOK, QUEUE, STATE, relevant evidence;
6. reconcile mutable STATE against live Git before trusting it;
7. continue the next ready item.

Do not treat chat history, local-only summaries, or stale refs as source of truth.

## Context rollover

Long context is expected.

When context becomes large:

1. update STATE;
2. write/commit durable evidence;
3. record exact HEAD and next ready item;
4. push the checkpoint;
5. discard old reasoning/context;
6. fresh-read the repository and continue.

Context size by itself is never a reason to ask the user what to do next.

## Continue-without-human rule

Muse should continue automatically when:

- the next queue item is ready;
- the action is reversible/read-only/temp-only/task-branch scoped;
- inputs are available;
- there is an executable test/metric/artifact to judge the result;
- no genuine stop code is active.

Safe autonomous actions normally include:

- read/search;
- diagnostics;
- temp fixtures;
- tests;
- runtime/host validation;
- task-branch edits;
- evidence/decision records;
- commits/pushes;
- Draft PR updates;
- queue/state updates.

Do not ask for confirmation at every small step.

## Retry budget

Retry the same unchanged failure at most once.

If it repeats, change at least one of:

- hypothesis;
- diagnostic;
- fixture;
- route;
- context/environment.

Never loop the same command/failure indefinitely.

## If-this-then-that recovery playbook

Define these before execution so ordinary problems do not become unnecessary human stops.

### Wrong repository / cwd

Switch to the expected repository and rerun the opening sequence.

### Local task ref missing

Query remote API / `git ls-remote`, explicit-fetch the ref, then continue. Missing local ref is not remote absence.

### Unrelated dirty tree

Preserve it. Use a fresh worktree or checkout at the intended exact commit.

### Main advanced

Fresh compare first. Integrate non-destructively if appropriate, then rerun only the proof affected by the new main. Do not force-rewrite.

### Push blocked by author/privacy rule

For unpushed commits, use the repository's established noreply identity / reset-author pattern without changing global configuration.

### Single deterministic test failure

Retry once. If reproducible, localize the smallest cause, fix boundedly, rerun affected tests and then the required full check.

### Evidence missing but reproducible

Regenerate it from qualified inputs and exact candidate. Record the new evidence as superseding the stale/missing one.

### Runtime/host absent

Reconnect/relaunch when safe, verify exact expected project/environment, run a sanity check before a full workload.

### Runtime/host crash

Record the incident. Retry the unchanged full route at most once; then change route and classify size/node/settings/memory/lifecycle causes. Do not call a host crash a semantic/pixel failure.

### Artifact hash changed

Recompute pixels/metadata/metrics. Hash change alone is not automatically a material regression.

### Strict comparator only shows known tiny quantization residual

Keep the strict failure as diagnostic evidence. Do not add byte-identity repair if acceptance says the difference is non-material.

### Verifier evidence/state failure

A separate Worker repairs evidence/state only. Then launch a new fresh verifier.

### Verifier code failure

A separate Worker applies the smallest bounded fix and affected regression. Then launch a new fresh verifier.

### Verifier material/semantic failure

`localize -> fixture -> hypotheses -> host evidence -> one bounded repair -> full regression -> new fresh verifier`.

### Pre-merge remote guard failure

If branch proof is valid but main is not yet promoted, this can be expected. Preserve branch PASS and wait only for the authority boundary.

### Post-merge guard failure

Fresh-read main/state/evidence. Repair reversible publish/state mismatch, rerun guard, escalate only if reasonable recovery fails.

## Stop codes

Use a small explicit set. A stop means Muse has no safe autonomous route left.

- `S-AUTHORITY` — merge/release/deploy/destructive/history/credential action requires explicit authority;
- `S-INPUT` — required input/hash/qualification is missing and not recoverable;
- `S-HOST` — required runtime proof cannot be acquired safely through reasonable routes;
- `S-CONFOUND` — a confound prevents a material conclusion and cannot be autonomously controlled;
- `S-NONLOCALIZED` — a real material defect persists but reasonable diagnostics cannot identify an owner boundary;
- `S-CONTRADICTION` — independent material evidence remains contradictory after confound isolation;
- `S-REGRESSION` — bounded repair creates a material regression and safe alternatives are exhausted;
- `S-UNSUPPORTED` — required semantics cannot be safely represented/declared with available verified paths;
- `S-VERIFIER` — repeated fresh verifier FAIL/BLOCKED after available bounded corrections;
- `S-REMOTE` — push/fetch/readback/guard mismatch cannot be resolved by reasonable retries.

## Things that are not stop conditions

Do not stop merely because:

- one test fails;
- one fixture fails;
- one hypothesis is rejected;
- local ref is missing;
- context is long;
- a safe commit is required;
- a Draft PR needs updating;
- runtime route must change;
- a temp artifact must be created;
- another bounded diagnostic is needed;
- a strict comparator reports known non-material quantization noise;
- verifier failed but there is a clear bounded correction route.

## Evidence ladder

Prefer:

`fact -> hypothesis -> discriminating experiment -> measured evidence -> decision -> bounded implementation -> focused regression -> full regression -> fresh verifier`

Do not promote a semantic/production conclusion directly from convenience, same-named host operations, or a single ambiguous fixture.

## Production-edit gate

Before production edits, require:

- reproducible target/failure;
- identified owner/boundary;
- competing hypotheses narrowed by evidence;
- no reference fitting;
- understood blast radius;
- independent referee check against false-PASS.

Change one boundary at a time.

## Verifier discipline

A Worker may prepare and submit a candidate. A fresh Verifier evaluates it.

The Verifier:

- does not rely on the Worker's reasoning transcript;
- does not repair its own candidate;
- reports PASS/FAIL/BLOCKED;
- names exact candidate/evidence/environment;
- checks false-PASS risks.

After a verifier failure, correction is performed by a separate Worker, followed by a new fresh verifier.

## Merge / authority boundary

Task-branch work may be autonomous. Main promotion should require explicit authority unless the user has granted standing bounded merge authority.

A useful bounded standing authority is:

> When fresh Verifier PASS, branch behind=0, no main divergence, expected HEAD/state/evidence match, and fast-forward is possible, the Coordinator may merge to main using fast-forward only. It must then fresh-read remote state and run the completion guard. Force-push, history rewrite, branch deletion, release, and deploy remain prohibited.

## Checkpoint policy

Do not send minor progress to chat.

Return to the user primarily when:

1. genuine human authority/input is required;
2. an unexpected material product/architecture decision needs judgment;
3. branch-level final closure is reached;
4. canonical/program DONE is proven.

Everything else belongs in repo evidence and mutable STATE.

## Minimal launcher prompt

Once the control plane exists, the chat prompt can stay short:

```text
Use Muse 1.3 as an autonomous orchestrator.
Fresh-read the live repository and GitHub remote, then read AGENTS.md, canonical state, RUNBOOK, QUEUE, STATE, and active-task evidence.
Reconcile STATE against live Git and execute ready queue items until completion or a genuine documented stop code.
Use Coordinator/Audit/Host/Referee lanes and a fresh independent Verifier; parallelize declared parallel groups when available.
Apply the runbook recovery route before escalating an ordinary failure to a stop.
Update durable STATE/evidence before context rollover and continue from the repository instead of asking for per-step confirmation.
Do not force-push, rewrite history, delete branches, release, or deploy unless separately authorized.
```

## Design principle

The intended behavior is not:

`problem -> stop -> ask human`

but:

`problem -> classify -> recovery route -> evidence -> next ready action`

Human intervention is reserved for genuine authority, irrecoverable inputs/runtime, unresolved material contradictions, or final product-level judgment.
