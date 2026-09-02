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

## Authority boundary

In-scope reversible repository edits and non-destructive validation are allowed. Do not overwrite the real PSD/reference, merge/release/deploy, change credentials, force-push shared history, or perform destructive/irreversible operations without explicit authority.

## Ownership map

- active task/status -> `.control/current.json`;
- active Goal, architecture, validation, Worker/Verifier rules -> `.control/CURRENT_GOAL.md`;
- historical FIRST_USABLE architecture -> root `ARCHITECTURE.md`;
- PSD/file-format evidence -> `docs/research/`;
- repeatable procedure -> tests/scripts/Harness;
- delegation procedure -> `docs/AGENT_OPERATIONS.md`.

Keep this file a map, not the project manual.
