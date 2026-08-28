#!/usr/bin/env python3
"""EXP-0098 runner. Executes the frozen case matrix (casematrix.py) and writes
gated/non-gated sibling records under raw/<run_id>/. Single-threaded harness:
one case, one process, run to completion (or hard-timed-out) before the next
starts. A NON-RECORDED smoke case runs first (written under work/, never
raw/); if it fails, no raw/ artifact is created for this run at all (standing
gate (c)).

Usage:
  python3 run.py --run run01 --out raw/m4_<date>_run01
  python3 run.py --list          # print the frozen case matrix and exit
"""
import argparse, hashlib, json, math, os, subprocess, sys, time
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
EXP = HERE.parent
REPO = EXP.parents[1]
sys.path.insert(0, str(HERE))
import casematrix as CM
import schema as S

WORKBIN = EXP / "work" / "bin"
GDDRAWS = WORKBIN / "gddraws"
XFBDRAWS = WORKBIN / "xfbdraws"

RUN_TIMEOUT_S = 90   # comfortably above the calibrated ~15.5s xfb_sync stall
                      # (PRE_REGISTRATION.md "Build-time findings")


def sh(cmd, timeout, cwd=None):
    t0 = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                            cwd=str(cwd) if cwd else str(EXP))
        return p.returncode, p.stdout, p.stderr, time.time() - t0
    except subprocess.TimeoutExpired as e:
        return -9, (e.stdout or ""), (e.stderr or "") + "\nTIMEOUT", time.time() - t0


def parse_observed(stdout):
    """Parse the STATUS/DEVICE/OBSERVED line protocol shared by
    gddraws/xfbdraws. Returns (status, observed_dict_of_str)."""
    status = None
    observed = {}
    for line in stdout.splitlines():
        if line.startswith("STATUS "):
            status = line[len("STATUS "):].strip()
        elif line.startswith("OBSERVED "):
            for tok in line[len("OBSERVED "):].split():
                if "=" in tok:
                    k, v = tok.split("=", 1)
                    observed[k] = v
    return status, observed


def status_for(rc, stdout_status):
    if stdout_status:
        return stdout_status
    if rc == -9:
        return "HANG"
    return "HARNESS_CRASH"


def nongated(case_id, wall, pid, out, err):
    tail = (out[-600:] + err[-300:])
    return {"case_id": case_id, "wall_ms": round(wall * 1000, 3), "pid": pid, "raw_tail": tail}


# ---------------------------------------------------------------------------
# Family: h_sync
def run_h_sync(case):
    p = case["params"]
    cmd = [str(GDDRAWS), "--family", "h_sync", "--indexed", str(p["indexed"]),
           "--sync", p["sync"], "--n", str(p["n"]), "--spin", str(p["spin"])]
    rc, out, err, wall = sh(cmd, RUN_TIMEOUT_S)
    status, obs = parse_observed(out)
    status = status_for(rc, status)
    unsafe = p["sync"] in ("unsync_split", "asym_producer", "asym_consumer")
    if status != "OK":
        verdict = "TIMEOUT" if status == "HANG" else "FAIL"
        observed = {}
    else:
        n = int(obs.get("n", 0)); n_correct = int(obs.get("n_correct", -1))
        n_stale = int(obs.get("n_stale", -1)); n_other = int(obs.get("n_other", -1))
        n_z_wrong = int(obs.get("n_z_wrong", -1))
        observed = {"n": n, "n_correct": n_correct, "n_stale": n_stale,
                    "n_other": n_other, "n_z_wrong": n_z_wrong}
        if unsafe:
            verdict = "N/A"   # observational: a single trial's outcome does not
                               # confirm or refute anything for a genuine race.
        else:
            verdict = "PASS" if (n_correct == n and n_stale == 0) else "FAIL"
    gated = {"case_id": case["id"], "family": case["family"], "kind": case["kind"],
             "params": p, "status": status, "verdict": verdict, "observed": observed}
    return gated, nongated(case["id"], wall, os.getpid(), out, err)


# ---------------------------------------------------------------------------
# Family: h_fields
def run_h_fields(case):
    p = case["params"]
    cmd = [str(GDDRAWS), "--family", "h_fields", "--indexed", str(p["indexed"]),
           "--cap", str(p["cap"]), "--vc", str(p["vc"]), "--ic", str(p["ic"]),
           "--vs", str(p["vs"]), "--bi", str(p["bi"]), "--bv", str(p["bv"]),
           "--idxbits", str(p["idxbits"]), "--idxbase", str(p["idxbase"]),
           "--restart-at", str(p["restartAt"]), "--ioff", str(p["ioff"])]
    rc, out, err, wall = sh(cmd, RUN_TIMEOUT_S)
    status, obs = parse_observed(out)
    status = status_for(rc, status)
    if status != "OK":
        verdict = "TIMEOUT" if status == "HANG" else "FAIL"
        observed = {}
    else:
        n_invoked = int(obs.get("n_invoked", -1)); n_correct = int(obs.get("n_correct", -1))
        minVid = int(obs.get("minVid", -1)); maxVid = int(obs.get("maxVid", -1))
        minIid = int(obs.get("minIid", -1)); maxIid = int(obs.get("maxIid", -1))
        observed = {"n_invoked": n_invoked, "n_correct": n_correct,
                    "minVid": minVid, "maxVid": maxVid, "minIid": minIid, "maxIid": maxIid}
        expected_invoked = p["vc"] * p["ic"]   # instanceCount=0 legitimately draws 0 invocations
        verdict = "PASS" if (n_invoked == expected_invoked and n_correct == n_invoked) else "FAIL"
    gated = {"case_id": case["id"], "family": case["family"], "kind": case["kind"],
             "params": p, "status": status, "verdict": verdict, "observed": observed}
    return gated, nongated(case["id"], wall, os.getpid(), out, err)


# ---------------------------------------------------------------------------
# Family: h_icbrange
def run_h_icbrange(case):
    p = case["params"]
    cmd = [str(GDDRAWS), "--family", "h_icbrange", "--maxcount", str(p["maxcount"]),
           "--wloc", str(p["wloc"]), "--wlen", str(p["wlen"])]
    rc, out, err, wall = sh(cmd, RUN_TIMEOUT_S)
    status, obs = parse_observed(out)
    status = status_for(rc, status)
    if p.get("expect_fault"):
        # Build-time-confirmed fault case (location > maxCommandCount): a
        # CMDBUF_ERROR is the CORRECT, expected outcome here, not a failure.
        verdict = "PASS" if status == "CMDBUF_ERROR" else "FAIL"
        observed = {}
    elif status != "OK":
        verdict = "TIMEOUT" if status == "HANG" else "FAIL"
        observed = {}
    else:
        n_executed = int(obs.get("n_executed", -1))
        rb_loc = int(obs.get("rangeReadback_loc", -1)); rb_len = int(obs.get("rangeReadback_len", -1))
        observed = {"n_executed": n_executed, "rangeReadback_loc": rb_loc, "rangeReadback_len": rb_len}
        maxc, wloc, wlen = p["maxcount"], p["wloc"], p["wlen"]
        expected = max(0, min(wlen, maxc - wloc)) if wloc < maxc else 0
        verdict = "PASS" if (n_executed == expected and rb_loc == wloc and rb_len == wlen) else "FAIL"
    gated = {"case_id": case["id"], "family": case["family"], "kind": case["kind"],
             "params": p, "status": status, "verdict": verdict, "observed": observed}
    return gated, nongated(case["id"], wall, os.getpid(), out, err)


# ---------------------------------------------------------------------------
# Family: h_icbmax
H_ICBMAX_EXPECT_CRASH = {8388608}

def run_h_icbmax(case):
    p = case["params"]
    cmd = [str(GDDRAWS), "--family", "h_icbmax", "--trycount", str(p["trycount"])]
    rc, out, err, wall = sh(cmd, RUN_TIMEOUT_S)
    status, obs = parse_observed(out)
    expect_crash = p["trycount"] in H_ICBMAX_EXPECT_CRASH
    if status is None:
        status = "HARNESS_CRASH" if rc != 0 else "HARNESS_CRASH"
    status = status_for(rc, status)
    if expect_crash:
        verdict = "PASS" if status != "OK" else "FAIL"
        observed = {"alloc_ok": None, "size_reported": None}
    elif status != "OK":
        verdict = "TIMEOUT" if status == "HANG" else "FAIL"
        observed = {}
    else:
        alloc_ok = int(obs.get("alloc_ok", -1)); size_reported = int(obs.get("size_reported", -1))
        observed = {"alloc_ok": alloc_ok, "size_reported": size_reported}
        verdict = "PASS" if (alloc_ok == 1 and size_reported == p["trycount"]) else "FAIL"
    gated = {"case_id": case["id"], "family": case["family"], "kind": case["kind"],
             "params": p, "status": status, "verdict": verdict, "observed": observed}
    return gated, nongated(case["id"], wall, os.getpid(), out, err)


# ---------------------------------------------------------------------------
def xfb_expected_written(numprim, maskmode, vppa, vppb, cap, stream):
    if maskmode == 0:
        req = numprim
    elif maskmode == 1:
        req = numprim if stream == 0 else 0
    elif maskmode == 2:
        req = math.ceil(numprim / 2) if stream < 2 else numprim // 2
    else:  # 3
        req = numprim if stream in (0, 1) else 0
    vpp = vppb if (maskmode == 3 and stream == 1) else vppa
    if vpp <= 0:
        return 0, req
    fits = min(req, cap // vpp)
    return fits * vpp, req


# Family: xfb_capacity
def run_xfb_capacity(case):
    p = case["params"]
    cmd = [str(XFBDRAWS), "--numprim", str(p["numprim"]), "--maskmode", str(p["maskmode"]),
           "--vppa", str(p["vppa"]), "--vppb", str(p["vppb"]),
           "--cap0", str(p["cap0"]), "--cap1", str(p["cap1"]),
           "--stride0", str(p["stride0"]), "--stride1", str(p["stride1"]),
           "--off0", str(p["off0"]), "--off1", str(p["off1"]),
           "--interleave", str(p["interleave"]), "--replay", str(p["replay"]), "--sync", "encoder_order"]
    rc, out, err, wall = sh(cmd, RUN_TIMEOUT_S)
    status, obs = parse_observed(out)
    status = status_for(rc, status)
    if status != "OK":
        verdict = "TIMEOUT" if status == "HANG" else "FAIL"
        observed = {}
    else:
        rs = p["replay"]
        wr = int(obs.get(f"wr{rs}", -1)); gen = int(obs.get(f"gen{rs}", -1))
        noPartial = int(obs.get("noPartialAtBoundary", -1))
        replay_vc = int(obs.get("replay_vertexCount", -1))
        n_invoked = int(obs.get("n_invoked", -1)); n_correct = int(obs.get("n_correct", -1))
        observed = {"wr": wr, "gen": gen, "noPartialAtBoundary": noPartial,
                    "replay_vertexCount": replay_vc, "n_invoked": n_invoked, "n_correct": n_correct}
        cap = p["cap0"] if rs == 0 else p["cap1"]
        expected_wr, expected_req = xfb_expected_written(p["numprim"], p["maskmode"], p["vppa"], p["vppb"], cap, rs)
        verdict = "PASS" if (wr == expected_wr and gen == expected_req and noPartial == 1 and
                              replay_vc == expected_wr and n_invoked == expected_wr and
                              n_correct == expected_wr) else "FAIL"
    gated = {"case_id": case["id"], "family": case["family"], "kind": case["kind"],
             "params": p, "status": status, "verdict": verdict, "observed": observed}
    return gated, nongated(case["id"], wall, os.getpid(), out, err)


# Family: xfb_multistream
def run_xfb_multistream(case):
    p = case["params"]
    cmd = [str(XFBDRAWS), "--numprim", str(p["numprim"]), "--maskmode", str(p["maskmode"]),
           "--vppa", str(p["vppa"]), "--vppb", str(p["vppb"]),
           "--cap0", str(p["cap0"]), "--cap1", str(p["cap1"]),
           "--cap2", str(p["cap0"]), "--cap3", str(p["cap0"]),
           "--replay", str(p["replay"]), "--sync", "encoder_order"]
    rc, out, err, wall = sh(cmd, RUN_TIMEOUT_S)
    status, obs = parse_observed(out)
    status = status_for(rc, status)
    if status != "OK":
        verdict = "TIMEOUT" if status == "HANG" else "FAIL"
        observed = {}
    else:
        gens = [int(obs.get(f"gen{i}", -1)) for i in range(4)]
        wrs = [int(obs.get(f"wr{i}", -1)) for i in range(4)]
        replay_vc = int(obs.get("replay_vertexCount", -1))
        n_invoked = int(obs.get("n_invoked", -1)); n_correct = int(obs.get("n_correct", -1))
        observed = {"gen0": gens[0], "gen1": gens[1], "gen2": gens[2], "gen3": gens[3],
                    "wr0": wrs[0], "wr1": wrs[1], "wr2": wrs[2], "wr3": wrs[3],
                    "replay_vertexCount": replay_vc, "n_invoked": n_invoked, "n_correct": n_correct}
        ok = True
        for s in range(4):
            cap = p["cap0"]
            exp_wr, exp_req = xfb_expected_written(p["numprim"], p["maskmode"], p["vppa"], p["vppb"], cap, s)
            if wrs[s] != exp_wr or gens[s] != exp_req:
                ok = False
        rs = p["replay"]
        exp_wr_replay, _ = xfb_expected_written(p["numprim"], p["maskmode"], p["vppa"], p["vppb"], p["cap0"], rs)
        if replay_vc != exp_wr_replay or n_invoked != exp_wr_replay or n_correct != exp_wr_replay:
            ok = False
        verdict = "PASS" if ok else "FAIL"
    gated = {"case_id": case["id"], "family": case["family"], "kind": case["kind"],
             "params": p, "status": status, "verdict": verdict, "observed": observed}
    return gated, nongated(case["id"], wall, os.getpid(), out, err)


# Family: xfb_discard
def run_xfb_discard(case):
    p = case["params"]
    cmd = [str(XFBDRAWS), "--numprim", str(p["numprim"]), "--maskmode", str(p["maskmode"]),
           "--vppa", str(p["vppa"]), "--cap0", str(p["cap0"]), "--discard", str(p["discard"]),
           "--sync", "encoder_order"]
    rc, out, err, wall = sh(cmd, RUN_TIMEOUT_S)
    status, obs = parse_observed(out)
    status = status_for(rc, status)
    if status != "OK":
        verdict = "TIMEOUT" if status == "HANG" else "FAIL"
        observed = {}
    else:
        wr0 = int(obs.get("wr0", -1)); n_invoked = int(obs.get("n_invoked", -1))
        replay_vc = int(obs.get("replay_vertexCount", -1))
        observed = {"wr0": wr0, "n_invoked": n_invoked, "replay_vertexCount": replay_vc}
        exp_wr, _ = xfb_expected_written(p["numprim"], p["maskmode"], p["vppa"], 0, p["cap0"], 0)
        if p["discard"]:
            verdict = "PASS" if (wr0 == exp_wr and n_invoked == 0 and replay_vc == 0) else "FAIL"
        else:
            verdict = "PASS" if (wr0 == exp_wr and n_invoked == exp_wr and replay_vc == exp_wr) else "FAIL"
    gated = {"case_id": case["id"], "family": case["family"], "kind": case["kind"],
             "params": p, "status": status, "verdict": verdict, "observed": observed}
    return gated, nongated(case["id"], wall, os.getpid(), out, err)


# Family: xfb_sync
def run_xfb_sync(case):
    p = case["params"]
    cmd = [str(XFBDRAWS), "--numprim", str(p["numprim"]), "--maskmode", "1", "--vppa", "3",
           "--cap0", str(p["cap0"]), "--replay", "0", "--sync", p["sync"], "--spin", str(p["spin"])]
    rc, out, err, wall = sh(cmd, RUN_TIMEOUT_S)
    status, obs = parse_observed(out)
    status = status_for(rc, status)
    unsafe = p["sync"] in ("unsync_split", "asym_producer", "asym_consumer")
    if status != "OK":
        verdict = "TIMEOUT" if status == "HANG" else "FAIL"
        observed = {}
    else:
        gen0 = int(obs.get("gen0", -1)); res0 = int(obs.get("res0", -1)); wr0 = int(obs.get("wr0", -1))
        replay_vc = int(obs.get("replay_vertexCount", -1))
        n_invoked = int(obs.get("n_invoked", -1)); n_correct = int(obs.get("n_correct", -1))
        n_stale = int(obs.get("n_stale", -1))
        observed = {"gen0": gen0, "res0": res0, "wr0": wr0, "replay_vertexCount": replay_vc,
                    "n_invoked": n_invoked, "n_correct": n_correct, "n_stale": n_stale}
        exp_wr, exp_req = xfb_expected_written(p["numprim"], 1, 3, 0, p["cap0"], 0)
        gen_res_ok = (gen0 == exp_req and wr0 == exp_wr)
        if unsafe:
            verdict = "N/A" if gen_res_ok else "FAIL"   # producer-side invariant must ALWAYS hold;
                                                          # consumer-side outcome is observational.
        else:
            verdict = "PASS" if (gen_res_ok and n_stale == 0 and replay_vc == exp_wr) else "FAIL"
    gated = {"case_id": case["id"], "family": case["family"], "kind": case["kind"],
             "params": p, "status": status, "verdict": verdict, "observed": observed}
    return gated, nongated(case["id"], wall, os.getpid(), out, err)


DISPATCH = {
    "h_sync": run_h_sync,
    "h_fields": run_h_fields,
    "h_icbrange": run_h_icbrange,
    "h_icbmax": run_h_icbmax,
    "xfb_capacity": run_xfb_capacity,
    "xfb_multistream": run_xfb_multistream,
    "xfb_discard": run_xfb_discard,
    "xfb_sync": run_xfb_sync,
}


def run_smoke():
    """NON-RECORDED smoke gate. A tiny, fast, known-good real GPU dispatch.
    Written to work/, NEVER to raw/ (standing gate (c))."""
    cmd = [str(GDDRAWS), "--family", "h_sync", "--indexed", "0", "--sync", "encoder_order", "--n", "16", "--spin", "0"]
    rc, out, err, wall = sh(cmd, 30)
    status, obs = parse_observed(out)
    ok = (status == "OK" and obs.get("n") == "16" and obs.get("n_correct") == "16" and obs.get("n_stale") == "0")
    return ok, {"cmd": cmd, "rc": rc, "stdout": out, "stderr": err, "wall_s": wall, "ok": ok}


def git_revision():
    rc, out, err, _ = sh(["git", "rev-parse", "HEAD"], 10, cwd=REPO)
    rev = out.strip() if rc == 0 else None
    rc2, out2, _, _ = sh(["git", "status", "--porcelain"], 10, cwd=REPO)
    dirty_tracked = any(line[:2].strip() and line[1] != "?" for line in out2.splitlines() if line.strip())
    return rev, dirty_tracked


def sha256_file(path):
    h = hashlib.sha256()
    h.update(Path(path).read_bytes())
    return h.hexdigest()


def authored_files():
    files = ["harness/schema.py", "harness/casematrix.py", "harness/run.py", "harness/verify.py",
              "harness/gddraws.m", "harness/xfbdraws.m"]
    for f in sorted((EXP / "kernels").glob("*.metal")):
        files.append(f"kernels/{f.name}")
    return files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", help="run id, e.g. m4_20260828_run01")
    ap.add_argument("--out", help="output raw/ directory")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    if args.list:
        for c in CM.MATRIX:
            print(c["id"], c["family"], c["kind"])
        print(f"TOTAL {CM.TOTAL}")
        return

    if not args.run or not args.out:
        print("need --run and --out (or --list)", file=sys.stderr)
        sys.exit(2)

    out_dir = Path(args.out)
    if out_dir.exists():
        print(f"FAIL: raw dir already exists: {out_dir}", file=sys.stderr)
        sys.exit(2)

    # --- NON-RECORDED smoke gate, BEFORE any raw/ artifact (gate (c)) -------
    work_dir = EXP / "work"
    work_dir.mkdir(parents=True, exist_ok=True)
    smoke_ok, smoke_receipt = run_smoke()
    (work_dir / f"{args.run}_smoke.json").write_text(json.dumps(smoke_receipt, indent=2))
    if not smoke_ok:
        print("FAIL: smoke gate failed, no raw/ artifact written", file=sys.stderr)
        sys.exit(1)
    print("SMOKE OK")

    rev, dirty = git_revision()
    inputs = {
        "run_id": args.run,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_revision_pinned": rev,
        "git_dirty_tracked": dirty,
        "authored_file_hashes": {f: sha256_file(EXP / f) for f in authored_files()},
        "total_cases": CM.TOTAL,
    }
    out_dir.mkdir(parents=True)
    (out_dir / "00_inputs.json").write_text(json.dumps(inputs, indent=2))

    gated_f = open(out_dir / "02_gated.jsonl", "a")
    nongated_f = open(out_dir / "03_nongated.jsonl", "a")
    counts = {"PASS": 0, "FAIL": 0, "TIMEOUT": 0, "N/A": 0}
    for i, case in enumerate(CM.MATRIX):
        fn = DISPATCH[case["kind"]]
        try:
            gated, ngated = fn(case)
        except Exception as e:
            gated = {"case_id": case["id"], "family": case["family"], "kind": case["kind"],
                      "params": case["params"], "status": "HARNESS_CRASH", "verdict": "FAIL",
                      "observed": {}}
            ngated = {"case_id": case["id"], "wall_ms": None, "pid": os.getpid(), "raw_tail": repr(e)[:400]}
        ok, msg = S.validate_gated(gated)
        if not ok:
            raise RuntimeError(f"schema violation for case {case['id']}: {msg}")
        ok2, msg2 = S.validate_nongated(ngated)
        if not ok2:
            raise RuntimeError(f"schema violation (nongated) for case {case['id']}: {msg2}")
        gated_f.write(json.dumps(gated, sort_keys=True) + "\n"); gated_f.flush()
        nongated_f.write(json.dumps(ngated, sort_keys=True) + "\n"); nongated_f.flush()
        counts[gated["verdict"]] = counts.get(gated["verdict"], 0) + 1
        print(f"[{i+1}/{CM.TOTAL}] {case['id']}: status={gated['status']} verdict={gated['verdict']}")
    gated_f.close(); nongated_f.close()

    manifest = {"run_id": args.run, "cases_planned": CM.TOTAL,
                "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "verdict_counts": counts}
    (out_dir / "04_manifest.json").write_text(json.dumps(manifest, indent=2))
    print("DONE", counts)


if __name__ == "__main__":
    main()
