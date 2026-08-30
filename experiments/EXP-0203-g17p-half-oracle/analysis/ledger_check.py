#!/usr/bin/env python3
"""EXP-0203 -- independent re-verification of the Gate A actual-byte ledger, offline.

The on-device half of Gate A reads the instruction bytes back out of the artifact handed to
the GPU.  This is the third leg: the HOST re-synthesizes each case's program from the frozen
sources and checks that the bytes the device actually received are the bytes the builder
would produce.  It runs from committed raw only and touches no device.

It also explains the one ledger field that legitimately differs between runs: `program_sha256`
covers the WHOLE spliced container, and `shdump` recompiles our MSL for every run, so the
container's compiler-generated metadata differs even though our spliced region does not.
`instr_offset` and `actual_instr` are identical across runs, which is the part Gate E cares
about.

Usage: python3 analysis/ledger_check.py raw/g17p_run31 [raw/g17p_run32 ...]
"""
import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EXP / "harness"))
import isa_helpers as H          # noqa: E402


def main():
    runs = sys.argv[1:] or ["raw/g17p_run31"]
    total = {"cases": 0, "instr_ok": 0, "decode_ok": 0, "decode_na": 0, "bytes_match": 0,
             "region_recomputed_ok": 0, "region_recomputed_na": 0}
    plans = {}
    for rd in runs:
        env = json.loads((EXP / rd / "00_env.json").read_text())
        regions = env.get("regions", {})
        for line in open(EXP / rd / "sweep.jsonl"):
            r = json.loads(line)
            led = r.get("ledger") or {}
            total["cases"] += 1
            if led.get("actual_instr") == r["bytes"]:
                total["instr_ok"] += 1
            if led.get("bytes_match"):
                total["bytes_match"] += 1
            if led.get("ledger_ok") is True:
                total["decode_ok"] += 1
            elif led.get("ledger_ok") is None:
                total["decode_na"] += 1
            rl = regions.get(r["carrier"])
            if not rl:
                total["region_recomputed_na"] += 1
                continue
            pk = (r["seeds"], r["layout"])
            if pk not in plans:
                plans[pk] = H.seed_plan(*pk)
            plan = plans[pk]
            blk = bytes.fromhex(r["bytes"]) + H.marker_chain(plan["lay"])
            prog, boff = H.synth_program(plan, blk, rl)
            n = len(bytes.fromhex(r["bytes"]))
            if prog[boff:boff + n].hex() == led.get("actual_instr"):
                total["region_recomputed_ok"] += 1
    print(json.dumps(total, indent=1))
    ok = (total["instr_ok"] == total["cases"] and total["bytes_match"] == total["cases"]
          and total["region_recomputed_ok"] + total["region_recomputed_na"] == total["cases"])
    print("GATE A INDEPENDENT RE-VERIFICATION:", "PASS" if ok else "FAIL")
    (EXP / "analysis" / "ledger_check.json").write_text(
        json.dumps({"runs": runs, "totals": total, "pass": ok}, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
