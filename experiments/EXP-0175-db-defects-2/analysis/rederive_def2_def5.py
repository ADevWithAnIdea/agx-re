#!/usr/bin/env python3
"""EXP-0175 / DEF-0171-2 and DEF-0171-5 re-derivation.

DEF-0171-2: `tools/agx-isa` has no length rule for byte0 == 0x31, so G17P's own
native bfloat ALU does not tokenize; and `bf_alu`'s match / `bf_fma_dst.fmt`'s
enum do not describe what G17P emits.

DEF-0171-5: `fspecial_est.subop == 0x0f` in G17P's precise rsqrt lowering, a value
absent from db.json's enum {9: rcp, 11: rsqrt, 13: sqrt}.

Both are re-derived from the ANCHOR BYTES recorded on every case in EXP-0171's
raw (i.e. from our own compiled shaders) fed to the LIVE `tools/agx-isa`.

    python3 analysis/rederive_def2_def5.py
"""
import json, os, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(EXP, "..", ".."))
SRC = os.path.join(REPO, "experiments", "EXP-0171-g17p-ilogic-srca", "raw")
sys.path.insert(0, os.path.join(REPO, "tools", "agx-isa"))
import isadb                                                   # noqa: E402

RUNS = ["g17p_20260830_run01", "g17p_20260830_run02"]


def anchors():
    """(arm, carrier_id) -> anchor hex, from both runs; assert they agree."""
    per_run = {}
    for run in RUNS:
        got = {}
        with open(os.path.join(SRC, run, "sweep.jsonl")) as fh:
            for line in fh:
                r = json.loads(line)
                k = (r["arm"], r["carrier_id"])
                if k not in got:
                    got[k] = r["anchor_bytes"]
        per_run[run] = got
    a, b = per_run[RUNS[0]], per_run[RUNS[1]]
    assert a == b, "anchor bytes differ between the two gated runs"
    return a


def main():
    A = anchors()
    db = json.load(open(os.path.join(REPO, "tools", "agx-isa", "db.json")))
    byname = {i["mnemonic"]: i for i in db["instructions"]}
    out = {}

    # ---------------- DEF-0171-2 ------------------------------------------------
    print("=== DEF-0171-2 : byte0 0x31 (G17P native bfloat ALU) ===")
    bf = sorted({v for (arm, cid), v in A.items() if arm.startswith("BF_")})
    dec = []
    for h in bf:
        b = bytes.fromhex(h)
        try:
            rec, ln = isadb.decode_one(b, 0)
            r = {"hex": h, "length": ln, "mnemonic": rec.get("mnemonic")}
        except Exception as e:
            r = {"hex": h, "length": None, "mnemonic": None, "error": str(e)}
        dec.append(r)
        print("  %-22s -> %s" % (h, r.get("error") or
                                 "%s (len %s)" % (r["mnemonic"], r["length"])))
    no_length = all(d["length"] is None for d in dec)
    print("  all three anchors fail to tokenize: %s" % no_length)

    # what the descriptors say vs what G17P emits
    bfa = byname["bf_alu"]
    print("\n  bf_alu.match = %s" % bfa["match"])
    print("    -> demands byte0 == 0x%02x (a full 8-bit byte0: the SAME dst-nibble over-fit"
          " as DEF-0171-1)\n       and byte+1 == 0x%02x" % (17, 2))
    for h in bf:
        b = bytes.fromhex(h)
        print("    G17P anchor %s : byte0 0x%02x  byte+1 0x%02x  byte+2 0x%02x"
              % (h, b[0], b[1], b[2]))
    fmt_enum = next(f for f in byname["bf_fma_dst"]["fields"] if f["name"] == "fmt")["enum"]
    emitted_fmt = bytes.fromhex(A[("BF_FMA_DST", "NAT:k_bffma@bf_fma_dst+46")])[1]
    print("\n  bf_fma_dst.fmt enum = %s ; G17P emits byte+1 = 0x%02x -> %s"
          % (fmt_enum, emitted_fmt,
             "PRESENT" if str(emitted_fmt) in fmt_enum else "ABSENT"))
    # but do the general dst-parameterised descriptors cover byte0 0x31?
    print("\n  Would a descriptor claim these bytes if the LENGTH rule knew 0x31?")
    for h in bf:
        b = bytes.fromhex(h)
        cands = []
        for i in db["instructions"]:
            ok = True
            for (s, w, v) in i.get("match", []):
                byte, lo = s // 8, s % 8
                if byte >= len(b) or lo + w > 8:
                    ok = False
                    break
                if ((b[byte] >> lo) & ((1 << w) - 1)) != v:
                    ok = False
                    break
            if ok and i.get("match"):
                cands.append((sum(w for _s, w, _v in i["match"]), i["mnemonic"],
                              i["length"]))
        cands.sort(reverse=True)
        print("    %-22s -> %s" % (h, cands[:3]))
    def2 = no_length and str(emitted_fmt) not in fmt_enum
    print("\n  VERDICT DEF-0171-2: %s" % ("CONFIRMED" if def2 else "NOT CONFIRMED"))
    out["def2"] = {"anchors": dec, "no_length_for_0x31": no_length,
                   "bf_alu_match": bfa["match"],
                   "bf_fma_dst_fmt_enum": fmt_enum,
                   "g17p_emitted_fmt": emitted_fmt,
                   "verdict": "CONFIRMED" if def2 else "NOT CONFIRMED"}

    # ---------------- DEF-0171-5 ------------------------------------------------
    print("\n=== DEF-0171-5 : fspecial_est.subop == 0x0f on G17P ===")
    fe = sorted({v for (arm, cid), v in A.items() if arm == "FSPECIAL_EST"})
    assert len(fe) == 1, fe
    b = bytes.fromhex(fe[0])
    print("  G17P precise-rsqrt anchor : %s   byte+3 = 0x%02x" % (fe[0], b[3]))
    fes = byname["fspecial_est"]
    sub = next(f for f in fes["fields"] if f["name"] == "subop")
    print("  db.json fspecial_est.subop enum = %s" % sub["enum"])
    # is 0x0f actually ENCODABLE, i.e. permitted by the descriptor's own match?
    covered = 0
    for (s, w, _v) in fes["match"]:
        covered |= ((1 << w) - 1) << s
    span = ((1 << sub["width"]) - 1) << sub["start"]
    free = span & ~covered
    legal = []
    for cand in range(256):
        word = int.from_bytes(b, "little")
        word = (word & ~span) | (cand << sub["start"])
        ok = all(((word >> s) & ((1 << w) - 1)) == v for (s, w, v) in fes["match"])
        if ok:
            legal.append(cand)
    print("  free bits in the subop span : %d  ->  %d legal values : %s"
          % (bin(free).count("1"), len(legal), [hex(x) for x in legal]))
    print("  emitted value 0x%02x is %s the match, and %s the enum"
          % (b[3], "PERMITTED by" if b[3] in legal else "FORBIDDEN by",
             "IN" if str(b[3]) in sub["enum"] else "ABSENT FROM"))
    # decode round trip through the live db
    rec, ln = isadb.decode_one(b, 0)
    print("  live decode: %s (len %s) subop=%s"
          % (rec["mnemonic"], ln, rec["fields"]["subop"]))
    def5 = (b[3] == 0x0f and b[3] in legal and str(b[3]) not in sub["enum"])
    print("\n  VERDICT DEF-0171-5: %s" % ("CONFIRMED" if def5 else "NOT CONFIRMED"))
    out["def5"] = {"anchor": fe[0], "byte3": b[3], "enum": sub["enum"],
                   "legal_subop_values": legal,
                   "verdict": "CONFIRMED" if def5 else "NOT CONFIRMED"}

    json.dump(out, open(os.path.join(HERE, "def2_def5_rederived.json"), "w"), indent=1)
    return 0 if (def2 and def5) else 1


sys.exit(main())
