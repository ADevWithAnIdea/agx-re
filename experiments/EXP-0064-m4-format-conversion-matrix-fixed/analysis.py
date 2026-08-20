#!/usr/bin/env python3
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
RUNS=("m4_20260820_run01","m4_20260820_run02")
CASES=("rgba8unorm_edges","bgra8unorm_edges","rgba8srgb_threshold","r16unorm_midpoint","rgba16float_edges","r32uint_exact")
def load(run):
 out={}
 for c in CASES:
  r=json.loads((HERE/"raw"/run/f"case_{c}.json").read_text()); assert not r["timeout"] and r["exit"]==0
  p=json.loads(r["stdout"]); assert p["status"]==4 and len(p["render_hex"])==768 and len(p["compute_hex"])==288 and all(p[k] for k in ("render_prefix_guard","render_suffix_guard","compute_prefix_guard","compute_suffix_guard"))
  out[c]={k:p[k] for k in ("physical_texel_hex","compute_words_le","render_hex","compute_hex")}
 return out
a,b=load(RUNS[0]),load(RUNS[1]); print(json.dumps({"runs":RUNS,"repeat_exact":a==b,"cases":a},indent=2,sort_keys=True)); assert a==b
