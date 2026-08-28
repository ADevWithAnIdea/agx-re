#!/usr/bin/env python3
"""Fail-closed static and post-capture verifier for EXP-0094.

One record checker, one frozen key set per record slot, imported from run.py
(never restated here) -- the standing anti-quarantine-class-defect rule.
Extra keys and missing keys both fail, everywhere, identically.

Two self-tests, both REQUIRED before any capture and both runnable in EVERY
tree state (they operate only on synthetic scratch copies under selftest/,
never on the real raw/):

  --selftest  fabricates complete synthetic captures (no Metal, no device, no
              Apple binary) and drives them through the same static()/captured()
              code paths used on real evidence, including the cross-run
              comparison; proves clean shapes pass and each broken shape fails
              for the right reason. Explicitly proves the NO-NONDETERMINISM
              distinction (gate class d): two synthetic runs whose GATED
              04_results.jsonl are byte-identical but whose NON-GATED
              04_results_raw.jsonl differ only in timing PASS the cross-run
              gate; a run whose GATED file differs semantically FAILS it.
  --seqtest   walks the contracted gate ORDER through synthetic states
              (PRE_GPU -> RUN01_PRESENT -> RUN02_PRESENT) and proves every gate
              is runnable and satisfiable in the exact state the contract
              invokes it, and refused everywhere else.

PINNED-REVISION RULE (experiments/SUBAGENT_BRIEF.md): the cross-run gate below
compares ONLY the authored-file sha256 sets recorded in each run's
00_inputs.json (bound to the frozen CAPTURE_CONTRACT.json) -- it never
compares git_revision between run01 and run02. Live repo HEAD moving because a
sibling experiment landed is not contamination.

Selftest fixtures are built from RECORDED REALITY (gate e): the synthetic case
lines are derived from casematrix.full_case_list() -- the SAME case identities
and EXPECTED/oracle values run.py computes from the pilot HW-derived
reference.py math -- never ad hoc constants invented in this file.
"""
import argparse, hashlib, json, shutil, subprocess, sys
from pathlib import Path

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "analysis"))
import run as R          # noqa: E402  (schema constants)
import casematrix as CM  # noqa: E402

RUNS = R.RUNS
BOUNDARY = R.BOUNDARY
TIMEOUTS = R.TIMEOUTS
AUTH_CODE = R.AUTH_CODE
AUTH_DOC = R.AUTH_DOC
AUTH_ALL = AUTH_DOC + AUTH_CODE
CASE_KEYS = R.CASE_KEYS
CASE_RAW_KEYS = R.CASE_RAW_KEYS
DISPATCH_KEYS = R.DISPATCH_KEYS
STATUS_ALLOWED = R.STATUS_ALLOWED
VERDICT_ALLOWED = R.VERDICT_ALLOWED
TOTAL = len(CM.full_case_list())
ALL_CASES = CM.full_case_list()

QUARANTINE_DIRS = ("quarantine-m4-20260828-run01", "quarantine-m4-20260828b-run01")
QUARANTINE_NOTES = ("QUARANTINE-run01-attempt1.md", "QUARANTINE-run01b-attempt2.md")
QUARANTINE_RUN_FILES = {"00_inputs.json", "01_cases.json", "02_build.json", "03_dispatch.json",
                        "04_results.jsonl", "04_results_raw.jsonl", "05_run_manifest.json"}
ROOT_FILES = {"CAPTURE_CONTRACT.json", "PRE_REGISTRATION.md", "README.md",
             "PROGRESS.md", "kernels", "harness", "analysis", "run.py", "verify.py",
             *QUARANTINE_DIRS, *QUARANTINE_NOTES}
RAW_FILES = {"00_inputs.json", "01_cases.json", "02_build.json", "03_dispatch.json",
            "04_results.jsonl", "04_results_raw.jsonl", "05_run_manifest.json"}
INPUTS_KEYS = {"schema", "git_revision", "git_dirty", "experiment_tree_dirty_entries",
              "authored_code_sha256", "authored_doc_sha256", "sw_vers", "xcrun_version",
              "python", "machine", "boundary", "timeouts_seconds"}
BUILD_KEYS = {"schema", "harness_build"}
NONDET_FORBIDDEN = {"duration_ms", "duration_seconds_case", "pid", "address",
                    "timestamp", "started_utc_case", "gputime_ns"}


def fail(s):
    raise SystemExit("FAIL " + s)


def req(v, s):
    if not v:
        fail(s)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def regular(p):
    return Path(p).is_file() and not Path(p).is_symlink()


def contract_checks(c, root):
    req(c.get("schema") == 1, "contract schema")
    req(set(c.get("authored_sha256", {})) == set(AUTH_ALL), "contract authored set")
    for p in AUTH_ALL:
        req(c["authored_sha256"][p] == sha(root / p), "contract hash drift " + p)
    req(c.get("run_ids") == list(RUNS), "contract run ids")
    req(isinstance(c.get("timeouts_seconds"), dict), "contract timeouts")


def static(capture=False, root=None, require_results=False):
    root = HERE if root is None else Path(root)
    names = {p.name for p in root.iterdir()}
    extra_allowed = ({"raw"} if capture else set()) | ({"work"} if "work" in names else set()) \
        | ({"RESULTS.md"} if "RESULTS.md" in names else set()) \
        | ({"selftest"} if "selftest" in names else set())
    allowed = ROOT_FILES | extra_allowed
    req(not root.is_symlink() and names <= allowed and ROOT_FILES <= names,
        "closed root: missing=%s extra=%s" % (sorted(ROOT_FILES - names), sorted(names - allowed)))
    if "work" in names:
        w = root / "work"
        req(w.is_dir() and not w.is_symlink() and not any(w.iterdir()), "work absent or empty")
    for p in AUTH_ALL + ("CAPTURE_CONTRACT.json", "PROGRESS.md", *QUARANTINE_NOTES):
        req(regular(root / p), "regular " + p)
    for qdname in QUARANTINE_DIRS:
        q = root / qdname
        req(q.is_dir() and not q.is_symlink()
            and {x.name for x in q.iterdir()} == QUARANTINE_RUN_FILES
            and all(regular(x) for x in q.iterdir()), "closed quarantine dir " + qdname)
    contract_checks(json.loads((root / "CAPTURE_CONTRACT.json").read_text()), root)
    if require_results:
        req(regular(root / "RESULTS.md"), "regular RESULTS.md (required once fully captured)")
        req("finite-resource" in (root / "RESULTS.md").read_text().lower()
            or "finite resource" in (root / "RESULTS.md").read_text().lower(),
            "RESULTS.md missing finite-resource section")


def case_line_checks(line, i, c):
    req(set(line) == CASE_KEYS, "case line keys %d: expected exactly %s, got %s"
        % (i, sorted(CASE_KEYS), sorted(set(line))))
    req(line["i"] == i and line["backend"] == c["backend"] and line["case_name"] == c["case_name"],
        "case echo %d" % i)
    req(line["status"] in STATUS_ALLOWED, "case status %d" % i)
    req(line["verdict"] in VERDICT_ALLOWED, "case verdict %d" % i)
    if line["backend"] == "regsplice_bias" and line["status"] == "OK":
        req(line["pipeline_source"] == "archive", "regsplice ok-shape (archive) %d" % i)
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
    for j, entry in enumerate(cases["cases"]):
        cc = ALL_CASES[j]
        req(entry["backend"] == cc["backend"] and entry["case_name"] == cc["case_name"],
            "case matrix echo %d %s" % (j, rid))

    build = json.loads((d / "02_build.json").read_text())
    req(set(build) == BUILD_KEYS, "build keys " + rid)

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
        case_line_checks(line, j, ALL_CASES[j])
        status_seen[line["status"]] = status_seen.get(line["status"], 0) + 1
        verdict_seen[line["verdict"]] = verdict_seen.get(line["verdict"], 0) + 1
    req(disp["status_counts"] == status_seen, "dispatch status counts " + rid)
    req(disp["verdict_counts"] == verdict_seen, "dispatch verdict counts " + rid)
    req(sha(d / "04_results.jsonl") == disp["results_sha256"], "results hash " + rid)

    rawres = (d / "04_results_raw.jsonl").read_text().splitlines()
    req(len(rawres) == TOTAL, "raw result line count " + rid)
    for j, ln in enumerate(rawres):
        raw_case_line_checks(json.loads(ln), j)

    prov_out.append({"rid": rid, "frozen": frozen, "status_counts": disp["status_counts"],
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
        req(x["frozen"] == y["frozen"], "cross-run authored provenance")
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
    static(capture=True, root=root, require_results=True)
    captured(RUNS, root)


# ---------------------------------------------------------------------------
# Synthetic-tree fabrication (selftest + seqtest). No Metal, no device.
# ---------------------------------------------------------------------------
SELFTEST_DIR = "selftest"
_SYNTH_TS = "2026-08-28T00:00:00+00:00"


def _put(p, o):
    Path(p).write_text(json.dumps(o, indent=2, sort_keys=True) + "\n")


def _synth_case_line(c, timing_salt=0):
    gated = {"i": c["i"], "backend": c["backend"], "case_name": c["case_name"],
             "params": c, "status": "OK", "pipeline_source": "source",
             "observed": c.get("expected"), "expected": c.get("expected"),
             "verdict": "MATCH_EXPECTED" if c.get("expected") is not None else "OBSERVED_NO_ORACLE"}
    if c["backend"] == "regsplice_bias":
        gated["pipeline_source"] = "archive"
    rawrec = {"i": c["i"], "duration_ms": 10 + timing_salt, "exit": 0, "timed_out": False,
             "exception": None, "stdout": "STATUS OK\n", "stderr": ""}
    return gated, rawrec


def _copy_authored(dst):
    for p in AUTH_ALL:
        src = HERE / p
        d = dst / p
        d.parent.mkdir(parents=True, exist_ok=True)
        d.write_bytes(src.read_bytes())


def _build_tree(root, runs=(), pre_gpu=False, mutate=None, timing_salt_by_run=None):
    root.mkdir(parents=True, exist_ok=True)
    _copy_authored(root)
    (root / "PROGRESS.md").write_text("synthetic\n")
    for note in QUARANTINE_NOTES:
        (root / note).write_text("synthetic quarantine note\n")
    for qdname in QUARANTINE_DIRS:
        qd = root / qdname
        qd.mkdir(parents=True, exist_ok=True)
        for fn in QUARANTINE_RUN_FILES:
            (qd / fn).write_text("{}\n" if fn.endswith(".json") else "\n")
    results_text = "finite-resource table present\n"
    (root / "RESULTS.md").write_text(results_text)
    contract = {"schema": 1, "authored_sha256": {p: sha(HERE / p) for p in AUTH_ALL},
               "run_ids": list(RUNS), "timeouts_seconds": TIMEOUTS}
    _put(root / "CAPTURE_CONTRACT.json", contract)
    if pre_gpu:
        return
    frozen = contract["authored_sha256"]
    for rid in runs:
        d = root / "raw" / rid
        d.mkdir(parents=True)
        salt = (timing_salt_by_run or {}).get(rid, 0)
        inputs = {"schema": 1, "git_revision": "deadbeef" * 5, "git_dirty": False,
                 "experiment_tree_dirty_entries": 0,
                 "authored_code_sha256": {p: frozen[p] for p in AUTH_CODE},
                 "authored_doc_sha256": {p: frozen[p] for p in AUTH_DOC},
                 "sw_vers": {}, "xcrun_version": {}, "python": "3.x", "machine": "arm64",
                 "boundary": BOUNDARY, "timeouts_seconds": TIMEOUTS}
        _put(d / "00_inputs.json", inputs)
        _put(d / "01_cases.json", {"schema": 1, "run_id": rid, "total": TOTAL,
                                   "cases": [{"i": c["i"], "backend": c["backend"],
                                             "case_name": c["case_name"]} for c in ALL_CASES]})
        _put(d / "02_build.json", {"schema": 1, "harness_build": {}})
        status_counts, verdict_counts = {}, {}
        with (d / "04_results.jsonl").open("a") as rf, (d / "04_results_raw.jsonl").open("a") as rrf:
            for c in ALL_CASES:
                gated, rawrec = _synth_case_line(c, timing_salt=salt)
                rf.write(json.dumps(gated, sort_keys=True, default=str) + "\n")
                rrf.write(json.dumps(rawrec, sort_keys=True) + "\n")
                status_counts[gated["status"]] = status_counts.get(gated["status"], 0) + 1
                verdict_counts[gated["verdict"]] = verdict_counts.get(gated["verdict"], 0) + 1
        results_sha = sha(d / "04_results.jsonl")
        _put(d / "03_dispatch.json", {"argv": ["python3"], "cwd": str(root), "started_utc": _SYNTH_TS,
                                      "finished_utc": _SYNTH_TS, "duration_seconds": 1.0,
                                      "n_cases": TOTAL, "status_counts": status_counts,
                                      "verdict_counts": verdict_counts, "results_sha256": results_sha,
                                      "results_lines": TOTAL})
        _put(d / "05_run_manifest.json", {"schema": 1, "run_id": rid, "total_cases": TOTAL})
    if mutate:
        mutate(root)


def m_overkeyed_dispatch(root):
    rid = RUNS[0] if (root / "raw" / RUNS[0]).exists() else RUNS[1]
    p = root / "raw" / rid / "03_dispatch.json"
    o = json.loads(p.read_text()); o["extra_field"] = 1; _put(p, o)


def m_overkeyed_gated_case_line(root):
    rid = RUNS[0] if (root / "raw" / RUNS[0]).exists() else RUNS[1]
    p = root / "raw" / rid / "04_results.jsonl"
    lines = p.read_text().splitlines()
    o = json.loads(lines[0]); o["extra_field"] = 1; lines[0] = json.dumps(o, sort_keys=True, default=str)
    p.write_text("\n".join(lines) + "\n")
    _put(root / "raw" / rid / "03_dispatch.json",
        {**json.loads((root / "raw" / rid / "03_dispatch.json").read_text()),
         "results_sha256": sha(p)})


def m_gated_leaks_timing(root):
    rid = RUNS[0] if (root / "raw" / RUNS[0]).exists() else RUNS[1]
    p = root / "raw" / rid / "04_results.jsonl"
    lines = p.read_text().splitlines()
    o = json.loads(lines[0]); o["duration_ms"] = 5; lines[0] = json.dumps(o, sort_keys=True, default=str)
    p.write_text("\n".join(lines) + "\n")
    _put(root / "raw" / rid / "03_dispatch.json",
        {**json.loads((root / "raw" / rid / "03_dispatch.json").read_text()),
         "results_sha256": sha(p)})


def m_case_status_counts_wrong(root):
    rid = RUNS[0] if (root / "raw" / RUNS[0]).exists() else RUNS[1]
    p = root / "raw" / rid / "03_dispatch.json"
    o = json.loads(p.read_text())
    n = sum(o["status_counts"].values())
    o["status_counts"] = {"OK": n - 1, "HANG": 1}  # sum preserved, distribution wrong
    _put(p, o)


def m_run02_gated_result_differs(root):
    p = root / "raw" / RUNS[1] / "04_results.jsonl"
    lines = p.read_text().splitlines()
    o = json.loads(lines[0]); o["status"] = "CMDBUF_ERROR"; o["verdict"] = "FAULT"
    lines[0] = json.dumps(o, sort_keys=True, default=str)
    p.write_text("\n".join(lines) + "\n")
    dp = root / "raw" / RUNS[1] / "03_dispatch.json"
    d = json.loads(dp.read_text())
    d["results_sha256"] = sha(p)
    d["status_counts"] = dict(d["status_counts"])
    d["status_counts"]["OK"] = d["status_counts"].get("OK", 0) - 1
    d["status_counts"]["CMDBUF_ERROR"] = d["status_counts"].get("CMDBUF_ERROR", 0) + 1
    d["verdict_counts"] = dict(d["verdict_counts"])
    d["verdict_counts"]["MATCH_EXPECTED"] = d["verdict_counts"].get("MATCH_EXPECTED", 0) - 1
    d["verdict_counts"]["FAULT"] = d["verdict_counts"].get("FAULT", 0) + 1
    _put(dp, d)


def m_run02_authored_hash_differs(root):
    p = root / "raw" / RUNS[1] / "00_inputs.json"
    o = json.loads(p.read_text())
    o["authored_code_sha256"][AUTH_CODE[0]] = "0" * 64
    _put(p, o)


def m_raw_extra_file(root):
    rid = RUNS[0] if (root / "raw" / RUNS[0]).exists() else RUNS[1]
    (root / "raw" / rid / "EXTRA.json").write_text("{}\n")


def m_case_line_missing(root):
    rid = RUNS[0] if (root / "raw" / RUNS[0]).exists() else RUNS[1]
    p = root / "raw" / rid / "04_results.jsonl"
    lines = p.read_text().splitlines()
    p.write_text("\n".join(lines[:-1]) + "\n")


def m_case_echo_tampered(root):
    rid = RUNS[0] if (root / "raw" / RUNS[0]).exists() else RUNS[1]
    p = root / "raw" / rid / "01_cases.json"
    o = json.loads(p.read_text()); o["cases"][0]["backend"] = "bogus_backend"; _put(p, o)


def m_authored_drift(root):
    (root / "analysis" / "reference.py").write_text("# tampered\n")


def selftest():
    scratch = HERE / SELFTEST_DIR
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    cases = []

    def add(name, expect_pass, needle, builder):
        cases.append((name, expect_pass, needle, builder))

    def broken(name, needle, mutate, **kw):
        add(name, False, needle, lambda r: _build_tree(r, runs=RUNS, mutate=mutate, **kw))

    add("preflight_gate_satisfiable", True, None, lambda r: _build_tree(r, runs=(), pre_gpu=True))
    add("between_runs_gate_satisfiable", True, None, lambda r: _build_tree(r, runs=(RUNS[0],)))
    add("captured_gate_satisfiable", True, None, lambda r: _build_tree(r, runs=RUNS))
    add("cross_run_timing_only_differs_still_passes", True, None,
        lambda r: _build_tree(r, runs=RUNS, timing_salt_by_run={RUNS[0]: 0, RUNS[1]: 9999}))
    broken("dispatch_overkeyed", "dispatch keys", m_overkeyed_dispatch)
    broken("gated_case_line_overkeyed", "case line keys", m_overkeyed_gated_case_line)
    broken("gated_case_line_leaks_timing", "case line keys", m_gated_leaks_timing)
    broken("status_counts_wrong", "dispatch status counts", m_case_status_counts_wrong)
    broken("cross_run_gated_repeat_broken", "byte-exact gated repeat", m_run02_gated_result_differs)
    broken("cross_run_authored_hash_differs", "inputs frozen-hash binding",
          m_run02_authored_hash_differs)
    broken("raw_extra_file", "closed raw", m_raw_extra_file)
    broken("case_line_missing", "result line count", m_case_line_missing)
    broken("case_echo_tampered", "case matrix echo", m_case_echo_tampered)
    broken("authored_hash_drift", "contract hash drift", m_authored_drift)

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
        _build_tree(s0, runs=(), pre_gpu=True)
        try:
            gate_preflight(s0); step("S0 --preflight (contracted)", True)
        except SystemExit as e:
            step("S0 --preflight (contracted)", False, str(e))
        try:
            gate_between(s0); step("S0 --between-runs correctly REFUSED", False, "gate passed pre-GPU")
        except SystemExit:
            step("S0 --between-runs correctly REFUSED", True)
        try:
            gate_captured(s0); step("S0 --captured correctly REFUSED", False, "gate passed pre-GPU")
        except SystemExit:
            step("S0 --captured correctly REFUSED", True)
        shutil.rmtree(s0, ignore_errors=True)

        s1 = scratch / "S1_run01"
        _build_tree(s1, runs=(RUNS[0],))
        try:
            gate_preflight(s1)
            step("S1 --preflight correctly REFUSED (raw present)", False, "passed with raw")
        except SystemExit:
            step("S1 --preflight correctly REFUSED (raw present)", True)
        try:
            gate_between(s1); step("S1 --between-runs (contracted)", True)
        except SystemExit as e:
            step("S1 --between-runs (contracted)", False, str(e))
        try:
            gate_captured(s1)
            step("S1 --captured correctly REFUSED (one run)", False, "passed with one run")
        except SystemExit:
            step("S1 --captured correctly REFUSED (one run)", True)
        shutil.rmtree(s1, ignore_errors=True)

        s2 = scratch / "S2_run02"
        _build_tree(s2, runs=RUNS)
        try:
            gate_between(s2)
            step("S2 --between-runs correctly REFUSED (two runs)", False, "passed with two")
        except SystemExit:
            step("S2 --between-runs correctly REFUSED (two runs)", True)
        try:
            gate_captured(s2); step("S2 --captured (contracted)", True)
        except SystemExit as e:
            step("S2 --captured (contracted)", False, str(e))
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
    elif a.between_runs:
        gate_between()
    elif a.captured:
        gate_captured()


if __name__ == "__main__":
    main()
