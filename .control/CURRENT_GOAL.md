# PSD2Fusion current Goal — PSD compositing parity

Status: ACTIVE  
Program: `PSD2FUSION-COMPOSITING-PARITY`  
Canonical state: `.control/current.json`

A fresh Codex or lower-reasoning coding agent must be able to continue from this repository without chat history.

## Objective

Reproduce PSD-defined blend modes, overall opacity, group scope, and especially clipping semantics in an inspectable Fusion graph, then compare an actual Fusion render with the supplied real-case golden PNG. PSD bytes and semantic provenance are authoritative for structure; Photoshop is optional historical/additional evidence and is not a prerequisite for verification.

Read-only real inputs:

```text
PSD:       D:\Downloads\a.psd
Reference: D:\Downloads\20260812.png
```

Never modify or commit either file. Before treating the PNG as a pixel oracle, establish its dimensions, profile, alpha, crop/scale/orientation, and relationship to the PSD.

Detailed contracts:

- compositing semantics and lowering boundaries: `docs/COMPOSITING_CONTRACT.md`
- fixtures, metrics, evidence and gates: `docs/PARITY_VALIDATION.md`
- PSD/file-format evidence: `docs/research/`
- historical FIRST_USABLE architecture: `ARCHITECTURE.md`

## Done

The program is done only when:

1. the supported subset is explicit and executable structural plus RGB/alpha gates exist;
2. the real PSD is reproducibly lowered, rendered by actual Fusion, and compared with the supplied PNG;
3. no unsupported/unverified semantic silently becomes Normal, 100% opacity, dropped, resized, graded, flattened, or hidden;
4. a fresh verifier reproduces the claim from Git, the two read-only files, deterministic independent fixtures, and documented Fusion/reference commands (optional GIMP cross-render evidence may supplement; Photoshop evidence is optional);
5. reports distinguish `parsed`, `planned`, `structural`, `host_loaded`, and `pixel_verified` claims.

## Opening sequence

1. Read root `AGENTS.md`.
2. Read `.control/current.json`.
3. Read the matching `active_task_id` section below and only the linked docs needed for it.
4. Inspect current branch/HEAD, relevant code/tests, and committed evidence.
5. Establish the current baseline or failure before editing.

Do not infer current state from chat, memory, an old log, or an agent completion message.

## State and roles

`.control/current.json` is canonical current state. Re-read current HEAD/state immediately before a state write.

A Worker may set the active task `in_progress`, attach branch/commit/evidence, and submit `awaiting_verification`. It must not mark its own task `done` or advance `active_task_id`.

A fresh Verifier evaluates the exact Goal, candidate diff/commit, executable evidence, host evidence and false-PASS risks. It records PASS/FAIL/BLOCKED. Only after PASS may a state-transition commit mark the task `done` and advance to the next unblocked task.

Use one task-scoped branch. Preserve unrelated work. Treat both real inputs as read-only. Do not commit source artwork, reference PNG, full-resolution renders, per-layer exports or sensitive screenshots to this public repository.

Worker closeout must contain:

```text
Task; branch/exact HEAD; changed files; commands and exact results;
host/reference versions, settings and hashes; quantitative metrics;
unresolved defects/blocker; committed evidence path; verifier starting point.
```

Verifier return must contain:

```text
Verdict: PASS | FAIL | BLOCKED
Task / exact candidate HEAD
Checks reproduced and environment
Findings with file/line or evidence path
False-PASS risks checked
Required correction or permitted state transition
```

## Evidence

Commit safe summaries under:

```text
.control/evidence/<task-id>/<run-id>/summary.json
```

Store real files and full-size outputs only under ignored `.local/`, `artifacts/`, or `parity-output/`. Keep the user PNG, PSD stored composite, psd-tools raster, actual Fusion render, optional GIMP render, and any optional Photoshop output as distinct origins.

## Ordered tasks

### PARITY-001 — Reference contract and parity harness

Create a one-command Windows validation path. Record file hashes, sizes, dimensions, modes/depth, alpha, profiles/metadata, PSD stored composite, and an explicit alignment/normalization classification. Add a deterministic comparator with RGB/alpha metrics, hard dimension failure, machine JSON, diff artifacts and synthetic false-PASS tests. Add `scripts/parity/` entrypoint covering inspection, conversion, offline checks, comparison and fail-closed host-required mode. Run an actual baseline against both read-only files. Do not alter compositor math merely to improve the baseline.

Done: identity/normalization and comparator are established, one actual baseline is recorded safely, and inputs remain unchanged/uncommitted.

### PARITY-002 — Evaluation IR and strict capability decisions

Add the smallest Evaluation IR for ordinary composition, transparent subtree, Pass Through, clipping spans, opacity stages and explicit native/custom/bake/reject decisions. Preserve raw provenance. Strict mode never silently uses Normal. FIRST_USABLE behavior remains only under an explicit compatibility policy. Prove the real PSD still plans the expected chain/member structure after re-hashing.

### PARITY-003 — Core blend and opacity

Verify Normal, Multiply, Linear Dodge, Overlay, ordinary opacity, isolated-group opacity, nested boundaries, source/backdrop alpha, color space, clamp and transparent RGB. Promote a native/custom registry entry only with host pixel proof tied to environment and commit.

### PARITY-004 — Grouped/default clipping

The current implementation run is limited to P4-02 in
`.control/PARITY-004_TODO.md`: extend the selected P4-01 recipe to a readable
base plus multiple clipped members with one fixed base matte. Host/render
validation, P4-03 and later queue items, Photoshop work, and pixel-proof
infrastructure changes remain deferred.

Verify absent/default true and explicit true `clbl`. Run the gates in order: deterministic independent fixtures as the semantic/math gate; real PSD bytes, structure and provenance; actual Fusion render with a fresh pixel artifact; full comparison with `D:\Downloads\20260812.png`; then, if available, an optional GIMP cross-renderer comparison. Establish base-coverage stage, fixed matte, local-alpha invariant, member order, outer-backdrop isolation, base/member opacity, fractional edges and mixed blends. PSD bytes/semantic provenance remain authoritative for structure, and graph/load evidence never promotes a pixel claim. Photoshop evidence is optional/additional. Do not claim `clbl=false`.

### PARITY-005 — `clbl=false` and group interaction

Use independent on/off fixtures and available renderer cross-checks to determine member backdrop and base mode/opacity. Verify isolated, Pass Through, nested and group-as-base/member cases. Reconstruct only with evidence; otherwise use explicit verified bake/reject. Photoshop evidence, if available, is optional/additional and never the sole semantic authority.

### PARITY-006 — Real PSD convergence

Partition reference differences by semantic region, chain, group, blend, opacity, alpha and color. Reduce each material issue to a fixture, repair the smallest correct boundary, rerun fixture then real PSD, and retain before/after evidence. No blind global grade, resize, blur or flatten.

### PARITY-007 — Independent closeout

A fresh clean-checkout verifier recomputes hashes, reruns offline/fixture/host/real-reference paths, audits comparator false-PASS paths, strict capability decisions, privacy, evidence linkage and complexity. PASS is required before program state becomes `done`.

## Repository check

Until PARITY-001 adds the host/reference command:

```powershell
pwsh -NoProfile -File .\scripts\check.ps1
```

This validates canonical state, unit tests and Python compilation. It never implies host/reference success.
Task completion additionally requires publishing commits and using the remote completion guard after a fresh fetch/readback of `origin/main:.control/current.json`; network or remote mismatch is not PASS.
