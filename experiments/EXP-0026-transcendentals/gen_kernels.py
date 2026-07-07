#!/usr/bin/env python3
# gen_kernels.py -- EXP-0026. Emit OUR OWN MSL kernels that exercise the
# transcendental / special-function lowerings (rcp, rsqrt, sqrt, div, sin, cos,
# tan, exp2, log2, exp, log, pow) plus fast::/precise:: namespace variants used
# to isolate the hardware ESTIMATE op from the Newton-Raphson refinement.
# CLEAN-ROOM: all source below is OURS; we compile it and disassemble only our
# own compiled bytes. No Apple binary is ever inspected.
import os
HERE = os.path.dirname(os.path.abspath(__file__))
KDIR = os.path.join(HERE, "kernels")
os.makedirs(KDIR, exist_ok=True)

HEADER = "#include <metal_stdlib>\nusing namespace metal;\n\n"

# (name, body-expr using a=in[0], b=in[1]).  one-arg kernels ignore b.
ONE = {
    # --- reciprocal / roots / division ---
    "rcp":        "1.0f / a[gid]",
    "rsqrt":      "rsqrt(a[gid])",
    "sqrt":       "sqrt(a[gid])",
    # --- fast:: (low-accuracy) variants: expected estimate-only or +1 NR ---
    "fast_rcp":   "fast::divide(1.0f, a[gid])",
    "fast_rsqrt": "fast::rsqrt(a[gid])",
    "fast_sqrt":  "fast::sqrt(a[gid])",
    # --- precise:: (full-accuracy) variants ---
    "prec_rcp":   "precise::divide(1.0f, a[gid])",
    "prec_rsqrt": "precise::rsqrt(a[gid])",
    "prec_sqrt":  "precise::sqrt(a[gid])",
    # --- transcendentals ---
    "sin":        "sin(a[gid])",
    "cos":        "cos(a[gid])",
    "tan":        "tan(a[gid])",
    "exp2":       "exp2(a[gid])",
    "log2":       "log2(a[gid])",
    "expe":       "exp(a[gid])",
    "loge":       "log(a[gid])",
    "exp10":      "exp10(a[gid])",
    "log10":      "log10(a[gid])",
    "fast_sin":   "fast::sin(a[gid])",
    "fast_cos":   "fast::cos(a[gid])",
    "fast_exp2":  "fast::exp2(a[gid])",
    "fast_log2":  "fast::log2(a[gid])",
    "prec_sin":   "precise::sin(a[gid])",
    "prec_exp2":  "precise::exp2(a[gid])",
    "prec_log2":  "precise::log2(a[gid])",
}
TWO = {
    "div":        "a[gid] / b[gid]",
    "pow":        "pow(a[gid], b[gid])",
    "powr":       "powr(a[gid], b[gid])",
    "fast_pow":   "fast::pow(a[gid], b[gid])",
    "prec_pow":   "precise::pow(a[gid], b[gid])",
    "fast_div":   "fast::divide(a[gid], b[gid])",
}

def emit(name, expr, two):
    sig = ("kernel void k(device const float* a [[buffer(0)]],\n"
           + ("               device const float* b [[buffer(1)]],\n" if two else "")
           + "               device float* out [[buffer(%d)]],\n" % (2 if two else 1)
           + "               uint gid [[thread_position_in_grid]]) {\n"
           + "    out[gid] = %s;\n}\n" % expr)
    with open(os.path.join(KDIR, name + ".metal"), "w") as f:
        f.write(HEADER + sig)

for n, e in ONE.items():
    emit(n, e, two=False)
for n, e in TWO.items():
    emit(n, e, two=True)

print("wrote", len(ONE) + len(TWO), "kernels to", KDIR)
