#!/usr/bin/env python3
"""Derive only mechanical capture facts; no expected hardware values are embedded."""
import argparse, json
from pathlib import Path
HERE=Path(__file__).resolve().parent
CASES=("rgba8unorm_edges","bgra8unorm_edges","rgba8srgb_threshold","r16unorm_midpoint","rgba16float_finite","r32uint_exact")
def payload(run):
    out={}
    for case in CASES:
        z=json.loads((HERE/"raw"/run/f"case_{case}.json").read_text())
        if z["timed_out"] or z["exit"] != 0: raise SystemExit("non-success case "+case)
        p=json.loads(z["stdout"])
        if set(p) != {"case","command_buffer_status","device","error","machine","os","physical_texel_hex","render_hex","compute_hex","compute_words_le","render_prefix_guard","render_suffix_guard","compute_prefix_guard","compute_suffix_guard"}: raise SystemExit("case schema "+case)
        if p["case"] != case or len(p["render_hex"]) != 768 or len(p["compute_hex"]) != 288 or not all(p[x] is True for x in ("render_prefix_guard","render_suffix_guard","compute_prefix_guard","compute_suffix_guard")): raise SystemExit("invalid owned backing "+case)
        out[case]={x:p[x] for x in ("physical_texel_hex","compute_words_le","render_hex","compute_hex","command_buffer_status","error")}
    return out
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--static",action="store_true");ap.add_argument("--run-a");ap.add_argument("--run-b");a=ap.parse_args()
    if a.static:
        if (HERE/"raw").exists(): raise SystemExit("raw exists: use capture verification, not static mode")
        print(json.dumps({"state":"PRE_GPU","result":"NO_OBSERVATIONS","cases":list(CASES)},sort_keys=True));return
    if not a.run_a or not a.run_b: raise SystemExit("two run IDs required")
    x,y=payload(a.run_a),payload(a.run_b)
    if x != y: raise SystemExit("repeat mismatch")
    print(json.dumps({"runs":[a.run_a,a.run_b],"repeat_exact":True,"cases":x},indent=2,sort_keys=True))
if __name__=="__main__": main()
