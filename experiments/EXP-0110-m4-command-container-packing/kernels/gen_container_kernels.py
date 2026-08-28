#!/usr/bin/env python3
"""Generate authored MSL compute kernels for the EXP-0110 P0.7 container/
metadata resource-count sweep. Each kernel declares exactly N device buffers,
T textures, and S samplers (0-based indices), doing trivial, side-effect-free
work so the compiler cannot dead-code-eliminate the bindings. OWN-SHADER: all
source below is authored by this experiment; nothing here is copied from or
derived from any Apple binary.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def buf_kernel(name, nbuf):
    args = ["device float *b%d [[buffer(%d)]]" % (i, i) for i in range(nbuf)]
    args.append("uint i [[thread_position_in_grid]]")
    body_lines = ["  float acc = 0.0;"]
    for i in range(nbuf):
        body_lines.append("  acc += b%d[i];" % i)
    if nbuf:
        body_lines.append("  b0[i] = acc;")
    src = "#include <metal_stdlib>\nusing namespace metal;\n"
    src += "kernel void %s(%s) {\n%s\n}\n" % (name, ", ".join(args), "\n".join(body_lines) if nbuf else "  (void)i;")
    return src


def tex_kernel(name, ntex, nsamp):
    args = []
    for i in range(ntex):
        args.append("texture2d<float> t%d [[texture(%d)]]" % (i, i))
    for i in range(nsamp):
        args.append("sampler s%d [[sampler(%d)]]" % (i, i))
    args.append("device float *out [[buffer(0)]]")
    args.append("uint i [[thread_position_in_grid]]")
    body = ["  float acc = 0.0;"]
    for i in range(ntex):
        sidx = i % max(nsamp, 1)
        if nsamp:
            body.append("  acc += t%d.sample(s%d, float2(0.5, 0.5)).x;" % (i, sidx))
        else:
            body.append("  acc += t%d.read(uint2(0,0)).x;" % i)
    body.append("  out[i] = acc;")
    src = "#include <metal_stdlib>\nusing namespace metal;\n"
    src += "kernel void %s(%s) {\n%s\n}\n" % (name, ", ".join(args), "\n".join(body))
    return src


def pressure_kernel(name, k):
    """K live 32-bit accumulators, cyclic FMA -- same shape as EXP-0020's
    gen_int_pressure.py, reproduced here (authored fresh) to re-validate the
    field-0 GPR-footprint mapping inside this experiment's own container
    framework (sanity cross-check, not a new claim)."""
    lines = ["  float a[%d];" % k]
    for i in range(k):
        lines.append("  a[%d] = in[i] + %d.0;" % (i, i))
    for _ in range(2):
        for i in range(k):
            lines.append("  a[%d] = a[%d] * a[(%d)%%%d] + a[(%d)%%%d];" % (i, i, i + 1, k, i + 2, k))
    lines.append("  float s = 0.0;")
    for i in range(k):
        lines.append("  s += a[%d];" % i)
    lines.append("  out[i] = s;")
    src = "#include <metal_stdlib>\nusing namespace metal;\n"
    src += ("kernel void %s(device float *out [[buffer(0)]], "
            "device float *in [[buffer(1)]], uint i [[thread_position_in_grid]]) {\n%s\n}\n"
            % (name, "\n".join(lines)))
    return src


def main():
    out_dir = os.path.join(HERE, "generated")
    os.makedirs(out_dir, exist_ok=True)
    manifest = []
    for n in (0, 1, 2, 4, 8):
        name = "kbuf%d" % n
        path = os.path.join(out_dir, name + ".metal")
        with open(path, "w") as f:
            f.write(buf_kernel(name, n))
        manifest.append({"file": name + ".metal", "function": name, "kind": "buffers", "n": n})
    for t, s in ((0, 0), (1, 0), (1, 1), (2, 1), (4, 2)):
        name = "ktex%d_samp%d" % (t, s)
        path = os.path.join(out_dir, name + ".metal")
        with open(path, "w") as f:
            f.write(tex_kernel(name, t, s))
        manifest.append({"file": name + ".metal", "function": name, "kind": "textures",
                          "n_textures": t, "n_samplers": s})
    for k in (4, 32, 96):
        name = "kpress%d" % k
        path = os.path.join(out_dir, name + ".metal")
        with open(path, "w") as f:
            f.write(pressure_kernel(name, k))
        manifest.append({"file": name + ".metal", "function": name, "kind": "pressure", "k": k})
    with open(os.path.join(out_dir, "manifest.json"), "w") as f:
        import json
        json.dump(manifest, f, indent=2, sort_keys=True)
        f.write("\n")
    print("generated %d kernels into %s" % (len(manifest), out_dir))


if __name__ == "__main__":
    main()
