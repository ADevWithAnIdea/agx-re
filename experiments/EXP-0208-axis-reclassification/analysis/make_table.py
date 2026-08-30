#!/usr/bin/env python3
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
A = json.load(open(os.path.join(HERE, "axes.json")))
def short(s, n=1):
    return s.split(":")[0].split("(")[0].split("|")[0].strip()
rows = []
for k, v in sorted(A.items()):
    a = v["axes"]; c = a["counts"]
    rows.append("\t".join(str(x) for x in [
        k, v["label"], short(a["geometry"]), short(a["liveness"]), short(a["semantics"]),
        short(a["target"]), short(a["reproducibility"]),
        "passed-own-gate" if a["frozen_gate"].startswith("PASSED") else "never-promoted",
        c["encodable"], c["dispatched_distinct_values"],
        c["distinct_actual_encodings_best_single_arm"], c["records"],
        c["legal_values_ok"], c["silent_or_no_effect_records"], c["hard_records"],
        c["fault_values"], c["hang_values"], c["collapsed_encodings"], c["untested_values"],
        c["distinct_valid_payloads_max_single_carrier"], c["semantic_checks"], c["carriers"],
        "yes" if not a["hazard"].startswith(("none", "no dispatched")) else "no"]))
hdr = ("row\tlabel\tgeometry\tliveness\tsemantics\ttarget\treproducibility\tfrozen_gate\t"
       "encodable\tdispatched\tdistinct_actual_enc\trecords\tlegal_ok\tsilent\thard\t"
       "fault_values\thang_values\tcollapsed\tuntested\tvalid_payloads\tsem_checks\tcarriers\thazard")
open(os.path.join(HERE, "axes_table.tsv"), "w").write(hdr + "\n" + "\n".join(rows) + "\n")
print(len(rows), "rows written")
