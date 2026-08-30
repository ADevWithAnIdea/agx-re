#!/usr/bin/env python3
"""EXP-0152 capture driver.

One `agxrun_persist` process per CARRIER SOURCE (cfN and cf0 are the same
compiled kernel with a different `n` input buffer, so they share one runner and
one library).  Every case appends ONE JSON object to raw/<run_id>/sweep.jsonl
with flush+fsync immediately, so a kill or a wedge costs at most the case in
flight (SUBAGENT_BRIEF.md).

CONTAMINATION DEFENCES (FIELD-SWEEP-PROTOCOL.md S7, all pre-registered):
  D1 unique splice-archive path per request, unlinked afterwards.
  D2 pre-poisoned read-back buffer everywhere + an integrity sentinel on every
     carrier that has room for one (the CF carrier's `_agc.main` is exactly 152
     bytes and the frozen skeleton fills it exactly -- EXP-0140 S9 proved that
     lengthening it changes its semantics -- so there the poison test alone is
     the integrity check; declared in PRE_REGISTRATION.md S7.4).
  D3 majority-of-3 replication; a fault/hang label needs the majority; the OS
     fault-classification string is recorded verbatim; `InnocentVictim` is
     segregated as environmental and retried.
  D4 periodic baseline re-validation; two consecutive failures => restart, then
     abort rather than record a cascade.

SAFETY (FIELD-SWEEP-PROTOCOL.md S8): 2 hangs stop that arm, 4 stop every
remaining CF arm, 8 abort the run.  Aborted cases are recorded as `skipped`.

Usage: run.py --run RUN_ID [--only PREFIX] [--limit N]
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
for p in ("tools/agx-isa", "tools/shdump", "tools/agxtest"):
    sys.path.insert(0, str(REPO / p))
sys.path.insert(0, str(HERE))
import isadb        # noqa: E402
from persistrun import PersistRunner  # noqa: E402
import cases as CS  # noqa: E402
import carriers as C   # noqa: E402
import isa_helpers as H  # noqa: E402
import baseline as B   # noqa: E402

REQ_TIMEOUT = 8.0
ARM_HANG_BUDGET = 2


def sha(b):
    return hashlib.sha256(b).hexdigest()


def words(raw, n):
    return [struct.unpack_from("<I", raw, 4 * i)[0] if 4 * i + 4 <= len(raw) else None
            for i in range(n)]


def read_out(outs_raw, key):
    b, i = key.split(":")
    raw = outs_raw.get(int(b), b"")
    o = 4 * int(i)
    return struct.unpack_from("<I", raw, o)[0] if o + 4 <= len(raw) else None


def classify(case, status, outs_raw, err):
    """(observed, match, outcome, valid).  All comparisons are done on the raw
    u32 word, and the oracle is stored as a raw u32 too (IEEE bits for float
    carriers), so no signed/unsigned mismatch is possible -- the exact harness
    bug EXP-0140 found after its captures."""
    if status == "HANG":
        return {}, None, "hang", True
    if status != "OK":
        victim = "InnocentVictim" in (err or "")
        return {}, None, ("invalid_run" if victim else "fault"), (not victim)
    keys = sorted(case["oracle"])
    observed = {k: read_out(outs_raw, k) for k in keys}
    if any(observed[k] is None for k in keys):
        return observed, False, "invalid_run", False
    if case["sentinel"]:
        skey, sval = case["sentinel"]
        got = read_out(outs_raw, skey)
        valid = (got == sval)
    else:
        # CF carrier: buffer 0 was pre-filled with POISON_WORD(i); if every
        # oracle word is still its poison fill nothing was written.
        valid = any(observed[k] != C.poison_word(int(k.split(":")[1]))
                    for k in keys if k.startswith("0:"))
    match = all(observed[k] == (case["oracle"][k] & 0xFFFFFFFF) for k in keys)
    if not valid:
        return observed, match, "invalid_run", False
    if match:
        return observed, match, "ok", True
    prim = observed[keys[0]]
    return observed, match, ("silent_zero" if prim == 0 else "wrong_value"), True


def make_inputs(work):
    work.mkdir(parents=True, exist_ok=True)
    paths = {}
    for k, fn in C.INPUT_FILES.items():
        p = work / (k + ".bin")
        p.write_bytes(fn())
        paths[k] = str(p)
    return paths


def splice(case, buf, roff, mainlen):
    b = bytearray(buf)
    if "prog" in case:
        prog = case["prog"]
        assert len(prog) == mainlen, (len(prog), mainlen)
        b[roff:roff + mainlen] = prog
    elif "patch" in case:
        for off, blob in case["patch"]:
            b[roff + off:roff + off + len(blob)] = blob
    else:
        raise ValueError("case has no splice directive")
    return bytes(b)


def roundtrip_note(spliced, roff, mainlen):
    """Does OUR OWN decoder still tokenize the spliced region cleanly?  Recorded
    as db-defect evidence; NEVER used to skip a case -- the hardware does not
    consult our decoder, and EXP-0148 showed tokenization is NON-LOCAL."""
    main = bytes(spliced[roff:roff + mainlen])
    try:
        recs, leftover = isadb.disassemble(main)
        if leftover:
            return "leftover:%d" % len(leftover)
        for r in recs:
            if r.get("mnemonic") == "<unknown>":
                return "unknown"
        return "clean"
    except Exception as e:                       # pragma: no cover
        return "error:%s" % type(e).__name__


class Bench:
    def __init__(self, bin_dir, spdir, timeout):
        self.bin_dir = Path(bin_dir)
        self.spdir = Path(spdir)
        self.spdir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.runner = None
        self.src = None
        self.seq = 0

    def use(self, src):
        if src != self.src:
            self.close()
            last = None
            for attempt in range(6):
                try:
                    self.runner = PersistRunner(
                        source=str(EXP / "kernels" / src), function="k",
                        fast_math=False,
                        agxrun_persist=str(self.bin_dir / "agxrun_persist"))
                    self.src = src
                    return
                except Exception as e:                        # noqa: BLE001
                    last = e
                    print("runner start failed (%d/6): %s" % (attempt + 1, e),
                          flush=True)
                    time.sleep(5 * (attempt + 1))
            raise RuntimeError("agxrun_persist would not start: %s" % last)

    def restart(self):
        s = self.src
        self.close()
        self.src = None
        self.use(s)

    def close(self):
        if self.runner:
            try:
                self.runner.close()
            except Exception:
                pass
        self.runner = None

    def submit(self, spliced, grid, tg, ins, outs):
        self.seq += 1
        pth = self.spdir / ("sp_%08d.bin" % self.seq)
        pth.write_bytes(spliced)
        try:
            return self.runner.request(archive=str(pth), grid=grid, tg=tg,
                                       ins=ins, outs=outs, timeout=self.timeout)
        finally:
            try:
                pth.unlink()
            except OSError:
                pass

    def attempt(self, spliced, grid, tg, ins, outs):
        att, errs = 0, []
        while True:
            att += 1
            rp = self.submit(spliced, grid, tg, ins, outs)
            errs.append(rp.get("error"))
            if rp["status"] == "OK" or att >= 4:
                return rp, att, errs
            if "InnocentVictim" not in (rp.get("error") or ""):
                return rp, att, errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--only", default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--timeout", type=float, default=REQ_TIMEOUT)
    ap.add_argument("--cf-hang-budget", type=int, default=4)
    ap.add_argument("--global-hang-budget", type=int, default=8)
    ap.add_argument("--baseline-every", type=int, default=250)
    a = ap.parse_args()

    run_dir = EXP / "raw" / a.run
    if run_dir.exists():
        sys.exit("run id %s already exists -- never reuse or overwrite a run id"
                 % a.run)
    run_dir.mkdir(parents=True)
    work = EXP / "work" / ("run_" + a.run)
    bin_dir = EXP / "work" / "bin"

    facts = B.derive(str(bin_dir), str(work / "baseline_bin"))
    cs = CS.build_cases(facts)
    if a.only:
        cs = [c for c in cs if c["arm"].startswith(a.only)]
    if a.limit:
        cs = cs[:a.limit]
    paths = make_inputs(work)

    arch = {}
    for name, spec in C.CARRIERS.items():
        src = spec["metal"]
        if src in arch:
            continue
        buf, roff, main = B.compile_carrier(bin_dir, EXP / "kernels" / src,
                                            work / (src + ".bin"))
        arch[src] = (buf, roff, len(main))

    def ins_for(carrier):
        return {i: paths[k] for i, k in C.CARRIERS[carrier]["ins"].items()}

    # unmutated reference per carrier for D4
    ml = facts["carriers"]["cfN"]["main_len"]
    ref = {}
    for car in C.CARRIERS:
        if car in ("cfN", "cf0"):
            nvec = C.CF_N_MIXED if car == "cfN" else C.CF_N_ZERO
            ref[car] = dict(carrier=car,
                            prog=H.cf_program_x(carrier_len=ml),
                            oracle=C.cf_oracle_words(nvec, H.cf_oracle))
        else:
            m, off, ln, orig = facts["sites"][car]
            orc = {"atdev": C.atdev_oracle, "atdevimm": C.atdevimm_oracle,
                   "attg": C.attg_oracle}[car]()
            ref[car] = dict(carrier=car, patch=[(off, bytes([orig[0]]))],
                            oracle=orc)
        spec = C.CARRIERS[car]
        ref[car].update(dispatch=(spec["grid"], spec["tg"]), mode=spec["mode"],
                        sentinel=spec["sentinel"], outs=dict(spec["outs"]),
                        note="baseline", expect_match=True)

    inputs_rec = {
        "run": a.run, "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "target": "local Apple M4 / G16G", "n_cases": len(cs),
        "n_dispatched": sum(1 for c in cs if "skip" not in c),
        "carriers": {k: {kk: vv for kk, vv in v.items() if kk != "tokens"}
                     for k, v in facts["carriers"].items()},
        "carrier_tokens": {k: v["tokens"] for k, v in facts["carriers"].items()},
        "sites": {k: [v[0], v[1], v[2], v[3].hex()]
                  for k, v in facts["sites"].items()},
        "cf_starts": facts["cf_starts"],
        "inputs": {"cf_a": C.CF_A, "cf_n_mixed": C.CF_N_MIXED,
                   "cf_n_zero": C.CF_N_ZERO, "atom_a": C.ATOM_A[:8],
                   "poison_base": "0x%08x" % C.POISON_BASE, "sentinel": C.SENT},
        "poison_offsets": {"P1": CS.P1, "P2": CS.P2, "natural": CS.JC_NATURAL},
        "excluded_known_hangs": {"%s.%s" % k: sorted(v[0])
                                 for k, v in CS.EXCLUDE.items()},
        "timeouts": {"per_request_s": a.timeout},
        "defences": {"unique_archive_path_per_request": True,
                     "poisoned_output_buffer": True,
                     "integrity_sentinel": [k for k, v in C.CARRIERS.items()
                                            if v["sentinel"]],
                     "replication_trials_min": 2, "replication_trials_max": 3,
                     "innocent_victim_retries": 4,
                     "baseline_every": a.baseline_every},
        "hang_budgets": {"per_arm": ARM_HANG_BUDGET, "cf_total": a.cf_hang_budget,
                         "global": a.global_hang_budget},
        "tool_sha256": {
            "isadb.py": sha((REPO / "tools/agx-isa/isadb.py").read_bytes()),
            "db.json": sha((REPO / "tools/agx-isa/db.json").read_bytes()),
            "agxrun_persist.m": sha((REPO / "tools/agxtest/agxrun_persist.m").read_bytes()),
            "persistrun.py": sha((REPO / "tools/agxtest/persistrun.py").read_bytes()),
            "shdump.m": sha((REPO / "tools/shdump/shdump.m").read_bytes()),
        },
        "harness_sha256": {p.name: sha(p.read_bytes())
                           for p in sorted((EXP / "harness").glob("*.py"))},
        "kernel_sha256": {p.name: sha(p.read_bytes())
                          for p in sorted((EXP / "kernels").glob("*.metal"))},
        "prereg_sha256": sha((EXP / "PRE_REGISTRATION.md").read_bytes()),
        "git_rev": subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(REPO),
                                  capture_output=True, text=True).stdout.strip(),
        "git_dirty": bool(subprocess.run(["git", "status", "--porcelain"],
                                         cwd=str(REPO), capture_output=True,
                                         text=True).stdout.strip()),
        "concurrent_gpu_procs": subprocess.run(
            ["bash", "-c", "ps ax | grep -c '[a]gxrun_persist\\|[a]gxrender'"],
            capture_output=True, text=True).stdout.strip(),
    }
    (run_dir / "00_inputs.json").write_text(json.dumps(inputs_rec, indent=1,
                                                       sort_keys=True))

    fh = open(run_dir / "sweep.jsonl", "a")
    bench = Bench(bin_dir, work / "spliced", a.timeout)
    arm_hangs, cf_hangs, total_hangs = {}, 0, 0
    dead_arms, cf_dead = set(), False
    invalid_runs, bl_fail_streak, aborted = 0, 0, None
    t0 = time.time()

    def emit(rec):
        fh.write(json.dumps(rec, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())

    def measure(case):
        src = C.CARRIERS[case["carrier"]]["metal"]
        buf, roff, mainlen = arch[src]
        spliced = splice(case, buf, roff, mainlen)
        rt = roundtrip_note(spliced, roff, mainlen)
        grid, tg = case["dispatch"]
        ins = ins_for(case["carrier"])
        trials = []
        for t in range(3):
            rp, att, errs = bench.attempt(spliced, grid, tg, ins, case["outs"])
            o, m, oc, ok = classify(case, rp["status"], rp["outs"], rp.get("error"))
            trials.append({"resp": rp, "attempts": att, "errors": errs,
                           "observed": o, "match": m, "outcome": oc, "valid": ok})
            if t == 0 and oc == "ok":
                continue
            if t == 1:
                k0 = (trials[0]["outcome"], json.dumps(trials[0]["observed"], sort_keys=True))
                k1 = (trials[1]["outcome"], json.dumps(trials[1]["observed"], sort_keys=True))
                if k0 == k1 and trials[0]["outcome"] == "ok":
                    break
        keys = [(t["outcome"], json.dumps(t["observed"], sort_keys=True)) for t in trials]
        winner = max(set(keys), key=keys.count)
        pick = trials[keys.index(winner)]
        return trials, pick, len(set(keys)) > 1, rt, spliced, roff, mainlen

    try:
        for n, c in enumerate(cs):
            arm = c["arm"]
            is_cf = c["carrier"] in ("cfN", "cf0")
            skip = c.get("skip")
            if not skip:
                if aborted:
                    skip = aborted
                elif arm in dead_arms:
                    skip = "arm_stopped_after_%d_hangs" % ARM_HANG_BUDGET
                elif is_cf and cf_dead:
                    skip = "cf_arms_stopped_after_%d_hangs" % a.cf_hang_budget
                elif total_hangs >= a.global_hang_budget:
                    skip = "run_stopped_after_%d_hangs" % a.global_hang_budget
            if skip:
                emit({"kind": "case", "instr": c["instr"], "field": c["field"],
                      "value": c["value"], "bytes": c["bytes"], "observed": {},
                      "oracle": {}, "match": None, "outcome": "skipped",
                      "carrier": c["carrier"], "note": c["note"], "i": c["i"],
                      "group": c["group"], "arm": arm, "skip_reason": skip,
                      "expect_match": c["expect_match"], "status": "SKIPPED"})
                continue

            bench.use(C.CARRIERS[c["carrier"]]["metal"])

            if a.baseline_every and n % a.baseline_every == 0:
                r = ref[c["carrier"]]
                bt, bp, bu, _, _, _, _ = measure(r)
                emit({"kind": "baseline_check", "at_case": n,
                      "carrier": c["carrier"], "outcome": bp["outcome"],
                      "match": bp["match"], "observed": bp["observed"],
                      "oracle": r["oracle"], "unstable": bu,
                      "statuses": [t["resp"]["status"] for t in bt],
                      "errors": [t["errors"] for t in bt],
                      "elapsed_s": round(time.time() - t0, 1)})
                if bp["outcome"] != "ok":
                    bl_fail_streak += 1
                    print("BASELINE FAIL #%d at case %d (%s)"
                          % (bl_fail_streak, n, bp["outcome"]), flush=True)
                    bench.restart()
                    bt2, bp2, _, _, _, _, _ = measure(r)
                    emit({"kind": "baseline_check", "at_case": n,
                          "carrier": c["carrier"], "outcome": bp2["outcome"],
                          "match": bp2["match"], "observed": bp2["observed"],
                          "oracle": r["oracle"], "note": "after runner restart",
                          "statuses": [t["resp"]["status"] for t in bt2],
                          "errors": [t["errors"] for t in bt2],
                          "elapsed_s": round(time.time() - t0, 1)})
                    if bp2["outcome"] != "ok":
                        aborted = "aborted_baseline_cascade_at_case_%d" % n
                        print("  -> ABORTING: baseline still failing", flush=True)
                        continue
                else:
                    bl_fail_streak = 0

            trials, pick, unstable, rt, spliced, roff, mainlen = measure(c)
            outcome = pick["outcome"]
            if outcome == "invalid_run":
                invalid_runs += 1

            emit({"kind": "case", "instr": c["instr"], "field": c["field"],
                  "value": c["value"], "bytes": c["bytes"],
                  "observed": pick["observed"], "oracle": c["oracle"],
                  "match": pick["match"], "outcome": outcome,
                  "carrier": c["carrier"], "note": c["note"], "i": c["i"],
                  "group": c["group"], "arm": arm,
                  "expect_match": c["expect_match"],
                  "status": pick["resp"]["status"], "mode": c["mode"],
                  "dispatch": list(c["dispatch"]), "rt": rt,
                  "attempts": pick["attempts"],
                  "fault_class": pick["resp"].get("error"),
                  "trial_statuses": [t["resp"]["status"] for t in trials],
                  "trial_outcomes": [t["outcome"] for t in trials],
                  "trial_errors": [t["errors"] for t in trials],
                  "replicates": len(trials), "unstable": unstable,
                  "sentinel_ok": pick["valid"],
                  "prog_sha256": sha(spliced[roff:roff + mainlen]),
                  "restarted": any(t["resp"].get("restarted") for t in trials)})

            if outcome == "hang":
                total_hangs += 1
                arm_hangs[arm] = arm_hangs.get(arm, 0) + 1
                if is_cf:
                    cf_hangs += 1
                print("HANG #%d arm=%s value=%s" % (total_hangs, arm, c["value"]),
                      flush=True)
                if arm_hangs[arm] >= ARM_HANG_BUDGET:
                    dead_arms.add(arm)
                    print("  -> STOPPING arm %s" % arm, flush=True)
                if is_cf and cf_hangs >= a.cf_hang_budget:
                    cf_dead = True
                    print("  -> STOPPING all CF arms (%d hangs)" % cf_hangs,
                          flush=True)
            if n % 500 == 0:
                print("[%5d/%5d] %-28s %.1fs inv=%d hang=%d"
                      % (n, len(cs), arm, time.time() - t0, invalid_runs,
                         total_hangs), flush=True)
    finally:
        bench.close()
        fh.close()
    dur = time.time() - t0
    summary = {"run": a.run, "n_cases": len(cs), "duration_s": round(dur, 1),
               "hangs": total_hangs, "cf_hangs": cf_hangs,
               "invalid_runs": invalid_runs, "arms_stopped": sorted(dead_arms),
               "cf_arms_stopped": cf_dead, "aborted": aborted,
               "concurrent_gpu_procs_at_end": subprocess.run(
                   ["bash", "-c", "ps ax | grep -c '[a]gxrun_persist\\|[a]gxrender'"],
                   capture_output=True, text=True).stdout.strip(),
               "sweep_sha256": sha((run_dir / "sweep.jsonl").read_bytes())}
    (run_dir / "01_summary.json").write_text(json.dumps(summary, indent=1,
                                                        sort_keys=True))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
