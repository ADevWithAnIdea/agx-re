#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0197 step 5 -- the consequential question: for each CLAUSE-FALSE row, did
EXP-0189's repair point `evidence` at an experiment that is a WORSE source than the
original it declared empty?

Three mechanical axes, plus one authored column:
  A. did the repair REMOVE the original citation?      (git, commit 1f763864)
  B. does the repaired source vary the SAME db bits?   (positive_half.py / distinct_bytes.py)
  C. is the repaired source on the row's declared TARGET?
  D. the label the row would carry on the ORIGINAL citation ALONE  (authored)

Read-only.  Writes analysis/worse_source.json / .tsv.
"""
import json, os, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(EXP, "..", ".."))

# label the row would carry judged ONLY on its original citation, and why  (authored)
ORIG_ONLY = {
 "call.offset": ("isolated-byte-diff", "SUSTAINED",
   "4 own-MSL call distances, each program dispatched OK; no splice sweep, so not hardware-run -- which is the label it has."),
 "device_load.base_slot": ("hardware-run", "SUSTAINED",
   "256/256 dense splice census with per-value readback, two gated runs (EXP-0083)."),
 "device_load.idx_off": ("hardware-run", "SUSTAINED",
   "two independent complete 0..2047 dense sweeps (EXP-0082 device space, EXP-0100 threadgroup space)."),
 "falu_srcmod12b.ctrl": ("hardware-run", "SUSTAINED-THIN",
   "8 of 128 ctrl values swept across 7 kernels with faults and a real GPU hang (EXP-0089) plus an isolated {0,1} "
   "bit-2 pair in two gated runs (EXP-0119); boundaries+samples, not full range."),
 "falu_srcmod12b.opsel": ("isolated-byte-diff", "DOWNGRADE",
   "the 0..7 exhaustive sweep is real but its per-value OBSERVATIONS are committed only as EXP-0119 prose; the gated "
   "raw holds a single opsel value. On committed observation artifacts alone this does not reach hardware-run."),
 "frag_color_pack.src_present_mask": ("hardware-run", "SUSTAINED-CHAIN-BROKEN",
   "7 values on 2 pack ops with per-value pixel outcomes and an illegal-value GPU fault -- but recorded only inside one "
   "narrative JSON string in an experiment with no raw/ tree."),
 "frag_color_store.rt_index": ("isolated-byte-diff", "SUSTAINED",
   "one isolated byte splice 0x00->0x02 with the predicted observed effect (EXP-0029 validations.log section 6)."),
 "frag_color_store.src": ("isolated-byte-diff", "SUSTAINED-WEAK",
   "3 values across dispatched own-MSL programs; EXP-0029 contains no splice of this byte, so the row's "
   "'splice-proven' wording is not supported by the original citation."),
 "fspecial_est.subop": ("hardware-run", "SUSTAINED", "256/256 dense, 3 carriers, 2 gated runs (EXP-0171)."),
 "half_alu.dst": ("hardware-run", "SUSTAINED-FOR-THE-FAMILY",
   "16/16 dense on byte0's high nibble, 2 carriers, 2 gated runs -- on the 8-byte sibling form; the 6-byte descriptor "
   "itself is never dispatched in EXP-0180."),
 "iadd2.srcA": ("hardware-run", "SUSTAINED", "256/256 dense, 3 carriers, 2 gated runs (EXP-0171)."),
 "ibfe.srcA": ("hardware-run", "SUSTAINED", "256/256 dense, 2 carriers, 2 gated runs (EXP-0171)."),
 "icmp_pred.dst_pred": ("hardware-run", "SUSTAINED", "16/16 exhaustive, 2 gated runs (EXP-0115 CF-05)."),
 "ilogic.lut_a_z": ("hardware-run", "SUSTAINED", "8/8 exhaustive for the 3-bit field, 3 carriers, 2 gated runs (EXP-0171)."),
 "ilogic.outmod": ("hardware-run", "SUSTAINED", "256/256 dense, 3 carriers, 2 gated runs (EXP-0171)."),
 "iter.mode": ("isolated-byte-diff", "SUSTAINED",
   "3 values across dispatched own-MSL interpolation variants with 4x4 pixel dumps (EXP-0029)."),
 "iter.src_slot": ("isolated-byte-diff", "SUSTAINED",
   "isolated byte splice 0x00->0x02 with baseline and spliced pixel dumps (EXP-0029 section 3)."),
 "mov_zext16.src_reg": ("hardware-run", "SUSTAINED",
   "16/16 nibble values on 2 carriers in 2 gated runs, via the byte0 probe (EXP-0161)."),
 "simd_shuffle.lane": ("hardware-run", "SUSTAINED",
   "42 distinct lane bytes incl. 0/1/2/126/127/128/254/255, 2 gated runs (EXP-0115 SIMD-03-static)."),
 "simd_shuffle.mode": ("isolated-byte-diff", "SUSTAINED",
   "6 mode values across own-MSL subgroup kernels, each with a per-kernel PASS (EXP-0018)."),
 "stop.reserved": ("untested", "N/A",
   "already `untested` and already WITHHELD; the two committed cases co-vary byte0 and so isolate nothing."),
 "tex_sample.result_desc": ("isolated-byte-diff", "SUSTAINED",
   "4 gather-component values with per-value OUT dumps (EXP-0034 hw_validation section 4)."),
 "tex_sample.samp_slot_offset": ("isolated-byte-diff", "SUSTAINED",
   "isolated splice 0x01->0x00 with a before/after 8x8 dump (EXP-0016 section 4) plus 5 corpus values (EXP-0034)."),
 "tex_sample.tex_slot": ("hardware-run", "SUSTAINED",
   "16/16 upper-nibble splices plus 12 low-nibble cases, each with its own out_word (EXP-0114, two non-quarantined runs)."),
 "tex_sample.variant": ("hardware-run", "SUSTAINED-PARTIAL",
   "~16 distinct dim/LOD codes across three originals, 8 of them splice-proven with a dim-splice break (EXP-M4-10); "
   "boundaries+interior, not the full 256."),
 "vary_store.out_slot": ("isolated-byte-diff", "SUSTAINED",
   "3 isolated byte+4 splices with observed corner pixels plus all 8 slot values in the committed vertex mains (EXP-0037)."),
 "vary_store.src": ("isolated-byte-diff", "SUSTAINED",
   "2 isolated byte+3 splices with observed corner pixels plus 8 corpus values (EXP-0037)."),
}

TGT = {"G17P/A18": {"A18", "G17P", "M4+A18"}, "M4": {"M4", "M4+A18"}}


def slug_target(slug):
    s = slug.lower()
    if "g17p" in s or "a18" in s:
        return "G17P/A18"
    if "m4" in s:
        return "M4"
    return "?"


def main():
    verdicts = {v["key"]: v for v in json.load(open(os.path.join(HERE, "verdicts.json")))}
    pos = json.load(open(os.path.join(EXP, "work", "positive_half.json")))
    # axis A -- straight from git
    before = json.loads(subprocess.check_output(
        ["git", "-C", ROOT, "show", "1f763864^:tools/agx-isa/validation.json"]))
    after = json.loads(subprocess.check_output(
        ["git", "-C", ROOT, "show", "1f763864:tools/agx-isa/validation.json"]))
    out = []
    for k, v in sorted(verdicts.items()):
        if v["verdict"] != "CLAUSE-FALSE":
            continue
        m, f = k.split(".", 1)
        eb = set(before["instructions"][m][f].get("evidence") or [])
        ea = set(after["instructions"][m][f].get("evidence") or [])
        p = pos.get(k, {}).get("per", {})
        have = {d: (s["k1_named"] + s["k2_byte"] + s["k4_anch"]) > 0 for d, s in p.items()}
        tgts = {d: slug_target(d) for d in p}
        rowtgt = v["target"]
        ok_tgt = [d for d, t in tgts.items() if rowtgt in TGT.get(t, set())]
        lab, status, why = ORIG_ONLY[k]
        out.append({
            "key": k, "label_now": v["label"], "target": rowtgt,
            "orig": v["orig_citation"], "repaired_to": v["repaired_to"],
            "A_original_removed": sorted(eb - ea),
            "B_repaired_has_records": have,
            "C_repaired_target": tgts,
            "C_any_repaired_on_row_target": bool(ok_tgt),
            "D_label_on_original_alone": lab,
            "D_status": status, "D_why": why,
        })
    json.dump(out, open(os.path.join(HERE, "worse_source.json"), "w"), indent=1)
    print("%-34s %-18s %-8s %-26s %s" % ("row", "label_now", "target",
                                         "label on ORIGINAL alone", "repaired source on row target?"))
    for o in out:
        print("%-34s %-18s %-8s %-26s %s   removed=%s"
              % (o["key"], o["label_now"], o["target"],
                 "%s (%s)" % (o["D_label_on_original_alone"], o["D_status"]),
                 o["C_any_repaired_on_row_target"], o["A_original_removed"] or "none"))
    print()
    print("rows where the repair REMOVED the original:",
          sum(1 for o in out if o["A_original_removed"]))
    print("rows where NO repaired source is on the row's declared target:",
          [o["key"] for o in out if not o["C_any_repaired_on_row_target"]])
    print("rows whose current label does NOT survive on the original alone:",
          [o["key"] for o in out if o["D_status"] == "DOWNGRADE"])


if __name__ == "__main__":
    main()
