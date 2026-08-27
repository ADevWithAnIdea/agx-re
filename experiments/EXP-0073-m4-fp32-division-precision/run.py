#!/usr/bin/env python3
"""EXP-0073 capture runner. Never runs a device operation without --execute.

Frozen inputs live here (DIRECTED + LCG); verify.py and analysis.py import this
module so the directed list and the randomized block have a single source of
truth that CAPTURE_CONTRACT.json freezes a copy of.
"""
import argparse, datetime, hashlib, json, platform, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
EXP_REL = "experiments/EXP-0073-m4-fp32-division-precision"

RUNS = ("m4-20260827-run01", "m4-20260827-run02")

# Frozen directed edge-case pairs: (name, a bits, b bits), uppercase hex.
DIRECTED = (
    ("nn_one_third",            "0x3F800000", "0x40400000"),  # 1/3
    ("nn_two_thirds",           "0x40000000", "0x40400000"),  # 2/3
    ("nn_one_tenth",            "0x3F800000", "0x41200000"),  # 1/10
    ("nn_one_seventh",          "0x3F800000", "0x40E00000"),  # 1/7
    ("nn_one_plus_eps",         "0x3F800001", "0x3F800000"),  # (1+2^-23)/1 exact
    ("nn_one_minus_ulp_half",   "0x3F7FFFFF", "0x3F800000"),  # (1-2^-24)/1 exact
    ("nn_eps_over_same",        "0x3F800001", "0x3F800001"),  # -> 1
    ("nn_pi_over_two",          "0x40490FDB", "0x40000000"),  # exact halving
    ("nn_seven_ninths",         "0x40E00000", "0x41100000"),  # awkward repeating
    ("nn_1e9_over_three",       "0x4E6E6B28", "0x40400000"),  # wide exponent gap
    ("nn_one_over_1e9",         "0x3F800000", "0x4E6E6B28"),
    ("nn_neg_one_third",        "0xBF800000", "0x40400000"),
    ("nn_negneg_one_third",     "0xBF800000", "0xC0400000"),
    ("nn_1e6_over_seven",       "0x49742400", "0x40E00000"),
    ("nn_awkward_mantissas",    "0x4B3B21AF", "0x3EA9FB62"),
    ("nn_identity",             "0x3F800000", "0x3F800000"),
    ("sd_minsub_div_one",       "0x00000001", "0x3F800000"),  # min subnormal / 1
    ("sd_maxsub_div_one",       "0x007FFFFF", "0x3F800000"),  # max subnormal / 1
    ("sd_minnorm_div_one",      "0x00800000", "0x3F800000"),
    ("sd_one_div_minsub",       "0x3F800000", "0x00000001"),  # -> overflow to inf
    ("sd_minsub_div_minsub",    "0x00000001", "0x00000001"),  # -> exactly 1
    ("sd_maxsub_div_minsub",    "0x007FFFFF", "0x00000001"),  # -> 8388607
    ("sd_minsub_div_subthree",  "0x00000001", "0x00000003"),  # sub/sub = exactly 1/3
    ("sd_two_sub_div_subthree", "0x00000002", "0x00000003"),  # sub/sub = exactly 2/3
    ("sd_threesub_div_subtwo",  "0x00000003", "0x00000002"),  # sub/sub = exactly 3/2
    ("sd_neg_minsub_div_minsub","0x80000001", "0x00000001"),  # -> -1
    ("sd_minsub_div_three",     "0x00000001", "0x40400000"),  # gradual RNE -> +0
    ("sd_twosub_div_three",     "0x00000002", "0x40400000"),  # 2/3 unit -> 1 unit
    ("sd_threesub_div_two",     "0x00000003", "0x40000000"),  # 1.5 tie -> even
    ("sd_sevensub_div_two",     "0x00000007", "0x40000000"),  # 3.5 tie -> even
    ("su_minnorm_div_two",      "0x00800000", "0x40000000"),  # exact subnormal 0x00400000
    ("su_maxsub_div_two",       "0x007FFFFF", "0x40000000"),  # 4194303.5 tie -> even
    ("su_minsub_div_half",      "0x00000001", "0x3F000000"),  # -> 0x00000002 exact
    ("su_minnorm_div_2p126",    "0x00800000", "0x7F000000"),  # 2^-252 -> +0
    ("su_minnorm_div_maxfloat", "0x00800000", "0x7F7FFFFF"),  # -> +0
    ("su_maxsub_div_maxfloat",  "0x007FFFFF", "0x7F7FFFFF"),  # -> +0
    ("ez_poszero_div_one",      "0x00000000", "0x3F800000"),  # +0
    ("ez_negzero_div_one",      "0x80000000", "0x3F800000"),  # -0
    ("ez_negzero_div_negone",   "0x80000000", "0xBF800000"),  # +0
    ("ez_x_div_negx",           "0x40400000", "0xC0400000"),  # -> -1
    ("ez_negx_div_x",           "0xC0400000", "0x40400000"),  # -> -1
    ("ez_negx_div_negx",        "0xC0400000", "0xC0400000"),  # -> +1
    ("dz_one_div_pzero",        "0x3F800000", "0x00000000"),  # +inf
    ("dz_one_div_nzero",        "0x3F800000", "0x80000000"),  # -inf
    ("dz_negone_div_pzero",     "0xBF800000", "0x00000000"),  # -inf
    ("dz_negone_div_nzero",     "0xBF800000", "0x80000000"),  # +inf
    ("dz_minsub_div_pzero",     "0x00000001", "0x00000000"),  # +inf
    ("nz_pzero_pzero",          "0x00000000", "0x00000000"),  # 0/0 NaN
    ("nz_nzero_pzero",          "0x80000000", "0x00000000"),  # 0/0 NaN
    ("nz_pzero_nzero",          "0x00000000", "0x80000000"),  # 0/0 NaN
    ("nz_nzero_nzero",          "0x80000000", "0x80000000"),  # 0/0 NaN
    ("nz_inf_inf",              "0x7F800000", "0x7F800000"),  # inf/inf NaN
    ("nz_neginf_inf",           "0xFF800000", "0x7F800000"),  # NaN
    ("nz_neginf_neginf",        "0xFF800000", "0xFF800000"),  # NaN
    ("ix_inf_div_three",        "0x7F800000", "0x40400000"),  # +inf
    ("ix_neginf_div_three",     "0xFF800000", "0x40400000"),  # -inf
    ("ix_inf_div_negthree",     "0x7F800000", "0xC0400000"),  # -inf
    ("xi_one_div_inf",          "0x3F800000", "0x7F800000"),  # +0
    ("xi_negone_div_inf",       "0xBF800000", "0x7F800000"),  # -0
    ("xi_pzero_div_inf",        "0x00000000", "0x7F800000"),  # +0
    ("xi_nzero_div_neginf",     "0x80000000", "0xFF800000"),  # +0
    ("xi_maxfloat_div_inf",     "0x7F7FFFFF", "0x7F800000"),  # +0
    ("ob_maxfloat_div_minnorm", "0x7F7FFFFF", "0x00800000"),  # -> inf
    ("ob_maxfloat_div_half",    "0x7F7FFFFF", "0x3F000000"),  # just above threshold -> inf
    ("ob_maxfloat_div_four",    "0x7F7FFFFF", "0x40800000"),  # finite near max
    ("ob_2p127_div_half",       "0x7F000000", "0x3F000000"),  # exactly 2^128 -> inf
    ("ob_2p127_div_two",        "0x7F000000", "0x40000000"),  # exactly 2^126
    ("ob_maxfloat_div_1plus",   "0x7F7FFFFF", "0x3F800001"),  # largest finite boundary
    ("ob_maxfloat_div_1minus",  "0x7F7FFFFF", "0x3F7FFFFF"),  # exactly 2^128 tie -> inf
    ("ob_negmaxfloat_div_1minus","0xFF7FFFFF","0x3F7FFFFF"),  # -> -inf
    ("ob_maxfloat_div_maxsub",  "0x7F7FFFFF", "0x007FFFFF"),  # max / tiny subnormal -> inf
    ("np_qnan_dividend",        "0x7FC12345", "0x3F800000"),  # NaN payload verbatim
    ("np_qnan_divisor",         "0x3F800000", "0x7FC54321"),  # NaN payload verbatim
    ("np_negqnan_dividend",     "0xFFC12345", "0x40400000"),  # NaN payload verbatim
    ("np_qnan_div_zero",        "0x7FC12345", "0x00000000"),  # NaN payload verbatim
)

# Frozen deterministic randomized block.
LCG = {
    "seed": 0x5A17C0DE,
    "multiplier": 1664525,
    "increment": 1013904223,
    "modulus": 2 ** 32,
    "pairs": 4096,
    "draws_per_pair": 2,
    "usage": "state=seed; per pair draw a then b; each draw used directly as the binary32 bit pattern",
}


def lcg_pairs():
    x = LCG["seed"]
    out = []
    for _ in range(LCG["pairs"]):
        x = (x * LCG["multiplier"] + LCG["increment"]) % LCG["modulus"]
        a = x
        x = (x * LCG["multiplier"] + LCG["increment"]) % LCG["modulus"]
        b = x
        out.append((a, b))
    return out


def all_cases():
    """Frozen ordered case list: (kind, name, a_int, b_int)."""
    cases = [("directed", nm, int(a, 16), int(b, 16)) for nm, a, b in DIRECTED]
    for j, (a, b) in enumerate(lcg_pairs()):
        cases.append(("randomized", "rnd_%04d" % j, a, b))
    return cases


TOTAL = len(DIRECTED) + LCG["pairs"]

AUTH_CODE = ("kernels/fdiv_precision.metal", "harness/probe.m", "run.py",
             "analysis.py", "make_manifest.py", "verify.py")
AUTH_DOC = ("PRE_REGISTRATION.md", "README.md")


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def provenance():
    def git(*a):
        return subprocess.run(["git", *a], cwd=REPO, text=True, capture_output=True, check=True).stdout
    exp = git("status", "--porcelain", "--", EXP_REL)
    return {
        "git_revision": git("rev-parse", "HEAD").strip(),
        "git_dirty": git("status", "--porcelain").strip() != "",
        "experiment_tree_dirty_entries": len([l for l in exp.splitlines() if l.strip()]),
        "authored_code_sha256": {p: sha(HERE / p) for p in AUTH_CODE},
        "authored_doc_sha256": {p: sha(HERE / p) for p in AUTH_DOC},
    }


def put(p, o):
    p.write_text(json.dumps(o, indent=2, sort_keys=True) + "\n")


def rec(argv, timeout, cwd):
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        p = subprocess.run([str(x) for x in argv], cwd=str(cwd), text=True, capture_output=True, timeout=timeout)
        return {"argv": [str(x) for x in argv], "cwd": str(cwd), "timeout_seconds": timeout,
                "started_utc": started, "timed_out": False, "exit": p.returncode,
                "stdout": p.stdout, "stderr": p.stderr, "exception": None}
    except subprocess.TimeoutExpired as e:
        return {"argv": [str(x) for x in argv], "cwd": str(cwd), "timeout_seconds": timeout,
                "started_utc": started, "timed_out": True, "exit": None,
                "stdout": e.stdout or "", "stderr": e.stderr or "", "exception": "TimeoutExpired"}
    except OSError as e:
        return {"argv": [str(x) for x in argv], "cwd": str(cwd), "timeout_seconds": timeout,
                "started_utc": started, "timed_out": False, "exit": None,
                "stdout": "", "stderr": "", "exception": type(e).__name__}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id")
    ap.add_argument("--execute", action="store_true")
    a = ap.parse_args()
    if not a.execute:
        raise SystemExit("refusing device operation: pass --execute only after approved pre-GPU review")
    if a.run_id not in RUNS:
        raise SystemExit("run-id must be one contracted append-only ID: " + ", ".join(RUNS))
    gate = "--preflight" if a.run_id == RUNS[0] else "--between-runs"
    if subprocess.run([sys.executable, "-B", "verify.py", gate], cwd=HERE).returncode:
        raise SystemExit("run gate failed")
    current = provenance()
    if a.run_id == RUNS[1]:
        first = json.loads((HERE / "raw" / RUNS[0] / "00_inputs.json").read_text())
        for k in ("git_revision", "git_dirty", "authored_code_sha256", "authored_doc_sha256"):
            if first.get(k) != current[k]:
                raise SystemExit("run02 provenance differs from closed run01: " + k)
    raw = HERE / "raw" / a.run_id
    work = HERE / "work" / a.run_id
    if raw.exists() or work.exists():
        raise SystemExit("append-only path already exists")
    raw.mkdir(parents=True)
    work.mkdir(parents=True)
    try:
        env = {
            "schema": 1,
            **current,
            "sw_vers": rec(["sw_vers"], 10, HERE),
            "xcrun_version": rec(["xcrun", "--version"], 10, HERE),
            "python": sys.version.split()[0],
            "machine": platform.machine(),
            "boundary": "public Metal API; runtime MSL compile with fastMathEnabled=NO and mathMode=Safe; "
                        "owned shared buffers; no binary/archive/BO/compiled-shader-byte inspection",
            "timeouts_seconds": {"env_command": 10, "host_build": 60, "library_compile": 120,
                                 "dispatch_readback": 300, "probe_process": 300},
        }
        put(raw / "00_inputs.json", env)
        if any(env[z]["timed_out"] or env[z]["exit"] != 0 or env[z]["exception"] is not None
               for z in ("sw_vers", "xcrun_version")):
            put(raw / "STOP.json", {"schema": 1, "phase": "environment", "automatic_retry": False})
            return

        cases = all_cases()
        doc = {"schema": 1, "run_id": a.run_id,
               "directed": [{"i": i, "name": nm, "a": "0x%08X" % ai, "b": "0x%08X" % bi}
                            for i, (k, nm, ai, bi) in enumerate(cases) if k == "directed"],
               "randomized": [{"i": i, "a": "0x%08X" % ai, "b": "0x%08X" % bi}
                              for i, (k, nm, ai, bi) in enumerate(cases) if k == "randomized"]}
        put(raw / "01_cases.json", doc)
        (work / "in.bin").write_bytes(b"".join(ai.to_bytes(4, "little") + bi.to_bytes(4, "little")
                                               for _, _, ai, bi in cases))

        build = rec(["xcrun", "clang", "-fobjc-arc", "-Wno-deprecated-declarations", "-o", work / "probe",
                     HERE / "harness/probe.m", "-framework", "Metal", "-framework", "Foundation"], 60, HERE)
        put(raw / "02_build.json", build)
        if build["timed_out"] or build["exit"] != 0 or build["exception"] is not None:
            put(raw / "STOP.json", {"schema": 1, "phase": "host_build", "automatic_retry": False})
            return

        disp = rec([work / "probe", "--source", HERE / "kernels/fdiv_precision.metal",
                    "--cases", work / "in.bin", "--n", TOTAL, "--out", work / "results.jsonl"], 300, HERE)
        if disp["timed_out"] or disp["exit"] != 0 or disp["exception"] is not None:
            put(raw / "03_dispatch.json", disp)
            put(raw / "STOP.json", {"schema": 1, "phase": "dispatch", "automatic_retry": False})
            return
        try:
            summary = json.loads(disp["stdout"])
        except ValueError:
            summary = None
        ok = (summary is not None and summary.get("command_buffer_status") == 4
              and summary.get("n") == TOTAL and summary.get("fast_math") is False
              and summary.get("math_mode_raw") == 0
              and all(summary.get(k) is True for k in
                      ("in_prefix_guard", "in_suffix_guard", "out_prefix_guard", "out_suffix_guard",
                       "results_written")))
        disp = {**disp, "results_sha256": sha(work / "results.jsonl"),
                "results_lines": sum(1 for _ in (work / "results.jsonl").open("rb")),
                "summary": summary}
        put(raw / "03_dispatch.json", disp)
        if not ok or disp["results_lines"] != TOTAL:
            put(raw / "STOP.json", {"schema": 1, "phase": "summary_check", "automatic_retry": False})
            return
        shutil.move(str(work / "results.jsonl"), str(raw / "04_results.jsonl"))
        put(raw / "05_run_manifest.json", {
            "schema": 1, "run_id": a.run_id, "directed_count": len(DIRECTED),
            "randomized_count": LCG["pairs"], "total_cases": TOTAL,
            "runner_sha256": sha(HERE / "run.py"), "harness_sha256": sha(HERE / "harness/probe.m"),
            "kernel_sha256": sha(HERE / "kernels/fdiv_precision.metal"),
            "cases_sha256": sha(raw / "01_cases.json"), "results_sha256": disp["results_sha256"]})
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
