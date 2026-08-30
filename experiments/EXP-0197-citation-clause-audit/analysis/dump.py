#!/usr/bin/env python3
"""EXP-0197 -- pretty-print one row's scan evidence.  Read-only."""
import json, os, sys
HERE=os.path.dirname(os.path.abspath(__file__))
W=os.path.join(HERE,"..","work")
s=json.load(open(os.path.join(W,"scan_summary.json")))
for k in sys.argv[1:]:
    r=s[k]
    print("="*90); print(k, r["row"]["label"], "span",r["row"]["start"],r["row"]["width"],"bytes",r["row"]["bytes_of_span"])
    for d,a in r["original"].items():
        print(" --",d,"files",a["files_scanned"],"jsonl",a["jsonl_files"],"json",a["json_files"],"text",a["text_files"],"uniq_blobs",a["unique_blobs"])
        for kk in ("k1_named","k2_byte"):
            print("   ",kk,a[kk]["n"],"distinct",a[kk].get("distinct_values"))
            if a[kk]["first"]: print("      first",json.dumps(a[kk]["first"])[:300])
        print("    k3_group",a["k3_group"]["n"],list(a["k3_group"]["labels"].items())[:8])
        for kk in ("k4_anchored","k4_matchfit"):
            print("   ",kk,a[kk]["blobs"],"distinct_field_values",a[kk]["distinct_values"],a[kk]["values"][:40])
            print("      byfile",list(a[kk]["by_file"].items())[:6])
        for e in a["k4_anchored"]["examples"][:6]:
            print("      ex",e)
        print("    instr_names_seen",list(a["instr_names_seen"].items())[:8])
        print("    field_names_seen",list(a["field_names_seen"].items())[:8])
