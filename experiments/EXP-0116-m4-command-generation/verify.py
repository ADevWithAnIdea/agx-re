#!/usr/bin/env python3
"""EXP-0116 verify.py -- the five standing gates.

  --selftest                 synthetic fixtures, no device needed
  --seqtest                  PRE_GPU / RUN01_PRESENT / RUN02_PRESENT gate
                              applicability, no device needed
  --preflight --run-id X     before running: binaries present, run-id free
  --between-runs --run01-id X   after run01: well-formed, no address leak
  --captured --run01-id X --run02-id Y   cross-run gate: gated JSONL
                              byte-identical per case

CLEAN ROOM: pure bookkeeping over our own harness output and schema.py.
Inspects no Apple binary. All scratch built by --selftest lives under
work/selftest_scratch/ inside this experiment directory (never /tmp).
"""
import argparse
import json
import os
import shutil
import sys

import schema

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "work")
RAW = os.path.join(HERE, "raw")
SCRATCH = os.path.join(WORK, "selftest_scratch")


def _fresh_scratch():
    if os.path.exists(SCRATCH):
        shutil.rmtree(SCRATCH)
    os.makedirs(SCRATCH)
    return SCRATCH


# ---------------------------------------------------------------------------
# --selftest: fixtures built from RECORDED REALITY (these are literal
# reproductions of this experiment's own calibration observations -- the
# 732/732/36 same_cb shape, tag 0x20, the skip_seg1 positive, and the
# codeswap x/y record pair -- not invented shapes). See PROGRESS.md.

FIXTURE_SKIP_SEG1_RUN_A = {
    "case": "skip_seg1", "mechanism": "same_cb",
    "found_seg0": True, "seg0_count": 732,
    "found_seg1": True, "seg1_count": 732,
    "found_seg2": True, "seg2_count": 36,
    "natural_chain_ok": True, "case_valid_setup": True, "wrote": True,
    "pre_link_hi": "0x20000100", "pre_link_lo": "0x00150000",
    "new_link_hi": "0x20000100", "new_link_lo": "0x001e0000", "new_link_tag": "0x20",
    "hang": False, "final_status": 4, "final_error": None,
    "readback_A_word0": "0xc0000023", "readback_MID_word0": "0x5eed1000",
    "expect_seg0_last": "0xa00002db", "expect_seg1_last": "0xb00002db", "expect_seg2_last": "0xc0000023",
    "sentinel_A": "0x5eed0000", "sentinel_MID": "0x5eed1000",
    "fault_only_after_seg0": False,
    "raw_addrs": {"seg0_va": "0x100000b0000", "seg1_va": "0x10000150000",
                  "seg2_va": "0x100001e0000", "new_target": "0x100001e0000"},
}
# A second "run" at genuinely different absolute addresses (as a real second
# process invocation would produce) but IDENTICAL content-level outcome.
FIXTURE_SKIP_SEG1_RUN_B = dict(FIXTURE_SKIP_SEG1_RUN_A)
FIXTURE_SKIP_SEG1_RUN_B["pre_link_hi"] = "0x20000100"
FIXTURE_SKIP_SEG1_RUN_B["pre_link_lo"] = "0x00230000"
FIXTURE_SKIP_SEG1_RUN_B["new_link_hi"] = "0x20000100"
FIXTURE_SKIP_SEG1_RUN_B["new_link_lo"] = "0x002c0000"
FIXTURE_SKIP_SEG1_RUN_B["raw_addrs"] = {"seg0_va": "0x100000190000", "seg1_va": "0x100000230000",
                                          "seg2_va": "0x1000002c0000", "new_target": "0x1000002c0000"}

# A REAL discovered case (see PROGRESS.md / schema.py docstring): two runs
# of the same FAULTING case (final_status=5, not Completed) whose readback
# content genuinely differs because how much of a faulted command buffer's
# earlier legitimate work is memory-visible by the time the fault is
# reported is racy -- literal reproduction of misaligned_word8's run01 vs
# run02 values from m4_20260828_run01/run02.
FIXTURE_FAULT_RUN_A = dict(FIXTURE_SKIP_SEG1_RUN_A)
FIXTURE_FAULT_RUN_A.update({
    "case": "misaligned_word8", "wrote": True, "final_status": 5,
    "final_error": "Caused GPU Address Fault Error (0000000b:kIOGPUCommandBufferCallbackErrorPageFault)",
    "readback_A_word0": "0x5eed0000", "readback_MID_word0": "0x5eed1000",
})
FIXTURE_FAULT_RUN_B = dict(FIXTURE_FAULT_RUN_A)
FIXTURE_FAULT_RUN_B["readback_A_word0"] = "0xc0000002"  # genuinely different: partial progress

# A SECOND real discovered case: two runs of `encoding_max` with the SAME
# final_status (5) but a DIFFERENT verbatim final_error string -- literal
# reproduction of m4_20260828_run03 vs run04.
FIXTURE_HANG_RUN_A = dict(FIXTURE_SKIP_SEG1_RUN_A)
FIXTURE_HANG_RUN_A.update({
    "case": "encoding_max", "wrote": True, "final_status": 5,
    "final_error": "Caused GPU Hang Error (00000003:kIOGPUCommandBufferCallbackErrorHang)",
    "readback_A_word0": "0xa00002db", "readback_MID_word0": "0x5eed1000",
})
FIXTURE_HANG_RUN_B = dict(FIXTURE_HANG_RUN_A)
FIXTURE_HANG_RUN_B["final_error"] = "Discarded (victim of GPU error/recovery) (00000005:kIOGPUCommandBufferCallbackErrorInnocentVictim)"

FIXTURE_CODESWAP = {
    "setup_ok": True, "extracted_ok": True, "wrote": True,
    "seg0_count": 732, "seg1_count": 732, "seg2_count": 38,
    "x_ptr": "0x00007970", "y_ptr": "0x00007973",
    "record_x_hex": "0000080000000001707900000100004040000000010000000100000020000000010000000100000060010060",
    "record_y_hex": "0000080000000001737900000100004040000000010000000100000020000000010000000100000060010060",
    "hybrid_hex":   "0000080000000001737900000100004040000000010000000100000020000000010000000100000060010060",
    "hang": False, "final_status": 5, "final_error": "Caused GPU Address Fault Error (0000000b:kIOGPUCommandBufferCallbackErrorPageFault)",
    "readback_A": "0x5eed0000", "readback_MID": "0x5eed1000", "readback_X": "0x5eed2000", "readback_Y": "0x5eed3000",
    "sentinel_X": "0x5eed2000", "sentinel_Y": "0x5eed3000",
    "expect_kernel_x_value": "0x11111111", "expect_kernel_y_value": "0x22222222",
    "hybrid_va": "0x10000080000", "seg0_va": "0x100000c0000",
}


def selftest():
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

    # 1. gating is idempotent-shaped: same content, different addresses -> byte-identical gated JSON
    gA = schema.build_gated_linksplice(FIXTURE_SKIP_SEG1_RUN_A)
    gB = schema.build_gated_linksplice(FIXTURE_SKIP_SEG1_RUN_B)
    check("linksplice gated dict identical across different absolute addresses",
          json.dumps(gA, sort_keys=True) == json.dumps(gB, sort_keys=True))

    # 2. addrs dicts legitimately DIFFER between the two synthetic runs
    aA = schema.build_addrs_linksplice(FIXTURE_SKIP_SEG1_RUN_A)
    aB = schema.build_addrs_linksplice(FIXTURE_SKIP_SEG1_RUN_B)
    check("linksplice addrs dict legitimately differs across runs",
          json.dumps(aA, sort_keys=True) != json.dumps(aB, sort_keys=True))

    # 3. no address-shaped key/value in the gated dict
    try:
        schema.assert_no_address_leak(gA)
        ok = True
    except AssertionError as e:
        print("    unexpected:", e)
        ok = False
    check("no-address-leak holds for a genuine gated linksplice record", ok)

    # 4. deliberately corrupt: inject an address-shaped key -> must be caught
    corrupt = dict(gA)
    corrupt["seg0_va"] = "0x100000b0000"
    try:
        schema.assert_no_address_leak(corrupt)
        caught = False
    except AssertionError:
        caught = True
    check("assert_no_address_leak CATCHES an injected va-shaped key", caught)

    # 5. deliberately corrupt: inject a long hex VALUE under an innocuous key
    corrupt2 = dict(gA)
    corrupt2["some_field"] = "0x100001e0000"
    try:
        schema.assert_no_address_leak(corrupt2)
        caught2 = False
    except AssertionError:
        caught2 = True
    check("assert_no_address_leak CATCHES an injected va-shaped value", caught2)

    # 5b. RACY-ON-FAULT correction: two runs of the SAME faulting case with
    # genuinely different readback_A_word0 (a real discovered hardware race,
    # not a bug) must gate to IDENTICAL records (the racy field excluded),
    # while their addrs siblings correctly retain the differing value.
    gFA = schema.build_gated_linksplice(FIXTURE_FAULT_RUN_A)
    gFB = schema.build_gated_linksplice(FIXTURE_FAULT_RUN_B)
    check("racy-on-fault: gated dict identical despite genuinely different readback on a FAULT",
          json.dumps(gFA, sort_keys=True) == json.dumps(gFB, sort_keys=True))
    check("racy-on-fault: readback_A_word0 is NOT a key in the gated fault record",
          "readback_A_word0" not in gFA)
    aFA = schema.build_addrs_linksplice(FIXTURE_FAULT_RUN_A)
    aFB = schema.build_addrs_linksplice(FIXTURE_FAULT_RUN_B)
    check("racy-on-fault: addrs sibling DOES retain the differing readback_A_word0",
          aFA.get("readback_A_word0") != aFB.get("readback_A_word0"))
    # and, symmetrically, a COMPLETED case's readback must still be gated
    # (this field is only excluded when final_status != COMPLETED_STATUS)
    gS = schema.build_gated_linksplice(FIXTURE_SKIP_SEG1_RUN_A)
    check("a COMPLETED case's readback_A_word0 IS still part of the gated record",
          "readback_A_word0" in gS and gS["readback_A_word0"] == "0xc0000023")

    # 5c. RACY final_error correction: two runs of the SAME hang-class case
    # with the same final_status but a genuinely different verbatim
    # final_error string must gate to identical records (category only).
    gHA = schema.build_gated_linksplice(FIXTURE_HANG_RUN_A)
    gHB = schema.build_gated_linksplice(FIXTURE_HANG_RUN_B)
    check("racy-final_error: gated dict identical despite different verbatim Hang/InnocentVictim strings",
          json.dumps(gHA, sort_keys=True) == json.dumps(gHB, sort_keys=True))
    check("racy-final_error: gated record carries the category, not the verbatim string",
          "final_error" not in gHA and gHA.get("final_error_category") == "GPU_RECOVERY_EVENT")
    aHA = schema.build_addrs_linksplice(FIXTURE_HANG_RUN_A)
    aHB = schema.build_addrs_linksplice(FIXTURE_HANG_RUN_B)
    check("racy-final_error: addrs sibling DOES retain the differing verbatim string",
          aHA.get("final_error") != aHB.get("final_error"))
    check("PageFault and GPU_RECOVERY_EVENT classify to DIFFERENT categories (category is not vacuous)",
          schema._classify_final_error(FIXTURE_FAULT_RUN_A["final_error"]) !=
          schema._classify_final_error(FIXTURE_HANG_RUN_A["final_error"]))

    # 6. codeswap gating redacts the +0x08 field but preserves the rest
    gc = schema.build_gated_codeswap(FIXTURE_CODESWAP)
    check("codeswap gated record redacts +0x08 (record_x != record_y after redaction... they SHOULD become equal, since that IS the only difference)",
          gc["record_x_hex_redacted"] == gc["record_y_hex_redacted"])
    check("codeswap gated record redaction preserves length",
          len(gc["record_x_hex_redacted"]) == len(FIXTURE_CODESWAP["record_x_hex"]))
    check("codeswap gated record does not contain x_ptr/y_ptr",
          "x_ptr" not in gc and "y_ptr" not in gc)
    ac = schema.build_addrs_codeswap(FIXTURE_CODESWAP)
    check("codeswap addrs record DOES carry x_ptr/y_ptr/hybrid_va",
          "x_ptr" in ac and "y_ptr" in ac and "hybrid_va" in ac)
    try:
        schema.assert_no_address_leak(gc)
        ok2 = True
    except AssertionError as e:
        print("    unexpected:", e)
        ok2 = False
    check("no-address-leak holds for a genuine gated codeswap record", ok2)

    # 7. redaction is a real content mask, not a no-op (values other than
    # +0x08 differ would NOT be masked away)
    fake_x = dict(FIXTURE_CODESWAP)
    fake_x["record_y_hex"] = "ff" + FIXTURE_CODESWAP["record_y_hex"][2:]  # corrupt a DIFFERENT byte
    gfx = schema.build_gated_codeswap(fake_x)
    check("redaction does NOT hide a genuine difference outside +0x08",
          gfx["record_x_hex_redacted"] != gfx["record_y_hex_redacted"])

    # 8. missing-field tolerance: a process-timeout stub record (as run.py
    # emits) must not crash the gate builder or the leak check.
    stub = {"case": "some_case", "mechanism": "same_cb", "PROCESS_LEVEL_TIMEOUT_OR_MISSING_OUTPUT": True}
    g_stub = schema.build_gated_linksplice(stub)
    try:
        schema.assert_no_address_leak(g_stub)
        ok3 = True
    except AssertionError:
        ok3 = False
    check("a process-timeout stub record passes the gate builder + leak check", ok3)

    print(f"selftest: {n_pass}/{n_total} PASS")
    return n_pass == n_total


# ---------------------------------------------------------------------------
def seqtest():
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

    print("=== --seqtest ===")
    scratch = _fresh_scratch()
    fake_run = os.path.join(scratch, "raw", "fake_run01")

    # PRE_GPU: before any raw/<run-id> exists, preflight-style checks must
    # find it absent (i.e. a run id is "free").
    check("PRE_GPU: fake_run01 does not exist before creation", not os.path.exists(fake_run))

    # RUN01_PRESENT: after creating run01's directory + a minimal gated file,
    # between-runs-style checks must find it present and parseable.
    os.makedirs(fake_run)
    with open(os.path.join(fake_run, "02_results.jsonl"), "w") as f:
        f.write(json.dumps({"case": "baseline_check", "wrote": False}) + "\n")
    check("RUN01_PRESENT: fake_run01/02_results.jsonl exists and parses",
          os.path.exists(os.path.join(fake_run, "02_results.jsonl")))
    with open(os.path.join(fake_run, "02_results.jsonl")) as f:
        lines = [json.loads(l) for l in f if l.strip()]
    check("RUN01_PRESENT: exactly one well-formed record", len(lines) == 1 and lines[0]["case"] == "baseline_check")

    # RUN02_PRESENT: captured-gate-style checks require BOTH run01 and run02;
    # must correctly detect run02 missing, then correctly detect it present.
    fake_run2 = os.path.join(scratch, "raw", "fake_run02")
    check("RUN02_PRESENT (before): fake_run02 does not exist yet", not os.path.exists(fake_run2))
    os.makedirs(fake_run2)
    with open(os.path.join(fake_run2, "02_results.jsonl"), "w") as f:
        f.write(json.dumps({"case": "baseline_check", "wrote": False}) + "\n")
    check("RUN02_PRESENT (after): fake_run02/02_results.jsonl exists", os.path.exists(os.path.join(fake_run2, "02_results.jsonl")))

    # a captured-style gate over the two fake runs must PASS (identical content)
    ok_gate, report = compare_gated(os.path.join(fake_run, "02_results.jsonl"),
                                     os.path.join(fake_run2, "02_results.jsonl"))
    check("captured-style gate over two identical fake runs PASSES", ok_gate)

    # and must FAIL when the two runs genuinely differ in content
    with open(os.path.join(fake_run2, "02_results.jsonl"), "w") as f:
        f.write(json.dumps({"case": "baseline_check", "wrote": True}) + "\n")
    ok_gate2, report2 = compare_gated(os.path.join(fake_run, "02_results.jsonl"),
                                       os.path.join(fake_run2, "02_results.jsonl"))
    check("captured-style gate CORRECTLY FAILS when content genuinely differs", not ok_gate2)

    shutil.rmtree(scratch, ignore_errors=True)
    print(f"seqtest: {n_pass}/{n_total} PASS")
    return n_pass == n_total


# ---------------------------------------------------------------------------
def compare_gated(path_a, path_b):
    def load(path):
        with open(path) as f:
            return [json.loads(l) for l in f if l.strip()]
    a = load(path_a)
    b = load(path_b)
    if len(a) != len(b):
        return False, f"record count differs: {len(a)} vs {len(b)}"
    mismatches = []
    for i, (ra, rb) in enumerate(zip(a, b)):
        if ra.get("case") != rb.get("case"):
            mismatches.append({"index": i, "kind": "case_name_mismatch", "a": ra.get("case"), "b": rb.get("case")})
            continue
        if json.dumps(ra, sort_keys=True) != json.dumps(rb, sort_keys=True):
            mismatches.append({"index": i, "case": ra.get("case"), "kind": "content_mismatch"})
    return (len(mismatches) == 0), mismatches


def preflight(run_id):
    print(f"=== --preflight --run-id {run_id} ===")
    ok = True
    linksplice_bin = os.path.join(WORK, "bin", "linksplice")
    codeswap_bin = os.path.join(WORK, "bin", "codeswap")
    for p in (linksplice_bin, codeswap_bin):
        exists = os.path.exists(p)
        print(f"  [{'PASS' if exists else 'INFO'}] {p} present (will be (re)built by run.py if missing)")
    raw_dir = os.path.join(RAW, run_id)
    free = not os.path.exists(raw_dir)
    print(f"  [{'PASS' if free else 'FAIL'}] run id {run_id!r} not already used under raw/")
    ok &= free
    contract = os.path.join(HERE, "CAPTURE_CONTRACT.json")
    has_contract = os.path.exists(contract)
    print(f"  [{'PASS' if has_contract else 'FAIL'}] CAPTURE_CONTRACT.json present")
    ok &= has_contract
    return ok


def between_runs(run01_id):
    print(f"=== --between-runs --run01-id {run01_id} ===")
    path = os.path.join(RAW, run01_id, "02_results.jsonl")
    if not os.path.exists(path):
        print(f"  [FAIL] {path} missing")
        return False
    ok = True
    with open(path) as f:
        for i, line in enumerate(f):
            if not line.strip():
                continue
            rec = json.loads(line)
            try:
                schema.assert_no_address_leak(rec)
            except AssertionError as e:
                print(f"  [FAIL] line {i}: {e}")
                ok = False
    print(f"  [{'PASS' if ok else 'FAIL'}] every gated record in {run01_id} is address-leak-free")
    return ok


def captured(run01_id, run02_id):
    print(f"=== --captured --run01-id {run01_id} --run02-id {run02_id} ===")
    p1 = os.path.join(RAW, run01_id, "02_results.jsonl")
    p2 = os.path.join(RAW, run02_id, "02_results.jsonl")
    for p in (p1, p2):
        if not os.path.exists(p):
            print(f"  [FAIL] {p} missing")
            return False
    ok, report = compare_gated(p1, p2)
    print(f"  [{'PASS' if ok else 'FAIL'}] {run01_id} vs {run02_id} gated payload byte-identical per case")
    if not ok:
        print("  mismatches:", json.dumps(report, indent=2))
    out_path = os.path.join(HERE, "analysis")
    os.makedirs(out_path, exist_ok=True)
    with open(os.path.join(out_path, "cross_run_report.json"), "w") as f:
        json.dump({"run01": run01_id, "run02": run02_id, "ok": ok, "mismatches": report}, f, indent=2)
        f.write("\n")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--seqtest", action="store_true")
    ap.add_argument("--preflight", action="store_true")
    ap.add_argument("--between-runs", action="store_true")
    ap.add_argument("--captured", action="store_true")
    ap.add_argument("--run-id")
    ap.add_argument("--run01-id")
    ap.add_argument("--run02-id")
    args = ap.parse_args()

    overall_ok = True
    ran_something = False

    if args.selftest:
        ran_something = True
        overall_ok &= selftest()
    if args.seqtest:
        ran_something = True
        overall_ok &= seqtest()
    if args.preflight:
        ran_something = True
        overall_ok &= preflight(args.run_id)
    if args.between_runs:
        ran_something = True
        overall_ok &= between_runs(args.run01_id or args.run_id)
    if args.captured:
        ran_something = True
        overall_ok &= captured(args.run01_id, args.run02_id)

    if not ran_something:
        print("nothing to do; pass at least one of --selftest/--seqtest/--preflight/--between-runs/--captured", file=sys.stderr)
        sys.exit(2)

    sys.exit(0 if overall_ok else 1)


if __name__ == "__main__":
    main()
