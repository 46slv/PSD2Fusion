# PSD2Fusion first-usable implementation policy

Legacy filename: `SOL_OPERATIONS.md`. This is not a general Sol manual. Read it only when the current Goal explicitly covers architecture reset, initial implementation strategy, or FIRST_USABLE delivery for PSD2Fusion.

## Development split
The intended sequence is:

`research evidence -> one deep architecture decision -> persist architecture -> shortest implementation -> continuation checks -> assembled usable candidate -> minimum Resolve/Fusion smoke -> user real-use -> evidence-driven hardening`

Architecture design is a phase, not a ceremony repeated during every implementation task.

## Architecture-reset phase
When architecture redesign is explicitly authorized, reason deeply about only the boundaries that are expensive to reverse:
- the semantic data that must survive PSD parsing;
- the boundary between PSD semantics and Fusion graph generation;
- Group compositing semantics versus node-graph visual organization;
- clipping representation independent of layout/serialization;
- host-specific behavior boundaries;
- unsupported-semantic raster/bake fallback boundaries.

Use the committed research baseline and current runtime evidence. Record the chosen architecture and material tradeoffs in the repository's architecture authority.

Once those boundaries are decided, freeze them for implementation. Reopen architecture only when current implementation/runtime evidence materially contradicts the design or the current Goal cannot fit the contract without destructive change.

Deep architecture reasoning may legitimately produce a small, direct implementation. Do not equate design depth with framework size.

## FIRST_USABLE target
Optimize for the shortest vertical slice the user can actually try:
1. accept/select a PSD;
2. read enough semantics for the current core;
3. generate the intended Fusion artifact/graph;
4. Resolve/Fusion recognizes or loads it;
5. ordinary layers appear;
6. a real Group case is readable;
7. a real Clipping case can be exercised.

Do not delay this slice for complete Photoshop parity, exhaustive blend modes, perfect graph layout, generalized fallback machinery, performance architecture, packaging polish, or broad regression infrastructure.

## Reuse prior art first
Do not rebuild solved plumbing for originality. The known implementation references include:
- `NUROKU/DaVinciResolve_PSDFusionGenerator`;
- `bixcl/PSDconverter`;
- `34j/DaVinciResolve.PSDGeneratorBuilder`;
- additional prior art committed with the research baseline.

Prefer adapting proven PSD extraction, position math, Merge construction, `.comp` / `.setting` serialization, loader/template generation, and path-handling mechanics when they fit the chosen architecture.

Material code copying requires a compatible license. Preserve required notices/attribution and record source repository + revision/path for copied or adapted code. If licensing is unclear/incompatible, use observed behavior or independently reimplement the pattern instead.

Prefer maintained libraries such as `psd-tools` over writing a PSD parser unless a demonstrated gap requires otherwise.

## Implementation cadence
After architecture is fixed, move continuously toward the usable vertical slice.

During assembly, use only cheap continuation checks needed to avoid developing blind, for example:
- syntax/import succeeds;
- the entrypoint starts;
- the expected artifact is emitted;
- generated Fusion syntax is structurally parseable enough to continue;
- a critical dependency/API assumption is confirmed.

Do not stop after every edit for broad validation. Do not repeatedly redesign because intermediate code is imperfect. Reversible local hard-coding/TODOs are acceptable when they accelerate the first usable path and do not violate the protected contracts.

## Validate after the candidate exists
Meaningful product validation begins after a coherent candidate is assembled.

Minimum FIRST_USABLE smoke:
1. the tool runs;
2. it accepts a PSD;
3. it emits the intended Fusion artifact;
4. Resolve/Fusion recognizes or loads it;
5. the primary ordinary-layer path executes once;
6. the current Group/Clipping path can be tried without immediate destructive failure.

If those pass, hand it to the user quickly.

Do not block first use on exhaustive fixtures, complete visual-parity sweeps, malformed-input matrices, broad Resolve-version compatibility, multiple review layers, extensive CI, performance sweeps, or release packaging unless the active Goal/risk explicitly requires them.

## Real-use hardening
After first use:

`real PSD / user friction -> concrete failure -> localize -> smallest fix -> smallest useful regression guard -> ship again`

Prefer observed Photoshop/Resolve behavior and real PSD failures over speculative edge cases.
Generalize only after real variation, repeated failures, or shared contracts justify it.

## Scope filter
- blocks first usable build -> fix now;
- prevents basic user use -> fix now;
- small reversible imperfection -> ship and observe;
- future Photoshop feature -> note, do not implement;
- interesting architecture possibility -> ignore until evidence requires it.

## Stop rule
For early development, stop and hand off as soon as a coherent real-use flow exists, Resolve/Fusion recognizes it, the core path can be exercised, and no immediate destructive failure is known.

A rough PSD2Fusion that successfully imports a real PSD into a readable Fusion graph is more valuable at this stage than a broader theoretically complete system that has not yet been used.