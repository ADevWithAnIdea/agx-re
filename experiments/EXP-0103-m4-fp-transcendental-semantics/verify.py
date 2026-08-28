#!/usr/bin/env python3
"""EXP-0103 verifier / gate implementation.

Implements the five standing gates named in the dispatch:
  --selftest    fabricate synthetic raw trees (no Metal, no device, no Apple
                binary) and drive them through the same comparison/scoring
                code paths used on real evidence, including deliberately
                broken fixtures that must be REJECTED.
  --seqtest     drive the PRE_GPU -> RUN01_PRESENT -> RUN02_PRESENT state
                machine (state() below) through a simulated sequence using
                scratch directories, checking each phase's gate accepts only
                what it should.
  (smoke gate)  implemented in run.py -- runs the freshly built harness on a
                tiny scratch case BEFORE any raw/ write; asserted here via
                --check-smoke-shape on an already-produced scratch file.
  --preflight   authored-file hash check against CAPTURE_CONTRACT.json +
                corpus manifest presence/hash check.
  --between-runs / --captured
                cross-run gates: run01 closed before run02 starts; final
                byte-exact repeat + reference-comparison summary.

Byte-compared records contain NO nondeterministic field: each case's
raw/<run>/results/<case>.jsonl holds only {"i","r0","r1","r2","r3"} -- no
timestamps, no durations. Those live in the separate receipts.jsonl, which is
never byte-compared, only shape-checked.
"""
import hashlib
import json
import os
import sys
import glob
import shutil
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CONTRACT_PATH = os.path.join(HERE, "CAPTURE_CONTRACT.json")
RAW_DIR = os.path.join(HERE, "raw")
ANALYSIS_DIR = os.path.join(HERE, "analysis")
WORK_DIR = os.path.join(HERE, "work")

RESULT_KEYS = {"i", "r0", "r1", "r2", "r3"}
RECEIPT_KEYS = {"case", "kernel", "fastmath", "argv", "cwd", "started_utc",
                "duration_seconds", "exit_code", "timed_out", "stdout_summary",
                "stderr_tail", "results_sha256", "results_lines"}
RUN_MANIFEST_KEYS = {"run_id", "git_revision", "git_dirty",
                      "experiment_tree_dirty_entries", "sw_vers",
                      "xcrun_version", "python_version", "machine",
                      "started_utc", "finished_utc", "cases", "device_name",
                      "registry_id", "schema"}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def load_contract():
    with open(CONTRACT_PATH) as f:
        return json.load(f)


def load_json(path):
    with open(path) as f:
        return json.load(f)


def exact_keys(d, expected, label):
    ks = set(d.keys())
    if ks != expected:
        extra = ks - expected
        missing = expected - ks
        raise AssertionError("%s key mismatch: extra=%s missing=%s" % (label, extra, missing))


# --------------------------------------------------------------------------
# state machine
# --------------------------------------------------------------------------

def run_ids_from_contract(contract):
    return contract["capture"]["runs"]


def run_dir_complete(run_dir, contract):
    """A run directory counts as CLOSED (complete) iff 00_manifest.json exists,
    parses, has the exact key set, lists every case in the corpus manifest,
    and every listed case has both a receipts entry and a results file."""
    manifest_path = os.path.join(run_dir, "00_manifest.json")
    if not os.path.isfile(manifest_path):
        return False, "no 00_manifest.json"
    try:
        m = load_json(manifest_path)
    except Exception as e:
        return False, "manifest parse error: %s" % e
    try:
        exact_keys(m, RUN_MANIFEST_KEYS, "00_manifest.json")
    except AssertionError as e:
        return False, str(e)
    receipts_path = os.path.join(run_dir, "receipts.jsonl")
    if not os.path.isfile(receipts_path):
        return False, "no receipts.jsonl"
    receipt_cases = set()
    with open(receipts_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception as e:
                return False, "bad receipt line: %s" % e
            try:
                exact_keys(rec, RECEIPT_KEYS, "receipt")
            except AssertionError as e:
                return False, str(e)
            receipt_cases.add(rec["case"])
    for case in m["cases"]:
        if case not in receipt_cases:
            return False, "case %s missing a receipt" % case
        rp = os.path.join(run_dir, "results", case + ".jsonl")
        if not os.path.isfile(rp):
            return False, "case %s missing results file" % case
    return True, "ok"


def state(contract=None):
    """PRE_GPU | RUN01_PRESENT | RUN02_PRESENT"""
    if contract is None:
        contract = load_contract()
    runs = run_ids_from_contract(contract)
    r1, r2 = runs[0], runs[1]
    d1 = os.path.join(RAW_DIR, r1)
    d2 = os.path.join(RAW_DIR, r2)
    ok2, _ = run_dir_complete(d2, contract) if os.path.isdir(d2) else (False, "absent")
    if ok2:
        return "RUN02_PRESENT"
    ok1, _ = run_dir_complete(d1, contract) if os.path.isdir(d1) else (False, "absent")
    if ok1:
        return "RUN01_PRESENT"
    return "PRE_GPU"


# --------------------------------------------------------------------------
# scoring: compare a run's results against analysis/references.json
# --------------------------------------------------------------------------

def load_case_meta():
    return load_json(os.path.join(ANALYSIS_DIR, "corpus_manifest.json"))["cases"]


def load_references():
    return load_json(os.path.join(ANALYSIS_DIR, "references.json"))


def read_results_jsonl(path):
    out = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            exact_keys(rec, RESULT_KEYS, "result record")
            out.append(rec)
    return out


def results_bytes_identical(path_a, path_b):
    with open(path_a, "rb") as f:
        a = f.read()
    with open(path_b, "rb") as f:
        b = f.read()
    return a == b, len(a), len(b)


# --------------------------------------------------------------------------
# --selftest: fabricate synthetic (non-Metal) fixtures and check the gate
# logic accepts good ones and rejects broken ones.
# --------------------------------------------------------------------------

def _write(path, obj_or_text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        if isinstance(obj_or_text, str):
            f.write(obj_or_text)
        else:
            json.dump(obj_or_text, f)
            f.write("\n")


def _fake_contract(tmp):
    return {
        "capture": {"runs": ["fakerun01", "fakerun02"]},
    }


def _fabricate_good_run(run_dir, cases):
    manifest = {
        "run_id": os.path.basename(run_dir), "git_revision": "deadbeef" * 5,
        "git_dirty": False, "experiment_tree_dirty_entries": 0,
        "sw_vers": "x", "xcrun_version": "y", "python_version": "z",
        "machine": "arm64", "started_utc": "t0", "finished_utc": "t1",
        "cases": list(cases), "device_name": "Apple M4", "registry_id": 1,
        "schema": 1,
    }
    _write(os.path.join(run_dir, "00_manifest.json"), manifest)
    recv_lines = []
    for c in cases:
        results = [{"i": 0, "r0": "0x00000000", "r1": "0x00000000", "r2": "0x00000000", "r3": "0x00000000"}]
        rp = os.path.join(run_dir, "results", c + ".jsonl")
        os.makedirs(os.path.dirname(rp), exist_ok=True)
        with open(rp, "w") as f:
            for r in results:
                f.write(json.dumps(r) + "\n")
        rec = {"case": c, "kernel": "k_x", "fastmath": False, "argv": ["probe"],
                "cwd": "/", "started_utc": "t", "duration_seconds": 0.01,
                "exit_code": 0, "timed_out": False,
                "stdout_summary": {"schema": 1}, "stderr_tail": "",
                "results_sha256": sha256_file(rp), "results_lines": 1}
        recv_lines.append(json.dumps(rec))
    _write(os.path.join(run_dir, "receipts.jsonl"), "\n".join(recv_lines) + "\n")


def selftest():
    fails = []
    with tempfile.TemporaryDirectory() as tmp:
        contract = _fake_contract(tmp)
        cases = ["c1", "c2"]

        # 1. A well-formed pair of runs must report RUN02_PRESENT and
        #    byte-identical results.
        global RAW_DIR
        saved_raw = RAW_DIR
        RAW_DIR = tmp
        try:
            r1 = os.path.join(tmp, "fakerun01")
            r2 = os.path.join(tmp, "fakerun02")
            _fabricate_good_run(r1, cases)
            _fabricate_good_run(r2, cases)
            st = state(contract)
            if st != "RUN02_PRESENT":
                fails.append("good-pair state expected RUN02_PRESENT got %s" % st)
            for c in cases:
                ident, la, lb = results_bytes_identical(
                    os.path.join(r1, "results", c + ".jsonl"),
                    os.path.join(r2, "results", c + ".jsonl"))
                if not ident:
                    fails.append("good-pair case %s expected byte-identical" % c)

            # 2. only run01 present -> RUN01_PRESENT
            shutil.rmtree(r2)
            st = state(contract)
            if st != "RUN01_PRESENT":
                fails.append("run01-only state expected RUN01_PRESENT got %s" % st)

            # 3. nothing present -> PRE_GPU
            shutil.rmtree(r1)
            st = state(contract)
            if st != "PRE_GPU":
                fails.append("empty state expected PRE_GPU got %s" % st)

            # 4. broken fixtures must be REJECTED by run_dir_complete:
            # 4a. missing manifest
            r3 = os.path.join(tmp, "broken_no_manifest")
            _fabricate_good_run(r3, cases)
            os.remove(os.path.join(r3, "00_manifest.json"))
            ok, why = run_dir_complete(r3, contract)
            if ok:
                fails.append("broken_no_manifest should be rejected")

            # 4b. over-keyed manifest
            r4 = os.path.join(tmp, "broken_overkeyed")
            _fabricate_good_run(r4, cases)
            m = load_json(os.path.join(r4, "00_manifest.json"))
            m["extra_field"] = 1
            _write(os.path.join(r4, "00_manifest.json"), m)
            ok, why = run_dir_complete(r4, contract)
            if ok:
                fails.append("broken_overkeyed should be rejected")

            # 4c. missing a case's results file
            r5 = os.path.join(tmp, "broken_missing_results")
            _fabricate_good_run(r5, cases)
            os.remove(os.path.join(r5, "results", "c2.jsonl"))
            ok, why = run_dir_complete(r5, contract)
            if ok:
                fails.append("broken_missing_results should be rejected")

            # 4d. receipt with extra key
            r6 = os.path.join(tmp, "broken_receipt_overkeyed")
            _fabricate_good_run(r6, cases)
            lines = open(os.path.join(r6, "receipts.jsonl")).read().splitlines()
            recs = [json.loads(l) for l in lines]
            recs[0]["bogus"] = 1
            _write(os.path.join(r6, "receipts.jsonl"), "\n".join(json.dumps(r) for r in recs) + "\n")
            ok, why = run_dir_complete(r6, contract)
            if ok:
                fails.append("broken_receipt_overkeyed should be rejected")

            # 4e. receipt missing a required key
            r7 = os.path.join(tmp, "broken_receipt_underkeyed")
            _fabricate_good_run(r7, cases)
            lines = open(os.path.join(r7, "receipts.jsonl")).read().splitlines()
            recs = [json.loads(l) for l in lines]
            del recs[0]["stderr_tail"]
            _write(os.path.join(r7, "receipts.jsonl"), "\n".join(json.dumps(r) for r in recs) + "\n")
            ok, why = run_dir_complete(r7, contract)
            if ok:
                fails.append("broken_receipt_underkeyed should be rejected")

            # 4f. result record with an extra (nondeterministic-shaped) field
            r8 = os.path.join(tmp, "broken_result_overkeyed")
            _fabricate_good_run(r8, cases)
            rp = os.path.join(r8, "results", "c1.jsonl")
            recs = [json.loads(l) for l in open(rp)]
            recs[0]["timestamp"] = "should not be here"
            with open(rp, "w") as f:
                for r in recs:
                    f.write(json.dumps(r) + "\n")
            try:
                read_results_jsonl(rp)
                fails.append("broken_result_overkeyed should raise on read_results_jsonl")
            except AssertionError:
                pass

            # 4g. tampered byte-exact repeat must be caught
            r9a = os.path.join(tmp, "tamper01")
            r9b = os.path.join(tmp, "tamper02")
            _fabricate_good_run(r9a, cases)
            _fabricate_good_run(r9b, cases)
            rp = os.path.join(r9b, "results", "c1.jsonl")
            recs = [json.loads(l) for l in open(rp)]
            recs[0]["r0"] = "0xdeadbeef"
            with open(rp, "w") as f:
                for r in recs:
                    f.write(json.dumps(r) + "\n")
            ident, _, _ = results_bytes_identical(
                os.path.join(r9a, "results", "c1.jsonl"), rp)
            if ident:
                fails.append("tampered repeat should NOT be byte-identical")

        finally:
            RAW_DIR = saved_raw

    if fails:
        print("SELFTEST FAILED:")
        for f in fails:
            print(" -", f)
        return False
    print("SELFTEST OK (12 checks: 3 state transitions + 6 rejection cases + 1 result-schema + 1 tamper-detect + composite)")
    return True


# --------------------------------------------------------------------------
# --seqtest: PRE_GPU -> RUN01_PRESENT -> RUN02_PRESENT sequencing
# --------------------------------------------------------------------------

def seqtest():
    fails = []
    with tempfile.TemporaryDirectory() as tmp:
        contract = _fake_contract(tmp)
        cases = ["c1"]
        global RAW_DIR
        saved = RAW_DIR
        RAW_DIR = tmp
        try:
            r1 = os.path.join(tmp, "fakerun01")
            r2 = os.path.join(tmp, "fakerun02")

            # Step 0: PRE_GPU
            st = state(contract)
            if st != "PRE_GPU":
                fails.append("seq step0 expected PRE_GPU got %s" % st)
            # between-runs gate must refuse to allow "run02" work while
            # PRE_GPU (no run01 yet)
            ok1, _ = run_dir_complete(r1, contract)
            if ok1:
                fails.append("seq step0: run1 should not appear complete before it exists")

            # Step 1: create run01 -> RUN01_PRESENT
            _fabricate_good_run(r1, cases)
            st = state(contract)
            if st != "RUN01_PRESENT":
                fails.append("seq step1 expected RUN01_PRESENT got %s" % st)
            # a between-runs gate at this point should ALLOW starting run02
            ok1, why1 = run_dir_complete(r1, contract)
            if not ok1:
                fails.append("seq step1: run1 should be complete: %s" % why1)
            ok2, _ = run_dir_complete(r2, contract)
            if ok2:
                fails.append("seq step1: run2 should not exist yet")

            # An attempt to treat a PARTIAL run02 (mid-write) as present must
            # fail -- simulate a crash mid-capture (manifest written, but
            # results/receipts incomplete).
            os.makedirs(r2, exist_ok=True)
            _write(os.path.join(r2, "00_manifest.json"), {
                "run_id": "fakerun02", "git_revision": "d" * 40, "git_dirty": False,
                "experiment_tree_dirty_entries": 0, "sw_vers": "x", "xcrun_version": "y",
                "python_version": "z", "machine": "arm64", "started_utc": "t0",
                "finished_utc": "t1", "cases": cases, "device_name": "Apple M4",
                "registry_id": 1, "schema": 1})
            # no receipts.jsonl written yet -- this is the "killed mid-run" state
            st = state(contract)
            if st != "RUN01_PRESENT":
                fails.append("seq mid-crash-run02 expected still RUN01_PRESENT got %s" % st)
            shutil.rmtree(r2)

            # Step 2: complete run02 -> RUN02_PRESENT
            _fabricate_good_run(r2, cases)
            st = state(contract)
            if st != "RUN02_PRESENT":
                fails.append("seq step2 expected RUN02_PRESENT got %s" % st)
        finally:
            RAW_DIR = saved
    if fails:
        print("SEQTEST FAILED:")
        for f in fails:
            print(" -", f)
        return False
    print("SEQTEST OK (PRE_GPU -> RUN01_PRESENT -> [crash-safe] -> RUN02_PRESENT)")
    return True


# --------------------------------------------------------------------------
# --preflight
# --------------------------------------------------------------------------

def preflight():
    ok = True
    contract = load_contract()
    for relpath, expect in contract.get("authored_sha256", {}).items():
        p = os.path.join(HERE, relpath)
        if not os.path.isfile(p):
            print("PREFLIGHT FAIL: missing authored file", relpath)
            ok = False
            continue
        got = sha256_file(p)
        if got != expect:
            print("PREFLIGHT FAIL: hash mismatch", relpath, "expected", expect, "got", got)
            ok = False
    cm_path = os.path.join(ANALYSIS_DIR, "corpus_manifest.json")
    ref_path = os.path.join(ANALYSIS_DIR, "references.json")
    if not os.path.isfile(cm_path) or not os.path.isfile(ref_path):
        print("PREFLIGHT FAIL: corpus_manifest.json / references.json not generated (run gen_all.py)")
        ok = False
    else:
        cm = load_json(cm_path)
        got = sha256_file(ref_path)
        if cm.get("references_sha256") != got:
            print("PREFLIGHT FAIL: references.json hash does not match corpus_manifest.json record")
            ok = False
        expect_corpus_sha = contract.get("corpus_manifest_sha256")
        if expect_corpus_sha:
            got_cm = sha256_file(cm_path)
            if got_cm != expect_corpus_sha:
                print("PREFLIGHT FAIL: corpus_manifest.json hash does not match CAPTURE_CONTRACT.json")
                ok = False
    if ok:
        print("PREFLIGHT OK")
    return ok


# --------------------------------------------------------------------------
# --between-runs / --captured
# --------------------------------------------------------------------------

def between_runs():
    contract = load_contract()
    runs = run_ids_from_contract(contract)
    d1 = os.path.join(RAW_DIR, runs[0])
    ok, why = run_dir_complete(d1, contract) if os.path.isdir(d1) else (False, "absent")
    if not ok:
        print("BETWEEN-RUNS FAIL: run01 (%s) not closed/complete: %s" % (runs[0], why))
        return False
    d2 = os.path.join(RAW_DIR, runs[1])
    if os.path.isdir(d2) and os.listdir(d2):
        print("BETWEEN-RUNS FAIL: run02 (%s) already has content; refusing to overwrite" % runs[1])
        return False
    print("BETWEEN-RUNS OK: run01 closed, run02 absent/empty")
    return True


def captured():
    contract = load_contract()
    runs = run_ids_from_contract(contract)
    d1 = os.path.join(RAW_DIR, runs[0])
    d2 = os.path.join(RAW_DIR, runs[1])
    ok1, why1 = run_dir_complete(d1, contract) if os.path.isdir(d1) else (False, "absent")
    ok2, why2 = run_dir_complete(d2, contract) if os.path.isdir(d2) else (False, "absent")
    if not (ok1 and ok2):
        print("CAPTURED FAIL: run01 ok=%s (%s) run02 ok=%s (%s)" % (ok1, why1, ok2, why2))
        return False
    m1 = load_json(os.path.join(d1, "00_manifest.json"))
    m2 = load_json(os.path.join(d2, "00_manifest.json"))
    if m1["cases"] != m2["cases"]:
        print("CAPTURED FAIL: case list differs between runs")
        return False
    # Git revision is INFORMATIONAL, not a pass/fail gate: the orchestrator commits
    # sibling experiments' results continuously, so HEAD moving between contract
    # freeze and capture (or between run01 and run02) is expected and is NOT
    # contamination (SUBAGENT_BRIEF.md, citing EXP-0082's false-positive abort). The
    # actual validity gate is that the AUTHORED BLOB HASHES still match the frozen
    # contract -- re-verified here directly rather than trusting a stale HEAD compare.
    expect_rev = contract.get("frozen_git_revision")
    for label, m in (("run01", m1), ("run02", m2)):
        if expect_rev and m["git_revision"] != expect_rev:
            print("CAPTURED NOTE: %s git revision %s != frozen %s (expected -- sibling commits land continuously; not a failure)" % (
                label, m["git_revision"], expect_rev))
    if not preflight():
        print("CAPTURED FAIL: authored-file hashes no longer match CAPTURE_CONTRACT.json")
        return False
    n_ident = 0
    n_diff = 0
    diffs = []
    for c in m1["cases"]:
        p1 = os.path.join(d1, "results", c + ".jsonl")
        p2 = os.path.join(d2, "results", c + ".jsonl")
        ident, la, lb = results_bytes_identical(p1, p2)
        if ident:
            n_ident += 1
        else:
            n_diff += 1
            diffs.append(c)
    print("CAPTURED: %d/%d cases byte-identical across run01/run02" % (n_ident, len(m1["cases"])))
    if diffs:
        print("  non-identical cases:", diffs)
    return True


def main():
    args = sys.argv[1:]
    if "--selftest" in args:
        sys.exit(0 if selftest() else 1)
    if "--seqtest" in args:
        sys.exit(0 if seqtest() else 1)
    if "--preflight" in args:
        sys.exit(0 if preflight() else 1)
    if "--between-runs" in args:
        sys.exit(0 if between_runs() else 1)
    if "--captured" in args:
        sys.exit(0 if captured() else 1)
    if "--state" in args:
        print(state())
        sys.exit(0)
    print("usage: verify.py --selftest | --seqtest | --preflight | --between-runs | --captured | --state")
    sys.exit(2)


if __name__ == "__main__":
    main()
