#!/usr/bin/env python3
"""EXP-0141 sweep executor.

Runs every arm of `sweepdefs.build_all()` against the local M4 through
`tools/agxtest/agxrun_persist` (one live MTLDevice per carrier; a fresh
MTLLibrary is loaded from each spliced archive, so every case's bytes really
execute) and APPENDS one JSON record per case to `raw/<run_id>/sweep.jsonl`,
flushing + fsync-ing after every record. Nothing is buffered to the end: a kill
at any point loses at most the case in flight.

Safety (FIELD-SWEEP-PROTOCOL 7): per-request watchdog; after TWO genuine hangs
in one arm the arm is ABORTED and marked PARTIAL, and after HANG_STOP_CARRIER
hangs on one carrier the whole carrier is abandoned. Faults and hangs are
recorded as results, never dropped.
"""
import argparse
import hashlib
import json
import os
import struct
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
REPO = EXP.parents[1]
sys.path.insert(0, str(EXP))
sys.path.insert(0, str(REPO / "tools" / "agxtest"))
import carriers as C  # noqa: E402
import sweepdefs as SD  # noqa: E402
import locate as LOC  # noqa: E402
from persistrun import PersistRunner  # noqa: E402

def _transient(resp):
    e = (resp.get("error") or "")
    return "Innocent" in e or "Discarded (victim" in e


HANG_STOP_ARM = 2
HANG_STOP_CARRIER = 6
REQ_TIMEOUT = 8.0


def _silent_signature(case):
    o = case.get("oracle")
    if o == SD.ALU_ORACLE:
        return ("f", SD.K_SMALL)          # srcA read as 0 -> immediate alone
    if o == SD.FWD_ORACLE:
        return ("f", 0.0)
    return ("z", 0)                        # all-zero output


def classify(case, status, observed, match):
    if status == "HANG":
        return "hang"
    if status != "OK":
        return "fault"
    if match:
        return "ok"
    kind, val = _silent_signature(case)
    got = observed.get("out0")
    if kind == "f" and got and got[0] == val:
        return "silent_zero"
    if kind == "z":
        n = observed.get("n_0")
        allz = all(v == 0 for v in (got or [1]))
        if allz and n:
            return "silent_zero"
    return "wrong_value"


def run_carrier(carrier, arms, bin_dir, work, fres, sites, mains, progress):
    spec = C.CARRIERS[carrier]
    arch_src, main_off, main = mains[carrier]
    base = Path(arch_src).read_bytes()
    ins = {}
    for idx, (fn, data) in spec["inputs"].items():
        p = work / fn
        p.write_bytes(data)
        ins[idx] = str(p)
    spdir = work / "sp"
    spdir.mkdir(exist_ok=True)
    seq = [0]

    def submit(blob, timeout=REQ_TIMEOUT):
        """One request, on a UNIQUE archive path.

        HARNESS FINDING (this experiment's own pilot, work/ stability probe):
        REUSING one archive filename across persistent-runner requests -- the
        pattern in RT-1a-FIX/harness/mem_index.py -- produces a ~7-8 % rate of
        SPURIOUS `CMDBUF_ERROR` on byte-identical, known-good archives
        (28 / 360 unmutated requests over three carriers). Giving every request
        its own path and unlinking it afterwards drove that to 0 / 360.
        Overwriting a file the driver may still hold mapped is the mechanism we
        infer; either way, a fresh inode per request is required or a sweep
        will report phantom faults."""
        seq[0] += 1
        p = spdir / ("%s_%d.bin" % (carrier, seq[0]))
        p.write_bytes(blob)
        try:
            return r.request(archive=str(p), grid=spec["grid"], tg=spec["tg"],
                             ins=ins, outs=spec["outs"], timeout=timeout)
        finally:
            try:
                os.unlink(p)
            except OSError:
                pass

    r = PersistRunner(source=str(EXP / spec["metal"]), function=spec["func"],
                      fast_math=False,
                      agxrun_persist=str(Path(bin_dir) / "agxrun_persist"))
    carrier_hangs = 0
    try:
        for arm in arms:
            arm_hangs = 0
            aborted = None
            t0 = time.time()
            for n, case in enumerate(arm["cases"]):
                b = bytearray(base)
                if case["kind"] == "synth":
                    prog = bytes.fromhex(case["prog"])
                    b[main_off:main_off + len(prog)] = prog
                else:
                    for rel, hx in case["splice"]:
                        by = bytes.fromhex(hx)
                        b[main_off + rel:main_off + rel + len(by)] = by
                blob = bytes(b)
                resp = submit(blob)
                attempts = [resp["status"]]
                # A GPU fault poisons the NEXT command buffers, which come back
                # as `kIOGPUCommandBufferCallbackErrorInnocentVictim /
                # Discarded (victim of GPU error/recovery)`. That is a HARNESS
                # artifact of the preceding case, not a property of this case's
                # bytes, so it is retried (bounded) rather than recorded as a
                # fault. Every attempt's status is kept in the record.
                tries = 0
                while resp["status"] != "OK" and tries < 4 and _transient(resp):
                    time.sleep(0.08 * (tries + 1))
                    resp = submit(blob)
                    attempts.append(resp["status"])
                    tries += 1
                # A non-transient non-OK is re-issued ONCE so a genuine
                # encoding fault is distinguishable from a one-off; a
                # disagreement is reported as `nondeterministic`.
                repeat_status = None
                if resp["status"] != "OK":
                    r2 = submit(blob)
                    repeat_status = r2["status"]
                    attempts.append(r2["status"])
                    if r2["status"] == "OK":
                        resp = r2
                oracle = case.get("oracle")
                observed, match = C.summarize(carrier, resp["outs"], oracle)
                if resp["status"] != "OK":
                    match = False
                outcome = classify(case, resp["status"], observed, match)
                if repeat_status is not None and (repeat_status == "OK") != (resp["status"] == "OK"):
                    outcome = "nondeterministic"
                rec = {"arm": arm["arm"], "i": n, "carrier": carrier,
                       "instr": case["instr"], "field": case["field"],
                       "value": case["value"], "bytes": case["ibytes"],
                       "observed": observed,
                       "oracle": oracle if oracle is not None else {"ref": "carrier:" + carrier},
                       "match": bool(match), "outcome": outcome,
                       "status": resp["status"], "rt": case.get("rt"),
                       "repeat_status": repeat_status,
                       "attempts": attempts if len(attempts) > 1 else None,
                       "error": (resp.get("error") or "")[:110] or None,
                       "expect_match": case["expect_match"], "note": case["note"]}
                fres.write(json.dumps(rec, sort_keys=True, separators=(",", ":")) + "\n")
                fres.flush()
                os.fsync(fres.fileno())
                if outcome == "hang":
                    arm_hangs += 1
                    carrier_hangs += 1
                    if arm_hangs >= HANG_STOP_ARM:
                        aborted = "arm aborted after %d hangs at case %d/%d" % (
                            arm_hangs, n + 1, len(arm["cases"]))
                        break
                    if carrier_hangs >= HANG_STOP_CARRIER:
                        aborted = "carrier abandoned after %d hangs" % carrier_hangs
                        break
            progress.append({"arm": arm["arm"], "carrier": carrier,
                             "cases_run": n + 1, "cases_total": len(arm["cases"]),
                             "seconds": round(time.time() - t0, 2),
                             "hangs": arm_hangs, "aborted": aborted})
            print("  %-28s %4d/%-4d %6.2fs%s" % (arm["arm"], n + 1,
                  len(arm["cases"]), time.time() - t0,
                  "  ABORTED: " + aborted if aborted else ""), flush=True)
            if carrier_hangs >= HANG_STOP_CARRIER:
                break
    finally:
        r.close()
    return carrier_hangs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--bin-dir", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--raw", required=True)
    ap.add_argument("--only-carrier", default=None)
    ap.add_argument("--arms-regex", default=None,
                    help="smoke/debug only: restrict to arms matching this regex")
    a = ap.parse_args()
    work = Path(a.work)
    work.mkdir(parents=True, exist_ok=True)
    raw = Path(a.raw)
    raw.mkdir(parents=True, exist_ok=True)

    sites, mains = LOC.locate_all(a.bin_dir, work)
    # the synthesis carrier is not a splice site; compile it here
    arch, moff, main = LOC.compile_carrier("synth", a.bin_dir, work)
    if len(main) != SD.CARRIER_LEN:
        raise SystemExit("synth carrier _agc.main length %d != %d"
                         % (len(main), SD.CARRIER_LEN))
    mains["synth"] = (str(arch), moff, main)

    arms = SD.build_all(sites)
    if a.arms_regex:
        import re
        rx = re.compile(a.arms_regex)
        arms = [x for x in arms if rx.search(x["arm"])]
    by_carrier = {}
    for arm in arms:
        if arm["carrier"] == "multi":
            continue
        by_carrier.setdefault(arm["carrier"], []).append(arm)
    # the multi-carrier control arm is split per case
    ctrl = [x for x in arms if x["carrier"] == "multi"]
    for arm in ctrl:
        groups = {}
        for c in arm["cases"]:
            groups.setdefault(c["carrier"], []).append(c)
        for cname, cases in groups.items():
            by_carrier.setdefault(cname, []).insert(
                0, {"arm": "CTRL_SPLICE", "carrier": cname, "instr": "-",
                    "field": "_controls", "cases": cases, "doc": arm["doc"]})

    manifest = {"run_id": a.run_id,
                "sites": {k: [v[0], v[1], v[2], v[3].hex()] for k, v in sites.items()},
                "mains": {c: {"main_off": mo, "main_len": len(mm),
                              "main_sha256": hashlib.sha256(mm).hexdigest()}
                          for c, (ap_, mo, mm) in mains.items()},
                "arms": [{"arm": x["arm"], "carrier": x["carrier"],
                          "instr": x["instr"], "field": x["field"],
                          "n_cases": len(x["cases"]), "doc": x["doc"]}
                         for x in arms],
                "n_cases": sum(len(x["cases"]) for x in arms),
                "carrier_oracles": {k: (v["oracle"] if k != "tgtile" else "ramp(256)")
                                    for k, v in C.CARRIERS.items()}}
    (raw / "00_manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")

    progress = []
    order = [c for c in ("synth", "atdev", "atdevimm", "attg", "tgtile", "devfence")
             if c in by_carrier and (a.only_carrier in (None, c))]
    with open(raw / "sweep.jsonl", "a") as fres:
        for cname in order:
            print("carrier %s (%d arms)" % (cname, len(by_carrier[cname])), flush=True)
            run_carrier(cname, by_carrier[cname], a.bin_dir, work, fres,
                        sites, mains, progress)
    (raw / "01_progress.json").write_text(json.dumps(progress, indent=1) + "\n")
    print("DONE %s: %d cases planned" % (a.run_id, manifest["n_cases"]))


if __name__ == "__main__":
    main()
