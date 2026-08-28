#!/usr/bin/env python3
"""EXP-0139 gated runner. One process = one whole capture.

  python3 harness/run.py --run m4_YYYYMMDD_runNN [--arms A,B] [--limit N]

Writes `raw/<run_id>/00_env.json`, `raw/<run_id>/01_anchors.json` and the
append-only `raw/<run_id>/sweep.jsonl` (one record per case, flushed+fsynced
immediately). Every case is executed TWICE back to back inside the same
process; both results are recorded so run-to-run nondeterminism -- the defect
EXP-0113 found in the `iminmax` family -- is visible per case rather than
averaged away. The two GATED RUNS are separate process launches, so the
cross-launch axis is covered too.

SAFETY (FIELD-SWEEP-PROTOCOL SS7): a per-arm hang budget of 2 stops that arm
and marks it PARTIAL; a global budget of 6 aborts the run. This host has no
out-of-band recovery.
"""
import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
REPO = EXP.parents[1]
sys.path.insert(0, str(HERE))
import anchors as A          # noqa: E402
import casematrix as CM      # noqa: E402
import sweeprun as S         # noqa: E402

ARM_HANG_BUDGET = 2
GLOBAL_HANG_BUDGET = 6


def sha_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def env_block():
    def cmd(c):
        try:
            return subprocess.run(c, shell=True, capture_output=True, text=True,
                                  timeout=20).stdout.strip()
        except Exception:
            return "?"
    return {
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "host_cpu": cmd("sysctl -n machdep.cpu.brand_string"),
        "os": cmd("sw_vers -productVersion"), "build": cmd("sw_vers -buildVersion"),
        "clang": cmd("xcrun clang --version | head -1"),
        "python": sys.version.split()[0], "platform": platform.platform(),
        "git_rev": cmd("git -C %s rev-parse HEAD" % REPO),
        "git_dirty": bool(cmd("git -C %s status --porcelain" % REPO)),
        "authored_hashes": {
            "kernels/ialu_probes.metal": sha_file(EXP / "kernels" / "ialu_probes.metal"),
            "kernels/carrier_dag.metal": sha_file(EXP / "kernels" / "carrier_dag.metal"),
            "harness/casematrix.py": sha_file(HERE / "casematrix.py"),
            "harness/anchors.py": sha_file(HERE / "anchors.py"),
            "harness/sweeprun.py": sha_file(HERE / "sweeprun.py"),
            "harness/isa_helpers.py": sha_file(HERE / "isa_helpers.py"),
            "harness/run.py": sha_file(HERE / "run.py"),
        },
        "tool_hashes": {
            "tools/agx-isa/db.json": sha_file(REPO / "tools" / "agx-isa" / "db.json"),
            "tools/agxtest/agxrun_persist.m": sha_file(REPO / "tools" / "agxtest" / "agxrun_persist.m"),
            "tools/agxtest/persistrun.py": sha_file(REPO / "tools" / "agxtest" / "persistrun.py"),
            "tools/shdump/shdump.m": sha_file(REPO / "tools" / "shdump" / "shdump.m"),
            "tools/shdump/agxparse.py": sha_file(REPO / "tools" / "shdump" / "agxparse.py"),
        },
    }


def words_hex(ws):
    return "".join("%08x" % (w & 0xFFFFFFFF) for w in ws)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--arms", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--timeout", type=float, default=8.0)
    a = ap.parse_args()

    run_dir = EXP / "raw" / a.run
    if (run_dir / "sweep.jsonl").exists():
        sys.exit("REFUSING to reuse run id %s (SUBAGENT_BRIEF: never reuse or "
                 "overwrite a run id)" % a.run)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "00_env.json").write_text(json.dumps(env_block(), indent=1, sort_keys=True))

    work = EXP / "work" / a.run
    nat_fns = sorted({fn for fn, _, _, _ in CM.NAT_ANCHORS.values()})
    mains = {fn: S._compile_only(EXP / "kernels" / CM.NAT_SRC, fn, work) for fn in nat_fns}

    anchors = {}
    for arm, (fn, mn, occ, _k) in CM.NAT_ANCHORS.items():
        off, ln, fl = A.find(mains[fn], mn, occ)
        anchors[arm] = {"fn": fn, "mnemonic": mn, "offset": off, "length": ln,
                        "bytes": mains[fn][off:off + ln].hex(), "fields": fl,
                        "main_sha256": hashlib.sha256(mains[fn]).hexdigest(),
                        "main_len": len(mains[fn])}
    cases = CM.build_cases(mains)
    matrix_sha = hashlib.sha256(
        json.dumps([{k: v for k, v in c.items() if k != "i"} for c in cases],
                   sort_keys=True, default=str).encode()).hexdigest()
    (run_dir / "01_anchors.json").write_text(json.dumps(
        {"anchors": anchors, "n_cases": len(cases), "matrix_sha256": matrix_sha,
         "inputs": {"A": CM.A_IN, "B": CM.B_IN, "FA": CM.FA_IN, "FB": CM.FB_IN},
         "seed_registers": CM.SEED, "seed_registers_pop": CM.SEED_POP},
        indent=1, sort_keys=True))
    print("matrix_sha256", matrix_sha, "cases", len(cases))

    want = set(a.arms.split(",")) if a.arms else None
    log = S.Log(run_dir / "sweep.jsonl")

    carriers = {}

    def carrier_for(case):
        if case["splice_kind"] == "synth":
            key = ("carrier_dag.metal", "k")
        else:
            key = (CM.NAT_SRC, case["fn"])
        if key not in carriers:
            carriers[key] = S.Carrier(EXP / "kernels" / key[0], key[1], work, timeout=a.timeout)
        return carriers[key]

    # input files (written once per carrier work dir)
    ins_files = {}

    def ins_for(case, c):
        kind = case["ins"]
        if kind not in ins_files:
            if kind == "dag":
                ins_files[kind] = {1: c.write_input("dag_mem.bin", [0] * 16),
                                   2: c.write_input("dag_imem.bin", [0] * 16)}
            elif kind == "float":
                import struct
                pa = Path(c.workdir) / "fa.bin"
                pa.write_bytes(b"".join(struct.pack("<f", v) for v in CM.FA_IN))
                pb = Path(c.workdir) / "fb.bin"
                pb.write_bytes(b"".join(struct.pack("<f", v) for v in CM.FB_IN))
                ins_files[kind] = {0: str(pa), 1: str(pb)}
            else:
                ins_files[kind] = {0: c.write_input("a.bin", CM.A_IN),
                                   1: c.write_input("b.bin", CM.B_IN)}
        return ins_files[kind]

    arm_hangs = {}
    stopped = set()
    total_hangs = 0
    t0 = time.time()
    done = 0
    for case in cases:
        if want and case["arm"] not in want:
            continue
        if case["arm"] in stopped:
            continue
        if a.limit and done >= a.limit:
            break
        c = carrier_for(case)
        ins = ins_for(case, c)
        splices = CM.materialize(case)
        nout = max(int(k) for k in case["oracle"]) + 1
        reps = []
        for _rep in range(2):
            resp, iw, fw = c.run(splices, ins, case["out_slot"], nout,
                                 grid=case["grid"], tg=case["tg"])
            if case["mode"] == "float_out":
                obs = {int(k): fw[int(k)] if int(k) < len(fw) else None for k in case["oracle"]}
            else:
                obs = {int(k): iw[int(k)] if int(k) < len(iw) else None for k in case["oracle"]}
            reps.append((resp, obs, iw))
        oracle = {int(k): v for k, v in case["oracle"].items()}
        outcome, match = S.classify(reps[0][0]["status"], reps[0][1], oracle)
        outcome2, match2 = S.classify(reps[1][0]["status"], reps[1][1], oracle)
        rec = {
            "i": case["i"], "arm": case["arm"], "instr": case["instr"],
            "field": case["field"], "subfield": case.get("subfield"),
            "value": case["value"], "bytes": case["instr_hex"],
            "carrier": case["carrier"], "oracle_kind": case["oracle_kind"],
            "predict": case["predict"], "note": case["note"],
            "status": reps[0][0]["status"], "status2": reps[1][0]["status"],
            "observed": words_hex(reps[0][2]), "observed2": words_hex(reps[1][2]),
            "oracle": words_hex([oracle.get(k, 0) for k in range(nout)]),
            "match": match, "match2": match2, "outcome": outcome,
            "outcome2": outcome2, "rep_agree": (reps[0][2] == reps[1][2]),
        }
        log.write(rec)
        done += 1
        if outcome == "hang" or outcome2 == "hang":
            arm_hangs[case["arm"]] = arm_hangs.get(case["arm"], 0) + 1
            total_hangs += 1
            print("!! HANG arm=%s %s.%s=%s (arm hangs=%d total=%d)" %
                  (case["arm"], case["instr"], case["field"], case["value"],
                   arm_hangs[case["arm"]], total_hangs))
            if arm_hangs[case["arm"]] >= ARM_HANG_BUDGET:
                stopped.add(case["arm"])
                print("!! STOPPING arm %s after %d hangs -> PARTIAL" %
                      (case["arm"], arm_hangs[case["arm"]]))
            if total_hangs >= GLOBAL_HANG_BUDGET:
                print("!! GLOBAL HANG BUDGET REACHED -- aborting run")
                break
        if done % 2000 == 0:
            print("... %d/%d cases, %.1fs, hangs=%d" % (done, len(cases), time.time() - t0, total_hangs))
    log.close()
    for c in carriers.values():
        c.close()
    (run_dir / "02_summary.json").write_text(json.dumps(
        {"cases_run": done, "arm_hangs": arm_hangs, "stopped_arms": sorted(stopped),
         "total_hangs": total_hangs, "wall_s": round(time.time() - t0, 1),
         "matrix_sha256": matrix_sha}, indent=1, sort_keys=True))
    print("DONE %d cases in %.1fs, hangs=%d, stopped=%s" %
          (done, time.time() - t0, total_hangs, sorted(stopped)))


if __name__ == "__main__":
    main()
