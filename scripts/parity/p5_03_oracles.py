"""PARITY-005 P5-03 rival clbl=false oracles H1-H5 (offline, independent).

Read-only semantics proposal. No import from psd2fusion.compositing or
psd2fusion.fusion_comp (circularity ban). Straight-RGB + source-over
conventions mirror docs/COMPOSITING_CONTRACT.md B/M/S/D separation.

Blend basis (own implementation):
  Normal(d,s)      = s
  Multiply(d,s)    = d*s
  Screen(d,s)      = d+s-d*s
  LinearDodge(d,s) = d+s            (clamped to [0,1] per stage)
  Overlay(d,s)     = 2*d*s          if d <= 0.5
                   = 1-2*(1-d)*(1-s) otherwise
Outer composite Over(D,(s,sa),F):
  b  = blend(D_rgb,s,F)
  bs = (1-Ad)*s + Ad*b
  Ao = sa + Ad*(1-sa); if Ao==0: return (0,0,0,0)
  Co = (sa*bs + Ad*(1-sa)*D_rgb)/Ao
Opacity folded once into sa; outer calls use opacity 1.0 (no double-apply).
Transparent RGB canonical_zero; per-stage clamp [0,1]; finite guards.
"""
from __future__ import annotations

import math

MODES = ("Normal", "Multiply", "Screen", "Linear Dodge", "Overlay")


def _finite(x, label):
    x = float(x)
    if not math.isfinite(x):
        raise ValueError("%s must be finite" % label)
    return x


def _clamp01(x):
    return max(0.0, min(1.0, x))


def _check_rgba(p, label):
    if len(p) != 4:
        raise ValueError("%s must be RGBA" % label)
    r, g, b, a = (_finite(v, "%s[%d]" % (label, i)) for i, v in enumerate(p))
    return (_clamp01(r), _clamp01(g), _clamp01(b), max(0.0, min(1.0, a)))


def _blend_channel(d, s, mode):
    if mode == "Normal":
        return s
    if mode == "Multiply":
        return d * s
    if mode == "Screen":
        return d + s - d * s
    if mode == "Linear Dodge":
        return d + s
    if mode == "Overlay":
        return 2.0 * d * s if d <= 0.5 else 1.0 - 2.0 * (1.0 - d) * (1.0 - s)
    raise ValueError("unsupported mode %s" % mode)


def _blend_rgb(d_rgb, s_rgb, mode):
    if mode not in MODES:
        raise ValueError("unsupported mode %s" % mode)
    out = tuple(_blend_channel(d_rgb[i], s_rgb[i], mode) for i in range(3))
    return tuple(_clamp01(v) for v in out)


def _over(backdrop, src_rgb, src_alpha_eff, mode):
    d_rgb = backdrop[:3]
    ad = backdrop[3]
    b = _blend_rgb(d_rgb, src_rgb, mode)
    bs = tuple((1.0 - ad) * src_rgb[i] + ad * b[i] for i in range(3))
    ao = src_alpha_eff + ad * (1.0 - src_alpha_eff)
    ao = max(0.0, min(1.0, ao))
    if ao <= 0.0:
        return (0.0, 0.0, 0.0, 0.0)
    co = tuple(
        (src_alpha_eff * bs[i] + ad * (1.0 - src_alpha_eff) * d_rgb[i]) / ao
        for i in range(3)
    )
    return (co[0], co[1], co[2], ao)


def h1_local_span_group(backdrop, base, members, base_mode="Normal", base_opacity=1.0):
    """H1 null: local prog stack, alpha fixed M, base mode/opacity once outer."""
    d = _check_rgba(backdrop, "backdrop")
    b = _check_rgba(base, "base")
    m_cov = b[3]
    local = b[:3]
    q_b = max(0.0, min(1.0, _finite(base_opacity, "base_opacity")))
    if m_cov <= 0.0:
        local = (0.0, 0.0, 0.0)
    else:
        for j, (pix, mode, op) in enumerate(members):
            mp = _check_rgba(pix, "member[%d]" % j)
            q = max(0.0, min(1.0, _finite(op, "member[%d].opacity" % j)))
            sa = mp[3] * q
            if sa <= 0.0:
                continue
            bl = _blend_rgb(local, mp[:3], mode)
            local = tuple(_clamp01(sa * bl[i] + (1.0 - sa) * local[i]) for i in range(3))
    return _over(d, local, m_cov * q_b, base_mode)


def h2_progressive_outer(backdrop, base, members, base_mode="Normal", base_opacity=1.0):
    """H2: R0=Over(D,B,Fb,qb); Ji=(Ci,Ai*qi*M); Ri=Over(Ri-1,Ji,Fi)."""
    d = _check_rgba(backdrop, "backdrop")
    b = _check_rgba(base, "base")
    q_b = max(0.0, min(1.0, _finite(base_opacity, "base_opacity")))
    m_cov = b[3]
    r = _over(d, b[:3], m_cov * q_b, base_mode)
    for j, (pix, mode, op) in enumerate(members):
        mp = _check_rgba(pix, "member[%d]" % j)
        q = max(0.0, min(1.0, _finite(op, "member[%d].opacity" % j)))
        r = _over(r, mp[:3], mp[3] * q * m_cov, mode)
    return r


def h3_independent_outer(backdrop, base, members, base_mode="Normal", base_opacity=1.0):
    """H3: Ti=Over(D,Mi,Fi) vs FIXED D; Ui=(Ti_rgb,Ti_a*M); Ri=Over(Ri-1,Ui,Normal)."""
    d = _check_rgba(backdrop, "backdrop")
    b = _check_rgba(base, "base")
    q_b = max(0.0, min(1.0, _finite(base_opacity, "base_opacity")))
    m_cov = b[3]
    r = _over(d, b[:3], m_cov * q_b, base_mode)
    for j, (pix, mode, op) in enumerate(members):
        mp = _check_rgba(pix, "member[%d]" % j)
        q = max(0.0, min(1.0, _finite(op, "member[%d].opacity" % j)))
        t = _over(d, mp[:3], mp[3] * q, mode)
        u_a = t[3] * m_cov
        r = _over(r, t[:3], u_a, "Normal")
    return r


def h4_permember_base(backdrop, base, members, base_mode="Normal", base_opacity=1.0):
    """H4: Li=(Fi(B,Ci),Ai*qi*M); Ri=Over(Ri-1,(Li,Li_a*qb),Fb). Fb/qb N+1 times."""
    d = _check_rgba(backdrop, "backdrop")
    b = _check_rgba(base, "base")
    q_b = max(0.0, min(1.0, _finite(base_opacity, "base_opacity")))
    m_cov = b[3]
    r = _over(d, b[:3], m_cov * q_b, base_mode)
    for j, (pix, mode, op) in enumerate(members):
        mp = _check_rgba(pix, "member[%d]" % j)
        q = max(0.0, min(1.0, _finite(op, "member[%d].opacity" % j)))
        l_rgb = _blend_rgb(b[:3], mp[:3], mode)
        r = _over(r, l_rgb, mp[3] * q * m_cov * q_b, base_mode)
    return r


def h5_matte_only(backdrop, base, members, base_mode="Normal", base_opacity=1.0):
    """H5: transparent seed; Ji=(Ci,Ai*qi*M); Normal prog; Over(D,Sn,Normal)."""
    d = _check_rgba(backdrop, "backdrop")
    b = _check_rgba(base, "base")
    m_cov = b[3]
    s = (0.0, 0.0, 0.0, 0.0)
    for j, (pix, mode, op) in enumerate(members):
        mp = _check_rgba(pix, "member[%d]" % j)
        q = max(0.0, min(1.0, _finite(op, "member[%d].opacity" % j)))
        _ = mode  # H5 ignores member mode by definition (Normal stack only)
        s = _over(s, mp[:3], mp[3] * q * m_cov, "Normal")
    return _over(d, s[:3], s[3], "Normal")


REGISTRY = {
    "H1": h1_local_span_group,
    "H2": h2_progressive_outer,
    "H3": h3_independent_outer,
    "H4": h4_permember_base,
    "H5": h5_matte_only,
}


def run_oracle(hypothesis_id, backdrop, base, members, base_mode="Normal", base_opacity=1.0):
    fn = REGISTRY[hypothesis_id]  # KeyError = unknown hypothesis (fail-closed)
    return fn(backdrop, base, members, base_mode, base_opacity)


def determinism_guard(cases, repeats=3):
    """Re-run every (hid, fixture) `repeats` times; raise on any divergence."""
    for hid, fn in sorted(REGISTRY.items()):
        for fid, kw in sorted(cases.items()):
            first = fn(**kw)
            for _ in range(repeats - 1):
                again = fn(**kw)
                if any(abs(a - b) > 0.0 for a, b in zip(first, again)):
                    raise AssertionError("nondeterministic %s %s" % (hid, fid))
    return True
