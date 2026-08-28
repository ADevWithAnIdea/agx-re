#!/usr/bin/env python3
"""EXP-0146 run06: bounded attempt to make `sr_read_wide` LIVE on an observable output path.

run05/P4 found `sr_read_wide` in our own `k_rayquery.metal` at compile time. This asks the only
remaining question that matters for emission: can the existing testbed EXECUTE that carrier?
`agxrun_persist` binds MTLBuffers only; an `instance_acceleration_structure` argument is bound
through `setAccelerationStructure:`, which it has no path for. One bounded attempt, recorded
either way. No sweep is run unless the baseline is correct -- per FIELD-SWEEP-PROTOCOL §3.2 a
field whose value cannot reach the output proves nothing.
"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import sweeplib as S   # noqa: E402
import isadb           # noqa: E402
from run_sweep import fault_class, hexlist  # noqa: E402

run_dir = EXP / "raw" / "run06"
if (run_dir / "sweep.jsonl").exists():
    sys.exit("REFUSING to reuse run id run06")
rec = S.Recorder(run_dir / "sweep.jsonl")
try:
    c = S.Carrier("srwide", EXP / "kernels" / "k_rayquery.metal",
                  {1: bytes(4096)}, {0: 32}, 8, 8, run_dir, EXP / "work" / "run06", timeout=8.0)
    recs, leftover = isadb.disassemble(c.main_bytes)
    seq = [r["mnemonic"] for r in recs]
    offs, o = [], 0
    for r in recs:
        if r["mnemonic"] == "sr_read_wide":
            offs.append(o)
        o += r["length"] or 0
    r = c.run_main(c.main_bytes)
    obs = S.words32(r["outs"].get(0, b""))
    rec.record({"instr": "sr_read_wide", "field": "_baseline", "value": 0,
                "bytes": c.main_bytes.hex(),
                "observed": {"status": r["status"], "words": hexlist(obs), "seq": seq,
                              "sr_read_wide_offsets": offs, "leftover": len(leftover),
                              "err": (r.get("error") or "")[:300],
                              "fault_class": fault_class(r.get("error"))},
                "oracle": {}, "match": False,
                "outcome": "ok" if r["status"] == "OK" else "fault", "carrier": "rayquery",
                "note": "run06: can the ray-query carrier EXECUTE without a bound "
                        "acceleration structure? agxrun_persist binds MTLBuffers only."})
    print("status", r["status"], "| sr_read_wide at", offs, "|", (r.get("error") or "")[:140])
    print("words", hexlist(obs)[:8])
    c.close()
except Exception as e:
    rec.record({"instr": "sr_read_wide", "field": "_baseline", "value": 0, "bytes": "",
                "observed": {"err": str(e)[:400]}, "oracle": {}, "match": False,
                "outcome": "undecodable", "carrier": "rayquery",
                "note": "run06: carrier could not be brought up"})
    print("carrier bring-up failed:", str(e)[:300])
rec.close()
