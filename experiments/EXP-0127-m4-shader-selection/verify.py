#!/usr/bin/env python3
"""EXP-0127 verify.py -- standing gates.

  --selftest    synthetic fixtures: gating is address-invariant, address
                leaks are caught, racy-on-fault fields are excluded
                correctly, and a genuine content mismatch is still caught.
  --seqtest     PRE_GPU / RUN01_PRESENT / RUN02_PRESENT gate-applicability
                checks against a synthetic fake run directory (never the
                real raw/<run-id>).
  --captured RUN01 RUN02
                cross-run gate: raw/<RUN01>/gated.jsonl and
                raw/<RUN02>/gated.jsonl must be byte-identical (as parsed
                JSON, per-line, order-preserved) after gating; addrs.jsonl
                siblings are NOT compared (legitimately differ run to run).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import schema  # noqa: E402

RAW = ROOT / "raw"
WORK = ROOT / "work"

n_pass = 0
n_total = 0


def check(label, cond):
    global n_pass, n_total
    n_total += 1
    ok = bool(cond)
    n_pass += int(ok)
    print(("PASS" if ok else "FAIL") + f": {label}")
    return ok


# ---------------------------------------------------------------------------
def selftest():
    print("=== --selftest ===")
    ok = True

    # 1. Gating is address-invariant: two "runs" with different raw VAs but
    #    identical architectural facts gate to byte-identical records.
    fake_vstoken_run1 = {
        "mode": "uniform", "count": 520,
        "schedule": [0, 1, 2, 3, 506, 507],
        "tokens": [448, 832, 960, 1088, 2818112, 2818240],
        "deltas": [384, 128, 128, 2752640, 128],
        "linear_base": 704, "linear_step": 128,
        "first_step_anomaly_token": 448,
        "boundary_index": 506, "boundary_delta": 2752640,
        "post_boundary_step_ok": True,
        "readback_status_all_completed": True,
        "new_region_appeared": True, "new_region_size": 262144,
        "new_region_va": 0x2b0000,  # differs between "runs" -- must not gate
    }
    fake_vstoken_run2 = dict(fake_vstoken_run1)
    fake_vstoken_run2["new_region_va"] = 0x9990000  # a DIFFERENT raw VA
    g1 = schema.build_gated_vstoken(fake_vstoken_run1, "uniform")
    g2 = schema.build_gated_vstoken(fake_vstoken_run2, "uniform")
    ok &= check("vstoken uniform: gating strips new_region_va (address-invariant)",
                json.dumps(g1, sort_keys=True) == json.dumps(g2, sort_keys=True))
    ok &= check("vstoken uniform: addrs sibling DOES carry the differing VA",
                schema.build_addrs_vstoken(fake_vstoken_run1)["new_region_va"] !=
                schema.build_addrs_vstoken(fake_vstoken_run2)["new_region_va"])

    fake_perturb1 = {"mode": "perturb_pad64", "pad_mb": 64, "extra_queues": 0, "n": 3,
                     "readback_status_all_completed": True,
                     "code_bo_va": 0x10000000000, "pool_va": 0x58000, "vdm_va": 0x18000,
                     "code_bo_base_unchanged_vs_pad0_baseline": True,
                     "pool_base_unchanged_vs_pad0_baseline": True,
                     "vdm_base_unchanged_vs_pad0_baseline": True}
    fake_perturb2 = dict(fake_perturb1)
    fake_perturb2["code_bo_va"] = 0x20000000000  # different ASLR-ish base
    fake_perturb2["pool_va"] = 0x98000
    gp1 = schema.build_gated_vstoken(fake_perturb1, "perturb")
    gp2 = schema.build_gated_vstoken(fake_perturb2, "perturb")
    ok &= check("vstoken perturb: gating strips raw code/pool VAs",
                json.dumps(gp1, sort_keys=True) == json.dumps(gp2, sort_keys=True))

    # 2. assert_no_address_leak catches an injected address-shaped key/value.
    try:
        schema.assert_no_address_leak({"pool_va": 0x58000})
        ok &= check("assert_no_address_leak rejects an address-shaped KEY", False)
    except AssertionError:
        ok &= check("assert_no_address_leak rejects an address-shaped KEY", True)
    try:
        schema.assert_no_address_leak({"weird_field": 0x10000000000})
        ok &= check("assert_no_address_leak rejects a huge (>=2**32) VALUE", False)
    except AssertionError:
        ok &= check("assert_no_address_leak rejects a huge (>=2**32) VALUE", True)
    ok &= check("assert_no_address_leak accepts small legitimate token values",
                schema.assert_no_address_leak({"tokens": [448, 832, 65344], "linear_step": 128}) is True)

    # 3. fsredirect racy result_colour: HW-OBSERVED (m4_20260828_run02 vs
    #    run03, retained raw evidence -- see schema.py's POST-CAPTURE
    #    SCHEMA CORRECTION note) that result_colour can differ across
    #    otherwise-identical runs even when final_status == Completed, for
    #    any case that spliced a value NOT exactly equal to one of the
    #    three discovered natural selectors. It must NOT create a gate
    #    mismatch in that case (fault OR off-natural-but-completed); a
    #    genuine difference for an EXACT-natural redirect (or a fault-class
    #    case) must still be caught.
    fault1 = {"case": "boundary_max", "bind": "red", "discovery_ok": True,
             "S_RED": 1216, "S_GREEN": 2176, "S_BLUE": 3264,
             "discover_colour_red": "red", "discover_colour_green": "green",
             "discover_colour_blue": "blue", "pool_found": True,
             "natural_selector": 1216, "case_valid_setup": True,
             "do_mutate": True, "mutate_desc": "0xFFFFFFFF", "mutate_value": 4294967295,
             "wrote": True, "hang": False, "final_status": 5,
             "final_error": "Caused GPU Address Fault Error (...PageFault)",
             "result_colour": "blue", "post_pool_found": True, "post_selector": 4294967295}
    fault2 = dict(fault1)
    fault2["result_colour"] = "black"  # HW-observed pattern: differs on fault
    gf1 = schema.build_gated_fsredirect(fault1)
    gf2 = schema.build_gated_fsredirect(fault2)
    ok &= check("fsredirect: result_colour excluded from gate when final_status != Completed",
                json.dumps(gf1, sort_keys=True) == json.dumps(gf2, sort_keys=True))
    ok &= check("fsredirect: result_colour absent from gated dict on fault",
                "result_colour" not in gf1)
    ok &= check("fsredirect: result_colour present in addrs sibling on fault",
                "result_colour" in schema.build_addrs_fsredirect(fault1))

    # Off-natural-but-COMPLETED case (the literal misalign_plus4 shape that
    # triggered this correction): must ALSO be excluded from the gate even
    # though final_status == 4.
    offnat1 = {"case": "misalign_plus4", "bind": "red", "discovery_ok": True,
              "S_RED": 1216, "S_GREEN": 2176, "S_BLUE": 3264,
              "discover_colour_red": "red", "discover_colour_green": "green",
              "discover_colour_blue": "blue", "pool_found": True,
              "natural_selector": 1216, "case_valid_setup": True,
              "do_mutate": True, "mutate_desc": "S_GREEN+4", "mutate_value": 2180,
              "wrote": True, "hang": False, "final_status": 4, "final_error": None,
              "result_colour": "black", "post_pool_found": True, "post_selector": 2180}
    offnat2 = dict(offnat1); offnat2["result_colour"] = "red"
    go1 = schema.build_gated_fsredirect(offnat1)
    go2 = schema.build_gated_fsredirect(offnat2)
    ok &= check("fsredirect: result_colour excluded from gate for an off-natural mutate_value "
                "even when final_status == Completed (the exact HW-observed misalign_plus4 case)",
                json.dumps(go1, sort_keys=True) == json.dumps(go2, sort_keys=True))
    ok &= check("fsredirect: result_colour absent from gated dict for off-natural completed case",
                "result_colour" not in go1)

    # EXACT-natural redirect while Completed (e.g. redirect_red_to_green):
    # this DID reproduce byte-identically in the real run02/run03 pair, so
    # result_colour must remain gated and a genuine difference caught.
    complete1 = {"case": "redirect_red_to_green", "bind": "red", "discovery_ok": True,
                "S_RED": 1216, "S_GREEN": 2176, "S_BLUE": 3264,
                "discover_colour_red": "red", "discover_colour_green": "green",
                "discover_colour_blue": "blue", "pool_found": True,
                "natural_selector": 1216, "case_valid_setup": True,
                "do_mutate": True, "mutate_desc": "S_GREEN", "mutate_value": 2176,
                "wrote": True, "hang": False, "final_status": 4, "final_error": None,
                "result_colour": "green", "post_pool_found": True, "post_selector": 2176}
    complete2 = dict(complete1); complete2["result_colour"] = "red"
    gc1 = schema.build_gated_fsredirect(complete1)
    gc2 = schema.build_gated_fsredirect(complete2)
    ok &= check("fsredirect: a genuine result_colour difference for an EXACT-natural "
                "redirect WHILE Completed IS a gate mismatch",
                json.dumps(gc1, sort_keys=True) != json.dumps(gc2, sort_keys=True))
    ok &= check("fsredirect: result_colour present in gated dict for exact-natural completed case",
                "result_colour" in gc1)

    # 4. final_error is never gated verbatim (only its category).
    e1 = dict(fault1); e1["final_error"] = "Caused GPU Hang Error (...ErrorHang)"
    e2 = dict(fault1); e2["final_error"] = "Discarded (victim of GPU error/recovery) (...ErrorInnocentVictim)"
    e1["final_status"] = e2["final_status"] = 5
    ge1 = schema.build_gated_fsredirect(e1)
    ge2 = schema.build_gated_fsredirect(e2)
    ok &= check("fsredirect: hang vs innocent-victim verbatim strings collapse to same category",
                ge1["final_error_category"] == ge2["final_error_category"] == "GPU_RECOVERY_EVENT")
    ok &= check("fsredirect: verbatim final_error string never appears in gated dict",
                "final_error" not in ge1)

    # 5. A genuine content mismatch (different S_RED discovered) IS caught.
    diff1 = dict(fault1); diff1["final_status"] = 4; diff1["S_RED"] = 1216
    diff2 = dict(fault1); diff2["final_status"] = 4; diff2["S_RED"] = 9999
    gd1 = schema.build_gated_fsredirect(diff1)
    gd2 = schema.build_gated_fsredirect(diff2)
    ok &= check("fsredirect: a genuine S_RED mismatch is NOT masked by gating",
                gd1 != gd2)

    print(f"selftest: {n_pass}/{n_total} PASS")
    return ok


# ---------------------------------------------------------------------------
def seqtest():
    print("=== --seqtest ===")
    scratch = WORK / "seqtest_scratch"
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)

    fake_run1 = scratch / "fake_run01"
    fake_run2 = scratch / "fake_run02"
    ok = True

    ok &= check("PRE_GPU: fake_run01 does not exist before creation", not fake_run1.exists())
    ok &= check("PRE_GPU: fake_run02 does not exist before creation", not fake_run2.exists())

    fake_run1.mkdir()
    (fake_run1 / "gated.jsonl").write_text(
        json.dumps({"kind": "vstoken_varied", "n": 8}, sort_keys=True) + "\n")
    (fake_run1 / "addrs.jsonl").write_text(
        json.dumps({"kind": "vstoken_varied"}, sort_keys=True) + "\n")
    ok &= check("RUN01_PRESENT: fake_run01/gated.jsonl exists and parses",
                json.loads((fake_run1 / "gated.jsonl").read_text().splitlines()[0])["n"] == 8)
    ok &= check("RUN01_PRESENT: fake_run02 still does not exist", not fake_run2.exists())

    fake_run2.mkdir()
    (fake_run2 / "gated.jsonl").write_text(
        json.dumps({"kind": "vstoken_varied", "n": 8}, sort_keys=True) + "\n")
    (fake_run2 / "addrs.jsonl").write_text(
        json.dumps({"kind": "vstoken_varied"}, sort_keys=True) + "\n")
    ok &= check("RUN02_PRESENT: fake_run02/gated.jsonl exists and matches run01 (gated)",
                (fake_run1 / "gated.jsonl").read_text() == (fake_run2 / "gated.jsonl").read_text())

    shutil.rmtree(scratch)
    print(f"seqtest: {n_pass}/{n_total} PASS")
    return ok


# ---------------------------------------------------------------------------
def load_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def captured(run01: str, run02: str):
    print(f"=== --captured {run01} {run02} ===")
    p1 = RAW / run01 / "gated.jsonl"
    p2 = RAW / run02 / "gated.jsonl"
    if not p1.exists() or not p2.exists():
        print(f"FAIL: missing gated.jsonl ({p1.exists()=} {p2.exists()=})")
        return False
    r1 = load_jsonl(p1)
    r2 = load_jsonl(p2)
    ok = True
    if len(r1) != len(r2):
        print(f"FAIL: record count differs ({len(r1)} vs {len(r2)})")
        return False
    mismatches = 0
    for i, (a, b) in enumerate(zip(r1, r2)):
        try:
            schema.assert_no_address_leak(a)
            schema.assert_no_address_leak(b)
        except AssertionError as e:
            print(f"FAIL: address leak in record {i}: {e}")
            ok = False
        if a != b:
            mismatches += 1
            print(f"MISMATCH record {i} kind={a.get('kind')} case={a.get('case', a.get('mode'))}:")
            print(f"  run01: {json.dumps(a, sort_keys=True)}")
            print(f"  run02: {json.dumps(b, sort_keys=True)}")
    ok &= check(f"{len(r1)} gated records byte-identical across {run01} vs {run02}",
                mismatches == 0)
    print(f"captured: {n_pass}/{n_total} PASS")
    return ok


def main():
    global n_pass, n_total
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--seqtest", action="store_true")
    ap.add_argument("--captured", nargs=2, metavar=("RUN01", "RUN02"))
    args = ap.parse_args()
    overall = True
    if args.selftest:
        n_pass = n_total = 0
        overall &= selftest()
    if args.seqtest:
        n_pass = n_total = 0
        overall &= seqtest()
    if args.captured:
        n_pass = n_total = 0
        overall &= captured(*args.captured)
    if not (args.selftest or args.seqtest or args.captured):
        ap.error("pass at least one of --selftest/--seqtest/--captured")
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
