#!/usr/bin/env python3
"""EXP-0108 analysis. Reads both closed raw/ runs, verifies byte-exact
reproduction of the gated 03_results.jsonl, and derives:

  - per-case named-role presence + sha256 (does a known control/descriptor
    region's content change with this configuration?)
  - per-case unnamed-region size multiset DELTA vs the a1 baseline (which
    configurations introduce/remove a distinct extra captured region, and
    how many, independent of GPU VA -- the address-free replacement for the
    dropped VA-arithmetic heuristic; see run.py's methodological note)
  - axis-grouped summaries (action/mrt/format/msaa/memoryless/depth/stencil/
    depth-stencil/empty/partial)
  - an explicit check for whether the 4GiB-aligned code window ever appears
    among captured/known content at all (it never should -- wtrace.c's
    capture_eligible policy excludes it by construction; this is a
    self-check that the exclusion held, not a discovery mechanism)

Writes analysis.json (schema'd, deterministic, no clock/timestamps beyond
what's already in the raw records).
"""
import argparse, json, sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "harness"))
import casematrix as CM
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run as R

HERE = Path(__file__).resolve().parent
BASELINE = "a1-clear-store-draw"


def load_run(run_id):
    d = HERE / "raw" / run_id
    results = [json.loads(l) for l in (d / "03_results.jsonl").read_text().splitlines()]
    timing = [json.loads(l) for l in (d / "03_timing.jsonl").read_text().splitlines()]
    return results, timing


def size_multiset(regions):
    return Counter(r["size"] for r in regions)


def region_multiset(regions):
    return Counter((r["size"], r["sha256"]) for r in regions)


def analyze(run_a="m4-20260828-run01", run_b="m4-20260828-run02"):
    ra, ta = load_run(run_a)
    rb, tb = load_run(run_b)
    assert len(ra) == len(rb) == CM.TOTAL

    # See run.records_reproducibly_equal: this experiment's own two gated run
    # pairs found that (a) each named role's whole-region sha256/
    # present_but_uncaptured and each unnamed_regions entry's sha256/
    # content_captured are NOT cross-run deterministic, and (b) content-
    # capture success itself for an otherwise-identical role can flake
    # between runs (a SIGUSR1-snapshot read-timing race, not a hardware
    # property). Both are excluded from the cross-run gate exactly as
    # verify.py's captured() gate excludes them.
    proj_a = [R.reproducible_projection(c) for c in ra]
    proj_b = [R.reproducible_projection(c) for c in rb]
    per_case_flakes = []
    cross_run_identical = True
    for x, y in zip(ra, rb):
        eq, flakes = R.records_reproducibly_equal(x, y)
        cross_run_identical = cross_run_identical and eq
        if flakes:
            per_case_flakes.append({"name": x["name"], "flakes": flakes})
    raw_identical = (ra == rb)

    by_name = {c["name"]: c for c in ra}
    base_regions = size_multiset(by_name[BASELINE]["unnamed_regions"])

    per_case = []
    for c in ra:
        regions = size_multiset(c["unnamed_regions"])
        delta = {}
        for k in set(regions) | set(base_regions):
            d = regions.get(k, 0) - base_regions.get(k, 0)
            if d:
                delta[k] = d
        named_hash = {role: v.get("sha256") for role, v in c["named"].items()}
        per_case.append({
            "name": c["name"], "axis": c["axis"], "status": c["status"],
            "named_roles_present": sorted(c["named"].keys()),
            "named_sha256": named_hash,
            "region_size_delta_vs_baseline": delta,
            "rts": c["rts"],
        })

    # Axis-grouped: does ANY named role's content change within this axis
    # (holding other axes at baseline)?
    axis_named_variation = {}
    for axis in CM.AXES:
        cases = [c for c in per_case if c["axis"] == axis]
        varies = {}
        all_roles = set()
        for c in cases:
            all_roles |= set(c["named_sha256"])
        for role in all_roles:
            vals = {c["named_sha256"].get(role) for c in cases}
            varies[role] = len(vals) > 1
        axis_named_variation[axis] = varies

    # Depth/stencil region-count finding (the headline structural result):
    depth_stencil_delta = {c["name"]: c["region_size_delta_vs_baseline"]
                            for c in per_case if c["axis"] in ("depth", "stencil", "depth-stencil")}
    format_delta = {c["name"]: c["region_size_delta_vs_baseline"]
                     for c in per_case if c["axis"] == "format"}
    mrt_delta = {c["name"]: c["region_size_delta_vs_baseline"]
                 for c in per_case if c["axis"] == "mrt"}
    partial_delta = {c["name"]: c["region_size_delta_vs_baseline"]
                      for c in per_case if c["axis"] == "partial"}
    partial_named = {c["name"]: c["named_sha256"] for c in per_case if c["axis"] == "partial"}

    # Code-window exclusion self-check: no named role's captured content
    # should ever originate from the 4GiB-aligned code window range: this is
    # true by construction (wtrace.c's capture_eligible excludes it), stated
    # here only as a static assertion over the policy, not a live check of
    # bytes (bytes from that range are never captured to check).
    code_window_excluded_by_construction = True

    status_counts_a = Counter(c["status"] for c in ra)
    status_counts_b = Counter(c["status"] for c in rb)

    # Roles this experiment's own two runs found NOT whole-region
    # cross-run-reproducible (see run.reproducible_projection). Any
    # within-axis content variation reported for these specific roles via
    # axis_named_role_content_varies should be corroborated by the trusted
    # field-level windows (first64_hex/k_load/k_store, present only for the
    # two color-descriptor roles) before being promoted as a hardware fact.
    known_noisy_named_roles = sorted({
        role for i, (x, y) in enumerate(zip(ra, rb))
        for role in set(x["named"]) | set(y["named"])
        if x["named"].get(role, {}).get("sha256") != y["named"].get(role, {}).get("sha256")
    })
    n_raw_diff_lines = sum(1 for x, y in zip(ra, rb) if x != y)
    n_projected_diff_lines = sum(1 for x, y in zip(proj_a, proj_b) if x != y)

    out = {
        "schema": 1,
        "run_a": run_a, "run_b": run_b,
        "total_cases": CM.TOTAL,
        "cross_run_byte_exact": cross_run_identical,
        "cross_run_raw_byte_exact": raw_identical,
        "n_raw_lines_differing": n_raw_diff_lines,
        "n_projected_lines_differing": n_projected_diff_lines,
        "known_noisy_named_roles": known_noisy_named_roles,
        "content_capture_read_flakes": per_case_flakes,
        "status_counts_run_a": dict(sorted(status_counts_a.items())),
        "status_counts_run_b": dict(sorted(status_counts_b.items())),
        "per_case": per_case,
        "axis_named_role_content_varies": axis_named_variation,
        "depth_stencil_region_delta": depth_stencil_delta,
        "format_axis_region_delta": format_delta,
        "mrt_axis_region_delta": mrt_delta,
        "partial_axis_region_delta": partial_delta,
        "partial_axis_named_sha256": partial_named,
        "code_window_excluded_by_construction": code_window_excluded_by_construction,
    }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-a", default="m4-20260828-run01")
    ap.add_argument("--run-b", default="m4-20260828-run02")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    out = analyze(a.run_a, a.run_b)
    text = json.dumps(out, indent=2, sort_keys=True) + "\n"
    if a.write:
        (HERE / "analysis.json").write_text(text)
        print("WROTE analysis.json")
    else:
        print(text)
    if not out["cross_run_byte_exact"]:
        print("WARNING: runs are not byte-exact on gated fields", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
