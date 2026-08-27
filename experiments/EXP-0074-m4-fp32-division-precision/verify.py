#!/usr/bin/env python3
"""Fail-closed static and post-capture verifier for EXP-0074.

This is the successor to the EXP-0073 verifier, whose dispatch-record check was
self-contradictory (one code path demanded 9 keys, another demanded those 9 plus
3 more, for the same record). EXP-0074 has ONE record checker and ONE frozen key
set per record slot:

    record(z, keys, ...)   -- the only function that validates an execution
                              record; it requires EXACT key-set equality.
    REC_KEYS               -- 9 keys, the plain subprocess receipt
                              (sw_vers, xcrun --version, host build).
    DISPATCH_KEYS          -- REC_KEYS + results_sha256 + results_lines +
                              summary, for raw/<run>/03_dispatch.json.

Extra-key policy, stated once and applied everywhere: a record carrying ANY key
outside its slot's frozen set FAILS; a record missing ANY frozen key FAILS.
There is no second definition to disagree with.

--selftest (REQUIRED before any build; named in CAPTURE_CONTRACT.json) proves
the gates are satisfiable and fail correctly BEFORE any GPU work: it fabricates
complete synthetic captures (no Metal, no device, no Apple binary) and drives
them through the same static()/captured() code paths used on real evidence,
including the run-to-run comparison. The synthetic receipt shapes required by
the task are all covered: base, complete, over-keyed, under-keyed, and
mismatched-hash.
"""
import argparse, datetime, hashlib, json, re, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import run as R          # noqa: E402
import analysis as A     # noqa: E402

# Single source of truth for the runner's own schema constants lives in run.py.
RUNS = R.RUNS
BOUNDARY = R.BOUNDARY
TIMEOUTS = R.TIMEOUTS
AUTH_CODE = R.AUTH_CODE
AUTH_DOC = R.AUTH_DOC
AUTH_ALL = AUTH_DOC + AUTH_CODE

ROOT_FILES = {"CAPTURE_CONTRACT.json", "PRE_REGISTRATION.md", "README.md",
              "RESULTS.md", "PROGRESS.md", "kernels", "harness", "run.py",
              "analysis.py", "make_manifest.py", "verify.py", "manifest.json"}
PRE_GPU_FILES = ("CAPTURE_CONTRACT.json", "PRE_REGISTRATION.md", "README.md",
                 "RESULTS.md", "PROGRESS.md", "kernels/fdiv_precision.metal",
                 "harness/probe.m", "run.py", "analysis.py", "make_manifest.py",
                 "verify.py")
RAW_FILES = {"00_inputs.json", "01_cases.json", "02_build.json", "03_dispatch.json",
             "04_results.jsonl", "05_run_manifest.json"}
REC_KEYS = {"argv", "cwd", "timeout_seconds", "started_utc", "timed_out", "exit",
            "stdout", "stderr", "exception"}
DISPATCH_KEYS = REC_KEYS | {"results_sha256", "results_lines", "summary"}
SUMMARY_KEYS = {"schema", "n", "device", "registry_id", "machine", "os", "fast_math",
                "math_mode_raw", "language_version_raw", "library_compile_seconds",
                "dispatch_seconds", "command_buffer_status", "error",
                "in_prefix_guard", "in_suffix_guard", "out_prefix_guard", "out_suffix_guard",
                "results_written"}
INPUTS_KEYS = {"schema", "git_revision", "git_dirty", "experiment_tree_dirty_entries",
               "authored_code_sha256", "authored_doc_sha256", "sw_vers", "xcrun_version",
               "python", "machine", "boundary", "timeouts_seconds"}
GATE_BETWEEN = ("run01 must be a complete closed successful raw tree and work/ absent or empty "
                "before run02 is created")
GATE_PROV = ("run02 current Git revision and authored hashes must equal the closed run01 input "
             "record; final verification additionally requires byte-identical results files")
GATE_SELFTEST = ("verify.py --selftest must pass immediately before every capture; "
                 "a capture whose verifier gates are unproven is not authorized")
GATE_SMOKE = ("before the real dispatch, the freshly built harness must run four frozen directed "
              "cases (indices 0, 26, 42, 47) into a scratch path under work/ that is never "
              "promoted into raw/, and its summary must parse with every expected field present "
              "and every result line must be complete and well formed; a payload-shape or "
              "truncation defect is a pre-capture STOP, not a post-capture quarantine")


def fail(s):
    raise SystemExit("FAIL " + s)


def req(v, s):
    if not v:
        fail(s)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def regular(p):
    return Path(p).is_file() and not Path(p).is_symlink()


# ---------------------------------------------------------------------------
# THE single authoritative execution-record check. keys is the frozen key set
# for the slot; extra keys and missing keys both fail, everywhere, identically.
# ---------------------------------------------------------------------------
def record(z, keys, argv, cwd, timeout, label):
    req(set(z) == keys, "record keys %s: expected exactly %s, got %s"
        % (label, sorted(keys), sorted(set(z))))
    req(z["argv"] == [str(x) for x in argv] and z["cwd"] == str(cwd)
        and z["timeout_seconds"] == timeout and z["timed_out"] is False
        and z["exit"] == 0 and z["exception"] is None
        and isinstance(z["stdout"], str) and isinstance(z["stderr"], str),
        "record content " + label)
    try:
        req(datetime.datetime.fromisoformat(z["started_utc"]).utcoffset() == datetime.timedelta(),
            "record timestamp " + label)
    except (TypeError, ValueError):
        fail("record timestamp " + label)


def manifest_expected(capture, root=None):
    root = HERE if root is None else Path(root)
    if capture:
        paths = tuple(sorted(str(p.relative_to(root)) for p in root.rglob("*")
                             if p.is_file() and not p.is_symlink() and p.name != "manifest.json"))
    else:
        paths = PRE_GPU_FILES
    return {"schema": 1, "state": "CAPTURED" if capture else "PRE_GPU",
            "artifacts": [{"path": p, "bytes": (root / p).stat().st_size, "sha256": sha(root / p)}
                          for p in paths]}


def contract_checks(c, root=None):
    root = HERE if root is None else Path(root)
    pairs = R.lcg_pairs()
    req(c["contract_version"] == 1 and c["experiment"] == "EXP-0074-m4-fp32-division-precision"
        and c["state"] == "PRE_GPU", "contract identity")
    req(c["target"] == "M4/G16G local host through public Metal only", "contract target")
    req(c["successor_of"] == "EXP-0073-m4-fp32-division-precision (quarantined; design adopted, "
        "verifier schema repaired)", "contract successor")
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
    req(tuple(c["preflight_sequence"]) ==
        ("python3 -B verify.py --selftest", "python3 -B make_manifest.py --check",
         "python3 -B verify.py --preflight"), "contract preflight sequence")
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
        req(h == sha(root / p), "authored hash " + p)
    req(c["timeouts_seconds"] == TIMEOUTS, "timeouts")
    cp = c["capture"]
    req(tuple(cp["runs"]) == RUNS and set(cp["required_run_paths"]) == RAW_FILES
        and set(cp["receipt_keys"]) == REC_KEYS
        and set(cp["dispatch_record_keys"]) == DISPATCH_KEYS
        and cp["extra_keys_policy"].startswith("Exact key-set equality for every record slot")
        and cp["case_line_keys"] == ["i", "a", "b", "r"]
        and set(cp["summary_keys"]) == SUMMARY_KEYS and set(cp["inputs_keys"]) == INPUTS_KEYS
        and cp["directed_count"] == len(R.DIRECTED) and cp["randomized_count"] == R.LCG["pairs"]
        and cp["total_cases"] == R.TOTAL and cp["between_runs_gate"] == GATE_BETWEEN
        and cp["cross_run_provenance_gate"] == GATE_PROV
        and cp["selftest_gate"] == GATE_SELFTEST and cp["smoke_gate"] == GATE_SMOKE
        and cp["failure_record"] == "STOP.json is append-only and ends that run; never retry automatically",
        "capture contract")
    req(c["gate"].startswith("A missing path, hash, schema field, guard flag, timeout record"),
        "gate text")


def strip_comments(t):
    return "\n".join(ln.split("//")[0] for ln in t.splitlines())


def source_checks(root=None):
    root = HERE if root is None else Path(root)
    h = (root / "harness/probe.m").read_text()
    k = strip_comments((root / "kernels/fdiv_precision.metal").read_text())
    hc = strip_comments(h)
    req("opts.fastMathEnabled = NO;" in hc and "opts.mathMode = MTLMathModeSafe;" in hc
        and "newLibraryWithSource:msl options:opts" in hc, "precise compile options")
    req("[ce dispatchThreads:" in hc and "MTLResourceStorageModeShared" in hc, "dispatch shape")
    req(not re.search(r"IOKit|objc_msgSend|MTLIO|metallib|BinaryArchive", hc), "forbidden harness token")
    # exit discipline (EXP-0072 lesson): the record must be flushed and
    # error-checked in the same thread that returns
    req("fflush(stdout) != 0 || ferror(stdout)" in hc and "STDOUT_FLUSH_FAIL" in hc
        and "single-threaded and synchronous" in h, "harness exit discipline")
    req("float a = as_type<float>(in[i].x);" in k and "float b = as_type<float>(in[i].y);" in k
        and "as_type<uint>(a / b)" in k, "kernel division form")
    req(not re.search(r"rsqrt|rcp|\bprecise\b|fast_|native_", k), "forbidden kernel token")
    rp = (root / "run.py").read_text()
    req("fastMathEnabled=NO and mathMode=Safe" in rp and "--execute" in rp, "runner boundary")
    # the repair this experiment exists to make: the runner may not start a
    # capture unless the self-test has just passed
    req('"--selftest"' in rp and "no capture is authorized" in rp, "runner selftest gate")
    # the non-recorded smoke gate must run before the real dispatch
    req('"smoke_in.bin"' in rp and "smoke_gate" in rp and '"smoke.jsonl"' in rp,
        "runner smoke gate")


def prereg_checks(root=None):
    root = HERE if root is None else Path(root)
    t = (root / "PRE_REGISTRATION.md").read_text()
    for nm, a, b in R.DIRECTED:
        req(a in t and b in t, "prereg directed anchor " + nm)
    req("0x5A17C0DE" in t and "1664525" in t and "1013904223" in t, "prereg lcg anchor")
    for nm, a, b, w in A.HAND:
        req(("0x%08X" % a) in t and ("0x%08X" % b) in t and ("0x%08X" % w) in t,
            "prereg hand anchor " + nm)
    req("roundTiesToEven" in t and "is-NaN only" in t, "prereg reference policy anchor")
    req("single authoritative" in t and "--selftest" in t, "prereg repair anchor")


def static(capture=False, require_analysis=False, root=None):
    root = HERE if root is None else Path(root)
    names = {p.name for p in root.iterdir()}
    allowed = ROOT_FILES | ({"raw"} if capture else set()) \
        | ({"analysis.json"} if require_analysis else set()) \
        | ({"work"} if "work" in names else set())
    req(not root.is_symlink() and names == allowed, "closed root: %s" % sorted(names ^ allowed))
    if require_analysis:
        req(regular(root / "analysis.json"), "derived analysis")
    if "work" in names:
        w = root / "work"
        req(w.is_dir() and not w.is_symlink() and not any(w.iterdir()), "work absent or empty")
    for p in AUTH_ALL + ("manifest.json", "RESULTS.md", "CAPTURE_CONTRACT.json", "PROGRESS.md"):
        req(regular(root / p), "regular " + p)
    for d, fs in (("kernels", {"fdiv_precision.metal"}), ("harness", {"probe.m"})):
        q = root / d
        req(q.is_dir() and not q.is_symlink() and {p.name for p in q.iterdir()} == fs
            and all(regular(x) for x in q.iterdir()), "closed " + d)
    contract_checks(json.loads((root / "CAPTURE_CONTRACT.json").read_text()), root)
    source_checks(root)
    prereg_checks(root)
    m = json.loads((root / "manifest.json").read_text())
    req(m == manifest_expected(capture, root), "manifest")


def one_run(rid, prov_out, root=None):
    root = HERE if root is None else Path(root)
    d = root / "raw" / rid
    req(d.is_dir() and not d.is_symlink(), "run dir " + rid)
    names = {p.name for p in d.iterdir()}
    req(names == RAW_FILES, "closed raw %s: %s" % (rid, sorted(names)))
    req(all(regular(p) for p in d.iterdir()), "regular raw " + rid)

    i = json.loads((d / "00_inputs.json").read_text())
    req(set(i) == INPUTS_KEYS and i["schema"] == 1 and i["machine"] == "arm64"
        and i["boundary"] == BOUNDARY and i["timeouts_seconds"] == TIMEOUTS
        and set(i["authored_code_sha256"]) == set(AUTH_CODE)
        and set(i["authored_doc_sha256"]) == set(AUTH_DOC), "inputs schema " + rid)
    c = json.loads((root / "CAPTURE_CONTRACT.json").read_text())
    frozen = {**i["authored_doc_sha256"], **i["authored_code_sha256"]}
    req(frozen == c["authored_sha256"], "inputs frozen-hash binding " + rid)
    for p, h in frozen.items():
        req(h == sha(root / p), "authored drift since capture " + rid + " " + p)
    req(subprocess.run(["git", "cat-file", "-e", i["git_revision"] + "^{commit}"],
                       cwd=REPO).returncode == 0, "revision object " + rid)
    record(i["sw_vers"], REC_KEYS, ["sw_vers"], root, TIMEOUTS["env_command"], "sw_vers " + rid)
    record(i["xcrun_version"], REC_KEYS, ["xcrun", "--version"], root,
           TIMEOUTS["env_command"], "xcrun " + rid)

    work = root / "work" / rid
    b = json.loads((d / "02_build.json").read_text())
    record(b, REC_KEYS, ["xcrun", "clang", "-fobjc-arc", "-Wno-deprecated-declarations",
                         "-o", work / "probe", root / "harness/probe.m",
                         "-framework", "Metal", "-framework", "Foundation"],
           root, TIMEOUTS["host_build"], "build " + rid)

    disp = json.loads((d / "03_dispatch.json").read_text())
    req(set(disp) == DISPATCH_KEYS, "dispatch keys %s: expected exactly %s, got %s"
        % (rid, sorted(DISPATCH_KEYS), sorted(set(disp))))
    record(disp, DISPATCH_KEYS, [work / "probe", "--source", root / "kernels/fdiv_precision.metal",
                                 "--cases", work / "in.bin", "--n", R.TOTAL,
                                 "--out", work / "results.jsonl"],
           root, TIMEOUTS["probe_process"], "dispatch " + rid)
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


def captured(runs, root=None):
    root = HERE if root is None else Path(root)
    raw = root / "raw"
    req(raw.is_dir() and not raw.is_symlink() and {p.name for p in raw.iterdir()} == set(runs),
        "exact raw runs")
    prov = []
    for rid in runs:
        one_run(rid, prov, root)
    if len(prov) == 2:
        x, y = prov
        req(x["git_revision"] == y["git_revision"] and x["frozen"] == y["frozen"],
            "cross-run revision/authored provenance")
        req(x["results"] == y["results"], "byte-exact repeat")
        req(x["summary_identity"] == y["summary_identity"], "cross-run device/compile identity")


def gate_preflight(root=None):
    root = HERE if root is None else Path(root)
    static(capture=False, root=root)
    req(not (root / "raw").exists(), "PRE_GPU tree must have no raw")


def gate_between(root=None):
    root = HERE if root is None else Path(root)
    static(capture=True, root=root)
    captured((RUNS[0],), root)


def gate_captured(root=None):
    root = HERE if root is None else Path(root)
    static(capture=True, require_analysis=True, root=root)
    captured(RUNS, root)


# ---------------------------------------------------------------------------
# Preflight self-test: synthetic captures driven through the real gates.
# No Metal, no device, no Apple binary, no network. Everything is fabricated
# inside a scratch tree that is removed on exit.
# ---------------------------------------------------------------------------
SELFTEST_DIR = "selftest"
_SYNTH_TS = "2026-08-27T00:00:00+00:00"


def _put(p, o):
    Path(p).write_text(json.dumps(o, indent=2, sort_keys=True) + "\n")


def _synth_record(keys, argv, cwd, timeout, **extra):
    z = {"argv": [str(x) for x in argv], "cwd": str(cwd), "timeout_seconds": timeout,
         "started_utc": _SYNTH_TS, "timed_out": False, "exit": 0,
         "stdout": "", "stderr": "", "exception": None}
    z.update(extra)
    return z


def _synth_summary():
    return {"schema": 1, "n": R.TOTAL, "device": "Apple M4", "registry_id": 424242,
            "machine": "arm64", "os": "SYNTHETIC 26.6.2 (build 25G82)", "fast_math": False,
            "math_mode_raw": 0, "language_version_raw": 262144, "library_compile_seconds": 0.1,
            "dispatch_seconds": 0.001, "command_buffer_status": 4, "error": "",
            "in_prefix_guard": True, "in_suffix_guard": True, "out_prefix_guard": True,
            "out_suffix_guard": True, "results_written": True}


def _synth_results_lines(flip_last=False):
    lines = []
    for i, (k, nm, ai, bi) in enumerate(R.all_cases()):
        r = (ai * 2654435761 + bi) & 0xFFFFFFFF
        if flip_last and i == R.TOTAL - 1:
            r ^= 1
        lines.append('{"i":%d,"a":"0x%08x","b":"0x%08x","r":"0x%08x"}' % (i, ai, bi, r))
    return lines


def _copy_authored(dst):
    for p in AUTH_ALL + ("CAPTURE_CONTRACT.json", "RESULTS.md", "PROGRESS.md"):
        q = Path(dst) / p
        q.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(HERE / p, q)


def _build_tree(root, runs=RUNS, mutate=None, post_manifest=None, with_analysis=True,
                pre_gpu=False):
    """Fabricate a complete, internally consistent synthetic capture tree."""
    root = Path(root)
    root.mkdir(parents=True)
    _copy_authored(root)
    git = lambda *a: subprocess.run(["git", *a], cwd=REPO, text=True,
                                    capture_output=True, check=True).stdout
    frozen = {p: sha(HERE / p) for p in AUTH_ALL}
    for rid in runs:
        d = root / "raw" / rid
        d.mkdir(parents=True)
        work = root / "work" / rid
        _put(d / "00_inputs.json", {
            "schema": 1,
            "git_revision": git("rev-parse", "HEAD").strip(),
            "git_dirty": git("status", "--porcelain").strip() != "",
            "experiment_tree_dirty_entries": 0,
            "authored_code_sha256": {p: frozen[p] for p in AUTH_CODE},
            "authored_doc_sha256": {p: frozen[p] for p in AUTH_DOC},
            "sw_vers": _synth_record(REC_KEYS, ["sw_vers"], root, TIMEOUTS["env_command"]),
            "xcrun_version": _synth_record(REC_KEYS, ["xcrun", "--version"], root,
                                           TIMEOUTS["env_command"]),
            "python": "synthetic", "machine": "arm64", "boundary": BOUNDARY,
            "timeouts_seconds": TIMEOUTS,
        })
        cases = R.all_cases()
        _put(d / "01_cases.json", {"schema": 1, "run_id": rid,
                                   "directed": [{"i": i, "name": nm, "a": "0x%08X" % ai,
                                                 "b": "0x%08X" % bi}
                                                for i, (k, nm, ai, bi) in enumerate(cases)
                                                if k == "directed"],
                                   "randomized": [{"i": i, "a": "0x%08X" % ai, "b": "0x%08X" % bi}
                                                  for i, (k, nm, ai, bi) in enumerate(cases)
                                                  if k == "randomized"]})
        _put(d / "02_build.json",
             _synth_record(REC_KEYS, ["xcrun", "clang", "-fobjc-arc",
                                      "-Wno-deprecated-declarations", "-o", work / "probe",
                                      root / "harness/probe.m", "-framework", "Metal",
                                      "-framework", "Foundation"], root, TIMEOUTS["host_build"]))
        txt = "\n".join(_synth_results_lines()) + "\n"
        (d / "04_results.jsonl").write_text(txt)
        _put(d / "03_dispatch.json",
             _synth_record(DISPATCH_KEYS, [work / "probe", "--source",
                                           root / "kernels/fdiv_precision.metal",
                                           "--cases", work / "in.bin", "--n", R.TOTAL,
                                           "--out", work / "results.jsonl"],
                           root, TIMEOUTS["probe_process"],
                           results_sha256=hashlib.sha256(txt.encode()).hexdigest(),
                           results_lines=R.TOTAL, summary=_synth_summary()))
        _put(d / "05_run_manifest.json", {
            "schema": 1, "run_id": rid, "directed_count": len(R.DIRECTED),
            "randomized_count": R.LCG["pairs"], "total_cases": R.TOTAL,
            "runner_sha256": frozen["run.py"], "harness_sha256": frozen["harness/probe.m"],
            "kernel_sha256": frozen["kernels/fdiv_precision.metal"],
            "cases_sha256": sha(d / "01_cases.json"),
            "results_sha256": hashlib.sha256(txt.encode()).hexdigest()})
    if with_analysis:
        (root / "analysis.json").write_text('{"synthetic": true}\n')
    if mutate is not None:
        mutate(root)
    _put(root / "manifest.json", manifest_expected(not pre_gpu, root))
    if post_manifest is not None:
        post_manifest(root)


def _load(root, rel):
    return json.loads((Path(root) / rel).read_text())


def _rel(kind, rid):
    return "raw/%s/%s" % (rid, {"inputs": "00_inputs.json", "cases": "01_cases.json",
                                "dispatch": "03_dispatch.json", "results": "04_results.jsonl",
                                "rmanifest": "05_run_manifest.json"}[kind])


# --- mutation helpers: each one breaks exactly one frozen expectation --------
def m_base_receipt_in_dispatch(root):          # the EXP-0073 failure shape
    rel = _rel("dispatch", RUNS[0])
    z = _load(root, rel)
    _put(Path(root) / rel, {k: z[k] for k in REC_KEYS})


def m_overkeyed_dispatch(root):
    rel = _rel("dispatch", RUNS[0])
    z = _load(root, rel)
    z["unexpected_extra_key"] = 1
    _put(Path(root) / rel, z)


def m_underkeyed_dispatch(root):
    rel = _rel("dispatch", RUNS[0])
    z = _load(root, rel)
    del z["results_lines"]
    _put(Path(root) / rel, z)


def m_mismatched_results_hash(root):
    rel = _rel("dispatch", RUNS[0])
    z = _load(root, rel)
    z["results_sha256"] = "0" * 64
    _put(Path(root) / rel, z)


def m_bad_dispatch_argv(root):
    rel = _rel("dispatch", RUNS[0])
    z = _load(root, rel)
    z["argv"] = ["/somewhere/else/probe"] + z["argv"][1:]
    _put(Path(root) / rel, z)


def m_overkeyed_sw_vers(root):
    rel = _rel("inputs", RUNS[0])
    z = _load(root, rel)
    z["sw_vers"]["unexpected_extra_key"] = 1
    _put(Path(root) / rel, z)


def m_overkeyed_summary(root):
    rel = _rel("dispatch", RUNS[0])
    z = _load(root, rel)
    z["summary"]["unexpected_extra_key"] = 1
    _put(Path(root) / rel, z)


def m_guard_violated(root):
    rel = _rel("dispatch", RUNS[0])
    z = _load(root, rel)
    z["summary"]["in_suffix_guard"] = False
    _put(Path(root) / rel, z)


def m_run02_result_differs(root):
    # one flipped result bit in run02, with run02's own results hash kept
    # consistent so the failure surfaces at the cross-run comparison
    txt = "\n".join(_synth_results_lines(flip_last=True)) + "\n"
    (Path(root) / _rel("results", RUNS[1])).write_text(txt)
    rel = _rel("dispatch", RUNS[1])
    z = _load(root, rel)
    z["results_sha256"] = hashlib.sha256(txt.encode()).hexdigest()
    _put(Path(root) / rel, z)
    rel = _rel("rmanifest", RUNS[1])
    rm = _load(root, rel)
    rm["results_sha256"] = z["results_sha256"]
    _put(Path(root) / rel, rm)


def m_run02_revision_differs(root):
    rel = _rel("inputs", RUNS[1])
    z = _load(root, rel)
    z["git_revision"] = subprocess.run(["git", "rev-parse", "HEAD~1"], cwd=REPO, text=True,
                                       capture_output=True, check=True).stdout.strip()
    _put(Path(root) / rel, z)


def m_raw_extra_file(root):
    (Path(root) / ("raw/%s/06_extra.json" % RUNS[0])).write_text("{}\n")


def m_results_line_missing(root):
    p = Path(root) / _rel("results", RUNS[0])
    lines = p.read_text().splitlines()
    p.write_text("\n".join(lines[:-1]) + "\n")


def m_case_echo_tampered(root):
    rel = _rel("cases", RUNS[0])
    z = _load(root, rel)
    z["randomized"][0]["a"] = "0x00000001"
    _put(Path(root) / rel, z)


def m_kernel_drift(root):
    p = Path(root) / "kernels/fdiv_precision.metal"
    p.write_text(p.read_text() + "\n// drifted\n")


def m_manifest_stale(root):
    # a non-authored file is edited after the manifest was generated
    p = Path(root) / "PROGRESS.md"
    p.write_text(p.read_text() + "\n")


def selftest():
    scratch = HERE / SELFTEST_DIR
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    cases = []          # (name, expectation, needle, builder)
    try:
        def add(name, expect_pass, needle, builder):
            cases.append((name, expect_pass, needle, builder))

        def broken(name, needle, mutate, **kw):
            add(name, False, needle, lambda r: _build_tree(r, mutate=mutate, **kw))

        add("preflight_gate_satisfiable", True, None,
            lambda r: _build_tree(r, runs=(), with_analysis=False, pre_gpu=True))
        add("captured_gate_satisfiable", True, None,
            lambda r: _build_tree(r))
        add("between_runs_gate_satisfiable", True, None,
            lambda r: _build_tree(r, runs=(RUNS[0],), with_analysis=False))
        broken("receipt_base_in_dispatch_slot", "dispatch keys", m_base_receipt_in_dispatch)
        broken("receipt_overkeyed_dispatch", "dispatch keys", m_overkeyed_dispatch)
        broken("receipt_underkeyed_dispatch", "dispatch keys", m_underkeyed_dispatch)
        broken("receipt_mismatched_results_hash", "results hash", m_mismatched_results_hash)
        broken("receipt_bad_dispatch_argv", "record content", m_bad_dispatch_argv)
        broken("receipt_overkeyed_sw_vers", "record keys", m_overkeyed_sw_vers)
        broken("summary_overkeyed", "summary keys", m_overkeyed_summary)
        broken("guard_violated", "summary content", m_guard_violated)
        broken("cross_run_repeat_broken", "byte-exact repeat", m_run02_result_differs)
        broken("cross_run_revision_differs", "cross-run revision", m_run02_revision_differs)
        broken("raw_extra_file", "closed raw", m_raw_extra_file)
        broken("results_line_missing", "result line count", m_results_line_missing)
        broken("case_echo_tampered", "echo", m_case_echo_tampered)
        broken("authored_hash_drift", "authored hash", m_kernel_drift)
        broken("manifest_stale", "manifest", None, post_manifest=m_manifest_stale)

        n_ok = 0
        for idx, (name, expect_pass, needle, builder) in enumerate(cases, 1):
            root = scratch / name
            try:
                builder(root)
                if expect_pass:
                    try:
                        if name == "preflight_gate_satisfiable":
                            gate_preflight(root)
                        elif name == "between_runs_gate_satisfiable":
                            gate_between(root)
                        else:
                            gate_captured(root)
                    except SystemExit as e:
                        print("  case %-32s FAIL (gate raised: %s)" % (name, e))
                        continue
                else:
                    try:
                        gate_captured(root)
                    except SystemExit as e:
                        msg = str(e)
                        if needle is not None and needle not in msg:
                            print("  case %-32s FAIL (failed on %r, expected %r)"
                                  % (name, msg, needle))
                            continue
                    else:
                        print("  case %-32s FAIL (gate unexpectedly PASSED)" % name)
                        continue
            finally:
                shutil.rmtree(root, ignore_errors=True)
            n_ok += 1
            print("  case %-32s PASS" % name)
        print("SELFTEST %s %d/%d synthetic cases (no Metal, no device, no Apple binary)"
              % ("PASS" if n_ok == len(cases) else "FAIL", n_ok, len(cases)))
        if n_ok != len(cases):
            raise SystemExit(1)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--selftest", action="store_true")
    g.add_argument("--preflight", action="store_true")
    g.add_argument("--between-runs", action="store_true")
    g.add_argument("--captured", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest()
    elif a.preflight:
        gate_preflight()
        print("PASS PRE_GPU contract; no GPU capture")
    elif a.between_runs:
        gate_between()
        print("PASS run01 contract; run02 may begin")
    else:
        gate_captured()
        print("PASS captured public-Metal FP32 division contract")


if __name__ == "__main__":
    main()
