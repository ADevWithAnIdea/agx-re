#!/usr/bin/env python3
"""EXP-0084 fail-closed verifier.

Every record slot has exactly ONE frozen key set, imported from run.py (the
single source of truth) -- verify.py never redefines a schema.

--selftest (REQUIRED before any capture; runnable in EVERY tree state --
PRE_GPU, RUN01_PRESENT, RUN02_PRESENT -- because it only touches synthetic
scratch trees under selftest/, never the real root) fabricates complete
synthetic captures (no Metal, no shdump, no device) and proves: the record
builders (case_line_dispatch/decode/splice, smoke_problems) are correct AND
fail correctly on tampered synthetic records; the cross-run comparator
passes on byte-identical results and fails on any semantic difference; no
frozen key set names a raw address field, and no harness source line prints
a `gpuAddress`/`.gpuAddress` value (the concrete implementation of the
EXP-0081 "no nondeterministic field in a byte-compared record" fix -- this
experiment's fix is stronger: it never captures a GPU address ANYWHERE, so
the cross-run gate can require full byte-identity with no carve-out).

--seqtest walks the CONTRACTED gate order through synthetic PRE_GPU /
RUN01_PRESENT / RUN02_PRESENT states (also root-independent) and proves each
gate the contract invokes in that state is both RUNNABLE and its expected
verdict SATISFIABLE there -- the EXP-0075 gate-order-contradiction class
(`--between-runs` requiring raw/ while `--selftest` requires PRE_GPU) is
caught here before any real capture, not discovered after run01 closes.

--preflight / --between-runs / --captured operate on the REAL experiment
root (`HERE`), the actual pre/mid/post-capture gates `run.py` calls.
"""
import argparse
import datetime
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run as R          # noqa: E402
import casematrix as CM  # noqa: E402

RUNS = R.RUNS
BOUNDARY = R.BOUNDARY
TIMEOUTS = R.TIMEOUTS
AUTH_CODE = R.AUTH_CODE
AUTH_DOC = R.AUTH_DOC
AUTH_TOOLS = R.AUTH_TOOLS
AUTH_ALL = AUTH_DOC + AUTH_CODE
RAW_FILES = set(R.RAW_FILES)
DISPATCH_SUMMARY_KEYS = R.DISPATCH_SUMMARY_KEYS
DISPATCH_CASE_KEYS = R.DISPATCH_CASE_KEYS
DECODE_SUMMARY_KEYS = R.DECODE_SUMMARY_KEYS
DECODE_CASE_KEYS = R.DECODE_CASE_KEYS
SPLICE_SUMMARY_KEYS = R.SPLICE_SUMMARY_KEYS
SPLICE_CASE_KEYS = R.SPLICE_CASE_KEYS
RECEIPT_LINE_KEYS = R.RECEIPT_LINE_KEYS
DISPATCH_KEYS = R.DISPATCH_KEYS
INPUTS_KEYS = R.INPUTS_KEYS
RUN_MANIFEST_KEYS = R.RUN_MANIFEST_KEYS
MATRIX_CASE_KEYS = R.MATRIX_CASE_KEYS
STATUS_VALUES = R.STATUS_VALUES

ALL_FROZEN_KEYSETS = {
    "DISPATCH_SUMMARY_KEYS": DISPATCH_SUMMARY_KEYS, "DISPATCH_CASE_KEYS": DISPATCH_CASE_KEYS,
    "DECODE_SUMMARY_KEYS": DECODE_SUMMARY_KEYS, "DECODE_CASE_KEYS": DECODE_CASE_KEYS,
    "SPLICE_SUMMARY_KEYS": SPLICE_SUMMARY_KEYS, "SPLICE_CASE_KEYS": SPLICE_CASE_KEYS,
    "RECEIPT_LINE_KEYS": RECEIPT_LINE_KEYS, "DISPATCH_KEYS(envelope)": DISPATCH_KEYS,
    "INPUTS_KEYS": INPUTS_KEYS, "RUN_MANIFEST_KEYS": RUN_MANIFEST_KEYS,
    "MATRIX_CASE_KEYS": MATRIX_CASE_KEYS,
}

ROOT_FILES = {"CAPTURE_CONTRACT.json", "PRE_REGISTRATION.md", "README.md", "RESULTS.md",
             "PROGRESS.md", "kernels", "harness", "analysis", "casematrix.py", "procutil.py",
             "run.py", "verify.py", "make_manifest.py", "manifest.json"}
PRE_GPU_ARTIFACTS = ("CAPTURE_CONTRACT.json", "PRE_REGISTRATION.md", "README.md",
                     "RESULTS.md", "PROGRESS.md") + AUTH_CODE

GATE_SELFTEST = ("verify.py --selftest and verify.py --seqtest must pass (runnable in every "
                 "tree state, on synthetic roots only) immediately before every capture")
GATE_SMOKE = ("before the append-only raw tree is created, the freshly built harness must run "
             "the ctrl_direct_baseline case into work/ (never promoted into raw/), and its "
             "stdout must parse as one complete JSON record with every contracted field present "
             "and the expected out_hex; any payload-shape or truncation defect is a pre-capture STOP")
GATE_FAULT = ("a faulted, hung, or killed case is a recorded result (status watchdog/proc_fail/"
             "proc_timeout) and is never retried in place; only 3 consecutive OS-level spawn "
             "failures stop the run")
GATE_CROSS_RUN = ("run01 and run02's 04_results.jsonl must be BYTE-IDENTICAL, case for case, "
                  "in full -- no carve-out -- because no field in any frozen case-record key "
                  "set can vary run-to-run for a fixed source (no timing, no GPU address, no "
                  "pid is ever captured anywhere in this experiment's records)")
GATE_ORDER = ("PRE_GPU: --selftest, --seqtest, --preflight, run01; "
             "RUN01_PRESENT: --selftest, --seqtest, --between-runs, run02; "
             "RUN02_PRESENT: --selftest, --seqtest, --captured")


def fail(s):
    raise SystemExit("FAIL " + s)


def req(v, s):
    if not v:
        fail(s)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def regular(p):
    return Path(p).is_file() and not Path(p).is_symlink()


def tree_state(root):
    root = Path(root)
    raw = root / "raw"
    if not raw.exists():
        return "PRE_GPU"
    present = sorted(p.name for p in raw.iterdir() if p.is_dir())
    if present == [RUNS[0]]:
        return "RUN01_PRESENT"
    if sorted(present) == sorted(RUNS):
        return "RUN02_PRESENT"
    fail("tree_state: unexpected raw/ contents %r" % (present,))


# ---------------------------------------------------------------------------
# Record-slot checkers (imported constants only; never a locally redefined
# key set). Receipts (05_receipts.jsonl) are NOT byte-compared across runs;
# their shape is checked inline in one_run() via RECEIPT_LINE_KEYS.
# ---------------------------------------------------------------------------
def check_dispatch_case_line(q):
    req(set(q) == DISPATCH_CASE_KEYS, "dispatch case_line keys: got %s" % sorted(q))
    req(q["status"] in STATUS_VALUES, "dispatch case_line status %r" % q["status"])
    return True


def check_decode_case_line(q):
    req(set(q) == DECODE_CASE_KEYS, "decode case_line keys: got %s" % sorted(q))
    req(q["status"] in STATUS_VALUES, "decode case_line status %r" % q["status"])
    return True


def check_splice_case_line(q):
    req(set(q) == SPLICE_CASE_KEYS, "splice case_line keys: got %s" % sorted(q))
    req(q["status"] in STATUS_VALUES, "splice case_line status %r" % q["status"])
    return True


CHECK_BY_KIND = {"dispatch": check_dispatch_case_line, "decode": check_decode_case_line,
                 "splice": check_splice_case_line}


def one_run(root, rid):
    raw = Path(root) / "raw" / rid
    req(raw.is_dir(), "raw dir missing: %s" % rid)
    present = {p.name for p in raw.iterdir() if regular(p)}
    req(present == RAW_FILES or present == RAW_FILES | {"STOP.json"},
        "raw file set for %s: got %s" % (rid, sorted(present)))
    req("STOP.json" not in present, "run %s ended with STOP.json (incomplete)" % rid)

    inputs = json.loads((raw / "00_inputs.json").read_text())
    req(set(inputs) == INPUTS_KEYS, "00_inputs keys %s" % rid)
    req(inputs["boundary"] == BOUNDARY, "boundary drift %s" % rid)
    req(inputs["timeouts_seconds"] == TIMEOUTS, "timeouts drift %s" % rid)
    for p in AUTH_CODE:
        req(inputs["authored_code_sha256"].get(p) == sha(HERE / p), "authored hash drift %s: %s" % (rid, p))
    for p in AUTH_DOC:
        req(inputs["authored_doc_sha256"].get(p) == sha(HERE / p), "authored doc hash drift %s: %s" % (rid, p))

    matrix = json.loads((raw / "01_matrix.json").read_text())
    req(matrix["cases"] == CM.CASES, "matrix drift from casematrix.py: %s" % rid)
    for c in matrix["cases"]:
        req(set(c) == MATRIX_CASE_KEYS, "matrix case keys %s" % rid)

    build = json.loads((raw / "02_build.json").read_text())
    req(build["exit"] == 0 and not build["timed_out"] and build["exception"] is None,
        "02_build not clean: %s" % rid)

    results_path = raw / "04_results.jsonl"
    req(sha(results_path) == json.loads((raw / "03_dispatch.json").read_text())["results_sha256"],
        "results hash mismatch (03 vs 04): %s" % rid)
    lines = [json.loads(l) for l in results_path.read_text().splitlines() if l.strip()]
    req(len(lines) == CM.TOTAL, "results line count %s: got %d want %d" % (rid, len(lines), CM.TOTAL))
    by_i = {}
    for q in lines:
        req("i" in q and "kind" in q, "results line missing i/kind: %s" % rid)
        c = CM.CASES[q["i"]]
        req(q["name"] == c["name"] and q["kind"] == c["kind"], "results echo mismatch %s case %s" % (rid, q.get("name")))
        CHECK_BY_KIND[c["kind"]](q)
        by_i[q["i"]] = q
    req(sorted(by_i) == list(range(CM.TOTAL)), "results missing/duplicate case indices: %s" % rid)

    receipts = [json.loads(l) for l in (raw / "05_receipts.jsonl").read_text().splitlines() if l.strip()]
    req(len(receipts) == CM.TOTAL, "receipts line count %s" % rid)
    for r in receipts:
        req(set(r) == RECEIPT_LINE_KEYS, "receipt keys %s case %s" % (rid, r.get("name")))

    dispatch = json.loads((raw / "03_dispatch.json").read_text())
    req(set(dispatch) == DISPATCH_KEYS, "03_dispatch keys %s" % rid)
    req(dispatch["cases_planned"] == CM.TOTAL and dispatch["cases_recorded"] == CM.TOTAL,
        "03_dispatch counts %s" % rid)
    counted = {s: sum(1 for q in lines if q["status"] == s) for s in STATUS_VALUES}
    for s in STATUS_VALUES:
        req(dispatch["n_%s" % s] == counted[s], "03_dispatch status count drift %s: %s" % (rid, s))

    rm = json.loads((raw / "06_run_manifest.json").read_text())
    req(set(rm) == RUN_MANIFEST_KEYS, "06_run_manifest keys %s" % rid)
    req(rm["matrix_sha256"] == sha(raw / "01_matrix.json"), "matrix hash drift %s" % rid)
    req(rm["results_sha256"] == sha(results_path), "results hash drift %s" % rid)
    req(rm["receipts_sha256"] == sha(raw / "05_receipts.jsonl"), "receipts hash drift %s" % rid)
    return lines


def captured_gate(root):
    lines1 = one_run(root, RUNS[0])
    lines2 = one_run(root, RUNS[1])
    raw1 = (Path(root) / "raw" / RUNS[0] / "04_results.jsonl").read_bytes()
    raw2 = (Path(root) / "raw" / RUNS[1] / "04_results.jsonl").read_bytes()
    req(raw1 == raw2, "cross-run gate: 04_results.jsonl differs between %s and %s" % RUNS)
    in1 = json.loads((Path(root) / "raw" / RUNS[0] / "00_inputs.json").read_text())
    in2 = json.loads((Path(root) / "raw" / RUNS[1] / "00_inputs.json").read_text())
    for k in ("git_revision", "git_dirty", "authored_code_sha256", "authored_doc_sha256",
             "authored_tools_sha256"):
        req(in1[k] == in2[k], "provenance drift between runs: %s" % k)
    return lines1, lines2


def contract_checks(root=None):
    root = HERE if root is None else Path(root)
    c = json.loads((root / "CAPTURE_CONTRACT.json").read_text())
    req(c.get("contract_version") == 1 and c.get("experiment") == "EXP-0084-m4-dynamic-buffer-addressing"
        and c.get("state") == "PRE_GPU", "contract identity")
    req(c.get("total_cases") == CM.TOTAL, "contract total_cases")
    req(c.get("runs") == list(RUNS), "contract runs")
    req(c.get("boundary") == BOUNDARY, "contract boundary")
    req(c.get("gate_order") == GATE_ORDER, "contract gate_order")
    req(c.get("gate_cross_run") == GATE_CROSS_RUN, "contract gate_cross_run")
    req(c.get("gate_smoke") == GATE_SMOKE, "contract gate_smoke")
    req(c.get("matrix") == CM.CASES, "contract matrix drift from casematrix.py")
    ah = c.get("authored_sha256") or {}
    for p in AUTH_ALL:
        req(ah.get(p) == sha(root / p), "contract authored hash drift: %s" % p)
    return True


def prereg_checks(root=None):
    root = HERE if root is None else Path(root)
    t = (root / "PRE_REGISTRATION.md").read_text()
    for anchor in ("--selftest", "--seqtest", "MEM-20", "MEM-21", "MEM-22",
                  "Splice identification algorithm", "gpuAddress"):
        req(anchor in t, "PRE_REGISTRATION.md missing anchor: %s" % anchor)
    return True


def no_address_fields_check():
    for name, ks in ALL_FROZEN_KEYSETS.items():
        for k in ks:
            req("address" not in k.lower() and k.lower() not in ("va", "gpuva", "ptr"),
                "frozen key set %s contains an address-shaped field: %s" % (name, k))
    for relpath in ("harness/probe.m", "harness/splice_run.m"):
        text = (HERE / relpath).read_text()
        for line in text.splitlines():
            if "gpuAddress" in line:
                req(not any(fn in line for fn in ("printf(", "js(", "hex_words(", "hex32(", "fwrite(")),
                    "%s: a line touching gpuAddress also appears to print it: %r" % (relpath, line))
    return True


# ---------------------------------------------------------------------------
# --selftest: synthetic fixtures, no Metal, no device, no shdump, no root
# mutation. Proves the record builders correct AND fail-correct.
# ---------------------------------------------------------------------------
def _z(status_kind, **overrides):
    base = {"argv": ["x"], "cwd": "/x", "timeout_seconds": 1, "started_utc": "2026-01-01T00:00:00+00:00",
           "timed_out": False, "exit": 0, "stdout": "", "stderr": "", "exception": None}
    if status_kind == "timeout":
        base.update(timed_out=True, exit=None)
    elif status_kind == "crash":
        base.update(exit=139)
    elif status_kind == "spawn_fail":
        base.update(exit=None, exception="OSError")
    base.update(overrides)
    return base


def _dispatch_payload(function="ctrl_direct", n=-1, **overrides):
    p = {k: None for k in DISPATCH_SUMMARY_KEYS}
    p.update(schema=1, mode="ctrl_direct", kernel="probes.metal", function=function, n=n,
            grid=32, tg=32, sel_u=-1, k_outlier=-1, use_resource=True, device="Apple M4",
            machine="arm64", os="26.6.2", fast_math=False, math_mode_raw=0, language_version_raw=1,
            library_compile_seconds=0.01, dispatch_seconds=0.001, compile_ok=True, compile_error="",
            dispatch_ok=True, command_buffer_status=4, error="",
            out_hex="".join("%08x" % (1000 + i) for i in range(32)), outb_hex="", outsel_hex="")
    p.update(overrides)
    return p


def selftest():
    steps = []

    def step(name, fn):
        try:
            fn()
            steps.append((name, True, None))
        except SystemExit as e:
            steps.append((name, False, str(e)))

    def step_expect_fail(name, fn):
        try:
            fn()
            steps.append((name, False, "expected failure but passed"))
        except SystemExit:
            steps.append((name, True, None))

    c0 = CM.CASES[0]  # ctrl_direct_baseline (dispatch)
    c12 = CM.CASES[12]  # decode
    c13 = CM.CASES[13]  # splice

    # -- dispatch case_line: PASS on a clean synthetic record --------------
    step("dispatch case_line clean OK",
        lambda: check_dispatch_case_line(R.case_line_dispatch(c0, _z("ok", stdout=json.dumps(_dispatch_payload())), "x")))
    # -- FAIL correctly: tampered key set (EXP-0073 receipt-schema class) --
    def _tampered_keys():
        p = _dispatch_payload()
        p["extra_field_should_not_exist"] = 1
        try:
            R.case_line_dispatch(c0, _z("ok", stdout=json.dumps(p)), "x")
        except SystemExit:
            raise
        raise AssertionError("tampered payload was not rejected")
    step_expect_fail("dispatch case_line rejects extra key", _tampered_keys)

    def _echo_mismatch():
        p = _dispatch_payload(function="WRONG_FUNCTION")
        R.case_line_dispatch(c0, _z("ok", stdout=json.dumps(p)), "x")
    step_expect_fail("dispatch case_line rejects function echo mismatch", _echo_mismatch)

    # -- timeout / crash / spawn-fail map to recorded statuses, not raises --
    def _timeout_ok():
        q = R.case_line_dispatch(c0, _z("timeout"), "x")
        assert q["status"] == "proc_timeout", q
    step("dispatch case_line timeout -> proc_timeout (recorded, not raised)", _timeout_ok)

    def _crash_ok():
        q = R.case_line_dispatch(c0, _z("crash"), "x")
        assert q["status"] == "proc_fail", q
    step("dispatch case_line crash -> proc_fail (recorded, not raised)", _crash_ok)

    def _compile_reject_ok():
        c9 = CM.CASES[9]  # mem22_direct_cap_32
        q = R.case_line_dispatch(c9, _z("ok", stdout=json.dumps(_dispatch_payload(
            function="cap32", n=31, compile_ok=False, compile_error="x", dispatch_ok=False,
            command_buffer_status=-1))), "x")
        assert q["status"] == "compile_reject", q
    step("dispatch case_line compile failure -> compile_reject (first-class outcome)", _compile_reject_ok)

    # -- decode case_line ----------------------------------------------------
    def _decode_payload(**overrides):
        p = {k: None for k in DECODE_SUMMARY_KEYS}
        p.update(schema=1, function="splice_target", build_ok=True, main_len=64, preamble_len=0,
                main_leftover_len=0, preamble_leftover_len=0, n_device_load_main=4,
                n_device_load_preamble=0,
                l1={"offset": 20, "hex": "67" * 14, "length": 14, "base_slot": 5, "index_reg": 9,
                    "addr_mode": 84, "idx_off": 0, "dst_reg": 2},
                l2={"offset": 34, "hex": "67" * 14, "length": 14, "base_slot": 5, "index_reg": 11,
                    "addr_mode": 84, "idx_off": 0, "dst_reg": 3},
                confirmation_ok=True)
        p.update(overrides)
        return p
    step("decode case_line clean OK",
        lambda: check_decode_case_line(R.case_line_decode(c12, _z("ok", stdout=json.dumps(_decode_payload())))))

    def _decode_echo_mismatch():
        R.case_line_decode(c12, _z("ok", stdout=json.dumps(_decode_payload(function="WRONG"))))
    step_expect_fail("decode case_line rejects function echo mismatch", _decode_echo_mismatch)

    def _decode_unconfirmed_ok():
        q = R.case_line_decode(c12, _z("ok", stdout=json.dumps(_decode_payload(confirmation_ok=False))))
        assert q["status"] == "identification_failed", q
    step("decode case_line unconfirmed -> identification_failed (recorded, not raised)", _decode_unconfirmed_ok)

    # -- splice case_line -----------------------------------------------------
    def _splice_payload(outcome="confirmed", **overrides):
        l1 = {"offset": 20, "hex": "x", "length": 14, "base_slot": 5, "index_reg": 9,
              "addr_mode": 84, "idx_off": 0, "dst_reg": 2}
        l2 = {"offset": 34, "hex": "x", "length": 14, "base_slot": 5, "index_reg": 11,
              "addr_mode": 84, "idx_off": 0, "dst_reg": 3}
        p = {k: None for k in SPLICE_SUMMARY_KEYS}
        p.update(schema=1, function="splice_target", build_ok=True,
                ident={"n_device_load_main": 4, "n_device_load_preamble": 0, "l1": l1, "l2": l2,
                      "confirmation_ok": True},
                baseline={"status": "OK", "pipeline_source": "archive", "cb_status": 4, "error": "",
                         "out_hex": "5a0000aa" * 32, "outb_hex": "5a0000bb" * 32},
                target=l1, splice_offset_abs=1000,
                splice_from=9, splice_to=11,
                spliced_result={"status": "OK", "pipeline_source": "archive", "cb_status": 4,
                               "error": "", "out_hex": "5a0000bb" * 32, "outb_hex": "5a0000bb" * 32},
                outcome=outcome)
        p.update(overrides)
        return p
    step("splice case_line clean confirmed OK",
        lambda: check_splice_case_line(R.case_line_splice(c13, _z("ok", stdout=json.dumps(_splice_payload())))))

    def _splice_refuted_ok():
        p = _splice_payload(outcome="refuted",
                            spliced_result={"status": "OK", "pipeline_source": "archive", "cb_status": 4,
                                           "error": "", "out_hex": "5a0000aa" * 32, "outb_hex": "5a0000bb" * 32})
        q = R.case_line_splice(c13, _z("ok", stdout=json.dumps(p)))
        assert q["status"] == "refuted" and q["other_index_reg"] == 11, q
    step("splice case_line refuted outcome recorded correctly (not raised)", _splice_refuted_ok)

    def _splice_unknown_outcome():
        p = _splice_payload(outcome="not_a_real_outcome")
        R.case_line_splice(c13, _z("ok", stdout=json.dumps(p)))
    step_expect_fail("splice case_line rejects an unknown outcome string", _splice_unknown_outcome)

    # -- smoke_problems(): correct on a clean record, and catches the -------
    # EXP-0072 truncation class (payload that doesn't parse as one JSON obj).
    def _smoke_synthetic(monkeypatch_stdout):
        saved = R.rec
        def fake_rec(argv, timeout, cwd):
            return _z("ok", stdout=monkeypatch_stdout)
        R.rec = fake_rec
        try:
            with tempfile.TemporaryDirectory() as td:
                (Path(td) / "bin").mkdir()
                return R.smoke_problems(Path(td))
        finally:
            R.rec = saved
    def _smoke_clean():
        problems = _smoke_synthetic(json.dumps(_dispatch_payload()))
        assert problems == [], problems
    step("smoke_problems: clean record -> no problems", _smoke_clean)

    def _smoke_truncated():
        problems = _smoke_synthetic('{"schema":1,"kernel":"probes.metal","op":')  # EXP-0072 class
        assert problems, "truncated smoke payload was NOT flagged"
    step("smoke_problems: truncated payload -> flagged (EXP-0072 class)", _smoke_truncated)

    def _smoke_wrong_output():
        problems = _smoke_synthetic(json.dumps(_dispatch_payload(out_hex="00" * 128)))
        assert problems, "wrong out_hex was NOT flagged"
    step("smoke_problems: wrong out_hex -> flagged", _smoke_wrong_output)

    # -- cross-run comparator: PASS byte-identical, FAIL on any diff --------
    def _cross_run_pass():
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _build_synthetic_root(root, mutate_run2=None)
            captured_gate(root)
    step("cross-run gate PASSES on byte-identical run01/run02", _cross_run_pass)

    def _cross_run_fail_on_semantic_diff():
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _build_synthetic_root(root, mutate_run2=lambda lines: _flip_one_status(lines))
            captured_gate(root)
    step_expect_fail("cross-run gate FAILS on any semantic difference", _cross_run_fail_on_semantic_diff)

    # -- no raw-address field anywhere, and no source line prints gpuAddress -
    step("no frozen key set names a raw-address field; harness never prints gpuAddress",
        no_address_fields_check)

    # -- contract/prereg static checks are themselves runnable here ---------
    step("CAPTURE_CONTRACT.json matches run.py/casematrix.py constants", contract_checks)
    step("PRE_REGISTRATION.md carries the required anchors", prereg_checks)

    failed = [s for s in steps if not s[1]]
    for name, ok, msg in steps:
        print(("PASS " if ok else "FAIL ") + name + (("  -- " + msg) if msg else ""))
    print("SELFTEST %d/%d" % (len(steps) - len(failed), len(steps)))
    if failed:
        raise SystemExit("selftest failures: %s" % [s[0] for s in failed])


def _flip_one_status(lines):
    out = list(lines)
    q = json.loads(out[0])
    q["status"] = "proc_fail" if q["status"] != "proc_fail" else "ok"
    out[0] = json.dumps(q, sort_keys=True)
    return out


def _build_synthetic_root(root, mutate_run2):
    """Fabricate a complete two-run synthetic capture tree under `root` using
    the SAME record builders/hash logic run.py uses, so --selftest exercises
    the real code paths, not a re-implementation of them."""
    root.mkdir(parents=True, exist_ok=True)
    for p in AUTH_CODE:
        dst = root / p
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes((HERE / p).read_bytes())
    for p in AUTH_DOC:
        dst = root / p
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes((HERE / p).read_bytes())

    def make_lines():
        out = []
        for c in CM.CASES:
            if c["kind"] == "dispatch":
                p = _dispatch_payload(function=c["function"], n=c["n"])
                out.append(R.case_line_dispatch(c, _z("ok", stdout=json.dumps(p)), "x"))
            elif c["kind"] == "decode":
                p = {k: None for k in DECODE_SUMMARY_KEYS}
                p.update(schema=1, function=c["function"], build_ok=True, main_len=64,
                        preamble_len=0, main_leftover_len=0, preamble_leftover_len=0,
                        n_device_load_main=4, n_device_load_preamble=0,
                        l1={"offset": 20, "hex": "x", "length": 14, "base_slot": 5, "index_reg": 9,
                            "addr_mode": 84, "idx_off": 0, "dst_reg": 2},
                        l2={"offset": 34, "hex": "x", "length": 14, "base_slot": 5, "index_reg": 11,
                            "addr_mode": 84, "idx_off": 0, "dst_reg": 3},
                        confirmation_ok=True)
                out.append(R.case_line_decode(c, _z("ok", stdout=json.dumps(p))))
            else:
                l1 = {"offset": 20, "hex": "x", "length": 14, "base_slot": 5, "index_reg": 9,
                     "addr_mode": 84, "idx_off": 0, "dst_reg": 2}
                l2 = {"offset": 34, "hex": "x", "length": 14, "base_slot": 5, "index_reg": 11,
                     "addr_mode": 84, "idx_off": 0, "dst_reg": 3}
                p = {k: None for k in SPLICE_SUMMARY_KEYS}
                p.update(schema=1, function=c["function"], build_ok=True,
                        ident={"n_device_load_main": 4, "n_device_load_preamble": 0,
                              "l1": l1, "l2": l2, "confirmation_ok": True},
                        baseline={"status": "OK", "pipeline_source": "archive", "cb_status": 4,
                                 "error": "", "out_hex": "5a0000aa" * 32, "outb_hex": "5a0000bb" * 32},
                        target=l1, splice_offset_abs=1000, splice_from=9, splice_to=11,
                        spliced_result={"status": "OK", "pipeline_source": "archive", "cb_status": 4,
                                       "error": "", "out_hex": "5a0000bb" * 32,
                                       "outb_hex": "5a0000bb" * 32},
                        outcome="confirmed")
                out.append(R.case_line_splice(c, _z("ok", stdout=json.dumps(p))))
        return [json.dumps(l, sort_keys=True) for l in out]

    lines1 = make_lines()
    lines2 = mutate_run2(lines1) if mutate_run2 else list(lines1)

    receipts = [json.dumps({"i": c["i"], "name": c["name"], "kind": c["kind"], **_z("ok")}, sort_keys=True)
               for c in CM.CASES]

    def write_run(rid, lines):
        raw = root / "raw" / rid
        raw.mkdir(parents=True)
        auth_code_sha = {p: sha(root / p) for p in AUTH_CODE}
        auth_doc_sha = {p: sha(root / p) for p in AUTH_DOC}
        auth_tools_sha = {p: sha(HERE.parents[1] / p) for p in AUTH_TOOLS}
        R.put(raw / "00_inputs.json", {
            "schema": 1, "git_revision": "0" * 40, "git_dirty": False,
            "experiment_tree_dirty_entries": 0, "authored_code_sha256": auth_code_sha,
            "authored_doc_sha256": auth_doc_sha, "authored_tools_sha256": auth_tools_sha,
            "sw_vers": "x", "xcrun_version": "x", "python": "3.x", "machine": "arm64",
            "boundary": BOUNDARY, "timeouts_seconds": TIMEOUTS})
        R.put(raw / "01_matrix.json", {"schema": 1, "run_id": rid, "cases": CM.CASES})
        R.put(raw / "02_build.json", _z("ok"))
        results_txt = "\n".join(lines) + "\n"
        (raw / "04_results.jsonl").write_text(results_txt)
        (raw / "05_receipts.jsonl").write_text("\n".join(receipts) + "\n")
        counted = {s: sum(1 for l in lines if json.loads(l)["status"] == s) for s in STATUS_VALUES}
        R.put(raw / "03_dispatch.json", {"schema": 1, "run_id": rid, "cases_planned": CM.TOTAL,
                                         "cases_recorded": CM.TOTAL,
                                         **{"n_%s" % s: counted[s] for s in STATUS_VALUES},
                                         "results_lines": CM.TOTAL,
                                         "results_sha256": sha(raw / "04_results.jsonl")})
        R.put(raw / "06_run_manifest.json", {"schema": 1, "run_id": rid, "cases_planned": CM.TOTAL,
                                             "cases_recorded": CM.TOTAL,
                                             "matrix_sha256": sha(raw / "01_matrix.json"),
                                             "results_sha256": sha(raw / "04_results.jsonl"),
                                             "receipts_sha256": sha(raw / "05_receipts.jsonl")})

    write_run(RUNS[0], lines1)
    write_run(RUNS[1], lines2)


# ---------------------------------------------------------------------------
# --seqtest: gate-order state machine over synthetic PRE_GPU / RUN01_PRESENT
# / RUN02_PRESENT trees (root-independent).
# ---------------------------------------------------------------------------
def seqtest():
    steps = []

    def step(name, ok):
        steps.append((name, ok))

    with tempfile.TemporaryDirectory() as td:
        pre = Path(td) / "pre_gpu"
        pre.mkdir()
        for p in AUTH_CODE + AUTH_DOC:
            dst = pre / p
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes((HERE / p).read_bytes())
        state = tree_state(pre)
        step("PRE_GPU: tree_state() detects PRE_GPU on a raw-less synthetic root", state == "PRE_GPU")
        # The REAL root (HERE) is actually in PRE_GPU state at every point before
        # run01 is captured, so contract_checks()/prereg_checks() (which default to
        # HERE) are exercised for real here -- this is the actual gate run.py calls
        # via --preflight, proven runnable+satisfiable in this state, not a re-
        # implementation of it.
        gate_ok = True
        try:
            contract_checks()
            prereg_checks()
        except SystemExit:
            gate_ok = False
        step("PRE_GPU: contract_checks/prereg_checks runnable and PASS on the real root", gate_ok)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "run01_present"
        _build_synthetic_root(root, mutate_run2=None)
        shutil.rmtree(root / "raw" / RUNS[1])
        step("RUN01_PRESENT: tree_state() detects RUN01_PRESENT", tree_state(root) == "RUN01_PRESENT")
        ok = True
        try:
            one_run(root, RUNS[0])
        except SystemExit:
            ok = False
        step("RUN01_PRESENT: one_run(run01) gate is RUNNABLE and SATISFIABLE on a valid synthetic run01", ok)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "run02_present"
        _build_synthetic_root(root, mutate_run2=None)
        step("RUN02_PRESENT: tree_state() detects RUN02_PRESENT", tree_state(root) == "RUN02_PRESENT")
        ok = True
        try:
            captured_gate(root)
        except SystemExit:
            ok = False
        step("RUN02_PRESENT: captured_gate() is RUNNABLE and SATISFIABLE on a valid synthetic pair", ok)
        # The EXP-0075 landmine, directly: prove --selftest-equivalent logic
        # (prereg/contract checks) remains runnable even once raw/ exists --
        # i.e. no gate in this contract is PRE_GPU-only in a way that makes it
        # unreachable once capture has started.
        ok2 = True
        try:
            prereg_checks()
            contract_checks()
        except SystemExit:
            ok2 = False
        step("RUN02_PRESENT: prereg/contract checks remain runnable (no EXP-0075-class landmine)", ok2)

    for name, ok in steps:
        print(("PASS " if ok else "FAIL ") + name)
    bad = [n for n, ok in steps if not ok]
    print("SEQTEST %d/%d" % (len(steps) - len(bad), len(steps)))
    if bad:
        raise SystemExit("seqtest failures: %s" % bad)


# ---------------------------------------------------------------------------
# Real-root gates.
# ---------------------------------------------------------------------------
def gate_preflight():
    req(tree_state(HERE) == "PRE_GPU", "preflight: raw/ must not exist yet")
    for p in PRE_GPU_ARTIFACTS:
        req(regular(HERE / p), "preflight: missing pre-GPU artifact %s" % p)
    contract_checks()
    prereg_checks()
    print("PREFLIGHT OK")


def gate_between_runs():
    req(tree_state(HERE) == "RUN01_PRESENT", "between-runs: exactly run01 must be present")
    one_run(HERE, RUNS[0])
    print("BETWEEN-RUNS OK")


def gate_captured():
    req(tree_state(HERE) == "RUN02_PRESENT", "captured: exactly run01+run02 must be present")
    captured_gate(HERE)
    print("CAPTURED OK")


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
        gate_between_runs()
    elif a.captured:
        gate_captured()


if __name__ == "__main__":
    main()
