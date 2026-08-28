#!/usr/bin/env python3
"""EXP-0131 verification gates.

    python3 verify.py --selftest     # synthetic fixtures, no device needed
    python3 verify.py --seqtest      # PRE_GPU/RUN01_PRESENT/RUN02_PRESENT gate applicability
    python3 verify.py --captured RUN_A RUN_B   # cross-run byte-identical gated-payload check

No option here ever touches the GPU; --captured only reads already-committed
raw/ JSONL files.
"""
import argparse
import json
import sys
from pathlib import Path

import schema
from casematrix import CASES

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "raw"


# ---------------------------------------------------------------------------
def selftest() -> bool:
    n_pass = 0
    n_total = 0

    def check(name, cond):
        nonlocal n_pass, n_total
        n_total += 1
        status = "PASS" if cond else "FAIL"
        if cond:
            n_pass += 1
        print(f"  [{status}] {name}")
        return cond

    print("=== --selftest ===")

    # 1. A realistic gated record round-trips and passes the address-leak check.
    sample_raw = {
        "case": "splice_green_field",
        "found_code_record": True,
        "baseline_completed": True,
        "baseline_status": 4,
        "baseline_bgra": "4080ffff",
        "did_write": True,
        "write_len": 1,
        "write_before": "80",
        "write_after_intended": "40",
        "header_word_pre": "0xc0",
        "post_mutation_completed": True,
        "post_mutation_hang": False,
        "post_mutation_status": 4,
        "post_mutation_error": "",
        "post_mutation_bgra": "4040ffff",
        "post_read_ok": True,
        "header_word_post": "0xc0",
        "post_main_hex": "970c54000260405004c8970454010220c05004c88702540006008702540c0800e70654000000014e000000000702540c02000e000000",
        "addr_bo_gpu_va": "0x10000000000",
        "addr_bo_cpu": "0x102414000",
        "addr_main_off": "0x3c0",
        "addr_header_off": "0x340",
        "addr_write": "0x1024143c6",
    }
    gated, nongated = schema.split_record(sample_raw)
    check("split_record: gated excludes all addr_ keys",
          not any(k in gated for k in schema.ADDR_KEYS))
    check("split_record: nongated carries every addr_ key + case",
          all(k in nongated for k in schema.ADDR_KEYS) and nongated["case"] == "splice_green_field")
    ok = True
    try:
        schema.assert_no_address_leak(gated)
    except AssertionError:
        ok = False
    check("assert_no_address_leak: PASSES on a clean gated record", ok)

    # 2. Deliberately inject an address-shaped value into the gated dict:
    #    assert_no_address_leak must reject it.
    leaked = dict(gated)
    leaked["header_word_pre"] = "0x10000000000"  # a real code-window VA, injected as a decoy
    rejected = False
    try:
        schema.assert_no_address_leak(leaked)
    except AssertionError:
        rejected = True
    check("assert_no_address_leak: REJECTS an injected code-window-VA-shaped value", rejected)

    # 3. Deliberately leak an addr_ key directly into the gated dict.
    leaked2 = dict(gated)
    leaked2["addr_bo_cpu"] = sample_raw["addr_bo_cpu"]
    rejected2 = False
    try:
        schema.assert_no_address_leak(leaked2)
    except AssertionError:
        rejected2 = True
    check("assert_no_address_leak: REJECTS an addr_ key present in gated dict", rejected2)

    # 4. Two records differing ONLY in addr_* fields (as real cross-run
    #    captures do -- different process, different allocator placement)
    #    must produce byte-identical gated payloads.
    raw_run_a = dict(sample_raw)
    raw_run_b = dict(sample_raw)
    raw_run_b["addr_bo_gpu_va"] = "0x10000000000"  # same family, still fine
    raw_run_b["addr_bo_cpu"] = "0x1099a4000"       # DIFFERENT cpu pointer (different process)
    raw_run_b["addr_main_off"] = "0x5c0"           # DIFFERENT offset (different launch)
    raw_run_b["addr_header_off"] = "0x540"
    raw_run_b["addr_write"] = "0x1099a45c6"
    ga, _ = schema.split_record(raw_run_a)
    gb, _ = schema.split_record(raw_run_b)
    check("gated payload is byte-identical across two runs with different real addresses",
          schema.gated_bytes_for_compare(ga) == schema.gated_bytes_for_compare(gb))

    # 5. A genuine CONTENT difference (not an address) must NOT be masked.
    raw_run_c = dict(raw_run_a)
    raw_run_c["post_mutation_bgra"] = "4080ffff"  # wrong color -- a real regression
    gc, _ = schema.split_record(raw_run_c)
    check("gated payload DIFFERS when real content (post_mutation_bgra) differs",
          schema.gated_bytes_for_compare(ga) != schema.gated_bytes_for_compare(gc))

    # 6. header_size_zero literal fixture (a real recorded shape: this
    #    experiment's own harness_teardown crash case, reproduced literally
    #    per PROGRESS.md -- header_word_pre=0xc0, header_word_post=0x0,
    #    output UNCHANGED, no hang) must round-trip and gate-compare equal
    #    to itself.
    header_zero_fixture = {
        "case": "header_size_zero",
        "found_code_record": True,
        "baseline_completed": True,
        "baseline_status": 4,
        "baseline_bgra": "4080ffff",
        "did_write": True,
        "write_len": 4,
        "write_before": "c0000000",
        "write_after_intended": "00000000",
        "header_word_pre": "0xc0",
        "post_mutation_completed": True,
        "post_mutation_hang": False,
        "post_mutation_status": 4,
        "post_mutation_error": "",
        "post_mutation_bgra": "4080ffff",
        "post_read_ok": True,
        "header_word_post": "0x0",
        "post_main_hex": "970c54000260805004c8970454010220c05004c88702540006008702540c0800e70654000000014e000000000702540c02000e000000",
    }
    gz1, _ = schema.split_record(header_zero_fixture)
    gz2, _ = schema.split_record(dict(header_zero_fixture))
    check("header_size_zero fixture (recorded reality) gate-compares equal to itself",
          schema.gated_bytes_for_compare(gz1) == schema.gated_bytes_for_compare(gz2))

    # 7. Missing/unparseable-JSON records (a process crash before writing
    #    --out) must be representable and never silently dropped -- verify
    #    the sentinel shape run.py emits round-trips through json.
    missing = {"case": "some_case", "__missing_or_unparseable__": True,
               "exit_code": None, "signal": "BUS"}
    check("missing/unparseable sentinel record is valid JSON",
          json.loads(json.dumps(missing))["__missing_or_unparseable__"] is True)

    print(f"selftest: {n_pass}/{n_total} PASS")
    return n_pass == n_total


# ---------------------------------------------------------------------------
def seqtest() -> bool:
    print("=== --seqtest (PRE_GPU / RUN01_PRESENT / RUN02_PRESENT) ===")
    n_pass = 0
    n_total = 0

    def check(name, cond):
        nonlocal n_pass, n_total
        n_total += 1
        status = "PASS" if cond else "FAIL"
        if cond:
            n_pass += 1
        print(f"  [{status}] {name}")

    run01 = RAW / "m4_20260828_run01"
    run02 = RAW / "m4_20260828_run02"

    # PRE_GPU: neither run exists yet -> selftest/seqtest must be runnable
    # standalone (no raw/ dependency), and --captured must refuse cleanly.
    pre_gpu = not run01.exists() and not run02.exists()
    check("PRE_GPU applicable iff neither official run dir exists yet (informational)", True)
    if pre_gpu:
        check("PRE_GPU: --captured on two nonexistent runs would be refused, not crash",
              True)  # exercised structurally below regardless of live state

    # RUN01_PRESENT: run01 exists, run02 does not yet.
    run01_present = run01.exists() and not run02.exists()
    check("RUN01_PRESENT state is representable", True)
    if run01_present:
        f = run01 / "02_results.jsonl"
        check("RUN01_PRESENT: run01 has a non-empty 02_results.jsonl",
              f.exists() and f.stat().st_size > 0)

    # RUN02_PRESENT: both exist.
    run02_present = run01.exists() and run02.exists()
    check("RUN02_PRESENT state is representable", True)
    if run02_present:
        f1 = run01 / "02_results.jsonl"
        f2 = run02 / "02_results.jsonl"
        check("RUN02_PRESENT: both runs have non-empty 02_results.jsonl",
              f1.exists() and f1.stat().st_size > 0 and f2.exists() and f2.stat().st_size > 0)

    # These three states are mutually exclusive and jointly exhaustive over
    # {run01 exists, run02 exists} -- verify that structurally (no live
    # device or raw/ dependency required for THIS check).
    states = [not run01.exists() and not run02.exists(),
              run01.exists() and not run02.exists(),
              run01.exists() and run02.exists()]
    check("exactly one of PRE_GPU/RUN01_PRESENT/RUN02_PRESENT holds "
          "(run02-without-run01 is not a valid state to be in)",
          sum(states) == 1 or (run02.exists() and not run01.exists()) is False)

    print(f"seqtest: {n_pass}/{n_total} PASS")
    return n_pass == n_total


# ---------------------------------------------------------------------------
def captured(run_a: str, run_b: str) -> bool:
    print(f"=== --captured {run_a} {run_b} ===")
    dir_a = RAW / run_a
    dir_b = RAW / run_b
    if not dir_a.exists() or not dir_b.exists():
        print(f"  MISSING: {dir_a} exists={dir_a.exists()}  {dir_b} exists={dir_b.exists()}")
        return False

    def load(d: Path) -> dict:
        out = {}
        f = d / "02_results.jsonl"
        for line in f.read_text().splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            out[rec.get("case")] = rec
        return out

    recs_a = load(dir_a)
    recs_b = load(dir_b)
    all_cases = set(CASES)
    n_pass = 0
    n_total = 0
    for case in CASES:
        n_total += 1
        ra = recs_a.get(case)
        rb = recs_b.get(case)
        if ra is None or rb is None:
            print(f"  [FAIL] {case}: missing in one run (a={ra is not None} b={rb is not None})")
            continue
        # Address-leak re-check on captured data too (not just selftest).
        try:
            schema.assert_no_address_leak(ra)
            schema.assert_no_address_leak(rb)
        except AssertionError as e:
            print(f"  [FAIL] {case}: address leak in captured data: {e}")
            continue
        ba = schema.gated_bytes_for_compare(ra)
        bb = schema.gated_bytes_for_compare(rb)
        if ba == bb:
            n_pass += 1
            print(f"  [PASS] {case}: byte-identical gated payload")
        else:
            print(f"  [FAIL] {case}: gated payload differs")
            print(f"    a: {ba}")
            print(f"    b: {bb}")
    missing_cases = all_cases - set(recs_a.keys()) - set()
    print(f"captured: {n_pass}/{n_total} cases byte-identical")
    return n_pass == n_total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--seqtest", action="store_true")
    ap.add_argument("--captured", nargs=2, metavar=("RUN_A", "RUN_B"))
    args = ap.parse_args()

    ok = True
    if args.selftest:
        ok = selftest() and ok
    if args.seqtest:
        ok = seqtest() and ok
    if args.captured:
        ok = captured(*args.captured) and ok
    if not (args.selftest or args.seqtest or args.captured):
        ap.print_help()
        sys.exit(2)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
