#!/usr/bin/env python3
"""EXP-0205 sweep driver (runs ON THE NEO, under ~/agxre/EXP-0205).

  python3 run.py --run-id g17p_YYYYMMDD_runNN [--only ballot,reduce,shuffle]
                 [--limit-values N]

One JSON object per case is appended to `raw/<run_id>/sweep.jsonl` and
flush+fsync'd IMMEDIATELY -- never buffered to write at the end.  A kill must
cost at most one case.

FROZEN BEHAVIOURS (PRE_REGISTRATION.md section 6; nothing else may promote):

* **NO ABORT PATH, no per-field hang budget.**  FIELD-SWEEP-PROTOCOL 3(c): a
  budget cannot characterise a contiguous hazard, it guarantees the region is
  never mapped.  Every value in every arm is dispatched.
* **A malformed response is a MEASUREMENT FAILURE, not a hang** (3d), via the
  pinned `saferunner`: one reader thread per child, tagged by owner.  A false
  hang and real inertness are indistinguishable in a summary, and telling those
  apart is this experiment's whole difficulty.
* **Poisoned read-back, integrity sentinel, and the OS fault-classification
  string on every case** (protocol section 7).
* **The tokenized mnemonic of the MUTATED bytes is recorded on every case**, so
  "movement" that is really a DIFFERENT INSTRUCTION is visible in the raw --
  and so is our own disassembler merely failing to decode, which a prior gate
  mistook for hardware movement.
* **Never conclude `fault` from one observation**: every non-OK case goes to
  majority-of-3 and `InnocentVictim` responses are retried first.
* **A dispatch that reports OK and writes nothing is `invalid_run`**, retried,
  never scored as a silent zero (EXP-0160 saw 25 such, with no victim string).

OUTCOME VOCABULARY (protocol section 4, plus this experiment's extensions,
declared in the pre-registration):
  ok | wrong_value | silent_zero | not_written | unpredicted | fault | hang |
  measurement_failure | invalid_run | nondeterministic
`unpredicted` means WE MADE NO PREDICTION for this value and are recording the
observation.  It is never a pass; movement is computed from the observed vector
in analysis, not from the outcome name.

CLEAN-ROOM: OWN-SHADER + HW-PROBE.  Every byte dispatched is the compiled form
of our own MSL in kernels/, mutated in exactly one field.  No Apple binary is
disassembled.
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

import carriers205 as C          # noqa: E402
import locate205 as L            # noqa: E402
import saferunner205 as SR       # noqa: E402

PINNED = L.PINNED
SafeRunner = SR.make_classes(str(PINNED))

# ------------------------------------------------------------------- frozen
REQ_TIMEOUT = 8.0
CONFIRM_ATTEMPTS = 3
INNOCENT_RETRIES = 3
CANARY_RETRIES = 3
BASELINE_EVERY = 128
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

    def mutated_main(self, off, length, start, width, value):
        m = bytearray(self.main)
        if off is not None:
            m[off:off + length] = L.patch_instr(
                bytes(self.main[off:off + length]), start, width, value)
        return bytes(m)

    def blob(self, off, length, start, width, value):
        b = bytearray(self.base)
        if off is None:
            return bytes(b)
        b[self.main_off + off:self.main_off + off + length] = L.patch_instr(
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

    def measure(self, blob, expect):
        observed, resp = {}, {"status": "NONE"}
        statuses, classes, innocent = [], [], 0
        for _ in range(CANARY_RETRIES):
            resp, statuses, classes, innocent, nbad = self.issue(blob)
            if resp["status"] == "HANG":
                return ("hang", {"status": "HANG"}, None, "HANG",
                        statuses, classes, innocent)
            if resp["status"] == "MALFORMED":
                return ("measurement_failure",
                        {"status": "MALFORMED", "raw": resp.get("raw")}, None,
                        "MALFORMED", statuses, classes, innocent)
            out = resp["outs"].get(0, b"")
            if not out:
                return ("fault" if nbad >= 2 else "nondeterministic",
                        {"status": resp["status"]}, None, resp["status"],
                        statuses, classes, innocent)
            observed, words = C.summarize(self.name, out)
            observed["status"] = resp["status"]
            observed["sentinel_ok"] = C.sentinel_ok(self.name, words)
            observed["unwritten"] = C.unwritten(self.name, words)
            observed["gputime_ns"] = resp.get("gputime_ns")
            if resp["status"] != "OK":
                return ("fault" if nbad >= 2 else "nondeterministic", observed,
                        None, resp["status"], statuses, classes, innocent)
            # OK + wrote nothing at all is an INVALID RUN, not a silent zero.
            if not observed["sentinel_ok"]:
                time.sleep(0.05)
                continue
            m = C.match_oracle(self.name, words, expect)
            if m is True:
                oc = "ok"
            elif len(observed["unwritten"]) == len(self.spec["val_words"]):
                oc = "not_written"
            elif all(v == 0 for v in observed["vals_u32"]):
                oc = "silent_zero"
            elif m is None:
                oc = "unpredicted"
            else:
                oc = "wrong_value"
            return (oc, observed, m, resp["status"], statuses, classes, innocent)
        return ("invalid_run", observed, None, resp.get("status"), statuses,
                classes, innocent)


def emit(f, rec):
    f.write(json.dumps(rec, sort_keys=True, separators=(",", ":"),
                       default=str) + "\n")
    f.flush()
    os.fsync(f.fileno())


def env_report(run_dir, arms_path, run_id):
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
        "arms_sha256": hashlib.sha256(Path(arms_path).read_bytes()).hexdigest(),
        "carriers_sha256": hashlib.sha256(
            (HERE / "harness" / "carriers205.py").read_bytes()).hexdigest(),
        "concurrent_gpu_procs": sh(
            "bash", "-lc",
            "ps -Ao pid,comm | grep -E 'agxrun|rendersweep|gfrun|shdump' "
            "| grep -v grep | head -40"),
    }
    (run_dir / "env.json").write_text(json.dumps(rep, indent=1))
    return rep


def width_probe(run_dir, sweep):
    """Unspliced SIMD-width measurement, once per gated run.  The width is an
    OBSERVATION in every run's raw, never an assumption carried between runs."""
    cr = CarrierRunner("sb_width")
    oc, obs, m, st, sts, cls, inn = cr.measure(cr.blob(None, 0, 0, 0, 0), None)
    vals = obs.get("vals_u32") or []
    emit(sweep, {"carrier": "sb_width", "arm": "sb_width#probe", "instr": "-",
                 "field": "_width_probe", "value": -1, "bytes": "",
                 "token": None, "observed": obs, "match": None,
                 "outcome": oc, "status": st, "statuses": sts,
                 "fault_classes": cls, "innocent_retries": inn,
                 "role": "probe",
                 "simd_width": sorted({(v >> 16) & 0xFFFF for v in vals}),
                 "lane_ids": [v & 0xFF for v in vals],
                 "simdgroup_ids": sorted({(v >> 8) & 0xFF for v in vals}),
                 "note": "measured, not assumed", "ts": time.time()})
    cr.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--arms", default=str(HERE / "harness" / "arms205.json"))
    ap.add_argument("--only", default="")
    ap.add_argument("--limit-values", type=int, default=0,
                    help="PILOT ONLY: dispatch every Nth value")
    args = ap.parse_args()

    doc = json.loads(Path(args.arms).read_text())
    arms = doc["arms"]
    if args.only:
        keep = set(args.only.split(","))
        arms = [a for a in arms if a["group"] in keep or a["carrier"] in keep]
    run_dir = HERE / "raw" / args.run_id
    if run_dir.exists():
        sys.stderr.write("REFUSING: run id %s already exists. Run ids are never "
                         "reused; a partial run is retained, never topped up.\n"
                         % args.run_id)
        return 2
    run_dir.mkdir(parents=True)
    env_report(run_dir, args.arms, args.run_id)
    sweep = open(run_dir / "sweep.jsonl", "a")

    width_probe(run_dir, sweep)

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
                         "note": str(e)[:400], "ts": time.time()})
            continue
        base_expect = C.baseline_oracle(carrier)
        emit(sweep, {"carrier": carrier, "outcome": "carrier_ready",
                     "note": json.dumps({
                         "device": cr.device, "main_len": len(cr.main),
                         "main_sha256": cr.main_sha, "main_off": cr.main_off,
                         "archive_sha256": hashlib.sha256(cr.base).hexdigest()}),
                     "ts": time.time()})

        def baseline(tag):
            oc, obs, m, st, sts, cls, inn = cr.measure(
                cr.blob(None, 0, 0, 0, 0), base_expect)
            emit(sweep, {"carrier": carrier, "arm": tag, "instr": "-",
                         "field": "_baseline", "value": -1, "bytes": "",
                         "token": None, "observed": obs, "match": m,
                         "outcome": oc, "status": st, "statuses": sts,
                         "fault_classes": cls, "innocent_retries": inn,
                         "role": "baseline", "note": tag, "ts": time.time()})
            return oc

        baseline("%s#carrier_open" % carrier)
        for a in carms:
            off, ilen = a["off"], a["len"]
            start, width = a["start"], a["width"]
            vals = a["values"]
            if args.limit_values > 1:
                vals = vals[::args.limit_values]
            baseline(a["arm"] + ":open")
            for n, v in enumerate(vals):
                expect = C.oracle_for(carrier, a["instr"], a["field"], v) \
                    if a["role"] == "target" else base_expect
                blob = cr.blob(off, ilen, start, width, v)
                mm = cr.mutated_main(off, ilen, start, width, v)
                tok = L.token_at(mm, off)
                oc, obs, m, st, sts, cls, inn = cr.measure(blob, expect)
                emit(sweep, {
                    "carrier": carrier, "arm": a["arm"], "instr": a["instr"],
                    "field": a["field"], "value": v,
                    "bytes": mm[off:off + ilen].hex(), "token": tok,
                    "observed": obs,
                    "oracle": (["0x%08x" % (x & C.M32) for x in expect]
                               if expect else None),
                    "match": m, "outcome": oc, "status": st, "statuses": sts,
                    "fault_classes": cls, "innocent_retries": inn,
                    "role": a["role"], "occ": a["occ"], "off": off,
                    "instr_len": ilen, "start": start, "width": width,
                    "baseline_field": a["baseline_field"],
                    "note": a.get("note", ""), "ts": time.time()})
                ncase += 1
                if n and n % BASELINE_EVERY == 0:
                    baseline(a["arm"] + ":mid%d" % n)
            baseline(a["arm"] + ":close")
            print("[%6.1fs] %-11s %-30s %d values" %
                  (time.time() - t0, carrier, a["arm"], len(vals)), flush=True)
        cr.close()
        time.sleep(0.3)

    sweep.close()
    print("cases=%d elapsed=%.1fs -> %s" % (ncase, time.time() - t0, run_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
