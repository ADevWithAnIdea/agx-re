#!/usr/bin/env python3
"""Repeatable human-readable report over one EXP-0125 captured run directory.

Usage: python3 analysis/analyze.py raw/<run-id> [--timing raw/<run-id>/03_timing.jsonl]

Three sections, one per hypothesis-family: I (init-time checkpoint diff),
B (ceiling bisection boundary + mesa-constant comparison), C (concurrent
exhaustion ladder). Never mutates raw/; purely derived.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import casematrix as CM  # noqa: E402


def load_jsonl(p):
    out = []
    p = Path(p)
    if p.is_file():
        for line in p.read_text().splitlines():
            if line.strip():
                out.append(json.loads(line))
    return out


def section_i(run_dir):
    recs = load_jsonl(run_dir / "02a_i_checkpoints.jsonl")
    summ = load_jsonl(run_dir / "02b_i_summary.jsonl")
    print("=" * 78)
    print("I FAMILY -- init-time checkpoint trace (H1 / H2)")
    print("=" * 78)
    by_variant = {}
    for r in recs:
        by_variant.setdefault(r["variant"], {})[r["cp_idx"]] = r
    print(f"{'cp':>3} {'label':<20} {'nospill.nbo':>12} {'spill.nbo':>10} "
         f"{'nospill.bytes':>14} {'spill.bytes':>12} {'shape_eq':>9} "
         f"{'codewin(ns/sp)':>16}")
    any_shape_diff = False
    any_nbo_diff = False
    for idx, label in enumerate(CM.CHECKPOINT_LABELS):
        ns = by_variant.get("nospill", {}).get(idx)
        sp = by_variant.get("spill", {}).get(idx)
        if not ns or not sp:
            print(f"{idx:>3} {label:<20} MISSING RECORD (ns={bool(ns)} sp={bool(sp)})")
            continue
        shape_eq = ns["resource_map_shape"] == sp["resource_map_shape"]
        if not shape_eq:
            any_shape_diff = True
        if ns["nbo"] != sp["nbo"]:
            any_nbo_diff = True
        cw = f"{ns['code_window_present']}/{sp['code_window_present']}"
        print(f"{idx:>3} {label:<20} {ns['nbo']:>12} {sp['nbo']:>10} "
             f"{ns['bo_total_bytes']:>14} {sp['bo_total_bytes']:>12} "
             f"{str(shape_eq):>9} {cw:>16}")
    print()
    print(f"any resource_map_shape difference nospill vs spill at ANY checkpoint: {any_shape_diff}")
    print(f"any nbo difference nospill vs spill at ANY checkpoint: {any_nbo_diff}")
    if any_shape_diff:
        print("--- shape diffs, checkpoint by checkpoint ---")
        for idx, label in enumerate(CM.CHECKPOINT_LABELS):
            ns = by_variant.get("nospill", {}).get(idx)
            sp = by_variant.get("spill", {}).get(idx)
            if not ns or not sp:
                continue
            if ns["resource_map_shape"] != sp["resource_map_shape"]:
                ns_set = {(e["class"], e["size"]): e["count"] for e in ns["resource_map_shape"]}
                sp_set = {(e["class"], e["size"]): e["count"] for e in sp["resource_map_shape"]}
                only_ns = {k: v for k, v in ns_set.items() if sp_set.get(k) != v}
                only_sp = {k: v for k, v in sp_set.items() if ns_set.get(k) != v}
                print(f"  cp{idx} {label}: nospill-differing={only_ns} spill-differing={only_sp}")
    print()
    for s in summ:
        print(f"summary: {s['case']} status={s['probe_status']} exit={s['probe_exit']} "
             f"timed_out={s['probe_timed_out']} checksum={s['checksum']}")
    print()
    return any_shape_diff, any_nbo_diff


def section_b(run_dir):
    trials = load_jsonl(run_dir / "04a_b_trials.jsonl")
    results = load_jsonl(run_dir / "04b_b_results.jsonl")
    print("=" * 78)
    print("B FAMILY -- compile-time ceiling bisection (H3)")
    print("=" * 78)
    print(f"{'stage':<4} {'last_ok(K)':>11} {'first_fail(K)':>14} {'last_ok_bytes(4K+16)':>21} "
         f"{'n_trials':>8} {'bracket_ok':>10} {'ratio_to_mesa_131072':>22}")
    for r in results:
        stage = r["stage"]
        lo = r["last_ok"]
        bytes_ = 4 * lo + 16 if lo is not None else None
        ratio = (CM.K_HIGH / lo) if lo else None
        print(f"{stage:<4} {lo!s:>11} {r['first_fail']!s:>14} {bytes_!s:>21} "
             f"{r['n_trials']:>8} {str(r['bracket_ok']):>10} {ratio!s:>22}")
    print()
    stage_bounds = {r["stage"]: (r["last_ok"], r["first_fail"]) for r in results}
    if len(stage_bounds) >= 2:
        vals = [v[0] for v in stage_bounds.values() if v[0] is not None]
        if vals:
            spread = max(vals) - min(vals)
            print(f"stage-to-stage last_ok spread: {spread} (of {vals})")
    print()
    n_by_stage = {}
    for t in trials:
        n_by_stage.setdefault(t["stage"], []).append(t)
    for stage, ts in n_by_stage.items():
        bisect_trials = [t for t in ts if t["phase"] == "bisect"]
        bracket_trials = [t for t in ts if t["phase"] == "bracket"]
        print(f"{stage}: {len(bracket_trials)} bracket trials, {len(bisect_trials)} bisect trials")
    print()
    return results


def section_c(run_dir):
    trials = load_jsonl(run_dir / "05_c_levels.jsonl")
    print("=" * 78)
    print("C FAMILY -- concurrent exhaustion, per-level FAILURE RATE over "
         f"{CM.C_REPEATS} repeats (H4)")
    print("=" * 78)
    print("(status/ok_queues/execfail_queues/nonfinite_queues/checksum_mismatch are this "
         "experiment's own directly-observed NONDETERMINISTIC fields -- not required to "
         "match run01 vs run02; the failure RATE is the finding, not any single trial)")
    print()
    by_level = {}
    for t in trials:
        by_level.setdefault(t["n_queues"], []).append(t)
    print(f"{'n_queues':>8} {'trials':>7} {'ok':>4} {'degraded':>9} {'other':>6} "
         f"{'total_execfail':>14} {'total_nonfinite':>15} {'total_mismatch':>14}")
    for n in sorted(by_level):
        ts = by_level[n]
        ok = sum(1 for t in ts if t["status"] == "OK")
        degraded = sum(1 for t in ts if t["status"] == "DEGRADED")
        other = len(ts) - ok - degraded
        tot_execfail = sum(t["execfail_queues"] or 0 for t in ts)
        tot_nonfinite = sum(t["nonfinite_queues"] or 0 for t in ts)
        tot_mismatch = sum(t["checksum_mismatch"] or 0 for t in ts)
        print(f"{n:>8} {len(ts):>7} {ok:>4} {degraded:>9} {other:>6} "
             f"{tot_execfail:>14} {tot_nonfinite:>15} {tot_mismatch:>14}")
    print()
    first_any_failure = None
    for n in sorted(by_level):
        if any(t["status"] != "OK" for t in by_level[n]):
            first_any_failure = n
            break
    print(f"lowest n_queues with >=1 non-OK trial: {first_any_failure}")
    print()
    return trials


def section_timing(run_dir):
    timing = load_jsonl(run_dir / "03_timing.jsonl")
    c_timing = [t for t in timing if t["record"].startswith("C:")]
    if not c_timing:
        return
    print("=" * 78)
    print("C FAMILY timing (ungated, informational -- wall-clock cliff check)")
    print("=" * 78)
    for t in c_timing:
        print(f"{t['record']:<14} duration_ms={t['duration_ms']}")
    print()


def main():
    if len(sys.argv) < 2:
        print("usage: analyze.py raw/<run-id>", file=sys.stderr)
        return 2
    run_dir = Path(sys.argv[1])
    print(f"# EXP-0125 analysis report for {run_dir}")
    print()
    section_i(run_dir)
    section_b(run_dir)
    section_c(run_dir)
    section_timing(run_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
