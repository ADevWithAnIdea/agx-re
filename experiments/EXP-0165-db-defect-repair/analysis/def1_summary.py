#!/usr/bin/env python3
"""Summarise the DEF-0161-1 re-derivation dump into an explicit fit/refute table."""
from __future__ import print_function
import json, sys, subprocess
from pathlib import Path
HERE = Path(__file__).resolve().parent
d = json.loads(subprocess.check_output([sys.executable, str(HERE / "rederive_def1_fspecial.py")]).decode())

out = {}
for run, rep in d.items():
    r = {"baseline_bytes": rep["baseline_bytes"],
         "byte1_hi_nibble_inert": (len(rep["db_dst_byte1hi"]["identical_to_baseline"]) == 16
                                   and not rep["db_dst_byte1hi"]["different"]),
         "byte1_hi_values_identical": len(rep["db_dst_byte1hi"]["identical_to_baseline"])}
    # byte+3 : does dest = v>>1 hold?
    fit3, miss3, quiet3 = [], [], []
    for c in rep["byte3_cases"]:
        v = c["value"]; want = v >> 1
        w = c["rsqrt_writes"]
        if not w:
            quiet3.append({"value": v, "changed": c["changed"], "zeroed": c["zeroed"]})
        elif all(i == want for (i, j) in w) and all(j == 0 for (i, j) in w):
            fit3.append(v)
        else:
            miss3.append({"value": v, "writes": w})
    r["byte3_dest_rule_v_shr_1"] = {"fits": len(fit3), "misfits": miss3,
                                    "no_visible_write": len(quiet3),
                                    "no_visible_write_values": [q["value"] for q in quiet3][:40],
                                    "fit_values": fit3}
    # is the SOURCE constant (r0) across all byte+3 values that wrote?
    srcs = sorted(set(j for c in rep["byte3_cases"] for (i, j) in c["rsqrt_writes"]))
    r["byte3_source_regs_seen"] = srcs
    # byte+5 : does source = v>>2 hold, and does the dest stay r0?
    fit5, miss5, quiet5 = [], [], []
    for c in rep["byte5_cases"]:
        v = c["value"]; want = v >> 2
        w = c["rsqrt_writes"]
        if not w:
            quiet5.append(v)
        elif all(j == want for (i, j) in w) and all(i == 0 for (i, j) in w):
            fit5.append(v)
        else:
            miss5.append({"value": v, "writes": w, "zeroed": c["zeroed"]})
    r["byte5_source_rule_v_shr_2"] = {"fits": len(fit5), "misfits": miss5,
                                      "no_visible_write": len(quiet5),
                                      "no_visible_write_values": quiet5[:40],
                                      "fit_values": fit5}
    # release-on-read: is the register named by byte+5 zeroed?
    rel_ok, rel_bad = [], []
    for c in rep["byte5_cases"]:
        v = c["value"]; want = v >> 2
        if want == 0:      # dest == src, cannot distinguish
            continue
        if want in c["zeroed"]:
            rel_ok.append(v)
        else:
            rel_bad.append({"value": v, "zeroed": c["zeroed"], "changed": c["changed"]})
    r["byte5_release_on_read"] = {"zeroed_as_predicted": len(rel_ok),
                                  "not_zeroed": rel_bad[:20],
                                  "n_not_zeroed": len(rel_bad)}
    out[run] = r
print(json.dumps(out, indent=1))
