#!/usr/bin/env python3
"""Repeatable analysis over one EXP-0107 raw/<run-id>/ capture.

Reads only:
  - 02_cases.jsonl (gated fields, incl. resource_map_shape / bo_content_seq_sha256)
  - 05_raw_maps.jsonl (ungated: the actual per-BO GPU VAs, for descriptive
    within-run BO identification only -- never used as a cross-run/cross-
    experiment invariant, and never fed back into any gated comparison)
  - dumps/<case>/allbo/*.hex (the bounded content prefixes captured by
    harness/maptrace.c)

Produces a text report: the scratch-vs-footprint table, the K-family
boundary, the O/X-family occupancy-vs-footprint table, and a positional
per-BO content diff between chosen case pairs (by VA, which this run's own
data shows is stable across same-shape CS dispatches -- an empirical
observation of this run, stated as such, not an assumed architectural
invariant).
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import traceparse as TP  # noqa: E402


def load_cases(run_dir):
    return [json.loads(l) for l in (run_dir / "02_cases.jsonl").read_text().splitlines() if l.strip()]


def load_raw_maps(run_dir):
    out = {}
    for line in (run_dir / "05_raw_maps.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        out[d["name"]] = d["raw_resource_maps"]
    return out


def by_name(cases):
    return {c["name"]: c for c in cases}


def hexfile_for_va(run_dir, case_name, va, size):
    p = run_dir / "dumps" / case_name / "allbo" / f"bo_va{va:x}_sz{size:x}.hex"
    return TP.hex_file_content(p)


def diff_case_pair(run_dir, raw_maps, name_a, name_b, label, out):
    maps_a = {(m["gpu_va"], m["size"]) for m in raw_maps.get(name_a, [])}
    maps_b = {(m["gpu_va"], m["size"]) for m in raw_maps.get(name_b, [])}
    out.append(f"\n--- {label}: {name_a} vs {name_b} ---")
    out.append(f"resource-map VA/size sets identical: {maps_a == maps_b}")
    if maps_a != maps_b:
        out.append(f"  only in {name_a}: {sorted(maps_a - maps_b)}")
        out.append(f"  only in {name_b}: {sorted(maps_b - maps_a)}")
    common = sorted(maps_a & maps_b)
    any_diff = False
    for va, size in common:
        ca = hexfile_for_va(run_dir, name_a, va, size)
        cb = hexfile_for_va(run_dir, name_b, va, size)
        n = min(len(ca), len(cb))
        diffs = [i for i in range(n) if ca[i] != cb[i]]
        if diffs:
            any_diff = True
            words = sorted({i & ~7 for i in diffs})[:16]
            out.append(f"  DIFFERS va=0x{va:x} size=0x{size:x} captured={len(ca)}/{len(cb)} "
                      f"ndiff={len(diffs)} first_words_of_diff={[hex(w) for w in words[:8]]}")
    if not any_diff:
        out.append("  every captured (prefix-bounded) BO content byte-identical at every shared VA.")
    return any_diff


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--output")
    a = ap.parse_args()
    run_dir = Path(a.run_dir).resolve()
    cases = load_cases(run_dir)
    raw_maps = load_raw_maps(run_dir)
    N = by_name(cases)
    out = []

    out.append("=== 1. K family: declared scratch vs registered-BO footprint (CS, grid=64/tg=32) ===")
    out.append(f"{'case':16s} {'K':>7s} {'meta_status':26s} {'probe_status':16s} "
              f"{'scratch_B':>9s} {'bo_count':>8s} {'bo_total_bytes':>14s} {'main_bytes':>10s}")
    for c in cases:
        if c["family"] != "K":
            continue
        out.append(f"{c['name']:16s} {str(c['k']):>7s} {str(c['meta_status']):26s} "
                  f"{str(c['probe_status']):16s} {str(c['scratch_field_41_or_14']):>9s} "
                  f"{str(c['bo_count']):>8s} {str(c['bo_total_bytes']):>14s} {str(c['main_bytes']):>10s}")
    k_exec = [c for c in cases if c["family"] == "K" and c["executed"]]
    ok_k = [c for c in k_exec if c["probe_status"] == "OK"]
    fail_k = [c for c in k_exec if c["probe_status"] != "OK"]
    bo_bytes_set = {c["bo_total_bytes"] for c in ok_k}
    bo_count_set = {c["bo_count"] for c in ok_k}
    out.append(f"\nDistinct bo_total_bytes values across all successful K cases: {sorted(bo_bytes_set)}")
    out.append(f"Distinct bo_count values across all successful K cases: {sorted(bo_count_set)}")
    if ok_k:
        out.append(f"Scratch range covered by successful K cases: "
                  f"{min(c['scratch_field_41_or_14'] for c in ok_k)} .. "
                  f"{max(c['scratch_field_41_or_14'] for c in ok_k)} bytes "
                  f"(K={min(c['k'] for c in ok_k)}..{max(c['k'] for c in ok_k)})")
    if fail_k:
        out.append(f"First/only clean failure in K family: {[c['name'] for c in fail_k]} "
                  f"(meta_status={[c['meta_status'] for c in fail_k]}, "
                  f"probe_detail={[c['probe_detail'] for c in fail_k]})")

    out.append("\n=== 2. S family: stage variation (VS/FS) at shared K levels ===")
    for c in cases:
        if c["family"] != "S":
            continue
        out.append(f"{c['name']:16s} scratch={c['scratch_field_41_or_14']} bo_count={c['bo_count']} "
                  f"bo_total_bytes={c['bo_total_bytes']} probe_status={c['probe_status']}")

    out.append("\n=== 3. O family: occupancy/topology ladder (K=1536 fixed) ===")
    for c in cases:
        if c["family"] != "O":
            continue
        out.append(f"{c['name']:28s} grid={c['grid']:>9} tg={c['tg']:>5} "
                  f"probe_status={c['probe_status']:8s} bo_count={c['bo_count']:>3} "
                  f"bo_total_bytes={c['bo_total_bytes']:>10}")

    out.append("\n=== 4. X family: compound stress (high K x large grid) ===")
    for c in cases:
        if c["family"] != "X":
            continue
        out.append(f"{c['name']:28s} K={c['k']:>6} grid={c['grid']:>9} "
                  f"scratch={c['scratch_field_41_or_14']:>7} probe_status={c['probe_status']:8s} "
                  f"bo_total_bytes={c['bo_total_bytes']:>10}")
        twin = None
        for o in cases:
            if o["family"] == "O" and o["grid"] == c["grid"] and o.get("tg") == c.get("tg"):
                twin = o
        if twin:
            same = twin["bo_total_bytes"] == c["bo_total_bytes"] and twin["resource_map_shape"] == c["resource_map_shape"]
            out.append(f"  vs O-family same-grid case {twin['name']} (K={twin['k']}): "
                      f"bo_total_bytes/shape identical despite {twin['k']}x vs {c['k']}x K = {same}")

    out.append("\n=== 5. H family: hot execution (n>1) ===")
    for c in cases:
        if c["family"] != "H":
            continue
        out.append(f"{c['name']:20s} n={c['n']:>5} probe_status={c['probe_status']:8s} "
                  f"checksum={c['checksum']} scratch={c['scratch_field_41_or_14']}")

    out.append("\n=== 6. Per-BO positional content diff (descriptive; VA used only as this run's "
              "own within-run key, never a cross-run/gate assumption) ===")
    if "K_cs_k8" in N and "K_cs_k65430" in N:
        diff_case_pair(run_dir, raw_maps, "K_cs_k8", "K_cs_k65430",
                       "K family: no-spill (K=8) vs max-tested-spill (K=65430, 261728 B)", out)
    if "O_cs_k1536_g1024_t32" in N and "O_cs_k1536_g1048576_t32" in N:
        diff_case_pair(run_dir, raw_maps, "O_cs_k1536_g1024_t32", "O_cs_k1536_g1048576_t32",
                       "O family: grid=1024 vs grid=1048576 (K fixed at 1536)", out)
    if "O_cs_k1536_g1048576_t32" in N and "X_cs_k49152_g1048576" in N:
        diff_case_pair(run_dir, raw_maps, "O_cs_k1536_g1048576_t32", "X_cs_k49152_g1048576",
                       "grid=1048576 fixed: K=1536 vs K=49152 (32x more declared scratch, same grid)", out)

    report = "\n".join(out) + "\n"
    if a.output:
        Path(a.output).write_text(report)
    print(report, end="")


if __name__ == "__main__":
    main()
