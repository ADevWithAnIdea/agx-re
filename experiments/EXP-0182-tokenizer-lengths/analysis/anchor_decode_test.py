#!/usr/bin/env python3
"""EXP-0182 -- THE ANCHOR DECODE TEST.  A regression test with teeth.

`roundtrip_test.py` is NOT an emitter gate: EXP-0170 re-implemented the pre-fix
OR-only assembler (which could not clear a bit) and the repo's own round trip passed
173/173; EXP-0173 showed it also passes with two operands swapped.  It is symmetric --
a defect present on both sides cancels.

This test is asymmetric.  It takes byte strings that REAL HARDWARE EXECUTED CORRECTLY,
committed in experiments' raw/, and asserts that our tokenizer decodes them to the
descriptor they were dispatched as, at that descriptor's declared length.  A tokenizer
that cannot read back an encoding our own GPU already accepted is wrong, and no
symmetric check can see it.

The five DEF-0181-2 anchors are pinned explicitly as MUST-PASS (they are the reason
this experiment exists); the remaining anchors from analysis/anchors.json are checked
as a regression corpus and reported with their committed baseline status, so a future
change that breaks one is visible.

Exit status: 0 iff every MUST-PASS anchor decodes AND no anchor that passed at the
EXP-0182 baseline has started failing.

Usage:
  python3 analysis/anchor_decode_test.py            # test tools/agx-isa
  python3 analysis/anchor_decode_test.py --tree DIR # test a candidate tree
  python3 analysis/anchor_decode_test.py --write-baseline
CLEAN-ROOM: pure analysis over our own db.json + our own committed raw.
"""
import importlib.util, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXPDIR = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(EXPDIR, "..", ".."))
BASELINE = os.path.join(HERE, "anchor_decode_baseline.json")

# ---------------------------------------------------------------------------
# MUST-PASS: the five DEF-0181-2 descriptors whose HW-VALIDATED anchor did not
# tokenize, plus the byte0==0x11 sibling `cvt_f2h` as the untouched control.
# Each `bytes` string is quoted from the cited experiment's committed raw/; the
# `raw` path is the file it was read from and `evidence` its outcome record.
# ---------------------------------------------------------------------------
MUST_PASS = [
    {"mnemonic": "bf_add_dst", "bytes": "21001c001100c081", "length": 8,
     "raw": "experiments/EXP-0156-g17p-emit-cf-mem/raw/g17p-20260830-bf03/sweep.jsonl",
     "target": "G17P",
     "evidence": 'outcome=ok match=true carrier=bfadd note="native bfloat ADD, host oracle '
                 '= exact bf16 of a+b"; also raw_sites.bfadd = [bf_add_dst, off 32, this hex]'},
    {"mnemonic": "bf_fma_dst", "bytes": "21001e0086041000c081", "length": 10,
     "raw": "experiments/EXP-0156-g17p-emit-cf-mem/raw/g17p-20260830-bf03/sweep.jsonl",
     "target": "G17P",
     "evidence": 'outcome=ok match=true carrier=bffma note="native bfloat FMA, host oracle '
                 '= exact bf16 of a*b+c"'},
    {"mnemonic": "hminmax", "bytes": "22001c0010c0", "length": 6,
     "raw": "experiments/EXP-0156-g17p-emit-cf-mem/raw/g17p-20260830-bf03/sweep.jsonl",
     "target": "G17P",
     "evidence": 'outcome=ok match=true carrier=hmax note="native fp16 MAX, host oracle '
                 '= exact fp16 of max(a,b)"'},
    {"mnemonic": "cvt_bf16", "bytes": "0101148105024000", "length": 8,
     "raw": "experiments/EXP-0162-g17p-pack-and-splices/raw/g17p_20260829_run01__cvt_bf16/sweep.jsonl",
     "target": "G17P",
     "evidence": 'outcome=ok match=true carrier=c_f2bf note="unmutated carrier" (+30 SEM '
                 'vectors ok); same bytes also ok on M4 in EXP-0144'},
    {"mnemonic": "cvt_f2h_dst", "bytes": "c10114810402", "length": 6,
     "raw": "experiments/EXP-0162-g17p-pack-and-splices/raw/g17p_20260829_run01__cvt_f2h_dst/sweep.jsonl",
     "target": "G17P",
     "evidence": 'outcome=ok match=true carrier=c_f2h_dst note="unmutated carrier"'},
    {"mnemonic": "cvt_f2h", "bytes": "110114810402", "length": 6,
     "raw": "CONTROL -- the byte0==0x11 dst-r1 sibling. Decoded correctly BEFORE the fix; "
            "must still decode after it.",
     "target": "G17P/M4", "evidence": "control"},
]


def load(tree):
    tree = os.path.abspath(tree)
    spec = importlib.util.spec_from_file_location(
        "isadb_adt_%x" % (abs(hash(tree)) & 0xffffffff), os.path.join(tree, "isadb.py"))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def check(m, mn, hexs, want_len):
    buf = bytes.fromhex(hexs)
    try:
        L = m.instr_length(buf, 0)
    except Exception as e:
        L = "ERR:%s" % type(e).__name__
    try:
        rec, LL = m.decode_one(buf, 0)
        got = rec["mnemonic"]
    except Exception as e:
        got, LL = "<%s>" % type(e).__name__, None
    return {"len": L, "mnemonic": got, "pass": (got == mn and L == want_len)}


def main():
    tree = os.path.join(REPO, "tools", "agx-isa")
    if "--tree" in sys.argv:
        tree = sys.argv[sys.argv.index("--tree") + 1]
    m = load(tree)

    print("== MUST-PASS: the five DEF-0181-2 anchors + the cvt_f2h control "
          "(tree: %s)" % os.path.relpath(os.path.abspath(tree), REPO))
    must_fail = []
    for a in MUST_PASS:
        r = check(m, a["mnemonic"], a["bytes"], a["length"])
        print("  [%s] %-14s %-22s want len=%-2d -> len=%-6s decoded=%s"
              % ("PASS" if r["pass"] else "FAIL", a["mnemonic"], a["bytes"],
                 a["length"], r["len"], r["mnemonic"]))
        if not r["pass"]:
            must_fail.append(a["mnemonic"])

    anchors = json.load(open(os.path.join(HERE, "anchors.json")))["anchors"]
    results = {}
    for a in anchors:
        r = check(m, a["mnemonic"], a["bytes"], a["declared_length"])
        results["%s/%s" % (a["mnemonic"], a["bytes"])] = r["pass"]
    npass = sum(1 for v in results.values() if v)
    print("== REGRESSION CORPUS: %d committed HW anchors, %d decode to themselves "
          "at the declared length" % (len(results), npass))

    if "--write-baseline" in sys.argv:
        json.dump(results, open(BASELINE, "w"), indent=1, sort_keys=True)
        print("wrote", os.path.relpath(BASELINE, REPO))
        return 0

    regressions = []
    if os.path.exists(BASELINE):
        base = json.load(open(BASELINE))
        regressions = sorted(k for k, v in base.items() if v and not results.get(k))
        fixed = sorted(k for k, v in results.items() if v and not base.get(k))
        print("   vs baseline: %d newly FIXED, %d REGRESSED" % (len(fixed), len(regressions)))
        for k in fixed:
            print("     FIXED     ", k)
        for k in regressions:
            print("     REGRESSED ", k)
    else:
        print("   (no baseline file; run with --write-baseline)")

    bad = bool(must_fail) or bool(regressions)
    print("== %s" % ("FAIL: " + ", ".join(must_fail + regressions) if bad else "ALL PASS"))
    return 1 if bad else 0


sys.exit(main())
