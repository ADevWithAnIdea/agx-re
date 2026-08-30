#!/usr/bin/env python3
"""EXP-0154 smoke test (pilot, NOT a gated run).

Validates the synthesized scaffold on live G17P hardware before anything is
frozen:
  S1  empty block          -- do the seeds, the 16-register dump and both
                              integrity sentinels come back exactly?
  S2  poison               -- do the untouched words keep 0xDEADBEEF?
  S3  lifted iadd2 block   -- does an instruction lifted verbatim out of our own
                              compiled MSL still compute in the synthesized
                              program, over registers WE seeded?
  S4  sensitivity witness  -- does a deliberately corrupted opcode byte change
                              the observation (i.e. can this method see a
                              difference at all)?
"""
from __future__ import print_function

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import isa_helpers as H          # noqa: E402
import sweeprun as S             # noqa: E402

WORK = EXP / "work" / "smoke"


def main():
    rep = json.loads((EXP / "work" / "anchors" / "anchor_report.json").read_text())
    car = S.Carrier(EXP / "kernels" / "carrier_dag.metal", "k", WORK, timeout=12.0)
    print("device      :", car.device)
    print("region len  :", car.region_len)

    def toks(fn):
        return rep[fn]["tokens"]

    def block(fn, lo, hi):
        m = bytes.fromhex(rep[fn]["main_hex"])
        return m[lo:hi]

    out = {"device": car.device, "region_len": car.region_len, "cases": {}}

    # --- S1/S2: empty block -------------------------------------------------
    prog = H.synth_program("int", b"", car.region_len)
    resp, words = car.run_program(prog)
    d = S.digest(words)
    print("S1 status   :", resp["status"], "err:", resp["error"])
    print("S1 regs     :", d["regs"])
    print("S1 pre/post : 0x%x / %d  (want 0x%x / %d)"
          % (d["pre"], d["post"], H.expected_pre(), H.SENT_POST))
    seeds_ok = d["regs"] == [H.SEED_I[i] for i in range(16)]
    print("S1 seeds ok :", seeds_ok)
    # any word that is neither a register slot nor a sentinel must stay poisoned
    slots = set(H.W_REG0 + i * H.STORE_STRIDE_WORDS for i in range(16))
    slots |= {H.W_PRE, H.W_POST}
    untouched = [w for i, w in enumerate(words) if i not in slots]
    print("S2 poison   :", "ALL POISON" if all(w == H.POISON for w in untouched)
          else "LEAKED %d/%d" % (sum(1 for w in untouched if w != H.POISON),
                                 len(untouched)))
    out["cases"]["S1"] = {"status": resp["status"], "digest": d,
                          "seeds_ok": seeds_ok,
                          "poison_ok": all(w == H.POISON for w in untouched),
                          "words": words}

    # --- S3: lifted iadd2 ---------------------------------------------------
    blk = block("k_u32add", 32, 42)
    print("S3 block    :", blk.hex())
    prog = H.synth_program("int", blk, car.region_len)
    resp, words = car.run_program(prog)
    d3 = S.digest(words)
    print("S3 status   :", resp["status"], "regs:", d3["regs"])
    print("S3 pre/post : 0x%x / %d" % (d3["pre"], d3["post"]))
    print("S3 delta    :", {i: (H.SEED_I[i], d3["regs"][i])
                            for i in range(16) if d3["regs"][i] != H.SEED_I[i]})
    out["cases"]["S3"] = {"status": resp["status"], "digest": d3,
                          "block": blk.hex()}

    # --- S4: sensitivity witness (corrupt the opcode byte) -------------------
    bad = bytearray(blk); bad[0] = 0x00
    prog = H.synth_program("int", bytes(bad), car.region_len)
    resp, words = car.run_program(prog)
    d4 = S.digest(words)
    print("S4 status   :", resp["status"], "err:", str(resp["error"])[:120])
    print("S4 regs     :", d4["regs"])
    print("S4 differs  :", d4["regs"] != d3["regs"])
    out["cases"]["S4"] = {"status": resp["status"], "digest": d4,
                          "error": resp["error"], "differs": d4["regs"] != d3["regs"]}

    # --- S5: float scaffold -------------------------------------------------
    prog = H.synth_program("float", b"", car.region_len)
    resp, words = car.run_program(prog)
    d5 = S.digest(words)
    import struct as _s
    fl = [_s.unpack("<f", _s.pack("<I", v))[0] for v in d5["regs"]]
    print("S5 status   :", resp["status"], "floats:", fl)
    print("S5 seeds ok :", all(abs(fl[i] - H.SEED_F[i]) < 1e-6 for i in range(14)))
    out["cases"]["S5"] = {"status": resp["status"], "digest": d5, "floats": fl}

    car.close()
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "smoke.json").write_text(json.dumps(out, indent=1, sort_keys=True))
    print("\nwrote", WORK / "smoke.json")


if __name__ == "__main__":
    main()
