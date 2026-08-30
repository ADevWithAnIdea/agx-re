#!/usr/bin/env python3
"""EXP-0206 sweep driver (runs ON THE NEO, under ~/agxre/EXP-0206).

  python3 run.py --run-id g17p_YYYYMMDD_runNN [--arms harness/arms206.json]
                 [--only if_push.scope,...] [--limit-values N]

One JSON object per case is appended to `raw/<run_id>/sweep.jsonl` and
flush+fsync'd immediately -- never buffered to write at the end. The host has
crashed mid-run before; a kill must cost at most one case.

FROZEN BEHAVIOURS (PRE_REGISTRATION.md sections 6, 7 and 10):

* **NO ABORT PATH, NO HANG BUDGET** (FIELD-SWEEP-PROTOCOL 3c): a per-field budget
  cannot characterise a CONTIGUOUS hazard -- it guarantees the region is never
  mapped. `frag_color_pack.dst` has an exact wall at 0xC0 that three experiments
  walked into and none saw, because a budget of 2 discovers exactly two more
  hazardous values and stops. Every value in every arm is dispatched.
* **A malformed response is a MEASUREMENT FAILURE, not a hang** (3d), with the
  raw lines kept. See harness/saferunner206.py.
* **Poisoned read-back, integrity sentinel, OS fault-classification string** on
  every case (protocol section 7, the three instruments). For control flow the
  poison is what separates "took the branch" from "never ran".
* **The tokenized mnemonic of the MUTATED bytes is recorded on every case**, so
  "movement" that is really a DIFFERENT INSTRUCTION is visible in the raw.
* **Never conclude `fault` from a single observation**: every non-OK case goes to
  majority-of-3, and `InnocentVictim` responses are retried first.
* **`gputime_ns` is NOT part of `observed`.** It varies run to run, so folding it
  into the observed payload would make every case distinct and manufacture
  movement out of scheduling noise.

CLEAN-ROOM: OWN-SHADER + HW-PROBE. Every byte dispatched is the compiled form of
our own MSL in `kernels/`, mutated in exactly one field. No Apple binary is
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

import carriers206 as C          # noqa: E402
import locate206 as L            # noqa: E402
import saferunner206 as SR       # noqa: E402

PINNED = L.PINNED
SafeRunner, _AS = SR.make_classes(str(PINNED))

REQ_TIMEOUT = 8.0
CONFIRM_ATTEMPTS = 3
INNOCENT_RETRIES = 3
CANARY_RETRIES = 3
BASELINE_EVERY = 128
BIN = HERE / "work" / "bin"
WORK = HERE / "work"


def h8(vals):
    return hashlib.sha256(
        json.dumps(vals, separators=(",", ":")).encode()).hexdigest()[:12]


def fault_class(resp):
    e = resp.get("error") or ""
    for k in ("InnocentVictim", "ErrorHang", "ErrorTimeout", "ErrorPageFault",
              "ErrorInvalidResource", "ErrorAccessViolation", "ErrorInnocent"):
        if k in e:
            return k
    return e[:160]


def is_innocent(resp):
    return "InnocentVictim" in (resp.get("error") or "")


# outcome -> the token `tools/agx-isa/wave_audit.py` recognises as a HARD outcome.
# Hard outcomes are counted and reported but are NEVER movement: a gate that
# separates `ok` from `fault` counts a GPU fault as evidence, which is exactly the
# defect that withdrew `ret_luse.linkmode`.
# `not_written` is DELIBERATELY ABSENT. It is only ever reached with the INTEGRITY
# SENTINEL PRESENT, so it means "the program ran, wrote the sentinel, and wrote no
# value words" -- a valid execution with a highly informative payload, and exactly
# how a MID-PROGRAM TERMINATOR announces itself (pilot p01: a synthesized `stop`
# over the optional frame marker gives sentinel + 32 poison words). Scoring it as a
# hard outcome would delete the one observation the termination-dimension positive
# control exists to make. `invalid_run` -- sentinel MISSING -- stays hard.
HARD_CLASS = {
    "fault": "fault",
    "hang": "hang",
    "invalid_run": "no_draw",
    "measurement_failure": "MALFORMED",
    "nondeterministic": "fault",
    "carrier_start_failed": "fault",
}


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
        self.timeout = REQ_TIMEOUT
        arch, regions = L.compile_carrier(
            BIN, HERE / self.spec["metal"], self.spec["func"], WORK / "arch")
        self.archive = arch
        # A kernel with an out-of-line callee puts the callee in its OWN symbol
        # region; `_agc.main` holds the CALL but not the callee's RETURN. Every
        # region is carved and splice-addressed separately.
        self.regions = regions
        self.region_sha = {rn: hashlib.sha256(r["bytes"]).hexdigest()[:16]
                           for rn, r in regions.items()}
        self.base = Path(arch).read_bytes()
        self.oracle_h = h8(self.spec["oracle"])
        exe = str(BIN / "agxrun_persist")
        self.runner = SafeRunner(
            source=str(HERE / self.spec["metal"]), function=self.spec["func"],
            fast_math=False, agxrun_persist=exe)
        self.device = self.runner.device

    def close(self):
        try:
            self.runner.close()
        except Exception:                                       # noqa: BLE001
            pass

    @staticmethod
    def patch_instr(raw, start, width, value):
        """Replace bits [start, start+width) of ONE instruction, little-endian
        over its own byte string -- the same bit convention `isadb._get_bits`
        uses to decode. Neighbouring bits (match constants, adjacent fields) are
        preserved exactly."""
        v = int.from_bytes(raw, "little")
        mask = ((1 << width) - 1) << start
        v = (v & ~mask) | ((value & ((1 << width) - 1)) << start)
        return v.to_bytes(len(raw), "little")

    def mutate(self, region, off, length, ops):
        """ops = [(start, width, value), ...] applied in order to the SAME
        instruction of ONE region. `force` pre-mutations (ret byte+2 0x54 -> 0x56,
        which synthesizes the `ret_luse` descriptor from a real compiled `ret`;
        frame_marker byte0 0x43 -> 0x0e, which synthesizes a MID-PROGRAM stop over
        an instruction EXP-0179 established is optional) come first; the swept
        field comes last."""
        m = bytearray(self.regions[region]["bytes"])
        if off is None:
            return bytes(m)
        raw = bytes(m[off:off + length])
        for (s, w, v) in ops:
            raw = self.patch_instr(raw, s, w, v)
        m[off:off + length] = raw
        return bytes(m)

    def blob(self, region, region_bytes):
        b = bytearray(self.base)
        a = self.regions[region]["abs"]
        b[a:a + len(region_bytes)] = region_bytes
        return bytes(b)

    def submit(self, blob):
        self.seq += 1
        p = self.spdir / ("%s_%d.bin" % (self.name, self.seq))
        p.write_bytes(blob)
        try:
            return self.runner.request(
                archive=str(p), grid=self.spec["grid"], tg=self.spec["tg"],
                ins=self.ins, outs={0: 4 * self.spec["nwords"]},
                timeout=self.timeout)
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

    def measure(self, blob):
        """-> dict(outcome, observed, vals, match, status, statuses, classes,
        innocent, gputime_ns)"""
        res = {"outcome": "invalid_run", "observed": None, "vals": None,
               "match": False, "status": "NONE", "statuses": [],
               "fault_classes": [], "innocent_retries": 0, "gputime_ns": None}
        for _ in range(CANARY_RETRIES):
            resp, statuses, classes, innocent, nbad = self.issue(blob)
            res.update(statuses=statuses, fault_classes=classes,
                       innocent_retries=innocent, status=resp["status"],
                       gputime_ns=resp.get("gputime_ns"))
            if resp["status"] == "HANG":
                res.update(outcome="hang", observed={"status": "HANG"})
                return res
            if resp["status"] == "MALFORMED":
                res.update(outcome="measurement_failure",
                           observed={"status": "MALFORMED"},
                           vals=None)
                res["raw_lines"] = resp.get("raw")
                return res
            blob_out = resp["outs"].get(0, b"")
            if not blob_out:
                res.update(outcome="fault" if nbad >= 2 else "nondeterministic",
                           observed={"status": resp["status"]})
                return res
            obs_full, words = C.summarize(self.name, blob_out)
            vals = obs_full["vals_u32"]
            sent = C.sentinel_ok(self.name, words)
            unw = C.unwritten(self.name, words)
            observed = {"vh": h8(vals),
                        "sent": obs_full["sent_u32"],
                        "nunwritten": len(unw),
                        "tail_ok": C.tail_ok(self.name, words)}
            res.update(observed=observed, vals=vals)
            if resp["status"] != "OK":
                res.update(outcome="fault" if nbad >= 2 else "nondeterministic")
                return res
            # A dispatch that reported OK and wrote NOTHING is an INVALID RUN,
            # not a silent zero (EXP-0160 saw 25 such, no victim string).
            if not sent and len(unw) == len(self.spec["val_words"]):
                time.sleep(0.05)
                continue
            if not sent:
                res.update(outcome="invalid_run")
                time.sleep(0.05)
                continue
            match = C.match_oracle(self.name, blob_out)
            if match:
                oc = "ok"
            elif len(unw) == len(self.spec["val_words"]):
                oc = "not_written"
            elif all(v == 0 for v in vals):
                oc = "silent_zero"
            else:
                oc = "wrong_value"
            res.update(outcome=oc, match=bool(match))
            return res
        return res


def emit(f, rec):
    f.write(json.dumps(rec, sort_keys=True, separators=(",", ":"),
                       default=str) + "\n")
    f.flush()
    os.fsync(f.fileno())


def env_report(run_dir, arms_path, run_id, args):
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
        "req_timeout_s": REQ_TIMEOUT,
        "confirm_attempts": CONFIRM_ATTEMPTS,
        "innocent_retries": INNOCENT_RETRIES,
        "canary_retries": CANARY_RETRIES,
        "limit_values": args.limit_values,
        "only": args.only,
        "concurrent_gpu_procs": sh(
            "bash", "-lc",
            "ps -Ao pid,comm | grep -E 'agxrun|rendersweep|gfrun|shdump' "
            "| grep -v grep | head -40"),
    }
    (run_dir / "env.json").write_text(json.dumps(rep, indent=1))
    return rep


def main():
    global REQ_TIMEOUT
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--arms", default=str(HERE / "harness" / "arms206.json"))
    ap.add_argument("--only", default="", help="comma-separated target keys")
    ap.add_argument("--carriers", default="", help="comma-separated carrier names")
    ap.add_argument("--limit-values", type=int, default=0,
                    help="PILOT ONLY: dispatch every Nth value")
    ap.add_argument("--req-timeout", type=float, default=REQ_TIMEOUT)
    args = ap.parse_args()
    REQ_TIMEOUT = args.req_timeout

    doc = json.loads(Path(args.arms).read_text())
    arms = doc["arms"]
    if args.only:
        keep = set(args.only.split(","))
        arms = [a for a in arms if a["key"] in keep]
    if args.carriers:
        keepc = set(args.carriers.split(","))
        arms = [a for a in arms if a["carrier"] in keepc]

    run_dir = HERE / "raw" / args.run_id
    if run_dir.exists():
        sys.stderr.write("REFUSING: run id %s already exists. Run ids are never "
                         "reused; a partial run is retained, never topped up.\n"
                         % args.run_id)
        return 2
    run_dir.mkdir(parents=True)
    env_report(run_dir, args.arms, args.run_id, args)
    sweep = open(run_dir / "sweep.jsonl", "a")

    by_carrier = {}
    for a in arms:
        by_carrier.setdefault(a["carrier"], []).append(a)

    ncase, t0 = 0, time.time()
    for carrier, carms in by_carrier.items():
        try:
            cr = CarrierRunner(carrier)
        except Exception as e:                                  # noqa: BLE001
            emit(sweep, {"carrier": carrier, "outcome": "carrier_start_failed",
                         "class": "fault", "note": str(e)[:400],
                         "ts": time.time()})
            continue
        emit(sweep, {"carrier": carrier, "outcome": "carrier_ready",
                     "role": "meta", "ts": time.time(),
                     "meta": {"device": cr.device,
                              "regions": {rn: {"abs": r["abs"], "len": r["len"],
                                               "sha16": cr.region_sha[rn]}
                                          for rn, r in cr.regions.items()},
                              "oracle_h": cr.oracle_h,
                              "oracle_vals": cr.spec["oracle"],
                              "archive_sha256":
                                  hashlib.sha256(cr.base).hexdigest()}})

        def baseline(tag):
            r = cr.measure(bytes(cr.base))
            emit(sweep, {"carrier": carrier, "arm": tag, "instr": "-",
                         "field": "_baseline", "value": -1, "bytes": "",
                         "token": None, "observed": r["observed"],
                         "vals": r["vals"],
                         "oracle": {"oh": cr.oracle_h, "expect_match": True},
                         "match": r["match"], "outcome": r["outcome"],
                         "class": HARD_CLASS.get(r["outcome"]),
                         "status": r["status"], "statuses": r["statuses"],
                         "fault_classes": r["fault_classes"],
                         "innocent_retries": r["innocent_retries"],
                         "gputime_ns": r["gputime_ns"],
                         "role": "baseline", "note": tag, "ts": time.time()})
            return r

        baseline("carrier_open")
        for a in carms:
            reg = a["region"]
            off, ilen = a["off"], a["len"]
            start, width = a["start"], a["width"]
            force = [tuple(x) for x in a.get("force", [])]
            vals = a["values"]
            if args.limit_values > 1:
                vals = vals[::args.limit_values]
            baseline(a["arm"] + ":open")
            # If the arm is a SYNTHESIZED descriptor (ret -> ret_luse), measure
            # the construction itself before sweeping it.
            if force:
                mm = cr.mutate(reg, off, ilen, force)
                r = cr.measure(cr.blob(reg, mm))
                emit(sweep, {"carrier": carrier, "arm": a["arm"],
                             "instr": a["instr"], "field": "_force_baseline",
                             "value": -1, "region": reg,
                             "bytes": mm[off:off + ilen].hex(),
                             "token": L.token_at(mm, off),
                             "observed": r["observed"], "vals": r["vals"],
                             "oracle": {"oh": cr.oracle_h, "expect_match": True},
                             "match": r["match"], "outcome": r["outcome"],
                             "class": HARD_CLASS.get(r["outcome"]),
                             "status": r["status"], "statuses": r["statuses"],
                             "fault_classes": r["fault_classes"],
                             "innocent_retries": r["innocent_retries"],
                             "gputime_ns": r["gputime_ns"],
                             "role": "force_baseline", "occ": a.get("occ"),
                             "off": off, "instr_len": ilen,
                             "note": a.get("force_note", ""), "ts": time.time()})
            expect = a.get("expect") or {}
            for n, v in enumerate(vals):
                mm = cr.mutate(reg, off, ilen, force + [(start, width, v)])
                r = cr.measure(cr.blob(reg, mm))
                em = expect.get(str(v), expect.get(v))
                rec = {
                    "carrier": carrier, "arm": a["arm"], "key": a["key"],
                    "region": reg, "synthesized": a.get("synthesized"),
                    "instr": a["instr"], "field": a["field"], "value": v,
                    "bytes": mm[off:off + ilen].hex(),
                    "token": L.token_at(mm, off),
                    "observed": r["observed"],
                    "oracle": {"oh": cr.oracle_h, "expect_match": em},
                    "match": r["match"],
                    "prediction_ok": (None if em is None else (bool(r["match"]) == bool(em))),
                    "outcome": r["outcome"],
                    "class": HARD_CLASS.get(r["outcome"]),
                    "status": r["status"], "statuses": r["statuses"],
                    "fault_classes": r["fault_classes"],
                    "innocent_retries": r["innocent_retries"],
                    "gputime_ns": r["gputime_ns"],
                    "role": a.get("role", "target"), "occ": a.get("occ"),
                    "occ_dim": a.get("occ_dim"),
                    "off": off, "instr_len": ilen,
                    "start": start, "width": width,
                    "note": a.get("note", ""), "ts": time.time(),
                }
                # Full value vector retained for every case that is NOT a clean
                # match, so a deviation is always fully reconstructible from raw.
                if not r["match"]:
                    rec["vals"] = r["vals"]
                emit(sweep, rec)
                ncase += 1
                if n and n % BASELINE_EVERY == 0:
                    baseline(a["arm"] + ":mid%d" % n)
            baseline(a["arm"] + ":close")
            print("[%6.1fs] %-12s %-40s %d values" %
                  (time.time() - t0, carrier, a["arm"], len(vals)), flush=True)
        cr.close()
        time.sleep(0.3)

    sweep.close()
    print("cases=%d elapsed=%.1fs -> %s" % (ncase, time.time() - t0, run_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
