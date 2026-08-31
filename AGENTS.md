# PSD2Fusion agent entrypoint

## Mission
PSD2Fusion converts Photoshop PSD structure into a readable, editable DaVinci Resolve/Fusion node graph.
Prioritize the practical core: faithful layer compositing, PSD group structure that remains visually legible in Fusion, and Photoshop-style clipping relationships reconstructed as graph logic rather than flattened away.

## Source of truth
Use this precedence when facts conflict:
1. current user/task instruction;
2. current repository code, tests, fixtures, Git state, and observed Resolve/Fusion runtime behavior;
3. this `AGENTS.md` and any more-specific nested agent instructions;
4. repo documentation and historical notes;
5. inference.

Read `README.md` for project identity. For non-trivial implementation, debugging, validation, or multi-agent work, also read `docs/AGENT_OPERATIONS.md`. When the supervising/root model is Sol or another strong reasoning model, also read `docs/SOL_OPERATIONS.md` to bound checking, research, and architecture scope. Do not load every document preemptively.

## Product invariants
- Preserve PSD layer order, visibility, opacity, positioning, and supported blend semantics when they affect output.
- Treat a PSD group as both a semantic hierarchy and a visual organization boundary. Do not flatten a group merely to simplify implementation when an editable Fusion subgraph can preserve the intended result.
- Give each reconstructable group a clear graph boundary/output so the parent graph can consume the group as one compositing unit while the group remains inspectable.
- Reconstruct clipping relationships explicitly. Do not silently drop clipping layers or claim support when the visual/semantic result is unverified.
- Separate visual grouping from pixel-compositing semantics when Photoshop behavior such as pass-through requires it.
- Prefer a faithful raster fallback for unsupported Photoshop-only behavior over an editable but visually wrong approximation; make fallback visible in evidence/documentation.
- Never claim Photoshop parity from node creation alone. Semantic success requires executable, image, or Resolve/Fusion host evidence appropriate to the changed behavior.

## Architecture direction
Keep parsing, semantic representation, graph compilation, graph layout, and host integration separable. Avoid binding PSD parsing directly to Fusion serialization in ways that make group/clipping behavior hard to test independently.

When a boundary becomes non-trivial, create a small owner document or test/fixture rather than expanding this file into an implementation manual.

## Agent orchestration
Use delegation when it reduces solver-context pollution or gives independent evidence; do not spawn agents ceremonially.

- Coordinator/Supervisor owns the current Goal, acceptance criteria, architecture boundaries, and adjudication. It does not duplicate routine implementation already delegated.
- Prefer Luna workers for bounded repository reading, implementation, debugging, focused tests, fixture work, and host-test execution when available.
- Prefer low reasoning while verification is producing new evidence. Use Luna medium tactically when the same evidence boundary repeats without narrowing, then return routine execution to the cheaper worker after the ambiguity is resolved.
- Use stronger/Sol reasoning for material architecture ambiguity, conflicting requirements, weak acceptance oracles, unresolved cross-layer diagnosis, high-impact review disagreement, or irreversible/data-loss risk.
- A worker owns only its assigned Goal/work package. It must not invent the next product Goal after completion.
- Parallel workers are allowed only for genuinely independent read scopes or explicitly partitioned write scopes. Do not allow concurrent unsynchronized edits to the same files.
- When model routing matters, verify actual runtime/session metadata where available; do not treat an agent name or self-description as proof of the model that executed.

Detailed work-packet, evidence, retry, checkpoint, and review rules live in `docs/AGENT_OPERATIONS.md`.

## Harness and verification
Make the repository progressively easier for a lightweight worker to verify deterministically.

- Prefer one stable command/script for each repeated build/test/fixture/host-validation operation once the operation exists.
- Distinguish command success, static/build success, test success, Resolve/Fusion host success, and semantic Goal success.
- Every Done criterion should have an observable oracle and evidence identity where practical.
- Prefer fixtures for PSD semantics: ordinary layers, nested groups, clipping, group+clipping combinations, pass-through behavior, and regression cases discovered during implementation.
- For visual fidelity, compare against an authoritative expected render/composite when practical; do not use worker self-report as the oracle.
- Host-only Resolve/Fusion behavior must be reported as host-unverified until actually exercised in the target host.
- Before repeating a write or external side effect, determine whether the previous attempt may already have succeeded. Never blind-retry an ambiguous write.
- Add timeouts/cleanup around subprocess or host automation that can hang.

If a repeated failure can be prevented by a test, fixture, validator, wrapper, script, runtime probe, or clearer failure envelope, improve that mechanical surface before adding another permanent instruction paragraph.

## Work discipline
Default loop: `OBSERVE -> LOCATE -> ACT -> VERIFY -> SELF-REVIEW -> CHECKPOINT/HANDOFF`.

- Inspect the nearest implementation and tests before editing.
- Keep changes coherent and bounded to the current Goal; avoid speculative broad rewrites.
- Preserve unrelated dirty work.
- Prefer task branches/worktrees for non-trivial or parallel changes.
- Coherent commits, pushes, and draft PRs are allowed when useful for handoff/review. Do not force-push shared history.
- Do not merge, release, publish, deploy, change credentials, or perform destructive/irreversible operations unless explicitly authorized.

## GitHub Actions
Do not add automatic/scheduled CI merely for convenience. If `.github/workflows/**` is created or changed, the task owns CI closure: check for over-broad triggers, duplicate/self-triggering runs, unbounded retry, missing timeout, and missing concurrency control where applicable, then inspect the real remote run until the workflow safely converges before calling the task Done.

## Completion evidence
A compact completion/handoff should contain:
- Goal/work package;
- current HEAD/state when relevant;
- changed files/surface;
- verified behavior;
- tests/fixtures/runtime/host evidence;
- remaining out-of-scope gaps;
- exact blocker if any;
- failure fingerprint/attempt count when retrying.

Do not forward raw worker transcripts when a compact evidence packet is sufficient.

## Learning closeout
For non-trivial implementation, command, CI/build, or debugging work, perform a learning check before reporting Done:
- extract any newly verified reusable failure guard, host/API contract, known-good validation pattern, or repeated procedure;
- place project-only truth in this repo's tests/docs/scripts/fixtures/harness;
- mechanize repeated failures where practical;
- do not accumulate raw logs, one-off typos, secrets, or duplicated rules.

If there is no reusable delta, leave the repository unchanged rather than manufacturing documentation.
