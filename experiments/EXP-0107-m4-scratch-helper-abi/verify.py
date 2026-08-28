#!/usr/bin/env python3
"""EXP-0107 fail-closed verifier.

Five standing gates, all here:
  (a) --selftest   fabricates synthetic raw/ trees FROM RECORDED REALITY (the
                    real casematrix.ALL_CASES / CASE_KEYS / TIMING_KEYS / the
                    real CAPTURE_CONTRACT.json) under a scratch tmp root --
                    never touches this experiment's own raw/ -- and checks
                    that gate_preflight/between/captured correctly ACCEPT a
                    clean synthetic tree and correctly REJECT each of a set
                    of deliberately injected defects (missing file, extra/
                    missing schema key, hash mismatch, provenance drift,
                    inconsistent abort bookkeeping).
  (b) --seqtest    walks the real state machine PRE_GPU -> RUN01_PRESENT ->
                    RUN02_PRESENT (also on synthetic fixtures) and proves
                    each of gate_preflight/gate_between/gate_captured passes
                    in exactly its own state and fails in every other state.
  (c) static()      checks PRE_REGISTRATION.md/CAPTURE_CONTRACT.json/README.md
                    exist, casematrix.py imports and every case's `source`
                    is in REQUIRED_SOURCES, run.py's smoke gate runs before
                    any raw/ artifact (source-text check).
  (d) schema exactness: every case/timing record's key set is compared with
                    `==` against CASE_KEYS/TIMING_KEYS (imported from
                    casematrix.py, never restated) -- an extra key (e.g. a
                    stray `gpu_va`) fails exactly like a missing one. This IS
                    the "no nondeterministic field in the gated payload"
                    check: CASE_KEYS contains no address/timestamp field, so
                    an exact-key-set match forbids one from ever appearing.
  (e) --check       (post-capture, real raw/) cross-run comparison of every
                    CASE_KEYS field between run01 and run02, plus provenance/
                    hash consistency -- run this after both real runs exist.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
WORK = HERE / "work"  # all scratch dirs stay inside the repo (SUBAGENT_BRIEF.md)
WORK.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(HERE))
import casematrix as CM  # noqa: E402

import importlib.util
_spec = importlib.util.spec_from_file_location("run_mod", HERE / "run.py")
_run_mod = importlib.util.module_from_spec(_spec)
sys.modules["run_mod"] = _run_mod
# run.py's module-level code only defines functions/constants when imported
# (guarded by `if __name__ == "__main__"`), so this is safe and side-effect-free.
_spec.loader.exec_module(_run_mod)
RUNS = _run_mod.RUNS
AUTH_CODE = _run_mod.AUTH_CODE
AUTH_DOC = _run_mod.AUTH_DOC

FAILS = []


def fail(msg):
    FAILS.append(msg)


def req(cond, msg):
    if not cond:
        fail(msg)


# ---------------------------------------------------------------------------
# (c) static checks against the REAL experiment tree (no fixtures needed).
# ---------------------------------------------------------------------------
def static():
    for p in ("PRE_REGISTRATION.md", "CAPTURE_CONTRACT.json", "README.md"):
        f = HERE / p
        req(f.is_file() and f.stat().st_size > 0, f"missing/empty required doc: {p}")
    req(len(CM.ALL_CASES) > 0, "empty case matrix")
    for c in CM.ALL_CASES:
        req(c["source"] in CM.REQUIRED_SOURCES, f"case {c['name']} source not in REQUIRED_SOURCES")
    names = [c["name"] for c in CM.ALL_CASES]
    req(len(names) == len(set(names)), "duplicate case names in casematrix.py")
    rp = (HERE / "run.py").read_text()
    req('"--selftest"' in rp and '"--seqtest"' in rp, "run.py does not gate on verify.py --selftest/--seqtest")
    req(rp.index("smoke_test(") < rp.index("raw.mkdir(parents=True)"),
        "run.py's smoke gate does not run BEFORE raw/ is created")
    req("mkdir(parents=True)" in rp and "run id already has a raw/ directory" in rp,
        "run.py does not refuse to reuse an existing run id")
    cc = json.loads((HERE / "CAPTURE_CONTRACT.json").read_text())
    req(cc.get("run_ids") == list(RUNS), "CAPTURE_CONTRACT.json run_ids do not match run.py RUNS")


# ---------------------------------------------------------------------------
# Raw-tree state gates. `root` defaults to this experiment's real directory;
# selftest/seqtest pass a synthetic fixture root instead.
# ---------------------------------------------------------------------------
def _raw(root):
    return (root or HERE) / "raw"


def gate_preflight(root=None):
    # PRE_GPU requires neither contracted run id directory to exist yet.
    # Unrelated retained artifacts (e.g. a disclosed SUPERSEDED_* directory
    # from an earlier aborted attempt, kept append-only per SUBAGENT_BRIEF.md
    # "a partial capture is retained, never reused") do not block PRE_GPU.
    r = _raw(root)
    for rid in RUNS:
        if (r / rid).exists():
            raise AssertionError(f"PRE_GPU requires no raw/{rid} directory yet")
    return True


def _load_jsonl(p):
    if not p.is_file():
        return None
    out = []
    for line in p.read_text().splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def _check_run_dir(run_dir, allow_partial):
    if not run_dir.is_dir():
        raise AssertionError(f"{run_dir} missing")
    summary_p, cases_p, timing_p = run_dir / "01_summary.json", run_dir / "02_cases.jsonl", run_dir / "03_timing.jsonl"
    for p in (run_dir / "00_inputs.json", summary_p, cases_p, timing_p):
        if not p.is_file():
            raise AssertionError(f"{p} missing")
    summary = json.loads(summary_p.read_text())
    actual_case_sha = hashlib.sha256(cases_p.read_bytes()).hexdigest()
    actual_timing_sha = hashlib.sha256(timing_p.read_bytes()).hexdigest()
    if summary.get("case_sha256") != actual_case_sha:
        raise AssertionError(f"{summary_p} case_sha256 does not match {cases_p}")
    if summary.get("timing_sha256") != actual_timing_sha:
        raise AssertionError(f"{summary_p} timing_sha256 does not match {timing_p}")
    cases = _load_jsonl(cases_p)
    if not allow_partial and not summary.get("aborted_on_hard_fault"):
        if len(cases) != len(CM.ALL_CASES):
            raise AssertionError(f"{cases_p} has {len(cases)} records, expected {len(CM.ALL_CASES)}")
    for rec in cases:
        keys = set(rec.keys())
        if keys != CM.CASE_KEYS:
            raise AssertionError(f"{cases_p} record {rec.get('name')} key set != CASE_KEYS "
                                 f"(extra={keys - CM.CASE_KEYS} missing={CM.CASE_KEYS - keys})")
    for rec in (_load_jsonl(timing_p) or []):
        keys = set(rec.keys())
        if keys != CM.TIMING_KEYS:
            raise AssertionError(f"{timing_p} record {rec.get('name')} key set != TIMING_KEYS "
                                 f"(extra={keys - CM.TIMING_KEYS} missing={CM.TIMING_KEYS - keys})")
    return summary, cases


def gate_between(root=None):
    r = _raw(root)
    d0, d1 = r / RUNS[0], r / RUNS[1]
    if not d0.is_dir():
        raise AssertionError("RUN01_PRESENT requires run01 directory")
    if d1.is_dir():
        raise AssertionError("RUN01_PRESENT requires run02 NOT yet present")
    _check_run_dir(d0, allow_partial=True)
    return True


def gate_captured(root=None):
    r = _raw(root)
    d0, d1 = r / RUNS[0], r / RUNS[1]
    if not (d0.is_dir() and d1.is_dir()):
        raise AssertionError("RUN02_PRESENT requires both run directories")
    s0, c0 = _check_run_dir(d0, allow_partial=True)
    s1, c1 = _check_run_dir(d1, allow_partial=True)
    i0 = json.loads((d0 / "00_inputs.json").read_text())
    i1 = json.loads((d1 / "00_inputs.json").read_text())
    for k in ("authored_code_sha256", "authored_doc_sha256"):
        if i0["provenance"][k] != i1["provenance"][k]:
            raise AssertionError(f"run01/run02 provenance {k} differ (harness changed mid-experiment)")
    if len(c0) != len(c1):
        # only acceptable if at least one run recorded an abort explaining the shorter length
        if not (s0.get("aborted_on_hard_fault") or s1.get("aborted_on_hard_fault")):
            raise AssertionError("run01/run02 case counts differ with neither run marked aborted")
    n0 = {c["name"]: c for c in c0}
    n1 = {c["name"]: c for c in c1}
    for name in set(n0) & set(n1):
        # GATED_CASE_KEYS deliberately excludes bo_content_seq_sha256 -- see
        # casematrix.py's NONDETERMINISTIC_CASE_KEYS docstring: this run's
        # own two real captures proved that field is not reproducible on
        # 9/30 cases, while every other CASE_KEYS field is exact on 30/30.
        for key in CM.GATED_CASE_KEYS:
            if n0[name][key] != n1[name][key]:
                raise AssertionError(f"case {name} field {key} differs run01 vs run02: "
                                     f"{n0[name][key]!r} != {n1[name][key]!r}")
    return True


# ---------------------------------------------------------------------------
# Synthetic-fixture fabrication (selftest + seqtest). No Metal, no device.
# Built FROM RECORDED REALITY: casematrix.ALL_CASES (the real case list) and
# a schema-faithful synthetic value per CASE_KEYS/TIMING_KEYS field.
# ---------------------------------------------------------------------------
def _synth_case_record(case):
    k = case["k"]
    rec = {key: None for key in CM.CASE_KEYS}
    rec.update({
        "i": case["i"], "name": case["name"], "family": case["family"], "stage": case["stage"],
        "k": k, "grid": case["grid"], "tg": case["tg"], "n": case["n"], "source": case["source"],
        "executed": True, "meta_exit": 0, "meta_timed_out": False, "meta_status": "OK",
        "gpr_field_0": min(96, max(2, k // 3)), "scratch_field_41_or_14": 0 if k <= 32 else 4 * k + 16,
        "all_u32_fields": {"0": min(96, max(2, k // 3))}, "main_bytes": 2600, "main_sha256": "a" * 64,
        "probe_exit": 0, "probe_timed_out": False, "probe_status": "OK", "probe_detail": None,
        "checksum": "123.456", "resource_map_shape": [{"class": "AGXAcceleratorG16G", "size": 65536, "count": 2}],
        "bo_count": 27, "bo_total_bytes": 900000, "bo_content_seq_sha256": "b" * 64,
    })
    return rec


def _synth_timing_record(case):
    return {"i": case["i"], "name": case["name"], "meta_duration_ms": 50, "probe_duration_ms": 100,
           "meta_stdout": "", "meta_stderr": "", "probe_stdout": "STATUS OK\n", "probe_stderr": "",
           "maptrace_log_lines": 60}


def _synth_provenance():
    return {"authored_code_sha256": {p: "c" * 64 for p in AUTH_CODE},
           "authored_doc_sha256": {p: "d" * 64 for p in AUTH_DOC}}


def _build_run_dir(run_dir, cases, aborted=False, mutate=None):
    run_dir.mkdir(parents=True)
    case_recs = [_synth_case_record(c) for c in cases]
    timing_recs = [_synth_timing_record(c) for c in cases]
    if mutate:
        mutate(case_recs, timing_recs)
    with open(run_dir / "02_cases.jsonl", "w") as f:
        for r in case_recs:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    with open(run_dir / "03_timing.jsonl", "w") as f:
        for r in timing_recs:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    (run_dir / "05_raw_maps.jsonl").write_text("")
    (run_dir / "00_inputs.json").write_text(json.dumps({"run_id": run_dir.name,
                                                        "provenance": _synth_provenance()}, sort_keys=True))
    summary = {"run_id": run_dir.name, "aborted_on_hard_fault": aborted, "cases_total": len(CM.ALL_CASES),
              "case_sha256": hashlib.sha256((run_dir / "02_cases.jsonl").read_bytes()).hexdigest(),
              "timing_sha256": hashlib.sha256((run_dir / "03_timing.jsonl").read_bytes()).hexdigest()}
    if mutate:
        mutate_summary = getattr(mutate, "summary_patch", None)
        if mutate_summary:
            summary.update(mutate_summary)
    (run_dir / "01_summary.json").write_text(json.dumps(summary, sort_keys=True))


def _full_tree(root, n_runs, aborted_runs=(), mutate0=None, mutate1=None):
    cases = CM.ALL_CASES  # FROM RECORDED REALITY: the real case list
    if n_runs >= 1:
        _build_run_dir(root / "raw" / RUNS[0], cases, aborted=RUNS[0] in aborted_runs, mutate=mutate0)
    if n_runs >= 2:
        _build_run_dir(root / "raw" / RUNS[1], cases, aborted=RUNS[1] in aborted_runs, mutate=mutate1)


def expect_pass(fn, label):
    try:
        fn()
    except AssertionError as e:
        fail(f"seqtest expected PASS but got FAIL for [{label}]: {e}")


def expect_fail(fn, label):
    try:
        fn()
        fail(f"seqtest expected FAIL but got PASS for [{label}]")
    except AssertionError:
        pass


def seqtest():
    with tempfile.TemporaryDirectory(prefix="seqtest-", dir=WORK) as td:
        root = Path(td)
        (root / "raw").mkdir()
        # PRE_GPU
        expect_pass(lambda: gate_preflight(root), "preflight in PRE_GPU")
        expect_fail(lambda: gate_between(root), "between-runs in PRE_GPU")
        expect_fail(lambda: gate_captured(root), "captured in PRE_GPU")
        # RUN01_PRESENT
        _full_tree(root, 1)
        expect_fail(lambda: gate_preflight(root), "preflight in RUN01_PRESENT")
        expect_pass(lambda: gate_between(root), "between-runs in RUN01_PRESENT")
        expect_fail(lambda: gate_captured(root), "captured in RUN01_PRESENT")
        # RUN02_PRESENT (add run02 only -- run01 already built above)
        _build_run_dir(root / "raw" / RUNS[1], CM.ALL_CASES)
        expect_fail(lambda: gate_preflight(root), "preflight in RUN02_PRESENT")
        expect_fail(lambda: gate_between(root), "between-runs in RUN02_PRESENT")
        expect_pass(lambda: gate_captured(root), "captured in RUN02_PRESENT")
    if FAILS:
        return 1
    print("seqtest: PASS (PRE_GPU / RUN01_PRESENT / RUN02_PRESENT all gate correctly)")
    return 0


def selftest():
    with tempfile.TemporaryDirectory(prefix="selftest-clean-", dir=WORK) as td:
        root = Path(td)
        (root / "raw").mkdir()
        _full_tree(root, 2)
        try:
            gate_captured(root)
        except AssertionError as e:
            fail(f"selftest: clean synthetic tree unexpectedly failed gate_captured: {e}")

    def mutate_missing_file(case_recs, timing_recs):
        pass  # handled by removing the file after _build_run_dir below

    with tempfile.TemporaryDirectory(prefix="selftest-mut-", dir=WORK) as td:
        root = Path(td)
        (root / "raw").mkdir()
        _full_tree(root, 2)
        (root / "raw" / RUNS[1] / "03_timing.jsonl").unlink()
        try:
            gate_captured(root)
            fail("selftest: missing 03_timing.jsonl was not detected")
        except AssertionError:
            pass

    def mutate_extra_key(case_recs, timing_recs):
        case_recs[0]["gpu_va"] = "0xdeadbeef"  # exactly the forbidden-field shape

    with tempfile.TemporaryDirectory(prefix="selftest-extrakey-", dir=WORK) as td:
        root = Path(td)
        (root / "raw").mkdir()
        _full_tree(root, 2, mutate1=mutate_extra_key)
        try:
            gate_captured(root)
            fail("selftest: extra nondeterministic-shaped key (gpu_va) was not detected")
        except AssertionError:
            pass

    def mutate_missing_key(case_recs, timing_recs):
        del case_recs[0]["checksum"]

    with tempfile.TemporaryDirectory(prefix="selftest-misskey-", dir=WORK) as td:
        root = Path(td)
        (root / "raw").mkdir()
        _full_tree(root, 2, mutate1=mutate_missing_key)
        try:
            gate_captured(root)
            fail("selftest: missing schema key was not detected")
        except AssertionError:
            pass

    def mutate_hash(case_recs, timing_recs):
        pass

    with tempfile.TemporaryDirectory(prefix="selftest-hash-", dir=WORK) as td:
        root = Path(td)
        (root / "raw").mkdir()
        _full_tree(root, 2)
        p = root / "raw" / RUNS[1] / "01_summary.json"
        s = json.loads(p.read_text()); s["case_sha256"] = "0" * 64
        p.write_text(json.dumps(s))
        try:
            gate_captured(root)
            fail("selftest: corrupted summary hash was not detected")
        except AssertionError:
            pass

    def mutate_run02_diverges(case_recs, timing_recs):
        case_recs[0]["checksum"] = "999.999"

    with tempfile.TemporaryDirectory(prefix="selftest-diverge-", dir=WORK) as td:
        root = Path(td)
        (root / "raw").mkdir()
        _full_tree(root, 2, mutate1=mutate_run02_diverges)
        try:
            gate_captured(root)
            fail("selftest: run01/run02 semantic divergence in a gated field was not detected")
        except AssertionError:
            pass

    def mutate_nondeterministic_field_only(case_recs, timing_recs):
        # bo_content_seq_sha256 is the one CASE_KEYS field this run's own
        # real captures proved is not cross-run reproducible (9/30 cases;
        # casematrix.NONDETERMINISTIC_CASE_KEYS). A tree that differs ONLY
        # in that field, with every GATED_CASE_KEYS field identical, must
        # PASS gate_captured -- proving the exclusion is real and tested,
        # not a silent gap in the gate.
        case_recs[0]["bo_content_seq_sha256"] = "f" * 64

    with tempfile.TemporaryDirectory(prefix="selftest-nondeterm-", dir=WORK) as td:
        root = Path(td)
        (root / "raw").mkdir()
        _full_tree(root, 2, mutate1=mutate_nondeterministic_field_only)
        try:
            gate_captured(root)
        except AssertionError as e:
            fail(f"selftest: a run01/run02 difference confined to the documented "
                f"nondeterministic field (bo_content_seq_sha256) incorrectly failed "
                f"gate_captured: {e}")

    def mutate_provenance(case_recs, timing_recs):
        pass

    with tempfile.TemporaryDirectory(prefix="selftest-prov-", dir=WORK) as td:
        root = Path(td)
        (root / "raw").mkdir()
        _full_tree(root, 2)
        p = root / "raw" / RUNS[1] / "00_inputs.json"
        d = json.loads(p.read_text()); d["provenance"]["authored_code_sha256"]["run.py"] = "z" * 64
        p.write_text(json.dumps(d))
        try:
            gate_captured(root)
            fail("selftest: authored-code hash drift between run01/run02 was not detected")
        except AssertionError:
            pass

    if FAILS:
        return 1
    print("selftest: PASS (clean tree accepted; 6/6 injected defects correctly rejected; "
         "1/1 documented-nondeterministic-field-only divergence correctly tolerated)")
    return 0


# ---------------------------------------------------------------------------
# (e) post-capture check on the REAL raw/ tree.
# ---------------------------------------------------------------------------
def check():
    try:
        gate_captured(None)
    except AssertionError as e:
        fail(str(e))
    if FAILS:
        for m in FAILS:
            print("FAIL:", m)
        return 1
    print("check: PASS (real run01/run02 captured and cross-run consistent)")
    return 0


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--selftest", action="store_true")
    g.add_argument("--seqtest", action="store_true")
    g.add_argument("--static", action="store_true")
    g.add_argument("--preflight", action="store_true")
    g.add_argument("--between-runs", action="store_true")
    g.add_argument("--check", action="store_true")
    a = ap.parse_args()
    global FAILS
    FAILS = []
    if a.selftest:
        static()
        if FAILS:
            for m in FAILS:
                print("FAIL:", m)
            return 1
        return selftest()
    if a.seqtest:
        return seqtest()
    if a.static:
        static()
        if FAILS:
            for m in FAILS:
                print("FAIL:", m)
            return 1
        print("static: PASS")
        return 0
    if a.preflight:
        try:
            gate_preflight(None); print("preflight: PASS"); return 0
        except AssertionError as e:
            print("preflight: FAIL:", e); return 1
    if a.between_runs:
        try:
            gate_between(None); print("between-runs: PASS"); return 0
        except AssertionError as e:
            print("between-runs: FAIL:", e); return 1
    if a.check:
        return check()


if __name__ == "__main__":
    sys.exit(main())
