# PSD2Fusion delegated agent operations

Scope: read this only when delegation or a persistent multi-agent loop materially helps the current Goal. General Codex behavior belongs to the user's global Codex instructions; this file contains only the PSD2Fusion-local delegation contract.

## Roles
A bounded one-shot task may run in one context.

When delegation helps:
- **Coordinator** owns the current Goal, acceptance, architecture authority, and next-Goal transition.
- **Worker** owns implementation/debug/verification for the assigned work package only.
- **Reviewer** is optional and should add an independent evidence path, not ceremony.

A Worker must not invent the next product Goal after completion.

## Luna use
Prefer Luna for bounded high-volume work when available, especially:
- repository localization / read-only prior-art comparison;
- adapting existing PSD/Fusion code;
- routine implementation and debugging;
- fixture generation;
- graph/serialization/layout work;
- focused checks and Resolve/Fusion host smoke.

Use stronger reasoning only when the current evidence leaves a material architecture/source-of-truth ambiguity, conflicting requirements, unresolved cross-layer diagnosis, weak critical acceptance oracle, or high-impact review disagreement.

Escalation is tactical: once the ambiguity is resolved, return routine execution to the Worker.

When model cost/routing matters, use authoritative session/runtime metadata where available; an agent name or self-description is not proof of the model that ran.

## Work package
Keep delegation compact:

```text
Task / Goal
Owned or writable scope
Starting references
Preserve / non-goals
Done / validation
Stop or escalation condition
Return schema
```

Do not forward the Coordinator transcript, old raw logs, or broad documentation that is not decision-relevant.

A read-only explorer returns paths/symbols/lines, relevant facts, uncertainty, and source refs rather than its transcript.

## PARITY-004 delegation constraint

When `PARITY-004` is active, delegate only the next unresolved gate from `.control/PARITY-004_TODO.md` and `docs/PARITY_004_HOST_PIXEL_GATE.md`.

Current gate order is:

```text
P4-08 host load/readback
-> P4-HOST-PIXEL micro renders
-> P4-09 real Fusion/reference baseline
-> smallest localized repair
```

P4-03 through P4-07 are preserved structural evidence. A Worker or Reviewer must not reopen them speculatively, start `PARITY-005`/`PARITY-006`, or launch a broad planner/compiler rewrite unless actual host/pixel evidence localizes the blocker there.

For host/pixel work, the return packet must distinguish at least:

```text
structural
host_loaded
pixel_verified
```

and include exact candidate commit, Resolve/Fusion version, relevant project/color/alpha settings, rendered artifact path/hash when pixels are claimed, comparator metrics, and the smallest localized blocker when failing.

A graph inspection or readback result is never sufficient to label `pixel_verified`.

## Evidence packet
Worker/reviewer return should normally contain:

```text
Goal / task
HEAD / workspace state when relevant
Changed files
Verified behavior
Checks / visual / host evidence
Remaining out-of-scope gaps
Exact blocker if any
Failure fingerprint + attempt count when relevant
Recommended next safe action
```

Self-report is not host evidence.

## Progress / no-progress
Stay on the current cheap execution path while evidence changes: checks begin passing, the failing set shrinks, the boundary localizes, a hypothesis is falsified, or the product visibly moves toward the target.

If essentially the same failure fingerprint/evidence state repeats twice without narrowing, change approach or request one tactical diagnostic pass. Do not spend indefinite cycles producing different prose around unchanged evidence.

## Parallel work
Parallel agents are allowed only for genuinely independent read scopes or explicitly partitioned write scopes.
Do not let multiple workers edit the same files unsynchronized or choose competing next Goals.

For `PARITY-004`, do not parallelize P4-08, the micro pixel gate, and P4-09 as independent implementation tracks because later interpretation depends on earlier host evidence. Read-only diagnostics may run in parallel if they cannot advance state or mutate the candidate graph.

## PSD2Fusion review targets
When independent review is useful, prioritize:
- Group / clipping semantic mistakes;
- alpha, pass-through, blend, coordinate or canvas errors;
- false-PASS fixtures;
- serialization/load assumptions not backed by Fusion/Resolve evidence;
- complexity that blocks the shortest path to a usable graph.

During the current host/pixel phase, review the smallest evidence boundary first: Loader/alpha/color contract, then local clipping math, then group/backdrop scope, then real-PSD-only semantics. Do not recommend a global rewrite before localizing the failing class.

Prefer reviewing exact diff/SHA + Goal + evidence before reading the implementer's narrative when practical.

## Durable learning
Project-only reusable failures belong in the smallest useful mechanical owner: fixture/test, validator, script, or Harness. Add prose here only when the delegation contract itself changes.