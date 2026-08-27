#!/usr/bin/env python3
"""Fail-closed static and post-capture verifier for EXP-0073."""
import argparse, datetime, hashlib, json, re, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import run as R          # noqa: E402
import analysis as A     # noqa: E402

ROOT = {"CAPTURE_CONTRACT.json", "PRE_REGISTRATION.md", "README.md", "RESULTS.md",
        "kernels", "harness", "run.py", "analysis.py", "make_manifest.py", "verify.py", "manifest.json"}
AUTH_CODE = ("kernels/fdiv_precision.metal", "harness/probe.m", "run.py", "analysis.py",
             "make_manifest.py", "verify.py")
AUTH_DOC = ("PRE_REGISTRATION.md", "README.md")
AUTH_ALL = AUTH_DOC + AUTH_CODE
RUNS = ("m4-20260827-run01", "m4-20260827-run02")
RAW_FILES = {"00_inputs.json", "01_cases.json", "02_build.json", "03_dispatch.json",
             "04_results.jsonl", "05_run_manifest.json"}
REC_KEYS = {"argv", "cwd", "timeout_seconds", "started_utc", "timed_out", "exit", "stdout",
            "stderr", "exception"}
SUMMARY_KEYS = {"schema", "n", "device", "registry_id", "machine", "os", "fast_math",
                "math_mode_raw", "language_version_raw", "library_compile_seconds",
                "dispatch_seconds", "command_buffer_status", "error",
                "in_prefix_guard", "in_suffix_guard", "out_prefix_guard", "out_suffix_guard",
                "results_written"}
INPUTS_KEYS = {"schema", "git_revision", "git_dirty", "experiment_tree_dirty_entries",
               "authored_code_sha256", "authored_doc_sha256", "sw_vers", "xcrun_version",
               "python", "machine", "boundary", "timeouts_seconds"}
TIMEOUTS = {"env_command": 10, "host_build": 60, "library_compile": 120,
            "dispatch_readback": 300, "probe_process": 300}
BOUNDARY = ("public Metal API; runtime MSL compile with fastMathEnabled=NO and mathMode=Safe; "
            "owned shared buffers; no binary/archive/BO/compiled-shader-byte inspection")
GATE_BETWEEN = ("run01 must be a complete closed successful raw tree and work/ absent or empty "
                "before run02 is created")
GATE_PROV = ("run02 current Git revision and authored hashes must equal the closed run01 input "
             "record; final verification additionally requires byte-identical results files")


def fail(s):
    raise SystemExit("FAIL " + s)


def req(v, s):
    if not v:
        fail(s)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def regular(p):
    return p.is_file() and not p.is_symlink()


def manifest_expected(capture):
    if capture:
        paths = tuple(sorted(str(p.relative_to(HERE)) for p in HERE.rglob("*")
                             if p.is_file() and not p.is_symlink() and p.name != "manifest.json"))
    else:
        paths = ("PRE_REGISTRATION.md", "README.md", "RESULTS.md", "CAPTURE_CONTRACT.json",
                 "kernels/fdiv_precision.metal", "harness/probe.m", "run.py", "analysis.py",
                 "make_manifest.py", "verify.py")
    return {"schema": 1, "state": "CAPTURED" if capture else "PRE_GPU",
            "artifacts": [{"path": p, "bytes": (HERE / p).stat().st_size, "sha256": sha(HERE / p)}
                          for p in paths]}


def receipt(z, argv, cwd, timeout, label):
    req(set(z) == REC_KEYS, "receipt keys " + label)
    req(z["argv"] == [str(x) for x in argv] and z["cwd"] == str(cwd)
        and z["timeout_seconds"] == timeout and z["timed_out"] is False
        and z["exit"] == 0 and z["exception"] is None
        and isinstance(z["stdout"], str) and isinstance(z["stderr"], str),
        "receipt content " + label)
    try:
        req(datetime.datetime.fromisoformat(z["started_utc"]).utcoffset() == datetime.timedelta(),
            "receipt timestamp " + label)
    except (TypeError, ValueError):
        fail("receipt timestamp " + label)


def contract_checks(c):
    pairs = R.lcg_pairs()
    req(c["contract_version"] == 1 and c["experiment"] == "EXP-0073-m4-fp32-division-precision"
        and c["state"] == "PRE_GPU", "contract identity")
    req(c["target"] == "M4/G16G local host through public Metal only", "contract target")
    b = c["boundary"]
    req(b["apple_binary_archive_bo_or_compiled_shader_byte_inspection"] == "NONE"
        and b["private_api_or_trace"] == "NONE" and b["native_encoding_or_isa_claim"] == "NONE",
        "contract boundary")
    req(b["accesses"] == "owned shared buffers; one compute dispatch per run; runtime MSL compile",
        "contract accesses")
    comp = c["compile"]
    req(comp["api"] == "newLibraryWithSource:options:" and comp["fast_math"] is False
        and comp["math_mode"] == "MTLMathModeSafe"
        and comp["language_version"] == "not pinned; default read back and recorded verbatim",
        "contract compile")
    dc = c["directed_cases"]
    req(len(dc) == len(R.DIRECTED) and len({d["name"] for d in dc}) == len(R.DIRECTED),
        "directed count")
    for d, (nm, a, bb) in zip(dc, R.DIRECTED):
        req(set(d) == {"name", "a", "b"} and d["name"] == nm and d["a"] == a and d["b"] == bb,
            "directed entry " + nm)
    rz = c["randomized"]
    req(rz["seed"] == R.LCG["seed"] and rz["multiplier"] == R.LCG["multiplier"]
        and rz["increment"] == R.LCG["increment"] and rz["modulus"] == R.LCG["modulus"]
        and rz["pairs"] == R.LCG["pairs"] and rz["draws_per_pair"] == 2
        and rz["usage"] == R.LCG["usage"], "lcg spec")
    req(rz["first_pair"] == ["0x%08X" % pairs[0][0], "0x%08X" % pairs[0][1]]
        and rz["last_pair"] == ["0x%08X" % pairs[-1][0], "0x%08X" % pairs[-1][1]], "lcg anchors")
    rf = c["reference"]
    req(rf["rounding"] == "IEEE-754 binary32 roundTiesToEven"
        and rf["denormals"] == "gradual underflow in the reference (no flush)"
        and rf["binary64_double_rounding"] == "forbidden; not used by either method"
        and rf["nan_policy"].startswith("NaN cases are compared by is-NaN only"), "reference spec")
    hv = rf["hand_validation"]
    req(len(hv) == len(A.HAND), "hand count")
    for h, (nm, a, bb, w) in zip(hv, A.HAND):
        req(set(h) == {"name", "a", "b", "expected"} and h["name"] == nm
            and h["a"] == "0x%08X" % a and h["b"] == "0x%08X" % bb
            and h["expected"] == "0x%08X" % w, "hand entry " + nm)
    req(tuple(c["required_authored_paths"]) == AUTH_ALL, "authored path set")
    req(c["authored_sha256"].keys() == set(AUTH_ALL), "authored hash set")
    for p, h in c["authored_sha256"].items():
        req(h == sha(HERE / p), "authored hash " + p)
    req(c["timeouts_seconds"] == TIMEOUTS, "timeouts")
    cp = c["capture"]
    req(tuple(cp["runs"]) == RUNS and set(cp["required_run_paths"]) == RAW_FILES
        and set(cp["receipt_keys"]) == REC_KEYS and cp["case_line_keys"] == ["i", "a", "b", "r"]
        and set(cp["summary_keys"]) == SUMMARY_KEYS and set(cp["inputs_keys"]) == INPUTS_KEYS
        and cp["directed_count"] == len(R.DIRECTED) and cp["randomized_count"] == R.LCG["pairs"]
        and cp["total_cases"] == R.TOTAL and cp["between_runs_gate"] == GATE_BETWEEN
        and cp["cross_run_provenance_gate"] == GATE_PROV
        and cp["failure_record"] == "STOP.json is append-only and ends that run; never retry automatically",
        "capture contract")
    req(c["gate"].startswith("A missing path, hash, schema field, guard flag, timeout record"),
        "gate text")


def strip_comments(t):
    return "\n".join(ln.split("//")[0] for ln in t.splitlines())


def source_checks():
    h = (HERE / "harness/probe.m").read_text()
    k = strip_comments((HERE / "kernels/fdiv_precision.metal").read_text())
    hc = strip_comments(h)
    req("opts.fastMathEnabled = NO;" in hc and "opts.mathMode = MTLMathModeSafe;" in hc
        and "newLibraryWithSource:msl options:opts" in hc, "precise compile options")
    req("[ce dispatchThreads:" in hc and "MTLResourceStorageModeShared" in hc, "dispatch shape")
    req(not re.search(r"IOKit|objc_msgSend|MTLIO|metallib|BinaryArchive", hc), "forbidden harness token")
    req("float a = as_type<float>(in[i].x);" in k and "float b = as_type<float>(in[i].y);" in k
        and "as_type<uint>(a / b)" in k, "kernel division form")
    req(not re.search(r"rsqrt|rcp|\bprecise\b|fast_|native_", k), "forbidden kernel token")
    rp = (HERE / "run.py").read_text()
    req("fastMathEnabled=NO and mathMode=Safe" in rp and "--execute" in rp, "runner boundary")


def prereg_checks():
    t = (HERE / "PRE_REGISTRATION.md").read_text()
    for nm, a, b in R.DIRECTED:
        req(a in t and b in t, "prereg directed anchor " + nm)
    req("0x5A17C0DE" in t and "1664525" in t and "1013904223" in t, "prereg lcg anchor")
    for nm, a, b, w in A.HAND:
        req(("0x%08X" % a) in t and ("0x%08X" % b) in t and ("0x%08X" % w) in t,
            "prereg hand anchor " + nm)
    req("roundTiesToEven" in t and "is-NaN only" in t, "prereg reference policy anchor")


def static(capture=False, require_analysis=False):
    names = {p.name for p in HERE.iterdir()}
    allowed = ROOT | ({"raw"} if capture else set()) \
        | ({"analysis.json"} if require_analysis else set()) \
        | ({"work"} if "work" in names else set())
    req(not HERE.is_symlink() and names == allowed, "closed root: %s" % sorted(names ^ allowed))
    if require_analysis:
        req(regular(HERE / "analysis.json"), "derived analysis")
    if "work" in names:
        w = HERE / "work"
        req(w.is_dir() and not w.is_symlink() and not any(w.iterdir()), "work absent or empty")
    for p in AUTH_ALL + ("manifest.json", "RESULTS.md", "CAPTURE_CONTRACT.json"):
        req(regular(HERE / p), "regular " + p)
    for d, fs in (("kernels", {"fdiv_precision.metal"}), ("harness", {"probe.m"})):
        q = HERE / d
        req(q.is_dir() and not q.is_symlink() and {p.name for p in q.iterdir()} == fs
            and all(regular(x) for x in q.iterdir()), "closed " + d)
    contract_checks(json.loads((HERE / "CAPTURE_CONTRACT.json").read_text()))
    source_checks()
    prereg_checks()
    m = json.loads((HERE / "manifest.json").read_text())
    req(m == manifest_expected(capture), "manifest")


def one_run(rid, prov_out):
    d = HERE / "raw" / rid
    req(d.is_dir() and not d.is_symlink(), "run dir " + rid)
    names = {p.name for p in d.iterdir()}
    req(names == RAW_FILES, "closed raw %s: %s" % (rid, sorted(names)))
    req(all(regular(p) for p in d.iterdir()), "regular raw " + rid)

    i = json.loads((d / "00_inputs.json").read_text())
    req(set(i) == INPUTS_KEYS and i["schema"] == 1 and i["machine"] == "arm64"
        and i["boundary"] == BOUNDARY and i["timeouts_seconds"] == TIMEOUTS
        and set(i["authored_code_sha256"]) == set(AUTH_CODE)
        and set(i["authored_doc_sha256"]) == set(AUTH_DOC), "inputs schema " + rid)
    c = json.loads((HERE / "CAPTURE_CONTRACT.json").read_text())
    frozen = {**i["authored_doc_sha256"], **i["authored_code_sha256"]}
    req(frozen == c["authored_sha256"], "inputs frozen-hash binding " + rid)
    for p, h in frozen.items():
        req(h == sha(HERE / p), "authored drift since capture " + rid + " " + p)
    req(subprocess.run(["git", "cat-file", "-e", i["git_revision"] + "^{commit}"],
                       cwd=REPO).returncode == 0, "revision object " + rid)
    receipt(i["sw_vers"], ["sw_vers"], HERE, 10, "sw_vers " + rid)
    receipt(i["xcrun_version"], ["xcrun", "--version"], HERE, 10, "xcrun " + rid)

    work = HERE / "work" / rid
    b = json.loads((d / "02_build.json").read_text())
    receipt(b, ["xcrun", "clang", "-fobjc-arc", "-Wno-deprecated-declarations", "-o", work / "probe",
                HERE / "harness/probe.m", "-framework", "Metal", "-framework", "Foundation"],
            HERE, 60, "build " + rid)

    disp = json.loads((d / "03_dispatch.json").read_text())
    req(set(disp) == REC_KEYS | {"results_sha256", "results_lines", "summary"},
        "dispatch keys " + rid)
    receipt(disp, [work / "probe", "--source", HERE / "kernels/fdiv_precision.metal",
                   "--cases", work / "in.bin", "--n", R.TOTAL, "--out", work / "results.jsonl"],
            HERE, 300, "dispatch " + rid)
    s = disp["summary"]
    req(isinstance(s, dict) and set(s) == SUMMARY_KEYS, "summary keys " + rid)
    req(s["schema"] == 1 and s["n"] == R.TOTAL and s["device"] == "Apple M4"
        and s["machine"] == "arm64" and s["fast_math"] is False and s["math_mode_raw"] == 0
        and isinstance(s["language_version_raw"], int)
        and s["command_buffer_status"] == 4 and s["error"] == ""
        and s["in_prefix_guard"] and s["in_suffix_guard"] and s["out_prefix_guard"]
        and s["out_suffix_guard"] and s["results_written"], "summary content " + rid)
    req(0 <= s["library_compile_seconds"] <= TIMEOUTS["library_compile"]
        and 0 <= s["dispatch_seconds"] <= TIMEOUTS["dispatch_readback"], "summary budgets " + rid)

    cases = json.loads((d / "01_cases.json").read_text())
    frozen_cases = R.all_cases()
    req(cases["schema"] == 1 and cases["run_id"] == rid
        and len(cases["directed"]) == len(R.DIRECTED)
        and len(cases["randomized"]) == R.LCG["pairs"], "cases counts " + rid)
    for idx, cse in enumerate(cases["directed"] + cases["randomized"]):
        k, nm, a, bb = frozen_cases[idx]
        req(set(cse) == ({"i", "name", "a", "b"} if k == "directed" else {"i", "a", "b"})
            and cse["i"] == idx and cse["a"] == "0x%08X" % a and cse["b"] == "0x%08X" % bb
            and (k != "directed" or cse["name"] == nm), "case %d echo %s" % (idx, rid))

    res = (d / "04_results.jsonl").read_text().splitlines()
    req(len(res) == R.TOTAL == disp["results_lines"], "result line count " + rid)
    for idx, ln in enumerate(res):
        r = json.loads(ln)
        k, nm, a, bb = frozen_cases[idx]
        req(set(r) == {"i", "a", "b", "r"} and r["i"] == idx
            and int(r["a"], 16) == a and int(r["b"], 16) == bb
            and re.fullmatch(r"0x[0-9a-f]{8}", r["r"]), "result line %d %s" % (idx, rid))
    req(sha(d / "04_results.jsonl") == disp["results_sha256"], "results hash " + rid)

    rm = json.loads((d / "05_run_manifest.json").read_text())
    req(rm == {"schema": 1, "run_id": rid, "directed_count": len(R.DIRECTED),
               "randomized_count": R.LCG["pairs"], "total_cases": R.TOTAL,
               "runner_sha256": frozen["run.py"], "harness_sha256": frozen["harness/probe.m"],
               "kernel_sha256": frozen["kernels/fdiv_precision.metal"],
               "cases_sha256": sha(d / "01_cases.json"),
               "results_sha256": disp["results_sha256"]}, "run manifest " + rid)
    prov_out.append({"rid": rid, "git_revision": i["git_revision"], "git_dirty": i["git_dirty"],
                     "frozen": frozen,
                     "summary_identity": {k: s[k] for k in ("device", "registry_id", "machine", "os",
                                                           "fast_math", "math_mode_raw",
                                                           "language_version_raw")},
                     "results": (d / "04_results.jsonl").read_bytes()})


def captured(runs):
    raw = HERE / "raw"
    req(raw.is_dir() and not raw.is_symlink() and {p.name for p in raw.iterdir()} == set(runs),
        "exact raw runs")
    prov = []
    for rid in runs:
        one_run(rid, prov)
    if len(prov) == 2:
        x, y = prov
        req(x["git_revision"] == y["git_revision"] and x["frozen"] == y["frozen"],
            "cross-run revision/authored provenance")
        req(x["results"] == y["results"], "byte-exact repeat")
        req(x["summary_identity"] == y["summary_identity"], "cross-run device/compile identity")


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--preflight", action="store_true")
    g.add_argument("--between-runs", action="store_true")
    g.add_argument("--captured", action="store_true")
    a = ap.parse_args()
    if a.preflight:
        static()
        req(not (HERE / "raw").exists(), "PRE_GPU tree must have no raw")
        print("PASS PRE_GPU contract; no GPU capture")
    elif a.between_runs:
        static(capture=True, require_analysis=False)
        captured((RUNS[0],))
        print("PASS run01 contract; run02 may begin")
    else:
        static(capture=True, require_analysis=True)
        captured(RUNS)
        print("PASS captured public-Metal FP32 division contract")


if __name__ == "__main__":
    main()
