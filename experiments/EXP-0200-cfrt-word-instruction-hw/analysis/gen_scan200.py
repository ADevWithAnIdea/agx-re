#!/usr/bin/env python3
"""EXP-0200 AMENDMENT A5 -- the STOP-SCAN reachability arm.

  python3 analysis/gen_scan200.py          # writes harness/arms200c.json

WHY THIS EXISTS, and it is the most important thing this experiment found.

The transparency arm of the gated pair reported, with 100 % cross-run agreement
in reversed order, that writing a `stop` (`0e 00 00 00`, `_instruction:
hardware-run`) into **61 of 65 natural compact-word occurrences** leaves the
carrier returning its exact non-zero oracle. The program does not halt.

At the SAME offset -- `rq_mdist` +1306 -- EXP-0187 and this experiment's target 1
both measured `04 <dst> 20 80` faulting the command buffer for exactly the 64
values satisfying `(dst & 0b110) == 0b100`, twice, in opposite case order.

So at one offset: an illegal encoding is REJECTED, and a terminator is IGNORED.
Two models explain that and they have opposite consequences for every
`n4_rt_word` result ever recorded:

  M1  The bytes are fetched and decoded but the instruction's architectural
      effect is suppressed -- e.g. the occurrence sits in a divergent region
      with no active lane for a grid-of-1 dispatch. Decode-stage validation
      still rejects the illegal encoding; `stop` still has nothing to halt.
  M2  The offset is NOT an instruction boundary in hardware. `04 <dst> 20 80`
      is the operand tail of a longer preceding instruction our tokenizer
      under-lengths, so changing byte+1 corrupts that operand (fault), and
      writing `0e 00 00 00` there just writes a different, benign operand.
      Under M2 `n4_rt_word` is not an instruction at these sites at all -- a
      descriptor defect in the sense of FIELD-SWEEP-PROTOCOL section 6.

THE SCAN. A `stop` halts a thread. So write one at every candidate offset across
a whole carrier and ask where the program stops producing output:

    halted  ->  `not_written`   (sentinel intact, result slot still poison)
            or  `invalid_run`   (halted BEFORE the sentinel store; nothing written)
    ran on  ->  `ok` / `wrong_value` / `silent_zero`

The claim is deliberately ONE-SIDED and therefore robust: **a halt proves the
region is fetched and executed.** Absence of a halt over a large window is
evidence of unreachability, not proof, and is reported that way.

If some offset near +1306 halts, the region IS executed and M2 is the live
explanation. If nothing halts anywhere in a wide window while offsets elsewhere
in the same program do halt, M1 (or plain dead code) is the live explanation --
and either way, a large part of the ray-query program is not exercised by a
grid-of-1 traversal, which bounds what every previous `n4_rt_word` /
`rt_query_traverse` sweep can possibly have measured.

COVERAGE: a FINE grid (every 2 bytes, the parcel size) in a +/-32-byte window
around each natural 4-byte occurrence the gated pair used, plus a COARSE grid
across the whole of `_agc.main`, so the scan can find the executed region rather
than assuming where it is. Offsets are dispatched whether or not our tokenizer
thinks they are instruction boundaries: a `stop` at a non-boundary is simply an
operand and cannot halt, which is itself part of the answer.

CLEAN-ROOM: OWN-SHADER. Our own compiled MSL, overwritten with bytes we chose.
"""
import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EXP / "harness"))
import words200 as W            # noqa: E402

FINE_RADIUS = 32          # +/- bytes around each natural occurrence
FINE_STEP = 2             # the parcel size
COARSE_STEP = 128
SCAN_CARRIERS = ("rq_mdist", "rq_inst", "rq_bbox", "cw_trans")
STOP4 = W.STOP4.hex()


def main():
    cpath = EXP / "raw" / "prefreeze" / "census200.v2.json"
    census = json.loads(cpath.read_text())
    arms200 = json.loads((EXP / "harness" / "arms200.json").read_text())["arms"]
    used = {}
    for a in arms200:
        if a["kind"] == "transparency" and a["len"] == 4:
            used.setdefault(a["carrier"], []).append(a["off"])

    arms, v = [], 0
    for carrier in SCAN_CARRIERS:
        c = census.get(carrier)
        if not c:
            continue
        n = c["main_len"]
        offs = set(range(256, n - 8, COARSE_STEP))
        for o in used.get(carrier, []):
            offs |= {x for x in range(o - FINE_RADIUS, o + FINE_RADIUS + 1,
                                      FINE_STEP) if 0 <= x <= n - 8}
        for o in sorted(offs):
            v += 1
            arms.append({
                "carrier": carrier, "kind": "scan",
                "arm": "%s@scan%d" % (carrier, o), "off": o, "len": 4,
                "covers": ["scan"],
                "fills": [{"fid": "S_stop", "instr": "stop", "hex": STOP4,
                           "predict": "not_written", "role": "scan_stop",
                           "value": v,
                           "note": "A5 reachability scan: a halt here proves "
                                   "the region is fetched and executed."}]})
    doc = {"rule": __doc__, "fine_radius": FINE_RADIUS, "fine_step": FINE_STEP,
           "coarse_step": COARSE_STEP, "carriers": list(SCAN_CARRIERS),
           "arms": arms, "n_arms": len(arms),
           "n_cases": sum(len(a["fills"]) for a in arms)}
    p = EXP / "harness" / "arms200c.json"
    p.write_text(json.dumps(doc, indent=1, sort_keys=True))
    print("wrote %s: %d scan arms, %d cases" % (p, len(arms), doc["n_cases"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
