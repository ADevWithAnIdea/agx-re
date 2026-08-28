#!/usr/bin/env python3
"""Fail-closed static and post-capture verifier for EXP-0078.

Schema discipline (lesson from quarantined EXP-0073): ONE record checker and
ONE frozen key set per record slot, imported from run.py -- the single source
of truth -- so the runner and the verifier cannot disagree. Extra keys and
missing keys both fail, everywhere, identically.

--selftest (REQUIRED before any capture; named in CAPTURE_CONTRACT.json) is
runnable in EVERY tree state (it works on synthetic roots only, never on the
real experiment root), so the EXP-0075 landmine class (a self-test that could
not run once raw/ existed) cannot recur. It proves, before any GPU work:

  1. every gate is satisfiable AND fails correctly, using synthetic captures
     driven through the same static()/captured() code paths used on real
     evidence -- including run.case_line, the exact record builder used at
     capture time, and run.case_argv receipt coupling against the run's own
     02_build identification record;
  2. the pre-capture smoke validator rejects the EXP-0072 truncation class
     and passes a clean record;
  3. a witness-corrupting or buffer-mutating OBSERVATION is valid evidence
     (those flags are results here, not gate failures);
  4. the GATE-SEQUENCE STATE MACHINE (the EXP-0075 fix, mandatory): one
     synthetic tree is walked through the contracted states PRE_GPU ->
     run01-present -> run02+analysis-present, and at each state every
     contracted gate is invoked: each must be runnable, must PASS where the
     contract invokes it, and must FAIL where the contract forbids it. A
     capture whose gate order is self-contradictory is therefore a
     pre-capture stop, not a post-capture discovery.
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
KERNEL_FILES = {"%s.metal" % k for k in R.KERNEL_NAMES}
HARNESS_FILES = {"probe.m", "build.sh"}

GATE_BETWEEN = ("run01 must be a complete closed raw tree (all 351 cases, consistent envelope, "
                "no STOP) and work absent or empty before run02 is created")
GATE_PROV = ("run02 current Git revision and authored hashes must equal the closed run01 input record")
GATE_REPEAT = ("every case must have identical status in both runs, and probe_word must be "
               "identical whenever either run's value is zero or pattern-decodable (the "
               "deterministic classes); only garbage-class values may differ and those are "
               "reported as the observed determinism answer, not gate-required")
GATE_SELFTEST = ("verify.py --selftest (runnable in every tree state, on synthetic roots only) "
                 "must pass immediately before every capture; a capture whose verifier gates "
                 "are unproven is not authorized")
GATE_SMOKE = ("before the append-only raw tree is created, the freshly built harness must run "
              "one scratch case (c31_load_slot_1) into work/ (never promoted into raw/), and "
              "its stdout must parse as one complete JSON record with every contracted field "
              "present and a consistent shape; any payload-shape or truncation defect is a "
              "pre-capture STOP")
GATE_FAULT = ("a faulted, hung, or killed case is a recorded result (status watchdog/proc_fail/"
              "proc_timeout) and is never retried in place; only 3 consecutive OS-level spawn "
              "failures stop the run")
GATE_IDENT = ("the probe instruction of every spliced kernel is located pre-capture from our own "
              "compiled bytes (differential compilation for the census kernels, unique-instruction "
              "decode for the store/atomic kernels) and the identification is recorded in "
              "02_build.json before any case runs")
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
    req(c["contract_version"] == 1 and c["experiment"] == "EXP-0078-m4-base-slot-census"
        and c["state"] == "PRE_GPU", "contract identity")
    req(c["target"] == "M4/G16G local host through public Metal only", "contract target")
    req(c["question"].startswith("MEM-15/MEM-16/MEM-17 device-buffer base-slot census"),
        "contract question")
    b = c["boundary"]
    req(b["apple_binary_or_archive_introspection"] == "NONE"
        and b["private_api_or_trace"] == "NONE"
        and b["accesses"] == "our own compiled kernel bytes with at most one spliced "
        "base-slot selector byte per case; one case per fresh process",
        "contract boundary")
    comp = c["compile"]
    req(comp["api"] == "newLibraryWithSource:options:" and comp["fast_math"] is True
        and comp["language_version"] == "not pinned; default read back and recorded verbatim",
        "contract compile")
    req(tuple(c["preflight_sequence"]) ==
        ("python3 -B verify.py --selftest", "python3 -B make_manifest.py --write",
         "python3 -B make_manifest.py --check", "python3 -B verify.py --preflight"),
        "contract preflight sequence")
    req(tuple(c["full_gate_sequence"]) == (
        "python3 -B verify.py --selftest",
        "python3 -B make_manifest.py --write", "python3 -B make_manifest.py --check",
        "python3 -B verify.py --preflight",
        "python3 -B run.py --execute --run-id m4-20260827-run01",
        "python3 -B make_manifest.py --write", "python3 -B make_manifest.py --check",
        "python3 -B verify.py --between-runs",
        "python3 -B verify.py --selftest",
        "python3 -B run.py --execute --run-id m4-20260827-run02",
        "python3 -B analysis.py --run-a m4-20260827-run01 --run-b m4-20260827-run02 --write",
        "python3 -B make_manifest.py --write", "python3 -B make_manifest.py --check",
        "python3 -B verify.py --captured"), "contract full gate sequence")
    req(c["geometry"] == GEOMETRY, "contract geometry")
    mx = c["matrix"]
    req(mx["total"] == R.TOTAL and mx["census31_slots"] == 256
        and mx["census4_slots"] == len(R.C4_SUBSET)
        and mx["mem17_slots"] == list(R.MEM17_SLOTS)
        and mx["cases"] == R.CASES, "contract matrix")
    req(tuple(c["required_authored_paths"]) == AUTH_ALL, "authored path set")
    req(c["authored_sha256"].keys() == set(AUTH_ALL), "authored hash set")
    for p, h in c["authored_sha256"].items():
        req(h == sha(root / p), "authored hash " + p)
    req(c["timeouts_seconds"] == TIMEOUTS, "timeouts")
    cp = c["capture"]
    req(tuple(cp["runs"]) == RUNS and set(cp["required_run_paths"]) == RAW_FILES
        and set(cp["receipt_keys"]) == R.REC_KEYS and set(cp["case_line_keys"]) == R.CASE_KEYS
        and set(cp["summary_keys"]) == R.SUMMARY_KEYS and set(cp["dispatch_keys"]) == R.DISPATCH_KEYS
        and set(cp["inputs_keys"]) == R.INPUTS_KEYS
        and set(cp["receipt_line_keys"]) == R.RECEIPT_LINE_KEYS
        and set(cp["run_manifest_keys"]) == R.RUN_MANIFEST_KEYS
        and set(cp["matrix_case_keys"]) == R.MATRIX_CASE_KEYS
        and set(cp["build_keys"]) == R.BUILD_KEYS
        and set(cp["kernel_rec_keys"]) == R.KERNEL_REC_KEYS
        and set(cp["ident_keys"]) == R.IDENT_KEYS
        and tuple(cp["status_values"]) == R.STATUS_VALUES
        and cp["extra_keys_policy"].startswith("Exact key-set equality for every record slot")
        and cp["case_fault_policy"] == GATE_FAULT
        and cp["consecutive_infra_stop"] == R.MAX_CONSECUTIVE_INFRA
        and cp["between_runs_gate"] == GATE_BETWEEN
        and cp["cross_run_provenance_gate"] == GATE_PROV
        and cp["cross_run_repeat_gate"] == GATE_REPEAT
        and cp["selftest_gate"] == GATE_SELFTEST and cp["smoke_gate"] == GATE_SMOKE
        and cp["identification_gate"] == GATE_IDENT
        and cp["failure_record"].startswith("Pre-capture failures retain work/<run-id>/STOP.json"),
        "capture contract")
    hyp = c["hypotheses"]
    req(hyp["H1_MEM15"].startswith("a kernel reading through all 31 MSL buffer indices")
        and hyp["H2_MEM16"].startswith("census31 slot k holds buffer k")
        and hyp["H3_MEM17_load"].startswith("slots outside the populated set read 0x00000000")
        and hyp["H4_MEM17_store"].startswith("a store through an unpopulated slot is discarded")
        and hyp["H5_MEM17_atomic"].startswith("an exchange through an unpopulated selector")
        and hyp["H6_control"].startswith("with only 4 buffers bound"),
        "hypotheses text")
    req(c["gate"].startswith("A missing path, hash, schema field, timeout record"), "gate text")


def strip_comments(t):
    return "\n".join(ln.split("//")[0] for ln in t.splitlines())


def source_checks(root=None):
    root = HERE if root is None else Path(root)
    h = (root / "harness/probe.m").read_text()
    hc = strip_comments(h)
    req("[opts setFastMathEnabled:YES]" in hc and "newLibraryWithSource:src options:opts" in hc,
        "precise compile options")
    req("[enc dispatchThreads:" in hc and "MTLResourceStorageModeShared" in hc,
        "dispatch shape")
    req("MTLPipelineOptionFailOnBinaryArchiveMiss" in hc, "archive-forced pipeline")
    req(not re.search(r"IOKit|objc_msgSend|MTLIO|otool|objdump", hc), "forbidden harness token")
    req("fflush(stdout) != 0 || ferror(stdout)" in hc and "STDOUT_FLUSH_FAIL" in hc
        and "single-threaded and synchronous" in h, "harness exit discipline")
    req("signal(SIGALRM, on_alarm)" in hc and "exit(97" not in hc, "harness watchdogs")
    kern_toks = {
        "census31.metal": ("out[0] = b1[i0];", "out[30] = i0;"),
        "census31_v2.metal": ("out[0] = b2[i0];",),
        "census4.metal": ("out[0] = b1[i0];", "gid & 0xF0u"),
        "census4_v2.metal": ("out[0] = b2[i0];", "gid & 0xF0u"),
        "capacity.metal": ("out[0] = b1[i0];", "out[30] = i0;"),
        "storeprobe.metal": ("tgt[i0] = 0x5A17C0DEu;",),
        "storeprobe_v2.metal": ("tgt[i0] = 0x5A17C0DEu;",),
        "atomicprobe.metal": ("atomic_exchange_explicit(&abuf[i0], 0x5A17C0DEu",),
        "atomicprobe_v2.metal": ("atomic_exchange_explicit(&abuf[i0], 0x5A17C0DEu",),
    }
    for name, toks in kern_toks.items():
        k = strip_comments((root / "kernels" / name).read_text())
        for tok in toks:
            req(tok in k, "kernel idiom %s: %s" % (name, tok))
        req(not re.search(r"precise|fast_|__", k), "forbidden kernel token in " + name)
    rp = (root / "run.py").read_text()
    req("fastMathEnabled=YES" in rp and "--execute" in rp, "runner boundary")
    req('"--selftest"' in rp and "run gate failed" in rp, "runner selftest gate")
    req('"pre_capture_smoke"' in rp and "smoke.json" in rp and "raw.mkdir(parents=True)" in rp,
        "runner smoke gate and pre-capture raw ordering")
    req('"consecutive_infra_failures"' in rp, "runner infra stop")
    req('"identify"' in rp and "diff_single_byte" in rp, "runner identification stage")


def prereg_checks(root=None):
    root = HERE if root is None else Path(root)
    t = (root / "PRE_REGISTRATION.md").read_text()
    for anchor in ("MEM-15", "MEM-16", "MEM-17", "0xC0DE0000", "0 and 30", "byte+5",
                   "c31_load_slot_0", "c31_load_slot_255", "c4_load_slot_128",
                   "capacity_baseline", "st_store_baseline", "st_store_slot_3",
                   "st_store_slot_255", "at_axch_baseline", "at_axch_sel_31",
                   "at_b4probe_255", "7/8", "15/16", "31/32", "63/64", "127/128", "255",
                   "uniform-register", "threadgroup", "reserved"):
        req(anchor in t, "prereg anchor " + anchor)
    req("Two fresh runs" in t and "identical status" in t, "prereg repeat-policy anchor")
    req("single authoritative" in t and "--selftest" in t, "prereg repair anchor")
    req("garbage" in t, "prereg garbage-class anchor")


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
    for d, fs in (("kernels", KERNEL_FILES), ("harness", HARNESS_FILES)):
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
    req(set(q) == R.CASE_KEYS, "case line keys %s[%d]: expected exactly %s, got %s"
        % (rid, q["i"], sorted(R.CASE_KEYS), sorted(set(q))))
    req(q["name"] == c["name"] and q["kernel"] == c["kernel"] and q["op"] == c["op"]
        and q["slot"] == c["slot"], "case line echo %s[%d]" % (rid, q["i"]))
    req(q["status"] in R.STATUS_VALUES, "case line status %s[%d]" % (rid, q["i"]))
    if q["status"] in ("ok", "cb_error"):
        req(q["exit"] == 0 and q["timed_out"] is False
        and isinstance(q["cb_status"], int) and (q["status"] == "ok") == (q["cb_status"] == 4)
            and isinstance(q["err"], str)
            and R._hex_ok(q["probe_word"], 8)
            and isinstance(q["witness_ok"], (bool, type(None)))
            and isinstance(q["changed"], list)
            and all(isinstance(x, int) and 1 <= x <= 30 for x in q["changed"]),
            "case line ok/cb_error-shape %s[%d]" % (rid, q["i"]))
    else:
        nones = q["cb_status"] is None and q["err"] is None and q["probe_word"] == "" \
            and q["witness_ok"] is None and q["changed"] == []
        if q["status"] == "watchdog":
            req(q["exit"] in (97, 98) and q["timed_out"] is False and nones,
                "case line watchdog-shape %s[%d]" % (rid, q["i"]))
        elif q["status"] == "proc_timeout":
            req(q["exit"] is None and q["timed_out"] is True and nones,
                "case line timeout-shape %s[%d]" % (rid, q["i"]))
        else:
            req(q["timed_out"] is False and isinstance(q["exit"], int) and q["exit"] != 0
                and q["exit"] not in (97, 98) and nones,
                "case line proc_fail-shape %s[%d]" % (rid, q["i"]))


def hexlike(s, n):
    return isinstance(s, str) and len(s) == n and all(ch in "0123456789abcdef" for ch in s)


def build_record_checks(b, root, rid):
    req(set(b) == R.BUILD_KEYS and b["schema"] == 1, "build record keys " + rid)
    record(b["build"], R.REC_KEYS, R.build_argv(Path(root) / "work" / rid), root,
           TIMEOUTS["host_build"], "build " + rid)
    req(set(b["tools_sha256"]) == {"tools/shdump/shdump.m", "tools/shdump/agxparse.py",
                                   "tools/agx-isa/isadb.py"}, "tools hash set " + rid)
    for p, h in b["tools_sha256"].items():
        req(h == sha(REPO / p), "tool hash drift " + p + " " + rid)
    req(set(b["kernels"]) == set(R.KERNEL_NAMES), "kernel record set " + rid)
    for k, kr in b["kernels"].items():
        req(set(kr) == R.KERNEL_REC_KEYS, "kernel record keys %s %s" % (rid, k))
        req(hexlike(kr["archive_sha256"], 64) and isinstance(kr["main_off"], int)
            and kr["main_off"] >= 0 and isinstance(kr["main_len"], int) and kr["main_len"] > 0
            and hexlike(kr["main_hex"], 2 * kr["main_len"]), "kernel record shape %s %s" % (rid, k))
    req(set(b["ident"]) == {"census31", "census4", "storeprobe", "atomicprobe"},
        "ident set " + rid)
    for k, ir in b["ident"].items():
        req(set(ir) == R.IDENT_KEYS, "ident keys %s %s" % (rid, k))
        kr = b["kernels"][k]
        main = bytes.fromhex(kr["main_hex"])
        req(ir["probe_main_off"] >= 0 and ir["probe_main_off"] + 14 <= kr["main_len"]
            and main[ir["probe_main_off"]] == 0x67, "ident probe opcode %s %s" % (rid, k))
        req(ir["abs_off"] == kr["main_off"] + ir["probe_main_off"] + ir["selector_rel"]
            and main[ir["probe_main_off"] + ir["selector_rel"]] == ir["orig_value"],
            "ident coupling %s %s" % (rid, k))
        req(hexlike(ir["insn_hex"], 28), "ident insn hex %s %s" % (rid, k))
    return b["ident"]


def one_run(rid, prov_out, root=None):
    root = HERE if root is None else Path(root)
    d = root / "raw" / rid
    req(d.is_dir() and not d.is_symlink(), "run dir " + rid)
    names = {p.name for p in d.iterdir()}
    req(names == RAW_FILES, "closed raw %s: %s" % (rid, sorted(names)))
    req(all(regular(p) for p in d.iterdir()), "regular raw " + rid)

    i = json.loads((d / "00_inputs.json").read_text())
    req(set(i) == R.INPUTS_KEYS and i["schema"] == 1 and i["machine"] == "arm64"
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
    record(i["sw_vers"], R.REC_KEYS, ["sw_vers"], root, TIMEOUTS["env_command"], "sw_vers " + rid)
    record(i["xcrun_version"], R.REC_KEYS, ["xcrun", "--version"], root,
           TIMEOUTS["env_command"], "xcrun " + rid)

    mx = json.loads((d / "01_matrix.json").read_text())
    req(mx["schema"] == 1 and mx["run_id"] == rid and set(mx) == {"schema", "run_id", "cases"}
        and mx["cases"] == R.CASES, "matrix echo " + rid)

    ident = build_record_checks(json.loads((d / "02_build.json").read_text()), root, rid)

    lines = (d / "04_results.jsonl").read_text().splitlines()
    req(len(lines) == R.TOTAL, "case line count " + rid)
    qs = []
    for idx, ln in enumerate(lines):
        q = json.loads(ln)
        check_case_line(q, rid)
        qs.append(q)

    rl = (d / "05_receipts.jsonl").read_text().splitlines()
    req(len(rl) == R.TOTAL, "receipt line count " + rid)
    work = root / "work" / rid
    for idx, ln in enumerate(rl):
        z = json.loads(ln)
        c = R.CASES[idx]
        req(set(z) == R.RECEIPT_LINE_KEYS and z["i"] == c["i"] and z["name"] == c["name"],
            "receipt line keys/echo %s[%d]" % (rid, idx))
        req(z["argv"] == [str(x) for x in R.case_argv(work, c, ident)]
            and z["cwd"] == str(root) and z["timeout_seconds"] == TIMEOUTS["case_process"]
            and isinstance(z["stdout"], str) and isinstance(z["stderr"], str),
            "receipt content %s[%d]" % (rid, idx))
        req(z["exit"] == qs[idx]["exit"] and z["timed_out"] == qs[idx]["timed_out"],
            "receipt/case coupling %s[%d]" % (rid, idx))

    disp = json.loads((d / "03_dispatch.json").read_text())
    req(set(disp) == R.DISPATCH_KEYS and disp["schema"] == 1 and disp["run_id"] == rid
        and disp["cases_planned"] == R.TOTAL and disp["cases_recorded"] == len(lines)
        and disp["results_lines"] == len(lines)
        and all(disp["n_%s" % s] == sum(1 for q in qs if q["status"] == s)
                for s in R.STATUS_VALUES)
        and disp["results_sha256"] == sha(d / "04_results.jsonl"), "dispatch envelope " + rid)

    rm = json.loads((d / "06_run_manifest.json").read_text())
    bld = json.loads((d / "02_build.json").read_text())
    req(set(rm) == R.RUN_MANIFEST_KEYS and rm["schema"] == 1 and rm["run_id"] == rid
        and rm["cases_planned"] == R.TOTAL and rm["cases_recorded"] == len(lines)
        and rm["runner_sha256"] == frozen["run.py"]
        and rm["harness_sha256"] == frozen["harness/probe.m"]
        and rm["kernel_sha256"] == {k: bld["kernels"][k]["archive_sha256"]
                                    for k in R.KERNEL_NAMES}
        and rm["matrix_sha256"] == sha(d / "01_matrix.json")
        and rm["build_sha256"] == sha(d / "02_build.json")
        and rm["results_sha256"] == sha(d / "04_results.jsonl")
        and rm["receipts_sha256"] == sha(d / "05_receipts.jsonl"), "run manifest " + rid)

    prov_out.append({"rid": rid, "git_revision": i["git_revision"], "git_dirty": i["git_dirty"],
                     "frozen": frozen, "qs": qs})


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
        problems = R.cross_run_problems(x["qs"], y["qs"])
        req(not problems, "cross-run repeat gate: %s" % json.dumps(problems[:4]))


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

SYNTH_MAIN = {"census31": (16752, 470), "census31_v2": (16752, 470),
              "census4": (7776, 84), "census4_v2": (7776, 84),
              "capacity": (17024, 560), "storeprobe": (16352, 508),
              "storeprobe_v2": (16000, 494), "atomicprobe": (16640, 864),
              "atomicprobe_v2": (16512, 850)}
SYNTH_IDENT = {
    "census31": {"method": "diff_single_byte", "probe_main_off": 426, "selector_rel": 4,
                 "orig_value": 1, "v2_value": 2, "byte4_value": 1,
                 "insn_hex": "67" + "00" * 13, "abs_off": 16752 + 426 + 4},
    "census4": {"method": "diff_single_byte", "probe_main_off": 52, "selector_rel": 4,
                "orig_value": 1, "v2_value": 2, "byte4_value": 1,
                "insn_hex": "67" + "00" * 13, "abs_off": 7776 + 52 + 4},
    "storeprobe": {"method": "decode_unique_nonout_store", "probe_main_off": 490,
                   "selector_rel": 4, "orig_value": 29, "v2_value": 28, "byte4_value": 29,
                   "insn_hex": "e7" + "00" * 13, "abs_off": 16352 + 490 + 4},
    "atomicprobe": {"method": "decode_unique_atomic", "probe_main_off": 824, "selector_rel": 5,
                    "orig_value": 29, "v2_value": 28, "byte4_value": 0,
                    "insn_hex": "67115400001d8080010200007c02", "abs_off": 16640 + 824 + 5},
}


def _put(p, o):
    Path(p).write_text(json.dumps(o, indent=2, sort_keys=True) + "\n")


def _synth_record(argv, cwd, timeout, **extra):
    z = {"argv": [str(x) for x in argv], "cwd": str(cwd), "timeout_seconds": timeout,
         "started_utc": _SYNTH_TS, "timed_out": False, "exit": 0,
         "stdout": "", "stderr": "", "exception": None}
    z.update(extra)
    return z


def _fill_hex(kernel):
    out = []
    for k in range(R.GEOMETRY["n_buffers"]):
        words = R.fill_words(kernel, k)
        if kernel == "storeprobe" and k == R.GEOMETRY["storeprobe_tgt_index"]:
            words = list(words)
            words[R.GEOMETRY["probe_element_index"]] = 0x5A17C0DE
        if kernel == "atomicprobe" and k == R.GEOMETRY["atomicprobe_abuf_index"]:
            words = list(words)
            words[R.GEOMETRY["probe_element_index"]] = 0x5A17C0DE
        out.append(b"".join(v.to_bytes(4, "little") for v in words).hex())
    return {str(k): out[k] for k in range(R.GEOMETRY["n_buffers"])}


def _synth_summary(c, witness_corrupt=False, force_probe=None):
    """A clean, complete synthetic harness record for case c (model values)."""
    kernel = c["kernel"]
    probe = force_probe
    if probe is None:
        if c["cls"] == "census31":
            probe = R.P(c["slot"], 5) if 1 <= c["slot"] <= 30 else (R.P(5, 0) if c["slot"] == 0 else 0)
        elif c["cls"] == "census4":
            probe = R.P(c["slot"], 5) if 1 <= c["slot"] <= 3 else 0
        elif c["cls"] == "capacity":
            probe = R.P(1, 5)
        elif c["cls"] == "store":
            probe = R.P(0, 0)
        else:
            probe = R.P(29, 5) if (not c["spliced"] or 1 <= c["slot"] <= 30) else 0
    words = [probe] + [R.fillword(kernel, k, 0) for k in range(1, 31)] \
        + [R.P(0, 31)]            # out word 31 is never written by any kernel
    if witness_corrupt:
        words[3] = 0xDEADBEEF
    out_hex = b"".join((w & 0xFFFFFFFF).to_bytes(4, "little") for w in words).hex()
    return {"schema": 1, "kernel": kernel, "op": c["op"], "slot": c["slot"],
            "splice_abs_off": SYNTH_IDENT[kernel]["abs_off"] if c["spliced"] else -1,
            "idxbuf": R.idxbuf_index(kernel), "device": "Apple M4", "registry_id": 424242,
            "machine": "arm64", "os": "SYNTHETIC 26.6.2 (build 25G82)", "fast_math": True,
            "math_mode_raw": 0, "language_version_raw": 262144,
            "library_compile_seconds": 0.1, "dispatch_seconds": 0.01,
            "command_buffer_status": 4, "error": "", "pre_ok": True,
            "out_hex": out_hex, "bufs_hex": _fill_hex(kernel)}


def _synth_receipt(c, root, rid, summary):
    return _synth_record(R.case_argv(Path(root) / "work" / rid, c, SYNTH_IDENT), root,
                         TIMEOUTS["case_process"], stdout=json.dumps(summary, sort_keys=True))


def _copy_authored(dst):
    for p in AUTH_ALL + ("CAPTURE_CONTRACT.json", "RESULTS.md", "PROGRESS.md"):
        q = Path(dst) / p
        q.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(HERE / p, q)


def _build_kernel_records():
    kernels = {}
    for k, (off, ln) in SYNTH_MAIN.items():
        main = bytearray(ln)
        kernels[k] = {"archive_sha256": "0" * 64, "main_off": off, "main_len": ln,
                      "main_hex": main.hex()}
    for k, ir in SYNTH_IDENT.items():
        m = bytearray.fromhex(kernels[k]["main_hex"])
        m[ir["probe_main_off"]] = 0x67
        m[ir["probe_main_off"] + ir["selector_rel"]] = ir["orig_value"]
        m[ir["probe_main_off"] + 4] = ir["byte4_value"]
        kernels[k]["main_hex"] = bytes(m).hex()
    return kernels


def _make_run_dir(root, rid, mutate_case=None):
    root = Path(root)
    d = root / "raw" / rid
    d.mkdir(parents=True)
    git = lambda *a: subprocess.run(["git", *a], cwd=REPO, text=True,
                                    capture_output=True, check=True).stdout
    frozen = {p: sha(HERE / p) for p in AUTH_ALL}
    _put(d / "00_inputs.json", {
        "schema": 1, "git_revision": git("rev-parse", "HEAD").strip(),
        "git_dirty": git("status", "--porcelain").strip() != "",
        "experiment_tree_dirty_entries": 0,
        "authored_code_sha256": {p: frozen[p] for p in AUTH_CODE},
        "authored_doc_sha256": {p: frozen[p] for p in AUTH_DOC},
        "sw_vers": _synth_record(["sw_vers"], root, TIMEOUTS["env_command"]),
        "xcrun_version": _synth_record(["xcrun", "--version"], root, TIMEOUTS["env_command"]),
        "python": "synthetic", "machine": "arm64", "boundary": BOUNDARY,
        "timeouts_seconds": TIMEOUTS, "geometry": GEOMETRY})
    _put(d / "01_matrix.json", {"schema": 1, "run_id": rid, "cases": R.CASES})
    _put(d / "02_build.json", {
        "schema": 1,
        "build": _synth_record(R.build_argv(root / "work" / rid), root, TIMEOUTS["host_build"]),
        "tools_sha256": {"tools/shdump/shdump.m": sha(REPO / "tools/shdump/shdump.m"),
                         "tools/shdump/agxparse.py": sha(REPO / "tools/shdump/agxparse.py"),
                         "tools/agx-isa/isadb.py": sha(REPO / "tools/agx-isa/isadb.py")},
        "kernels": _build_kernel_records(), "ident": SYNTH_IDENT})
    lines, receipts = [], []
    for c in R.CASES:
        s = _synth_summary(c)
        if mutate_case is not None and mutate_case.get("name") == c["name"]:
            s.update(mutate_case.get("patch", {}))
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
        "results_lines": len(lines), "results_sha256": sha(d / "04_results.jsonl")})
    _put(d / "06_run_manifest.json", {
        "schema": 1, "run_id": rid, "cases_planned": R.TOTAL,
        "cases_recorded": len(lines), "runner_sha256": frozen["run.py"],
        "harness_sha256": frozen["harness/probe.m"],
        "kernel_sha256": {k: _build_kernel_records()[k]["archive_sha256"] for k in R.KERNEL_NAMES},
        "matrix_sha256": sha(d / "01_matrix.json"),
        "build_sha256": sha(d / "02_build.json"),
        "results_sha256": sha(d / "04_results.jsonl"),
        "receipts_sha256": sha(d / "05_receipts.jsonl")})


def _build_tree(root, runs=RUNS, pre_gpu=False, with_analysis=True, mutate=None,
                post_manifest=None, run01_mutate_case=None, run02_mutate_case=None):
    root = Path(root)
    root.mkdir(parents=True)
    _copy_authored(root)
    if not pre_gpu:
        if "run01" in runs or RUNS[0] in runs:
            _make_run_dir(root, RUNS[0], mutate_case=run01_mutate_case)
        if "run02" in runs or RUNS[1] in runs:
            _make_run_dir(root, RUNS[1], mutate_case=run02_mutate_case)
    if with_analysis and not pre_gpu and len(runs) == 2:
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
    qs = _load_lines(root, RUNS[0]); qs[0]["unexpected"] = 1
    _write_lines(root, RUNS[0], qs); _resync(root, RUNS[0])


def m_case_line_underkeyed(root):
    qs = _load_lines(root, RUNS[0]); del qs[0]["witness_ok"]
    _write_lines(root, RUNS[0], qs); _resync(root, RUNS[0])


def m_case_line_bad_status(root):
    qs = _load_lines(root, RUNS[0]); qs[0]["status"] = "mystery"
    _write_lines(root, RUNS[0], qs); _resync(root, RUNS[0])


def m_case_line_bad_hex(root):
    qs = _load_lines(root, RUNS[0]); qs[0]["probe_word"] = "zz"
    _write_lines(root, RUNS[0], qs); _resync(root, RUNS[0])


def m_ident_decoupled(root):
    b = json.loads((Path(root) / "raw" / RUNS[0] / "02_build.json").read_text())
    b["ident"]["census31"]["orig_value"] = 9
    _put(Path(root) / "raw" / RUNS[0] / "02_build.json", b)
    d = Path(root) / "raw" / RUNS[0]
    rm = json.loads((d / "06_run_manifest.json").read_text())
    rm["build_sha256"] = sha(d / "02_build.json")
    _put(d / "06_run_manifest.json", rm)


def m_repeat_deterministic_value_differs(root):
    qs = _load_lines(root, RUNS[1])
    q = next(x for x in qs if x["name"] == "c31_load_slot_5")
    # a DIFFERENT but still pattern-decodable value: P(5,4) instead of P(5,5)
    q["probe_word"] = R.probe_word_hex(R.P(5, 4))
    _write_lines(root, RUNS[1], qs); _resync(root, RUNS[1])


def m_repeat_status_differs(root):
    qs = _load_lines(root, RUNS[1])
    q = next(x for x in qs if x["name"] == "c31_load_slot_200")
    q.update({"status": "proc_timeout", "exit": None, "timed_out": True, "cb_status": None,
              "err": None, "probe_word": "", "witness_ok": None, "changed": []})
    _write_lines(root, RUNS[1], qs)
    rp = Path(root) / "raw" / RUNS[1] / "05_receipts.jsonl"
    rl = [json.loads(l) for l in rp.read_text().splitlines()]
    z = next(z for z in rl if z["name"] == "c31_load_slot_200")
    z.update({"exit": None, "timed_out": True, "exception": "TimeoutExpired", "stdout": ""})
    rp.write_text("\n".join(json.dumps(x, sort_keys=True) for x in rl) + "\n")
    _resync(root, RUNS[1])


def m_matrix_echo_tampered(root):
    rel, mx = _load(root, "matrix", RUNS[0])
    mx["cases"][0]["slot"] = 99
    _put(Path(root) / rel, mx)
    d = Path(root) / "raw" / RUNS[0]
    rm = json.loads((d / "06_run_manifest.json").read_text())
    rm["matrix_sha256"] = sha(d / "01_matrix.json")
    _put(d / "06_run_manifest.json", rm)


def m_dispatch_counts_wrong(root):
    rel, disp = _load(root, "dispatch", RUNS[0]); disp["n_ok"] += 1
    _put(Path(root) / rel, disp)


def m_receipt_line_missing(root):
    p = Path(root) / "raw" / RUNS[0] / "05_receipts.jsonl"
    lines = p.read_text().splitlines()
    p.write_text("\n".join(lines[:-1]) + "\n")


def m_raw_extra_file(root):
    (Path(root) / ("raw/%s/07_extra.json" % RUNS[0])).write_text("{}\n")


def m_kernel_drift(root):
    p = Path(root) / "kernels/census31.metal"
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
    n_ok = 0
    try:
        cases = []

        def add(name, expect_pass, needle, builder):
            cases.append((name, expect_pass, needle, builder))

        def broken(name, needle, mutate, **kw):
            add(name, False, needle, lambda r: _build_tree(r, mutate=mutate, **kw))

        # ---- part 1: schema gates satisfiable + fail-correct ----------------
        add("preflight_gate_satisfiable", True, None,
            lambda r: _build_tree(r, runs=(), with_analysis=False, pre_gpu=True))
        add("captured_gate_satisfiable", True, None, lambda r: _build_tree(r))
        add("between_runs_gate_satisfiable", True, None,
            lambda r: _build_tree(r, runs=(RUNS[0],), with_analysis=False))
        # a witness-corrupting observation is VALID evidence here: the harness
        # record stays well-formed, the witness words just disagree with the
        # model -- exactly the class of result this census must admit.
        def _corrupt_witness(root):
            case = R.BY_NAME["c31_load_slot_40"]
            s = _synth_summary(case)
            ws = [int.from_bytes(bytes.fromhex(s["out_hex"][8 * i:8 * i + 8]), "little")
                  for i in range(len(s["out_hex"]) // 8)]
            ws[3] = 0xDEADBEEF
            s["out_hex"] = b"".join((w & 0xFFFFFFFF).to_bytes(4, "little")
                                    for w in ws).hex()
            _build_tree(root, run01_mutate_case={"name": "c31_load_slot_40",
                                                 "patch": {"out_hex": s["out_hex"]}})

        add("witness_corrupt_case_is_valid_evidence", True, None, _corrupt_witness)
        # a garbage-class value difference is REPORTED, not gate-required
        def _garbage_differ(root):
            qs = _load_lines(root, RUNS[1])
            q = next(x for x in qs if x["name"] == "c31_load_slot_200")
            q["probe_word"] = "12345678"
            _write_lines(root, RUNS[1], qs)
            _resync(root, RUNS[1])

        add("repeat_garbage_differ_is_reported_not_gated", True, None,
            lambda r: _build_tree(r, mutate=_garbage_differ))
        broken("case_line_overkeyed", "case line keys", m_case_line_overkeyed)
        broken("case_line_underkeyed", "case line keys", m_case_line_underkeyed)
        broken("case_line_bad_status", "case line status", m_case_line_bad_status)
        broken("case_line_bad_hex", "ok/cb_error-shape", m_case_line_bad_hex)
        broken("ident_decoupled_from_main_bytes", "ident coupling", m_ident_decoupled)
        broken("repeat_deterministic_value_differs", "cross-run repeat gate",
               m_repeat_deterministic_value_differs)
        broken("repeat_status_differs", "cross-run repeat gate", m_repeat_status_differs)
        broken("matrix_echo_tampered", "matrix echo", m_matrix_echo_tampered)
        broken("dispatch_counts_wrong", "dispatch envelope", m_dispatch_counts_wrong)
        broken("receipt_line_missing", "receipt line count", m_receipt_line_missing)
        broken("raw_extra_file", "closed raw", m_raw_extra_file)
        broken("authored_hash_drift", "authored hash", m_kernel_drift)
        broken("manifest_stale", "manifest", None, post_manifest=m_manifest_stale)
        broken("cross_run_revision_differs", "cross-run revision", m_run02_revision_differs)

        # ---- part 2: smoke-validator purity (EXP-0072 truncation class) -----
        smoke_case = R.BY_NAME[R.SMOKE_CASE]

        def smoke_receipt(stdout):
            return _synth_record(R.case_argv(Path("/w"), smoke_case, SYNTH_IDENT), "/w",
                                 TIMEOUTS["case_process"], stdout=stdout)

        smoke_checks = []

        def smoke(name, needle, z):
            probs = R.smoke_problems(z, smoke_case)
            good = (not probs) if needle is None else any(needle in p for p in probs)
            smoke_checks.append((name, good))

        smoke("smoke_clean_passes", None,
              smoke_receipt(json.dumps(_synth_summary(smoke_case), sort_keys=True)))
        smoke("smoke_truncated_rejected", "not exactly one JSON object",
              smoke_receipt(json.dumps(_synth_summary(smoke_case))[:120]))
        smoke("smoke_overkeyed_rejected", "key set differs",
              smoke_receipt(json.dumps({**_synth_summary(smoke_case), "x": 1}, sort_keys=True)))
        smoke("smoke_wrong_identity_rejected", "identity",
              smoke_receipt(json.dumps({**_synth_summary(smoke_case), "slot": 7}, sort_keys=True)))
        smoke("smoke_nonzero_exit_rejected", "exit code",
              {**smoke_receipt(json.dumps(_synth_summary(smoke_case), sort_keys=True)), "exit": 4})
        smoke("smoke_pre_ok_false_rejected", "upload integrity",
              smoke_receipt(json.dumps({**_synth_summary(smoke_case), "pre_ok": False},
                                       sort_keys=True)))

        # ---- part 3: GATE-SEQUENCE STATE MACHINE (the EXP-0075 fix) ---------
        # One synthetic root is walked through the contracted states; at each
        # state every gate is invoked. PASS where the contract invokes it,
        # FAIL where the contract forbids it.
        seq_root = scratch / "gate_sequence_walk"

        def expect(name, fn, should_pass, needle=None):
            try:
                fn()
            except SystemExit as e:
                ok = (not should_pass) and (needle is None or needle in str(e))
                return (name, ok, None if ok else "raised %s (wanted pass=%s needle=%r)"
                        % (e, should_pass, needle))
            except Exception as e:      # noqa: BLE001
                return (name, False, "unexpected exception %r" % (e,))
            return (name, should_pass, None if should_pass
                    else "gate PASSED where the contract requires FAIL")

        seq = []
        # State A: PRE_GPU (no raw)
        _build_tree(seq_root, runs=(), with_analysis=False, pre_gpu=True)
        seq.append(expect("A: preflight PASS", lambda: gate_preflight(seq_root), True))
        seq.append(expect("A: manifest matches", lambda: req(
            json.loads((seq_root / "manifest.json").read_text())
            == manifest_expected(False, seq_root), "manifest"), True))
        seq.append(expect("A: between-runs FAIL (no raw)", lambda: gate_between(seq_root),
                          False, "closed root"))
        seq.append(expect("A: captured FAIL (no raw)", lambda: gate_captured(seq_root),
                          False, "closed root"))
        # State B: run01 present, run02 absent (the manifest is regenerated
        # after run01, per the contracted between-runs sequence)
        _make_run_dir(seq_root, RUNS[0])
        _put(seq_root / "manifest.json", manifest_expected(True, seq_root))
        seq.append(expect("B: between-runs PASS", lambda: gate_between(seq_root), True))
        seq.append(expect("B: preflight FAIL (raw exists)", lambda: gate_preflight(seq_root),
                          False, "closed root"))
        seq.append(expect("B: captured FAIL (one run)", lambda: gate_captured(seq_root),
                          False, "closed root"))
        # State C: both runs + analysis
        _make_run_dir(seq_root, RUNS[1])
        (seq_root / "analysis.json").write_text('{"synthetic": true}\n')
        _put(seq_root / "manifest.json", manifest_expected(True, seq_root))
        seq.append(expect("C: captured PASS", lambda: gate_captured(seq_root), True))
        seq.append(expect("C: between-runs FAIL (analysis present)", lambda: gate_between(seq_root),
                          False, "closed root"))
        seq.append(expect("C: preflight FAIL (raw exists)", lambda: gate_preflight(seq_root),
                          False, "closed root"))
        seq.append(expect("C: manifest regen matches", lambda: req(
            json.loads((seq_root / "manifest.json").read_text())
            == manifest_expected(True, seq_root), "manifest"), True))

        # ---- run everything --------------------------------------------------
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
                        print("  case %-46s FAIL (gate raised: %s)" % (name, e))
                        continue
                else:
                    try:
                        gate_captured(root)
                    except SystemExit as e:
                        msg = str(e)
                        if needle is not None and needle not in msg:
                            print("  case %-46s FAIL (failed on %r, expected %r)"
                                  % (name, msg, needle))
                            continue
                    else:
                        print("  case %-46s FAIL (gate unexpectedly PASSED)" % name)
                        continue
            finally:
                shutil.rmtree(root, ignore_errors=True)
            n_ok += 1
            print("  case %-46s PASS" % name)
        for name, good in smoke_checks:
            if good:
                n_ok += 1
                print("  smoke %-45s PASS" % name)
            else:
                print("  smoke %-45s FAIL" % name)
        for (name, ok, why) in seq:
            if ok:
                n_ok += 1
                print("  gate-seq %-41s PASS" % name)
            else:
                print("  gate-seq %-41s FAIL (%s)" % (name, why))
        total = len(cases) + len(smoke_checks) + len(seq)
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
        print("PASS captured M4 base-slot census contract")


if __name__ == "__main__":
    main()
