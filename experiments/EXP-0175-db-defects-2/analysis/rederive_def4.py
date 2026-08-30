#!/usr/bin/env python3
"""EXP-0175 / DEF-0171-4 re-derivation, from EXP-0171's committed raw ONLY.

Claim under test: `ilogic`/`b_alu10_*` byte+7 (`outmod`) bit 7 is a SOURCE-READ
control, not the "output/store flag" `db.json` names. With bit 7 clear the LUT
still evaluates and the destination is still written -- both SOURCES read as zero.

Discriminator (pre-registered): a flag that zeroed the OUTPUT gives 0 for every
kernel including nand. A control that zeroes the SOURCES gives ~(0 & 0) =
0xFFFFFFFF for nand and 0 for and/or/xor/andn.

Method: for each NAT store-consumed carrier (k_and, k_or, k_xor, k_andn, k_nand),
take the byte+7 dense sweep from both gated runs, split by bit 7, and report the
distinct out[] words together with poison_out and the sentinel state.

    python3 analysis/rederive_def4.py
"""
import json, os, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(EXP, "..", ".."))
SRC = os.path.join(REPO, "experiments", "EXP-0171-g17p-ilogic-srca", "raw")
RUNS = ["g17p_20260830_run01", "g17p_20260830_run02"]
NAT = ["NAT:k_and@ilogic+32", "NAT:k_or@ilogic+32", "NAT:k_xor@ilogic+32",
       "NAT:k_andn@ilogic+32", "NAT:k_nand@ilogic+32"]
SYNTH = "SYNTH:k_and@ilogic+32"
FRAME = "FRAME:k_and@ilogic+32"
POISON = 0xDEADBEEF


def collect(run, byte_index, carriers):
    out = collections.defaultdict(dict)
    dropped = 0
    with open(os.path.join(SRC, run, "sweep.jsonl")) as fh:
        for line in fh:
            r = json.loads(line)
            if r["arm"] != "ILOGIC" or r["byte_index"] != byte_index:
                continue
            if r["carrier_id"] not in carriers or r["role"] != "target":
                continue
            if r.get("invalid_run"):
                dropped += 1
                continue
            out[r["carrier_id"]][r["value"]] = r
    return out, dropped


def outwords(rec):
    obs = rec.get("observed") or {}
    return (obs.get("words") or [])


def main():
    all_ok = True
    report = {}
    for run in RUNS:
        recs, dropped = collect(run, 7, NAT + [SYNTH, FRAME])
        print("\n=== %s (byte+7 dense sweep, %d invalid_run dropped) ===" % (run, dropped))
        print("  %-26s %-8s %-30s %-30s" % ("carrier", "n", "bit7 SET (128 values)",
                                            "bit7 CLEAR (128 values)"))
        for cid in NAT + [SYNTH, FRAME]:
            d = recs.get(cid, {})
            if not d:
                print("  %-26s  (no cases)" % cid)
                continue
            groups = {1: collections.Counter(), 0: collections.Counter()}
            poison = {1: collections.Counter(), 0: collections.Counter()}
            sent = {1: collections.Counter(), 0: collections.Counter()}
            for v, r in d.items():
                b = 1 if (v & 0x80) else 0
                w = outwords(r)
                # NAT out[] is the leading 8 words; SYNTH/FRAME dump the GPRs.
                groups[b][tuple(w[:8])] += 1
                poison[b][r.get("poison_out")] += 1
                sent[b][bool(r.get("sentinel_bad"))] += 1

            def fmt(b):
                items = groups[b].most_common(2)
                s = []
                for words, n in items:
                    if not words:
                        s.append("(no words) x%d" % n)
                    else:
                        u = sorted(set(words))
                        s.append("%s x%d" % ("/".join("%08x" % x for x in u[:3]), n))
                return "; ".join(s)
            print("  %-26s %-8d %-30s %-30s" % (cid, len(d), fmt(1), fmt(0)))
            print("       %26s poison_out set=%s clear=%s   sentinel_bad set=%s clear=%s"
                  % ("", dict(poison[1]), dict(poison[0]), dict(sent[1]), dict(sent[0])))

        # -------- the discriminator ------------------------------------------
        print("\n  DISCRIMINATOR (bit 7 CLEAR, distinct out[0] over the 128 values):")
        verdict_run = {}
        for cid in NAT:
            d = recs.get(cid, {})
            clear = [outwords(r) for v, r in d.items() if not (v & 0x80)]
            vals = collections.Counter(w[0] for w in clear if w)
            verdict_run[cid] = dict(vals)
            print("    %-26s %s" % (cid, {("0x%08x" % k): n for k, n in vals.items()}))
        nand = verdict_run.get("NAT:k_nand@ilogic+32", {})
        others = [verdict_run.get(c, {}) for c in NAT if "nand" not in c]
        nand_ones = set(nand) == {0xFFFFFFFF}
        others_zero = all(set(o) == {0} for o in others)
        print("    nand writes 0xFFFFFFFF for all 128: %s" % nand_ones)
        print("    and/or/xor/andn write 0 for all 128: %s" % others_zero)
        # no poison, sentinels intact on the clear half
        clean = True
        for cid in NAT:
            for v, r in recs.get(cid, {}).items():
                if v & 0x80:
                    continue
                if r.get("poison_out") != 0 or r.get("sentinel_bad"):
                    clean = False
        print("    every bit7-clear case: poison_out==0 and sentinels intact: %s" % clean)
        ok = nand_ones and others_zero and clean
        all_ok = all_ok and ok
        report[run] = {"nand_all_ones": nand_ones, "others_all_zero": others_zero,
                       "store_ran_and_sentinels_intact": clean,
                       "per_carrier_bit7_clear_out0": {
                           k: {("0x%08x" % kk): vv for kk, vv in v.items()}
                           for k, v in verdict_run.items()}}

    print("\nVERDICT DEF-0171-4: %s" % ("CONFIRMED" if all_ok else "NOT CONFIRMED"))
    print("  A flag that zeroed the OUTPUT would give 0 for nand too. 0xFFFFFFFF is")
    print("  ~(0 & 0): the LUT evaluated and the destination was written -- both SOURCES")
    print("  read as zero. db.json's enum {128: 'output/store'} names the symptom.")
    report["verdict"] = "CONFIRMED" if all_ok else "NOT CONFIRMED"
    json.dump(report, open(os.path.join(HERE, "def4_rederived.json"), "w"), indent=1)
    return 0 if all_ok else 1


sys.exit(main())
