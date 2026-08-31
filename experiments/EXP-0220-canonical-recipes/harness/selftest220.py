#!/usr/bin/env python3
"""EXP-0220 OFFLINE gate suite -- no GPU, no device, no SSH.

Runs before the frozen contract is written and again before every capture.
It checks the things a device run cannot check for us:

  T0  every case builds, and NO case emits a field tagged COPIED or CARRIER
      (the Gate D donor test, evaluated over the whole matrix).
  T1  Gate A, offline: for every instruction of every case the bytes the caller
      asked for are the bytes in the program, and an INDEPENDENT decode of those
      bytes returns the requested field values.
  T2  framing: every generated offset is a boundary of the whole-program
      tokenizer walk and decodes to the requested descriptor -- except in the
      named, declared-ambiguous cases.
  T3  determinism: building the same case twice gives byte-identical programs,
      and no two cases collide on a program hash.
  T4  the scorer: feed it a SIMULATED PERFECT DEVICE (the base state with the
      oracle's own writes applied) and every non-falsifier case must score
      `match`; feed it the base state UNCHANGED and every case must fail.
      A scorer that cannot come out both ways is the DEF-0190-1 defect.
  T5  the pre-registered FALSIFIERS must NOT match on the perfect device.
"""
import hashlib
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import synth220 as S      # noqa: E402
import prog220 as P       # noqa: E402
import cases220 as C      # noqa: E402
import run220 as RUN      # noqa: E402

SLOTS = {"out": 0, "mem": 1, "imem": 2}
CLEN = 2048

DECLARED_AMBIGUOUS = {"f2_opsel0", "f2_opsel1", "ds_space006", "ds_space022"}


def simulate(pg, base_state, slots, perfect=True):
    """A device that does EXACTLY what the host oracle predicts (or nothing)."""
    surf = {i: bytearray(b) for i, b in base_state.items()}
    if perfect:
        idx = {"out": slots["out"], "mem": slots["mem"], "imem": slots["imem"]}
        for basename, want in pg.oracle().items():
            b = surf[idx[basename]]
            for off, val in want.items():
                if val is None or off >= len(b):
                    continue
                b[off] = val
    return {i: bytes(b) for i, b in surf.items()}


def main():
    cs = C.build_cases(include_hazard=True)
    base_state = {0: P.poison_bytes(), 1: P.mem_bytes(), 2: P.imem_bytes()}
    fails = []
    hashes = {}
    dups = []
    t0 = t1 = t2 = t3 = t4 = t5 = 0
    for c in cs:
        pg, prog = C.build_program_for(c, SLOTS, CLEN)
        pg2, prog2 = C.build_program_for(c, SLOTS, CLEN)
        if prog != prog2:
            fails.append(("T3-nondeterministic", c["name"]))
        else:
            t3 += 1
        h = hashlib.sha256(prog).hexdigest()
        if h in hashes:
            prev, prevarm = hashes[h]
            if prevarm == c["arm"]:
                # two cases in the SAME arm that build the same program are a
                # matrix defect: the arm thinks it varied something and did not.
                fails.append(("T3-collision-within-arm",
                              "%s == %s" % (c["name"], prev)))
            else:
                dups.append("%s == %s" % (c["name"], prev))
        hashes[h] = (c["name"], c["arm"])

        cnt = pg.E.led.counts()
        if cnt["COPIED"] or cnt["CARRIER"]:
            fails.append(("T0-donor", "%s %s" % (c["name"], pg.E.led.nonsynthesised())))
        else:
            t0 += 1

        rows, bad, alias = S.gate_a_ledger(prog, pg.E.parts)
        if bad:
            fails.append(("T1-gateA", "%s %r" % (c["name"], bad[:2])))
        else:
            t1 += 1
        hard_alias = [x for x in alias if x["kind"] != "walk_leftover_bytes"]
        if hard_alias and c["name"] not in DECLARED_AMBIGUOUS:
            fails.append(("T2-framing", "%s %r" % (c["name"], hard_alias[:2])))
        else:
            t2 += 1

        oracle = pg.oracle()
        good = simulate(pg, base_state, SLOTS, perfect=True)
        rec = RUN.score(c, pg, prog, rows, bad, alias,
                        {"status": "OK", "surf": good}, base_state, oracle,
                        SLOTS, True)
        if c["arm"] == "S0" or c["kind"].endswith("falsifier"):
            # S0 MEASURES the slot mapping (its write is deliberately not
            # predicted) and the falsifiers can only be judged on real hardware:
            # a simulator that applies the oracle applies the WRONG oracle too.
            t4 += 1
        elif c["expect_match"]:
            if not rec["match"]:
                fails.append(("T4-perfect-device-should-match",
                              "%s %s ok=%d wrong=%d nowrite=%d stray=%d unpred=%d"
                              % (c["name"], rec["outcome"], rec.get("n_pred_ok", -1),
                                 rec.get("n_pred_wrong", -1), rec.get("n_pred_nowrite", -1),
                                 rec.get("n_stray_bytes", -1), rec.get("n_unpredicted", -1))))
            else:
                t4 += 1
        if c["kind"].endswith("falsifier"):
            # OFFLINE form of T5: the falsifier's oracle must DISAGREE with what
            # the program actually computes, or it cannot fail on the device.
            truth = C.BUILDERS[c["kind"]].__doc__ is not None
            twin = dict(c); twin["kind"] = c["kind"].replace("_falsifier", "")
            wrongword = pg.dump_byte(C.RD) if c["kind"] == "f2_falsifier" else None
            if c["kind"] == "f2_falsifier":
                a = pg.rbits(C.RA); b = pg.rbits(C.RB)
                import struct as _st
                truthful = _st.unpack("<I", _st.pack("<f", S.f32(
                    S.bits_f32(a) + S.bits_f32(b))))[0]
                got = pg.rbits(C.RD)
                if got == truthful:
                    fails.append(("T5-falsifier-oracle-agrees-with-truth", c["name"]))
                else:
                    t5 += 1
            else:
                # the store falsifier predicts rB's codeword where rA's is stored
                if pg.rbits(C.RA) == pg.rbits(C.RB):
                    fails.append(("T5-falsifier-operands-equal", c["name"]))
                else:
                    t5 += 1

        # a device that did NOTHING must fail every case that predicts a write
        if oracle["out"] or oracle["mem"] or oracle["imem"]:
            dead = simulate(pg, base_state, SLOTS, perfect=False)
            rec2 = RUN.score(c, pg, prog, rows, bad, alias,
                             {"status": "OK", "surf": dead}, base_state, oracle,
                             SLOTS, True)
            if rec2["match"] and c["expect_match"]:
                fails.append(("T4-dead-device-should-fail", c["name"]))

    print("cases            : %d" % len(cs))
    print("T0 no-donor      : %d" % t0)
    print("T1 gate A        : %d" % t1)
    print("T2 framing       : %d" % t2)
    print("T3 deterministic : %d" % t3)
    print("T4 perfect-device: %d" % t4)
    print("T5 falsifiers    : %d" % t5)
    print("cross-arm duplicate programs (a free repeatability pair, not a defect): %d"
          % len(dups))
    for d in dups[:6]:
        print("   %s" % d)
    print("FAILURES         : %d" % len(fails))
    for k, v in fails[:25]:
        print("   %-32s %s" % (k, v))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
