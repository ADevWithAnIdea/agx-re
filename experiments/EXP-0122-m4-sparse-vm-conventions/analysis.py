#!/usr/bin/env python3
"""EXP-0122 analysis: cross-run gated-equality check (must be clean, or this refuses to
write) plus derived, human-readable summaries per domain. Writes analysis/summary.json and
analysis/report.txt. Never edits raw/."""
import argparse, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run as R          # noqa: E402
import verify as V        # noqa: E402

OUT_DIR = HERE / "analysis"


def load(run_id):
    d = HERE / "raw" / run_id
    return V.load_run(d), d


def rows_by_name(run, domain):
    return {r["name"]: r for r in run.get(domain, [])}


def rec_gated(row):
    return row["record"]["gated"] if row and row.get("record") else None


def summarize_align(run):
    rows = rows_by_name(run, "align")
    sweep = rows.get("align_sweep")
    if not sweep:
        return {"present": False}
    entries = rec_gated(sweep)["rows"]
    aligns = sorted(set(int(e["heap_align"]) for e in entries))
    all_ok = all(e["alloc_ok"] for e in entries)
    return {"present": True, "n_rows": len(entries), "distinct_heap_align_values": aligns,
            "all_alloc_ok": all_ok}


def summarize_maxlen(run):
    rows = rows_by_name(run, "maxlen_boundary")
    r = rows.get("maxlen_boundary")
    if not r:
        return {"present": False}
    entries = rec_gated(r)["rows"]
    by_label = {}
    for e in entries:
        by_label.setdefault(e["label"], []).append(e["alloc_ok"])
    return {"present": True, "boundary_by_label": {k: v for k, v in by_label.items()}}


def summarize_addrsurvey(run):
    rows = rows_by_name(run, "addrsurvey")
    r = rows.get("addrsurvey")
    if not r or not r.get("record"):
        return {"present": False}
    raw_passes = r["record"]["raw"]["passes"]
    identical_across_passes = all(
        [e["gpu_addr_hex"] for e in raw_passes[0]] == [e["gpu_addr_hex"] for e in p]
        for p in raw_passes[1:]
    ) if len(raw_passes) > 1 else None
    return {"present": True, "n_passes": len(raw_passes),
            "addresses_identical_across_passes_within_run": identical_across_passes,
            "pass1_addresses": [e["gpu_addr_hex"] for e in raw_passes[0]]}


def summarize_guard(run):
    rows = run.get("guard", [])
    by_name = {r["name"]: r for r in rows}
    skipped = [n for n, r in by_name.items() if r["exec_status"] != "ok" and
               (r.get("record") is None)]
    watchdogs = [n for n, r in by_name.items() if r["exec_status"] in
                 ("watchdog_compile", "watchdog_dispatch", "proc_timeout")]
    zero_reads, nonzero_reads = [], []
    for n, r in by_name.items():
        if not n.startswith("guard_read_"):
            continue
        g = rec_gated(r)
        if not g or g.get("status") != "ok":
            continue
        obs = g.get("obs_hex", "")
        (zero_reads if obs == "00000000" else nonzero_reads).append(n)
    return {
        "n_cases": len(rows), "n_skipped_or_missing": len(skipped), "n_watchdog_or_timeout": len(watchdogs),
        "watchdog_names": watchdogs,
        "n_zero_reads": len(zero_reads), "n_nonzero_reads": len(nonzero_reads),
        "zero_read_names": sorted(zero_reads), "nonzero_read_names": sorted(nonzero_reads),
    }


def summarize_sparse_caps(run):
    rows = rows_by_name(run, "sparse_caps")
    r = rows.get("sparse_caps")
    if not r or not r.get("record"):
        return {"present": False}
    entries = rec_gated(r)["rows"]
    table = []
    for e in entries:
        bpp = None
        row = {"type": e["type"], "format": e["format"], "samples": e["samples"],
               "tile_default": [e["tile_w"], e["tile_h"], e["tile_d"]]}
        for pg in ("16", "64", "256"):
            key = "tile_page" + pg
            if key in e:
                row[key] = [e[key]["w"], e[key]["h"], e[key]["d"]]
        table.append(row)
    return {"present": True, "n_combos": len(entries), "table": table}


def summarize_sparse_miptail(run):
    rows = rows_by_name(run, "sparse_miptail")
    r = rows.get("sparse_miptail")
    if not r or not r.get("record"):
        return {"present": False}
    entries = rec_gated(r)["rows"]
    return {"present": True, "n_cases": len(entries), "table": entries}


def summarize_sparse_unmapped(run):
    rows = run.get("sparse_unmapped_read", [])
    out = []
    all_zero = True
    for r in rows:
        g = rec_gated(r)
        if not g:
            continue
        vals = g.get("values_hex", [])
        zero = all(v == "0" * len(v) for v in vals)
        all_zero = all_zero and zero
        out.append({"name": r["name"], "cb_status": g.get("cb_status"), "all_values_zero": zero,
                    "n_coords": len(vals)})
    return {"cases": out, "every_case_all_zero": all_zero}


def summarize_sparse_partial_and_remap(run):
    pm = []
    for r in run.get("sparse_partial_map", []):
        g = rec_gated(r)
        if not g:
            continue
        pm.append({"name": r["name"], "map_ok": g.get("map_ok"),
                   "heap_used_bytes_after_map": g.get("heap_used_bytes_after_map"),
                   "read_values_hex": g.get("read_values_hex"),
                   "write_appears_to_persist": any(v != "0" * len(v) for v in g.get("read_values_hex", []))})
    rm = []
    for r in run.get("sparse_remap", []):
        g = rec_gated(r)
        if not g:
            continue
        rm.append({"name": r["name"], "map1_ok": g.get("map1_ok"), "unmap_ok": g.get("unmap_ok"),
                   "remap_ok": g.get("remap_ok"),
                   "read_after_write": g.get("read_after_write_hex"),
                   "read_after_unmap": g.get("read_after_unmap_hex"),
                   "read_after_remap": g.get("read_after_remap_hex")})
    return {"partial_map": pm, "remap": rm}


def summarize_timestamp(run):
    rows = rows_by_name(run, "timestamp_ladder")
    r = rows.get("timestamp_ladder")
    if not r or not r.get("record"):
        return {"present": False}
    g = rec_gated(r)
    all_mono = all(row["cpu_monotonic"] and row["gpu_monotonic"] for row in g["rows"])
    raw_rows = r["record"]["raw"]["rows"]
    all_equal_cpu_gpu = all(row["cpu1"] == row["gpu1"] and row["cpu2"] == row["gpu2"] for row in raw_rows)
    return {"present": True, "mach_timebase_numer": g["mach_timebase_numer"],
            "mach_timebase_denom": g["mach_timebase_denom"],
            "all_pairs_monotonic": all_mono, "all_pairs_cpu_equals_gpu": all_equal_cpu_gpu,
            "raw_pairs": raw_rows}


def build_summary(run_id_a, run_id_b):
    run_a, dir_a = load(run_id_a)
    run_b, dir_b = load(run_id_b)
    mismatches = V.compare_gated(run_a, run_b)
    summary = {
        "schema": R.SCHEMA, "experiment": R.EXPERIMENT,
        "run_a": run_id_a, "run_b": run_id_b,
        "cross_run_gated_mismatches": mismatches,
        "cross_run_gated_clean": mismatches == [],
        "align": summarize_align(run_a),
        "maxlen_boundary": summarize_maxlen(run_a),
        "addrsurvey": summarize_addrsurvey(run_a),
        "guard": summarize_guard(run_a),
        "sparse_caps": summarize_sparse_caps(run_a),
        "sparse_miptail": summarize_sparse_miptail(run_a),
        "sparse_unmapped_read": summarize_sparse_unmapped(run_a),
        "sparse_partial_map_and_remap": summarize_sparse_partial_and_remap(run_a),
        "timestamp": summarize_timestamp(run_a),
    }
    return summary


def render_report(s):
    lines = []
    lines.append("EXP-0122 analysis report")
    lines.append("run_a=%s run_b=%s" % (s["run_a"], s["run_b"]))
    lines.append("cross_run_gated_clean=%s (mismatches=%d)" %
                  (s["cross_run_gated_clean"], len(s["cross_run_gated_mismatches"])))
    lines.append("")
    lines.append("[align] rows=%s distinct_heap_align=%s all_alloc_ok=%s" %
                  (s["align"].get("n_rows"), s["align"].get("distinct_heap_align_values"),
                   s["align"].get("all_alloc_ok")))
    lines.append("[maxlen_boundary] %s" % s["maxlen_boundary"].get("boundary_by_label"))
    lines.append("[addrsurvey] passes=%s identical_across_passes=%s" %
                  (s["addrsurvey"].get("n_passes"), s["addrsurvey"].get("addresses_identical_across_passes_within_run")))
    g = s["guard"]
    lines.append("[guard] n_cases=%d watchdog_or_timeout=%d zero_reads=%d nonzero_reads=%d" %
                  (g["n_cases"], g["n_watchdog_or_timeout"], g["n_zero_reads"], g["n_nonzero_reads"]))
    lines.append("  nonzero_read_names=%s" % g["nonzero_read_names"])
    lines.append("[sparse_caps] combos=%d" % s["sparse_caps"].get("n_combos", 0))
    lines.append("[sparse_miptail] cases=%d" % s["sparse_miptail"].get("n_cases", 0))
    su = s["sparse_unmapped_read"]
    lines.append("[sparse_unmapped_read] every_case_all_zero=%s (%d cases)" %
                  (su["every_case_all_zero"], len(su["cases"])))
    spr = s["sparse_partial_map_and_remap"]
    lines.append("[sparse_partial_map] write_appears_to_persist=%s" %
                  [pm["write_appears_to_persist"] for pm in spr["partial_map"]])
    lines.append("[sparse_remap] %s" % spr["remap"])
    t = s["timestamp"]
    lines.append("[timestamp] all_monotonic=%s all_cpu_equals_gpu=%s mach_timebase=%s/%s" %
                  (t.get("all_pairs_monotonic"), t.get("all_pairs_cpu_equals_gpu"),
                   t.get("mach_timebase_numer"), t.get("mach_timebase_denom")))
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-a", default="m4-20260828-run01")
    ap.add_argument("--run-b", default="m4-20260828-run02")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    summary = build_summary(args.run_a, args.run_b)
    report = render_report(summary)
    print(report)
    if not summary["cross_run_gated_clean"]:
        print("REFUSING to write: cross-run gated mismatches present", file=sys.stderr)
        sys.exit(1)
    if args.write:
        OUT_DIR.mkdir(exist_ok=True)
        (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
        (OUT_DIR / "report.txt").write_text(report)
        print("wrote", OUT_DIR / "summary.json", "and", OUT_DIR / "report.txt")


if __name__ == "__main__":
    main()
