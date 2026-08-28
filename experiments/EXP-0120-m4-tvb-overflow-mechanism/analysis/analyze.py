#!/usr/bin/env python3
"""Derive summary.json + report.txt for one EXP-0120 capture run.

Usage: python3 analyze.py <run_id>   (reads raw/<run_id>/, writes
       analysis/<run_id>.json and analysis/<run_id>_report.txt)

Pure analysis over already-captured raw/ data; never re-runs anything.
"""
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP_ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from iotrace_parse import parse_iotrace_log

STDOUT_FIELDS_RE = re.compile(r"status=(\d+|None)\s+error=(.*?)\s+exact=(\d+)")


def load_records(run_id):
    path = os.path.join(EXP_ROOT, "raw", run_id, "records.jsonl")
    recs = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def extract_done_fields(stdout_tail):
    for line in reversed(stdout_tail):
        if "G17P_PARTIAL_DONE" in line:
            m = STDOUT_FIELDS_RE.search(line)
            if m:
                return {"status": m.group(1), "error": m.group(2).strip(),
                         "exact": int(m.group(3))}
    return None


def linreg(xs, ys):
    n = len(xs)
    if n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    if sxx == 0:
        return None
    b = sxy / sxx
    a = my - b * mx
    ss_tot = sum((y - my) ** 2 for y in ys)
    ss_res = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 1.0
    return {"intercept_ms": a, "slope_ms_per_tri": b, "r2": r2}


def analyze_sweep_A(recs):
    by_group = {}
    for r in recs:
        if r["sweep"] != "A":
            continue
        by_group.setdefault(r["group"], []).append(r)

    points = []  # (N, marginal_ms, method)
    for group, grecs in by_group.items():
        roles = {r["role"]: r for r in grecs}
        n = grecs[0]["params"]["N"]
        if "s1" in roles and "s2" in roles:
            s1, s2 = roles["s1"], roles["s2"]
            if s1["timed_out"] or s2["timed_out"] or s1["returncode"] != 0 or s2["returncode"] != 0:
                continue
            ds = s2["params"]["S"] - s1["params"]["S"]
            dt_ms = (s2["elapsed_s"] - s1["elapsed_s"]) * 1000.0
            marginal_ms = dt_ms / ds
            points.append({"N": n, "marginal_ms": marginal_ms, "method": "slope",
                            "S1": s1["params"]["S"], "S2": s2["params"]["S"]})
        elif "single" in roles:
            s = roles["single"]
            if s["timed_out"] or s["returncode"] != 0:
                continue
            marginal_ms = s["elapsed_s"] * 1000.0
            points.append({"N": n, "marginal_ms": marginal_ms, "method": "single",
                            "S": s["params"]["S"]})

    points.sort(key=lambda p: p["N"])
    for p in points:
        p["per_tri_ns"] = (p["marginal_ms"] * 1e6) / p["N"] if p["N"] else None

    # Global linear fit ms = A + B*N over all points.
    xs = [p["N"] for p in points]
    ys = [p["marginal_ms"] for p in points]
    fit_all = linreg(xs, ys)
    for p in points:
        if fit_all:
            pred = fit_all["intercept_ms"] + fit_all["slope_ms_per_tri"] * p["N"]
            p["linear_fit_predicted_ms"] = pred
            p["linear_fit_residual_ratio"] = (p["marginal_ms"] - pred) / pred if pred else None

    # Regime comparison: mean per-tri rate for N<50000 (small) vs N>=1,000,000 (large),
    # restricted to points where the fixed-overhead contribution is <5% of marginal_ms
    # (i.e. per_tri*N far exceeds a ~1.5ms floor) so the comparison isn't just overhead noise.
    small = [p for p in points if 3000 <= p["N"] < 50000]
    large = [p for p in points if p["N"] >= 1000000]
    rate_small = sum(p["per_tri_ns"] for p in small) / len(small) if small else None
    rate_large = sum(p["per_tri_ns"] for p in large) / len(large) if large else None

    return {
        "points": points,
        "linear_fit_all": fit_all,
        "mean_per_tri_ns_small_N_3000_50000": rate_small,
        "mean_per_tri_ns_large_N_ge_1e6": rate_large,
        "rate_ratio_large_over_small": (rate_large / rate_small) if (rate_small and rate_large) else None,
    }


def _remove_up_to_n(values, target, n):
    out = list(values)
    removed = 0
    i = 0
    while i < len(out) and removed < n:
        if out[i] == target:
            del out[i]
            removed += 1
        else:
            i += 1
    return out


def analyze_mechanism_sweep(recs, sweep_letter):
    out = []
    for r in recs:
        if r["sweep"] != sweep_letter:
            continue
        case_dir = os.path.join(EXP_ROOT, "raw", r["_run_id"], "cases", r["case_id"])
        log_path = os.path.join(case_dir, r["iotrace_log"]) if r["iotrace_log"] else None
        parsed = parse_iotrace_log(log_path) if log_path and os.path.exists(log_path) else None
        entry = {
            "case_id": r["case_id"],
            "params": r["params"],
            "returncode": r["returncode"],
            "timed_out": r["timed_out"],
            "done_fields": extract_done_fields(r["stdout_tail"]),
        }
        if parsed:
            bpr = (r["params"]["width"] * 4 + 255) & ~255
            expected_own_output_buffer_size = bpr * r["params"]["height"]
            large_multiset = sorted(s for s in parsed["size_multiset"] if s >= 0x40000)
            entry.update({
                "n_bo": parsed["n_bo"],
                "size_multiset": parsed["size_multiset"],
                "selector_histogram": parsed["selector_histogram"],
                "sel9_calls": parsed["sel9_calls"],
                "total_calls": parsed["total_calls"],
                "calls_after_first_bodump": parsed["calls_after_first_bodump"],
                "had_bodump": parsed["had_bodump"],
                # analysis-only refinement (does not change gated raw payload):
                # our own 8 R32F output buffers scale with width*height and would
                # otherwise dominate/confound a dimension-axis invariance check.
                # >=0x40000 (256KiB) cleanly separates them (at WH>=256) plus the
                # three large fixed-size control/heap regions from every small
                # (<=0x20000) control/descriptor BO. Reported alongside, not
                # substituted for, the full raw multiset.
                "expected_own_output_buffer_size": expected_own_output_buffer_size,
                "large_region_multiset_ge_256KiB": large_multiset,
                # EXP-0118's accumulate mode always allocates exactly 8 output
                # R32F buffers (attachment_count, hard-coded); remove at most 8
                # occurrences of that exact size so a large TVB-candidate region
                # that coincidentally has the SAME size as those 8 buffers (this
                # happens at width=height=512, where both are 0x100000) is not
                # also stripped -- removing *all* occurrences would silently
                # erase a real, present region instead of just our own buffers.
                "large_region_multiset_excluding_own_buffers":
                    sorted(_remove_up_to_n(large_multiset, expected_own_output_buffer_size, 8)),
            })
        out.append(entry)
    out.sort(key=lambda e: e["params"]["N"] if sweep_letter == "B" else e["params"]["width"])

    multisets_seen = {}
    for e in out:
        if "size_multiset" in e:
            key = json.dumps(e["size_multiset"])
            multisets_seen.setdefault(key, []).append(e["case_id"])
    invariant = len(multisets_seen) <= 1

    histograms_seen = {}
    for e in out:
        if "selector_histogram" in e:
            key = json.dumps(e["selector_histogram"], sort_keys=True)
            histograms_seen.setdefault(key, []).append(e["case_id"])
    histogram_invariant = len(histograms_seen) <= 1

    large_seen = {}
    for e in out:
        if "large_region_multiset_excluding_own_buffers" in e:
            key = json.dumps(e["large_region_multiset_excluding_own_buffers"])
            large_seen.setdefault(key, []).append(e["case_id"])
    large_invariant = len(large_seen) <= 1

    return {
        "cases": out,
        "distinct_size_multisets": len(multisets_seen),
        "size_multiset_invariant_across_sweep": invariant,
        "distinct_selector_histograms": len(histograms_seen),
        "selector_histogram_invariant_across_sweep": histogram_invariant,
        "multiset_groups": {k: v for k, v in multisets_seen.items()},
        "distinct_large_region_multisets_excl_own_buffers": len(large_seen),
        "large_region_multiset_invariant_across_sweep": large_invariant,
    }


def analyze_sweep_D(recs):
    out = []
    for r in recs:
        if r["sweep"] != "D":
            continue
        case_dir = os.path.join(EXP_ROOT, "raw", r["_run_id"], "cases", r["case_id"])
        log_path = os.path.join(case_dir, r["iotrace_log"]) if r["iotrace_log"] else None
        parsed = parse_iotrace_log(log_path) if log_path and os.path.exists(log_path) else None
        entry = {
            "case_id": r["case_id"],
            "role": r["role"],
            "params": r["params"],
            "returncode": r["returncode"],
            "timed_out": r["timed_out"],
            "elapsed_s": r["elapsed_s"],
            "done_fields": extract_done_fields(r["stdout_tail"]),
        }
        if parsed:
            entry["n_bo"] = parsed["n_bo"]
            entry["size_multiset"] = parsed["size_multiset"]
        out.append(entry)
    return out


def main():
    run_id = sys.argv[1]
    recs = load_records(run_id)
    for r in recs:
        r["_run_id"] = run_id

    result = {
        "run_id": run_id,
        "n_records": len(recs),
        "sweep_A": analyze_sweep_A(recs),
        "sweep_B": analyze_mechanism_sweep(recs, "B"),
        "sweep_C": analyze_mechanism_sweep(recs, "C"),
        "sweep_D": analyze_sweep_D(recs),
    }

    out_json = os.path.join(HERE, f"{run_id}.json")
    with open(out_json, "w") as f:
        json.dump(result, f, indent=2)
        f.write("\n")

    lines = []
    lines.append(f"EXP-0120 analysis report: run_id={run_id}")
    lines.append(f"records: {len(recs)}")
    lines.append("")
    lines.append("== Sweep A (timing) ==")
    fit = result["sweep_A"]["linear_fit_all"]
    if fit:
        lines.append(f"global linear fit: ms = {fit['intercept_ms']:.4f} + {fit['slope_ms_per_tri']:.8f}*N   R^2={fit['r2']:.6f}")
    lines.append(f"mean per-tri ns, N in [3000,50000): {result['sweep_A']['mean_per_tri_ns_small_N_3000_50000']}")
    lines.append(f"mean per-tri ns, N >= 1e6: {result['sweep_A']['mean_per_tri_ns_large_N_ge_1e6']}")
    lines.append(f"ratio (large/small): {result['sweep_A']['rate_ratio_large_over_small']}")
    lines.append("N, marginal_ms, per_tri_ns, linear_fit_residual_ratio")
    for p in result["sweep_A"]["points"]:
        lines.append(f"  {p['N']:>10} {p['marginal_ms']:>12.4f} {p['per_tri_ns']:>10.4f} {p.get('linear_fit_residual_ratio')}")
    lines.append("")
    for sw in ("B", "C"):
        s = result[f"sweep_{sw}"]
        lines.append(f"== Sweep {sw} (mechanism) ==")
        lines.append(f"distinct size multisets across sweep: {s['distinct_size_multisets']} (invariant={s['size_multiset_invariant_across_sweep']})")
        lines.append(f"distinct selector histograms across sweep: {s['distinct_selector_histograms']} (invariant={s['selector_histogram_invariant_across_sweep']})")
        lines.append(f"distinct >=256KiB-region multisets (own output buffers excluded): "
                     f"{s['distinct_large_region_multisets_excl_own_buffers']} (invariant={s['large_region_multiset_invariant_across_sweep']})")
        for c in s["cases"]:
            lines.append(f"  {c['case_id']:16s} n_bo={c.get('n_bo')} sel9_calls={c.get('sel9_calls')} "
                         f"calls_after_bodump={c.get('calls_after_first_bodump')} "
                         f"large_excl_own={c.get('large_region_multiset_excluding_own_buffers')} "
                         f"done={c.get('done_fields')}")
        lines.append("")
    lines.append("== Sweep D (limits, exploratory single-shot) ==")
    for c in result["sweep_D"]:
        lines.append(f"  {c['case_id']:24s} rc={c['returncode']} timeout={c['timed_out']} "
                     f"elapsed={c['elapsed_s']:.3f}s n_bo={c.get('n_bo')} done={c.get('done_fields')}")

    report_path = os.path.join(HERE, f"{run_id}_report.txt")
    with open(report_path, "w") as f:
        f.write("\n".join(lines) + "\n")

    print(f"wrote {out_json}")
    print(f"wrote {report_path}")


if __name__ == "__main__":
    main()
