# PARITY-003 deterministic compositing fixtures

`scripts/parity/parity003.py` owns the small, reproducible software matrix for
the core compositing contract.  It is deliberately independent of
`psd-tools`, Resolve and Photoshop so a verifier can recompute every expected
pixel from Git.

Generate and validate it in an ignored directory:

```powershell
python .\scripts\parity\parity003.py generate --output .\.local\parity003-fixtures
python .\scripts\parity\parity003.py validate --fixtures .\.local\parity003-fixtures
```

The matrix contains 1,983 per-pixel cases for Normal, Multiply, Linear Dodge
and Overlay.  Each mode covers transparent (including non-zero transparent
RGB), black, white, gray, saturated, partial-alpha and gradient backdrops;
source alpha `0/.125/.25/.375/.5/.625/.75/.875/1`; and opacity
`0/.25/.5/.75/1`.  Additional rows isolate the declared linear-sRGB boundary,
Linear Dodge clamp/over-range behavior, ordinary opacity, isolated-group
opacity, nested boundaries, and fractional-alpha premultiply round-trips.

The oracle uses straight RGBA at the API boundary, evaluates a separable blend
in the explicitly named working space, then performs one premultiplied
source-over step.  A zero-alpha backdrop is canonicalized to RGB black and a
source remains unblended where the backdrop is transparent.  The generated
PNG profile is a byte-stable sRGB ICC profile; no implicit transform is made.

Validation calls the PARITY-001 `compare_images` harness and checks the
metamorphic invariants (opacity-zero and source-alpha-zero no-ops, local group
independence, canonical zero-alpha unpremultiply, and no premultiplied edge
fringe).  The generated `host/` candidates are Resolve inputs only.  Loading a
`.comp`, finding its Merge controls, or a successful graph parse is not a
promotion claim.  `scripts/parity/run_parity003_host.ps1` removes stale Saver
outputs, runs the bounded Fusion probe, and requires a fresh Saver output plus
the PARITY-001 comparator to return `PASS` for every candidate; otherwise it
records `BLOCKED`.

The strict capability registry in `psd2fusion/capabilities.py` therefore keeps
all four modes and opacity/group operations `unverified` until one evidence
packet contains Photoshop/reference pixels and an actual Resolve/Fusion render
tied to the exact candidate commit, host versions, color settings, ICC bytes,
alpha contract and quantitative RGBA/alpha metrics.  Unknown modes are
rejected; the compiler never changes them to Normal.
