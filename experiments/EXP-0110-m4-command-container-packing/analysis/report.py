#!/usr/bin/env python3
"""EXP-0110 report.py -- derive the summary tables RESULTS.md quotes,
directly from the two frozen `raw/<run>/02_results.jsonl` GATED captures
(plus the non-gated `_addrs.jsonl` siblings for human-readable address
context only -- never used to derive a claimed fact that must survive the
cross-run gate). Repeatable; no argument needed beyond the two run ids.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent


def load(run_id):
    p = HERE / "raw" / run_id / "02_results.jsonl"
    return [json.loads(l) for l in p.read_text().splitlines()]


def load_addrs(run_id):
    p = HERE / "raw" / run_id / "02_results_addrs.jsonl"
    return {json.loads(l)["case"]: json.loads(l) for l in p.read_text().splitlines()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run01-id", default="m4_20260827_run01")
    ap.add_argument("--run02-id", default="m4_20260827_run02")
    args = ap.parse_args()

    r1 = {r["case"]: r for r in load(args.run01_id)}
    r2 = {r["case"]: r for r in load(args.run02_id)}
    a1 = load_addrs(args.run01_id)

    print("=== CDM/VDM segment chains (run01; run02 gated-identical per --captured) ===")
    for case in r1:
        rec = r1[case]
        if rec["kind"] not in ("cdm", "vdm"):
            continue
        segs = rec["segments"]
        chain = a1[case].get("chain_va", [])
        print("%-16s status=%-6s segs=%d records=%-5d chain=%s" %
              (case, rec["status"], rec["segment_count"], rec["total_records"], chain))
        for i, s in enumerate(segs):
            print("    seg%d records=%-4d tail=%-11s tag=%s delta=%s transform_ok=%s" %
                  (i, s["record_count"], s["tail_kind"], s["link_tag"], s["delta_from_baseline"], s["transform_ok"]))
        both_ok = rec == r2[case]
        print("    cross-run gated-identical: %s" % both_ok)

    print("\n=== state-packet pool fields (run01) ===")
    for case in r1:
        rec = r1[case]
        if rec["kind"] != "state":
            continue
        print(case, rec["status"], rec["pool_fields"])

    print("\n=== state-packet bind pairs, deltas from pool base (run01, state_baseline) ===")
    base = r1.get("state_baseline")
    if base:
        for p in base["pairs"]:
            print("  control=0x%04x delta_from_pool=%s" % (p["control"], hex(p["delta_from_pool"]) if p["delta_from_pool"] is not None else None))

    print("\n=== container metadata field survey (run01) ===")
    for case in r1:
        rec = r1[case]
        if rec["kind"] != "container":
            continue
        print("%-24s meta_len=%-4d fields=%s" % (case, rec["meta_len"], rec["fields"]))

    print("\n=== container live cross-check (run01) ===")
    for case in r1:
        rec = r1[case]
        if rec["kind"] != "container_live":
            continue
        print("%-16s nbuf=%d argtab_entries=%s preamble_nz=%s cdm_norm=%s" %
              (case, rec["nbuf"], rec["arg_table_entry_count"], rec["preamble_nonzero_len"],
               rec["cdm_record_hex_normalized"]))
    all_cdm_norms = {r1[c]["cdm_record_hex_normalized"] for c in r1 if r1[c]["kind"] == "container_live"}
    print("distinct normalized CDM records across all nbuf:", len(all_cdm_norms))


if __name__ == "__main__":
    sys.exit(main())
