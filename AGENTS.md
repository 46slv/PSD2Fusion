# PSD2Fusion agent entrypoint

## Purpose

PSD2Fusion turns Photoshop PSD structure into a readable, editable DaVinci Resolve/Fusion graph. The active program is correct Photoshop compositing for blend modes, opacity, groups, and especially clipping, verified against deterministic fixtures and the real reference case.

## Authority

Use this order when facts conflict:

1. current user/Goal instruction;
2. `.control/current.json` for current task/status and the current repository HEAD;
3. current code, tests, `.control/CURRENT_GOAL.md`, and observed Photoshop/Resolve runtime evidence;
4. this `AGENTS.md` and more-specific nested instructions;
5. committed research/prior-art notes;
6. inference.

Do not treat chat history, memory, an uncommitted local note, or an agent completion message as repository authority.

## Mandatory opening

For non-trivial work:

1. read `.control/current.json`;
2. read `.control/CURRENT_GOAL.md`;
3. work only the `active_task_id`;
4. inspect current branch/HEAD, relevant code/tests, and committed evidence;
5. establish the current baseline or failure before editing.

When `active_task_id` is `PARITY-004`, also read `.control/PARITY-004_TODO.md` and `docs/PARITY_004_HOST_PIXEL_GATE.md` before changing compositor code or advancing work.

Read `docs/AGENT_OPERATIONS.md` only when delegation or a persistent loop materially helps. Do not load all research files by default.

## Protected invariants

- Keep raw PSD extraction, Semantic IR, Evaluation IR, Fusion lowering/layout, and host/reference verification separate.
- Do not confuse visual grouping with Photoshop compositing semantics.
- Treat clipping as a same-parent ordered compositing relation, not a per-layer mask shortcut.
- Preserve raw blend/opacity/clipping/group provenance even when the backend cannot render it.
- In strict parity work, never silently use Normal, 100% opacity, enabled visibility, unlabeled resize/color correction, or flattening.
- Prefer an explicit verified bake/reject over an editable but knowingly wrong approximation.
- Do not claim Photoshop pixel parity from parser structure, graph text, Resolve load success, or agent self-report.
- The real PSD, reference PNG, full-resolution renders, and per-layer exports must not be committed to this public repository.
- Material prior-art code reuse must be license-compatible and preserve attribution/provenance.

## PARITY-004 execution guard

While `PARITY-004` is active, P4-01 through P4-07 are a preserved structural candidate, not a completed pixel claim. Do not roll them back merely because host/pixel proof is pending.

Unless actual Fusion evidence localizes a blocker elsewhere, the remaining order is mandatory:

```text
P4-08 ordinary Fusion load/readback
-> P4-HOST-PIXEL deterministic micro renders
-> P4-09 real Fusion/reference baseline
-> smallest evidence-driven repair
-> rerun focused micro fixture and real comparison
```

Until that baseline exists:

- do not start `PARITY-005` or `PARITY-006`;
- do not mark `PARITY-004` done;
- do not treat structural/load evidence as `pixel_verified`;
- do not perform a broad Evaluation IR / Lowering Plan / compiler redesign merely because known architecture debt exists;
- do not fit the reference with threshold relaxation, grading, resize, blur, flattening, or whole-image correction.

Known architecture debts must remain visible: capability decisions do not yet drive backend selection before graph compilation, and asset materialization still needs a verified ICC/straight-premult/transparent-RGB contract. Use host/pixel evidence to determine whether either debt is causal. Before introducing multiple backends, custom operations, verified bake paths, or broad feature expansion, capability planning must be connected to lowering so strict mode cannot silently emit an unverified backend.

## Work and verification

- A Worker may submit the active task as `awaiting_verification`; it may not self-mark `done` or advance `active_task_id`.
- A fresh Verifier evaluates the Goal, exact candidate diff/commit, tests, and reproducible evidence, not the Worker's reasoning transcript.
- Prefer executable fixtures, validators, comparison metrics, and scripts over more prompt prose.
- Retry the same unchanged failure once at most; then change hypothesis/diagnostic or escalate.
- Preserve unrelated work and both read-only reference inputs.

Repository-level offline check:

```powershell
pwsh -NoProfile -File .\scripts\check.ps1
```

Host/reference checks are defined by the active task. Offline checks cannot substitute for a required Photoshop/Resolve run.
Before reporting `done`/`verification=pass`, publish commits and run the inspection-only remote completion guard after a fresh fetch/readback of `origin/main:.control/current.json`; offline `check.ps1` alone never proves canonical completion.

## Authority boundary

In-scope reversible repository edits and non-destructive validation are allowed. Do not overwrite the real PSD/reference, merge/release/deploy, change credentials, force-push shared history, or perform destructive/irreversible operations without explicit authority.

## Ownership map

- active task/status -> `.control/current.json`;
- active Goal, architecture, validation, Worker/Verifier rules -> `.control/CURRENT_GOAL.md`;
- active PARITY-004 queue -> `.control/PARITY-004_TODO.md`;
- active PARITY-004 host/pixel procedure -> `docs/PARITY_004_HOST_PIXEL_GATE.md`;
- historical FIRST_USABLE architecture -> root `ARCHITECTURE.md`;
- PSD/file-format evidence -> `docs/research/`;
- repeatable procedure -> tests/scripts/Harness;
- delegation procedure -> `docs/AGENT_OPERATIONS.md`.

Keep this file a map, not the project manual.