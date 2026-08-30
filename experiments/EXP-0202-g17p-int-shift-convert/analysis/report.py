#!/usr/bin/env python3
"""EXP-0202 human-readable per-field report, re-derived from raw on every run.

    python3 analysis/report.py raw/<runA> raw/<runB>

Everything printed here is recomputed from the append-only `raw/`; nothing is
read back from a verdicts file. Exact numerators and denominators only -- never a
percentage alone (RE_EXPERIMENT_PROCESS_CORRECTIONS.md section 5).
"""
import collections
import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
NORM = {"unexpected_ok": "ok"}     # same hardware observation, different prediction


def load(d):
    return [json.loads(l) for l in (Path(d) / "sweep.jsonl").read_text().splitlines() if l.strip()]


def rng(xs):
    xs = sorted(xs)
    if not xs:
        return "none"
    out, s, p = [], xs[0], xs[0]
    for x in xs[1:]:
        if x == p + 1:
            p = x
            continue
        out.append((s, p))
        s = p = x
    out.append((s, p))
    return ",".join("%d" % a if a == b else "%d-%d" % (a, b) for a, b in out)


def key(r):
    o = r.get("observed") or {}
    return (NORM.get(r["outcome"], r["outcome"]), tuple(o.get("vals_u32") or []))


def main():
    A, B = load(sys.argv[1]), load(sys.argv[2])
    ia = {(r.get("arm"), r.get("value")): r for r in A if r.get("role") not in (None, "baseline")}
    ib = {(r.get("arm"), r.get("value")): r for r in B if r.get("role") not in (None, "baseline")}
    common = sorted(set(ia) & set(ib))
    agree = sum(1 for k in common if key(ia[k]) == key(ib[k]))
    print("cross-run: %d shared cases, %d agree, %d disagree"
          % (len(common), agree, len(common) - agree))
    dis = collections.Counter(k[0].split("/")[0] for k in common if key(ia[k]) != key(ib[k]))
    print("disagreements by group:", dict(dis))

    def arms_of(pred):
        return sorted({r["arm"] for r in A if r.get("arm") and pred(r)})

    print("\n== shift_amt_move.src_flag : profile over the source index, both flags ==")
    for c in sorted({r["carrier"] for r in A if r.get("field") == "_byte1_composite"}):
        d = {r["value"]: key(r) for r in A if r.get("field") == "_byte1_composite"
             and r["carrier"] == c}
        e = {r["value"]: key(r) for r in B if r.get("field") == "_byte1_composite"
             and r["carrier"] == c}
        n = same = 0
        for i in range(128):
            if i in d and (i | 0x80) in d and i in e and (i | 0x80) in e:
                n += 1
                if d[i] == d[i | 0x80] and e[i] == e[i | 0x80]:
                    same += 1
        print("  %-10s indices where flag=0 and flag=1 are IDENTICAL in BOTH runs: %d/%d"
              % (c, same, n))

    print("\n== b_alu10_lo7.src_flag : the same-dimension positive control ==")
    for k in sorted(k for k in common if k[0].startswith("BALU") and "src_flag" in k[0]):
        r = ia[k]
        print("  %-26s v=%d  %-13s  identical-across-values=%s"
              % (k[0], k[1], r["outcome"],
                 key(ia[(k[0], 0)]) == key(ia[(k[0], 1)]) if (k[0], 0) in ia and (k[0], 1) in ia else "?"))

    print("\n== ibitcount.cache ==")
    for arm in arms_of(lambda r: r.get("instr") == "ibitcount" and r.get("field") == "cache"):
        if (arm, 0) in ia and (arm, 1) in ia and (arm, 0) in ib:
            m = key(ia[(arm, 0)]) != key(ia[(arm, 1)])
            m2 = key(ib[(arm, 0)]) != key(ib[(arm, 1)])
            print("  %-24s base=%s  moved_runA=%s moved_runB=%s  v0=%s v1=%s"
                  % (arm, ia[(arm, 0)].get("baseline_field_value"), m, m2,
                     ia[(arm, 0)]["outcome"], ia[(arm, 1)]["outcome"]))

    print("\n== ibitcount.dst : delivery set and the hazard wall ==")
    for arm in arms_of(lambda r: r.get("instr") == "ibitcount" and r.get("field") == "dst"):
        va = [k[1] for k in common if k[0] == arm]
        ok = [v for v in va if NORM.get(ia[(arm, v)]["outcome"], ia[(arm, v)]["outcome"]) == "ok"
              and NORM.get(ib[(arm, v)]["outcome"], ib[(arm, v)]["outcome"]) == "ok"]
        fl = [v for v in va if ia[(arm, v)]["outcome"] == "fault"
              and ib[(arm, v)]["outcome"] == "fault"]
        print("  %-22s base=%-3s  reproduces_in_BOTH=%s  faults_in_BOTH(%d)=%s"
              % (arm, ia[(arm, va[0])].get("baseline_field_value"), ok, len(fl), rng(fl)))

    print("\n== irotate.operands byte+6 : the EXACT rotate-amount predictor ==")
    for arm in arms_of(lambda r: r.get("sub") == "byte+6"):
        mod = [k[1] for k in common if k[0] == arm
               and (ia[k].get("oracle") or {}).get("class") == "exact"]
        hit = [v for v in mod if ia[(arm, v)]["outcome"] == "ok" and ib[(arm, v)]["outcome"] == "ok"]
        print("  %-28s modelled=%d  matched_the_exact_vector_in_BOTH_runs=%d  misses=%s"
              % (arm, len(mod), len(hit), rng([v for v in mod if v not in hit])))

    print("\n== irotate.operands byte+6 : the amount recovered INDEPENDENTLY of the model ==")
    print("   (for each aligned value, search all 32 K for one whose rotate-LEFT-by-K vector")
    print("    reproduces the observation; the codewords are asymmetric so left/right and every")
    print("    K are distinguishable. This does not use the pre-registered formula at all.)")
    sys.path.insert(0, str(EXP / "harness"))
    import carriers202 as CC          # noqa: E402
    for arm in arms_of(lambda r: r.get("sub") == "byte+6"):
        base = None
        rec = collections.OrderedDict()
        for k in common:
            if k[0] != arm:
                continue
            base = ia[k].get("baseline_field_value") if base is None else base
            if (k[1] & 3) != (base & 3):
                continue
            oa = (ia[k].get("observed") or {}).get("vals_u32")
            ob = (ib[k].get("observed") or {}).get("vals_u32")
            if oa is None or oa != ob:
                rec[k[1]] = None
                continue
            hit = None
            for K in range(32):
                vec = [CC.rotl(a, K) for a in CC.A_ROT]
                if ia[k].get("note", "") and False:
                    pass
                if "rot_alu" in arm:
                    vec = [((x * 3) + 7) & CC.M32 for x in vec]
                if oa == vec:
                    hit = K
                    break
            rec[k[1]] = hit
        got = {v: k for v, k in rec.items() if k is not None}
        fml = {v: k for v, k in got.items() if k == (32 - (v >> 2)) % 32}
        print("  %-28s aligned values=%d  a single rotate-LEFT amount recovered at %d of them "
              "(in BOTH runs); of those, %d match K = (32 - (byte+6 >> 2)) mod 32; distinct K = %d"
              % (arm, len(rec), len(got), len(fml), len(set(got.values()))))
        bad = [v for v in got if v not in fml]
        print("       values where a K was recovered but the formula disagrees: %s" % (bad or "none"))
        print("       values where NO single rotate amount reproduces the output: %s"
              % rng([v for v, k in rec.items() if k is None])[:110])

    print("\n== irotate.operands : the other four bytes, and the joint 40-bit arm ==")
    for arm in arms_of(lambda r: r.get("instr") == "irotate" and r.get("field") == "operands"
                       and r.get("sub") != "byte+6"):
        va = [k[1] for k in common if k[0] == arm]
        c = collections.Counter(NORM.get(ia[(arm, v)]["outcome"], ia[(arm, v)]["outcome"]) for v in va)
        ok = [v for v in va if NORM.get(ia[(arm, v)]["outcome"], ia[(arm, v)]["outcome"]) == "ok"]
        print("  %-30s n=%-4d %s  reproduces_at=%s"
              % (arm, len(va), dict(c), rng(ok) if len(ok) < 40 else "%d values" % len(ok)))

    print("\n== iunary (SYNTHESIZED 27 2d 22) ==")
    for arm in arms_of(lambda r: r.get("instr") == "iunary" and r.get("role") == "target"):
        va = [k[1] for k in common if k[0] == arm]
        g = collections.defaultdict(list)
        for v in va:
            g[NORM.get(ia[(arm, v)]["outcome"], ia[(arm, v)]["outcome"])].append(v)
        tok = collections.Counter((ia[(arm, v)].get("token") or {}).get("mnemonic") for v in va)
        print("  %-24s %s" % (arm, {k: len(v) for k, v in sorted(g.items())}))
        for k2, v2 in sorted(g.items()):
            mods = sorted({x % 8 for x in v2}), sorted({x % 4 for x in v2})
            print("       %-12s n=%-4d  value mod 8 -> %s   mod 4 -> %s"
                  % (k2, len(v2), mods[0], mods[1]))
        print("       tokenizes as: %s" % dict(tok))

    print("\n== cvt_f2i.b9 ==")
    for arm in arms_of(lambda r: r.get("field") == "b9"):
        va = [k[1] for k in common if k[0] == arm]
        c = collections.Counter(NORM.get(ia[(arm, v)]["outcome"], ia[(arm, v)]["outcome"]) for v in va)
        pay = {key(ia[(arm, v)]) for v in va} | {key(ib[(arm, v)]) for v in va}
        print("  %-24s n=%-4d %s  distinct (outcome,payload) across BOTH runs=%d"
              % (arm, len(va), dict(c), len(pay)))

    print("\n== cvt_f2i.signflag (H8): lane 7 = int(2^31 + 2^8), outside int32 ==")
    arm = "CVT/cvt_sgn#0/signflag"
    l7 = collections.defaultdict(list)
    for k in common:
        if k[0] != arm:
            continue
        o = ia[k].get("observed") or {}
        v = (o.get("vals_u32") or [None] * 8)
        if len(v) > 7 and key(ia[k]) == key(ib[k]):
            l7[v[7]].append(k[1])
    for val, vs in sorted(l7.items(), key=lambda x: -len(x[1])):
        print("  lane7 = 0x%08x  at %3d signflag values : %s"
              % (val, len(vs), rng(vs)[:110]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
