#!/usr/bin/env python3
"""EXP-0213 -- device-health gate (AMENDMENT-03).  Runs on the repo host.

    python3 harness/health_gate.py <probe_run_dir>

Compares a probe capture of `tex_sample@msfilt/0` -- an arm this experiment measured 256/256
payload-stable across three orders -- against the B-series.  Exit 0 iff all 256 `mode`
payloads are byte-identical to B1, B2 and B3 AND the arm's `baseline_final_ok` is true.

Stage 6B drove EXP-0206's abort-path-free run.py into a hang cascade whose degraded state
OUTLIVED the capture and hung the NEXT capture's `carrier_open`.  That is a contamination
source the quiet gate cannot see, because it is us.  This gate can fail and stop the
experiment; that is its purpose.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
E204 = os.path.join(HERE, "..", "EXP-0204-g17p-tex-carrier-dimensions", "raw")
REF = ["g17p_e0213_B1_tex_sample_msfilt_0",
       "g17p_e0213_B2_tex_sample_msfilt_0",
       "g17p_e0213_B3_tex_sample_msfilt_0"]


def load_mode(d):
    out = {}
    p = os.path.join(d, "sweep.jsonl")
    for ln in open(p):
        r = json.loads(ln)
        if r.get("field") == "mode" and isinstance(r.get("value"), int) and r["value"] >= 0:
            o = dict(r["observed"])
            o.pop("_ledger", None)
            out[r["value"]] = json.dumps(o, sort_keys=True, default=str)
    return out


def main():
    probe_dir = sys.argv[1]
    probe = load_mode(probe_dir)
    man = json.load(open(os.path.join(probe_dir, "05_run_manifest.json")))
    base_ok = all(s.get("baseline_final_ok") is True for s in man["arms"].values())
    refs = [load_mode(os.path.join(E204, r)) for r in REF]
    common = set(probe)
    for r in refs:
        common &= set(r)
    agree = sum(1 for v in common if all(probe[v] == r[v] for r in refs))
    ok = (len(probe) == 256 and len(common) == 256 and agree == 256 and base_ok
          and not man.get("cascade"))
    print(json.dumps({"probe": os.path.basename(probe_dir),
                      "probe_values": len(probe), "common_with_B_series": len(common),
                      "payload_identical_to_all_three_B_runs": agree,
                      "baseline_final_ok": base_ok, "cascade": man.get("cascade"),
                      "HEALTH_GATE": "PASS" if ok else "FAIL"}, indent=1, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
