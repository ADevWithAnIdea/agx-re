#!/usr/bin/env python3
"""Compare two complete EXP-0041 runs after excluding CPU/ASLR-only values."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

CASES=("cs_nospill_k72","cs_spill_k80","cs_spill_k96","cs_spill_k112","cs_spill_k160",
       "vs_nospill_k72","vs_spill_k112","fs_nospill_k72","fs_spill_k112")

def jsonline(path):
    return json.loads(next(x for x in path.read_text().splitlines() if x.startswith("{")))
def maps(path):
    out=[]
    for line in path.read_text().splitlines():
        m=re.match(r"RESOURCE_MAP class=(\S+) gpu_va=(0x[0-9a-f]+) size=(0x[0-9a-f]+)",line)
        if m: out.append((m.group(1),int(m.group(2),16),int(m.group(3),16)))
    return Counter(out)
def hexbytes(path):
    b=bytearray()
    for line in path.read_text().splitlines():
        if line.startswith("#"): continue
        b.extend(bytes.fromhex("".join(line.split(":",1)[1].split())))
    return bytes(b)
def main():
    p=argparse.ArgumentParser(); p.add_argument("--run-a",required=True); p.add_argument("--run-b",required=True); p.add_argument("--output",required=True)
    o=p.parse_args(); a=Path(o.run_a); b=Path(o.run_b); lines=[]; ok=True
    for case in CASES:
        ma=jsonline(a/f"metadata_{case}.log")["stages"]; mb=jsonline(b/f"metadata_{case}.log")["stages"]
        meq=ma==mb; mapq=maps(a/f"map_{case}.log")==maps(b/f"map_{case}.log")
        ra=next(x for x in (a/f"run_{case}.log").read_text().splitlines() if x.startswith("RESULT"))
        rb=next(x for x in (b/f"run_{case}.log").read_text().splitlines() if x.startswith("RESULT")); req=ra==rb
        ca={p.name:hexbytes(p) for p in (a/f"cmd_{case}").glob("*.hex")}; cb={p.name:hexbytes(p) for p in (b/f"cmd_{case}").glob("*.hex")}
        ceq=ca==cb
        lines.append(f"{case}: metadata_equal={meq} resource_maps_equal={mapq} result_equal={req} command_bos_equal={ceq}")
        for name,data in sorted(ca.items()): lines.append(f"  {name} sha256={hashlib.sha256(data).hexdigest()}")
        ok &= meq and mapq and req and ceq
    lines.append(f"VERDICT all_semantic_observations_repeat={ok}")
    Path(o.output).write_text("\n".join(lines)+"\n")
    print("\n".join(lines))
    raise SystemExit(0 if ok else 1)
if __name__=="__main__": main()
