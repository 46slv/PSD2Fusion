# Photoshop compositing semantics deep dive

Research date: 2026-09-03  
Scope: PSD semantics that materially affect pixel reproduction after the binary structure has already been parsed  
Status: **research evidence, not current task state and not an implementation authorization**  
Current project authority remains `.control/current.json`, `.control/CURRENT_GOAL.md`, and `docs/COMPOSITING_CONTRACT.md`.

This document extends `00-psd-file-format-foundations.md` and `02-psd-semantic-requirements.md`. The earlier documents establish *where* PSD data lives. This document asks a different question:

> Given the layer tree, pixels, masks, tags, and descriptors, what additional semantics are required to reproduce Photoshop-visible pixels without silently fitting to a reference?

The main conclusion is that Photoshop compositing is an **evaluation problem**, not only a blend-mode lookup problem. Coverage, fill, effects, masks, clipping scope, group backdrop, advanced blending flags, color-space behavior, bit depth, and some Photoshop Color Settings can change the result.

---

## 1. Source authority used here

### Primary Photoshop behavior documentation

- Adobe — Layer opacity and blending  
  https://helpx.adobe.com/photoshop/using/layer-opacity-blending.html
- Adobe — Reveal layers with clipping masks  
  https://helpx.adobe.com/photoshop/using/revealing-layers-clipping-masks.html
- Adobe — Create a knockout  
  https://helpx.adobe.com/photoshop/using/knockout-reveal-content-layers.html
- Adobe — Color settings  
  https://helpx.adobe.com/photoshop/using/color-settings.html
- Adobe — High dynamic range images / 32-bpc feature support  
  https://helpx.adobe.com/photoshop/using/high-dynamic-range-images.html
- Adobe — Blending mode descriptions  
  https://helpx.adobe.com/photoshop/desktop/repair-retouch/adjust-light-tone/blending-mode-descriptions.html

### Mathematical reference, not Photoshop authority

- W3C Compositing and Blending Level 1  
  https://www.w3.org/TR/compositing-1/

W3C is useful for source-over, isolated groups, straight/non-premultiplied blend inputs, and standard blend formulas. It does **not** prove that every Photoshop-specific advanced option follows the W3C model.

### Current parser/compositor implementation evidence

`psd-tools` current source checked at commit:

```text
6fb7bd5215069ed63cbe009e921c3f33aa97a3ec
```

Important files:

- `src/psd_tools/composite/composite.py`
- `src/psd_tools/composite/blend.py`
- `src/psd_tools/api/pil_io.py`
- `src/psd_tools/psd/layer_and_mask.py`
- `src/psd_tools/psd/tagged_blocks.py`
- `docs/changelog.rst`

### Secondary evidence

The commonly described Photoshop “Special 8” Fill behavior is documented by Photoshop Training Channel and other long-lived technical references, but I did not find an Adobe page that specifies the exact eight-mode Fill equations. Treat that list as **secondary evidence / fixture target**, not as a primary-spec formula.

---

## 2. New upstream fact: psd-tools 1.19.0 materially changed rendering

`psd-tools 1.19.0` was released on 2026-09-02. PSD2Fusion currently pins:

```toml
psd-tools>=1.18,<1.19
```

Therefore PSD2Fusion's current environment intentionally remains on the older renderer/parser line during the active parity work.

Relevant 1.19 changes include:

- corrected Soft Light;
- corrected Vivid Light;
- corrected Hard Mix;
- corrected CMYK behavior for the six non-separable modes;
- document-aware widening/conversion of single-channel sources;
- several Lab/CMYK conversion fixes;
- corrected Pass Through group opacity below 255, where the older path blended backdrop contribution twice and varied with nesting depth;
- implemented shallow/deep Knockout compositing;
- corrected real-mask parameter detection.

This matters in two ways.

### CONFIRMED

`psd-tools` itself was still changing Photoshop-facing compositor behavior immediately after the earlier PSD2Fusion foundation research. It should not be treated as a fixed Photoshop oracle.

### DESIGN CONSEQUENCE

Do **not** silently upgrade the dependency during an in-progress pixel baseline. A controlled 1.18-vs-1.19 A/B should be a separate evidence step after the current baseline, because an upgrade can change raster/compositor output independently of PSD2Fusion's own lowering.

For future research, 1.19 is nevertheless more useful as an independent implementation cross-check because several behaviors are now explicitly pinned against Photoshop 2026 observations in upstream tests/comments.

---

## 3. A safer evaluation model

Do not encode one universal exact ordering until fixtures prove it for each semantic combination. The following is a **semantic dependency model**, not a claim that Photoshop executes these as literal sequential passes:

```text
source representation
  pixel / text / vector / fill / smart object
        |
source transparency / source shape
        |
pixel and vector mask coverage
        |
fill-opacity semantics
        |
layer effects + advanced effect-scope flags
        |
overall layer opacity
        |
blend mode + advanced channel / Blend If restrictions
        |
clipping-span evaluation and base coverage
        |
group isolation / Pass Through / group mask / group opacity
        |
adjustment-layer backdrop transformations
        |
color-space / gamma / bit-depth behavior
        |
final document composite
```

The key invariant is not the visual order of this diagram. It is that these are **different semantic quantities** and cannot safely be collapsed into one `Merge.Blend` value or one alpha channel.

---

## 4. Overall opacity and Fill are semantically distinct

Adobe explicitly distinguishes them:

- Overall Opacity affects the completed layer, including layer styles and the layer's blending result.
- Fill affects the layer's pixels, shape, or text while leaving effects such as Drop Shadow unaffected.
- A selected group exposes Opacity but not Fill in the normal Layers-panel contract.

This validates the current PSD2Fusion rule that overall opacity and fill opacity must remain separate.

### Additional “Special 8” behavior

Secondary Photoshop technical sources consistently report that these eight modes respond differently to Fill and Opacity even without layer effects:

```text
Color Burn
Linear Burn
Color Dodge
Linear Dodge (Add)
Vivid Light
Linear Light
Hard Mix
Difference
```

This should be treated as a **required fixture family**, not yet as a hard-coded formula. If PSD2Fusion later supports Fill natively, a simple `source_alpha *= fill_opacity` implementation must not be promoted for these modes without Photoshop/reference evidence.

Current `psd-tools 1.19` reads `iOpa` and folds fill into its compositing equations, but the existence of that implementation is not independent proof of Photoshop parity for every special-mode boundary.

---

## 5. Group semantics: Pass Through is a backdrop-scope operation

Adobe confirms:

- a layer group defaults to Pass Through;
- with Pass Through, the group does not behave as a self-contained blended image;
- choosing a different group blend mode changes evaluation: children are composed first, then the composite group is treated as one image against the outer document;
- adjustment layers and child blend modes inside an isolated/non-Pass group do not affect layers outside that group.

This is stronger than “Fusion Group is only organizational”: it establishes an explicit **backdrop dependency boundary**.

### Isolated group

A useful general model, also consistent with W3C isolated-group semantics:

```text
local backdrop = transparent
S = composite(children, local backdrop)
output = composite(parent_backdrop, S, group mode, group opacity)
```

### Pass Through

Conceptually:

```text
children consume the incoming parent backdrop
```

A Pass Through group's opacity cannot automatically be treated as “multiply every child's opacity.” `psd-tools 1.19` had to specifically repair Pass Through opacity because a backdrop contribution was being applied twice. This is direct evidence that Pass Through opacity is a boundary-level operation with non-trivial alpha/backdrop behavior.

### Current PSD2Fusion implication

Current `parse_psd.py` still labels Pass Through opacity below 1.0 as outside its first-slice native path. That conservative policy remains appropriate until Fusion host pixels prove the lowering.

---

## 6. Clipping is a span, not a mask shortcut

Adobe confirms all of the following:

- the bottom/base layer determines the visible clipping coverage;
- clipped layers above it must be successive/contiguous;
- multiple clipped layers may share one base;
- `Blend Clipped Layers As Group` determines whether the base layer's blend mode applies to the whole clipping group or only to the base.

Adobe also documents that `Blend Clipped Layers As Group` is selected by default.

Therefore a clipping IR should preserve at least:

```text
base identity
base evaluated coverage
ordered member identities
same-parent boundary
member modes/opacities
base mode/opacity
clbl: absent/default | explicit true | explicit false
raw provenance
```

### Current grouped/default hypothesis

The current PSD2Fusion compositing contract uses:

```text
M = evaluated base coverage
S = evaluated base content
for member bottom-to-top:
    J = member restricted by M
    S = local_blend(S, J, member mode, member opacity)
    coverage(S) remains M
output = composite(outer_backdrop, S, base mode, base overall opacity)
```

This is a plausible executable hypothesis and is structurally consistent with Adobe's group-level description, but it remains a **candidate until host pixels prove the alpha/mode/opacity boundaries**.

### Important upstream gap

Current `psd-tools 1.19` still contains:

```text
# TODO: Consider Tag.BLEND_CLIPPING_ELEMENTS.
```

inside `_apply_clip_layers()`.

So even after 1.19, `psd-tools` must not be used as the oracle for `clbl` true/false semantics.

### `clbl=false`

This deserves its own fixture family. Adobe defines the user-visible meaning, but that description is insufficient to derive every fractional-alpha/member-backdrop equation. PSD2Fusion's current strict bake/reject posture for unverified `clbl=false` remains justified.

---

## 7. Advanced blending options are first-class semantics

Adobe exposes multiple advanced switches that materially change the composite.

### 7.1 Blend Interior Effects As Group

Photoshop can apply the layer's blend mode to effects that modify opaque pixels, such as Inner Glow, Satin, Color Overlay, and Gradient Overlay.

PSD tag:

```text
infx
```

Current `psd-tools 1.19` parses the tag, but its compositor still contains:

```text
# TODO: Tag.BLEND_INTERIOR_ELEMENTS controls how inner effects apply.
```

Therefore `infx` is currently **parseable but not a trustworthy rendered semantic** in upstream.

### 7.2 Transparency Shapes Layer

Adobe documents this option as restricting layer effects and knockouts to opaque layer areas; deselecting changes their scope. Default is selected.

PSD tag family includes:

```text
tsly
```

Current upstream exposes/parses it, but no complete compositor use was found in the inspected current source.

### 7.3 Layer Mask Hides Effects / Vector Mask Hides Effects

Adobe treats these as separate effect-scope controls. They mean that “mask coverage” and “effect coverage” cannot always be represented by one unified post-effect alpha mask.

### 7.4 Channel exclusion

Adobe allows excluding selected color channels from blending. PSD already has channel-blending restriction metadata/tag families. A converter that ignores this can be visually wrong even if the named blend mode itself is mathematically correct.

### DESIGN REQUIREMENT

Advanced blending flags should be inventoried in Semantic IR before broad parity claims. Unsupported values should produce `detected_unsupported` / bake / reject decisions rather than silently behaving like defaults.

---

## 8. Blend If is a backdrop-dependent coverage function

Photoshop's `Blend If` controls whether pixels from the active layer or underlying visible composite participate based on tonal ranges. Split sliders create partial transitions rather than binary thresholds.

PSD stores Layer Blending Ranges in the LayerRecord extra data. `psd-tools` parses the structure, but no use of those blending ranges was found in the inspected compositor path.

This has an important architectural consequence:

```text
Blend If
!= simple source mask in the general case
```

The `Underlying Layer` side depends on the **current backdrop/composite**, so a verified bake may need a backdrop dependency closure. It belongs in Evaluation IR / capability planning, not merely asset materialization.

Minimum future fixture set:

- This Layer black/white range;
- Underlying Layer black/white range;
- split black slider;
- split white slider;
- individual RGB channel range;
- same settings inside isolated and Pass Through groups.

---

## 9. Knockout establishes another explicit backdrop boundary

Adobe distinguishes:

- **Shallow**: punches through to the first stopping boundary, such as the enclosing group boundary or clipping base;
- **Deep**: punches through toward the document Background layer; if no Background exists, transparency can be revealed.

Adobe also documents reducing Fill opacity or changing blend mode as part of making the knockout visible.

`psd-tools 1.19` now implements shallow/deep knockout and documents a Photoshop 2026 probe in source comments. This makes it useful implementation evidence, but Knockout is still not part of PSD2Fusion's current supported subset.

Future IR should preserve:

```text
knockout = none | shallow | deep
background-layer identity
isolation boundary
clipping-base stopping boundary
fill opacity
```

Do not reduce Knockout to a negative alpha mask.

---

## 10. Masks are more than grayscale pixels

The earlier foundation document already separates:

- layer transparency;
- user pixel mask;
- real/combined mask;
- vector mask;
- document alpha.

The deeper compositor problem adds:

- mask density;
- mask feather;
- vector mask density;
- vector mask feather;
- disabled/inverted/default-color state;
- effect-hiding policy;
- group-mask scope.

Current `psd-tools 1.19` `_get_mask()` applies density and combines vector coverage in several paths. In the inspected code, parsed feather parameters are **not applied there**. Therefore mask feather remains a renderer gap for exact parity.

Minimum fixtures should separate:

```text
hard pixel mask
pixel mask + density
pixel mask + feather
vector mask hard edge
vector mask + density
vector mask + feather
pixel + vector / real mask
mask on isolated group
mask on Pass Through group
mask + layer effects
```

---

## 11. Layer effects cannot be treated as one post-layer raster

Even before implementing all effects, PSD2Fusion needs to know when an effect changes evaluation boundaries.

Adobe's advanced options prove at least these distinctions:

```text
interior effects
transparent-area effects
layer blend interaction
fill-opacity interaction
mask-hides-effects interaction
Transparency Shapes Layer interaction
knockout interaction
```

Current `psd-tools` has partial overlay/stroke rendering but also leaves ordering/scope TODOs. This reinforces the current policy:

> If an unsupported effect can be rasterized, label the result as a bake. Do not claim editable semantic parity from a raster fallback.

When effects become a parity target, fixture them by effect family and interaction, not only by effect presence.

---

## 12. Alpha and blend math: keep straight color separate from coverage

W3C's general blending model is useful here:

- blending is conceptually applied to source/backdrop colors where they overlap;
- the blend function must not consume premultiplied color values;
- after blending, compositing resolves the result with source/backdrop alpha;
- an isolated group begins against transparent black.

This supports the PSD2Fusion separation between:

```text
color
coverage/shape
alpha
backdrop
```

and explains why a same-named Fusion ApplyMode is insufficient evidence.

### Transparent RGB is observable after resampling/filtering

A pixel with alpha 0 may still carry RGB bytes. Those bytes do not affect a single ideal source-over sample, but they can affect filtering/resampling or incorrect pre/post-multiplication boundaries.

Current PSD2Fusion asset materialization does:

```python
canvas = Image.new("RGBA", ..., (0, 0, 0, 0))
canvas.alpha_composite(cropped, ...)
```

A deterministic Pillow probe shows that fully transparent source pixels become `(0,0,0,0)` on that transparent canvas; fractional-alpha pixels retain their straight RGB in the simple one-source case. Therefore the current materializer **normalizes away hidden RGB at alpha=0**.

That may be acceptable under an explicit transparent-RGB contract, but it must not happen silently while claiming byte/pixel equivalence to arbitrary Photoshop intermediate data.

---

## 13. Current asset path performs an implicit ICC conversion

This is a concrete current-code fact.

PSD2Fusion calls:

```python
raw.topil()
```

with no `apply_icc` argument. In current `psd-tools`, Layer `topil()` defaults to:

```text
apply_icc = True
```

and `convert_layer_to_pil()` retrieves the document ICC profile. `_apply_icc()` converts through Pillow/LittleCMS to an sRGB output profile.

PSD2Fusion then creates a new document-size RGBA canvas and saves it as PNG without explicitly carrying the source ICC payload into that new image.

So the general pipeline is currently closer to:

```text
PSD layer pixels in document space
 -> psd-tools ICC transform toward sRGB
 -> RGBA
 -> new transparent canvas
 -> PNG without explicit preserved source-profile payload
 -> Fusion Loader
```

rather than a raw-channel-preserving extraction path.

### Real reference case nuance

PARITY-001 evidence records:

- PSD: 8-bit RGB, ICC present;
- reference PNG: ICC present;
- source and reference ICC payload SHA-256 are identical;
- reference alpha is fully opaque;
- canvas is exact-size matched.

The recorded profile hash is consistent with a commonly distributed Windows sRGB Color Space Profile. Therefore for the **current real case**, a profile-to-sRGB conversion may be close to a semantic no-op. It is still not a safe general contract for arbitrary PSDs.

The same evidence shows the PSD stored composite is already very close to the supplied reference at the byte level (`RGB max error 3`, mean about `0.186`) even though the comparator fails closed on profile provenance. That makes the stored composite a valuable diagnostic reference while still keeping its origin distinct from the supplied PNG.

---

## 14. Photoshop has an application-level RGB blend-gamma control

Adobe Color Settings exposes:

```text
Blend RGB Colors Using Gamma
```

Adobe states:

- it controls how RGB colors blend to produce composite data, including Normal-mode layer blending/painting;
- when enabled, blending happens according to the specified gamma;
- gamma 1.00 is considered colorimetrically correct;
- when disabled, RGB colors are blended directly in the document color space;
- enabling the setting can make layered documents look different in other applications.

There is also a separate:

```text
Blend Text Colors Using Gamma
```

### CONFIRMED

Photoshop's visible/composite result can depend on a Color Settings control outside the ordinary per-layer blend-mode fields.

### OPEN QUESTION

This research did **not** establish whether the effective blend-gamma choice is serialized into every PSD in a form sufficient to recreate the authoring result. `cinf` and other undocumented compositor metadata exist, but their relationship to this user preference has not been proven here.

Therefore do not yet state either:

```text
PSD bytes always fully determine this preference
```

or:

```text
PSD bytes can never determine it
```

The correct next step is a Photoshop-authored two-file fixture pair that differs only in the Color Settings gamma option, followed by raw/tag/descriptor diffing and stored-composite comparison.

This is one of the most important unresolved questions for the phrase “complete Photoshop pixel reproduction.”

---

## 15. Bit depth changes the available semantic surface

Photoshop does not expose every blend mode equally at every bit depth/color mode.

Adobe's 32-bpc/HDR documentation lists a restricted blend-mode set, including Normal, Dissolve, Darken, Multiply, Lighten, Darker Color, Linear Dodge, Lighter Color, Difference, Subtract, Divide, Hue, Saturation, Color, and Luminosity.

Therefore a capability registry should eventually be keyed by at least:

```text
blend mode
color mode
bit depth
host/version
alpha contract
color-space/gamma contract
```

A blend proof obtained from an 8-bit RGB fixture is not automatically a 16/32-bit, CMYK, or Lab proof.

---

## 16. Current psd-tools 1.19 capability/gap matrix

This table describes the inspected upstream implementation, **not Photoshop truth**.

| Semantic | Current upstream state | PSD2Fusion consequence |
|---|---|---|
| Ordinary source-over / alpha | implemented | useful cross-check, still require Fusion proof |
| Common blend functions | broad implementation; several corrected in 1.19 | version-pin evidence |
| Pass Through opacity | repaired in 1.19 | strong warning against naive child-opacity lowering |
| Isolated groups | implemented model | useful independent comparison |
| Clipping members | implemented | not oracle for `clbl` |
| `clbl` | parsed; compositor TODO | must fixture independently |
| Fill opacity | implemented internally | special modes still require direct proof |
| `infx` | parsed; compositor TODO | detect/bake/reject |
| `tsly` | parsed; no complete compositor use found | detect/bake/reject |
| Blend If / blending ranges | parsed data structure; no compositor use found | detect/bake/reject |
| Mask density | used | useful cross-check |
| Mask feather | parsed; not applied in inspected mask path | not parity oracle |
| Knockout | implemented in 1.19 | useful cross-check, outside current subset |
| Adjustment layers | partial | never generic parity oracle |
| Layer effects | partial + ordering/scope TODOs | selective bake only |
| Text rendering | not general Photoshop typesetting oracle | keep raster/reference separation |
| ICC/color conversion | active conversion logic | must record transform provenance |

---

## 17. Current PSD2Fusion semantic inventory gaps

Current `parse_psd.py` already captures or inventories:

- raw/canonical blend;
- bbox/order/visibility;
- overall opacity;
- non-default fill opacity as unsupported;
- pixel/vector mask presence as unsupported;
- group Pass Through/isolation;
- clipping chain;
- `clbl` explicit/default-true provenance.

For future broad parity, add detection before implementation for:

```text
Layer Blending Ranges / Blend If
channel blending restrictions
Blend Interior Effects As Group (`infx`)
Transparency Shapes Layer (`tsly`)
Knockout (`knko`)
Layer Mask Hides Effects
Vector Mask Hides Effects
mask density/feather details
effect inventory + enabled state
background-layer semantic identity
bit-depth-specific mode availability
color/gamma environment evidence
unknown compositor-related descriptor inventory
```

The important sequence is:

```text
detect -> preserve provenance -> capability decision -> fixture -> implement/bake/reject
```

not:

```text
implement approximate behavior -> discover later that the source had an advanced flag
```

---

## 18. Recommended next deterministic fixture matrix

These are research/validation fixtures, not a request to interrupt the active PARITY-004 run.

### Immediate compositing boundary fixtures

1. Normal + fractional source alpha over transparent and opaque backdrop.
2. Multiply + fractional source/backdrop alpha.
3. Pass Through group opacity at 25/50/75%, nested one and two levels.
4. Isolated group opacity at the same values.
5. clipping base alpha 0 / 1 / 64 / 128 / 255.
6. clipping member opacity 25/50/75%.
7. base overall opacity 25/50/75%.
8. default/absent `clbl` vs explicit true.
9. explicit `clbl=false` with member blend modes chosen to make backdrop scope obvious.
10. transparent RGB with alpha=0 next to fractional-alpha edge, then resample/transform.

### Advanced blending fixtures

11. Fill vs Opacity for the candidate Special 8 modes.
12. `infx` on/off with Color Overlay and Inner Glow.
13. `tsly` on/off with effect and knockout.
14. Layer Mask Hides Effects on/off.
15. Vector Mask Hides Effects on/off.
16. Blend If This Layer hard/split threshold.
17. Blend If Underlying Layer hard/split threshold.
18. RGB channel-exclusion case.
19. shallow vs deep Knockout with/without Background layer.
20. knockout inside Pass Through vs isolated group.

### Mask fixtures

21. pixel mask density.
22. pixel mask feather.
23. vector mask density.
24. vector mask feather.
25. pixel + vector real/combined mask.
26. group mask around a clipping span.

### Color / environment fixtures

27. embedded sRGB vs a non-sRGB RGB profile.
28. same source with `raw.topil(apply_icc=True)` vs `False`.
29. Photoshop `Blend RGB Colors Using Gamma` off/on at gamma 1.00.
30. Photoshop `Blend Text Colors Using Gamma` off/on.
31. 8-bit vs 16-bit common-mode pair.
32. 32-bpc supported-mode pair.

Each fixture should preserve:

```text
PSD hash
raw relevant bytes/tags
Semantic IR
Evaluation plan
reference origin and profile
renderer/version/settings
RGB + alpha metrics
transparent-RGB policy
claim level
```

---

## 19. Priority relative to the active PARITY program

Fresh main on 2026-09-03 says the active task remains `PARITY-004`. The current Goal explicitly orders:

```text
P4-08 load/readback
-> deterministic Fusion micro renders
-> P4-09 real Fusion/reference baseline
-> smallest evidence-driven repair
```

P4-08 has recorded ordinary Fusion load/readback PASS, but no pixel-reference claim in that evidence.

Therefore this research should **not** trigger a broad architecture or dependency rewrite before the first required host/pixel baseline. The highest-value use is:

1. keep the current P4 lowering fixed long enough to obtain the baseline;
2. use this semantic matrix to classify any diff;
3. reduce material differences to a tiny fixture;
4. change only the causal boundary;
5. after the baseline, separately evaluate `psd-tools 1.19` as an upstream parser/raster/compositor upgrade.

This preserves causal evidence instead of changing the renderer, dependency, graph, and color path at once.

---

## 20. Strongest conclusions from this research

### CONFIRMED

- Photoshop group Pass Through and isolated group modes imply different backdrop scopes.
- Overall opacity and Fill are distinct semantics.
- Clipping is a same-parent ordered span with a base coverage relationship.
- `Blend Clipped Layers As Group` changes the blend scope of the clipping span and defaults enabled in Photoshop UI behavior.
- Advanced blending options (`infx`, transparency-shape behavior, mask-hides-effects, channel restrictions, Blend If) can change pixels independently of the ordinary blend-mode name.
- Knockout introduces shallow/deep backdrop stopping rules.
- Photoshop exposes an RGB blend-gamma Color Setting that changes composite data.
- 32-bpc Photoshop supports only a restricted blend-mode surface.
- current `psd-tools 1.19` materially improved Photoshop-facing compositing but still leaves `clbl` and `infx` TODOs and does not cover every advanced semantic.
- current PSD2Fusion asset materialization uses `topil()` with ICC conversion enabled and normalizes into new RGBA PNG canvases.
- current real reference PSD/PNG have matching ICC payloads and exact canvas dimensions; the reference alpha is fully opaque.

### INFERENCE / DESIGN CONSEQUENCE

- “Photoshop parity” needs an Evaluation IR/backdrop-scope model, not only a PSD-to-Fusion blend-name map.
- Unsupported advanced blending state must be detected before broad parity can be claimed.
- color/profile/gamma/alpha policy must be part of a pixel-proof record.
- psd-tools should remain a parser/cross-check implementation, not the semantic oracle.
- the current active P4 baseline should be completed before adopting 1.19 or redesigning the lowering, so causal attribution remains possible.

### OPEN

- exact fractional-alpha equations for every `clbl=false` interaction;
- exact base/member Fill placement in all special blend modes;
- whether Photoshop's effective RGB blend-gamma preference is sufficiently serialized in PSD metadata to reproduce authoring behavior from the file alone;
- exact effect ordering for every `infx`/`tsly`/mask-hides-effects combination;
- mask-feather parity between Photoshop, psd-tools, and Fusion;
- host-specific premult/transparent-RGB behavior through Fusion Loader, Merge, transform/filtering, and output.

These open items should be resolved by deterministic micro-fixtures and exact host/reference evidence rather than by extending prose assumptions.
