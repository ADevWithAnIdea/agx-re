#!/usr/bin/env python3
"""EXP-0129 fail-closed verifier: --selftest, --seqtest, --crossrun, --smoke.

--selftest and --seqtest use ONLY synthetic scratch copies under
work/selftest_scratch/ / work/seqtest_scratch/ (never touch raw/) and are
runnable in EVERY tree state, including with zero raw/ captures present.
--smoke wraps run.py --smoke-only (writes only to work/, never raw/).
Architecture follows EXP-0109/EXP-0117's verify.py (our own prior authored
code in this project).
"""
import argparse, json, shutil, subprocess, sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import casematrix as CM
import run as R

TOTAL = len(CM.full_case_list())
FIXTURE = HERE / "harness" / "fixtures" / "recorded_reality.json"


def fail(s):
    raise SystemExit("FAIL " + s)


def load_jsonl(p: Path):
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def run_complete(run_dir: Path) -> bool:
    manifest = run_dir / "05_run_manifest.json"
    results = run_dir / "04_results.jsonl"
    if not manifest.exists() or not results.exists():
        return False
    try:
        m = json.loads(manifest.read_text())
        recs = load_jsonl(results)
    except Exception:
        return False
    return m.get("total") == TOTAL and len(recs) == TOTAL


def tree_state(raw_dir: Path):
    if not raw_dir.exists():
        return "PRE_GPU", []
    complete = sorted(d.name for d in raw_dir.iterdir() if d.is_dir() and run_complete(d))
    if len(complete) == 0:
        return "PRE_GPU", complete
    if len(complete) == 1:
        return "RUN01_PRESENT", complete
    return "RUN02_PRESENT", complete


# ---------------------------------------------------------------- crossrun --
def crossrun(run_a: Path, run_b: Path, quiet=False):
    ra = load_jsonl(run_a / "04_results.jsonl")
    rb = load_jsonl(run_b / "04_results.jsonl")
    if len(ra) != len(rb):
        fail(f"record count differs: {len(ra)} vs {len(rb)}")
    by_id_a = {r["id"]: r for r in ra}
    by_id_b = {r["id"]: r for r in rb}
    if set(by_id_a) != set(by_id_b):
        fail(f"case-id sets differ: {set(by_id_a) ^ set(by_id_b)}")
    mismatches = []
    for cid, a in by_id_a.items():
        b = by_id_b[cid]
        ga, gb = json.dumps(a["gated"], sort_keys=True), json.dumps(b["gated"], sort_keys=True)
        if ga != gb:
            mismatches.append({"id": cid, "gated_a": a["gated"], "gated_b": b["gated"]})
    result = {"total": len(ra), "mismatches": len(mismatches), "pass": len(mismatches) == 0,
              "mismatch_ids": [m["id"] for m in mismatches]}
    if not quiet:
        print(json.dumps(result, indent=2))
    return result, mismatches


# ------------------------------------------------------------------ selftest
def make_run_dir(base: Path, name: str, records):
    d = base / name
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "04_results.jsonl", "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    (d / "05_run_manifest.json").write_text(json.dumps({"total": len(records)}))
    return d


def load_fixture():
    if not FIXTURE.exists():
        fail(f"missing fixture {FIXTURE} (selftest requires recorded-reality shapes)")
    return json.loads(FIXTURE.read_text())


def selftest():
    n = 0
    scratch = HERE / "work" / "selftest_scratch"
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)

    fx = load_fixture()
    base_records = fx["sample_records"]
    assert len(base_records) >= 2, "fixture needs >=2 sample records"

    a = [dict(r, meta={"duration_ms": 111, "started_utc": "T1"}) for r in base_records]
    b = [dict(r, meta={"duration_ms": 999, "started_utc": "T2"}) for r in base_records]
    d1 = make_run_dir(scratch, "s1a", a)
    d2 = make_run_dir(scratch, "s1b", b)
    res, _ = crossrun(d1, d2, quiet=True)
    if not res["pass"]:
        fail("selftest#1: identical-gated/differing-meta pair should PASS crossrun")
    n += 1

    b2 = [dict(r) for r in base_records]
    b2[0] = dict(b2[0], gated=dict(b2[0]["gated"], status="DELIBERATELY_WRONG"))
    d3 = make_run_dir(scratch, "s2b", b2)
    res2, mm2 = crossrun(d1, d3, quiet=True)
    if res2["pass"]:
        fail("selftest#2: semantically-differing gated pair should FAIL crossrun")
    if res2["mismatch_ids"] != [base_records[0]["id"]]:
        fail(f"selftest#2: wrong mismatch id reported: {res2['mismatch_ids']}")
    n += 1

    bad = {"status": "OK", "duration_ms": 5}
    try:
        R.check_no_nondet(bad)
        fail("selftest#3: check_no_nondet should have raised on forbidden key")
    except SystemExit:
        pass
    n += 1

    bad2 = {"status": "OK", "result": {"pid": 123}}
    try:
        R.check_no_nondet(bad2)
        fail("selftest#4: check_no_nondet should catch nested forbidden key")
    except SystemExit:
        pass
    n += 1

    R.check_no_nondet({"status": "OK", "result": {"vid": 1, "attr": [0.1, 0.2]}})
    n += 1

    d4 = make_run_dir(scratch, "s6b", a[:-1])
    try:
        crossrun(d1, d4, quiet=True)
        fail("selftest#6: record-count mismatch should raise")
    except SystemExit:
        pass
    n += 1

    empty_raw = scratch / "empty_raw"
    st, _ = tree_state(empty_raw)
    if st != "PRE_GPU":
        fail(f"selftest#7a: expected PRE_GPU, got {st}")
    one_raw = scratch / "one_raw"
    one_raw.mkdir()
    manifest = {"total": TOTAL}
    d = one_raw / "runX"
    d.mkdir()
    (d / "05_run_manifest.json").write_text(json.dumps(manifest))
    with open(d / "04_results.jsonl", "w") as f:
        for i in range(TOTAL):
            f.write(json.dumps({"i": i, "id": f"c{i}", "gated": {"status": "OK"}, "meta": {}}) + "\n")
    st, _ = tree_state(one_raw)
    if st != "RUN01_PRESENT":
        fail(f"selftest#7b: expected RUN01_PRESENT, got {st}")
    two_raw = scratch / "two_raw"
    two_raw.mkdir()
    for name in ("runX", "runY"):
        d = two_raw / name
        d.mkdir()
        (d / "05_run_manifest.json").write_text(json.dumps(manifest))
        with open(d / "04_results.jsonl", "w") as f:
            for i in range(TOTAL):
                f.write(json.dumps({"i": i, "id": f"c{i}", "gated": {"status": "OK"}, "meta": {}}) + "\n")
    st, _ = tree_state(two_raw)
    if st != "RUN02_PRESENT":
        fail(f"selftest#7c: expected RUN02_PRESENT, got {st}")
    n += 1

    partial_raw = scratch / "partial_raw"
    partial_raw.mkdir()
    d = partial_raw / "runZ"
    d.mkdir()
    (d / "05_run_manifest.json").write_text(json.dumps(manifest))
    with open(d / "04_results.jsonl", "w") as f:
        f.write(json.dumps({"i": 0, "id": "c0", "gated": {"status": "OK"}, "meta": {}}) + "\n")
    st, _ = tree_state(partial_raw)
    if st != "PRE_GPU":
        fail(f"selftest#8: an incomplete run dir must not count; expected PRE_GPU, got {st}")
    n += 1

    ids = [c["id"] for c in CM.full_case_list()]
    if len(ids) != len(set(ids)) or len(ids) != TOTAL:
        fail("selftest#9: casematrix id/TOTAL invariant broken")
    n += 1

    # 10. isahelper.disasm_summary correctness on a known synthetic byte
    # stream (our own deterministic table-driven decoder, not any Apple
    # binary): a single `stop` opcode (0e 00 00 00) must decode cleanly to
    # exactly 1 instruction with 0 leftover bytes.
    import isahelper
    summ = isahelper.disasm_summary("0e000000")
    if summ["n_instr"] != 1 or not summ["clean"] or summ["leftover_bytes"] != 0:
        fail(f"selftest#10: disasm_summary parsed a known-clean stop op incorrectly: {summ}")
    n += 1

    # 11. check_no_nondet recurses into lists of dicts (the 'iters' array shape).
    bad3 = {"status": "OK", "iters": [{"dst": 0}, {"timestamp": "now"}]}
    try:
        R.check_no_nondet(bad3)
        fail("selftest#11: check_no_nondet should catch forbidden key inside a list of dicts")
    except SystemExit:
        pass
    n += 1

    shutil.rmtree(scratch)
    print(f"SELFTEST: {n}/{n} PASS")
    return True


# ------------------------------------------------------------------- seqtest
def seqtest():
    n = 0
    scratch = HERE / "work" / "seqtest_scratch"
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)

    raw0 = scratch / "raw0"
    st, complete = tree_state(raw0)
    assert st == "PRE_GPU"
    try:
        crossrun(raw0 / "a", raw0 / "b", quiet=True)
        fail("seqtest: crossrun must fail in PRE_GPU (missing dirs)")
    except Exception:
        pass
    n += 1

    raw1 = scratch / "raw1"
    raw1.mkdir()
    full = []
    for i, c in enumerate(CM.full_case_list()):
        full.append({"i": i, "id": c["id"], "family": c["family"],
                     "gated": {"status": "OK", "backend": c["backend"]}, "meta": {"duration_ms": 1}})
    make_run_dir(raw1, "run01", full)
    (raw1 / "run01" / "05_run_manifest.json").write_text(json.dumps({"total": TOTAL}))
    st, complete = tree_state(raw1)
    if st != "RUN01_PRESENT":
        fail(f"seqtest: expected RUN01_PRESENT, got {st}")
    try:
        crossrun(raw1 / "run01", raw1 / "run01", quiet=True)
    except Exception as e:
        fail(f"seqtest: crossrun of a dir against itself should not raise: {e}")
    n += 1

    raw2 = scratch / "raw2"
    raw2.mkdir()
    make_run_dir(raw2, "run01", full)
    (raw2 / "run01" / "05_run_manifest.json").write_text(json.dumps({"total": TOTAL}))
    make_run_dir(raw2, "run02", full)
    (raw2 / "run02" / "05_run_manifest.json").write_text(json.dumps({"total": TOTAL}))
    st, complete = tree_state(raw2)
    if st != "RUN02_PRESENT":
        fail(f"seqtest: expected RUN02_PRESENT, got {st}")
    res, _ = crossrun(raw2 / "run01", raw2 / "run02", quiet=True)
    if not res["pass"]:
        fail("seqtest: identical run01/run02 fixtures should crossrun PASS")
    n += 1

    shutil.rmtree(scratch)
    print(f"SEQTEST: {n}/{n} PASS (PRE_GPU -> RUN01_PRESENT -> RUN02_PRESENT all correct)")
    return True


def smoke():
    r = subprocess.run([sys.executable, str(HERE / "run.py"), "--run", "smoke_tmp",
                         "--out", str(HERE / "work" / "smoke_out_unused"), "--smoke-only"],
                        capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        fail(f"smoke: run.py --smoke-only exited {r.returncode}: {r.stderr[-2000:]}")
    try:
        j = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception as e:
        fail(f"smoke: could not parse run.py --smoke-only output: {e}\n{r.stdout[-1000:]}")
    if not j.get("all_ok"):
        fail(f"smoke: not all smoke cases OK: {j}")
    unused = HERE / "work" / "smoke_out_unused"
    if (unused / "04_results.jsonl").exists() or (unused / "05_run_manifest.json").exists():
        fail("smoke: --smoke-only wrote case results/manifest to its --out dir (should only "
             "happen for a real capture)")
    raw_dir = HERE / "raw"
    if raw_dir.exists() and any(raw_dir.iterdir()):
        fail("smoke: raw/ is non-empty -- smoke gate must run BEFORE any official capture exists")
    print("SMOKE: PASS (2/2 cases OK; --smoke-only wrote no case results/manifest, and raw/ "
          "has no official capture yet)")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--seqtest", action="store_true")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--crossrun", nargs=2, metavar=("RUN_A", "RUN_B"))
    args = ap.parse_args()
    if args.selftest:
        selftest()
    elif args.seqtest:
        seqtest()
    elif args.smoke:
        smoke()
    elif args.crossrun:
        res, mm = crossrun(Path(args.crossrun[0]), Path(args.crossrun[1]))
        if not res["pass"]:
            sys.exit(1)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
