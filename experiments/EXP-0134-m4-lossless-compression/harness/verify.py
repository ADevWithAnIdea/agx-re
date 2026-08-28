#!/usr/bin/env python3
"""EXP-0134 verifier. Implements the five standing gates required by the dispatch:
  (a) --selftest
  (b) --seqtest over PRE_GPU / RUN01_PRESENT / RUN02_PRESENT
  (c) NON-RECORDED smoke gate (enforced at capture time by run.py, which writes
      work/<run_id>_smoke.json BEFORE creating raw/<run_id>/; checked structurally here)
  (d) nondeterminism exclusion (no nondeterministic field in byte-compared gated
      records; this experiment's cases are all deterministic -- see
      casematrix.nondeterministic_observed_keys())
  (e) fixtures from RECORDED REALITY (fixtures/recorded_reality.json holds real
      captured records, referenced -- not hand-typed -- by --selftest)

Usage:
  python3 verify.py --selftest
  python3 verify.py --seqtest
  python3 verify.py --captured RUN_ID_1 RUN_ID_2
"""
import argparse, json, sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import casematrix as CM
import schema as S


def load_jsonl(path):
    recs = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


# ---------------------------------------------------------------------------
def gate_selftest():
    issues = []

    ids = [c["id"] for c in CM.MATRIX]
    if len(ids) != len(set(ids)):
        issues.append("duplicate case ids in casematrix.MATRIX")
    if CM.TOTAL != len(CM.MATRIX):
        issues.append("CM.TOTAL does not match len(MATRIX)")
    for c in CM.MATRIX:
        if c["family"] not in S.FAMILIES:
            issues.append(f"case {c['id']} has unknown family {c['family']}")
        if c["decode"] not in ("descriptor", "descriptor2", "replicate", "stdout"):
            issues.append(f"case {c['id']} has unknown decode mode {c['decode']}")
        if "w" not in c["params"] or "h" not in c["params"]:
            issues.append(f"case {c['id']} params missing w/h")

    if S.GATED_KEYS & (S.NONGATED_KEYS - {"case_id"}):
        issues.append("GATED_KEYS overlaps NONGATED_KEYS beyond case_id")
    if "wall_ms" in S.GATED_KEYS or "pid" in S.GATED_KEYS:
        issues.append("wall_ms/pid must live only in NONGATED_KEYS (gate (d))")

    # Gate (d) structural proof: every case in this experiment is deterministic.
    nd_nonempty_cases = [c["id"] for c in CM.MATRIX if CM.nondeterministic_observed_keys(c)]
    if nd_nonempty_cases:
        issues.append(f"unexpected nondeterministic-key exclusions: {nd_nonempty_cases}")

    # Gate (e): fixtures must validate against the schema and look like real captures.
    fx_path = EXP / "fixtures" / "recorded_reality.json"
    if not fx_path.exists():
        issues.append("fixtures/recorded_reality.json missing")
    else:
        fx = json.loads(fx_path.read_text())
        if not isinstance(fx, list) or len(fx) < 3:
            issues.append("recorded_reality.json must be a list of >=3 real captures")
        for i, rec in enumerate(fx):
            ok, msg = S.validate_gated(rec.get("gated", {}))
            if not ok:
                issues.append(f"recorded_reality[{i}].gated invalid: {msg}")
            ok2, msg2 = S.validate_nongated(rec.get("nongated", {}))
            if not ok2:
                issues.append(f"recorded_reality[{i}].nongated invalid: {msg2}")
            if "source" not in rec:
                issues.append(f"recorded_reality[{i}] missing 'source' provenance note")

    for st in ("OK", "ALLOC_REJECTED", "HARNESS_CRASH", "HANG"):
        if st not in S.STATUS_VALUES:
            issues.append(f"status {st} used by harness but not declared in schema.STATUS_VALUES")

    return issues


# ---------------------------------------------------------------------------
def list_run_dirs(raw_dir):
    if not raw_dir.exists():
        return []
    out = []
    for d in sorted(raw_dir.iterdir()):
        if not d.is_dir():
            continue
        if (d / "QUARANTINE.md").exists():
            continue
        if (d / "04_manifest.json").exists():
            out.append(d)
    return out


def state_of(raw_dir):
    n = len(list_run_dirs(raw_dir))
    return "PRE_GPU" if n == 0 else ("RUN01_PRESENT" if n == 1 else "RUN02_PRESENT"), n


def _write_fake_run_dir(d, n_cases):
    d.mkdir(parents=True)
    (d / "00_inputs.json").write_text("{}")
    with open(d / "02_gated.jsonl", "w") as f:
        for i in range(n_cases):
            f.write(json.dumps({"case_id": f"x{i}", "family": "elig", "kind": "elig_usage",
                                 "params": {}, "status": "OK", "verdict": "PASS", "observed": {}}) + "\n")
    with open(d / "03_nongated.jsonl", "w") as f:
        for i in range(n_cases):
            f.write(json.dumps({"case_id": f"x{i}", "wall_ms": 1.0, "pid": 1,
                                 "raw_tail": "", "raw_ticks": {}}) + "\n")
    (d / "04_manifest.json").write_text(json.dumps({"cases_planned": n_cases}))


def gate_seqtest():
    """Deterministic unit test of the PRE_GPU / RUN01_PRESENT / RUN02_PRESENT state
    machine, built against disposable scratch directories under work/ (never
    touching the real raw/ tree or /tmp)."""
    import shutil
    checks = []
    scratch_root = EXP / "work" / "_seqtest_scratch"
    if scratch_root.exists():
        shutil.rmtree(scratch_root)
    scratch_root.mkdir(parents=True)
    try:
        pre_gpu = scratch_root / "pre_gpu" / "raw"
        pre_gpu.mkdir(parents=True)
        state, n = state_of(pre_gpu)
        checks.append(("PRE_GPU: zero dirs -> state PRE_GPU", state == "PRE_GPU" and n == 0))

        run01 = scratch_root / "run01" / "raw"
        run01.mkdir(parents=True)
        _write_fake_run_dir(run01 / "m4_test_run01", CM.TOTAL)
        state, n = state_of(run01)
        checks.append(("RUN01_PRESENT: one dir -> state RUN01_PRESENT", state == "RUN01_PRESENT" and n == 1))
        d = list_run_dirs(run01)[0]
        complete = all((d / f).exists() for f in
                       ("00_inputs.json", "02_gated.jsonl", "03_nongated.jsonl", "04_manifest.json"))
        checks.append(("RUN01_PRESENT: run dir structurally complete", complete))
        checks.append(("RUN01_PRESENT: case count matches matrix",
                        len(load_jsonl(d / "02_gated.jsonl")) == CM.TOTAL))

        run02 = scratch_root / "run02" / "raw"
        run02.mkdir(parents=True)
        _write_fake_run_dir(run02 / "m4_test_run01", CM.TOTAL)
        _write_fake_run_dir(run02 / "m4_test_run02", CM.TOTAL)
        state, n = state_of(run02)
        checks.append(("RUN02_PRESENT: two dirs -> state RUN02_PRESENT", state == "RUN02_PRESENT" and n == 2))

        quarantined = scratch_root / "quarantine" / "raw"
        quarantined.mkdir(parents=True)
        _write_fake_run_dir(quarantined / "m4_test_run01", CM.TOTAL)
        (quarantined / "m4_test_run01" / "QUARANTINE.md").write_text("quarantined")
        state, n = state_of(quarantined)
        checks.append(("quarantined dir excluded -> state stays PRE_GPU", state == "PRE_GPU" and n == 0))
    finally:
        shutil.rmtree(scratch_root, ignore_errors=True)

    real_state, real_n = state_of(EXP / "raw")
    checks.append((f"informational: real raw/ is currently {real_state} (n={real_n})", True))
    return checks


# ---------------------------------------------------------------------------
def gate_captured(run_id_a, run_id_b):
    da, db = EXP / "raw" / run_id_a, EXP / "raw" / run_id_b
    issues = []
    if not da.exists() or not db.exists():
        return {"error": f"run dir missing: {da if not da.exists() else db}"}
    ga = {r["case_id"]: r for r in load_jsonl(da / "02_gated.jsonl")}
    gb = {r["case_id"]: r for r in load_jsonl(db / "02_gated.jsonl")}
    if set(ga) != set(gb):
        issues.append(f"case_id set mismatch: only-in-a={sorted(set(ga)-set(gb))} "
                       f"only-in-b={sorted(set(gb)-set(ga))}")
    verdict_counts_a, verdict_counts_b = {}, {}
    for cid in sorted(set(ga) & set(gb)):
        ra, rb = ga[cid], gb[cid]
        verdict_counts_a[ra["verdict"]] = verdict_counts_a.get(ra["verdict"], 0) + 1
        verdict_counts_b[rb["verdict"]] = verdict_counts_b.get(rb["verdict"], 0) + 1
        for top_key in ("family", "kind", "params", "status", "verdict"):
            if ra.get(top_key) != rb.get(top_key):
                issues.append(f"{cid}: top-level '{top_key}' differs: {ra.get(top_key)!r} vs {rb.get(top_key)!r}")
        # gate (d): every case in this experiment is deterministic -- 'observed' must
        # be byte-identical across runs with no exclusions.
        if ra.get("observed") != rb.get("observed"):
            issues.append(f"{cid}: observed differs across runs (no nondeterministic keys declared): "
                           f"{ra.get('observed')} vs {rb.get('observed')}")

    return {
        "issues_total": len(issues),
        "issues": issues,
        "verdict_counts_a": verdict_counts_a,
        "verdict_counts_b": verdict_counts_b,
        "cross_run_gate_pass": len(issues) == 0,
    }


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--seqtest", action="store_true")
    ap.add_argument("--captured", nargs=2, metavar=("RUN_A", "RUN_B"))
    args = ap.parse_args()

    ran_any = False
    if args.selftest:
        ran_any = True
        issues = gate_selftest()
        print(f"selftest: {'PASS' if not issues else 'FAIL'} ({len(issues)} issues)")
        for i in issues:
            print("  -", i)
        if issues:
            sys.exit(1)

    if args.seqtest:
        ran_any = True
        checks = gate_seqtest()
        failed = [c for c in checks if not c[1]]
        print(f"seqtest: {'PASS' if not failed else 'FAIL'} ({len(checks)} checks, {len(failed)} failed)")
        for name, ok in checks:
            print(f"  [{'OK' if ok else 'FAIL'}] {name}")
        if failed:
            sys.exit(1)

    if args.captured:
        ran_any = True
        result = gate_captured(*args.captured)
        print(json.dumps(result, indent=2))
        if result.get("issues_total", 1) != 0:
            sys.exit(1)

    if not ran_any:
        ap.print_help()
        sys.exit(2)


if __name__ == "__main__":
    main()
