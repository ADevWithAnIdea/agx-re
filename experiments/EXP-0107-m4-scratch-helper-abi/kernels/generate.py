#!/usr/bin/env python3
"""Generate complete authored MSL sources for EXP-0107's scratch-pressure ladder.

Design (distinct from EXP-0041's manual-unroll `pressure_body`, chosen so
SOURCE TEXT SIZE stays constant regardless of pressure level K -- avoiding the
huge-source/slow-compile risk of writing K separate named scalars):

  float a[K];
  for (i = 0; i < K; ++i) a[i] = input[(gid*K + i) % 4096];   // seed, bounded input
  for (pass = 1; pass < n; ++pass) {                          // n is a runtime constant
      t = input[pass % 4096];
      for (i = 0; i < K; ++i) a[i] = fma(a[i], t, a[(i+1) % K]);
  }
  sum = reduce(a); out = sum;

`a[K]` is a `thread`-address-space (private, per-invocation) array. Every
element is written and read across a runtime-bounded (`n` from a constant
buffer, opaque at compile time) loop, so the compiler cannot statically prove
a smaller live set and cannot promote the whole array to registers once K
exceeds the ~96 x 32-bit GPR file (EXP-0020). The `% 4096` bound on every
input-buffer index keeps the INPUT buffer a fixed 16 KiB regardless of K or
grid size -- this matters: without it, a naive `input[gid*K+i]` indexing
scheme would require a `grid * K` - sized input allocation, which becomes
tens of GiB at this experiment's high-K/high-grid combinations and would
fail for a reason having nothing to do with scratch. `n=1` degenerates the
pass loop entirely (pure init+reduce, fastest safe correctness check); a
small number of cases use `n>1` for genuine repeated spill/fill traffic.

Clean-room: this file, and every generated .metal source, is 100% authored by
this project. No Apple code, header, or template is copied.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent

PRELUDE = "#include <metal_stdlib>\nusing namespace metal;\n\n"


def array_body(k, index_expr, out_stmt, indent="    "):
    # The per-pass update is a bounded contraction (convex combination of two
    # already-bounded elements plus a tiny scaled input term), not `fma`
    # growth: with n=1 (the default, degenerate correctness check) this loop
    # never executes, so it is irrelevant there. For the small number of
    # n>1 "hot" cases (genuine repeated spill/fill traffic), an
    # unboundedly-growing recurrence (plain `fma(a[i], t, a[i+1])` iterated
    # hundreds of times) drives every lane to +-inf within a few dozen
    # passes -- a numerical artifact of the authored kernel, not a hardware
    # or scratch-memory fault. The contraction keeps every element inside
    # the input value range for arbitrarily many passes while still reading
    # AND writing every element of `a` every pass (so the compiler cannot
    # prove a smaller live set and cannot eliminate the loop as dead code).
    lines = [
        f"float a[{k}];",
        f"for (uint i = 0u; i < {k}u; ++i) a[i] = input[(({index_expr}) * {k}u + i) % 4096u];",
        "for (uint pass = 1u; pass < n; ++pass) {",
        "    float t = input[pass % 4096u];",
        f"    for (uint i = 0u; i < {k}u; ++i) "
        f"a[i] = 0.5f * a[i] + 0.5f * a[(i + 1u) % {k}u] + t * 1e-6f;",
        "}",
        "float sum = 0.0f;",
        f"for (uint i = 0u; i < {k}u; ++i) sum += a[i];",
        out_stmt,
    ]
    return "\n".join(indent + l for l in lines)


def compute_source(k):
    body = array_body(k, "gid", "out[gid] = sum;")
    return PRELUDE + f'''kernel void k_main(device float *out [[buffer(0)]],
                   device const float *input [[buffer(1)]],
                   constant uint &n [[buffer(2)]],
                   uint gid [[thread_position_in_grid]]) {{
{body}
}}
'''


def vertex_source(k):
    body = array_body(k, "vid", "out.color = float4(sum * 0x1p-16f, 0.25f, 0.5f, 1.0f);")
    return PRELUDE + f'''struct VOut {{ float4 position [[position]]; float4 color; }};

vertex VOut v_main(device const float *input [[buffer(0)]],
                   constant uint &n [[buffer(1)]],
                   uint vid [[vertex_id]]) {{
    VOut out;
{body}
    float2 p = (vid == 0u) ? float2(-1.0f, -1.0f) :
               ((vid == 1u) ? float2(3.0f, -1.0f) : float2(-1.0f, 3.0f));
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}}

fragment float4 f_main(VOut in [[stage_in]]) {{ return in.color; }}
'''


def fragment_source(k):
    body = array_body(k, "pixel", "return float4(sum * 0x1p-16f, 0.25f, 0.5f, 1.0f);")
    return PRELUDE + f'''struct VOut {{ float4 position [[position]]; }};

vertex VOut v_main(uint vid [[vertex_id]]) {{
    VOut out;
    float2 p = (vid == 0u) ? float2(-1.0f, -1.0f) :
               ((vid == 1u) ? float2(3.0f, -1.0f) : float2(-1.0f, 3.0f));
    out.position = float4(p, 0.0f, 1.0f);
    return out;
}}

fragment float4 f_main(VOut in [[stage_in]],
                       device const float *input [[buffer(0)]],
                       constant uint &n [[buffer(1)]]) {{
    uint pixel = uint(in.position.y) * 8u + uint(in.position.x);
{body}
}}
'''


# K values used anywhere in casematrix.py. Kept in one place so the source
# tree and the case matrix cannot silently drift apart.
CS_K = (8, 32, 96, 192, 384, 768, 1536, 3072, 6144, 12288, 24576, 49152, 65430, 65440)
VS_FS_K = (96, 1536, 6144)


def main():
    written = []
    for k in CS_K:
        name = f"cs_k{k}.metal"
        (HERE / name).write_text(compute_source(k))
        written.append(name)
    for k in VS_FS_K:
        name = f"vs_k{k}.metal"
        (HERE / name).write_text(vertex_source(k))
        written.append(name)
        name = f"fs_k{k}.metal"
        (HERE / name).write_text(fragment_source(k))
        written.append(name)
    for name in sorted(written):
        print(f"wrote {name} ({(HERE / name).stat().st_size} bytes)")


if __name__ == "__main__":
    main()
