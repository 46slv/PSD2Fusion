# PSD2Fusion agent entrypoint

## Purpose
PSD2Fusion turns Photoshop PSD structure into a readable, editable DaVinci Resolve/Fusion graph.
The practical core is correct layer compositing, readable PSD group structure, and Photoshop-style clipping reconstructed as graph logic instead of being silently flattened or dropped.

## Authority
Use this order when facts conflict:
1. current user / Goal instruction;
2. current repository code, tests, committed design authority, and observed Resolve/Fusion runtime evidence;
3. this `AGENTS.md` and any more-specific nested instructions;
4. committed research / prior-art notes;
5. inference.

Do not treat chat history or an uncommitted local note as repository authority.

## Read conditionally
- `docs/AGENT_OPERATIONS.md` — only when delegation, multi-agent work, or a long-running worker loop is useful.
- `docs/SOL_OPERATIONS.md` — only for an explicit architecture-reset / first-usable implementation phase; it is project-specific development policy, not a requirement to redesign architecture during ordinary implementation.

Do not load every mapped document for every task.

## Protected invariants
- Keep PSD semantic structure separate from Fusion serialization/layout so one does not become the accidental source of truth for the other.
- Do not confuse visual grouping with Photoshop compositing semantics; Group/Underlay organization must not silently change pixel behavior.
- Reconstruct clipping relationships explicitly when supported; never omit a clipping member while claiming fidelity.
- Prefer an explicit raster/bake fallback for unsupported semantics over an editable but knowingly wrong approximation.
- Do not claim Photoshop or Resolve parity without evidence appropriate to that claim; host behavior requires actual Resolve/Fusion host evidence.
- When materially copying prior-art code, use only license-compatible sources and preserve required attribution/provenance.

## Work rules
- For ordinary implementation, treat the committed architecture as a constraint. Understand the touched boundary, then implement; do not reopen architecture merely because a cleaner system is imaginable.
- For an explicitly authorized architecture redesign, reason deeply about the expensive-to-reverse boundaries, persist the resulting design, then stop redesigning and move to implementation.
- Prefer adapting proven prior-art mechanics over rewriting solved plumbing for originality.
- Keep the current Goal bounded and preserve unrelated work.
- Add a new abstraction only when current required behavior or observed evidence needs it.

## Validation entrypoints
Until dedicated scripts exist, use the smallest executable check that proves the changed boundary.

For FIRST_USABLE work, the minimum host smoke is: produce the intended Fusion artifact, have Resolve/Fusion recognize or load it, and execute the primary path once without immediate destructive failure.

Run broader regression, compatibility, packaging, performance, or release validation only when the current Goal, changed risk surface, or release policy requires it. Do not encode “run everything after every edit” as the default.

## Authority boundary
In-scope reversible repository edits and non-destructive validation are allowed.
Do not merge/release/publish, change credentials, force-push shared history, or perform destructive/irreversible operations without explicit authority.

## Ownership map
- detailed architecture / rationale -> architecture docs / ADRs created for that purpose;
- current objective and stopping condition -> current Goal / task prompt;
- repeated deterministic procedure -> test / script / Harness;
- delegation procedure -> `docs/AGENT_OPERATIONS.md`;
- project-specific first-usable implementation posture -> `docs/SOL_OPERATIONS.md`.

Keep this file a map. Do not grow it into the project manual.