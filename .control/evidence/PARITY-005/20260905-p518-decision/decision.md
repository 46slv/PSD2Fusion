# PARITY-005 Stage S4 semantic decision record

Status: DECIDED (Coordinator, Axis C audit attached).
Date: 2026-09-05. Branch: `codex/parity-005`.
Task: explicit PSD `clbl=false` + group interaction.
Renderer scope: DaVinci Resolve Studio 21.0.3.7, fuscript current-composition
paste route, Loader `PostMultiply=0` + `StartFrame=-1` + float32
ChangeDepth/AlphaMultiply, Saver `PreDivide=1`. No Photoshop evidence exists
or is required; `psd-tools` 1.18.0 composite carries `BLEND_CLIPPING_ELEMENTS`
TODO and is not an oracle. Real PSD `a.psd` contains zero explicit-false
chains (23 chains, all `photoshop_default_true`).

## 1. Surviving hypotheses

- H2 (progressive-outer, base-underneath, clip-only) survives SOLELY as
  documented characterization of the committed legacy fallback graph's own
  math (`R0=Over(D,B,Fb,qb); Ji=(Ci,Ai*qi*M); Ri=Over(Ri-1,Ji,Fi)`),
  self-consistent across ~26 temp-only host renders spanning ungrouped,
  isolated group-local, pass-through parent, nested, and group-as-base
  scopes. H2 is NOT promoted to Photoshop semantics.

## 2. Rejected hypotheses and decisive fixtures (fallback-scoped)

- H1 (local-span-then-base-as-group): REJECTED by F4 base-opacity q128
  (host matches H2 0-LSB, H1 diverges >=63) and 06T alpha-growth (host
  alpha 157 vs H1 pin 102, delta 55).
- H3 (independent-outer + Normal stack): REJECTED by P5-07 backdrop-swap
  (host 0-LSB invariant vs H3-predicted 0->102->178 swing, ~35-49 LSB).
- H4 (per-member base interaction / double-apply): REJECTED by P5-09
  (host matches single-apply H2 0-LSB; H4 diverges 85,127,0,63, max 127).
- H5 (matte-only Normal stack): REJECTED by F1 absolute + AB/BA + 06 +
  group scopes (margins 0.524-0.587, 130+ LSB). P5-08 primaries fixture is
  explicitly non-discriminating and is never cited as the mode kill; the
  mode kill rests on F1-absolute and P5-15 group-base N-vs-M (FAIL 93).

## 3. Unresolved / excluded cases

- Ungrouped base-mode pixel scope: S-NONDISCRIMINATING (P5-08 primaries
  mask mode; matrix-color follow-up still open).
- Pass-through opacity<1, isolated group opacity != 1.0, member fractional
  opacity in groups: untested, explicitly excluded from any claim.
- Group-as-member: structurally unsupported via `psd_tools` `Group.clipping`
  guard (`psd_tools/api/layers.py:1362-1373`) -> explicit reject/bake
  category, not a pixel claim.
- Photoshop-pair `clbl=false` pixel truth: unverified and unverifiable from
  current inputs (zero real chains, no Photoshop pair). 06T H2 support is
  <=1-LSB (at noise) and cannot carry promotion alone.

## 4. Alpha/opacity/backdrop/group semantics (fallback characterization)

- Span root consumes whatever backdrop the span root sees: parent stream
  ungrouped (P5-07 invariance is base-opaque erase + H2-R0 equivalence),
  inner transparent canvas in isolated groups (P5-12, 0-LSB group-local),
  incoming parent stream in pass-through groups (P5-13, 0-LSB direct x2),
  inner isolated canvas when nested (P5-14, nesting adds structure only).
- Base opacity applies ONCE (P5-09; H4 double-apply contradicted).
- Member-member chaining is sequential in PSD order (P5-10, AB!=BA by 78).
- Span alpha grows under fractional base coverage (P5-11, 102->157);
  H1 fixed-coverage pin contradicted.
- Group-as-base: coverage/mode/opacity all measurable (P5-15, FAILs
  95/93/45); fallback uses the group terminal as matte.

## 5. False-PASS risks checked (Axis C audit)

Circularity scoped: fallback~=H2 coincidence licenses zero Photoshop
inference. Oracle shares straight-RGB/canonical-zero/per-stage-clamp/sRGB
assumptions with the fallback boundary (within-family coincidence).
Premult/transparent-RGB/clamp/ICC/byte-quant residuals (0-1 LSB) cannot flip
any 24-127 LSB kill; 8x8-uniform generality, single-session variance, and
untested opacity scopes are recorded exclusions. p503-07 degeneracy control
clean; 6dp rounding headroom >=3500x. No S-CONTRADICTION (all host sources
agree); no new S-CONFOUND.

## 6. Implementation authority: REJECT

Strict policy must fail closed on any explicit `clbl=false` span (raise or
explicit bake/reject marker; the legacy approximate graph must not be
emitted under strict). P5-19 fail-closed repair (strict capability gates
lowering) is mandatory first regardless of the H2-fallback coincidence. No
`native_candidate` is granted. No `verified_bake_candidate` is granted for
general `clbl=false` pixels. H2 is retained solely as documented
fallback-graph characterization under an explicit compatibility policy,
never as promoted semantics. Any future native/bake proposal must preserve
the 32-bit float production path, introduce no 8-bit quantization for byte
identity, contain no real-PSD layer-ID special cases, and carry the
provenance caveat that Photoshop-pair `clbl=false` pixel truth remains
unverified. S-FAILOPEN remains ACTIVE and is carried to P5-19.
