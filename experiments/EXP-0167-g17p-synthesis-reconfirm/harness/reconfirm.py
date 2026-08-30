#!/usr/bin/env python3
"""EXP-0158 section 7A re-confirmation pass, WITNESS-GATED.

WHY THE GATE.  The first re-confirmation attempt
(`work/reconfirm/reconfirm01.jsonl`) is retained and is NOT used as evidence:
it was taken inside a machine-wide hang cascade.  427 of its observations came
back `Caused GPU Hang Error` in long consecutive streaks (36 in a row, then 14
clean, then 17 in a row), and among the "faulting" programs was `dag_000_n2` --
a two-node program that had already run correctly in the recorded hardware
fixture and in both gated runs.  A trivially correct program cannot hang the
device; the device was being reset by somebody else.

That is EXP-0153's section 7A lesson one step further: the `InnocentVictim`
class is NOT the only contamination signature.  Under sustained sibling load
the driver also reports `...ErrorHang` on OUR command buffer.

So this pass runs a WITNESS program immediately before every observation.  The
witness contains no instruction under test beyond `device_store`: it is
`mov_imm` -> `device_store` of the integrity sentinel, nothing else.  If the
witness fails, the device is in a cascade and the observation that follows is
DISCARDED rather than recorded.  A verdict is only reported once a case has
`--reps` witness-valid observations (or the attempt budget runs out, which is
itself recorded).


`FIELD-SWEEP-PROTOCOL.md` §7A (added 2026-08-29 after EXP-0153) is explicit:
majority-of-3 is NOT sufficient for a `fault`/`hang` verdict.  Under sustained
sibling load contamination can look reproducible *and* survive an independent
second run.  Any case this experiment still reports as `fault`, `hang`,
`victim` or `invalid_run` after both gated runs is re-run REPS more times here,
and its verdict is whatever the majority of those independent observations say.

This is a separate, named pass over a named case list -- it never edits a gated
`raw/` tree.  Its output is its own append-only JSONL.

Usage: reconfirm.py --indices 12,34,56 --reps 5 --out FILE --bin-dir D --repo R
"""
import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP))
sys.path.insert(0, str(HERE))
import casematrix as CM   # noqa: E402
import case_exec as CE    # noqa: E402  (the same executor the gated runs use)
import synth as S         # noqa: E402


def witness_case():
    """A program that ONLY writes the integrity sentinel: mov_imm into a
    register, one device_store, stop.  No falu2/falu2i/device_load/iadd2, so it
    cannot fail for any reason this experiment is testing.  If it fails, the
    machine is in a cascade."""
    led = S.Ledger()
    ins = [S.mov_imm(led, S.R_IDX, 0, salt="w")]
    ins += S.sentinel_instrs(led, 0, "w")
    ins.append(S.stop(led, offnatural=False))
    prog = S.build_program(led, ins, 1536)
    S.assert_round_trip(prog)
    return {"i": 99999, "name": "__cascade_witness__", "group": "WITNESS",
            "carrier": "dag", "hex": prog.hex(),
            "oracle": {}, "oracle_bits": {}, "expect_match": True,
            "notes": "cascade witness", "sentinel": True}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--indices", required=True)
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--out", required=True)
    ap.add_argument("--bin-dir", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--max-attempts", type=int, default=14)
    a = ap.parse_args()
    cs = CM.build_cases()
    wit = witness_case()
    f = open(a.out, "a")
    for idx in [int(x) for x in a.indices.split(",") if x.strip()]:
        c = cs[idx]
        obs = []
        discarded = 0
        attempt = 0
        while len(obs) < a.reps and attempt < a.max_attempts:
            args = argparse.Namespace(run_dir="%s/rep%d" % (a.run_dir, attempt),
                                      bin_dir=a.bin_dir, repo=a.repo)
            wrec, _ = CE.run_one(wit, args)
            wok = (wrec["status"] == "OK"
                   and wrec["sentinel"] == S.sentinel_expected_f32())
            rec, ms = CE.run_one(c, args)
            attempt += 1
            if not wok:
                discarded += 1
                continue
            obs.append({"rep": len(obs), "attempt": attempt - 1,
                        "outcome": rec["outcome"], "status": rec["status"],
                        "fault_class": rec["fault_class"], "match": rec["match"],
                        "observed": rec["observed"], "sentinel": rec["sentinel"],
                        "victim_retries": rec["victim_retries"]})
        if not obs:
            f.write(json.dumps({"i": idx, "name": c["name"], "group": c["group"],
                                "expect_match": c["expect_match"], "reps": 0,
                                "observations": [], "tally": {},
                                "majority_outcome": "NO_WITNESS_VALID_OBSERVATION",
                                "majority_count": 0, "majority_is_ok": False,
                                "discarded_cascade_attempts": discarded},
                               sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())
            print("%-40s NO WITNESS-VALID OBSERVATION (%d discarded)"
                  % (c["name"], discarded), flush=True)
            continue
        tally = {}
        for o in obs:
            tally[o["outcome"]] = tally.get(o["outcome"], 0) + 1
        maj = sorted(tally.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        row = {"i": idx, "name": c["name"], "group": c["group"],
               "expect_match": c["expect_match"], "reps": len(obs),
               "discarded_cascade_attempts": discarded,
               "observations": obs, "tally": tally,
               "majority_outcome": maj[0], "majority_count": maj[1],
               "majority_is_ok": maj[0] == "ok"}
        f.write(json.dumps(row, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())
        print("%-40s %-12s %-28s discarded=%d"
              % (c["name"], maj[0], tally, discarded), flush=True)
    f.close()


if __name__ == "__main__":
    main()
