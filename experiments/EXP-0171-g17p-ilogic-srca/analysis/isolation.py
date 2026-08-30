#!/usr/bin/env python3
"""EXP-0171 -- ISOLATION / adversarial reproduction of the decisive result.

Runs ON THE DEVICE, in a FRESH process, after both gated runs. Three jobs:

1. **Reproduce the decisive `outmod` observation** — byte+7 = 0x80 (anchor, bit 7
   set) vs 0x00 (bit 7 clear) on all five store-consumed NAT carriers, 5
   repetitions each, and check the result is identical every time.
2. **Record `GPUTIME_NS`.** The NAT carriers ran ~30x faster than the SYNTH
   carrier during the sweep (a small archive vs `carrier_dag`'s), which is
   exactly the kind of throughput anomaly an audit should attack: if the
   dispatches were being served from a cache the results would be constant.
   A non-zero GPU time per request, together with a value-dependent result, is
   the direct refutation.
3. **The `nand` discriminator.** With bit 7 clear, `k_nand` must write
   `0xFFFFFFFF` (= ~(0 & 0)) while the other four write 0 — that is what
   separates "the SOURCES read as zero" from "the OUTPUT was zeroed".

  python3 analysis/isolation.py <out.json>

CLEAN-ROOM: our own MSL, our own runner. No Apple binary introspected.
"""
from __future__ import print_function

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "work" / "frozen"))
sys.path.insert(0, str(EXP / "harness"))
import isa_helpers as H       # noqa: E402
import sweeprun as S          # noqa: E402

PROBES = ["k_and", "k_or", "k_xor", "k_andn", "k_nand"]
REPS = 5
VALUES = [0x80, 0x00, 0xFF, 0x7F]


def main():
    outp = Path(sys.argv[1] if len(sys.argv) > 1 else "isolation.json")
    rep = json.loads((EXP / "work" / "anchors" / "anchor_report.json").read_text())
    res = {"reps": REPS, "values": VALUES, "probes": {}}
    for probe in PROBES:
        tok = [t for t in rep[probe]["tokens"]
               if t["mn"] in ("ilogic", "b_alu10_lof", "b_alu10_loe")][0]
        car = S.NatCarrier(EXP / "kernels" / "probes.metal", probe,
                           EXP / "work" / "isolation", timeout=8.0)
        e = {"instr_off": tok["off"], "anchor_bytes": tok["bytes"],
             "tokenizes_as": tok["mn"], "device": car.device,
             "host_oracle": S.digest_hex(car.oracle), "cases": []}
        for v in VALUES:
            obs = []
            for _ in range(REPS):
                resp, w = car.run_mut(tok["off"], [[7, v]])
                obs.append({"status": resp["status"],
                            "gputime_ns": resp["gputime_ns"],
                            "error": resp["error"],
                            "digest": S.digest_hex(w),
                            "out0_7": (w[:8] if w else None),
                            "sent": (w[16:18] if w else None)})
            digs = set(o["digest"] for o in obs)
            e["cases"].append({
                "byte7": v, "reproducible": len(digs) == 1,
                "distinct_digests": len(digs),
                "gputime_ns": [o["gputime_ns"] for o in obs],
                "gputime_all_nonzero": all(o["gputime_ns"] for o in obs),
                "out0_7": obs[0]["out0_7"], "sent": obs[0]["sent"],
                "matches_host_oracle": obs[0]["digest"] == S.digest_hex(car.oracle),
                "observations": obs})
        car.close()
        res["probes"][probe] = e
        print(probe, json.dumps([(c["byte7"], c["reproducible"],
                                  c["out0_7"][0] if c["out0_7"] else None)
                                 for c in e["cases"]]))
    # the nand discriminator
    d = {}
    for probe in PROBES:
        c = [x for x in res["probes"][probe]["cases"] if x["byte7"] == 0x00][0]
        d[probe] = c["out0_7"]
    res["nand_discriminator"] = {
        "bit7_clear_out0_7": d,
        "all_zero_except_nand": all(all(x == 0 for x in d[p]) for p in PROBES
                                    if p != "k_nand"),
        "nand_all_ones": all(x == 0xFFFFFFFF for x in d["k_nand"]),
        "reading": "0xFFFFFFFF == ~(0 & 0): the LUT still evaluates and the "
                   "destination is still written -- both SOURCES read as ZERO. "
                   "An output-zeroing flag would give 0 for nand too."}
    outp.write_text(json.dumps(res, indent=1, sort_keys=True))
    print("wrote", outp)
    print("nand discriminator:", json.dumps(
        dict((k, v) for k, v in res["nand_discriminator"].items()
             if k != "bit7_clear_out0_7"), sort_keys=True))


if __name__ == "__main__":
    main()
