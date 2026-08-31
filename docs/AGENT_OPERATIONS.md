# PSD2Fusion Codex / Agent Operations

This document owns the repo-local operating procedure for delegated Codex work. `AGENTS.md` stays a compact map; task-specific Goals stay in the task/Goal surface rather than here.

## 1. Default topology

For a bounded one-shot task, one agent may execute directly.

For non-trivial work where delegation helps:

`Coordinator/Supervisor -> bounded Work Package -> Luna Worker -> deterministic verification -> Evidence Packet -> Coordinator`

The Coordinator may request an independent reviewer or stronger adjudicator only when it changes risk-adjusted confidence.

For development that intentionally continues across multiple Goals, keep Execution and Goal-transition responsibility in separate contexts:
- Execution Worker: implement/repair/verify the current Goal only.
- Coordinator: inspect evidence and repo authority, then choose the next single Goal. It does not duplicate implementation.

## 2. Work Package contract

A delegated package should contain only decision-relevant information:

```text
Task / Goal
Owned or target scope
Starting references
Required behavior / invariants
Non-goals
Acceptance / validation
Stop or escalation condition
Return schema
```

Do not send the full Supervisor transcript, old debug history, unrelated repository documentation, or raw logs already summarized.

A read-only explorer should return paths, symbols/lines, relevance, and uncertainty—not its entire exploration transcript.

## 3. Luna-first execution policy

Use Luna for high-volume bounded work when available:
- repository localization and targeted reading;
- clear-contract implementation;
- reproducible bugfixes;
- PSD fixture creation and semantic tests;
- graph/compiler/layout implementation;
- focused regression tests;
- Resolve/Fusion host validation when the environment is available;
- mechanical refactors and docs tied to verified behavior.

Prefer low reasoning while each cycle produces meaningful evidence. A slow cycle is acceptable when the failing boundary is narrowing or verified behavior is accumulating.

Escalate low -> medium when two semantic cycles reach essentially the same failure fingerprint/evidence state without narrowing, or when the next edit would otherwise become a speculative broad rewrite. Medium should return a changed hypothesis, bounded strategy, or oracle improvement, then hand execution back to low where possible.

Escalate beyond Luna only for a hard boundary such as:
- materially ambiguous architecture/source of truth;
- conflicting requirements;
- unresolved cross-layer causal diagnosis after changed approaches;
- weak/ambiguous acceptance oracle on a critical change;
- high-impact independent review disagreement;
- security, data-loss, irreversible migration, credential, or authority risk.

Escalation is tactical, not sticky.

## 4. Worker cycle

Within one Goal, use an evidence-driven cycle:

`OBSERVE -> choose one current hypothesis/boundary -> ACT -> VERIFY -> CHECKPOINT -> continue/replan`

A cycle may include a coherent multi-file change. The bound is one testable hypothesis or implementation slice, not one command or one line.

Progress means evidence changed, for example:
- a new check passes;
- the failing set shrinks;
- the failing location becomes more precise;
- a hypothesis is falsified with new evidence;
- output moves measurably toward the expected composite;
- regression checks remain green after a meaningful patch.

Different prose with the same failure fingerprint is not progress.

No-progress response:
1. first repeat: force a changed observation/hypothesis;
2. second unchanged repeat: change tool/approach or use Luna medium;
3. continued unchanged evidence: Coordinator/stronger diagnostic escalation or alternate critical path;
4. never burn indefinite cycles on unchanged evidence.

## 5. Verification hierarchy

Prefer evidence in this order when applicable:
1. executable acceptance/regression test;
2. Resolve/Fusion host/runtime observation;
3. authoritative image/composite comparison;
4. parser/compiler/layout fixture assertions;
5. type/static/lint/build checks;
6. diff inspection;
7. agent self-report.

Self-report cannot promote a Host-not-run state to Host PASS.

For PSD2Fusion, separate at least these semantic layers in tests as implementation appears:
- PSD semantic extraction;
- group hierarchy and nesting;
- layer order/visibility/opacity/position;
- clipping base/member relationships;
- blend/group pass-through behavior;
- graph topology/serialization;
- readable node layout as a deterministic structural contract where feasible;
- rendered/composited visual fidelity;
- Resolve/Fusion import/runtime behavior.

## 6. Failure envelope

Normalize meaningful failures before handing them back to a lightweight worker:

```text
check_id
status = FAIL | INCONCLUSIVE | TRANSIENT
failure_class
target/location
expected
observed
evidence_refs
retry_safe
admissible_next_actions[]
```

Useful failure classes include:
- SYNTAX_BUILD
- TEST_ASSERTION
- RUNTIME_BEHAVIOR
- CONTRACT_SCHEMA
- STATE_IDENTITY
- TIMEOUT_HANG
- ENVIRONMENT_DEPENDENCY
- PERMISSION_AUTHORITY
- REGRESSION
- UNKNOWN_SEMANTIC

Do not fabricate a location or solution when evidence cannot establish it.

## 7. Checkpoint / resume

Checkpoint after meaningful verified progress, before context rotation/escalation, and around risky host operations when practical.

Keep only cognition-critical state:
- Goal and Done checks;
- current HEAD/worktree/dirty state;
- verified completed behavior;
- current failing check/fingerprint;
- last meaningful hypothesis and negative evidence;
- changed files;
- in-flight side effect state: none / known-success / known-failure / unknown;
- next safe action;
- model/reasoning tier and escalation history when relevant.

Resume by reading current repo state first, then re-run the smallest validating check and reconcile the checkpoint against reality. Do not replay a long transcript as state.

## 8. Independent review

Use independent review for changes where an extra evidence path is useful. The reviewer receives Goal/acceptance, exact diff/SHA, relevant contracts, and test/runtime evidence—not implementer reasoning.

Prioritize review for:
- unmet behavior/acceptance;
- false-PASS tests or weak fixtures;
- clipping/group semantic errors;
- pass-through/blend/alpha boundary errors;
- coordinate/canvas mistakes;
- regression/compatibility;
- unnecessary complexity that makes future graph compilation harder to verify.

When practical, review the raw diff/evidence before reading the implementer's explanatory handoff to reduce anchoring.

## 9. Harness growth policy

Do not prebuild a giant custom harness. Add only demonstrated missing capabilities, in roughly this priority:
1. deterministic test/fixture entrypoint;
2. structured failure output;
3. visual/reference comparison entrypoint;
4. checkpoint/run identity for long tasks;
5. timeout/process cleanup;
6. focused test selection;
7. diff/dirty-state capture;
8. Resolve/Fusion host probe/automation;
9. reviewer hook and metrics only when they pay for themselves.

Repeated manual operation should migrate toward the smallest deterministic owner: test before script, script before Skill, Skill before permanent prompt prose.

## 10. PSD2Fusion-specific harness expectations

As the implementation matures, fixtures should make it cheap to answer these questions without opening Photoshop manually every cycle:
- Did the parser preserve the semantic tree?
- Did a nested group compile into the intended subgraph boundary?
- Did clipping preserve base alpha semantics?
- Did pass-through vs isolated group behavior choose the correct graph strategy?
- Did layout remain readable without changing compositing semantics?
- Does serialization round-trip/load in Fusion?
- Does the Resolve/Fusion output match the authoritative expected composite within the chosen comparison tolerance?

Use synthetic minimal fixtures for isolated rules and a small curated set of real-world PSDs for integration regression. Do not rely only on large real-world PSDs because they make failures hard to localize.

## 11. Git and side-effect safety

- Prefer one task/work package per branch/worktree when edits are substantial or concurrent.
- Explicitly partition write ownership before parallel work.
- Inspect current remote/local state before retrying a push, PR creation, or host mutation after ambiguous failure.
- Never force-push shared history as a recovery shortcut.
- Merge/release/deploy/publication/credential/destructive operations require explicit authority.

For GitHub Actions changes, verify trigger scope, concurrency, timeout, retry/self-trigger behavior, then inspect the actual remote run through safe convergence before Done.

## 12. Evidence Packet

Worker/reviewer return should normally be compact:

```text
Goal / task
HEAD / workspace state
Changed files
Verified behavior
Tests / fixtures / visual / host evidence
Remaining out-of-scope gaps
Exact blocker, if any
Failure fingerprint + attempt count, if relevant
Recommended next safe action
```

Do not treat completion prose as completion evidence.

## 13. Learning closeout

At the end of non-trivial work, decide whether a verified reusable delta was discovered.

If yes, prefer this ownership order:
1. project behavior/invariant -> test/fixture/code;
2. deterministic failure prevention -> validator/script/harness;
3. repeated procedure -> Skill/script;
4. architecture rationale -> repo docs;
5. durable behavioral routing -> `AGENTS.md` only when truly repo-wide.

A repeated failure after a guard already exists is a guard failure: strengthen the mechanical guard instead of adding another warning paragraph.

Do not store raw transcripts/logs, secrets, one-off typos, or volatile current-task state as durable agent policy.
