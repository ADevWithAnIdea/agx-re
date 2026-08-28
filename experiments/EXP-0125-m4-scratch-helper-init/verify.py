#!/usr/bin/env python3
"""EXP-0125 fail-closed verifier.

Five standing gates (SUBAGENT_BRIEF.md / dispatch brief):
  (a) --selftest   fabricates synthetic raw/ trees FROM RECORDED REALITY (the
                    real casematrix constants: I_VARIANTS/CHECKPOINT_LABELS,
                    B_STAGES + the real deterministic run_bisection()
                    algorithm, C_LEVELS; and the real *_KEYS schemas) under a
                    scratch tmp root -- never touches this experiment's own
                    raw/ -- and checks that gate_captured correctly ACCEPTS a
                    clean synthetic tree and correctly REJECTS each of a set
                    of deliberately injected defects.
  (b) --seqtest    walks PRE_GPU -> RUN01_PRESENT -> RUN02_PRESENT (synthetic
                    fixtures) and proves each of gate_preflight/gate_between/
                    gate_captured passes in exactly its own state.
  (c) static()      required docs exist; casematrix.py imports; I_K == C_K
                    (both must equal kernels/kernelgen.py's FIXED_K, or the I
                    and C families would silently diverge on which "heavy"
                    kernel they mean); run.py's smoke gate runs before any
                    raw/ artifact; run.py refuses to reuse a run id.
  (d) schema exactness: every record's key set is compared with `==` against
                    the matching *_KEYS constant (imported from casematrix.py,
                    never restated) for ALL FIVE gated files
                    (02a_i_checkpoints, 02b_i_summary, 04a_b_trials,
                    04b_b_results, 05_c_levels). None of those five schemas
                    contains a raw GPU address or wall-clock/mach_absolute_time
                    field -- an injected one (e.g. a stray "gpu_va" or
                    "mach_time" key) fails exactly like a missing field. This
                    IS the "no nondeterministic field in the gated payload"
                    check.
  (e) --check       (post-capture, real raw/) cross-run comparison of every
                    gated field across all five files between run01/run02.
"""
import argparse
import hashlib
import json
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
# (c) static checks against the REAL experiment tree.
# ---------------------------------------------------------------------------
def static():
    for p in ("PRE_REGISTRATION.md", "CAPTURE_CONTRACT.json", "README.md"):
        f = HERE / p
        req(f.is_file() and f.stat().st_size > 0, f"missing/empty required doc: {p}")
    req(len(CM.I_VARIANTS) == 2 and len(CM.CHECKPOINT_LABELS) == 6, "I family shape drifted")
    req(len(CM.B_STAGES) == 3, "B family shape drifted")
    req(len(CM.C_LEVELS) >= 3, "C family shape drifted")

    kg = (HERE / "kernels/kernelgen.py").read_text()
    m = None
    for line in kg.splitlines():
        if line.strip().startswith("FIXED_K"):
            m = line
            break
    req(m is not None, "kernels/kernelgen.py missing FIXED_K")
    fixed_k = int(m.split("=")[1].strip())
    req(CM.I_K == fixed_k, f"casematrix.I_K ({CM.I_K}) != kernelgen.FIXED_K ({fixed_k})")
    req(CM.C_K == fixed_k, f"casematrix.C_K ({CM.C_K}) != kernelgen.FIXED_K ({fixed_k})")

    rp = (HERE / "run.py").read_text()
    req('"--selftest"' in rp and '"--seqtest"' in rp, "run.py does not gate on verify.py --selftest/--seqtest")
    req(rp.index("smoke_test(") < rp.index('raw.mkdir(parents=True)'),
        "run.py's smoke gate does not run BEFORE raw/ is created")
    req("run id already has a raw/ directory" in rp,
        "run.py does not refuse to reuse an existing run id")
    cc = json.loads((HERE / "CAPTURE_CONTRACT.json").read_text())
    req(cc.get("run_ids") == list(RUNS), "CAPTURE_CONTRACT.json run_ids do not match run.py RUNS")


# ---------------------------------------------------------------------------
# Raw-tree state gates.
# ---------------------------------------------------------------------------
def _raw(root):
    return (root or HERE) / "raw"


def gate_preflight(root=None):
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


FILES = {
    "i_checkpoints": ("02a_i_checkpoints.jsonl", "i_checkpoints_sha256", CM.I_CHECKPOINT_KEYS),
    "i_summary": ("02b_i_summary.jsonl", "i_summary_sha256", CM.I_SUMMARY_KEYS),
    "b_trials": ("04a_b_trials.jsonl", "b_trials_sha256", CM.B_TRIAL_KEYS),
    "b_results": ("04b_b_results.jsonl", "b_results_sha256", CM.B_RESULT_KEYS),
    "c_levels": ("05_c_levels.jsonl", "c_levels_sha256", CM.C_TRIAL_KEYS),
}


def _check_run_dir(run_dir):
    if not run_dir.is_dir():
        raise AssertionError(f"{run_dir} missing")
    summary_p = run_dir / "01_summary.json"
    for _, (fname, _, _) in FILES.items():
        if not (run_dir / fname).is_file():
            raise AssertionError(f"{run_dir / fname} missing")
    if not (run_dir / "00_inputs.json").is_file():
        raise AssertionError(f"{run_dir}/00_inputs.json missing")
    if not summary_p.is_file():
        raise AssertionError(f"{summary_p} missing")
    summary = json.loads(summary_p.read_text())
    parsed = {}
    for key, (fname, hashkey, keyset) in FILES.items():
        p = run_dir / fname
        actual = hashlib.sha256(p.read_bytes()).hexdigest()
        if summary.get(hashkey) != actual:
            raise AssertionError(f"{p} sha256 does not match 01_summary.json[{hashkey}]")
        recs = _load_jsonl(p) or []
        for rec in recs:
            keys = set(rec.keys())
            if keys != keyset:
                raise AssertionError(f"{p} record {rec} key set != {key.upper()}_KEYS "
                                     f"(extra={keys - keyset} missing={keyset - keys})")
        parsed[key] = recs
    return summary, parsed


def gate_between(root=None):
    r = _raw(root)
    d0, d1 = r / RUNS[0], r / RUNS[1]
    if not d0.is_dir():
        raise AssertionError("RUN01_PRESENT requires run01 directory")
    if d1.is_dir():
        raise AssertionError("RUN01_PRESENT requires run02 NOT yet present")
    _check_run_dir(d0)
    return True


def gate_captured(root=None):
    r = _raw(root)
    d0, d1 = r / RUNS[0], r / RUNS[1]
    if not (d0.is_dir() and d1.is_dir()):
        raise AssertionError("RUN02_PRESENT requires both run directories")
    s0, p0 = _check_run_dir(d0)
    s1, p1 = _check_run_dir(d1)
    i0 = json.loads((d0 / "00_inputs.json").read_text())
    i1 = json.loads((d1 / "00_inputs.json").read_text())
    for k in ("authored_code_sha256", "authored_doc_sha256"):
        if i0["provenance"][k] != i1["provenance"][k]:
            raise AssertionError(f"run01/run02 provenance {k} differ (harness changed mid-experiment)")

    if not (s0.get("aborted_on_hard_fault") or s1.get("aborted_on_hard_fault")):
        for key in FILES:
            if len(p0[key]) != len(p1[key]):
                raise AssertionError(f"{key}: run01/run02 record counts differ "
                                     f"({len(p0[key])} vs {len(p1[key])}) with neither aborted")

    # Cross-run field comparison, keyed per family:
    def index_by(recs, keyfn):
        return {keyfn(r): r for r in recs}

    i_idx0 = index_by(p0["i_checkpoints"], lambda r: (r["case"], r["cp_idx"]))
    i_idx1 = index_by(p1["i_checkpoints"], lambda r: (r["case"], r["cp_idx"]))
    for k in set(i_idx0) & set(i_idx1):
        for field in CM.I_CHECKPOINT_KEYS:
            if i_idx0[k][field] != i_idx1[k][field]:
                raise AssertionError(f"i_checkpoints {k} field {field} differs: "
                                     f"{i_idx0[k][field]!r} != {i_idx1[k][field]!r}")

    is_idx0 = index_by(p0["i_summary"], lambda r: r["case"])
    is_idx1 = index_by(p1["i_summary"], lambda r: r["case"])
    for k in set(is_idx0) & set(is_idx1):
        for field in CM.I_SUMMARY_KEYS:
            if is_idx0[k][field] != is_idx1[k][field]:
                raise AssertionError(f"i_summary {k} field {field} differs: "
                                     f"{is_idx0[k][field]!r} != {is_idx1[k][field]!r}")

    bt_idx0 = index_by(p0["b_trials"], lambda r: (r["stage"], r["step"]))
    bt_idx1 = index_by(p1["b_trials"], lambda r: (r["stage"], r["step"]))
    for k in set(bt_idx0) & set(bt_idx1):
        for field in CM.B_TRIAL_KEYS:
            if bt_idx0[k][field] != bt_idx1[k][field]:
                raise AssertionError(f"b_trials {k} field {field} differs: "
                                     f"{bt_idx0[k][field]!r} != {bt_idx1[k][field]!r}")

    br_idx0 = index_by(p0["b_results"], lambda r: r["stage"])
    br_idx1 = index_by(p1["b_results"], lambda r: r["stage"])
    for k in set(br_idx0) & set(br_idx1):
        for field in CM.B_RESULT_KEYS:
            if br_idx0[k][field] != br_idx1[k][field]:
                raise AssertionError(f"b_results {k} field {field} differs: "
                                     f"{br_idx0[k][field]!r} != {br_idx1[k][field]!r}")

    # c_levels (really: per-trial C-family records): only C_GATED_TRIAL_KEYS
    # is compared byte-for-byte. status/ok_queues/execfail_queues/
    # nonfinite_queues/checksum_mismatch are this experiment's own directly
    # observed nondeterministic fields (casematrix.py module docstring;
    # confirmed by repeated same-config trials during pre-capture
    # reconnaissance showing different outcomes) and are deliberately
    # excluded here, exactly as EXP-0107 excluded `bo_content_seq_sha256`.
    c_idx0 = index_by(p0["c_levels"], lambda r: (r["name"], r["trial"]))
    c_idx1 = index_by(p1["c_levels"], lambda r: (r["name"], r["trial"]))
    for k in set(c_idx0) & set(c_idx1):
        for field in CM.C_GATED_TRIAL_KEYS:
            if c_idx0[k][field] != c_idx1[k][field]:
                raise AssertionError(f"c_levels {k} field {field} differs: "
                                     f"{c_idx0[k][field]!r} != {c_idx1[k][field]!r}")
    return True


# ---------------------------------------------------------------------------
# Synthetic-fixture fabrication (selftest + seqtest). No Metal, no device.
# ---------------------------------------------------------------------------
def _synth_i(mutate_extra_key=False):
    recs, summ = [], []
    for v in CM.I_VARIANTS:
        case = f"I_{v}"
        for idx, label in enumerate(CM.CHECKPOINT_LABELS):
            nbo = 18 if idx < 4 else 27
            rec = {
                "case": case, "variant": v, "cp_idx": idx, "cp_label": label,
                "nbo": nbo, "bo_total_bytes": 900000 + nbo * 1000,
                "resource_map_shape": [{"class": "AGXAcceleratorG16G", "size": 65536, "count": 2}],
                "nshared": 0, "shared_addr0_present": False, "shared_addr1_present": False,
                "code_window_present": idx >= 2, "code_window_size": 65536 if idx >= 2 else None,
            }
            if mutate_extra_key:
                rec["gpu_va"] = "0xdeadbeef"
            recs.append(rec)
        summ.append({"case": case, "variant": v, "probe_exit": 0, "probe_timed_out": False,
                    "probe_status": "OK", "checksum": "123.456"})
    return recs, summ


def _synth_b():
    trials, results = [], []
    for stage in CM.B_STAGES:
        tr, res = CM.run_bisection(lambda k: k <= 65437)
        for t in tr:
            trials.append({"stage": stage, **t})
        results.append({"stage": stage, "n_trials": len(tr), **res})
    return trials, results


def _synth_c():
    trials = []
    for n in CM.C_LEVELS:
        for t in range(CM.C_REPEATS):
            trials.append({"name": f"C_nq{n}", "n_queues": n, "trial": t, "executed": True,
                           "exit": 0, "timed_out": False, "status": "OK",
                           "ok_queues": n, "execfail_queues": 0, "nonfinite_queues": 0,
                           "checksum_mismatch": 0})
    return trials


def _synth_provenance():
    return {"authored_code_sha256": {p: "c" * 64 for p in AUTH_CODE},
           "authored_doc_sha256": {p: "d" * 64 for p in AUTH_DOC}}


def _build_run_dir(run_dir, aborted=False, mutate=None):
    run_dir.mkdir(parents=True)
    i_recs, i_summ = _synth_i()
    b_trials, b_results = _synth_b()
    c_levels = _synth_c()
    payload = {"i_checkpoints": i_recs, "i_summary": i_summ, "b_trials": b_trials,
              "b_results": b_results, "c_levels": c_levels}
    if mutate:
        mutate(payload)
    hashes = {}
    for key, (fname, hashkey, _) in FILES.items():
        p = run_dir / fname
        with open(p, "w") as f:
            for r in payload[key]:
                f.write(json.dumps(r, sort_keys=True) + "\n")
        hashes[hashkey] = hashlib.sha256(p.read_bytes()).hexdigest()
    (run_dir / "00_inputs.json").write_text(json.dumps(
        {"run_id": run_dir.name, "provenance": _synth_provenance()}, sort_keys=True))
    summary = {"run_id": run_dir.name, "aborted_on_hard_fault": aborted, **hashes}
    if mutate:
        summary_patch = getattr(mutate, "summary_patch", None)
        if summary_patch:
            summary.update(summary_patch)
    (run_dir / "01_summary.json").write_text(json.dumps(summary, sort_keys=True))


def _full_tree(root, n_runs, aborted_runs=(), mutate0=None, mutate1=None):
    if n_runs >= 1:
        _build_run_dir(root / "raw" / RUNS[0], aborted=RUNS[0] in aborted_runs, mutate=mutate0)
    if n_runs >= 2:
        _build_run_dir(root / "raw" / RUNS[1], aborted=RUNS[1] in aborted_runs, mutate=mutate1)


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
        expect_pass(lambda: gate_preflight(root), "preflight in PRE_GPU")
        expect_fail(lambda: gate_between(root), "between-runs in PRE_GPU")
        expect_fail(lambda: gate_captured(root), "captured in PRE_GPU")
        _full_tree(root, 1)
        expect_fail(lambda: gate_preflight(root), "preflight in RUN01_PRESENT")
        expect_pass(lambda: gate_between(root), "between-runs in RUN01_PRESENT")
        expect_fail(lambda: gate_captured(root), "captured in RUN01_PRESENT")
        _build_run_dir(root / "raw" / RUNS[1])
        expect_fail(lambda: gate_preflight(root), "preflight in RUN02_PRESENT")
        expect_fail(lambda: gate_between(root), "between-runs in RUN02_PRESENT")
        expect_pass(lambda: gate_captured(root), "captured in RUN02_PRESENT")
    if FAILS:
        return 1
    print("seqtest: PASS (PRE_GPU / RUN01_PRESENT / RUN02_PRESENT all gate correctly)")
    return 0


def selftest():
    static()
    if FAILS:
        for m in FAILS:
            print("FAIL:", m)
        return 1

    with tempfile.TemporaryDirectory(prefix="selftest-clean-", dir=WORK) as td:
        root = Path(td)
        (root / "raw").mkdir()
        _full_tree(root, 2)
        try:
            gate_captured(root)
        except AssertionError as e:
            fail(f"selftest: clean synthetic tree unexpectedly failed gate_captured: {e}")

    with tempfile.TemporaryDirectory(prefix="selftest-missing-", dir=WORK) as td:
        root = Path(td)
        (root / "raw").mkdir()
        _full_tree(root, 2)
        (root / "raw" / RUNS[1] / "04a_b_trials.jsonl").unlink()
        try:
            gate_captured(root)
            fail("selftest: missing 04a_b_trials.jsonl was not detected")
        except AssertionError:
            pass

    def mutate_extra_key(payload):
        payload["c_levels"][0]["gpu_va"] = "0xdeadbeef"

    with tempfile.TemporaryDirectory(prefix="selftest-extrakey-", dir=WORK) as td:
        root = Path(td)
        (root / "raw").mkdir()
        _full_tree(root, 2, mutate1=mutate_extra_key)
        try:
            gate_captured(root)
            fail("selftest: extra nondeterministic-shaped key (gpu_va) in c_levels was not detected")
        except AssertionError:
            pass

    def mutate_extra_key_i(payload):
        for r in payload["i_checkpoints"]:
            r["mach_time"] = 12345  # exactly the forbidden nondeterministic-field shape

    with tempfile.TemporaryDirectory(prefix="selftest-extrakey-i-", dir=WORK) as td:
        root = Path(td)
        (root / "raw").mkdir()
        _full_tree(root, 2, mutate1=mutate_extra_key_i)
        try:
            gate_captured(root)
            fail("selftest: extra nondeterministic-shaped key (mach_time) in i_checkpoints was not detected")
        except AssertionError:
            pass

    def mutate_missing_key(payload):
        del payload["i_summary"][0]["checksum"]

    with tempfile.TemporaryDirectory(prefix="selftest-misskey-", dir=WORK) as td:
        root = Path(td)
        (root / "raw").mkdir()
        _full_tree(root, 2, mutate1=mutate_missing_key)
        try:
            gate_captured(root)
            fail("selftest: missing schema key was not detected")
        except AssertionError:
            pass

    with tempfile.TemporaryDirectory(prefix="selftest-hash-", dir=WORK) as td:
        root = Path(td)
        (root / "raw").mkdir()
        _full_tree(root, 2)
        p = root / "raw" / RUNS[1] / "01_summary.json"
        s = json.loads(p.read_text()); s["c_levels_sha256"] = "0" * 64
        p.write_text(json.dumps(s))
        try:
            gate_captured(root)
            fail("selftest: corrupted summary hash was not detected")
        except AssertionError:
            pass

    def mutate_diverge(payload):
        payload["b_results"][0]["last_ok"] = -1

    with tempfile.TemporaryDirectory(prefix="selftest-diverge-", dir=WORK) as td:
        root = Path(td)
        (root / "raw").mkdir()
        _full_tree(root, 2, mutate1=mutate_diverge)
        try:
            gate_captured(root)
            fail("selftest: run01/run02 semantic divergence in a gated field (b_results.last_ok) was not detected")
        except AssertionError:
            pass

    def mutate_c_nondeterministic_only(payload):
        # status/ok_queues/execfail_queues/nonfinite_queues/checksum_mismatch
        # are C_NONDETERMINISTIC_TRIAL_KEYS -- a tree differing ONLY in
        # these fields (never in C_GATED_TRIAL_KEYS) must still PASS
        # gate_captured, proving the exclusion is real and tested (this
        # experiment's own directly-observed analogue of EXP-0107's
        # bo_content_seq_sha256 selftest case).
        payload["c_levels"][0]["status"] = "DEGRADED"
        payload["c_levels"][0]["ok_queues"] = 0
        payload["c_levels"][0]["execfail_queues"] = payload["c_levels"][0]["n_queues"]

    with tempfile.TemporaryDirectory(prefix="selftest-c-nondeterm-", dir=WORK) as td:
        root = Path(td)
        (root / "raw").mkdir()
        _full_tree(root, 2, mutate1=mutate_c_nondeterministic_only)
        try:
            gate_captured(root)
        except AssertionError as e:
            fail(f"selftest: a run01/run02 difference confined to the documented C-family "
                f"nondeterministic fields incorrectly failed gate_captured: {e}")

    def mutate_provenance(payload):
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
    print("selftest: PASS (clean tree accepted; 7/7 injected defects correctly rejected; "
         "1/1 documented-nondeterministic-C-field-only divergence correctly tolerated)")
    return 0


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
