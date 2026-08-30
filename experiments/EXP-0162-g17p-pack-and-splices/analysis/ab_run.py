#!/usr/bin/env python3
"""EXP-0162 A/B: run the frozen metric set against the live tree and each variant.

Reports exactly the pair EXP-0148 gated on -- CLEAN FILES and STRICT LEFTOVER
BYTES over the 1080-file own-MSL corpus -- plus roundtrip_test.py pass/fail and
the per-descriptor firing deltas, and a FUNCTIONAL check: does the variant decode
the encodings the HARDWARE accepted in EXP-0162's own runs?

  python3 analysis/ab_run.py            -> analysis/ab/metrics.json
"""
import collections, importlib.util, io, json, os, runpy, sys, contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(EXP, "..", ".."))
HEXDIR = os.path.join(REPO, "experiments", "EXP-M4-13-full-corpus", "hex")
TREES = {"baseline": os.path.join(REPO, "tools", "agx-isa")}
for v in ("pixel_order", "vary_store", "both"):
    TREES[v] = os.path.join(EXP, "work", "cvar", v)


def load(d):
    d = os.path.abspath(d)
    spec = importlib.util.spec_from_file_location("isadb_%s" % abs(hash(d)),
                                                  os.path.join(d, "isadb.py"))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def corpus(m):
    clean = 0
    leftover = 0
    files = 0
    firings = collections.Counter()
    for fn in sorted(os.listdir(HEXDIR)):
        if not fn.endswith(".hex"):
            continue
        files += 1
        buf = bytes.fromhex("".join(open(os.path.join(HEXDIR, fn)).read().split()))
        off = 0
        n = len(buf)
        while off < n:
            try:
                rec, length = m.decode_one(buf, off)
            except Exception:
                break
            if not length:
                break
            firings[rec["mnemonic"]] += 1
            off += length
        leftover += n - off
        if off == n:
            clean += 1
    return {"files": files, "clean": clean, "leftover": leftover}, firings


def roundtrip(d):
    buf = io.StringIO()
    old = list(sys.path), list(sys.argv)
    sys.path.insert(0, os.path.abspath(d))
    sys.argv = [os.path.join(os.path.abspath(d), "roundtrip_test.py")]
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                runpy.run_path(sys.argv[0], run_name="__main__")
            except SystemExit:
                pass
    finally:
        sys.path, sys.argv = old
        for k in [k for k in sys.modules if k.startswith("isadb")]:
            pass
    t = buf.getvalue()
    return {"ok": t.count("[OK]"), "fail": t.count("[FAIL]"),
            "crash": t.count("Traceback")}, t


# ---- FUNCTIONAL check: encodings the hardware ACCEPTED in EXP-0162's own runs
HW_ACCEPTED = {
  # pixel_order: the compiler's own pair, plus the texture-barrier pair that
  # EXP-0162 run04 proved is behaviourally the SAME acquire/release pair, plus a
  # byte+4 value outside the old match constant that is pixel-exact on hardware.
  "071454500600": "pixel_order (acquire, compiler's own)",
  "070454d00600": "pixel_order (release, compiler's own)",
  "071454510e00": "pixel_order acquire == threadgroup_barrier(mem_texture) acquire (HW ok)",
  "070454d10e00": "pixel_order release == threadgroup_barrier(mem_texture) release (HW ok)",
  "071454500e00": "acquire with byte+4 = 0x0e (HW ok, undecodable under the old match)",
  "070454d00a00": "release with byte+4 = 0x0a (HW ok, undecodable under the old match)",
  # the corpus barrier encodings the hardware REFUSED as raster-order markers --
  # a correct match must NOT claim these
  "070454610900": "!compute threadgroup_barrier (HW: ordering LOST -- must stay tgbar)",
  "0702540c0200": "!fragment tile barrier (HW: ordering LOST -- must stay tgbar)",
  "070454840a00": "!device mem_fence (HW: ordering LOST -- must stay mem_fence)",
  # vary_store split
  "571454000001": "frag_sample_submit (6 bytes; bytes +6..+7 belong to the NEXT op)",
  "5746540400404a00": "vary_store (8 bytes, vertex form)",
}


def functional(m):
    out = {}
    for hexs, note in HW_ACCEPTED.items():
        b = bytes.fromhex(hexs)
        try:
            rec, length = m.decode_one(b, 0)
            out[hexs] = {"mnemonic": rec["mnemonic"], "length": length, "note": note}
        except Exception as e:
            out[hexs] = {"mnemonic": "<undecodable>", "length": None,
                         "error": str(e)[:80], "note": note}
    return out


def main():
    res = {}
    base_f = None
    for name, d in TREES.items():
        m = load(d)
        met, fir = corpus(m)
        rt, _ = roundtrip(d)
        res[name] = {"corpus": met, "roundtrip": rt, "functional": functional(m)}
        if name == "baseline":
            base_f = fir
        else:
            delta = {k: [base_f.get(k, 0), fir.get(k, 0)]
                     for k in set(base_f) | set(fir) if base_f.get(k, 0) != fir.get(k, 0)}
            res[name]["firing_delta"] = delta
        res[name]["firings_total"] = sum(fir.values())
    outp = os.path.join(EXP, "analysis", "ab", "metrics.json")
    os.makedirs(os.path.dirname(outp), exist_ok=True)
    json.dump(res, open(outp, "w"), indent=1)
    for name in TREES:
        r = res[name]
        print("%-12s corpus clean=%d leftover=%d  roundtrip OK=%d FAIL=%d crash=%d  tokens=%d"
              % (name, r["corpus"]["clean"], r["corpus"]["leftover"],
                 r["roundtrip"]["ok"], r["roundtrip"]["fail"], r["roundtrip"]["crash"],
                 r["firings_total"]))
        if "firing_delta" in r and r["firing_delta"]:
            print("   delta:", r["firing_delta"])
    print("\nFUNCTIONAL (does the tree decode what the HARDWARE accepted?)")
    for hexs, note in HW_ACCEPTED.items():
        row = "  %-18s %-62s" % (hexs, note[:62])
        for name in TREES:
            f = res[name]["functional"][hexs]
            row += " | %s:%s/%s" % (name[:4], f["mnemonic"][:20], f["length"])
        print(row)


main()
