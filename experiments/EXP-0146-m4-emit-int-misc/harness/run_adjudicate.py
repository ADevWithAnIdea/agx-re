#!/usr/bin/env python3
"""EXP-0146 adjudication pass (FIELD-SWEEP-PROTOCOL §7, 2026-08-28 revision).

Re-tests, 5x each and strictly serially, every case that either (a) the two gated runs
disagreed on, or (b) either gated run recorded as `fault`/`hang`. Records the OS
fault-classification string per repetition so `ErrorInnocentVictim` failures -- command
buffers discarded because ANOTHER command buffer errored, which say nothing about our bytes
-- can be segregated from genuine faults.

The unmutated carrier baseline is re-validated before the arm and every `--baseline-every`
cases; a failing baseline means a cascade, so the runner process is torn down and restarted
and the baseline failure is recorded as data, never as a case result.

  python3 harness/run_adjudicate.py --run-id run04 --list analysis/adjudicate_list.json
"""
import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import sweeplib as S      # noqa: E402
import oracles as O       # noqa: E402
import arms as A          # noqa: E402
import isadb              # noqa: E402
from run_sweep import fault_class, hexlist  # noqa: E402

K = EXP / "kernels"

# (instr, carrier) -> (arm_id, offset)  built from the frozen arm table
SITE = {}
for (arm_id, instr, cname, off, fields, byteprobes, note) in A.ARMS:
    SITE[(instr, cname)] = (arm_id, off)


def build_instr(instr, irec, field, value):
    """Rebuild the target instruction with one field/byte set to `value`."""
    if field.startswith("byte+"):
        rel = int(field[5:])
        mut = bytearray(irec["_raw"])
        mut[rel] = value
        return bytes(mut)
    if "+" in field:                       # paired sweep, e.g. lut_a+lut_b+op_base
        names = field.split("+")
        f2 = dict(irec["fields"])
        for nm, v in zip(names, value):
            f2[nm] = v
        return isadb.assemble(instr, f2)
    f2 = dict(irec["fields"])
    f2[field] = value
    return isadb.assemble(instr, f2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--list", required=True)
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--baseline-every", type=int, default=25)
    ap.add_argument("--timeout", type=float, default=8.0)
    args = ap.parse_args()

    run_dir = EXP / "raw" / args.run_id
    if (run_dir / "sweep.jsonl").exists():
        sys.exit("REFUSING to reuse run id %s" % args.run_id)
    workdir = EXP / "work" / args.run_id
    rec = S.Recorder(run_dir / "sweep.jsonl")
    cases = [tuple(x) for x in json.load(open(args.list))]
    rec.record({"instr": "_meta", "field": "run", "value": 0, "bytes": "", "observed":
                {"run_id": args.run_id, "n_cases": len(cases), "reps": args.reps},
                "oracle": {}, "match": True, "outcome": "ok", "carrier": "-",
                "note": "adjudication of run01/run03 disagreements + every fault/hang case; "
                        "5 serial repetitions each; baseline re-validated every %d cases"
                        % args.baseline_every})

    CAR = A.carriers()
    bycarrier = {}
    for c in cases:
        bycarrier.setdefault((c[0], c[1]), []).append(c)

    t_start = time.time()
    for (instr, cname), group in sorted(bycarrier.items()):
        if (instr, cname) not in SITE:
            rec.record({"instr": instr, "field": "_site", "value": 0, "bytes": "", "observed": {},
                        "oracle": {}, "match": False, "outcome": "undecodable", "carrier": cname,
                        "note": "no frozen arm site for this (instr,carrier)"})
            continue
        arm_id, off = SITE[(instr, cname)]
        msl, ins, outs, oidx, dec, oracle, tol = CAR[cname]

        def new_carrier(tag):
            return S.Carrier("%s_%s_adj%s" % (cname, arm_id, tag), K / msl, ins, outs, 8, 8,
                             run_dir, workdir, timeout=args.timeout)

        gen = 0
        c = new_carrier(gen)
        irec, iraw = c.instr_at(off)
        irec["_raw"] = iraw

        def check_baseline(why):
            """True if the unmutated carrier still produces the right answer."""
            r = c.run_main(c.main_bytes)
            obs = dec(r["outs"].get(oidx, b""))
            oc, mt = S.classify(r["status"], obs, oracle, tol)
            rec.record({"instr": instr, "field": "_baseline_check", "value": 0,
                        "bytes": iraw.hex(),
                        "observed": {"words": hexlist(obs), "status": r["status"],
                                      "fault_class": fault_class(r.get("error")),
                                      "err": (r.get("error") or "")[:200], "why": why},
                        "oracle": {"words": hexlist(oracle)}, "match": mt, "outcome": oc,
                        "carrier": cname, "note": "%s | cascade guard" % arm_id})
            return mt

        n = 0
        for (i_, c_, field, valjson) in group:
            value = json.loads(valjson)
            if n % args.baseline_every == 0:
                if not check_baseline("periodic"):
                    # cascade: tear down and restart in a fresh process, then re-check
                    c.close()
                    gen += 1
                    c = new_carrier(gen)
                    irec, iraw = c.instr_at(off)
                    irec["_raw"] = iraw
                    check_baseline("after_restart")
            n += 1
            try:
                mut = build_instr(instr, irec, field, value)
            except Exception as e:
                rec.record({"instr": instr, "field": field, "value": value, "bytes": "",
                            "observed": {}, "oracle": {}, "match": False,
                            "outcome": "undecodable", "carrier": cname,
                            "note": "rebuild failed: %s" % e})
                continue
            reps = []
            for _ in range(args.reps):
                r = c.run_with_instr(off, mut)
                obs = dec(r["outs"].get(oidx, b""))
                oc, mt = S.classify(r["status"], obs, oracle, tol)
                reps.append({"outcome": oc, "status": r["status"],
                              "fault_class": fault_class(r.get("error")),
                              "words": hexlist(obs)})
            outs_seen = [x["outcome"] for x in reps]
            fcs = [x["fault_class"] for x in reps]
            # segregate innocent victims: they carry no information about our bytes
            informative = [x for x in reps if x["fault_class"] != "innocent_victim"]
            pool = informative or reps
            counts = {}
            for x in pool:
                sig = (x["outcome"], tuple(x["words"]))
                counts[sig] = counts.get(sig, 0) + 1
            best, nbest = max(counts.items(), key=lambda kv: kv[1])
            stable = (nbest == len(pool))
            observed = {"reps": outs_seen, "fault_classes": fcs,
                        "n_informative": len(informative),
                        "majority": best[0], "majority_n": nbest,
                        "stable": stable, "words": list(best[1])}
            rec.record({"instr": instr, "field": field, "value": value, "bytes": mut.hex(),
                        "observed": observed, "oracle": {"words": hexlist(oracle)},
                        "match": (best[0] == "ok"), "outcome": best[0], "carrier": cname,
                        "note": "%s | adjudicated %dx | stable=%s | victims=%d"
                                % (arm_id, args.reps, stable, len(reps) - len(informative))})
        check_baseline("arm_end")
        print("%-16s %-12s %5d cases adjudicated (%d runner generations)"
              % (arm_id, instr, len(group), gen + 1))
        c.close()

    rec.record({"instr": "_meta", "field": "done", "value": rec.n, "bytes": "",
                "observed": {"cases": rec.n, "elapsed_s": round(time.time() - t_start, 1)},
                "oracle": {}, "match": True, "outcome": "ok", "carrier": "-", "note": "complete"})
    print("TOTAL %d records in %.1fs" % (rec.n, time.time() - t_start))
    rec.close()


if __name__ == "__main__":
    main()
