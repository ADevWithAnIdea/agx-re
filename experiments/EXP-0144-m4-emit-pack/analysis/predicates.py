#!/usr/bin/env python3
"""EXP-0144: exact predicate search for the bytes whose behaviour is NOT a single
bitmask, plus the measured format/source tables.

  python3 analysis/predicates.py --runs RUN [RUN2]

For every swept byte this searches, exhaustively and in order of simplicity:
  1. a 1-bit rule, 2. a 2-bit rule (all 4 patterns, AND/OR/XOR-shaped via the
  pattern set), 3. a 3-bit rule -- for the predicate "this value reproduced the
  instruction's documented result". The FIRST exact fit is reported. An emitter can
  use an exact predicate; it cannot use "192 of 256 worked".
Writes analysis/predicates.json.
"""
import argparse, collections, itertools, json, struct, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "harness"))
import casematrix as CM      # noqa: E402
import oracle as O           # noqa: E402


def load(run):
    """See verdicts.py::load_run -- same '+' merge, valid-beats-skipped semantics."""
    out = {}
    for part in run.split("+"):
        dirs = sorted(EXP.glob("raw/%s__*" % part)) or [EXP / "raw" / part]
        for d in dirs:
            f = d / "sweep.jsonl"
            if not f.exists():
                continue
            for line in f.read_text().splitlines():
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                prev = out.get(r["i"])
                if prev is None or (prev.get("validity") != "valid"
                                    and r.get("validity") == "valid"):
                    out[r["i"]] = r
    return out


def w(rec, k=0):
    if not rec.get("observed"):
        return None
    b = bytes.fromhex(rec["observed"])
    return struct.unpack("<I", b[4 * k:4 * k + 4])[0] if len(b) >= 4 * k + 4 else None


def exact_predicate(true_set, universe):
    """Smallest exact bit predicate for `true_set` over `universe`."""
    U = set(universe)
    T = set(true_set)
    if T == U:
        return {"form": "ALWAYS (every value executed reproduced the result: the byte "
                        "is INERT over the tested range)", "kind": "always"}
    if not T:
        return {"form": "NEVER (no value executed reproduced the result)", "kind": "never"}
    for nbits in (1, 2, 3):
        for bits in itertools.combinations(range(8), nbits):
            for pats in itertools.product([0, 1], repeat=nbits):
                # "value matches this exact bit pattern"
                sel = {v for v in U if all(((v >> b) & 1) == p for b, p in zip(bits, pats))}
                if sel == T:
                    return {"form": "bits %s == %s" % (list(bits), list(pats)),
                            "kind": "equality", "bits": list(bits), "pattern": list(pats)}
                if U - sel == T:
                    return {"form": "NOT (bits %s == %s)" % (list(bits), list(pats)),
                            "kind": "not_equality", "bits": list(bits), "pattern": list(pats)}
            # "any of these bits set" / "all of these bits set"
            anyset = {v for v in U if any((v >> b) & 1 for b in bits)}
            if anyset == T:
                return {"form": "ANY of bits %s set" % list(bits), "kind": "any_set",
                        "bits": list(bits)}
            allset = {v for v in U if all((v >> b) & 1 for b in bits)}
            if allset == T:
                return {"form": "ALL of bits %s set" % list(bits), "kind": "all_set",
                        "bits": list(bits)}
    return {"form": "no exact 1-3 bit predicate", "kind": "none"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", required=True)
    a = ap.parse_args()
    runs = [load(r) for r in a.runs]
    prim = runs[0]
    stable = set(prim)
    for other in runs[1:]:
        stable &= {i for i in other
                   if i in prim and other[i].get("observed") == prim[i].get("observed")
                   and other[i]["outcome"] == prim[i]["outcome"]
                   and other[i]["validity"] == "valid" and prim[i]["validity"] == "valid"}

    out = {"_runs": a.runs, "_n_stable": len(stable)}
    byb = collections.defaultdict(list)
    for i, r in prim.items():
        if r["arm"] == "F" and i in stable and r["validity"] == "valid":
            byb[(r["instr"], r["byte"])].append(r)

    for (instr, byte), recs in sorted(byb.items()):
        tgt = next(t for t in CM.TARGETS if t["mnem"] == instr)
        carrier, vec = tgt["carrier"], CM.FIXED[tgt["carrier"]][1]
        slot = CM.RESULT_SLOTS[carrier][0]
        want = CM.expect(carrier, vec)[slot]
        universe = sorted({r["value"] for r in recs})
        ok = {r["value"] for r in recs if w(r, slot) == want}
        pred = exact_predicate(ok, universe)
        e = {"n_executed": len(recs), "n_reproducing": len(ok),
             "exact_predicate_for_reproducing_the_result": pred}
        # measured model/source tables (what each value actually produced)
        models = {}
        for r in recs:
            got = w(r, slot)
            if got is None:
                continue
            for name, val in _models(carrier, vec).items():
                if got == val:
                    models.setdefault(name, []).append(r["value"])
        if len(models) > 1:
            e["measured_value_tables"] = {k: sorted(v)[:16] for k, v in sorted(models.items())}
        out["%s.byte%d" % (instr, byte)] = e

    (HERE / "predicates.json").write_text(json.dumps(out, indent=1, sort_keys=True))
    print("wrote analysis/predicates.json (%d bytes analysed, %d stable records)"
          % (len(out) - 2, len(stable)))


def _models(carrier, vec):
    m = {}
    if carrier == "c_unpack":
        for i in range(len(vec)):
            x, y = O.unpack_unorm2x16(vec[i]); sx, sy = O.unpack_snorm2x16(vec[i])
            m["unorm16_lo(v%d)" % i] = O.f32_bits(x)
            m["unorm16_hi(v%d)" % i] = O.f32_bits(y)
            m["snorm16_lo(v%d)" % i] = O.f32_bits(sx)
            m["snorm16_hi(v%d)" % i] = O.f32_bits(sy)
            m["unorm8_lo(v%d)" % i] = O.f32_bits((vec[i] & 0xFF) / 255.0)
            m["half_lo(v%d)" % i] = O.f32_bits(O.bits_f16(vec[i] & 0xFFFF))
    elif carrier == "c_pack":
        for i in range(len(vec)):
            for j in range(len(vec)):
                m["unorm2x16(v%d,v%d)" % (i, j)] = O.pack_unorm2x16(vec[i], vec[j])
                m["snorm2x16(v%d,v%d)" % (i, j)] = O.pack_snorm2x16(vec[i], vec[j])
    elif carrier in ("c_i2f", "c_i2f_src"):
        for i in range(len(vec)):
            m["i2f(v%d)" % i] = O.f32_bits(O.i2f(vec[i] & 0xFFFFFFFF))
    elif carrier == "c_f2i":
        for i in range(len(vec)):
            m["f2i(v%d)" % i] = O.f2i(vec[i])
    elif carrier in ("c_f2h", "c_f2h_dst", "c_f2bf"):
        for i in range(len(vec)):
            m["f2h(v%d)" % i] = O.f16_bits(vec[i])
            m["f2bf_rne(v%d)" % i] = O.f2bf_rne(vec[i])
            m["f2bf_trunc(v%d)" % i] = O.f2bf_trunc(vec[i])
    return m


if __name__ == "__main__":
    main()
