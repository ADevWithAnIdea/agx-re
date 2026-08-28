#!/usr/bin/env python3
"""EXP-0093 runner. Executes the frozen case matrix (casematrix.py) and writes
gated/non-gated sibling records under raw/<run_id>/. Single-threaded harness:
one case, one process, run to completion (or hard-timed-out) before the next
starts. A NON-RECORDED smoke case runs first (written under work/, never
raw/); if it fails, no raw/ artifact is created for this run at all (standing
gate (c)).

Usage:
  python3 run.py --run run01 --out raw/m4_<date>_run01
  python3 run.py --list          # print the frozen case matrix and exit
"""
import argparse, hashlib, json, os, subprocess, sys, time
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
EXP = HERE.parent
REPO = EXP.parents[1]
sys.path.insert(0, str(HERE))
import casematrix as CM
import schema as S

BIN = HERE / "bin_shortcut"  # unused; binaries live in work/bin (built once, see README)
WORKBIN = EXP / "work" / "bin"
ROGLITMUS = WORKBIN / "roglitmus"
FENCELITMUS = WORKBIN / "fencelitmus"
SHDUMP = WORKBIN / "shdump"
AGXRUN = WORKBIN / "agxrun"
AGXPARSE = REPO / "tools" / "shdump" / "agxparse.py"
AGXTEST = REPO / "tools" / "agxtest" / "agxtest.py"
SPLICE = HERE / "splice.py"
ARCH_DIR = EXP / "work" / "archives"
GEN_DIR = EXP / "work" / "gen"

RUN_TIMEOUT_S = 90
COMPILE_TIMEOUT_S = 120


def sh(cmd, timeout, cwd=None):
    t0 = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                            cwd=str(cwd) if cwd else str(EXP))
        return p.returncode, p.stdout, p.stderr, time.time() - t0
    except subprocess.TimeoutExpired as e:
        return -9, (e.stdout or ""), (e.stderr or "") + "\nTIMEOUT", time.time() - t0


def parse_kv_lines(text):
    """Parse the STATUS/DEVICE/PIPELINE_SOURCE/GPUTIME_NS/... line protocol
    shared by roglitmus/fencelitmus/agxrun."""
    out = {}
    for line in text.splitlines():
        line = line.rstrip("\n")
        if not line:
            continue
        parts = line.split(" ", 1)
        key = parts[0]
        val = parts[1] if len(parts) > 1 else ""
        out.setdefault(key, []).append(val)
    return out


# ---------------------------------------------------------------------------
# Family A/B: rog_gpu
# ---------------------------------------------------------------------------
def run_rog_gpu(case):
    p = case["params"]
    src = str(EXP / p["source"])
    cmd = [str(ROGLITMUS), "--source", src, "--mode", p["mode"], "--instances", str(p["instances"])]
    rc, out, err, wall = sh(cmd, RUN_TIMEOUT_S)
    kv = parse_kv_lines(out)
    status = kv.get("STATUS", ["HANG" if rc == -9 else "HARNESS_CRASH"])[0]
    n = p["instances"]
    final_hex = None
    final_val = None
    if p["mode"] == "tex" and "CTR_TEX" in kv:
        final_hex = kv["CTR_TEX"][0]
        final_val = int(final_hex, 16)
    elif p["mode"] == "buf" and "CTR_BUF" in kv:
        toks = kv["CTR_BUF"][0].split()
        final_hex = toks[1] if len(toks) > 1 else None
        final_val = int(final_hex, 16) if final_hex else None
    if status != "OK" or final_val is None:
        verdict = "TIMEOUT" if status == "HANG" else "FAIL"
    else:
        is_exact = (final_val == n)
        if p["tag"] == "strong":
            verdict = "PASS" if is_exact else "FAIL"
        else:  # weak control: expected to race (final < N)
            verdict = "PASS" if not is_exact else "FAIL"
    gated = {"case_id": case["id"], "family": case["family"], "kind": case["kind"],
             "params": p, "status": status, "verdict": verdict,
             "observed": {"final_hex": final_hex, "n": n}}
    gputime = int(kv["GPUTIME_NS"][0]) if "GPUTIME_NS" in kv else None
    nongated = {"case_id": case["id"], "gputime_ns": gputime, "wall_ms": round(wall * 1000, 3),
                "pid": os.getpid(), "raw_tail": out[-400:] + err[-400:]}
    return gated, nongated


# ---------------------------------------------------------------------------
# Family C/D: rog_splice_gpu
# ---------------------------------------------------------------------------
def build_spliced_archive(source_path, splice_name, offsets, cache_key):
    """Compile source (--render) once per (source, splice signature), splice
    the fragment region at each offset to 0x00, return the archive path."""
    ARCH_DIR.mkdir(parents=True, exist_ok=True)
    base_arch = ARCH_DIR / f"{cache_key}_base.bin"
    if not base_arch.exists():
        rc, out, err, _ = sh([str(SHDUMP), "-o", str(base_arch), "--render",
                               "--vertex", "v_main", "--fragment", "f_main", source_path],
                              COMPILE_TIMEOUT_S)
        if rc != 0:
            raise RuntimeError(f"shdump failed: {err}")
    out_arch = ARCH_DIR / f"{cache_key}_{splice_name}.bin"
    if not out_arch.exists():
        splice_args = ["--archive", str(base_arch), "--stage", "fragment", "--out", str(out_arch)]
        for off in offsets:
            splice_args += ["--splice", f"{off}=00"]
        rc, out, err, _ = sh(["python3", str(SPLICE)] + splice_args, COMPILE_TIMEOUT_S)
        if rc != 0:
            raise RuntimeError(f"splice.py failed: {err}")
    return out_arch


def run_rog_splice_gpu(case):
    p = case["params"]
    src = str(EXP / p["source"])
    cache_key = "tex" if p["mode"] == "tex" else "buf"
    arch = build_spliced_archive(src, p["splice_name"], p["splice_offsets"], f"litmus_rog_{cache_key}")
    cmd = [str(ROGLITMUS), "--source", src, "--archive", str(arch), "--mode", p["mode"],
           "--instances", str(p["instances"])]
    rc, out, err, wall = sh(cmd, RUN_TIMEOUT_S)
    kv = parse_kv_lines(out)
    status = kv.get("STATUS", ["HANG" if rc == -9 else "HARNESS_CRASH"])[0]
    n = p["instances"]
    final_hex = None
    final_val = None
    if p["mode"] == "tex" and "CTR_TEX" in kv:
        final_hex = kv["CTR_TEX"][0]
        final_val = int(final_hex, 16)
    elif p["mode"] == "buf" and "CTR_BUF" in kv:
        toks = kv["CTR_BUF"][0].split()
        final_hex = toks[1] if len(toks) > 1 else None
        final_val = int(final_hex, 16) if final_hex else None
    pipeline_source = kv.get("PIPELINE_SOURCE", [None])[0]
    if status != "OK" or final_val is None:
        verdict = "TIMEOUT" if status == "HANG" else "FAIL"
    else:
        is_exact = (final_val == n)
        verdict = "PASS" if is_exact == p["expect_exact"] else "FAIL"
    gated = {"case_id": case["id"], "family": case["family"], "kind": case["kind"],
             "params": p, "status": status, "verdict": verdict,
             "observed": {"final_hex": final_hex, "n": n, "pipeline_source": pipeline_source}}
    gputime = int(kv["GPUTIME_NS"][0]) if "GPUTIME_NS" in kv else None
    nongated = {"case_id": case["id"], "gputime_ns": gputime, "wall_ms": round(wall * 1000, 3),
                "pid": os.getpid(), "raw_tail": out[-400:] + err[-400:]}
    return gated, nongated


# ---------------------------------------------------------------------------
# Family E: devfence_gpu
# ---------------------------------------------------------------------------
def run_devfence_gpu(case):
    p = case["params"]
    src = str(EXP / "kernels" / "litmus_devfence_pairs.metal")
    cmd = [str(FENCELITMUS), "--source", src, "--function", p["function"],
           "--pairs", str(p["pairs"]), "--iterations", str(p["iterations"]),
           "--spin-bound", str(p["spin_bound"])]
    rc, out, err, wall = sh(cmd, RUN_TIMEOUT_S)
    kv = parse_kv_lines(out)
    status = kv.get("STATUS", ["HANG" if rc == -9 else "HARNESS_CRASH"])[0]
    mismatch = producer_to = consumer_to = completed = None
    if "OUT" in kv:
        toks = kv["OUT"][0].split()
        d = dict(t.split("=") for t in toks)
        mismatch = int(d["mismatch"]); producer_to = int(d["producer_timeouts"])
        consumer_to = int(d["consumer_timeouts"]); completed = int(d["completed"])
    if status != "OK" or mismatch is None:
        verdict = "TIMEOUT" if status == "HANG" else "FAIL"
    else:
        observed_race = mismatch > 0
        verdict = "PASS" if observed_race == p["expect_race"] else "FAIL"
    gated = {"case_id": case["id"], "family": case["family"], "kind": case["kind"],
             "params": p, "status": status, "verdict": verdict,
             "observed": {"mismatch": mismatch, "producer_timeouts": producer_to,
                          "consumer_timeouts": consumer_to, "completed": completed}}
    gputime = int(kv["GPUTIME_NS"][0]) if "GPUTIME_NS" in kv else None
    nongated = {"case_id": case["id"], "gputime_ns": gputime, "wall_ms": round(wall * 1000, 3),
                "pid": os.getpid(), "raw_tail": out[-400:] + err[-400:]}
    return gated, nongated


# ---------------------------------------------------------------------------
# Family F: tgdiv_gpu (via tools/agxtest/agxtest.py, read-only tool usage)
# ---------------------------------------------------------------------------
_A_VALS = ",".join(["1"] * 256)
_SCRATCH_SENTINEL = ",".join(["-559038737"] * 256)  # 0xdeadbeef as signed int32
_EXPECTED = CM.tgdiv_expected_output()


def _s32(x):
    return x - (1 << 32) if x >= (1 << 31) else x


def run_tgdiv_gpu(case):
    p = case["params"]
    src = str(EXP / p["source"])
    workdir = EXP / "work" / "agxtest_work"
    workdir.mkdir(parents=True, exist_ok=True)
    cmd = ["python3", str(AGXTEST), "--source", src, "--function", "k",
           "--grid", "256", "--tg", "256", "--int",
           "--buf", f"0={_A_VALS}", "--out", "1=256",
           "--workdir", str(workdir), "--shdump", str(SHDUMP), "--agxrun", str(AGXRUN),
           "--agxparse", str(AGXPARSE), "--run-timeout", str(RUN_TIMEOUT_S)]
    if p["prefill_scratch"]:
        cmd += ["--buf", f"2={_SCRATCH_SENTINEL}"]
    if p["splice_offset"] is not None:
        cmd += ["--splice", f"_agc.main@{p['splice_offset']}={p['splice_hex']}"]
    rc, out, err, wall = sh(cmd, RUN_TIMEOUT_S + 30)
    status = "HANG" if rc == -9 else None
    result_vals = None
    for line in out.splitlines():
        if line.startswith("STATUS "):
            status = line.split()[1]
        if line.startswith("RESULT 1 "):
            result_vals = [int(v) for v in line.split()[2:]]
    if status is None:
        status = "HARNESS_CRASH"
    mismatch_count = None
    if status == "OK" and result_vals and len(result_vals) == 256:
        mismatch_count = sum(1 for i in range(256) if _s32(result_vals[i]) != _s32(_EXPECTED[i]))
    if status != "OK" or mismatch_count is None:
        verdict = "TIMEOUT" if status == "HANG" else "FAIL"
    else:
        verdict = "PASS" if (mismatch_count == 0) == p["expect_converge"] else "FAIL"
    gated = {"case_id": case["id"], "family": case["family"], "kind": case["kind"],
             "params": p, "status": status, "verdict": verdict,
             "observed": {"mismatch_count": mismatch_count}}
    nongated = {"case_id": case["id"], "gputime_ns": None, "wall_ms": round(wall * 1000, 3),
                "pid": os.getpid(), "raw_tail": out[-400:] + err[-400:]}
    return gated, nongated


# ---------------------------------------------------------------------------
# Family G: structural_compile (own-compile census, no GPU dispatch)
# ---------------------------------------------------------------------------
def run_structural_compile(case):
    p = case["params"]
    t0 = time.time()
    if p["kind"] == "rog_index":
        GEN_DIR.mkdir(parents=True, exist_ok=True)
        idx = p["index"]
        src_path = GEN_DIR / f"rog_idx_{idx}.metal"
        src_path.write_text(f"""#include <metal_stdlib>
using namespace metal;
struct VOut {{ float4 pos [[position]]; }};
vertex VOut v_main(uint vid [[vertex_id]]) {{
    float2 p = float2(float((vid << 1) & 2), float(vid & 2));
    VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;
}}
fragment void f_main(texture2d<uint, access::read_write> tex
                        [[raster_order_group({idx}), texture(0)]]) {{
    uint v = tex.read(uint2(0,0)).r;
    tex.write(uint4(v + 1u,0,0,0), uint2(0,0));
}}
""")
        arch = ARCH_DIR / f"rog_idx_{idx}.bin"
        rc, out, err, _ = sh([str(SHDUMP), "-o", str(arch), "--render", "--vertex", "v_main",
                               "--fragment", "f_main", str(src_path)], COMPILE_TIMEOUT_S)
        status = "OK" if rc == 0 else "COMPILE_FAIL"
        digest = None
        if rc == 0:
            rc2, hx, err2, _ = sh(["python3", str(AGXPARSE), str(arch), "--stage", "fragment",
                                    "--extract-hex"], COMPILE_TIMEOUT_S)
            digest = hashlib.sha256(hx.strip().encode()).hexdigest() if rc2 == 0 else None
        observed = {"sha256": digest}
        verdict = "PASS" if status == "OK" and digest else "FAIL"
    elif p["kind"] == "compute":
        arch = ARCH_DIR / f"struct_{Path(p['source']).stem}.bin"
        rc, out, err, _ = sh([str(SHDUMP), "-o", str(arch), "--function", p["function"],
                               str(EXP / p["source"])], COMPILE_TIMEOUT_S)
        status = "OK" if rc == 0 else "COMPILE_FAIL"
        digest = None
        if rc == 0:
            rc2, hx, err2, _ = sh(["python3", str(AGXPARSE), str(arch), "--extract-hex"],
                                   COMPILE_TIMEOUT_S)
            digest = hashlib.sha256(hx.strip().encode()).hexdigest() if rc2 == 0 else None
        observed = {"sha256": digest}
        verdict = "PASS" if status == "OK" and digest else "FAIL"
    else:  # fragment
        arch = ARCH_DIR / f"struct_{Path(p['source']).stem}.bin"
        rc, out, err, _ = sh([str(SHDUMP), "-o", str(arch), "--render", "--vertex", "v_main",
                               "--fragment", "f_main", str(EXP / p["source"])], COMPILE_TIMEOUT_S)
        status = "OK" if rc == 0 else "COMPILE_FAIL"
        digest = None
        if rc == 0:
            rc2, hx, err2, _ = sh(["python3", str(AGXPARSE), str(arch), "--stage", "fragment",
                                    "--extract-hex"], COMPILE_TIMEOUT_S)
            digest = hashlib.sha256(hx.strip().encode()).hexdigest() if rc2 == 0 else None
        observed = {"sha256": digest}
        verdict = "PASS" if status == "OK" and digest else "FAIL"
    wall = time.time() - t0
    gated = {"case_id": case["id"], "family": case["family"], "kind": case["kind"],
             "params": p, "status": status, "verdict": verdict, "observed": observed}
    nongated = {"case_id": case["id"], "gputime_ns": None, "wall_ms": round(wall * 1000, 3),
                "pid": os.getpid(), "raw_tail": ""}
    return gated, nongated


DISPATCH = {
    "rog_gpu": run_rog_gpu,
    "rog_splice_gpu": run_rog_splice_gpu,
    "devfence_gpu": run_devfence_gpu,
    "tgdiv_gpu": run_tgdiv_gpu,
    "structural_compile": run_structural_compile,
}


def run_smoke():
    """NON-RECORDED smoke gate. A tiny, fast, known-good real GPU dispatch.
    Written to work/, NEVER to raw/ (standing gate (c))."""
    src = str(EXP / CM.KERNELS_ROG_TEX_STRONG)
    cmd = [str(ROGLITMUS), "--source", src, "--mode", "tex", "--instances", "16"]
    rc, out, err, wall = sh(cmd, 30)
    kv = parse_kv_lines(out)
    ok = (kv.get("STATUS", [None])[0] == "OK" and kv.get("CTR_TEX", [None])[0] == "00000010")
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
    files = ["harness/schema.py", "harness/casematrix.py", "harness/run.py",
              "harness/verify.py", "harness/splice.py", "harness/roglitmus.m",
              "harness/fencelitmus.m"]
    for kdir in ["kernels"]:
        for f in sorted((EXP / kdir).glob("*.metal")):
            files.append(f"{kdir}/{f.name}")
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
            gated, nongated = fn(case)
        except Exception as e:
            gated = {"case_id": case["id"], "family": case["family"], "kind": case["kind"],
                      "params": case["params"], "status": "HARNESS_CRASH", "verdict": "FAIL",
                      "observed": {}}
            nongated = {"case_id": case["id"], "gputime_ns": None, "wall_ms": None,
                        "pid": os.getpid(), "raw_tail": repr(e)[:400]}
        ok, msg = S.validate_gated(gated)
        if not ok:
            raise RuntimeError(f"schema violation for case {case['id']}: {msg}")
        ok2, msg2 = S.validate_nongated(nongated)
        if not ok2:
            raise RuntimeError(f"schema violation (nongated) for case {case['id']}: {msg2}")
        gated_f.write(json.dumps(gated, sort_keys=True) + "\n"); gated_f.flush()
        nongated_f.write(json.dumps(nongated, sort_keys=True) + "\n"); nongated_f.flush()
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
