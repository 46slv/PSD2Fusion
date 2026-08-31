# PSD2Fusion Sol Operating Policy

Use this policy when the supervising/root agent is a strong Sol-class model. Its purpose is to prevent strong reasoning from turning a bounded Goal into repeated audits, speculative architecture, or unnecessary framework work.

## Core operating bias

**Think deeply about architecture once. Implement by the shortest practical route. Validate broadly only after a usable slice exists.**

Default sequence:

`deep architecture pass -> freeze the needed boundaries -> fastest implementation -> continuation smoke only -> first usable build -> minimum host smoke -> user use -> fix what real use exposes`

The objective is not to prove the system theoretically complete before it can be used. The objective is to get a real PSD into a real Fusion graph quickly enough that the user can judge the product in practice.

## 1. Architecture deep, implementation small

Architecture quality and implementation size are different things.

Before substantial implementation, Sol should reason deeply enough to settle only the boundaries that are expensive to reverse, such as:
- what semantic information must survive PSD parsing;
- where PSD semantics end and Fusion graph generation begins;
- how group semantics differ from graph layout/visual grouping;
- how clipping is represented independently of serialization;
- where host-specific behavior is isolated;
- where unsupported semantics fall back to rasterization/baking.

Then stop architecting and implement.

Do not turn the architecture pass into building generalized infrastructure. A deep design may still result in five small modules and direct functions.

Re-open an architecture decision only when implementation/runtime evidence contradicts it or when a concrete required behavior cannot fit it without destructive change.

## 2. First usable build outranks completeness

Optimize for the shortest route to a tool the user can actually try.

The early product target should be approximately:
1. select/open a PSD;
2. read enough layer semantics;
3. generate a Fusion composition/graph;
4. Resolve/Fusion recognizes and loads it;
5. ordinary layers work;
6. one real Group case is readable;
7. one real Clipping case behaves plausibly enough for user testing.

Do not delay this build for complete Photoshop parity, exhaustive blend-mode coverage, perfect layout, generalized fallback systems, performance optimization, packaging polish, or comprehensive regression infrastructure.

A known limitation with a direct implementation is preferable to an elegant subsystem that postpones first use.

## 3. Sol anti-overengineering rules

Sol must not widen the Goal merely because it can see future complexity.

Do not introduce without current evidence:
- plugin/framework systems;
- generalized IR layers beyond semantics currently needed to generate the first working graph;
- strategy/factory/provider abstractions for one implementation;
- registries, dependency-injection systems, event buses, schedulers, graph optimizers, generalized caches, migration/versioning frameworks;
- compatibility layers for hypothetical hosts or future PSD features;
- broad fallback matrices when one explicit fallback is sufficient;
- performance architecture before a measured bottleneck;
- speculative Adjustment Layer, Smart Object, Layer Style, native text, or unrelated Photoshop support.

Prefer direct code first. Extract an abstraction after a second real use demonstrates duplication or conflicting behavior.

A clean seam is useful. Pre-building every implementation behind the seam is not.

## 4. Reuse prior art aggressively

Do not rebuild solved mechanics for originality.

The previously researched PSD/Fusion projects are implementation references, especially:
- `NUROKU/DaVinciResolve_PSDFusionGenerator`;
- `bixcl/PSDconverter`;
- `34j/DaVinciResolve.PSDGeneratorBuilder`;
- other source-backed prior art recorded under `docs/research/` once it is in the repository.

Use prior art to shorten implementation:
- copy/adapt proven `.comp` / `.setting` serialization patterns;
- reuse known layer-position/merge construction logic;
- reuse PSD extraction patterns;
- reuse loader/template generation and path-handling approaches;
- reuse small utilities instead of rewriting them when doing so is cleaner and faster.

Code copying is allowed only when the source license permits it. Preserve required license notices/attribution and record the source repository + relevant revision/path when code is materially copied or adapted. Do not copy code with incompatible, unclear, or proprietary licensing. Ideas, observed behavior, interfaces, and independently reimplemented patterns may still be used where legally appropriate.

Prefer an existing maintained library such as `psd-tools` over writing a PSD parser unless a demonstrated semantic gap forces otherwise.

When choosing between inventing and adapting a working implementation, **adapt first**.

## 5. Implementation cadence: build first

Once the architecture pass has produced a bounded route, implementation should move continuously toward a complete vertical slice.

During implementation:
- do not stop after every small edit for broad validation;
- do not repeatedly run full suites;
- do not create tests for every internal helper before the flow exists;
- do not ask reviewers to audit incomplete intermediate states unless a concrete blocker requires it;
- do not repeatedly reconsider architecture because code is temporarily ugly;
- TODOs and local hard-coded choices are acceptable when reversible and visible.

Use only **continuation checks** needed to avoid developing blind:
- syntax/import succeeds;
- script starts;
- expected file is emitted;
- generated syntax is parseable enough to continue;
- a dependency/API assumption is not obviously false.

Continuation checks are not an acceptance campaign. Keep them cheap.

## 6. Validation happens after the slice is assembled

The default is **implementation first, meaningful validation after a complete candidate exists**.

For the first usable build, minimum validation is deliberately small:
1. the program/script runs;
2. it accepts a PSD;
3. it produces the intended Fusion artifact;
4. Resolve/Fusion recognizes or loads the artifact;
5. a minimal ordinary-layer example appears;
6. the current Group/Clipping target can be tried in the host without immediate failure.

If those pass, hand the build to the user quickly.

Do not block first use on:
- exhaustive fixture matrices;
- full visual parity sweeps;
- every blend mode;
- every malformed PSD;
- broad cross-version testing;
- multiple independent reviews;
- extensive CI;
- theoretical proof that the graph model covers future Photoshop semantics.

The user using the tool is an important validation surface. Real failures should become the next focused bugfix/fixture/regression case.

Exceptions: perform early safety checks when an action risks destructive data loss, credentials, irreversible mutation, or uncontrolled external side effects. This exception is about safety, not software perfection.

## 7. User-driven hardening loop

After first usable build:

`user tries real PSD -> observe concrete failure/friction -> localize -> fix -> add the smallest regression guard -> ship again`

Prefer evidence from actual user files and Resolve behavior over speculative edge-case design.

Only promote behavior into a durable test/harness when it is required by the product, exposes a real failure, or protects a boundary likely to regress.

Do not front-load a large verification framework before there is a product behavior worth protecting.

## 8. Research stop rule

Research is complete when it supports the pending architecture decision or implementation choice.

- Do not collect equivalent sources after the decision-relevant fact is established.
- For uncertain Resolve behavior, prefer a minimal host probe over further abstract reasoning.
- Record unknowns explicitly and design a reversible seam around them if needed.
- Do not wait for every host semantic to be known before starting the core implementation.

When uncertainty can be answered by building the minimal candidate and trying it, build it.

## 9. Luna / Sol split

Use Sol for:
- one deep architecture pass;
- hard semantic boundary decisions;
- resolving conflicting evidence;
- bounded diagnosis when Luna is genuinely stuck;
- deciding whether a discovered issue matters now.

Use Luna for:
- repository reading/localization;
- adapting prior-art code;
- routine implementation;
- repetitive graph/serialization work;
- debugging;
- small smoke checks;
- host trial execution when available.

After Sol answers the hard question, return execution to Luna. Do not let Sol remain in a repeated inspect/review/rewrite loop.

## 10. Scope control

Classify discoveries:
- **blocks first usable build** -> fix now;
- **prevents basic user use** -> fix now;
- **small reversible imperfection** -> ship it and observe;
- **future feature** -> note briefly, do not implement;
- **interesting architecture possibility** -> ignore until evidence requires it.

Finding an improvement is not authority to implement it.

## 11. Stop rule

For early development, stop and hand off to user as soon as:
- a coherent first-use flow exists;
- the application/host recognizes it;
- the basic target behavior can be exercised;
- there is no immediate destructive failure;
- known limitations are stated briefly.

Do not continue polishing because more checking is possible.

For PSD2Fusion, **a rough tool that successfully imports a real PSD into a readable Fusion graph is more valuable than a nearly perfect architecture that has not yet imported one.**
