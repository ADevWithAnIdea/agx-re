#!/usr/bin/env python3
"""EXP-0084 post-capture correctness analysis (repeatable; CODEX `analysis/`
convention). NOT part of the frozen captured-provenance hash set (it runs
AFTER both raw runs close and does not influence capture; `run.py` never
invokes it) -- a completeness gap against the EXP-0076 precedent (which DID
pre-register its analysis.py), acknowledged in RESULTS.md.

For every DISPATCH-kind case, computes the expected `out_hex`/`outb_hex`/
`outsel_hex` from the case's OWN frozen metadata (name/function/n/sel/k) and
the harness's documented, source-visible TAG formula (`kernels/probes.metal`,
`harness/probe.m`: `TAG(k) = 0x5A000000 | (k & 0xFFFFFF)`), and compares
against the OBSERVED value recorded in `04_results.jsonl`. For DECODE/SPLICE-
kind cases, surfaces the recorded identification/outcome fields verbatim (no
separate "expected" computation -- H7/H8's refutation, if any, IS the
observation).

Usage: python3 analysis.py --run raw/m4-20260827-run01 [--write out.json]
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import casematrix as CM  # noqa: E402


def TAG(k):
    return "%08x" % (0x5A000000 | (k & 0xFFFFFF))


def words(h):
    return [h[i:i + 8] for i in range(0, len(h), 8)] if h else []


def expected_dispatch(c):
    """Returns (expected_out, expected_outb, expected_outsel) as lists of
    8-hex-char words, or (None, None, None) if not applicable (compile-reject
    cases have no expectation)."""
    name = c["name"]
    if name == "ctrl_direct_baseline":
        return (["%08x" % (1000 + i) for i in range(32)], [], [])
    if name in ("mem20_uniform_single", "mem20_no_useresource"):
        return ([TAG(0)] * 32, [], [])
    if name == "mem20_implicit_ab":
        return ([TAG(0x300000 + i) for i in range(32)], [], [])
    if name == "mem20_chained_indirection":
        return ([TAG(0x700000 + i) for i in range(32)], [], [])
    if name == "mem21_uniform_ctrl":
        return ([TAG(1)] * 32, [], [])
    if name == "mem21_perlane_divergent_32":
        return ([TAG(i) for i in range(32)], [], ["%08x" % i for i in range(32)])
    if name == "mem21_outlier_lane17":
        return ([TAG(1) if i == 17 else TAG(0) for i in range(32)], [], [])
    if name == "mem22_dynamic_64":
        return ([TAG(i) for i in range(64)], [], ["%08x" % i for i in range(64)])
    if name == "mem22_dynamic_256":
        return ([TAG(i) for i in range(256)], [], ["%08x" % i for i in range(256)])
    if name in ("mem22_direct_cap_31", "mem22_direct_cap_32"):
        return (None, None, None)  # compile-time boundary probes; no dispatch expectation
    raise KeyError("no expectation rule for dispatch case %r" % name)


def analyze_run(run_dir):
    run_dir = Path(run_dir)
    lines = [json.loads(l) for l in (run_dir / "04_results.jsonl").read_text().splitlines() if l.strip()]
    by_i = {q["i"]: q for q in lines}
    out = {"run_dir": str(run_dir), "cases": []}
    for c in CM.CASES:
        q = by_i[c["i"]]
        row = {"i": c["i"], "name": c["name"], "kind": c["kind"], "status": q["status"]}
        if c["kind"] == "dispatch":
            exp_out, exp_outb, exp_outsel = expected_dispatch(c)
            if exp_out is None:
                row["value_check"] = "not_applicable"
            elif q["status"] != "ok":
                row["value_check"] = "not_ok_status"
            else:
                obs_out = words(q["out_hex"])
                obs_outb = words(q["outb_hex"])
                obs_outsel = words(q["outsel_hex"])
                match = (obs_out == exp_out and obs_outb == exp_outb and obs_outsel == exp_outsel)
                row["value_check"] = "match" if match else "MISMATCH"
                if not match:
                    row["observed_out"] = obs_out
                    row["expected_out"] = exp_out
        elif c["kind"] == "decode":
            row["confirmation_ok"] = q.get("confirmation_ok")
            row["n_device_load_main"] = q.get("n_device_load_main")
            row["l1_base_slot"], row["l1_index_reg"] = q.get("l1_base_slot"), q.get("l1_index_reg")
            row["l2_base_slot"], row["l2_index_reg"] = q.get("l2_base_slot"), q.get("l2_index_reg")
            row["base_slot_differs"] = (q.get("l1_base_slot") != q.get("l2_base_slot")
                                        if q.get("l1_base_slot") is not None else None)
            row["index_reg_differs"] = (q.get("l1_index_reg") != q.get("l2_index_reg")
                                        if q.get("l1_index_reg") is not None else None)
        elif c["kind"] == "splice":
            row["outcome"] = q.get("outcome")
        out["cases"].append(row)
    out["all_dispatch_match"] = all(
        r["value_check"] in ("match", "not_applicable") for r in out["cases"] if r["kind"] == "dispatch")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--write")
    a = ap.parse_args()
    result = analyze_run(a.run)
    text = json.dumps(result, indent=2, sort_keys=True)
    if a.write:
        Path(a.write).write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
