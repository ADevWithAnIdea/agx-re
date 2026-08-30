#!/usr/bin/env python3
"""EXP-0161 PILOT: why do r0..r4 read 0 after 15 device_load seeds?

Smoke S2 showed r5..r14 holding their seeds and r0..r4 reading 0, while S3
showed the SAME seeding delivering r1 and r3 correctly to a lifted block. So
the loads land; something about the DUMP of the first few registers does not.
Competing explanations, and the variant that separates them:

  P1 loads -> dump                     (reproduce S2)
  P2 loads -> 64 pad ops -> dump       latency: if the first stores are issued
                                       before the loads retire, padding fixes it
  P3 loads issued r14..r0 -> dump      if the FIRST-ISSUED loads are the ones
                                       lost, this moves the zeros to r10..r14
  P4 only r0..r4 loaded -> dump        if only 5 loads are outstanding, they
                                       all land
  P5 loads -> dump in reverse reg order  if the FIRST STORES are too early, the
                                       zeros move to r10..r14
  P6 loads -> one dummy consumer -> dump

Not evidence; writes work/pilot_seed.json.
"""
from __future__ import print_function
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import isa_helpers as H   # noqa
import sweeprun as S      # noqa
import cases as CM        # noqa

car = S.Carrier(EXP / "kernels" / "carrier_seed.metal", "k",
                EXP / "work" / "pilot_seed", timeout=8.0, fast_math=False,
                inputs={0: ("poison_synth.bin", CM.poison(H.OUT_WORDS)),
                        1: ("seedbuf.bin", H.seed_buffer_bytes())},
                outs={0: H.OUT_WORDS * 4})
SEEDS = H.seeds_for("int")


def run(instrs, tag):
    prog = H.build_program(instrs + [H.stop()], car.region_len)
    resp, outs = car.run_program(prog, grid=1, tg=1)
    d = S.digest(S.words_u32(outs.get(0, b"")))
    regs = d["regs"] if d else None
    bad = [i for i in range(15) if not regs or regs[i] != SEEDS[i]]
    print("%-6s status=%-4s bad=%s" % (tag, resp["status"], bad))
    if regs:
        print("       ", " ".join("%08x" % v for v in regs))
    return {"tag": tag, "status": resp["status"], "error": resp["error"],
            "regs": ["%08x" % v for v in regs] if regs else None, "bad": bad}


def loads(order, n=15, base=0):
    out = [H.mov_imm(H.R_IDX, 0)]
    for r in order[:n]:
        out.append(H.device_load(index_reg=H.R_IDX, base_slot=H.SLOT_SEED,
                                 extmode=2 * r, dst_lo=1, dst_ext9=1,
                                 idx_off=base + r, elem_code=3))
    return out


PRE = H.pre_sentinel_instrs()
DUMP = H.dump_instrs()
res = {}
res["P1"] = run(PRE + loads(list(range(15))) + DUMP, "P1")
res["P2"] = run(PRE + loads(list(range(15))) + [H.mov_imm(13, 0) * 64] + DUMP, "P2")
res["P3"] = run(PRE + loads(list(range(14, -1, -1))) + DUMP, "P3")
res["P4"] = run(PRE + loads(list(range(5))) + DUMP, "P4")
rev = []
for r in range(15, -1, -1):
    rev.append(H.store_word(H.W_REG0 + r * H.STORE_STRIDE_WORDS, r))
rev.append(H.mov_imm(H.R_SENT, H.SENT_POST))
rev.append(H.store_word(H.W_POST, H.R_SENT))
res["P5"] = run(PRE + loads(list(range(15))) + rev, "P5")
# P6: a dummy consumer of r0 that does not release it -- there is none, so use
# a 2-byte mov_imm chain instead of a real consumer (pure delay, 16 ops)
res["P6"] = run(PRE + loads(list(range(15))) + [H.mov_imm(13, 0) * 16] + DUMP, "P6")
res["P7"] = run(PRE + loads(list(range(15))) + [H.mov_imm(13, 0) * 4] + DUMP, "P7")
# P8: load each register TWICE (second pass re-arms the interlock)
res["P8"] = run(PRE + loads(list(range(15))) + loads(list(range(15)))[1:] + DUMP, "P8")
car.close()
(EXP / "work" / "pilot_seed.json").write_text(json.dumps(res, indent=1, sort_keys=True))
print("wrote work/pilot_seed.json")
