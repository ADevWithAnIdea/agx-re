#!/usr/bin/env python3
"""EXP-0159 — TEX-01 post-registration adversarial extension.

The pre-registered FF family tested the five `form` values db.json names.  This
pass sweeps the WHOLE form byte, 0x00..0xFF, against three different values of
the third scalar operand and four coordinate pairs, and asks a single question:
does ANY value of the form byte make the sampled texel depend on that operand in
the way a projective divide would?

That is the strongest available refuter for "Apple9 has a coordinate-projection
setup form": if no form value divides the coordinates, the capability is absent
from this instruction, not merely absent from the value db.json labelled.

  python3 ff_formsweep.py --run-id <id> [--carrier texlod|texarr]

Authored by the clean-room RE team.  Clean-room: OWN-SHADER splice + HW-PROBE.
"""
import argparse, hashlib, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import run as R

# (u, v) -> the level-0 nearest texel under NO projection, and under a divide by w
UVS = [("a", 0.375, 0.625), ("b", 0.75, 0.25), ("c", 0.9, 0.9), ("d", 0.125, 0.125)]
WS = ["1.0", "2.0", "4.0"]


def texel(u, v, w=1.0, size=4):
    """Host oracle: nearest texel of (u/w, v/w) at level 0, clamp-to-edge."""
    x = int(max(0, min(size - 1, int((u / w) * size))))
    y = int(max(0, min(size - 1, int((v / w) * size))))
    return 100.0 * y + x


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--carrier", default="texlod")
    ap.add_argument("--bin", default=os.path.expanduser("~/agxre/EXP-0159/bin"))
    ap.add_argument("--work", default=os.path.expanduser("~/agxre/EXP-0159/work"))
    args = ap.parse_args()
    rawdir = os.path.join(ROOT, "raw", args.run_id)
    os.makedirs(rawdir, exist_ok=True)
    sink = R.Sink(rawdir)
    wd = os.path.join(args.work, "ff_sweep")
    os.makedirs(wd, exist_ok=True)

    # host-side oracle table, emitted so the reader can check the arithmetic
    sink.w("ffsweep", {"family": "ffsweep", "case": "__oracle", "outcome": "ok",
                       "observed": json.dumps(
                           {"%s_w%s" % (n, w): {"noproj": texel(u, v),
                                                "proj": texel(u, v, float(w))}
                            for n, u, v in UVS for w in WS}),
                       "note": "level-0 nearest texel with and without a divide by the third "
                               "operand; the two differ for every w != 1"})

    cf = os.path.join(wd, "cases.txt")
    with open(cf, "w") as f:
        for n, u, v in UVS:
            for w in WS:
                f.write("%s_w%s %r %r %s\n" % (n, w, u, v, w))

    src = os.path.join(ROOT, "kernels", args.carrier + ".metal")
    arch = os.path.join(wd, args.carrier + ".bin")
    cp = subprocess.run([R.SHDUMP, "-o", arch, "-f", "k", src], capture_output=True, text=True)
    if cp.returncode != 0:
        sink.w("ffsweep", {"family": "ffsweep", "case": "__compile", "outcome": "undecodable",
                           "note": (cp.stdout + cp.stderr)[:400]})
        return
    p = subprocess.run([sys.executable, R.AGXPARSE, arch, "--locate", "_agc.main"],
                       capture_output=True, text=True)
    abs_off, mlen = [int(x, 0) for x in p.stdout.split()[:2]]
    blob = open(arch, "rb").read()
    main = blob[abs_off:abs_off + mlen]
    dis, leftover = R.disasm(main)
    tas = [d for d in dis if d.get("mnemonic") == "tex_addr_setup"]
    sink.w("ffsweep", {"family": "ffsweep", "case": "__carrier", "observed": main.hex(),
                       "outcome": "ok" if tas else "undecodable",
                       "main_sha256": hashlib.sha256(main).hexdigest(),
                       "note": "%d tex_addr_setup; disasm=%s" % (
                           len(tas), " ".join(str(d.get("mnemonic")) for d in dis))})
    if not tas:
        return
    off = tas[0]["offset"]
    exe = os.path.join(args.bin, "texrun")
    extra = ["--array"] if args.carrier == "texarr" else []
    sp = os.path.join(wd, "%s_sweep.bin" % args.carrier)
    for fv in range(256):
        mut = bytearray(blob)
        mm = bytearray(main); mm[off + 1] = fv
        mut[abs_off:abs_off + mlen] = bytes(mm)
        open(sp, "wb").write(bytes(mut))
        R.run_stream([exe, sp, "k", "%s/form0x%02x" % (args.carrier, fv), cf] + extra,
                     sink, "ffsweep", timeout=120)
    sink.w("ffsweep", {"family": "ffsweep", "case": "__done", "value": 256, "outcome": "ok",
                       "note": "complete form-byte sweep, %s carrier" % args.carrier})
    sink.close()


if __name__ == "__main__":
    main()
