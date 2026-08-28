#!/usr/bin/env python3
"""Repeatable derived report from a closed run directory. Turns raw JSONL into
the finite-resource limit table and per-family summaries used by RESULTS.md.
Does not alter any raw/ file; writes analysis/report.json.

Usage: python3 analysis/report.py raw/m4_20260828_run01
"""
import json, sys
from pathlib import Path


def load(run_dir):
    run_dir = Path(run_dir)
    recs = [json.loads(l) for l in (run_dir / "02_gated.jsonl").read_text().splitlines() if l.strip()]
    return {r["case_id"]: r for r in recs}


def main():
    run_dir = sys.argv[1] if len(sys.argv) > 1 else "raw/m4_20260828_run01"
    recs = load(run_dir)
    by_family = {}
    for r in recs.values():
        by_family.setdefault(r["family"], []).append(r)

    report = {"run_dir": run_dir, "total_cases": len(recs), "families": {}}
    for fam, items in sorted(by_family.items()):
        pass_n = sum(1 for i in items if i["verdict"] == "PASS")
        report["families"][fam] = {
            "n": len(items), "pass": pass_n, "fail": len(items) - pass_n,
            "case_ids": sorted(i["case_id"] for i in items),
        }

    def st(cid):
        return recs[cid]["status"]

    def get(cid):
        return recs[cid]["observed"]

    report["limit_table"] = {
        "attachments_max": {"boundary": 8, "boundary_status": st("attach_n8"),
                             "first_invalid": 9, "first_invalid_status": st("attach_n9")},
        "viewports_functional_max": {"boundary": 16, "boundary_status": st("vp_n16"),
                                      "degrade_starts": 17, "degrade_status": st("vp_n17"),
                                      "process_crash_at": 21, "crash_status": st("vp_n21")},
        "texture2d_cube_dim_max": {"boundary": 16384, "boundary_status": get("tex2d_16384")["create_status"],
                                    "first_invalid": 16385, "first_invalid_status": st("tex2d_16385")},
        "texture3d_axis_max": {"boundary": 2048, "boundary_status": get("tex3d_2048")["create_status"],
                                "first_invalid": 2049, "first_invalid_status": st("tex3d_2049")},
        "texture2darray_layers_max": {"boundary": 2048, "boundary_status": get("texarr_2048")["create_status"],
                                       "first_invalid": 2049, "first_invalid_status": st("texarr_2049")},
        "mip_levels_formula": "floor(log2(max(w,h)))+1",
        "buffer_bind_index_max": {"boundary": 30, "boundary_status": st("bufidx_30"),
                                   "first_invalid": 31, "first_invalid_status": st("bufidx_31")},
        "texture_bind_index_max": {"boundary": 127, "boundary_status": st("texidx_127"),
                                    "first_invalid": 128, "first_invalid_status": st("texidx_128")},
        "inline_bytes_max": {"boundary": 32752, "boundary_status": st("bytesconst_32752"),
                              "first_invalid": 32753, "first_invalid_status": st("bytesconst_32753")},
        "buffer_offset_alignment": "none observed; offsets 0,1,2,3,4,15,17 all functional",
        "threadgroup_size_max": {"boundary": 1024, "boundary_status": st("tgsize_1024"),
                                  "first_invalid": 1025, "first_invalid_behavior": "silent no-op, not an error"},
        "simd_width": get("simdwidth_tg32")["thread_execution_width"],
    }
    Path("analysis/report.json").write_text(json.dumps(report, indent=2, sort_keys=True))
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
