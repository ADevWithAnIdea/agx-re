#!/usr/bin/env python3
"""EXP-0182 -- WORKED DEMONSTRATION (not applied): the one db.json change that closes
the fifth anchor, `cvt_bf16`.

After this experiment's length fix, `01 01 14 81 05 02 40 00` -- the byte string EXP-0162
dispatched on G17P and EXP-0144 on M4, `outcome: ok, match: true` against a host oracle --
is lengthed correctly at 8. It still does not decode to `cvt_bf16`, and NOT because of any
length rule: `db.json` gives `cvt_bf16` the match `[[0,4,1],[24,8,129],[32,8,1]]`, pinning
byte+4 to the single value 0x01, and the anchor carries 0x05. `decode_one` filters candidates
by `match`, so the descriptor cannot claim its own hardware-validated encoding.

EXP-0162 already measured that constant to be WRONG, not merely narrow: a dense 0..255 sweep
of byte+4 on the unmutated `cvt_bf16` carrier found 52 values that reproduce the convert, and
**0x01 is not among them**. EXP-0162 could not act on it because "instr_length() has no rule
at all for byte0 == 0x01, so cvt_bf16 cannot be lengthed and no match relaxation can reach
it. Db defect 28 must land first." **Db defect 28 is this experiment's `n1` patch.** The
prerequisite is now met.

This script builds the candidate in work/ ONLY -- it never writes tools/agx-isa/db.json,
which is the orchestrator's file -- and reports what changes.

Usage: python3 analysis/demo_cvt_bf16_dbfix.py
"""
import importlib.util, json, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXPDIR = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(EXPDIR, "..", ".."))
SRC = os.path.join(EXPDIR, "work", "cand_full")
DST = os.path.join(EXPDIR, "work", "demo_dbfix")
HEXDIR = os.path.join(REPO, "experiments", "EXP-M4-13-full-corpus", "hex")
ANCHOR = "0101148105024000"


def load(d, n):
    sp = importlib.util.spec_from_file_location(n, os.path.join(d, "isadb.py"))
    m = importlib.util.module_from_spec(sp)
    sys.modules[n] = m
    sp.loader.exec_module(m)
    return m


def corpus(m):
    clean = leftover = files = 0
    for fn in sorted(os.listdir(HEXDIR)):
        if not fn.endswith(".hex"):
            continue
        files += 1
        buf = bytes.fromhex("".join(open(os.path.join(HEXDIR, fn)).read().split()))
        off, n = 0, len(buf)
        while off < n:
            try:
                _, L = m.decode_one(buf, off)
            except Exception:
                break
            if not L:
                break
            off += L
        leftover += n - off
        if off == n:
            clean += 1
    return clean, files, leftover


def main():
    if not os.path.isdir(SRC):
        raise SystemExit("build work/cand_full first: python3 analysis/apply_fix.py "
                         "work/cand_full n1 r9 n2 n2b n2c n0c")
    if os.path.isdir(DST):
        shutil.rmtree(DST)
    shutil.copytree(SRC, DST, ignore=shutil.ignore_patterns("__pycache__"))
    db = json.load(open(os.path.join(DST, "db.json")))
    n = 0
    for d in db["instructions"]:
        if d["mnemonic"] == "cvt_bf16":
            before = json.dumps(d["match"])
            d["match"] = [[0, 4, 1], [24, 8, 129], [32, 1, 1]]
            print("cvt_bf16.match  %s  ->  %s" % (before, json.dumps(d["match"])))
            n += 1
    assert n == 1
    json.dump(db, open(os.path.join(DST, "db.json"), "w"), indent=1)

    for name, tree in (("cand_full (isadb fix only)", SRC), ("demo_dbfix (+ match relax)", DST)):
        m = load(tree, "isadb_demo_%d" % abs(hash(tree)))
        buf = bytes.fromhex(ANCHOR)
        try:
            rec, L = m.decode_one(buf, 0)
            got = "%s (len %d)" % (rec["mnemonic"], L)
        except Exception as e:
            got = "<%s: %s>" % (type(e).__name__, e)
        c, f, lo = corpus(m)
        print("%-28s anchor -> %-24s corpus clean=%d/%d leftover=%d" % (name, got, c, f, lo))
    print("\nNOT APPLIED. db.json is the orchestrator's file; this is a measured recommendation.")


main()
