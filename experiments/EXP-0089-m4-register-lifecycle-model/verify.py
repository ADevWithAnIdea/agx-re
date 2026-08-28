#!/usr/bin/env python3
"""Fail-closed static and post-capture verifier for EXP-0089.

One record checker, one frozen key set per record slot, imported from run.py
(never restated here) -- the EXP-0073 quarantine-class defect. Extra keys and
missing keys both fail, everywhere, identically.

Two self-tests, both REQUIRED before any capture and both runnable in EVERY
tree state (they operate only on synthetic scratch copies under selftest/,
never on the real raw/ -- the EXP-0075 quarantine class):

  --selftest  fabricates complete synthetic captures (no Metal, no device, no
              Apple binary) and drives them through the same static()/captured()
              code paths used on real evidence, including the cross-run
              comparison; proves clean shapes pass and each broken shape fails
              for the right reason. Explicitly proves the NO-NONDETERMINISM
              distinction (gate class d): two synthetic runs whose GATED
              04_results.jsonl are byte-identical but whose NON-GATED
              04_results_raw.jsonl differ only in timing/duration PASS the
              cross-run gate; a run whose GATED file differs semantically
              FAILS it. ALSO proves a second, EXP-0089-specific lesson (see
              ../SUBAGENT_BRIEF.md, "Pin the revision at pre-registration; do
              not gate on live HEAD"): two runs whose live `git_revision`
              differs (because the orchestrator committed OTHER experiments'
              work between run01 and run02) but whose AUTHORED SOURCE HASHES
              match still PASS the cross-run gate -- git_revision is
              informational only, never gated.
  --seqtest   walks the contracted gate ORDER through synthetic states
              (PRE_GPU -> RUN01_PRESENT -> RUN02_PRESENT) and proves every gate
              is runnable and satisfiable in the exact state the contract
              invokes it, and that every gate FAILS in the states where the
              contract does not invoke it.
"""
import argparse, datetime, hashlib, json, re, shutil, subprocess, sys
from pathlib import Path

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
import run as R           # noqa: E402  (schema constants + splice builder)
import casematrix as CM   # noqa: E402

RUNS = R.RUNS
BOUNDARY = R.BOUNDARY
TIMEOUTS = R.TIMEOUTS
AUTH_CODE = R.AUTH_CODE
AUTH_DOC = R.AUTH_DOC
AUTH_ALL = AUTH_DOC + AUTH_CODE
REC_KEYS = R.REC_KEYS
DISPATCH_KEYS = R.DISPATCH_KEYS
CASE_KEYS = R.CASE_KEYS
CASE_RAW_KEYS = R.CASE_RAW_KEYS
TOTAL = len(CM.full_case_list())

ROOT_FILES = {"CAPTURE_CONTRACT.json", "PRE_REGISTRATION.md", "README.md",
              "RESULTS.md", "PROGRESS.md", "kernels", "harness", "baseline.py",
              "casematrix.py", "run.py", "analysis.py", "make_manifest.py",
              "verify.py", "manifest.json"}
KERNEL_FILES = {f"{k}.metal" for k in CM.KERNELS}
HARNESS_FILES = {"build.sh"}
RAW_FILES = {"00_inputs.json", "01_cases.json", "02_build.json", "03_dispatch.json",
             "04_results.jsonl", "04_results_raw.jsonl", "05_run_manifest.json"}
INPUTS_KEYS = {"schema", "git_revision", "git_dirty", "experiment_tree_dirty_entries",
               "authored_code_sha256", "authored_doc_sha256", "sw_vers", "xcrun_version",
               "python", "machine", "boundary", "timeouts_seconds", "repeat_n", "tol_rel"}
BUILD_KEYS = {"schema", "harness_build", "baseline"}
STATUS_ALLOWED = {"OK", "COMPILE_FAIL", "FUNCTION_MISSING", "ARCHIVE_FAIL",
                  "PIPELINE_MISS", "PIPELINE_FAIL", "CMDBUF_ERROR", "HANG",
                  "NO_STATUS", "EXTRACT_FAIL"}
VERDICT_ALLOWED = {"MATCH_EXPECTED", "MISMATCH_EXPECTED", "FAULT"}
# fields that MUST NEVER appear in the gated (cross-run byte-compared) record
NONDET_FORBIDDEN = {"duration_ms", "duration_seconds_case", "pid", "address", "timestamp",
                    "started_utc_case", "gputime_ns"}


def fail(s):
    raise SystemExit("FAIL " + s)


def req(v, s):
    if not v:
        fail(s)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def regular(p):
    return Path(p).is_file() and not Path(p).is_symlink()


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


def record_interp(z, keys, argv_tail, cwd, timeout, label):
    req(set(z) == keys, "record keys %s: expected exactly %s, got %s"
        % (label, sorted(keys), sorted(set(z))))
    req(len(z["argv"]) == len(argv_tail) + 1
        and z["argv"][1:] == [str(x) for x in argv_tail]
        and ("python" in Path(z["argv"][0]).name)
        and z["cwd"] == str(cwd) and z["timeout_seconds"] == timeout
        and z["timed_out"] is False and z["exit"] == 0 and z["exception"] is None,
        "record content " + label)


def manifest_expected(capture, root=None):
    import make_manifest as MM
    old = MM.HERE
    MM.HERE = Path(root) if root is not None else HERE
    try:
        exp = MM.expected(capture)
    finally:
        MM.HERE = old
    return exp


def contract_checks(c, root=None):
    root = HERE if root is None else Path(root)
    req(c["contract_version"] == 1 and c["experiment"] == "EXP-0089-m4-register-lifecycle-model"
        and c["state"] == "PRE_GPU", "contract identity")
    req(c["target"] == "M4/G16G local host through public Metal only", "contract target")
    req(tuple(c["required_authored_paths"]) == AUTH_ALL, "authored path set")
    req(c["authored_sha256"].keys() == set(AUTH_ALL), "authored hash set")
    for p, h in c["authored_sha256"].items():
        req(h == sha(root / p), "authored hash " + p)
    req(c["timeouts_seconds"] == TIMEOUTS, "timeouts")
    cp = c["capture"]
    req(tuple(cp["runs"]) == RUNS and set(cp["required_run_paths"]) == RAW_FILES
        and set(cp["gated_case_keys"]) == CASE_KEYS
        and set(cp["nongated_case_keys"]) == CASE_RAW_KEYS
        and cp["total_cases"] == TOTAL
        and cp["status_allowed"] == sorted(STATUS_ALLOWED)
        and cp["verdict_allowed"] == sorted(VERDICT_ALLOWED), "capture contract")


def source_checks(root=None):
    root = HERE if root is None else Path(root)
    rp = (root / "run.py").read_text()
    req("--execute" in rp and "no capture is authorized" in rp, "runner execute gate")
    req('"--selftest"' in rp and '"--seqtest"' in rp and "verify.py %s failed" in rp,
        "runner selftest+seqtest gate before every capture")
    req('"--preflight" if a.run_id == RUNS[0] else "--between-runs"' in rp,
        "runner state gate selection")
    req("smoke_gate" in rp and "SMOKE_CASE" in rp, "runner smoke gate")
    req(rp.index("NON-RECORDED smoke gate") < rp.index("raw.mkdir(parents=True)"),
        "runner smoke gate runs BEFORE any raw artifact")
    req("import threading" not in rp and "Thread(" not in rp and "multiprocessing" not in rp,
        "runner single-threaded discipline")
    req("rf.flush()" in rp and "rrf.flush()" in rp, "runner per-case flush discipline (both streams)")
    req("REPO / \"tools\" / \"agxtest\" / \"agxtest.py\"" in rp, "runner uses read-only agxtest")
    req('"duration_ms"' not in rp.split("CASE_KEYS = {")[1].split("}")[0], "no timing leak into CASE_KEYS literal")
    for f in NONDET_FORBIDDEN:
        req(('"%s"' % f) not in [k.strip().strip('"') for k in
            re.findall(r'"[a-z_]+"', rp.split("CASE_KEYS = {")[1].split("}")[0] + "}")],
            "gated key set excludes " + f)
    req("live git HEAD is explicitly" in rp or "NOT required to be unchanged" in rp,
        "runner documents the pinned-revision/live-HEAD distinction")
    cm = (root / "casematrix.py").read_text()
    req("REPEAT_N = 3" in cm, "repeat count anchor")
    bp = (root / "baseline.py").read_text()
    req("frozen_anchor_diffs" in bp and "sys.exit(3)" in bp, "baseline stop discipline")
    hs = (root / "harness" / "build.sh").read_text()
    req("tools/shdump/shdump.m" in hs and "tools/agxtest/agxrun.m" in hs,
        "harness builds tool sources")


def prereg_checks(root=None):
    root = HERE if root is None else Path(root)
    t = (root / "PRE_REGISTRATION.md").read_text()
    req(str(TOTAL) in t, "prereg total case count anchor")
    req("--seqtest" in t and "--selftest" in t, "prereg gate anchors")
    for kernel in CM.KERNELS:
        req(kernel in t, "prereg kernel anchor " + kernel)
    req("0x40" in t, "prereg CAND_A bit anchor")
    req("0x02" in t, "prereg literal-bit-17 anchor")


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


def case_line_checks(line, i, c):
    req(set(line) == CASE_KEYS, "case line keys %d: expected exactly %s, got %s"
        % (i, sorted(CASE_KEYS), sorted(set(line))))
    req(line["i"] == i and line["kernel"] == c["kernel"] and line["case_name"] == c["name"]
        and line["item"] == c["item"] and line["rep"] == c["rep"], "case echo %d" % i)
    req(line["status"] in STATUS_ALLOWED, "case status %d" % i)
    req(line["verdict"] in VERDICT_ALLOWED, "case verdict %d" % i)
    if line["status"] == "OK":
        req(line["pipeline_source"] == "archive", "case ok-shape %d" % i)
    for f in NONDET_FORBIDDEN:
        req(f not in line, "gated line %d leaks nondeterministic field %s" % (i, f))


def raw_case_line_checks(line, i):
    req(set(line) == CASE_RAW_KEYS, "raw case line keys %d: expected exactly %s, got %s"
        % (i, sorted(CASE_RAW_KEYS), sorted(set(line))))
    req(isinstance(line["duration_ms"], int), "raw case timing shape %d" % i)


def one_run(rid, prov_out, root=None):
    root = HERE if root is None else Path(root)
    d = root / "raw" / rid
    req(d.is_dir() and not d.is_symlink(), "run dir " + rid)
    names = {p.name for p in d.iterdir()}
    req(names == RAW_FILES, "closed raw %s: %s" % (rid, sorted(names)))
    req(all(regular(p) for p in d.iterdir()), "regular raw " + rid)

    i = json.loads((d / "00_inputs.json").read_text())
    req(set(i) == INPUTS_KEYS and i["boundary"] == BOUNDARY
        and i["timeouts_seconds"] == TIMEOUTS
        and set(i["authored_code_sha256"]) == set(AUTH_CODE)
        and set(i["authored_doc_sha256"]) == set(AUTH_DOC), "inputs schema " + rid)
    c = json.loads((root / "CAPTURE_CONTRACT.json").read_text())
    frozen = {**i["authored_doc_sha256"], **i["authored_code_sha256"]}
    req(frozen == c["authored_sha256"], "inputs frozen-hash binding " + rid)

    cases = json.loads((d / "01_cases.json").read_text())
    req(cases["schema"] == 1 and cases["run_id"] == rid and cases["total"] == TOTAL,
        "cases header " + rid)
    all_cases = CM.full_case_list()
    for j, entry in enumerate(cases["cases"]):
        cc = all_cases[j]
        req(entry["kernel"] == cc["kernel"] and entry["case_name"] == cc["name"]
            and entry["item"] == cc["item"] and entry["rep"] == cc["rep"],
            "case matrix echo %d %s" % (j, rid))

    disp = json.loads((d / "03_dispatch.json").read_text())
    req(set(disp) == DISPATCH_KEYS, "dispatch keys %s" % rid)
    req(disp["n_cases"] == TOTAL and disp["results_lines"] == TOTAL
        and sum(disp["status_counts"].values()) == TOTAL
        and sum(disp["verdict_counts"].values()) == TOTAL, "dispatch content " + rid)

    res = (d / "04_results.jsonl").read_text().splitlines()
    req(len(res) == TOTAL == disp["results_lines"], "result line count " + rid)
    status_seen, verdict_seen = {}, {}
    for j, ln in enumerate(res):
        line = json.loads(ln)
        case_line_checks(line, j, all_cases[j])
        status_seen[line["status"]] = status_seen.get(line["status"], 0) + 1
        verdict_seen[line["verdict"]] = verdict_seen.get(line["verdict"], 0) + 1
    req(disp["status_counts"] == status_seen, "dispatch status counts " + rid)
    req(disp["verdict_counts"] == verdict_seen, "dispatch verdict counts " + rid)
    req(sha(d / "04_results.jsonl") == disp["results_sha256"], "results hash " + rid)

    rawres = (d / "04_results_raw.jsonl").read_text().splitlines()
    req(len(rawres) == TOTAL, "raw result line count " + rid)
    for j, ln in enumerate(rawres):
        raw_case_line_checks(json.loads(ln), j)

    prov_out.append({"rid": rid, "git_revision": i["git_revision"],
                     "frozen": frozen, "status_counts": disp["status_counts"],
                     "verdict_counts": disp["verdict_counts"],
                     "gated_results": (d / "04_results.jsonl").read_bytes()})


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
        # NOTE: git_revision is recorded per-run (informational) but
        # DELIBERATELY NOT required to match between runs -- the orchestrator
        # may commit other experiments' work between run01 and run02; only
        # the AUTHORED SOURCE HASHES ("frozen") are the pinned contract (see
        # ../SUBAGENT_BRIEF.md and this file's module docstring).
        req(x["frozen"] == y["frozen"], "cross-run authored provenance")
        # THE gate-class-(d) check: the GATED file must be byte-identical.
        # (04_results_raw.jsonl, which carries timing, is deliberately NEVER
        # compared here.)
        req(x["gated_results"] == y["gated_results"], "byte-exact gated repeat")
        req(x["status_counts"] == y["status_counts"], "cross-run status identity")
        req(x["verdict_counts"] == y["verdict_counts"], "cross-run verdict identity")


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
# Synthetic-tree fabrication (selftest + seqtest). No Metal, no device.
# ---------------------------------------------------------------------------
SELFTEST_DIR = "selftest"
_SYNT_TS = "2026-08-28T00:00:00+00:00"
_SYNTH_TS = _SYNT_TS


def _put(p, o):
    Path(p).write_text(json.dumps(o, indent=2, sort_keys=True) + "\n")


def _synth_record(keys, argv, cwd, timeout, **extra):
    z = {"argv": [str(x) for x in argv], "cwd": str(cwd), "timeout_seconds": timeout,
         "started_utc": _SYNTH_TS, "timed_out": False, "exit": 0,
         "stdout": "", "stderr": "", "exception": None}
    z.update(extra)
    return z


def _copy_authored(dst):
    dst = Path(dst)
    dst.mkdir(parents=True, exist_ok=True)
    for p in AUTH_ALL + ("CAPTURE_CONTRACT.json", "RESULTS.md", "PROGRESS.md"):
        q = dst / p
        q.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(HERE / p, q)


def _gitrev():
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, text=True,
                          capture_output=True, check=True).stdout.strip()


def _synth_case_line(c, timing_salt=0):
    """One internally consistent, deterministic (except raw timing) case pair
    (gated, raw). verdict is always MATCH_EXPECTED (a clean synthetic tree)."""
    expected = CM.EXPECTED[c["kernel"]](CM.INPUTS[c["kernel"]])
    gated = {"i": c["i"], "kernel": c["kernel"], "case_name": c["name"], "item": c["item"],
             "rep": c["rep"], "splice_args": [], "changed_bytes": [], "status": "OK",
             "pipeline_source": "archive", "out_values": ["%.8g" % v for v in expected],
             "expected_values": ["%.8g" % v for v in expected],
             "verdict": "MATCH_EXPECTED", "mismatch_indices": []}
    rawrec = {"i": c["i"], "duration_ms": 10 + timing_salt, "exit": 0, "timed_out": False,
              "exception": None, "stdout": "synthetic run %d" % timing_salt, "stderr": ""}
    return gated, rawrec


def _build_tree(root, runs=RUNS, with_analysis=True, pre_gpu=False, mutate=None,
                post_manifest=None, timing_salt_by_run=None, git_revision_by_run=None):
    root = Path(root)
    root.mkdir(parents=True)
    _copy_authored(root)
    frozen = {p: sha(HERE / p) for p in AUTH_ALL}
    all_cases = CM.full_case_list()
    base_rev = _gitrev()
    for rid in runs:
        d = root / "raw" / rid
        d.mkdir(parents=True)
        work = root / "work" / rid
        rev = (git_revision_by_run or {}).get(rid, base_rev)
        _put(d / "00_inputs.json", {
            "schema": 1, "git_revision": rev,
            "git_dirty": True, "experiment_tree_dirty_entries": 1,
            "authored_code_sha256": {p: frozen[p] for p in AUTH_CODE},
            "authored_doc_sha256": {p: frozen[p] for p in AUTH_DOC},
            "sw_vers": _synth_record(REC_KEYS, ["sw_vers"], root, TIMEOUTS["env_command"]),
            "xcrun_version": _synth_record(REC_KEYS, ["xcrun", "--version"], root,
                                           TIMEOUTS["env_command"]),
            "python": "synthetic", "machine": "arm64", "boundary": BOUNDARY,
            "timeouts_seconds": TIMEOUTS, "repeat_n": CM.REPEAT_N, "tol_rel": R.TOL_REL})
        _put(d / "01_cases.json", {
            "schema": 1, "run_id": rid, "total": TOTAL,
            "cases": [{"i": c["i"], "kernel": c["kernel"], "case_name": c["name"],
                       "item": c["item"], "rep": c["rep"], "note": c["note"]}
                      for c in all_cases]})
        _put(d / "02_build.json", {
            "schema": 1,
            "harness_build": _synth_record(REC_KEYS, [root / "harness" / "build.sh",
                                                      work / "shared" / "bin"], root,
                                           TIMEOUTS["host_build"]),
            "baseline": _synth_record(REC_KEYS, [sys.executable, "-B", "baseline.py",
                                                 "--bin-dir", work / "shared" / "bin",
                                                 "--out", work / "baseline.json"],
                                      root, TIMEOUTS["baseline"])})
        salt = (timing_salt_by_run or {}).get(rid, 0)
        gated_lines, raw_lines = [], []
        status_counts, verdict_counts = {}, {}
        for c in all_cases:
            gated, rawrec = _synth_case_line(c, timing_salt=salt + c["i"])
            gated_lines.append(json.dumps(gated, sort_keys=True))
            raw_lines.append(json.dumps(rawrec, sort_keys=True))
            status_counts[gated["status"]] = status_counts.get(gated["status"], 0) + 1
            verdict_counts[gated["verdict"]] = verdict_counts.get(gated["verdict"], 0) + 1
        gtxt = "\n".join(gated_lines) + "\n"
        rtxt = "\n".join(raw_lines) + "\n"
        (d / "04_results.jsonl").write_text(gtxt)
        (d / "04_results_raw.jsonl").write_text(rtxt)
        _put(d / "03_dispatch.json", {
            "argv": [sys.executable, "run.py", "--execute", "--run-id", rid],
            "cwd": str(root), "started_utc": _SYNT_TS, "finished_utc": _SYNT_TS,
            "duration_seconds": 1.0, "n_cases": TOTAL, "status_counts": status_counts,
            "verdict_counts": verdict_counts,
            "results_sha256": hashlib.sha256(gtxt.encode()).hexdigest(),
            "results_lines": TOTAL})
        item_counts = {}
        for c in all_cases:
            item_counts[c["item"]] = item_counts.get(c["item"], 0) + 1
        _put(d / "05_run_manifest.json", {
            "schema": 1, "run_id": rid, "total_cases": TOTAL,
            "item_counts": dict(sorted(item_counts.items())),
            "runner_sha256": frozen["run.py"], "casematrix_sha256": frozen["casematrix.py"],
            "harness_sha256": frozen["harness/build.sh"], "baseline_sha256": "0" * 64,
            "cases_sha256": sha(d / "01_cases.json"),
            "results_sha256": hashlib.sha256(gtxt.encode()).hexdigest()})
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
                                "results_raw": "04_results_raw.jsonl",
                                "rmanifest": "05_run_manifest.json",
                                "build": "02_build.json"}[kind])


def _resync_hash(root, rid, resync_counts=False):
    rel = _rel("dispatch", rid)
    d = _load(root, rel)
    txt = (Path(root) / _rel("results", rid)).read_text()
    d["results_sha256"] = hashlib.sha256(txt.encode()).hexdigest()
    if resync_counts:
        status_counts, verdict_counts = {}, {}
        for ln in txt.splitlines():
            z = json.loads(ln)
            status_counts[z["status"]] = status_counts.get(z["status"], 0) + 1
            verdict_counts[z["verdict"]] = verdict_counts.get(z["verdict"], 0) + 1
        d["status_counts"] = status_counts
        d["verdict_counts"] = verdict_counts
    _put(Path(root) / rel, d)
    rm = _load(root, _rel("rmanifest", rid))
    rm["results_sha256"] = d["results_sha256"]
    _put(Path(root) / _rel("rmanifest", rid), rm)


# --- mutation helpers: each breaks exactly one frozen expectation ------------
def m_overkeyed_dispatch(root):
    rel = _rel("dispatch", RUNS[0])
    z = _load(root, rel)
    z["unexpected_extra_key"] = 1
    _put(Path(root) / rel, z)


def m_underkeyed_dispatch(root):
    rel = _rel("dispatch", RUNS[0])
    z = _load(root, rel)
    del z["status_counts"]
    _put(Path(root) / rel, z)


def m_overkeyed_gated_case_line(root):
    p = Path(root) / _rel("results", RUNS[0])
    lines = p.read_text().splitlines()
    z = json.loads(lines[0])
    z["unexpected_extra_key"] = 1
    lines[0] = json.dumps(z, sort_keys=True)
    p.write_text("\n".join(lines) + "\n")
    _resync_hash(root, RUNS[0])


def m_gated_leaks_timing(root):
    """The class-(d) defect, verbatim: a duration field sneaks into the GATED
    file. Must be rejected even though the shape is otherwise plausible."""
    p = Path(root) / _rel("results", RUNS[0])
    lines = p.read_text().splitlines()
    z = json.loads(lines[0])
    z["duration_ms"] = 123
    lines[0] = json.dumps(z, sort_keys=True)
    p.write_text("\n".join(lines) + "\n")
    _resync_hash(root, RUNS[0])


def m_case_status_counts_wrong(root):
    rel = _rel("dispatch", RUNS[0])
    z = _load(root, rel)
    sc = dict(z["status_counts"])
    sc["OK"] = sc.get("OK", 0) - 1
    sc["HANG"] = sc.get("HANG", 0) + 1
    z["status_counts"] = sc
    _put(Path(root) / rel, z)


def m_run02_gated_result_differs(root):
    p = Path(root) / _rel("results", RUNS[1])
    lines = p.read_text().splitlines()
    z = json.loads(lines[3])
    z["out_values"] = ["9.99999e9"] * len(z["out_values"])
    z["verdict"] = "MISMATCH_EXPECTED"
    lines[3] = json.dumps(z, sort_keys=True)
    p.write_text("\n".join(lines) + "\n")
    _resync_hash(root, RUNS[1], resync_counts=True)


def m_raw_extra_file(root):
    (Path(root) / ("raw/%s/06_extra.json" % RUNS[0])).write_text("{}\n")


def m_case_line_missing(root):
    p = Path(root) / _rel("results", RUNS[0])
    lines = p.read_text().splitlines()
    p.write_text("\n".join(lines[:-1]) + "\n")
    _resync_hash(root, RUNS[0])


def m_case_echo_tampered(root):
    rel = _rel("cases", RUNS[0])
    z = _load(root, rel)
    z["cases"][0]["kernel"] = "far16"
    _put(Path(root) / rel, z)


def m_kernel_drift(root):
    p = Path(root) / "kernels" / "adjacent.metal"
    p.write_text(p.read_text() + "\n// drifted\n")


def m_manifest_stale(root):
    p = Path(root) / "PROGRESS.md"
    p.write_text(p.read_text() + "\n")


def selftest():
    scratch = HERE / SELFTEST_DIR
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    cases = []

    def add(name, expect_pass, needle, builder):
        cases.append((name, expect_pass, needle, builder))

    def broken(name, needle, mutate, **kw):
        add(name, False, needle, lambda r: _build_tree(r, mutate=mutate, **kw))

    add("preflight_gate_satisfiable", True, None,
        lambda r: _build_tree(r, runs=(), with_analysis=False, pre_gpu=True))
    add("between_runs_gate_satisfiable", True, None,
        lambda r: _build_tree(r, runs=(RUNS[0],), with_analysis=False))
    add("captured_gate_satisfiable", True, None, lambda r: _build_tree(r))
    # gate class (d): timing-only divergence between runs must still PASS.
    add("cross_run_timing_only_differs_still_passes", True, None,
        lambda r: _build_tree(r, timing_salt_by_run={RUNS[0]: 0, RUNS[1]: 9999}))
    # EXP-0089-specific lesson: live git_revision divergence between runs
    # (informational only) must NOT break the cross-run gate -- only the
    # authored source hashes are pinned. See module docstring.
    add("cross_run_git_revision_differs_still_passes", True, None,
        lambda r: _build_tree(r, git_revision_by_run={
            RUNS[0]: "0" * 40, RUNS[1]: "f" * 40}))
    broken("dispatch_overkeyed", "dispatch keys", m_overkeyed_dispatch)
    broken("dispatch_underkeyed", "dispatch keys", m_underkeyed_dispatch)
    broken("gated_case_line_overkeyed", "case line keys", m_overkeyed_gated_case_line)
    broken("gated_case_line_leaks_timing", "case line keys", m_gated_leaks_timing)
    broken("status_counts_wrong", "dispatch status counts", m_case_status_counts_wrong)
    broken("cross_run_gated_repeat_broken", "byte-exact gated repeat", m_run02_gated_result_differs)
    broken("raw_extra_file", "closed raw", m_raw_extra_file)
    broken("case_line_missing", "result line count", m_case_line_missing)
    broken("case_echo_tampered", "case matrix echo", m_case_echo_tampered)
    broken("authored_hash_drift", "authored hash", m_kernel_drift)
    broken("manifest_stale", "manifest", None, post_manifest=m_manifest_stale)

    n_ok = 0
    try:
        for name, expect_pass, needle, builder in cases:
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
                        print("  case %-42s FAIL (gate raised: %s)" % (name, e))
                        continue
                else:
                    try:
                        gate_captured(root)
                    except SystemExit as e:
                        msg = str(e)
                        if needle is not None and needle not in msg:
                            print("  case %-42s FAIL (failed on %r, expected %r)"
                                  % (name, msg, needle))
                            continue
                    else:
                        print("  case %-42s FAIL (gate unexpectedly PASSED)" % name)
                        continue
            finally:
                shutil.rmtree(root, ignore_errors=True)
            n_ok += 1
            print("  case %-42s PASS" % name)
        print("SELFTEST %s %d/%d synthetic cases (no Metal, no device, no Apple binary)"
              % ("PASS" if n_ok == len(cases) else "FAIL", n_ok, len(cases)))
        if n_ok != len(cases):
            raise SystemExit(1)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def seqtest():
    scratch = HERE / SELFTEST_DIR
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    steps = []

    def step(name, ok, detail=""):
        steps.append((name, ok, detail))
        print("  step %-52s %s %s" % (name, "PASS" if ok else "FAIL", detail))
        return ok

    try:
        s0 = scratch / "S0_pre_gpu"
        _build_tree(s0, runs=(), with_analysis=False, pre_gpu=True)
        step("S0 make_manifest --check", manifest_expected(False, s0)
             == json.loads((s0 / "manifest.json").read_text()))
        try:
            gate_preflight(s0)
            step("S0 --preflight (contracted)", True)
        except SystemExit as e:
            step("S0 --preflight (contracted)", False, str(e))
        try:
            gate_between(s0)
            step("S0 --between-runs correctly REFUSED", False, "gate passed pre-GPU")
        except SystemExit:
            step("S0 --between-runs correctly REFUSED", True)
        try:
            gate_captured(s0)
            step("S0 --captured correctly REFUSED", False, "gate passed pre-GPU")
        except SystemExit:
            step("S0 --captured correctly REFUSED", True)
        shutil.rmtree(s0, ignore_errors=True)

        s1 = scratch / "S1_run01"
        _build_tree(s1, runs=(RUNS[0],), with_analysis=False)
        try:
            gate_preflight(s1)
            step("S1 --preflight correctly REFUSED (raw present)", False, "passed with raw")
        except SystemExit:
            step("S1 --preflight correctly REFUSED (raw present)", True)
        try:
            gate_between(s1)
            step("S1 --between-runs (contracted)", True)
        except SystemExit as e:
            step("S1 --between-runs (contracted)", False, str(e))
        try:
            gate_captured(s1)
            step("S1 --captured correctly REFUSED (one run)", False, "passed with one run")
        except SystemExit:
            step("S1 --captured correctly REFUSED (one run)", True)
        step("S1 --selftest runnable (root-independent)", _selftest_quiet(scratch / "st1"))
        step("S1 --seqtest runnable (root-independent)", True)
        shutil.rmtree(s1, ignore_errors=True)

        s2 = scratch / "S2_run02"
        _build_tree(s2, runs=RUNS, with_analysis=False)
        try:
            gate_between(s2)
            step("S2 --between-runs correctly REFUSED (two runs)", False, "passed with two")
        except SystemExit:
            step("S2 --between-runs correctly REFUSED (two runs)", True)
        try:
            gate_captured(s2)
            step("S2 --captured correctly REFUSED (no analysis)", False, "passed w/o analysis")
        except SystemExit:
            step("S2 --captured correctly REFUSED (no analysis)", True)
        (s2 / "analysis.json").write_text('{"synthetic": true}\n')
        _put(s2 / "manifest.json", manifest_expected(True, s2))
        try:
            gate_captured(s2)
            step("S2 --captured (contracted, after analysis + manifest refresh)", True)
        except SystemExit as e:
            step("S2 --captured (contracted, after analysis + manifest refresh)", False, str(e))
        rp = (HERE / "run.py").read_text()
        step("run.py requires --selftest AND --seqtest before every capture",
             '"--selftest"' in rp and '"--seqtest"' in rp
             and 'for gate in ("--selftest", "--seqtest")' in rp)
        step("run.py state gate: preflight for run01, between-runs for run02",
             '"--preflight" if a.run_id == RUNS[0] else "--between-runs"' in rp)
        shutil.rmtree(s2, ignore_errors=True)

        n_ok = sum(1 for _, ok, _ in steps if ok)
        print("SEQTEST %s %d/%d state-machine steps (contracted order walkable end to end)"
              % ("PASS" if n_ok == len(steps) else "FAIL", n_ok, len(steps)))
        if n_ok != len(steps):
            raise SystemExit(1)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def _selftest_quiet(scratch):
    global SELFTEST_DIR
    old = SELFTEST_DIR
    SELFTEST_DIR = str(scratch)
    try:
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            try:
                selftest()
            except SystemExit:
                return False
        return True
    finally:
        SELFTEST_DIR = old


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--selftest", action="store_true")
    g.add_argument("--seqtest", action="store_true")
    g.add_argument("--preflight", action="store_true")
    g.add_argument("--between-runs", action="store_true")
    g.add_argument("--captured", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest()
    elif a.seqtest:
        seqtest()
    elif a.preflight:
        gate_preflight()
        print("PASS PRE_GPU contract; no GPU capture")
    elif a.between_runs:
        gate_between()
        print("PASS run01 contract; run02 may begin")
    else:
        gate_captured()
        print("PASS captured EXP-0089 register-lifecycle contract")


if __name__ == "__main__":
    main()
