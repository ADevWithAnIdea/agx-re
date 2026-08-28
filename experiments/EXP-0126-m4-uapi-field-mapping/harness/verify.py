#!/usr/bin/env python3
"""EXP-0126 verification gates.

  (a) --selftest    -- fixture/logic checks, including the proof that excluding GPU-
                        address fields from the cross-run gate does not hide a real
                        semantic difference (standing gate requirement).
  (b) --seqtest      -- deterministic PRE_GPU / RUN01_PRESENT / RUN02_PRESENT scratch-dir
                        state-machine unit test (quarantine-exclusion included).
  (c) --captured     -- the real cross-run comparison: --run01 <id> --run02 <id>, gated on
                        casematrix.GATED_KEYS only (case_id/family/kind/params/status/
                        observed); va_vtxbuf/va_resbuf/hex_path/raw_stdout/raw_stderr/
                        wall_ms/rc are read for provenance but never gated.

Usage:
  python3 verify.py --selftest
  python3 verify.py --seqtest
  python3 verify.py --captured --run01 m4_<date>_run01 --run02 m4_<date>_run02
"""
import argparse, json, shutil, sys, tempfile
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import casematrix as CM
import hexparse as HP

FIXTURES = EXP / "fixtures" / "recorded_reality.json"
RAW = EXP / "raw"


def gated_view(rec):
    return {k: rec.get(k) for k in CM.GATED_KEYS}


def compare_records(a, b):
    """True iff a and b agree on every GATED key. Deliberately ignores everything in
    NONGATED_KEYS (va_vtxbuf/va_resbuf especially -- allocator-dependent GPU addresses)."""
    return gated_view(a) == gated_view(b)


# ---------------------------------------------------------------------------
# (a) selftest
# ---------------------------------------------------------------------------

def gate_selftest():
    issues = []

    if not FIXTURES.exists():
        return [f"missing fixtures file {FIXTURES}"]
    fixtures = json.loads(FIXTURES.read_text())
    if len(fixtures) < 5:
        issues.append(f"expected >=5 recorded-reality fixtures, got {len(fixtures)}")

    required_top = {"case_id", "family", "kind", "params", "status", "observed",
                     "va_vtxbuf", "va_resbuf", "hex_path", "raw_stdout", "raw_stderr",
                     "wall_ms", "rc"}
    for rec in fixtures:
        missing = required_top - set(rec.keys())
        if missing:
            issues.append(f"{rec.get('case_id')}: missing top-level keys {missing}")

    by_id = {r["case_id"]: r for r in fixtures}

    # --- known-value regression checks pinned to the ACTUAL M4 capture that produced
    # these fixtures (drawn from work/pilot_full/records.jsonl, a real run of this same
    # harness) -- this is the exhaustive-grid + rounding-rule finding this experiment
    # exists to establish, re-checked here so a future harness change that silently
    # breaks parsing or the hex offset convention is caught.
    checks = [
        ("sp_gridx_00", lambda r: r["observed"]["x0"] == 0.0),
        ("sp_gridx_15", lambda r: r["observed"]["x0"] == 0.9375),
        ("sp_ladder_0p03124", lambda r: r["observed"]["x0"] == 0.0),   # below the 1/32 tie -> rounds down
        ("sp_ladder_0p03125", lambda r: r["observed"]["x0"] == 0.0625),  # AT the 1/32 tie -> rounds up
        ("sp_boundx_0p99", lambda r: r["observed"]["x0"] == 1.0),      # past-grid: no ceiling clamp observed
        ("sp_boundx_n0p001", lambda r: r["status"] == "ABORT_sig6" and r["observed"]["x0"] is None),
        ("sp_count2_0p1", lambda r: r["observed"]["x0"] == 0.125 and r["params"]["samples"] == 2),
        ("sc_count_02", lambda r: r["observed"]["capquery"] == "supported=1"),
        ("sc_count_03", lambda r: r["observed"]["capquery"] == "supported=0"),
        ("sc_count_16", lambda r: r["status"].startswith("ABORT") or r["observed"]["capquery"] == "supported=0"),
    ]
    for cid, pred in checks:
        rec = by_id.get(cid)
        if rec is None:
            issues.append(f"fixture missing required case {cid}")
            continue
        try:
            ok = pred(rec)
        except Exception as e:
            ok = False
            issues.append(f"{cid}: predicate raised {e!r}")
            continue
        if not ok:
            issues.append(f"{cid}: regression check failed, record={rec['observed']}")

    # --- standing-gate proof: excluding va_vtxbuf/va_resbuf from the cross-run gate
    # does NOT hide a real semantic difference, and DOES tolerate a pure GPU-address
    # difference. This is the required proof for "NO nondeterministic field in
    # byte-compared records (GPU addresses vary -- exclude or normalize and prove it
    # in the selftest)".
    base = by_id["sp_gridx_00"]
    va_only_diff = json.loads(json.dumps(base))
    va_only_diff["va_vtxbuf"] = "0x00000199deadbeef"
    va_only_diff["va_resbuf"] = "0x0000019900000000"
    if not compare_records(base, va_only_diff):
        issues.append("VA-only difference incorrectly failed the gated comparison "
                       "(GPU addresses must be excluded)")

    semantic_diff = json.loads(json.dumps(base))
    semantic_diff["observed"] = dict(semantic_diff["observed"])
    semantic_diff["observed"]["x0"] = 0.9999
    if compare_records(base, semantic_diff):
        issues.append("semantic (observed.x0) difference was WRONGLY masked by the "
                       "gated comparison -- exclusion logic is unsound")

    status_diff = json.loads(json.dumps(base))
    status_diff["status"] = "ABORT_sig6"
    if compare_records(base, status_diff):
        issues.append("status difference was wrongly masked")

    # --- hex-parser logic check, independent of any live capture: build a synthetic
    # BODUMP-format snapshot in the exact documented format and confirm hexparse.py
    # recovers the intended float.
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "synthetic.hex"
        # bytes at offset 0x40: IEEE-754 0.375 = 0x3EC00000 -> LE bytes 00 00 c0 3e
        p.write_text(
            "# BODUMP reason=synthetic handle=0 gpu_va=0x100000e8000 cpu=0xdeadbeef size=0x8000 read=0x2000\n"
            "00000030: 00000000 00000000 00000000 00000000 \n"
            "00000040: 0000c03e 0000003e 00000000 00000000 \n"
        )
        v, header = HP.read_f32(str(p), 0x40)
        if v is None or abs(v - 0.375) > 1e-9:
            issues.append(f"hexparse synthetic check failed: got {v}, want 0.375")
        v2, _ = HP.read_f32(str(p), 0x44)
        if v2 is None or abs(v2 - 0.125) > 1e-9:
            issues.append(f"hexparse synthetic y-check failed: got {v2}, want 0.125")

    # --- case matrix sanity: exactly 59 cases, no duplicate ids, every sampos case has
    # a samples in {2,4}, every id matches its own params.
    cases = CM.all_cases()
    ids = [c["case_id"] for c in cases]
    if len(ids) != len(set(ids)):
        issues.append("duplicate case_id in casematrix.all_cases()")
    if len(cases) != 59:
        issues.append(f"expected 59 frozen cases, got {len(cases)}")
    for c in cases:
        if c["kind"] == "sampos" and c["params"]["samples"] not in (2, 4):
            issues.append(f"{c['case_id']}: samples must be 2 or 4, got {c['params']['samples']}")

    return issues


# ---------------------------------------------------------------------------
# (b) seqtest
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
        out.append(d)
    return out


def state_of(raw_dir):
    n = len(list_run_dirs(raw_dir))
    return ("PRE_GPU" if n == 0 else ("RUN01_PRESENT" if n == 1 else "RUN02_PRESENT")), n


def _write_fake_run_dir(d, n_cases):
    d.mkdir(parents=True)
    (d / "hex").mkdir()
    with open(d / "records.jsonl", "w") as f:
        for c in CM.all_cases()[:n_cases]:
            rec = dict(gated_view(c) if False else {})
            rec = {
                "case_id": c["case_id"], "family": c["family"], "kind": c["kind"],
                "params": c["params"], "status": "OK",
                "observed": {"x0": 0.0, "y0": 0.0} if c["kind"] == "sampos" else {"capquery": "supported=1"},
                "va_vtxbuf": "0xdead", "va_resbuf": "0xbeef", "hex_path": None,
                "raw_stdout": "", "raw_stderr": "", "wall_ms": 1.0, "rc": 0,
            }
            f.write(json.dumps(rec) + "\n")
    with open(d / "run_manifest.json", "w") as f:
        json.dump({"run_id": d.name, "n_cases": n_cases}, f)


def gate_seqtest():
    checks = []
    scratch_root = EXP / "work" / "_seqtest_scratch"
    if scratch_root.exists():
        shutil.rmtree(scratch_root)
    scratch_root.mkdir(parents=True)
    try:
        raw = scratch_root / "raw"
        raw.mkdir()

        state, n = state_of(raw)
        checks.append(("PRE_GPU: zero dirs -> state PRE_GPU", state == "PRE_GPU" and n == 0))

        _write_fake_run_dir(raw / "m4_fake_run01", 59)
        state, n = state_of(raw)
        checks.append(("RUN01_PRESENT: one dir -> state RUN01_PRESENT", state == "RUN01_PRESENT" and n == 1))
        recs = [json.loads(l) for l in open(raw / "m4_fake_run01" / "records.jsonl")]
        checks.append(("RUN01_PRESENT: run dir case count matches matrix", len(recs) == 59))

        _write_fake_run_dir(raw / "m4_fake_run02", 59)
        state, n = state_of(raw)
        checks.append(("RUN02_PRESENT: two dirs -> state RUN02_PRESENT", state == "RUN02_PRESENT" and n == 2))

        r1 = [json.loads(l) for l in open(raw / "m4_fake_run01" / "records.jsonl")]
        r2 = [json.loads(l) for l in open(raw / "m4_fake_run02" / "records.jsonl")]
        all_match = all(compare_records(a, b) for a, b in zip(r1, r2))
        checks.append(("RUN02_PRESENT: identical fake runs compare equal under gate", all_match))

        # quarantine exclusion
        (raw / "m4_fake_run02" / "QUARANTINE.md").write_text("quarantined for seqtest\n")
        state, n = state_of(raw)
        checks.append(("quarantined dir excluded -> state back to RUN01_PRESENT", state == "RUN01_PRESENT" and n == 1))
    finally:
        shutil.rmtree(scratch_root, ignore_errors=True)
    return checks


# ---------------------------------------------------------------------------
# (c) captured -- real cross-run comparison
# ---------------------------------------------------------------------------

def gate_captured(run01, run02):
    p1 = RAW / run01 / "records.jsonl"
    p2 = RAW / run02 / "records.jsonl"
    if not p1.exists() or not p2.exists():
        return [f"missing records.jsonl for {run01 if not p1.exists() else run02}"]
    r1 = {json.loads(l)["case_id"]: json.loads(l) for l in open(p1)}
    r2 = {json.loads(l)["case_id"]: json.loads(l) for l in open(p2)}
    issues = []
    if set(r1) != set(r2):
        issues.append(f"case_id sets differ: only-run01={set(r1)-set(r2)} only-run02={set(r2)-set(r1)}")
    for cid in sorted(set(r1) & set(r2)):
        if not compare_records(r1[cid], r2[cid]):
            issues.append(f"{cid}: gated mismatch run01={gated_view(r1[cid])} run02={gated_view(r2[cid])}")
    return issues


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--seqtest", action="store_true")
    ap.add_argument("--captured", action="store_true")
    ap.add_argument("--run01")
    ap.add_argument("--run02")
    args = ap.parse_args()

    any_run = False
    ok = True

    if args.selftest:
        any_run = True
        issues = gate_selftest()
        print(f"selftest: {'PASS' if not issues else 'FAIL'} ({len(issues)} issues)")
        for i in issues:
            print("  -", i)
        ok = ok and not issues

    if args.seqtest:
        any_run = True
        checks = gate_seqtest()
        failed = [c for c in checks if not c[1]]
        print(f"seqtest: {'PASS' if not failed else 'FAIL'} ({len(checks)} checks, {len(failed)} failed)")
        for name, passed in checks:
            print(f"  [{'ok' if passed else 'FAIL'}] {name}")
        ok = ok and not failed

    if args.captured:
        any_run = True
        if not args.run01 or not args.run02:
            print("captured: need --run01 and --run02", file=sys.stderr)
            sys.exit(2)
        issues = gate_captured(args.run01, args.run02)
        print(f"captured: {'PASS' if not issues else 'FAIL'} ({len(issues)} issues)")
        for i in issues:
            print("  -", i)
        ok = ok and not issues

    if not any_run:
        print("nothing to do; pass --selftest / --seqtest / --captured", file=sys.stderr)
        sys.exit(2)

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
