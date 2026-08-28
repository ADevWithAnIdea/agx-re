#!/usr/bin/env python3
"""EXP-0140 capture driver.

One `agxrun_persist` process per CARRIER (cases are ordered so the carrier
changes at most three times).  Every case appends ONE JSON object to
raw/<run_id>/sweep.jsonl with flush+fsync immediately, so a kill or a wedge
costs at most the case in flight (SUBAGENT_BRIEF.md).

ENVIRONMENTAL NOISE.  This host runs a live desktop, so an unrelated GPU
client's error puts our command buffer into recovery.  Two signatures were
observed on BYTE-IDENTICAL programs that otherwise pass 9/10 times (this
experiment's own disclosed pilots 6 and 7, work/pilot/):
  * status CMDBUF_ERROR carrying `kIOGPUCommandBufferCallbackErrorInnocentVictim`;
  * status OK with an ALL-ZERO output buffer (dispatch discarded before it wrote).
Neither is a property of the bytes under test.  Handling: an InnocentVictim
status triggers an immediate status-level retry (<=4 tries), and EVERY case is
REPLICATED -- run twice, and on disagreement a third time, majority wins.  The
replication is symmetric: it never prefers `ok`.  Every attempt is recorded
(`replicates`, `replicate_outcomes`, `unstable`).

SAFETY (FIELD-SWEEP-PROTOCOL.md SS7): a hang budget is enforced per sweep arm
and globally.  Two genuine hangs inside one arm abort the remainder of THAT
arm; `--cf-hang-budget` hangs across the control-flow arms abort every
remaining CF arm; `--global-hang-budget` aborts the run.  Aborted cases are
recorded as `skipped` records, never silently dropped.

Usage: run.py --run RUN_ID [--only GROUP_PREFIX] [--limit N] [--raw-root DIR]
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
import agxparse     # noqa: E402
from persistrun import PersistRunner  # noqa: E402
import cases as C   # noqa: E402
import isa_helpers as H  # noqa: E402
import baseline as B     # noqa: E402

CARRIER_SRC = {"uni": "carrier_uni.metal", "dsel5": "dsel5.metal",
                "gsel4": "gsel4.metal", "cf": "carrier_cf.metal"}
REQ_TIMEOUT = 8.0
ARM_HANG_BUDGET = 2
CF_CARRIER = "cf"


def sha(b):
    return hashlib.sha256(b).hexdigest()


def words(raw, mode, n):
    fmt = "<i" if mode == "int" else "<f"
    return [struct.unpack_from(fmt, raw, 4 * i)[0] if 4 * i + 4 <= len(raw) else None
            for i in range(n)]


def f32bits(v):
    return struct.unpack("<I", struct.pack("<f", v))[0]


def classify(case, status, out_raw):
    """(observed, match, outcome).  Observed values are JSON-exact: int32 for
    int mode, the IEEE-754 bit pattern for float mode."""
    if status == "HANG":
        return {}, None, "hang"
    if status != "OK":
        return {}, None, "fault"
    idxs = sorted(int(k) for k in case["oracle"])
    vals = words(out_raw, case["mode"], max(idxs) + 1)
    if any(vals[i] is None for i in idxs):
        return {str(i): None for i in idxs}, False, "wrong_value"
    if case["mode"] == "float":
        observed = {str(i): f32bits(vals[i]) for i in idxs}
        oracle = {str(i): f32bits(case["oracle"][i]) for i in idxs}
    else:
        observed = {str(i): vals[i] for i in idxs}
        oracle = {str(i): case["oracle"][i] for i in idxs}
    match = all(observed[k] == oracle[k] for k in oracle)
    if match:
        outcome = "ok"
    else:
        prim = observed[str(idxs[0])]
        outcome = "silent_zero" if prim == 0 else "wrong_value"
    return observed, match, outcome


def make_inputs(work):
    work.mkdir(parents=True, exist_ok=True)
    paths = {}
    p = work / "uni_mem.bin"
    p.write_bytes(b"".join(struct.pack("<i", 1000 + i) for i in range(64)))
    paths["uni_mem"] = str(p)
    for i, v in enumerate(C.MAGIC):
        p = work / ("uni_u%d.bin" % i)
        p.write_bytes(struct.pack("<I", v))
        paths["uni_u%d" % i] = str(p)
    for nm, vec in (("A1", C.SEL_A1), ("A2", C.SEL_A2)):
        p = work / ("sel_%s.bin" % nm)
        p.write_bytes(b"".join(struct.pack("<i", v) for v in vec))
        paths["sel_" + nm] = str(p)
    p = work / "cf_a.bin"
    p.write_bytes(b"".join(struct.pack("<f", v) for v in C.CF_A))
    paths["cf_a"] = str(p)
    p = work / "cf_n.bin"
    p.write_bytes(b"".join(struct.pack("<i", v) for v in C.CF_N))
    paths["cf_n"] = str(p)
    return paths


def ins_for(case, paths):
    c = case["carrier"]
    if c == "uni":
        return {1: paths["uni_mem"], 2: paths["uni_u0"], 3: paths["uni_u1"],
                4: paths["uni_u2"], 5: paths["uni_u3"]}
    if c == "dsel5":
        return {1: paths["sel_" + case.get("inputs", "A1")]}
    if c == "gsel4":
        return {1: paths["sel_A1"]}
    if c == "cf":
        return {1: paths["cf_a"], 2: paths["cf_n"]}
    raise ValueError(c)


def splice(case, buf, roff, mainlen):
    b = bytearray(buf)
    if "prog" in case:
        prog = case["prog"]
        assert len(prog) == mainlen, (len(prog), mainlen)
        b[roff:roff + mainlen] = prog
    elif "patch" in case:
        off, val = case["patch"]
        b[roff + off] = val
    elif "patch3" in case:
        off, blob = case["patch3"]
        b[roff + off:roff + off + len(blob)] = blob
    else:
        raise ValueError("case has no splice directive")
    return bytes(b)


def roundtrip_note(spliced, roff, mainlen):
    """Does OUR OWN decoder still tokenize the spliced region cleanly?  Recorded
    as evidence for db.json defects; never used to skip a case -- the hardware
    does not consult our decoder."""
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--only", default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--timeout", type=float, default=REQ_TIMEOUT)
    ap.add_argument("--cf-hang-budget", type=int, default=6)
    ap.add_argument("--global-hang-budget", type=int, default=10)
    ap.add_argument("--raw-root", default=None)
    a = ap.parse_args()

    run_dir = (Path(a.raw_root) / a.run) if a.raw_root else (EXP / "raw" / a.run)
    if run_dir.exists():
        sys.exit("run id %s already exists -- never reuse or overwrite a run id" % a.run)
    run_dir.mkdir(parents=True)
    work = EXP / "work" / ("run_" + a.run)
    bin_dir = EXP / "work" / "bin"

    facts = B.derive(str(bin_dir), str(work / "baseline_bin"))
    mainlens = {k: v["main_len"] for k, v in facts.items()}
    cs = C.build_cases(mainlens)
    if a.only:
        cs = [c for c in cs if c["group"].startswith(a.only)]
    if a.limit:
        cs = cs[:a.limit]

    paths = make_inputs(work)
    inputs_rec = {
        "run": a.run, "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "target": "local Apple M4 / G16G", "n_cases": len(cs),
        "carriers": {k: {kk: vv for kk, vv in v.items() if kk != "tokens"}
                     for k, v in facts.items()},
        "carrier_tokens": {k: v["tokens"] for k, v in facts.items()},
        "inputs": {"uni_magic": ["0x%08x" % m for m in C.MAGIC],
                    "sel_A1": C.SEL_A1, "sel_A2": C.SEL_A2,
                    "cf_a": C.CF_A, "cf_n": C.CF_N, "poison": C.POISON},
        "timeouts": {"per_request_s": a.timeout},
        "replication": {"trials_min": 2, "trials_max": 3,
                         "innocent_victim_retries": 4},
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
        "git_rev": subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(REPO),
                                   capture_output=True, text=True).stdout.strip(),
    }
    (run_dir / "00_inputs.json").write_text(json.dumps(inputs_rec, indent=1, sort_keys=True))

    arch = {}
    for name, fn in CARRIER_SRC.items():
        buf, roff, main = B.compile_carrier(bin_dir, EXP / "kernels" / fn,
                                             work / (name + "_base.bin"))
        arch[name] = (buf, roff, len(main))

    fh = open(run_dir / "sweep.jsonl", "a")
    sp = work / "spliced.bin"
    runner, cur_carrier = None, None
    arm_hangs, cf_hangs, total_hangs = {}, 0, 0
    dead_arms, cf_dead = set(), False
    t0 = time.time()
    try:
        for n, c in enumerate(cs):
            arm = c["arm"]
            is_cf = (c["carrier"] == CF_CARRIER)
            skip = None
            if arm in dead_arms:
                skip = "arm_stopped_after_%d_hangs" % ARM_HANG_BUDGET
            elif is_cf and cf_dead:
                skip = "cf_arm_stopped_after_%d_hangs" % a.cf_hang_budget
            elif total_hangs >= a.global_hang_budget:
                skip = "run_stopped_after_%d_hangs" % a.global_hang_budget
            if skip:
                rec = {"instr": c["instr"], "field": c["field"], "value": c["value"],
                       "bytes": c["bytes"], "observed": {}, "oracle": {},
                       "match": None, "outcome": "skipped", "carrier": c["carrier"],
                       "note": skip, "i": c["i"], "group": c["group"], "arm": arm,
                       "expect_match": c["expect_match"], "status": "SKIPPED"}
                fh.write(json.dumps(rec, sort_keys=True) + "\n")
                fh.flush(); os.fsync(fh.fileno())
                continue

            if c["carrier"] != cur_carrier:
                if runner:
                    runner.close()
                src = EXP / "kernels" / CARRIER_SRC[c["carrier"]]
                runner = PersistRunner(source=str(src), function="k", fast_math=False,
                                        agxrun_persist=str(bin_dir / "agxrun_persist"))
                cur_carrier = c["carrier"]
            buf, roff, mainlen = arch[c["carrier"]]
            spliced = splice(c, buf, roff, mainlen)
            sp.write_bytes(spliced)
            rt = roundtrip_note(spliced, roff, mainlen)
            grid, tg = c["dispatch"]
            nout = 4 * (max(int(k) for k in c["oracle"]) + 1)

            def one_attempt():
                att, errs = 0, []
                while True:
                    att += 1
                    rp = runner.request(archive=str(sp), grid=grid, tg=tg,
                                         ins=ins_for(c, paths), outs={0: max(nout, 8)},
                                         timeout=a.timeout)
                    errs.append(rp.get("error"))
                    if rp["status"] == "OK" or att >= 4:
                        return rp, att, errs
                    if "InnocentVictim" not in (rp.get("error") or ""):
                        return rp, att, errs

            trials = []
            for t in range(3):
                rp, att, errs = one_attempt()
                o, m, oc = classify(c, rp["status"], rp["outs"].get(0, b""))
                trials.append((rp, att, errs, o, m, oc))
                if t == 1 and (trials[0][5], trials[0][3]) == (trials[1][5], trials[1][3]):
                    break
            keys = [(t[5], json.dumps(t[3], sort_keys=True)) for t in trials]
            winner = max(set(keys), key=keys.count)
            unstable = len(set(keys)) > 1
            resp, attempts, errors, observed, match, outcome = trials[keys.index(winner)]
            victim = "InnocentVictim" in (resp.get("error") or "")

            rec = {"instr": c["instr"], "field": c["field"], "value": c["value"],
                   "bytes": c["bytes"], "observed": observed,
                   "oracle": ({str(k): f32bits(v) for k, v in c["oracle"].items()}
                              if c["mode"] == "float"
                              else {str(k): v for k, v in c["oracle"].items()}),
                   "match": match, "outcome": outcome, "carrier": c["carrier"],
                   "note": c["note"], "i": c["i"], "group": c["group"], "arm": arm,
                   "expect_match": c["expect_match"], "status": resp["status"],
                   "mode": c["mode"], "dispatch": [grid, tg],
                   "inputs": c.get("inputs"), "rt": rt,
                   "attempts": attempts, "error": resp.get("error"),
                   "errors": errors if attempts > 1 else None,
                   "environmental_victim": victim,
                   "replicates": len(trials), "unstable": unstable,
                   "replicate_outcomes": [t[5] for t in trials],
                   "prog_sha256": sha(spliced[roff:roff + mainlen]),
                   "restarted": any(t[0].get("restarted") for t in trials)}
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
            fh.flush(); os.fsync(fh.fileno())

            if outcome == "hang":
                total_hangs += 1
                arm_hangs[arm] = arm_hangs.get(arm, 0) + 1
                if is_cf:
                    cf_hangs += 1
                print("HANG #%d arm=%s value=%s" % (total_hangs, arm, c["value"]), flush=True)
                if arm_hangs[arm] >= ARM_HANG_BUDGET:
                    dead_arms.add(arm)
                    print("  -> STOPPING arm %s (%d hangs)" % (arm, arm_hangs[arm]), flush=True)
                if is_cf and cf_hangs >= a.cf_hang_budget:
                    cf_dead = True
                    print("  -> STOPPING all CF arms (%d hangs)" % cf_hangs, flush=True)
            if n % 500 == 0:
                print("[%5d/%5d] %-30s %.1fs" % (n, len(cs), c["group"],
                                                  time.time() - t0), flush=True)
    finally:
        if runner:
            runner.close()
        fh.close()
    dur = time.time() - t0
    summary = {"run": a.run, "n_cases": len(cs), "duration_s": round(dur, 1),
               "hangs": total_hangs, "cf_hangs": cf_hangs,
               "arms_stopped": sorted(dead_arms), "cf_arm_stopped": cf_dead,
               "sweep_sha256": sha((run_dir / "sweep.jsonl").read_bytes())}
    (run_dir / "01_summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
