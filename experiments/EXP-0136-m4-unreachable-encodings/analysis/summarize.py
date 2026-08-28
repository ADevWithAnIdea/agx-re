#!/usr/bin/env python3
"""EXP-0136 analysis: reads raw/<run>/02_gated.jsonl and prints the per-family
summaries used in RESULTS.md. Read-only; does not mutate raw/."""
import json, sys
from pathlib import Path
from collections import defaultdict

EXP = Path(__file__).resolve().parent.parent
RUN = sys.argv[1] if len(sys.argv) > 1 else "m4_20260828_run01"


def load():
    recs = {}
    for line in (EXP / "raw" / RUN / "02_gated.jsonl").read_text().splitlines():
        d = json.loads(line)
        recs[d["case_id"]] = d
    return recs


def main():
    recs = load()

    print("=== ANISO (H1) ===")
    for ratio in (16, 64, 128):
        row = []
        for a in (1, 2, 4, 8, 16):
            cid = f"aniso_ratio{ratio}_real{a}"
            if cid in recs:
                r = recs[cid]["observed"]["pixel"][0]
                row.append(f"real{a}={r:.3f}")
        for a in (32, 64, 128):
            cid = f"aniso_ratio{ratio}_patch{a}"
            if cid in recs:
                r = recs[cid]["observed"]["pixel"][0]
                row.append(f"patch{a}={r:.3f}")
        print(f"ratio={ratio:4d}: " + "  ".join(row))

    print()
    print("=== ADDRMODE (H2) signatures (pixel per code x 4 u-points) ===")
    sigs = {}
    for code in range(8):
        sig = []
        for ui in range(4):
            cid = f"addrmode_code{code}_u{ui}"
            sig.append(tuple(round(v, 4) for v in recs[cid]["observed"]["pixel"]))
        sigs[code] = sig
        print(f"code{code}: {sig}")
    print()
    print("-- alias check (codes 4,6,7 vs 0,1,2,3,5) --")
    for unk in (4, 6, 7):
        matches = [known for known in (0, 1, 2, 3, 5) if sigs[unk] == sigs[known]]
        print(f"code{unk} signature matches: {matches if matches else 'NO MATCH -- distinct behavior'}")

    print()
    print("=== BORDER (H3) ===")
    for creation in ("transparentBlack", "opaqueBlack", "opaqueWhite"):
        row = []
        for code in (0, 1, 2, 3):
            cid = f"border_create{creation}_code{code}"
            p = recs[cid]["observed"]["pixel"]
            row.append(f"code{code}={tuple(round(v,2) for v in p)}")
        print(f"created={creation:17s}: " + "  ".join(row))

    print()
    print("=== SWIZZLE (H4) ===")
    for comp in (0, 1):
        for code in range(8):
            cid = f"swizzle_comp{comp}_code{code}"
            if cid not in recs:
                continue
            rec = recs[cid]
            status = rec["status"]
            pix = rec["observed"].get("pixel")
            err = rec["observed"].get("error")
            print(f"comp{comp} code{code}: status={status} pixel={pix} error={err}")

    print()
    print("=== RESTART (H5) ===")
    for cid in ("restart_u16_allones", "restart_u16_allones_minus1", "restart_u16_small_oob",
                "restart_u32_allones", "restart_u32_allones_minus1", "restart_u32_small_oob"):
        o = recs[cid]["observed"]
        print(f"{cid}: status={recs[cid]['status']} sentinel={o.get('sentinel_used')} "
              f"connector_lit={o.get('connector_band_lit')} left={o.get('left_segment_lit')} "
              f"right={o.get('right_segment_lit')}")

    print()
    print("=== NORENDER (H6) ===")
    for cid in ("norender_rasterTrue", "norender_rasterFalse"):
        o = recs[cid]["observed"]
        print(f"{cid}: status={recs[cid]['status']} vtx_invocations={o.get('vertex_invocations_observed')} "
              f"any_fragment={o.get('any_fragment_rendered')}")

    print()
    print("=== OPCODE (H7) ===")
    fails = 0
    for cid, rec in recs.items():
        if rec["family"] != "opcode":
            continue
        if rec["verdict"] != "PASS":
            fails += 1
            print(f"NON-PASS: {cid} status={rec['status']} observed={rec['observed']}")
    print(f"opcode family: {sum(1 for r in recs.values() if r['family']=='opcode')} cases, {fails} non-PASS")


if __name__ == "__main__":
    main()
