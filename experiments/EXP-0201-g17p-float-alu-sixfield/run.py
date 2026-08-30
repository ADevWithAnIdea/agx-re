#!/usr/bin/env python3
"""EXP-0201 sweep driver (runs ON THE NEO, under ~/agxre/EXP-0201).

  python3 run.py --run-id g17p_YYYYMMDD_runNN [--only falu3,copysign] [--quiet-watch]

One JSON object per case is appended to `raw/<run_id>/sweep.jsonl` and
flush+fsync'd immediately -- never buffered to write at the end.

FROZEN BEHAVIOURS (PRE_REGISTRATION.md sections 6-8):

* **NO ABORT PATH, no hang budget** (protocol 3c): a budget cannot characterise a
  contiguous hazard, it guarantees the region is never mapped. Every value is
  dispatched in every gated run.
* **A malformed response is a MEASUREMENT FAILURE, never a hang** (3d).
* **Poisoned read-back + integrity sentinel + OS fault string** on every case.
* **`observed` is DETERMINISTIC ONLY.** `gputime_ns` and retry counts live at the
  TOP LEVEL of the record. An indexer that hashes the whole `observed` dict to
  compare runs otherwise measures a nanosecond timer -- which alone drove one
  field's apparent cross-run agreement from 100 % to 39 % and got it withheld.
* **The pinned tokenizer's opinion of the MUTATED bytes is recorded per case**,
  so movement that is really a different instruction is visible in the raw.
* **A per-value host-computed prediction** (`harness/models201.py`) and the NAME
  of the library member the hardware actually produced (`observed_fn`).
* **Never conclude `fault` from one observation**: majority-of-3, victims retried.

CLEAN-ROOM: OWN-SHADER + HW-PROBE. Every byte dispatched is the compiled form of
our own MSL in `kernels/`, mutated in exactly one field's own bit span.
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

import carriers201 as C          # noqa: E402
import locate201 as L            # noqa: E402
import models201 as M            # noqa: E402
import saferunner201 as SR       # noqa: E402

PINNED = L.PINNED
SafeRunner, _ = SR.make_classes(str(PINNED))

REQ_TIMEOUT = 8.0
CONFIRM_ATTEMPTS = 3
INNOCENT_RETRIES = 3
CANARY_RETRIES = 3
BASELINE_EVERY = 200
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
        self.main_sha = hashlib.sha256(main).hexdigest()
        self.runner = SafeRunner(
            source=str(HERE / self.spec["metal"]), function=self.spec["func"],
            fast_math=False, agxrun_persist=str(BIN / "agxrun_persist"))
        self.base = Path(arch).read_bytes()
        self.device = self.runner.device

    def close(self):
        try:
            self.runner.close()
        except Exception:                                       # noqa: BLE001
            pass

    @staticmethod
    def patch_instr(raw, start, width, value):
        """Replace bits [start, start+width) of ONE instruction, little-endian
        over its own byte string -- the same convention `isadb._get_bits` decodes
        with. No assembler is involved, so a value written to a `match`-pinned
        bit really lands: that is what makes values 4 and 6 of a 3-bit field
        straddling a pinned bit produce DIFFERENT bytes here."""
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

    def measure(self, blob, expect):
        """-> dict with the deterministic `observed` payload and the outcome.

        `expect` is the host-computed vector this case is predicted to produce,
        or None when the model makes no vector prediction."""
        for _ in range(CANARY_RETRIES):
            resp, statuses, classes, innocent, nbad = self.issue(blob)
            base = {"statuses": statuses, "fault_classes": classes,
                    "innocent_retries": innocent,
                    "gputime_ns": resp.get("gputime_ns")}
            if resp["status"] == "HANG":
                return dict(base, outcome="hang", observed={"status": "HANG"},
                            match=False, observed_fn=None, status="HANG")
            if resp["status"] == "MALFORMED":
                return dict(base, outcome="measurement_failure",
                            observed={"status": "MALFORMED"},
                            raw_lines=resp.get("raw"), match=False,
                            observed_fn=None, status="MALFORMED")
            out = resp["outs"].get(0, b"")
            if not out:
                return dict(base,
                            outcome="fault" if nbad >= 2 else "nondeterministic",
                            observed={"status": resp["status"]}, match=False,
                            observed_fn=None, status=resp["status"])
            obs, words, vals = C.summarize(self.name, out)
            obs["status"] = resp["status"]
            obs["sentinel_ok"] = C.sentinel_ok(self.name, words)
            obs["tail_ok"] = C.tail_ok(self.name, words)
            obs["unwritten"] = C.unwritten(self.name, words)
            if resp["status"] != "OK":
                return dict(base,
                            outcome="fault" if nbad >= 2 else "nondeterministic",
                            observed=obs, match=False, observed_fn=None,
                            status=resp["status"])
            # OK + wrote nothing = invalid run, not a silent zero (EXP-0160 saw
            # 25 such dispatches with no victim string anywhere).
            if not obs["sentinel_ok"]:
                time.sleep(0.05)
                continue
            fn = C.classify(self.name, vals)
            m = bool(expect is not None and C.vec_match(self.name, vals, expect))
            if m:
                oc = "ok"
            elif len(obs["unwritten"]) == len(self.spec["val_words"]):
                oc = "not_written"
            elif all(v == 0 for v in obs["vals_u32"]):
                oc = "silent_zero"
            else:
                oc = "wrong_value"
            return dict(base, outcome=oc, observed=obs, match=m,
                        observed_fn=fn, status=resp["status"])
        return dict(base, outcome="invalid_run", observed=obs, match=False,
                    observed_fn=None, status=resp.get("status"))


def emit(f, rec):
    f.write(json.dumps(rec, sort_keys=True, separators=(",", ":"), default=str) + "\n")
    f.flush()
    os.fsync(f.fileno())


def sh(*c):
    try:
        return subprocess.check_output(c, text=True, timeout=30).strip()
    except Exception as e:                                      # noqa: BLE001
        return "ERR %s" % e


def env_report(run_dir, arms_path, run_id):
    rep = {
        "run_id": run_id,
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "host": sh("hostname"), "os": sh("sw_vers", "-productVersion"),
        "build": sh("sw_vers", "-buildVersion"),
        "model": sh("sysctl", "-n", "hw.model"),
        "python": sys.version.split()[0],
        "pinned_db_sha256": hashlib.sha256((PINNED / "db.json").read_bytes()).hexdigest(),
        "pinned_isadb_sha256": hashlib.sha256((PINNED / "isadb.py").read_bytes()).hexdigest(),
        "arms_sha256": hashlib.sha256(Path(arms_path).read_bytes()).hexdigest(),
        "concurrent_gpu_procs": sh("bash", "-lc",
                                   "ps -Ao pid,comm | grep -E 'agxrun|rendersweep|gfrun|shdump'"
                                   " | grep -v grep | head -40"),
    }
    (run_dir / "env.json").write_text(json.dumps(rep, indent=1))
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--arms", default=str(HERE / "harness" / "arms201.json"))
    ap.add_argument("--only", default="")
    ap.add_argument("--carriers", default="")
    ap.add_argument("--limit-values", type=int, default=0)
    args = ap.parse_args()

    arms = json.loads(Path(args.arms).read_text())["arms"]
    if args.only:
        keep = set(args.only.split(","))
        arms = [a for a in arms if a["group"] in keep]
    if args.carriers:
        keep = set(args.carriers.split(","))
        arms = [a for a in arms if a["carrier"] in keep]
    run_dir = HERE / "raw" / args.run_id
    if run_dir.exists():
        sys.stderr.write("REFUSING: run id %s exists. Run ids are never reused; "
                         "a partial run is retained, never topped up.\n" % args.run_id)
        return 2
    run_dir.mkdir(parents=True)
    env_report(run_dir, args.arms, args.run_id)
    sweep = open(run_dir / "sweep.jsonl", "a")

    by_carrier = {}
    for a in arms:
        by_carrier.setdefault(a["carrier"], []).append(a)

    ncase, t0 = 0, time.time()
    for carrier, carms in by_carrier.items():
        spec = C.CARRIERS[carrier]
        try:
            cr = CarrierRunner(carrier)
        except Exception as e:                                  # noqa: BLE001
            emit(sweep, {"carrier": carrier, "outcome": "carrier_start_failed",
                         "note": str(e)[:400], "ts": time.time()})
            continue
        emit(sweep, {"carrier": carrier, "outcome": "carrier_ready",
                     "ts": time.time(),
                     "note": json.dumps({"device": cr.device,
                                         "main_len": len(cr.main),
                                         "main_sha256": cr.main_sha,
                                         "main_off": cr.main_off,
                                         "func": spec["func"]})})

        def baseline(tag):
            r = cr.measure(cr.blob(None, 0, 0, 0, 0), spec["oracle"])
            emit(sweep, dict(r, carrier=carrier, arm=tag, instr="-",
                             field="_baseline", value=-1, bytes="", token=None,
                             oracle={"predicted_fn": "carrier_correct",
                                     "vals": spec["oracle"], "equiv": -1},
                             role="baseline", note=tag, ts=time.time()))
            return r

        baseline("carrier_open")
        for a in carms:
            off, ilen, start, width = a["off"], a["len"], a["start"], a["width"]
            bb = int.from_bytes(bytes.fromhex(a["baseline_bytes"]), "little")
            baseline_value = (bb >> start) & ((1 << width) - 1)
            vals = a["values"]
            if args.limit_values > 1:
                vals = vals[::args.limit_values]
            baseline(a["arm"] + ":open")
            for n, v in enumerate(vals):
                pred = M.predict(a["instr"], a["field"], v, spec,
                                 baseline_value, spec["library"])
                # On an identity-routed carrier the tested instruction's result
                # IS the read-back, so the model's per-value vector is directly
                # testable. On a chained carrier the result is post-processed, so
                # the only vector the host can predict is the carrier's own
                # correct output, and only for the compiled encoding.
                if spec["identity_post"]:
                    expect = pred["vals"]
                else:
                    expect = spec["oracle"] if v == baseline_value else None
                blob = cr.blob(off, ilen, start, width, v)
                mm = cr.mutated_main(off, ilen, start, width, v)
                tok = L.token_at(mm, off)
                r = cr.measure(blob, expect)
                emit(sweep, dict(
                    r, carrier=carrier, arm=a["arm"], instr=a["instr"],
                    field=a["field"], control_field=a.get("control_field"),
                    value=v, bytes=mm[off:off + ilen].hex(), token=tok,
                    oracle={"predicted_fn": pred["predicted_fn"],
                            "vals": expect, "equiv": pred["equiv"],
                            "predicted_token": pred["predicted_token"]},
                    role=a.get("role", "target"), occ=a.get("occ"),
                    off=off, instr_len=ilen, start=start, width=width,
                    baseline_value=baseline_value,
                    note=a.get("note", ""), ts=time.time()))
                ncase += 1
                if n and n % BASELINE_EVERY == 0:
                    baseline(a["arm"] + ":mid%d" % n)
            baseline(a["arm"] + ":close")
            print("[%6.1fs] %-10s %-34s %d values" %
                  (time.time() - t0, carrier, a["arm"], len(vals)), flush=True)
        cr.close()
        time.sleep(0.3)

    sweep.close()
    print("cases=%d elapsed=%.1fs -> %s" % (ncase, time.time() - t0, run_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
