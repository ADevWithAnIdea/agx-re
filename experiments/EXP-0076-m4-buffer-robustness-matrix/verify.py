#!/usr/bin/env python3
"""Fail-closed static and post-capture verifier for EXP-0076.

Schema discipline (lesson from quarantined EXP-0073): ONE record checker and
ONE frozen key set per record slot, imported from run.py -- the single source
of truth -- so the runner and the verifier cannot disagree. Extra keys and
missing keys both fail, everywhere, identically.

--selftest (REQUIRED before any capture; named in CAPTURE_CONTRACT.json) proves
every gate is satisfiable AND fails correctly BEFORE any GPU work, using
synthetic captures driven through the same static()/captured() code paths used
on real evidence -- including run.case_line, the exact record builder used at
capture time. It additionally proves the pre-capture smoke validator rejects
the EXP-0072 truncation class and passes a clean record, and -- specific to
this experiment -- that a guard-corrupting OOB-store OBSERVATION is valid
evidence (guard flags are results here, not gate failures).
"""
import argparse, datetime, hashlib, json, re, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import run as R          # noqa: E402

# Single source of truth for the runner's own schema constants lives in run.py.
RUNS = R.RUNS
BOUNDARY = R.BOUNDARY
TIMEOUTS = R.TIMEOUTS
AUTH_CODE = R.AUTH_CODE
AUTH_DOC = R.AUTH_DOC
AUTH_ALL = AUTH_DOC + AUTH_CODE
GEOMETRY = R.GEOMETRY

ROOT_FILES = {"CAPTURE_CONTRACT.json", "PRE_REGISTRATION.md", "README.md",
              "RESULTS.md", "PROGRESS.md", "kernels", "harness", "run.py",
              "analysis.py", "make_manifest.py", "verify.py", "manifest.json"}
PRE_GPU_ARTIFACTS = ("CAPTURE_CONTRACT.json", "PRE_REGISTRATION.md", "README.md",
                     "RESULTS.md", "PROGRESS.md") + AUTH_CODE
RAW_FILES = set(R.RAW_FILES)
REC_KEYS = R.REC_KEYS
CASE_KEYS = R.CASE_KEYS
SUMMARY_KEYS = R.SUMMARY_KEYS
DISPATCH_KEYS = R.DISPATCH_KEYS
INPUTS_KEYS = R.INPUTS_KEYS
RECEIPT_LINE_KEYS = R.RECEIPT_LINE_KEYS
RUN_MANIFEST_KEYS = R.RUN_MANIFEST_KEYS
MATRIX_CASE_KEYS = R.MATRIX_CASE_KEYS

GATE_BETWEEN = ("run01 must be a complete closed raw tree (all 106 cases, consistent envelope, "
                "no STOP) and work absent or empty before run02 is created")
GATE_PROV = ("run02 current Git revision and authored hashes must equal the closed run01 input record")
GATE_REPEAT = ("in-bounds cases (align_in, mis1, mishalf, last) must be byte-identical between the "
               "two runs and every case must have identical status; per-case byte-identity of "
               "out-of-allocation/straddle/atomic observations is reported as an observed "
               "determinism result, not gate-required")
GATE_SELFTEST = ("verify.py --selftest must pass immediately before every capture; a capture whose "
                 "verifier gates are unproven is not authorized")
GATE_SMOKE = ("before the append-only raw tree is created, the freshly built harness must run one "
              "scratch case (load_w32_align_in) into work/ (never promoted into raw/), and its "
              "stdout must parse as one complete JSON record with every contracted field present "
              "and a consistent shape; any payload-shape or truncation defect is a pre-capture STOP")
GATE_FAULT = ("a faulted, hung, or killed case is a recorded result (status watchdog/proc_fail/"
              "proc_timeout) and is never retried in place; only 3 consecutive OS-level spawn "
              "failures stop the run")
EXTRA_KEYS_POLICY = ("Exact key-set equality for every record slot: a record carrying any key outside "
                     "its frozen set fails, and a record missing any frozen key fails.")


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
# THE single authoritative execution-record check (plain subprocess receipts).
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
        paths = PRE_GPU_ARTIFACTS
    return {"schema": 1, "state": "CAPTURED" if capture else "PRE_GPU",
            "artifacts": [{"path": p, "bytes": (root / p).stat().st_size, "sha256": sha(root / p)}
                          for p in paths]}


def contract_checks(c, root=None):
    root = HERE if root is None else Path(root)
    req(c["contract_version"] == 1 and c["experiment"] == "EXP-0076-m4-buffer-robustness-matrix"
        and c["state"] == "PRE_GPU", "contract identity")
    req(c["target"] == "M4/G16G local host through public Metal only", "contract target")
    req(c["successor_of"] == "EXP-0068-m4-robustness-contract (superseded scaffold; "
        "nothing captured, binds nothing)", "contract successor")
    b = c["boundary"]
    req(b["apple_binary_archive_bo_or_compiled_shader_byte_inspection"] == "NONE"
        and b["private_api_or_trace"] == "NONE" and b["native_encoding_or_isa_claim"] == "NONE",
        "contract boundary")
    req(b["accesses"] == "owned shared buffers sized exactly; one case per fresh process",
        "contract accesses")
    comp = c["compile"]
    req(comp["api"] == "newLibraryWithSource:options:" and comp["fast_math"] is False
        and comp["math_mode"] == "MTLMathModeSafe"
        and comp["language_version"] == "not pinned; default read back and recorded verbatim",
        "contract compile")
    req(tuple(c["preflight_sequence"]) ==
        ("python3 -B verify.py --selftest", "python3 -B make_manifest.py --check",
         "python3 -B verify.py --preflight"), "contract preflight sequence")
    req(c["geometry"] == GEOMETRY, "contract geometry")
    mx = c["matrix"]
    req(mx["total"] == R.TOTAL and mx["widths_bits"] == [8 * w for w in R.WIDTHS]
        and mx["cases"] == R.CASES, "contract matrix")
    req(tuple(c["required_authored_paths"]) == AUTH_ALL, "authored path set")
    req(c["authored_sha256"].keys() == set(AUTH_ALL), "authored hash set")
    for p, h in c["authored_sha256"].items():
        req(h == sha(root / p), "authored hash " + p)
    req(c["timeouts_seconds"] == TIMEOUTS, "timeouts")
    cp = c["capture"]
    req(tuple(cp["runs"]) == RUNS and set(cp["required_run_paths"]) == RAW_FILES
        and set(cp["receipt_keys"]) == REC_KEYS and set(cp["case_line_keys"]) == CASE_KEYS
        and set(cp["summary_keys"]) == SUMMARY_KEYS and set(cp["dispatch_keys"]) == DISPATCH_KEYS
        and set(cp["inputs_keys"]) == INPUTS_KEYS
        and set(cp["receipt_line_keys"]) == RECEIPT_LINE_KEYS
        and set(cp["run_manifest_keys"]) == RUN_MANIFEST_KEYS
        and set(cp["matrix_case_keys"]) == MATRIX_CASE_KEYS
        and tuple(cp["status_values"]) == R.STATUS_VALUES
        and tuple(cp["in_bound_classes"]) == R.IN_BOUND_CLASSES
        and cp["extra_keys_policy"].startswith("Exact key-set equality for every record slot")
        and cp["case_fault_policy"] == GATE_FAULT
        and cp["consecutive_infra_stop"] == R.MAX_CONSECUTIVE_INFRA
        and cp["between_runs_gate"] == GATE_BETWEEN
        and cp["cross_run_provenance_gate"] == GATE_PROV
        and cp["cross_run_repeat_gate"] == GATE_REPEAT
        and cp["selftest_gate"] == GATE_SELFTEST and cp["smoke_gate"] == GATE_SMOKE
        and cp["failure_record"].startswith("Pre-capture failures retain work/<run-id>/STOP.json"),
        "capture contract")
    hyp = c["hypotheses"]
    req(hyp["H1_MEM06"] .startswith("unaligned loads return the exact in-bounds fill bytes")
        and hyp["H2_MEM07"].startswith("unaligned stores write exactly the frozen pattern")
        and hyp["H3_MEM08"].startswith("out-of-allocation reads return the uniform value 0x00")
        and hyp["H4_MEM09"].startswith("boundary-straddling reads return the per-component mix")
        and hyp["H5_MEM10"].startswith("out-of-allocation stores are discarded"),
        "hypotheses text")
    req(c["gate"].startswith("A missing path, hash, schema field, timeout record"), "gate text")


def strip_comments(t):
    return "\n".join(ln.split("//")[0] for ln in t.splitlines())


def source_checks(root=None):
    root = HERE if root is None else Path(root)
    h = (root / "harness/probe.m").read_text()
    k = strip_comments((root / "kernels/robustness_matrix.metal").read_text())
    hc = strip_comments(h)
    req("opts.fastMathEnabled = NO;" in hc and "opts.mathMode = MTLMathModeSafe;" in hc
        and "newLibraryWithSource:msl options:opts" in hc, "precise compile options")
    req("[ce dispatchThreads:" in hc and "MTLResourceStorageModeShared" in hc, "dispatch shape")
    req(not re.search(r"IOKit|objc_msgSend|MTLIO|metallib|BinaryArchive|otool|objdump", hc),
        "forbidden harness token")
    # exit discipline (EXP-0072 lesson)
    req("fflush(stdout) != 0 || ferror(stdout)" in hc and "STDOUT_FLUSH_FAIL" in hc
        and "single-threaded and synchronous" in h, "harness exit discipline")
    # frozen access idioms, one per width, plus the atomic stretch idiom
    for tok in ("*(device ushort *)p", "*(device uint *)p", "*(device ulong *)p",
                "*(device uint4 *)p", "*p = uchar(params[2]", "atomic_exchange_explicit"):
        req(tok in k, "kernel idiom " + tok)
    req("buf + params[0]" in k, "kernel runtime offset idiom")
    req(not re.search(r"precise|fast_|__|\bsimd\b", k), "forbidden kernel token")
    rp = (root / "run.py").read_text()
    req("fastMathEnabled=NO and mathMode=Safe" in rp and "--execute" in rp, "runner boundary")
    req('"--selftest"' in rp and "run gate failed" in rp, "runner selftest gate")
    req('"pre_capture_smoke"' in rp and "smoke.json" in rp and "raw.mkdir(parents=True)" in rp,
        "runner smoke gate and pre-capture raw ordering")
    req('"consecutive_infra_failures"' in rp, "runner infra stop")


def re_search(t, pat):  # kept for symmetry; callers use re.search directly
    return re.search(pat, t)


def prereg_checks(root=None):
    root = HERE if root is None else Path(root)
    t = (root / "PRE_REGISTRATION.md").read_text()
    for anchor in ("0xA5 + 0x1B", "0xC7 + j", "0x5A", "0xC3", "1088", "MEM-06", "MEM-07",
                   "MEM-08", "MEM-09", "MEM-10", "MEM-12"):
        req(anchor in t, "prereg anchor " + anchor)
    for nm in ("load_w32_align_in", "store_w128_straddle_15", "axch_w32_oob1",
               "load_w64_mishalf", "store_w1_last"):
        req(nm in t, "prereg case anchor " + nm)
    req("in-bounds" in t and "byte-identical" in t, "prereg repeat-policy anchor")
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
    for d, fs in (("kernels", {"robustness_matrix.metal"}), ("harness", {"probe.m"})):
        q = root / d
        req(q.is_dir() and not q.is_symlink() and {p.name for p in q.iterdir()} == fs
            and all(regular(x) for x in q.iterdir()), "closed " + d)
    contract_checks(json.loads((root / "CAPTURE_CONTRACT.json").read_text()), root)
    source_checks(root)
    prereg_checks(root)
    m = json.loads((root / "manifest.json").read_text())
    req(m == manifest_expected(capture, root), "manifest")


def check_case_line(q, rid):
    c = R.CASES[q["i"]]
    req(set(q) == CASE_KEYS, "case line keys %s[%d]: expected exactly %s, got %s"
        % (rid, q["i"], sorted(CASE_KEYS), sorted(set(q))))
    req(q["name"] == c["name"] and q["op"] == c["op"] and q["width"] == c["width"]
        and q["off"] == c["off"], "case line echo %s[%d]" % (rid, q["i"]))
    req(q["status"] in R.STATUS_VALUES, "case line status %s[%d]" % (rid, q["i"]))
    ol = R.obs_len(c["width"], c["op"])
    if q["status"] == "ok":
        req(q["exit"] == 0 and q["timed_out"] is False and q["cb_status"] == 4
            and q["err"] == "" and q["pre_ok"] is True
            and hexlike(q["obs"], ol) and hexlike(q["buf_after"], 128)
            and all(isinstance(q[k], bool) for k in ("g1_ok", "g2_ok", "res_g0_ok", "res_g1_ok")),
            "case line ok-shape %s[%d]" % (rid, q["i"]))
    elif q["status"] == "cb_error":
        req(q["exit"] == 0 and q["timed_out"] is False and isinstance(q["cb_status"], int)
            and q["cb_status"] != 4 and isinstance(q["err"], str)
            and hexlike(q["obs"], ol) and hexlike(q["buf_after"], 128)
            and all(isinstance(q[k], bool) for k in ("pre_ok", "g1_ok", "g2_ok", "res_g0_ok", "res_g1_ok")),
            "case line cb_error-shape %s[%d]" % (rid, q["i"]))
    elif q["status"] == "watchdog":
        req(q["exit"] in (97, 98) and q["timed_out"] is False and q["cb_status"] is None
            and q["err"] is None and q["obs"] == "" and q["buf_after"] == ""
            and all(q[k] is None for k in ("pre_ok", "g1_ok", "g2_ok", "res_g0_ok", "res_g1_ok")),
            "case line watchdog-shape %s[%d]" % (rid, q["i"]))
    elif q["status"] == "proc_timeout":
        req(q["exit"] is None and q["timed_out"] is True and q["cb_status"] is None
            and q["err"] is None and q["obs"] == "" and q["buf_after"] == ""
            and all(q[k] is None for k in ("pre_ok", "g1_ok", "g2_ok", "res_g0_ok", "res_g1_ok")),
            "case line timeout-shape %s[%d]" % (rid, q["i"]))
    else:  # proc_fail
        req(q["timed_out"] is False and isinstance(q["exit"], int) and q["exit"] != 0
            and q["exit"] not in (97, 98) and q["cb_status"] is None and q["err"] is None
            and q["obs"] == "" and q["buf_after"] == ""
            and all(q[k] is None for k in ("pre_ok", "g1_ok", "g2_ok", "res_g0_ok", "res_g1_ok")),
            "case line proc_fail-shape %s[%d]" % (rid, q["i"]))


def hexlike(s, n):
    return isinstance(s, str) and len(s) == n and all(ch in "0123456789abcdef" for ch in s)


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
        and i["geometry"] == GEOMETRY
        and set(i["authored_code_sha256"]) == set(AUTH_CODE)
        and set(i["authored_doc_sha256"]) == set(AUTH_DOC), "inputs schema " + rid)
    frozen = {**i["authored_doc_sha256"], **i["authored_code_sha256"]}
    req(frozen == json.loads((root / "CAPTURE_CONTRACT.json").read_text())["authored_sha256"],
        "inputs frozen-hash binding " + rid)
    for p, h in frozen.items():
        req(h == sha(root / p), "authored drift since capture " + rid + " " + p)
    req(subprocess.run(["git", "cat-file", "-e", i["git_revision"] + "^{commit}"],
                       cwd=REPO).returncode == 0, "revision object " + rid)
    record(i["sw_vers"], REC_KEYS, ["sw_vers"], root, TIMEOUTS["env_command"], "sw_vers " + rid)
    record(i["xcrun_version"], REC_KEYS, ["xcrun", "--version"], root,
           TIMEOUTS["env_command"], "xcrun " + rid)

    mx = json.loads((d / "01_matrix.json").read_text())
    req(mx["schema"] == 1 and mx["run_id"] == rid and set(mx) == {"schema", "run_id", "cases"}
        and mx["cases"] == R.CASES, "matrix echo " + rid)

    work = root / "work" / rid
    b = json.loads((d / "02_build.json").read_text())
    record(b, REC_KEYS, R.build_argv(work), root, TIMEOUTS["host_build"], "build " + rid)

    lines = (d / "04_results.jsonl").read_text().splitlines()
    req(len(lines) == R.TOTAL, "case line count " + rid)
    qs = []
    for idx, ln in enumerate(lines):
        q = json.loads(ln)
        check_case_line(q, rid)
        qs.append(q)

    rl = (d / "05_receipts.jsonl").read_text().splitlines()
    req(len(rl) == R.TOTAL, "receipt line count " + rid)
    for idx, ln in enumerate(rl):
        z = json.loads(ln)
        c = R.CASES[idx]
        req(set(z) == RECEIPT_LINE_KEYS and z["i"] == c["i"] and z["name"] == c["name"],
            "receipt line keys/echo %s[%d]" % (rid, idx))
        req(z["argv"] == [str(x) for x in R.case_argv(work, c)]
            and z["cwd"] == str(root) and z["timeout_seconds"] == TIMEOUTS["case_process"]
            and isinstance(z["stdout"], str) and isinstance(z["stderr"], str),
            "receipt content %s[%d]" % (rid, idx))
        req(z["exit"] == qs[idx]["exit"] and z["timed_out"] == qs[idx]["timed_out"],
            "receipt/case coupling %s[%d]" % (rid, idx))

    disp = json.loads((d / "03_dispatch.json").read_text())
    req(set(disp) == DISPATCH_KEYS and disp["schema"] == 1 and disp["run_id"] == rid
        and disp["cases_planned"] == R.TOTAL and disp["cases_recorded"] == len(lines)
        and disp["results_lines"] == len(lines)
        and all(disp["n_%s" % s] == sum(1 for q in qs if q["status"] == s)
                for s in R.STATUS_VALUES)
        and disp["results_sha256"] == sha(d / "04_results.jsonl"), "dispatch envelope " + rid)

    rm = json.loads((d / "06_run_manifest.json").read_text())
    req(rm == {"schema": 1, "run_id": rid, "cases_planned": R.TOTAL,
               "cases_recorded": len(lines), "runner_sha256": frozen["run.py"],
               "harness_sha256": frozen["harness/probe.m"],
               "kernel_sha256": frozen["kernels/robustness_matrix.metal"],
               "matrix_sha256": sha(d / "01_matrix.json"),
               "results_sha256": sha(d / "04_results.jsonl"),
               "receipts_sha256": sha(d / "05_receipts.jsonl")}, "run manifest " + rid)

    prov_out.append({"rid": rid, "git_revision": i["git_revision"], "git_dirty": i["git_dirty"],
                     "frozen": frozen, "lines": lines})


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
        for i in range(R.TOTAL):
            a, b = x["lines"][i], y["lines"][i]
            ja, jb = json.loads(a), json.loads(b)
            req(ja["status"] == jb["status"], "cross-run status differs at case %d" % i)
            if R.CASES[i]["cls"] in R.IN_BOUND_CLASSES:
                req(a == b, "in-bounds cases differ between runs at case %d" % i)


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
# Preflight self-test: synthetic captures driven through the real gates and the
# real record builder. No Metal, no device, no Apple binary, no network.
# ---------------------------------------------------------------------------
SELFTEST_DIR = "selftest"
_SYNTH_TS = "2026-08-27T00:00:00+00:00"


def _put(p, o):
    Path(p).write_text(json.dumps(o, indent=2, sort_keys=True) + "\n")


def _synth_record(argv, cwd, timeout, **extra):
    z = {"argv": [str(x) for x in argv], "cwd": str(cwd), "timeout_seconds": timeout,
         "started_utc": _SYNTH_TS, "timed_out": False, "exit": 0,
         "stdout": "", "stderr": "", "exception": None}
    z.update(extra)
    return z


def _fill_bytes():
    return bytes(R.fill(i) for i in range(64))


def _store_bytes():
    return bytes((0xC7 + j) & 0xFF for j in range(16))


def _synth_summary(c):
    """A clean, complete synthetic harness record for case c (expected-model values)."""
    import analysis as A
    if c["op"] == "store":
        obs = ""
        buf = A.expected_store_buffer(c["off"], c["width"]).hex()
    else:
        obs = A.expected_load(c["off"], c["width"]).hex()
        if len(obs) < 2 * max(4, c["width"]):
            obs = obs + "00" * (max(4, c["width"]) - c["width"])
        buf = _fill_bytes().hex()
    return {"schema": 1, "kernel": c["kernel"], "op": c["op"], "width": c["width"],
            "off": c["off"], "device": "Apple M4", "registry_id": 424242,
            "machine": "arm64", "os": "SYNTHETIC 26.6.2 (build 25G82)", "fast_math": False,
            "math_mode_raw": 0, "language_version_raw": 262144,
            "library_compile_seconds": 0.1, "dispatch_seconds": 0.01,
            "command_buffer_status": 4, "error": "", "obs": obs, "buf_after": buf,
            "pre_ok": True, "g1_ok": True, "g2_ok": True, "res_g0_ok": True, "res_g1_ok": True}


def _synth_receipt(c, root, rid, summary):
    return _synth_record(R.case_argv(root / "work" / rid, c), root,
                         TIMEOUTS["case_process"], stdout=json.dumps(summary, sort_keys=True))


def _copy_authored(dst):
    for p in AUTH_ALL + ("CAPTURE_CONTRACT.json", "RESULTS.md", "PROGRESS.md"):
        q = Path(dst) / p
        q.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(HERE / p, q)


def _build_tree(root, runs=RUNS, mutate=None, post_manifest=None, with_analysis=True,
                pre_gpu=False, corrupt_guard_case=None):
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
            "schema": 1, "git_revision": git("rev-parse", "HEAD").strip(),
            "git_dirty": git("status", "--porcelain").strip() != "",
            "experiment_tree_dirty_entries": 0,
            "authored_code_sha256": {p: frozen[p] for p in AUTH_CODE},
            "authored_doc_sha256": {p: frozen[p] for p in AUTH_DOC},
            "sw_vers": _synth_record(["sw_vers"], root, TIMEOUTS["env_command"]),
            "xcrun_version": _synth_record(["xcrun", "--version"], root,
                                           TIMEOUTS["env_command"]),
            "python": "synthetic", "machine": "arm64", "boundary": BOUNDARY,
            "timeouts_seconds": TIMEOUTS, "geometry": GEOMETRY})
        _put(d / "01_matrix.json", {"schema": 1, "run_id": rid, "cases": R.CASES})
        _put(d / "02_build.json",
             _synth_record(R.build_argv(work), root, TIMEOUTS["host_build"]))
        lines, receipts = [], []
        for c in R.CASES:
            s = _synth_summary(c)
            if corrupt_guard_case == c["name"] and c["op"] != "load":
                s["g1_ok"] = False          # a real observation: guard allocation corrupted
            z = _synth_receipt(c, root, rid, s)
            q = R.case_line(c, z)
            lines.append(json.dumps(q, sort_keys=True))
            receipts.append(json.dumps({"i": c["i"], "name": c["name"], **z}, sort_keys=True))
        (d / "04_results.jsonl").write_text("\n".join(lines) + "\n")
        (d / "05_receipts.jsonl").write_text("\n".join(receipts) + "\n")
        counts = {s: sum(1 for l in lines if json.loads(l)["status"] == s)
                  for s in R.STATUS_VALUES}
        _put(d / "03_dispatch.json", {
            "schema": 1, "run_id": rid, "cases_planned": R.TOTAL,
            "cases_recorded": len(lines), **{"n_%s" % s: counts[s] for s in R.STATUS_VALUES},
            "results_lines": len(lines),
            "results_sha256": sha(d / "04_results.jsonl")})
        _put(d / "06_run_manifest.json", {
            "schema": 1, "run_id": rid, "cases_planned": R.TOTAL,
            "cases_recorded": len(lines), "runner_sha256": frozen["run.py"],
            "harness_sha256": frozen["harness/probe.m"],
            "kernel_sha256": frozen["kernels/robustness_matrix.metal"],
            "matrix_sha256": sha(d / "01_matrix.json"),
            "results_sha256": sha(d / "04_results.jsonl"),
            "receipts_sha256": sha(d / "05_receipts.jsonl")})
    if with_analysis:
        (root / "analysis.json").write_text('{"synthetic": true}\n')
    if mutate is not None:
        mutate(root)
    _put(root / "manifest.json", manifest_expected(not pre_gpu, root))
    if post_manifest is not None:
        post_manifest(root)


def _load(root, kind, rid):
    rel = "raw/%s/%s" % (rid, {"results": "04_results.jsonl", "dispatch": "03_dispatch.json",
                               "matrix": "01_matrix.json", "receipts": "05_receipts.jsonl"}[kind])
    return rel, json.loads((Path(root) / rel).read_text())


def _load_lines(root, rid):
    p = Path(root) / "raw" / rid / "04_results.jsonl"
    return [json.loads(l) for l in p.read_text().splitlines()]


def _write_lines(root, rid, qs):
    p = Path(root) / "raw" / rid / "04_results.jsonl"
    p.write_text("\n".join(json.dumps(q, sort_keys=True) for q in qs) + "\n")
    return p


def _resync(root, rid):
    """Recompute dispatch envelope + run manifest hashes after a line mutation."""
    d = Path(root) / "raw" / rid
    disp = json.loads((d / "03_dispatch.json").read_text())
    counts = {s: sum(1 for l in _load_lines(root, rid) if l["status"] == s)
              for s in R.STATUS_VALUES}
    disp.update({"n_%s" % s: counts[s] for s in R.STATUS_VALUES})
    disp["results_sha256"] = sha(d / "04_results.jsonl")
    _put(d / "03_dispatch.json", disp)
    rm = json.loads((d / "06_run_manifest.json").read_text())
    rm["results_sha256"] = disp["results_sha256"]
    rm["receipts_sha256"] = sha(d / "05_receipts.jsonl")
    _put(d / "06_run_manifest.json", rm)


# --- mutation helpers: each one breaks exactly one frozen expectation --------
def m_case_line_overkeyed(root):
    qs = _load_lines(root, RUNS[0])
    qs[0]["unexpected"] = 1
    _write_lines(root, RUNS[0], qs)
    _resync(root, RUNS[0])


def m_case_line_underkeyed(root):
    qs = _load_lines(root, RUNS[0])
    del qs[0]["pre_ok"]
    _write_lines(root, RUNS[0], qs)
    _resync(root, RUNS[0])


def m_case_line_bad_status(root):
    qs = _load_lines(root, RUNS[0])
    qs[0]["status"] = "mystery"
    _write_lines(root, RUNS[0], qs)
    _resync(root, RUNS[0])


def m_case_line_bad_hex(root):
    qs = _load_lines(root, RUNS[0])
    qs[0]["buf_after"] = "zz" * 64
    _write_lines(root, RUNS[0], qs)
    _resync(root, RUNS[0])


def m_control_repeat_broken(root):
    qs = _load_lines(root, RUNS[1])
    qs[0]["obs"] = ("0" * len(qs[0]["obs"]))[:-1] + "1"
    _write_lines(root, RUNS[1], qs)
    _resync(root, RUNS[1])


def m_oob_status_differs(root):
    qs = _load_lines(root, RUNS[1])
    q = next(x for x in qs if x["name"] == "load_w32_oob1")
    q.update({"status": "proc_timeout", "exit": None, "timed_out": True, "cb_status": None,
              "err": None, "obs": "", "buf_after": "", "pre_ok": None, "g1_ok": None,
              "g2_ok": None, "res_g0_ok": None, "res_g1_ok": None})
    _write_lines(root, RUNS[1], qs)
    # keep the receipt coupled so the failure surfaces at the cross-run check
    rp = Path(root) / "raw" / RUNS[1] / "05_receipts.jsonl"
    rl = [json.loads(l) for l in rp.read_text().splitlines()]
    z = next(z for z in rl if z["name"] == "load_w32_oob1")
    z.update({"exit": None, "timed_out": True, "exception": "TimeoutExpired", "stdout": ""})
    rp.write_text("\n".join(json.dumps(x, sort_keys=True) for x in rl) + "\n")
    _resync(root, RUNS[1])


def m_matrix_echo_tampered(root):
    rel, mx = _load(root, "matrix", RUNS[0])
    mx["cases"][0]["off"] = 31
    _put(Path(root) / rel, mx)
    d = Path(root) / "raw" / RUNS[0]
    rm = json.loads((d / "06_run_manifest.json").read_text())
    rm["matrix_sha256"] = sha(d / "01_matrix.json")
    _put(d / "06_run_manifest.json", rm)


def m_dispatch_counts_wrong(root):
    rel, disp = _load(root, "dispatch", RUNS[0])
    disp["n_ok"] += 1
    _put(Path(root) / rel, disp)


def m_results_hash_mismatch(root):
    rel, disp = _load(root, "dispatch", RUNS[0])
    disp["results_sha256"] = "0" * 64
    _put(Path(root) / rel, disp)


def m_receipt_line_missing(root):
    p = Path(root) / "raw" / RUNS[0] / "05_receipts.jsonl"
    lines = p.read_text().splitlines()
    p.write_text("\n".join(lines[:-1]) + "\n")


def m_receipt_line_overkeyed(root):
    p = Path(root) / "raw" / RUNS[0] / "05_receipts.jsonl"
    lines = p.read_text().splitlines()
    z = json.loads(lines[0])
    z["extra"] = 1
    lines[0] = json.dumps(z, sort_keys=True)
    p.write_text("\n".join(lines) + "\n")


def m_raw_extra_file(root):
    (Path(root) / ("raw/%s/07_extra.json" % RUNS[0])).write_text("{}\n")


def m_kernel_drift(root):
    p = Path(root) / "kernels/robustness_matrix.metal"
    p.write_text(p.read_text() + "\n// drifted\n")


def m_manifest_stale(root):
    p = Path(root) / "PROGRESS.md"
    p.write_text(p.read_text() + "\n")


def m_run02_revision_differs(root):
    p = Path(root) / "raw" / RUNS[1] / "00_inputs.json"
    i = json.loads(p.read_text())
    i["git_revision"] = subprocess.run(["git", "rev-parse", "HEAD~1"], cwd=REPO, text=True,
                                       capture_output=True, check=True).stdout.strip()
    _put(p, i)


def selftest():
    scratch = HERE / SELFTEST_DIR
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    cases = []
    n_ok = 0
    try:
        def add(name, expect_pass, needle, builder):
            cases.append((name, expect_pass, needle, builder))

        def broken(name, needle, mutate, **kw):
            add(name, False, needle, lambda r: _build_tree(r, mutate=mutate, **kw))

        add("preflight_gate_satisfiable", True, None,
            lambda r: _build_tree(r, runs=(), with_analysis=False, pre_gpu=True))
        add("captured_gate_satisfiable", True, None, lambda r: _build_tree(r))
        add("between_runs_gate_satisfiable", True, None,
            lambda r: _build_tree(r, runs=(RUNS[0],), with_analysis=False))
        # a guard-corrupting OOB store observation is VALID evidence here
        add("guard_corrupt_oob_store_is_valid_evidence", True, None,
            lambda r: _build_tree(r, corrupt_guard_case="store_w32_oob1"))
        broken("case_line_overkeyed", "case line keys", m_case_line_overkeyed)
        broken("case_line_underkeyed", "case line keys", m_case_line_underkeyed)
        broken("case_line_bad_status", "case line status", m_case_line_bad_status)
        broken("case_line_bad_hex", "ok-shape", m_case_line_bad_hex)
        broken("control_repeat_broken", "in-bounds cases differ", m_control_repeat_broken)
        broken("oob_status_differs", "cross-run status", m_oob_status_differs)
        broken("matrix_echo_tampered", "matrix echo", m_matrix_echo_tampered)
        broken("dispatch_counts_wrong", "dispatch envelope", m_dispatch_counts_wrong)
        broken("results_hash_mismatch", "dispatch envelope", m_results_hash_mismatch)
        broken("receipt_line_missing", "receipt line count", m_receipt_line_missing)
        broken("receipt_line_overkeyed", "receipt line keys", m_receipt_line_overkeyed)
        broken("raw_extra_file", "closed raw", m_raw_extra_file)
        broken("authored_hash_drift", "authored hash", m_kernel_drift)
        broken("manifest_stale", "manifest", None, post_manifest=m_manifest_stale)
        broken("cross_run_revision_differs", "cross-run revision", m_run02_revision_differs)

        # smoke-validator purity: the EXP-0072 truncation class must be rejected
        smoke_case = next(c for c in R.CASES if c["name"] == R.SMOKE_CASE)

        def smoke_receipt(stdout):
            return _synth_record(R.case_argv(Path("/w"), smoke_case), "/w",
                                 TIMEOUTS["case_process"], stdout=stdout)

        smoke_checks = []

        def smoke(name, needle, z):
            probs = R.smoke_problems(z, smoke_case)
            good = (not probs) if needle is None else any(needle in p for p in probs)
            smoke_checks.append((name, good))

        smoke("smoke_clean_passes", None, smoke_receipt(json.dumps(_synth_summary(smoke_case),
                                                                   sort_keys=True)))
        smoke("smoke_truncated_rejected", "not exactly one JSON object",
              smoke_receipt(json.dumps(_synth_summary(smoke_case))[:120]))
        smoke("smoke_overkeyed_rejected", "key set differs",
              smoke_receipt(json.dumps({**_synth_summary(smoke_case), "x": 1}, sort_keys=True)))
        smoke("smoke_wrong_identity_rejected", "identity",
              smoke_receipt(json.dumps({**_synth_summary(smoke_case), "off": 31}, sort_keys=True)))
        smoke("smoke_nonzero_exit_rejected", "exit code",
              {**smoke_receipt(json.dumps(_synth_summary(smoke_case), sort_keys=True)),
               "exit": 4})
        smoke("smoke_guard_false_rejected", "integrity flags",
              smoke_receipt(json.dumps({**_synth_summary(smoke_case), "g1_ok": False},
                                       sort_keys=True)))

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
                        print("  case %-40s FAIL (gate raised: %s)" % (name, e))
                        continue
                else:
                    try:
                        gate_captured(root)
                    except SystemExit as e:
                        msg = str(e)
                        if needle is not None and needle not in msg:
                            print("  case %-40s FAIL (failed on %r, expected %r)"
                                  % (name, msg, needle))
                            continue
                    else:
                        print("  case %-40s FAIL (gate unexpectedly PASSED)" % name)
                        continue
            finally:
                shutil.rmtree(root, ignore_errors=True)
            n_ok += 1
            print("  case %-40s PASS" % name)
        for name, good in smoke_checks:
            if good:
                n_ok += 1
                print("  smoke %-39s PASS" % name)
            else:
                print("  smoke %-39s FAIL" % name)
        total = len(cases) + len(smoke_checks)
        print("SELFTEST %s %d/%d synthetic cases (no Metal, no device, no Apple binary)"
              % ("PASS" if n_ok == total else "FAIL", n_ok, total))
        if n_ok != total:
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
        print("PASS captured M4 buffer robustness matrix contract")


if __name__ == "__main__":
    main()
