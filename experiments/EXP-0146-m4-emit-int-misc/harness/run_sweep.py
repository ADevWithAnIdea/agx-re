#!/usr/bin/env python3
"""EXP-0146 sweep driver.

  python3 harness/run_sweep.py --run-id run01

Executes, in order:
  1. the I64 functional baselines (no mutation) for every 64-bit kernel,
  2. every arm in `harness/arms.py` (per-field dense sweeps + raw byte probes),
  3. the paired/2-D sweeps.

Every case is appended to `raw/<run_id>/sweep.jsonl` and flush+fsync'd immediately.
Stop rule: two genuine hangs in one arm abandons that arm (recorded), per
`experiments/FIELD-SWEEP-PROTOCOL.md` §7.
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
import isadb              # noqa: E402  (re-exported by sweeplib's sys.path insert)

K = EXP / "kernels"

DECODERS = {"words32": S.words32, "words64": S.words64, "floats32": S.floats32}


def fault_class(err):
    """Classify the OS/Metal command-buffer error string. `innocent_victim` means the
    command buffer was killed for ANOTHER process's GPU error and says nothing about our
    bytes -- FIELD-SWEEP-PROTOCOL §7 (2026-08-28) requires these to be segregated."""
    if not err:
        return "none"
    e = err.lower()
    if "innocentvictim" in e or "innocent victim" in e:
        return "innocent_victim"
    if "excessive" in e or "prior" in e:
        return "ignored_prior_errors"
    if "hang" in e:
        return "hang"
    if "timeout" in e:
        return "timeout"
    if "fault" in e or "invalidresource" in e or "access" in e:
        return "fault"
    return "other"


def hexlist(vals):
    return [("0x%x" % v) if isinstance(v, int) else round(float(v), 7) for v in vals]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--only", default="", help="comma-separated arm ids")
    ap.add_argument("--timeout", type=float, default=8.0)
    args = ap.parse_args()

    run_dir = EXP / "raw" / args.run_id
    if (run_dir / "sweep.jsonl").exists():
        sys.exit("REFUSING to reuse run id %s: raw/%s/sweep.jsonl already exists "
                 "(SUBAGENT_BRIEF: never reuse or overwrite a run id)" % (args.run_id, args.run_id))
    workdir = EXP / "work" / args.run_id
    rec = S.Recorder(run_dir / "sweep.jsonl")
    only = set(x for x in args.only.split(",") if x)
    t_start = time.time()

    # ---------------------------------------------------------------- meta
    rec.record({"instr": "_meta", "field": "run", "value": 0, "bytes": "",
                "observed": {"run_id": args.run_id}, "oracle": {}, "match": True,
                "outcome": "ok", "carrier": "-",
                "note": "EXP-0146 %s; M4/G16G; pre-registration frozen at rev 3efd06c6" % args.run_id})

    # -------------------------------------------------- 1. I64 functional set
    if not only or "I64" in only:
        for (name, msl, ins, outs, oidx, dec, orc) in A.I64_FUNCTIONAL:
            try:
                c = S.Carrier(name, K / msl, ins, outs, 8, 8, run_dir, workdir,
                              timeout=args.timeout)
            except Exception as e:
                rec.record({"instr": "_i64", "field": name, "value": 0, "bytes": "",
                            "observed": {}, "oracle": {}, "match": False,
                            "outcome": "undecodable", "carrier": name,
                            "note": "carrier build failed: %s" % e})
                continue
            oracle = getattr(O, orc)()
            resp = c.run_main(c.main_bytes)
            obs = DECODERS[dec](resp["outs"].get(oidx, b""))
            outcome, match = S.classify(resp["status"], obs, oracle)
            recs, leftover = isadb.disassemble(c.main_bytes)
            seq = [r["mnemonic"] for r in recs]
            rec.record({"instr": "_i64", "field": name, "value": 0,
                        "bytes": c.main_bytes.hex(),
                        "observed": {"words": hexlist(obs), "seq": seq,
                                      "main_len": len(c.main_bytes),
                                      "leftover": len(leftover)},
                        "oracle": {"words": hexlist(oracle)},
                        "match": match, "outcome": outcome, "carrier": name,
                        "note": "I64 functional baseline (no mutation); 8 frozen rows"})
            print("I64 %-12s %-6s %s" % (name, outcome, " ".join(seq)))
            c.close()

    # ------------------------------------------------------------ 2. the arms
    CAR = A.carriers()
    for (arm_id, instr, cname, off, fields, byteprobes, note) in A.ARMS:
        if only and arm_id not in only:
            continue
        msl, ins, outs, oidx, dec, oracle, tol = CAR[cname]
        try:
            c = S.Carrier(cname + "_" + arm_id, K / msl, ins, outs, 8, 8, run_dir, workdir,
                          timeout=args.timeout)
        except Exception as e:
            rec.record({"instr": instr, "field": "_carrier", "value": 0, "bytes": "",
                        "observed": {}, "oracle": {}, "match": False, "outcome": "undecodable",
                        "carrier": cname, "note": "carrier build failed: %s" % e})
            continue
        # frozen-offset gate
        try:
            irec, iraw = c.instr_at(off)
        except Exception as e:
            rec.record({"instr": instr, "field": "_offset", "value": off, "bytes": "",
                        "observed": {}, "oracle": {}, "match": False, "outcome": "undecodable",
                        "carrier": cname, "note": "decode at frozen offset failed: %s" % e})
            c.close()
            continue
        if irec["mnemonic"] != instr:
            rec.record({"instr": instr, "field": "_offset", "value": off, "bytes": iraw.hex(),
                        "observed": {"mnemonic": irec["mnemonic"]}, "oracle": {"mnemonic": instr},
                        "match": False, "outcome": "undecodable", "carrier": cname,
                        "note": "FROZEN OFFSET MISMATCH -- arm aborted"})
            c.close()
            continue
        # round-trip gate: db.json must reproduce the carrier's own bytes
        rt = isadb.assemble(instr, irec["fields"])
        rt_ok = (rt == iraw)

        # baseline
        resp = c.run_main(c.main_bytes)
        base_obs = dec(resp["outs"].get(oidx, b""))
        outcome, match = S.classify(resp["status"], base_obs, oracle, tol)
        rec.record({"instr": instr, "field": "_baseline", "value": 0, "bytes": iraw.hex(),
                    "observed": {"words": hexlist(base_obs)},
                    "oracle": {"words": hexlist(oracle)}, "match": match, "outcome": outcome,
                    "carrier": cname,
                    "note": "%s | offset +0x%x | db round-trip=%s | fields=%s | %s"
                            % (arm_id, off, rt_ok, json.dumps(irec["fields"], sort_keys=True), note)})
        if not match:
            print("  !! baseline mismatch for %s/%s (%s)" % (arm_id, cname, outcome))

        hangs = 0
        n0 = rec.n
        t0 = time.time()

        def one(fieldname, value, mutated_instr, extra_note=""):
            nonlocal hangs
            r = c.run_with_instr(off, mutated_instr)
            obs = dec(r["outs"].get(oidx, b""))
            oc, mt = S.classify(r["status"], obs, oracle, tol)
            observed = {"words": hexlist(obs)}
            if cname == "logic_and" and r["status"] == "OK":
                lut = O.derive_lut2(O.LOGIC_A, O.LOGIC_B, obs)
                observed["lut"] = list(lut) if lut else None
                observed["fn"] = O.LUT_NAMES.get(lut) if lut else None
            if cname in ("u64add", "u64sub") and r["status"] == "OK":
                # per-row delta from the host oracle, in 64-bit units
                observed["delta"] = ["0x%x" % ((o - e) & O.M64) for o, e in zip(obs, oracle)]
            observed["status"] = r["status"]
            if r.get("error"):
                observed["err"] = r["error"][:200]
                observed["fault_class"] = fault_class(r["error"])
            rec.record({"instr": instr, "field": fieldname, "value": value,
                        "bytes": mutated_instr.hex(), "observed": observed,
                        "oracle": {"words": hexlist(oracle)}, "match": mt, "outcome": oc,
                        "carrier": cname, "note": extra_note})
            if oc == "hang":
                hangs += 1
            return oc

        aborted = False
        for fname, values in fields.items():
            if aborted:
                break
            for v in values:
                f2 = dict(irec["fields"])
                f2[fname] = v
                try:
                    mut = isadb.assemble(instr, f2)
                except Exception as e:
                    rec.record({"instr": instr, "field": fname, "value": v, "bytes": "",
                                "observed": {}, "oracle": {}, "match": False,
                                "outcome": "undecodable", "carrier": cname,
                                "note": "assemble failed: %s" % e})
                    continue
                one(fname, v, mut)
                if hangs >= 2:
                    rec.record({"instr": instr, "field": fname, "value": v, "bytes": "",
                                "observed": {}, "oracle": {}, "match": False, "outcome": "hang",
                                "carrier": cname,
                                "note": "STOP RULE: 2 hangs in arm %s -- arm abandoned PARTIAL" % arm_id})
                    aborted = True
                    break
        for brel, values in byteprobes.items():
            if aborted:
                break
            for v in values:
                mut = bytearray(iraw)
                mut[brel] = v
                one("byte+%d" % brel, v, bytes(mut),
                    "raw byte probe (not a db.json field)")
                if hangs >= 2:
                    rec.record({"instr": instr, "field": "byte+%d" % brel, "value": v,
                                "bytes": "", "observed": {}, "oracle": {}, "match": False,
                                "outcome": "hang", "carrier": cname,
                                "note": "STOP RULE: 2 hangs in arm %s -- arm abandoned PARTIAL" % arm_id})
                    aborted = True
                    break
        dt = time.time() - t0
        print("%-18s %-16s %5d cases  %5.1fs  hangs=%d%s"
              % (arm_id, instr, rec.n - n0, dt, hangs, "  ABORTED" if aborted else ""))
        c.close()

    # ------------------------------------------------------- 3. paired sweeps
    for (arm_id, instr, cname, off, pairs, note) in A.PAIRED:
        if only and arm_id not in only:
            continue
        msl, ins, outs, oidx, dec, oracle, tol = CAR[cname]
        c = S.Carrier(cname + "_" + arm_id, K / msl, ins, outs, 8, 8, run_dir, workdir,
                      timeout=args.timeout)
        irec, iraw = c.instr_at(off)
        names = [p[0] for p in pairs]
        n0 = rec.n
        t0 = time.time()
        import itertools
        for combo in itertools.product(*[p[1] for p in pairs]):
            f2 = dict(irec["fields"])
            for nm, v in zip(names, combo):
                f2[nm] = v
            mut = isadb.assemble(instr, f2)
            r = c.run_with_instr(off, mut)
            obs = dec(r["outs"].get(oidx, b""))
            oc, mt = S.classify(r["status"], obs, oracle, tol)
            observed = {"words": hexlist(obs), "status": r["status"]}
            if r.get("error"):
                observed["err"] = r["error"][:200]
                observed["fault_class"] = fault_class(r["error"])
            if r["status"] == "OK":
                lut = O.derive_lut2(O.LOGIC_A, O.LOGIC_B, obs)
                observed["lut"] = list(lut) if lut else None
                observed["fn"] = O.LUT_NAMES.get(lut) if lut else None
            rec.record({"instr": instr, "field": "+".join(names),
                        "value": list(combo), "bytes": mut.hex(), "observed": observed,
                        "oracle": {"words": hexlist(oracle)}, "match": mt, "outcome": oc,
                        "carrier": cname, "note": "%s | %s" % (arm_id, note)})
        print("%-18s %-16s %5d cases  %5.1fs" % (arm_id, instr, rec.n - n0, time.time() - t0))
        c.close()

    rec.record({"instr": "_meta", "field": "done", "value": rec.n, "bytes": "",
                "observed": {"cases": rec.n, "elapsed_s": round(time.time() - t_start, 1)},
                "oracle": {}, "match": True, "outcome": "ok", "carrier": "-", "note": "run complete"})
    print("TOTAL %d records in %.1fs -> %s" % (rec.n, time.time() - t_start, rec.path))
    rec.close()


if __name__ == "__main__":
    main()
