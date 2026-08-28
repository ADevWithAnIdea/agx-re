#!/usr/bin/env python3
"""EXP-0094 register-pressure differential-compilation generator (v3, FINAL).

History (see PROGRESS.md for exact timestamps):
  v1: junk read directly from `constant float* params`, consumed via a flat
      `sink += j[i]*const` reduction. Compiled to BYTE-IDENTICAL "main" for
      every N in {0..32}, with/without --no-fast-math. Cause: the reduction
      pattern is trivially recognized and collapsed.
  v2: replaced the flat reduction with a serially-dependent, non-uniform
      FMA/mul/max chain. STILL byte-identical "main" for every N. Cause
      (confirmed via agxparse.py --json region listing): every value in v1/v2
      derives ONLY from the `constant` address space, which MSL/AGX treats as
      provably uniform across the invocation group -- the ENTIRE computation
      (junk chain, bias/gradient operands, and even the sample instruction
      itself for the compute/grad kernel, which has no non-uniform input at
      all) was hoisted into the shader PREAMBLE ("_agc.main.constant_program",
      which DOES grow with N: 64/128/256/512 bytes for grad N=0/4/16/32), while
      "_agc.main" (the per-invocation body we were diffing) stayed fixed
      because it just references an already-computed preamble/uniform-register
      result. This is the SAME preloaded-uniform mechanism EXP-0016 already
      documented for texture width/height/mip-count queries.
  v3 (this file): forces the operand-under-test and every junk value to be
      GENUINELY per-invocation-varying, so the compiler cannot hoist them:
        - grad (compute): buffer indices are offset by
          `[[thread_position_in_grid]].x` (`params[tid.x + K]`). A per-thread
          SR is not a compile-time constant, so the load address -- and
          everything downstream of it -- cannot be proven uniform, REGARDLESS
          of the fact that our dispatch is always exactly 1 thread (the
          compiler has no visibility into dispatch size at compile time). This
          is exactly the "memory load feeding a float ALU instruction" shape
          `apple9_isa_explainer.md` prescribes for testing the consumer-route
          field, applied here as a uniformity-defeating technique instead.
        - bias (fragment): values are routed through a genuine per-vertex
          INTERPOLATED VARYING (all 3 triangle vertices write the SAME value,
          so the interpolated per-fragment result is numerically constant --
          but the FRAGMENT compiler has zero compile-time visibility into what
          the paired vertex stage will output, so a `[[stage_in]]` field is
          always treated as per-fragment-varying by construction). This is
          more principled than a position-arithmetic trick (an expression like
          `x*0.0` or `x-x` is ALWAYS uniform regardless of x's runtime value,
          so a real optimizer is CORRECT to hoist it -- not a bug to route
          around by obfuscation).
  Verified (quick standalone probes, not committed as their own experiment
  artifacts): grad "main" grew 68 -> 246 bytes; bias "main" grew 116 -> 286
  bytes, both with "constant_program" back down to the small fixed baseline.

Purpose (unchanged): find which (if any) AGX byte in or near the
texture-sample bundle varies with register pressure N, as a candidate for
"the register holding the coordinate / bias / gradient operand" in the
GENUINELY PER-LANE-VARYING case (the uniform-sourced case is now known to be a
DIFFERENT code path entirely -- see the note above -- and is reported
separately). OWN-SHADER-DIFF correlation evidence; the minimal-pair splice
test (regpair_*/regsplice_* kernels) supplies the HW-VALIDATED
downstream-consumer proof for whichever byte this correlation nominates.

CLEAN-ROOM: generates only our own MSL text. No Apple binary is touched here.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
KDIR = HERE.parent / "kernels" / "generated"
KDIR.mkdir(parents=True, exist_ok=True)

N_VALUES = [0, 1, 2, 4, 8, 12, 16, 24, 32]


def sink_chain(n, jexpr):
    """Serially-dependent, non-uniform FMA/mul/max chain over j0..j(n-1).
    jexpr(i) returns the MSL expression for junk value i."""
    if n == 0:
        return "    float sink = 0.0;", ""
    decls = "\n".join(f"    float j{i} = {jexpr(i)};" for i in range(n))
    lines = ["    float sink = j0;"]
    for i in range(1, n):
        op = i % 3
        if op == 0:
            lines.append(f"    sink = fma(sink, 1.0000{i % 7 + 1}f, j{i});")
        elif op == 1:
            lines.append(f"    sink = sink * j{i} - j{i - 1};")
        else:
            lines.append(f"    sink = max(sink, j{i}) + sink * 0.0001f;")
    return "\n".join(lines), decls


BIAS_TEMPLATE = """// EXP-0094 generated register-pressure probe (bias, N={n}), v3.
// analysis/gen_regpressure.py -- do not hand-edit. bias/junk values arrive as
// a per-vertex-interpolated varying (stage_in), NOT a direct constant-buffer
// read, so the fragment compiler cannot hoist them to the preamble -- see the
// v3 header note in this file for why v1/v2 failed.
#include <metal_stdlib>
using namespace metal;

struct VOut {{
    float4 position [[position]];
    float4 vbias [[user(locn0)]];   // x=uvScaleX y=uvScaleY z=biasVal w=unused
{jfields}
}};

vertex VOut vmain(uint vid [[vertex_id]], constant float *params [[buffer(0)]]) {{
    float2 p[3] = {{ float2(-1,-1), float2(3,-1), float2(-1,3) }};
    VOut o;
    o.position = float4(p[vid], 0, 1);
    o.vbias = float4(params[0], params[1], params[{bias_idx}], 0);
{jassign}
    return o;
}}

fragment float4 fmain(VOut in [[stage_in]],
                       texture2d<float> tex [[texture(0)]],
                       sampler s [[sampler(0)]]) {{
    float2 uv = in.position.xy * float2(in.vbias.x, in.vbias.y);
{decls}
{chain}
    float biasVal = in.vbias.z;
    float v = tex.sample(s, uv, bias(biasVal)).r;
    return float4(v, sink, 0, 1);
}}
"""

GRAD_TEMPLATE = """// EXP-0094 generated register-pressure probe (grad, N={n}), v3.
// analysis/gen_regpressure.py -- do not hand-edit. Every params[] read is
// offset by the per-thread SR `tid.x` (always 0 in our 1-thread dispatch, but
// NOT a compile-time constant), so the compiler cannot prove uniformity and
// cannot hoist to the preamble -- see the v3 header note in this file.
#include <metal_stdlib>
using namespace metal;

kernel void kmain(texture2d<float> tex [[texture(0)]],
                   sampler s [[sampler(0)]],
                   constant float *params [[buffer(0)]],
                   device float *out [[buffer(1)]],
                   uint2 tid [[thread_position_in_grid]]) {{
{decls}
{chain}
    float2 dx = float2(params[tid.x + {dx_idx}], params[tid.x + {dx_idx1}]);
    float2 dy = float2(params[tid.x + {dy_idx}], params[tid.x + {dy_idx1}]);
    float v = tex.sample(s, float2(0.5, 0.5), gradient2d(dx, dy)).r;
    out[0] = v;
    out[1] = sink;
}}
"""


def gen_bias(n):
    # varying slots: pack junk floats 4-per-float4, locn1..
    nslots = (n + 3) // 4
    jfields = "\n".join(f"    float4 vj{k} [[user(locn{k + 1})]];" for k in range(nslots))
    jassign_lines = []
    for k in range(nslots):
        comps = []
        for c in range(4):
            i = k * 4 + c
            comps.append(f"params[{4 + i}]" if i < n else "0")
        jassign_lines.append(f"    o.vj{k} = float4({', '.join(comps)});")
    jassign = "\n".join(jassign_lines)

    def jexpr(i):
        k, c = divmod(i, 4)
        comp = "xyzw"[c]
        return f"in.vj{k}.{comp}"

    chain, decls = sink_chain(n, jexpr)
    bias_idx = 2  # fixed slot (uv scale takes 0,1; bias always at params[2])
    return BIAS_TEMPLATE.format(n=n, jfields=jfields, jassign=jassign,
                                 decls=decls, chain=chain, bias_idx=bias_idx)


def gen_grad(n):
    def jexpr(i):
        return f"params[tid.x + {4 + i}]"

    chain, decls = sink_chain(n, jexpr)
    return GRAD_TEMPLATE.format(n=n, decls=decls, chain=chain,
                                 dx_idx=4 + n, dx_idx1=4 + n + 1,
                                 dy_idx=4 + n + 2, dy_idx1=4 + n + 3)


def main():
    manifest = []
    for n in N_VALUES:
        bp = KDIR / f"regpress_bias_n{n:02d}.metal"
        bp.write_text(gen_bias(n))
        gp = KDIR / f"regpress_grad_n{n:02d}.metal"
        gp.write_text(gen_grad(n))
        manifest.append({"n": n, "bias": bp.name, "grad": gp.name})
    print(f"wrote {2 * len(N_VALUES)} kernels to {KDIR}")
    for m in manifest:
        print(m)


if __name__ == "__main__":
    main()
