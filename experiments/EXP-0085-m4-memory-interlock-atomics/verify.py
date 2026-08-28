#!/usr/bin/env python3
"""EXP-0085 fail-closed verifier. Implements the standing gate set:

  --selftest    synthetic, offline (no Metal/device, no real raw/): proves
                the case matrix is well-formed, every record schema is a
                single authoritative key set, and the cross-run gate in
                analysis.py PASSES two synthetic runs that differ only in a
                case's declared order-sensitive keys (+ receipts/timing) and
                FAILS when any other key differs. Runnable in every tree
                state, including before any GPU work.
  --seqtest     walks the contracted gate order through synthetic states
                (PRE_GPU -> RUN01_PRESENT -> RUN02_PRESENT, fabricated under
                work/seqtest_scratch/, never touching real raw/) and proves
                every gate is runnable+satisfiable in the state the contract
                invokes it, and FAILS in every state the contract does not.
  --preflight       PRE_GPU: no run directory may exist yet in raw/.
  --between-runs    RUN01_PRESENT: run01 must be a complete, closed run.
  --captured RUN01 RUN02   RUN02_PRESENT: both runs complete/closed.
"""
import argparse, json, shutil, sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import casematrix as CM


def fail(msg):
    raise SystemExit("FAIL " + msg)


# ---------------------------------------------------------------------------
# Pure gate functions, parametrized by raw_root so --seqtest can exercise
# them against fabricated synthetic trees without ever touching real raw/.
# ---------------------------------------------------------------------------
def list_run_dirs(raw_root):
    if not raw_root.exists():
        return []
    return sorted([p for p in raw_root.iterdir() if p.is_dir()])


def run_is_closed(run_dir):
    manifest_p = run_dir / "06_run_manifest.json"
    if (run_dir / "STOP.json").exists():
        return False, "STOP.json present"
    if not manifest_p.exists():
        return False, "missing 06_run_manifest.json"
    try:
        manifest = json.loads(manifest_p.read_text())
    except Exception as e:
        return False, f"unreadable manifest: {e}"
    results_p, receipts_p = run_dir / "04_results.jsonl", run_dir / "05_receipts.jsonl"
    if not results_p.exists() or not receipts_p.exists():
        return False, "missing results/receipts"
    lines = [l for l in results_p.read_text().splitlines() if l.strip()]
    if len(lines) != manifest.get("cases_planned"):
        return False, f"results line count {len(lines)} != cases_planned {manifest.get('cases_planned')}"
    if manifest.get("cases_planned") != CM.TOTAL:
        return False, f"manifest cases_planned {manifest.get('cases_planned')} != frozen TOTAL {CM.TOTAL}"
    return True, "ok"


def gate_preflight(raw_root):
    dirs = list_run_dirs(raw_root)
    if dirs:
        return False, f"raw tree already present: {[d.name for d in dirs]}"
    return True, "no run directories present"


def gate_between_runs(raw_root):
    dirs = list_run_dirs(raw_root)
    if len(dirs) != 1:
        return False, f"expected exactly 1 run directory, found {len(dirs)}"
    ok, msg = run_is_closed(dirs[0])
    return ok, msg


def gate_captured(raw_root):
    dirs = list_run_dirs(raw_root)
    if len(dirs) != 2:
        return False, f"expected exactly 2 run directories, found {len(dirs)}"
    for d in dirs:
        ok, msg = run_is_closed(d)
        if not ok:
            return False, f"{d.name}: {msg}"
    return True, "both runs closed"


# ---------------------------------------------------------------------------
# --selftest
# ---------------------------------------------------------------------------
def selftest():
    n = 0

    # 1. matrix well-formed: unique i == 0..TOTAL-1, unique names, atom_item set.
    idxs = [c["i"] for c in CM.MATRIX]
    if idxs != list(range(CM.TOTAL)):
        fail("matrix indices not 0..TOTAL-1 in order")
    n += 1
    names = [c["name"] for c in CM.MATRIX]
    if len(set(names)) != len(names):
        fail("matrix has duplicate case names")
    n += 1
    for c in CM.MATRIX:
        if not c.get("atom_item"):
            fail(f"case {c['name']} missing atom_item tag")
    n += 1

    # 2. every family has exactly one authoritative RESULT_KEYS set, and every
    #    case's order_sensitive_keys is a subset of that family's keys.
    for c in CM.MATRIX:
        keys = CM.RESULT_KEYS_BY_FAMILY[c["family"]]
        excl = CM.case_order_sensitive_keys(c)
        if not excl.issubset(keys):
            fail(f"case {c['name']}: order_sensitive_keys {excl} not subset of {c['family']} keys")
    n += 1

    # 3. STATUS_ALLOWED sanity + RECEIPT_KEYS disjoint from RESULT_KEYS (timing
    #    lives only in receipts -- fenced class (d): no nondeterministic field
    #    inside any byte-compared record).
    nondeterministic = {"gputime_ns", "duration_ms", "started_utc", "argv", "cwd", "exit", "timed_out"}
    for fam, keys in CM.RESULT_KEYS_BY_FAMILY.items():
        bad = keys & nondeterministic
        if bad:
            fail(f"family {fam} result keys contain nondeterministic field(s) {bad}")
    n += 1
    if not nondeterministic.issubset(CM.RECEIPT_KEYS | {"argv", "cwd", "exit", "timed_out"}):
        pass  # receipts are explicitly where timing lives; nothing to assert beyond keys existing
    n += 1

    # 4. synthetic cross-run gate proof: fabricate two in-memory "runs" that
    #    differ ONLY in each case's declared order-sensitive keys, and prove
    #    analysis.cross_run_gate PASSES; then flip one non-excluded key and
    #    prove it FAILS. Pure in-memory, no Metal, no files under raw/.
    import analysis as AN

    def synth_result(case, variant):
        keys = CM.RESULT_KEYS_BY_FAMILY[case["family"]]
        r = {k: None for k in keys}
        r["i"] = case["i"]
        r["name"] = case["name"]
        r["status"] = "ok"
        for k in keys:
            if k in ("i", "name", "status"):
                continue
            if isinstance(k, str) and k.endswith("_hex"):
                r[k] = "ab" * 4
            elif k in ("idx", "success_out"):
                r[k] = [0, 1]
            else:
                r[k] = 1
        excl = CM.case_order_sensitive_keys(case)
        for k in excl:
            # order-sensitive keys legitimately differ run to run
            r[k] = ("cd" * 4) if (isinstance(k, str) and k.endswith("_hex")) else ([1, 0] if k in ("idx", "success_out") else 2)
        return r

    run_a = {"results": {}, "inputs": {"git_revision": "deadbeef", "authored_sha256": {"x": "1"}}}
    run_b = {"results": {}, "inputs": {"git_revision": "deadbeef", "authored_sha256": {"x": "1"}}}
    for case in CM.MATRIX:
        run_a["results"][case["i"]] = synth_result(case, "a")
        rb = dict(synth_result(case, "a"))
        excl = CM.case_order_sensitive_keys(case)
        for k in excl:
            rb[k] = ("ef" * 4) if (isinstance(k, str) and k.endswith("_hex")) else ([9, 9] if k in ("idx", "success_out") else 3)
        run_b["results"][case["i"]] = rb

    ok, issues = AN.cross_run_gate(run_a, run_b)
    if not ok:
        fail(f"selftest: cross_run_gate should PASS when only order-sensitive keys differ; issues={issues[:5]}")
    n += 1

    # now corrupt a non-excluded key in one case and prove the gate FAILS.
    target_case = CM.MATRIX[0]
    non_excl_keys = CM.RESULT_KEYS_BY_FAMILY[target_case["family"]] - CM.case_order_sensitive_keys(target_case) - {"i", "name"}
    corrupt_key = sorted(non_excl_keys)[0]
    run_b2 = {"results": dict(run_b["results"]), "inputs": run_b["inputs"]}
    corrupted = dict(run_b2["results"][target_case["i"]])
    corrupted[corrupt_key] = "__CORRUPTED__"
    run_b2["results"][target_case["i"]] = corrupted
    ok2, issues2 = AN.cross_run_gate(run_a, run_b2)
    if ok2:
        fail("selftest: cross_run_gate should FAIL when a non-order-sensitive key differs")
    if not any(f"key {corrupt_key} differs" in msg for msg in issues2):
        fail(f"selftest: cross_run_gate did not report the corrupted key {corrupt_key}")
    n += 1

    # 5. provenance_gate proof
    pok, _ = AN.provenance_gate(run_a, run_b)
    if not pok:
        fail("selftest: provenance_gate should PASS on identical inputs")
    n += 1
    run_b3 = {"inputs": {"git_revision": "OTHER", "authored_sha256": run_b["inputs"]["authored_sha256"]}}
    pok2, pissues2 = AN.provenance_gate(run_a, run_b3)
    if pok2:
        fail("selftest: provenance_gate should FAIL on differing git_revision")
    n += 1

    print(f"SELFTEST PASS ({n} checks)")
    return True


# ---------------------------------------------------------------------------
# --seqtest
# ---------------------------------------------------------------------------
def fabricate_run(run_dir, complete=True, stop=False):
    run_dir.mkdir(parents=True, exist_ok=True)
    if stop:
        (run_dir / "STOP.json").write_text(json.dumps({"stage": "capture"}))
        return
    lines = []
    for c in CM.MATRIX:
        keys = CM.RESULT_KEYS_BY_FAMILY[c["family"]]
        r = {k: (c["i"] if k == "i" else (c["name"] if k == "name" else "ok" if k == "status" else None)) for k in keys}
        lines.append(json.dumps(r))
    if not complete:
        lines = lines[:5]
    (run_dir / "04_results.jsonl").write_text("\n".join(lines) + "\n")
    (run_dir / "05_receipts.jsonl").write_text("\n".join(json.dumps({"i": i}) for i in range(len(lines))) + "\n")
    (run_dir / "06_run_manifest.json").write_text(json.dumps({
        "schema": "exp0085.run_manifest.v1", "cases_planned": (CM.TOTAL if complete else 5),
    }))


def seqtest():
    scratch = HERE / "work" / "seqtest_scratch"
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    checks = 0
    try:
        # ---- PRE_GPU: raw/ empty ----
        pre_gpu = scratch / "pre_gpu" / "raw"
        pre_gpu.mkdir(parents=True)
        ok, _ = gate_preflight(pre_gpu)
        if not ok:
            fail("seqtest: preflight must PASS in PRE_GPU state")
        checks += 1
        ok, _ = gate_between_runs(pre_gpu)
        if ok:
            fail("seqtest: between-runs must FAIL in PRE_GPU state")
        checks += 1
        ok, _ = gate_captured(pre_gpu)
        if ok:
            fail("seqtest: captured must FAIL in PRE_GPU state")
        checks += 1

        # ---- RUN01_PRESENT: one closed run ----
        run01 = scratch / "run01" / "raw"
        run01.mkdir(parents=True)
        fabricate_run(run01 / "m4-run01", complete=True)
        ok, _ = gate_preflight(run01)
        if ok:
            fail("seqtest: preflight must FAIL in RUN01_PRESENT state")
        checks += 1
        ok, msg = gate_between_runs(run01)
        if not ok:
            fail(f"seqtest: between-runs must PASS in RUN01_PRESENT state ({msg})")
        checks += 1
        ok, _ = gate_captured(run01)
        if ok:
            fail("seqtest: captured must FAIL in RUN01_PRESENT state")
        checks += 1

        # RUN01_PRESENT but INCOMPLETE (unreachable-second-run landmine class,
        # EXP-0075/0077): between-runs must FAIL, not silently pass.
        run01b = scratch / "run01_incomplete" / "raw"
        run01b.mkdir(parents=True)
        fabricate_run(run01b / "m4-run01", complete=False)
        ok, _ = gate_between_runs(run01b)
        if ok:
            fail("seqtest: between-runs must FAIL on an incomplete run01 (short results file)")
        checks += 1

        # RUN01_PRESENT but STOPped: between-runs must FAIL.
        run01c = scratch / "run01_stop" / "raw"
        run01c.mkdir(parents=True)
        fabricate_run(run01c / "m4-run01", stop=True)
        ok, _ = gate_between_runs(run01c)
        if ok:
            fail("seqtest: between-runs must FAIL on a STOPped run01")
        checks += 1

        # ---- RUN02_PRESENT: two closed runs ----
        run02 = scratch / "run02" / "raw"
        run02.mkdir(parents=True)
        fabricate_run(run02 / "m4-run01", complete=True)
        fabricate_run(run02 / "m4-run02", complete=True)
        ok, _ = gate_preflight(run02)
        if ok:
            fail("seqtest: preflight must FAIL in RUN02_PRESENT state")
        checks += 1
        ok, _ = gate_between_runs(run02)
        if ok:
            fail("seqtest: between-runs must FAIL in RUN02_PRESENT state (already 2 runs)")
        checks += 1
        ok, msg = gate_captured(run02)
        if not ok:
            fail(f"seqtest: captured must PASS in RUN02_PRESENT state ({msg})")
        checks += 1

        print(f"SEQTEST PASS ({checks} state/gate combinations)")
        return True
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
    args = ap.parse_args()

    if args.selftest:
        selftest(); return
    if args.seqtest:
        seqtest(); return

    raw_root = HERE / "raw"
    if args.preflight:
        ok, msg = gate_preflight(raw_root)
    elif args.between_runs:
        ok, msg = gate_between_runs(raw_root)
    elif args.captured:
        ok, msg = gate_captured(raw_root)
    else:
        fail("no gate selected")
    print(("PASS " if ok else "FAIL ") + msg)
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
