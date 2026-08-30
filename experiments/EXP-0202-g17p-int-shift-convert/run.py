#!/usr/bin/env python3
"""EXP-0202 sweep driver (runs ON THE NEO, under ~/agxre/EXP-0202).

  python3 run.py --run-id g17p_YYYYMMDD_runNN --arms harness/arms202.json [--only grp]

One JSON object per case is appended to `raw/<run_id>/sweep.jsonl` and
flush+fsync'd immediately -- never buffered to write at the end. A kill must cost
at most one case.

FROZEN BEHAVIOURS (PRE_REGISTRATION.md sections 2.2, 4, 5, 6):

* **NO ABORT PATH except one, named in advance.** Faults never abort. The only
  abort is the `irotate` JOINT 40-bit arm after 3 GENUINE hangs, pre-registered
  because a 2^40 space cannot be mapped by any sweep so FIELD-SWEEP-PROTOCOL
  3(c)'s objection to hang budgets does not apply there. If it fires, the arm is
  reported PARTIAL with the exact value it stopped at.
* **A malformed response is a MEASUREMENT FAILURE, never a hang** (3d).
* **Poisoned read-back, integrity sentinel, OS fault-classification string** on
  every case (section 7's three instruments).
* **The tokenized mnemonic of the MUTATED bytes is recorded on every case**, so
  "movement" that is really a different instruction is visible in the raw.
* **Never conclude `fault` from one observation**: every non-OK case goes to
  majority-of-3, `InnocentVictim` responses are retried first.
* **A per-value HOST oracle** from `harness/oracles202.py`, recorded per case.

CLEAN-ROOM: OWN-SHADER + HW-PROBE. Every byte dispatched is the compiled form of
our own MSL in `kernels/`, mutated in exactly one field.
Shape reused and cited from EXP-0184 run.py.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "harness"))

import carriers202 as C          # noqa: E402
import locate202 as L            # noqa: E402
import oracles202 as O           # noqa: E402
import saferunner202 as SR       # noqa: E402

PINNED = L.PINNED
SafeRunner = SR.make_classes(str(PINNED))

REQ_TIMEOUT = 8.0
CONFIRM_ATTEMPTS = 3
INNOCENT_RETRIES = 3
CANARY_RETRIES = 3
BASELINE_EVERY = 256
BIN = HERE / "work" / "bin"
WORK = HERE / "work"


def fault_class(resp):
    e = resp.get("error") or ""
    for k in ("InnocentVictim", "ErrorHang", "ErrorTimeout", "ErrorPageFault",
              "ErrorInvalidResource", "ErrorAccessViolation", "ErrorInnocent"):
        if k in e:
            return k
    return e[:160]


def is_innocent(resp):
    return "InnocentVictim" in (resp.get("error") or "")


class CarrierRunner:
    def __init__(self, name):
        self.name = name
        self.spec = C.CARRIERS[name]
        self.seq = 0
        self.spdir = WORK / "splice"
        self.spdir.mkdir(parents=True, exist_ok=True)
        indir = WORK / "inputs"
        indir.mkdir(parents=True, exist_ok=True)
        self.ins = {}
        for idx, (fn, blob) in C.out_inputs(name).items():
            p = indir / fn
            p.write_bytes(blob)
            self.ins[idx] = str(p)
        arch, off, main = L.compile_carrier(
            BIN, HERE / self.spec["metal"], self.spec["func"], WORK / "arch")
        self.archive = arch
        self.main_off = off
        self.main = main
        self.base = Path(arch).read_bytes()
        self.main_sha = hashlib.sha256(main).hexdigest()
        self.runner = SafeRunner(
            source=str(HERE / self.spec["metal"]), function=self.spec["func"],
            fast_math=False, agxrun_persist=str(BIN / "agxrun_persist"))
        self.device = self.runner.device

    def close(self):
        try:
            self.runner.close()
        except Exception:                                       # noqa: BLE001
            pass

    @staticmethod
    def patch_instr(raw, start, width, value):
        v = int.from_bytes(raw, "little")
        mask = ((1 << width) - 1) << start
        v = (v & ~mask) | ((value & ((1 << width) - 1)) << start)
        return v.to_bytes(len(raw), "little")

    def mutated_main(self, off, length, start, width, value):
        m = bytearray(self.main)
        if off is not None:
            m[off:off + length] = self.patch_instr(
                bytes(self.main[off:off + length]), start, width, value)
        return bytes(m)

    def blob(self, off, length, start, width, value):
        b = bytearray(self.base)
        if off is None:
            return bytes(b)
        b[self.main_off + off:self.main_off + off + length] = self.patch_instr(
            bytes(self.main[off:off + length]), start, width, value)
        return bytes(b)

    def submit(self, blob):
        self.seq += 1
        p = self.spdir / ("%s_%d.bin" % (self.name, self.seq))
        p.write_bytes(blob)
        try:
            return self.runner.request(
                archive=str(p), grid=self.spec["grid"], tg=self.spec["tg"],
                ins=self.ins, outs={0: 4 * self.spec["nwords"]},
                timeout=REQ_TIMEOUT)
        finally:
            try:
                os.unlink(str(p))
            except OSError:
                pass

    def issue(self, blob):
        statuses, classes, innocent = [], [], 0
        resp = self.submit(blob)
        while resp["status"] != "OK" and is_innocent(resp) and innocent < INNOCENT_RETRIES:
            classes.append(fault_class(resp))
            innocent += 1
            time.sleep(0.08 * innocent)
            resp = self.submit(blob)
        statuses.append(resp["status"])
        if resp["status"] != "OK":
            classes.append(fault_class(resp))
        best = resp
        if resp["status"] != "OK":
            for _ in range(CONFIRM_ATTEMPTS - 1):
                r2 = self.submit(blob)
                inn = 0
                while (r2["status"] != "OK" and is_innocent(r2)
                       and inn < INNOCENT_RETRIES):
                    classes.append(fault_class(r2))
                    inn += 1
                    time.sleep(0.08 * inn)
                    r2 = self.submit(blob)
                statuses.append(r2["status"])
                if r2["status"] != "OK":
                    classes.append(fault_class(r2))
                else:
                    best = r2
        nbad = sum(1 for s in statuses if s != "OK")
        return best, statuses, classes, innocent, nbad

    def measure(self, blob, oracle, expect):
        observed, resp = {}, {"status": "NONE"}
        statuses, classes, innocent = [], [], 0
        nvals = len(self.spec["val_words"])
        for _ in range(CANARY_RETRIES):
            resp, statuses, classes, innocent, nbad = self.issue(blob)
            if resp["status"] == "HANG":
                return ("hang", {"status": "HANG"}, False, "HANG",
                        statuses, classes, innocent)
            if resp["status"] == "MALFORMED":
                return ("measurement_failure",
                        {"status": "MALFORMED", "raw": resp.get("raw")}, False,
                        "MALFORMED", statuses, classes, innocent)
            blob_out = resp["outs"].get(0, b"")
            if not blob_out:
                return ("fault" if nbad >= 2 else "nondeterministic",
                        {"status": resp["status"]}, False, resp["status"],
                        statuses, classes, innocent)
            observed, words = C.summarize(self.name, blob_out)
            observed["status"] = resp["status"]
            observed["sentinel_ok"] = C.sentinel_ok(self.name, words)
            observed["tail_ok"] = C.tail_ok(self.name, words)
            observed["unwritten"] = C.unwritten(self.name, words)
            observed["gputime_ns"] = resp.get("gputime_ns")
            if resp["status"] != "OK":
                return ("fault" if nbad >= 2 else "nondeterministic", observed,
                        False, resp["status"], statuses, classes, innocent)
            # STATUS OK with nothing written is an INVALID RUN, not a silent zero
            # (EXP-0160: 25 such cases, no victim string anywhere).
            if not observed["sentinel_ok"] and \
                    len(observed["unwritten"]) == nvals:
                time.sleep(0.05)
                continue
            if not observed["sentinel_ok"]:
                time.sleep(0.05)
                continue
            oc, m = O.score(self.name, words, oracle, expect,
                            len(observed["unwritten"]), nvals)
            return (oc, observed, bool(m), resp["status"], statuses, classes,
                    innocent)
        return ("invalid_run", observed, False, resp.get("status"), statuses,
                classes, innocent)


def emit(f, rec):
    f.write(json.dumps(rec, sort_keys=True, separators=(",", ":"), default=str) + "\n")
    f.flush()
    os.fsync(f.fileno())


def env_report(run_dir, arms, run_id):
    def sh(*c):
        try:
            return subprocess.check_output(c, text=True, timeout=30).strip()
        except Exception as e:                                  # noqa: BLE001
            return "ERR %s" % e
    rep = {
        "run_id": run_id,
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "host": sh("hostname"),
        "os": sh("sw_vers", "-productVersion"),
        "build": sh("sw_vers", "-buildVersion"),
        "cpu": sh("sysctl", "-n", "machdep.cpu.brand_string"),
        "python": sys.version.split()[0],
        "pinned_db_sha256": hashlib.sha256((PINNED / "db.json").read_bytes()).hexdigest(),
        "pinned_isadb_sha256": hashlib.sha256((PINNED / "isadb.py").read_bytes()).hexdigest(),
        "arms_sha256": hashlib.sha256(Path(arms).read_bytes()).hexdigest(),
        "concurrent_gpu_procs": sh("bash", "-lc",
                                   "ps -Ao pid,comm | grep -E 'agxrun|rendersweep|gfrun|shdump' "
                                   "| grep -v grep | head -40"),
    }
    (run_dir / "env.json").write_text(json.dumps(rep, indent=1))
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--arms", default=str(HERE / "harness" / "arms202.json"))
    ap.add_argument("--only", default="")
    ap.add_argument("--limit-values", type=int, default=0)
    args = ap.parse_args()

    arms = json.loads(Path(args.arms).read_text())["arms"]
    if args.only:
        keep = set(args.only.split(","))
        arms = [a for a in arms if a.get("group") in keep]
    run_dir = HERE / "raw" / args.run_id
    if run_dir.exists():
        sys.stderr.write("REFUSING: run id %s already exists. Run ids are never "
                         "reused; a partial run is retained, never topped up.\n"
                         % args.run_id)
        return 2
    run_dir.mkdir(parents=True)
    env_report(run_dir, args.arms, args.run_id)
    sweep = open(run_dir / "sweep.jsonl", "a")

    by_carrier = {}
    for a in arms:
        by_carrier.setdefault(a["carrier"], []).append(a)

    ncase = 0
    t0 = time.time()
    for carrier, carms in by_carrier.items():
        try:
            cr = CarrierRunner(carrier)
        except Exception as e:                                  # noqa: BLE001
            emit(sweep, {"carrier": carrier, "outcome": "carrier_start_failed",
                         "note": str(e)[:400]})
            continue
        emit(sweep, {"carrier": carrier, "outcome": "carrier_ready",
                     "note": json.dumps({"device": cr.device,
                                         "main_len": len(cr.main),
                                         "main_sha256": cr.main_sha,
                                         "main_off": cr.main_off,
                                         "grid": cr.spec["grid"], "tg": cr.spec["tg"],
                                         "archive_sha256": hashlib.sha256(cr.base).hexdigest()})})

        def baseline(tag):
            ora = {"class": "exact", "rule": "baseline", "vals": cr.spec["oracle"]}
            oc, obs, m, st, sts, cls, inn = cr.measure(
                cr.blob(None, 0, 0, 0, 0), ora, cr.spec["oracle"])
            emit(sweep, {"carrier": carrier, "arm": tag, "instr": "-",
                         "field": "_baseline", "value": -1,
                         "bytes": "", "token": None,
                         "observed": obs, "oracle": ora,
                         "match": m, "outcome": oc, "status": st,
                         "statuses": sts, "fault_classes": cls,
                         "innocent_retries": inn, "role": "baseline",
                         "grid": cr.spec["grid"], "tg": cr.spec["tg"],
                         "note": tag, "ts": time.time()})
            return oc

        baseline("carrier_open")
        for a in carms:
            off, ilen = a["off"], a["len"]
            start, width = a["start"], a["width"]
            vals = a["values"]
            if args.limit_values > 1:
                vals = vals[::args.limit_values]
            budget = int(a.get("hang_budget", 0))
            hangs = 0
            baseline(a["arm"] + ":open")
            for n, v in enumerate(vals):
                ora, expect = O.predict(a, carrier, v)
                blob = cr.blob(off, ilen, start, width, v)
                mm = cr.mutated_main(off, ilen, start, width, v)
                tok = L.token_at(mm, off)
                oc, obs, m, st, sts, cls, inn = cr.measure(blob, ora, expect)
                rec = {
                    "carrier": carrier, "arm": a["arm"], "instr": a["instr"],
                    "field": a["field"], "value": v,
                    "bytes": mm[off:off + ilen].hex(),
                    "token": tok, "observed": obs, "oracle": ora,
                    "match": m, "outcome": oc, "status": st, "statuses": sts,
                    "fault_classes": cls, "innocent_retries": inn,
                    "role": a.get("role", "target"), "occ": a.get("occ"),
                    "off": off, "instr_len": ilen,
                    "start": a["start"], "width": a["width"],
                    "grid": cr.spec["grid"], "tg": cr.spec["tg"],
                    "baseline_field_value": a.get("baseline_field_value"),
                    "note": a.get("note", ""), "ts": time.time(),
                }
                emit(sweep, rec)
                ncase += 1
                if oc == "hang":
                    hangs += 1
                    if budget and hangs >= budget:
                        emit(sweep, {"carrier": carrier, "arm": a["arm"],
                                     "instr": a["instr"], "field": a["field"],
                                     "value": v, "outcome": "arm_aborted",
                                     "role": "meta",
                                     "note": "PRE-REGISTERED abort: %d genuine "
                                             "hangs on the joint 40-bit arm; "
                                             "reported PARTIAL at this value"
                                             % hangs, "ts": time.time()})
                        break
                if n and n % BASELINE_EVERY == 0:
                    baseline(a["arm"] + ":mid%d" % n)
            baseline(a["arm"] + ":close")
            print("[%6.1fs] %-10s %-34s %d values" %
                  (time.time() - t0, carrier, a["arm"], len(vals)), flush=True)
        cr.close()
        time.sleep(0.2)

    sweep.close()
    print("cases=%d elapsed=%.1fs -> %s" % (ncase, time.time() - t0, run_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
