#!/usr/bin/env python3
"""EXP-0202 AMENDMENT (v3) sweep driver -- the GATED CONFIRMATION runs.

  python3 run2.py --run-id <id> --arms harness/arms202b.json --order forward|reverse

`run.py` is NOT edited: run02 executed against its frozen hash and must stay
reproducible. This driver adds exactly what
`RE_EXPERIMENT_PROCESS_CORRECTIONS.md` requires and nothing else.

GATE A -- THE ACTUAL-BYTE LEDGER. Every case records, and the analysis ASSERTS
before any hardware conclusion:

    requested field value == value decoded from the ACTUAL dispatched bytes

Per case: `requested_value`, `requested_bytes` (built by the patcher),
`actual_bytes` (read back out of the final mutated `_agc.main` that goes into the
dispatched archive), `decoded_actual` (extracted by the PINNED TOKENIZER's own
field decoder -- a different code path from the patcher), `ledger_ok`,
`main_sha256` + `off`, and the db / arms / harness revisions. A symmetric
assemble-disassemble round trip is explicitly NOT this gate, and this ledger is
what would have caught DEF-0166 (an assembler that could not clear a requested
bit) on the first case.

GATE C -- A PREDICTED OUTCOME BUCKET per case (`harness/oracles202b.py`), scored
as `sem_checked` / `sem_match`. Liveness is no longer allowed to imply semantics.

GATE E -- `--order reverse` dispatches every arm's values in reversed order, so
the confirmation pair differs in case order and an order-dependent artefact
cannot pass as agreement. A MALFORMED response stays `measurement_failure` and is
never a hardware outcome.

CLEAN-ROOM: OWN-SHADER + HW-PROBE. Every byte dispatched is the compiled form of
our own MSL in `kernels/`, mutated in exactly one field.
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
import carriers202b              # noqa: E402,F401  (adds the v3 carriers)
import locate202 as L            # noqa: E402
import oracles202b as O          # noqa: E402
import saferunner202 as SR       # noqa: E402

PINNED = L.PINNED
SafeRunner = SR.make_classes(str(PINNED))

REQ_TIMEOUT = 8.0
CONFIRM_ATTEMPTS = 3
INNOCENT_RETRIES = 3
CANARY_RETRIES = 3
BASELINE_EVERY = 256
REV = {}
BIN = HERE / "work" / "bin"
WORK = HERE / "work"


def decode_field(raw_bytes, mnemonic, field, start, width):
    """Decode the field from the ACTUAL bytes by a DIFFERENT code path than the
    patcher: the pinned tokenizer's own field extraction. Falls back to a
    byte-wise (not int-wide) bit assembly, which is still a different
    implementation from `patch_instr`'s single big-integer mask."""
    try:
        rec, _ = L.isadb.decode_one(bytes(raw_bytes), 0)
        if rec.get("mnemonic") == mnemonic and field in (rec.get("fields") or {}):
            return rec["fields"][field], "pinned_tokenizer"
    except Exception:                                           # noqa: BLE001
        pass
    v = 0
    for i in range(width):
        bit = start + i
        v |= ((raw_bytes[bit // 8] >> (bit % 8)) & 1) << i
    return v, "bytewise"


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

    def patched_main(self, patches):
        """Apply an ordered list of {off,len,start,width,value} patches.

        A PREPATCH is how an arm reaches an encoding the compiler never emits.
        EXP-0139 established that no `iunary`-tokenizing instruction exists in 30
        authored MSL kernels (our own census of 50 more agrees), so its fields can
        only be reached by SYNTHESIS: rewrite an 8-byte `ibitcount` occurrence's
        byte+1/byte+2 into the `27 2d 22` form that tokenizes as `iunary` and
        still computes, then sweep the field on THAT. The arm's own baseline is
        dispatched WITH the prepatch and WITHOUT the field mutation, so an arm
        whose synthesized base does not reproduce the carrier's host oracle has no
        detection power and is barred by the gate.
        """
        m = bytearray(self.main)
        for p in patches:
            if p.get("off") is None:
                continue
            o, ln = p["off"], p["len"]
            m[o:o + ln] = self.patch_instr(bytes(m[o:o + ln]), p["start"],
                                           p["width"], p["value"])
        return bytes(m)

    def requested_instr_bytes(self, patches, off, ilen):
        """The instruction bytes the CALLER asked for, built independently of the
        blob assembly: start from the compiled bytes and apply the same ordered
        patch list to that 8/10/12-byte window alone."""
        w = bytearray(self.main[off:off + ilen])
        for p in patches:
            if p.get("off") is None:
                continue
            if p["off"] != off:
                continue
            w[0:ilen] = self.patch_instr(bytes(w), p["start"], p["width"],
                                         p["value"])
        return bytes(w)

    def blob_from_main(self, m):
        b = bytearray(self.base)
        b[self.main_off:self.main_off + len(m)] = m
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
        "order": REV.get("order"),
        "rev": REV,
        "concurrent_gpu_procs": sh("bash", "-lc",
                                   "ps -Ao pid,comm | grep -E 'agxrun|rendersweep|gfrun|shdump' "
                                   "| grep -v grep | head -40"),
    }
    (run_dir / "env.json").write_text(json.dumps(rep, indent=1))
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--arms", default=str(HERE / "harness" / "arms202b.json"))
    ap.add_argument("--only", default="")
    ap.add_argument("--limit-values", type=int, default=0)
    ap.add_argument("--order", choices=("forward", "reverse"), default="forward",
                    help="Gate E: the confirmation pair must differ in case order")
    args = ap.parse_args()

    global REV
    REV = {"db": hashlib.sha256((PINNED / "db.json").read_bytes()).hexdigest()[:12],
           "arms": hashlib.sha256(Path(args.arms).read_bytes()).hexdigest()[:12],
           "harness": hashlib.sha256(
               (HERE / "harness" / "oracles202b.py").read_bytes()).hexdigest()[:12],
           "driver": hashlib.sha256((HERE / "run2.py").read_bytes()).hexdigest()[:12],
           "order": args.order}
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

        def baseline(tag, prepatch=()):
            ora = {"class": "exact", "rule": "baseline", "vals": cr.spec["oracle"]}
            mm = cr.patched_main(list(prepatch))
            oc, obs, m, st, sts, cls, inn = cr.measure(
                cr.blob_from_main(mm), ora, cr.spec["oracle"])
            emit(sweep, {"carrier": carrier, "arm": tag, "instr": "-",
                         "field": "_baseline", "value": -1,
                         "bytes": "", "token": None,
                         "observed": obs, "oracle": ora,
                         "match": m, "outcome": oc, "status": st,
                         "statuses": sts, "fault_classes": cls,
                         "innocent_retries": inn, "role": "baseline",
                         "grid": cr.spec["grid"], "tg": cr.spec["tg"],
                         "prepatch": list(prepatch),
                         "note": tag, "ts": time.time()})
            return oc

        baseline("carrier_open")
        for a in carms:
            off, ilen = a["off"], a["len"]
            start, width = a["start"], a["width"]
            vals = a["values"]
            if args.limit_values > 1:
                vals = vals[::args.limit_values]
            if args.order == "reverse":
                vals = list(reversed(vals))
            budget = int(a.get("hang_budget", 0))
            hangs = 0
            pre = a.get("prepatch", [])
            baseline(a["arm"] + ":open", pre)
            for n, v in enumerate(vals):
                ora, expect = O.predict(a, carrier, v)
                patches = list(pre) + [
                    {"off": off, "len": ilen, "start": start, "width": width,
                     "value": v}]
                mm = cr.patched_main(patches)
                blob = cr.blob_from_main(mm)
                tok = L.token_at(mm, off)
                actual = mm[off:off + ilen]
                requested = cr.requested_instr_bytes(patches, off, ilen)
                dec, dec_via = decode_field(actual, a["instr"], a["field"],
                                            start, width)
                oc, obs, m, st, sts, cls, inn = cr.measure(blob, ora, expect)
                sem_checked, sem_match = O.sem_check(ora, oc)
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
                    "prepatch": pre, "sub": a.get("sub"),
                    "note": a.get("note", ""), "ts": time.time(),
                    # ---- Gate A: the actual-byte ledger --------------------
                    "requested_value": v,
                    "requested_bytes": requested.hex(),
                    "actual_bytes": actual.hex(),
                    "decoded_actual": dec,
                    "decoded_via": dec_via,
                    "ledger_ok": bool(requested == actual
                                      and (dec == (v & ((1 << width) - 1)))),
                    "main_sha256": hashlib.sha256(mm).hexdigest(),
                    "rev": REV,
                    "case_order": ncase,
                    # ---- Gate C: the semantic check ------------------------
                    "predicted_bucket": (ora or {}).get("predicted_bucket"),
                    "sem_checked": sem_checked,
                    "sem_match": sem_match,
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
                    baseline(a["arm"] + ":mid%d" % n, pre)
            baseline(a["arm"] + ":close", pre)
            print("[%6.1fs] %-10s %-34s %d values" %
                  (time.time() - t0, carrier, a["arm"], len(vals)), flush=True)
        cr.close()
        time.sleep(0.2)

    sweep.close()
    print("cases=%d elapsed=%.1fs -> %s" % (ncase, time.time() - t0, run_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
