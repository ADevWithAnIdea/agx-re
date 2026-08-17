#!/usr/bin/env python3
"""Compare resource-map geometry across the EXP-0041 scale sweep."""
import argparse
from collections import Counter
from pathlib import Path
import re
def maps(path):
    c=Counter()
    for line in path.read_text().splitlines():
        m=re.match(r"RESOURCE_MAP class=(\S+) gpu_va=(0x[0-9a-f]+) size=(0x[0-9a-f]+)",line)
        if m:c[(m.group(1),int(m.group(2),16),int(m.group(3),16))]+=1
    return c
def main():
    p=argparse.ArgumentParser();p.add_argument("--run-dir",required=True);p.add_argument("--output",required=True);o=p.parse_args();root=Path(o.run_dir)
    names=sorted(x.stem[4:] for x in root.glob("map_*.log")); base=maps(root/"map_nospill_k72_g64_t32.log");lines=[]
    for n in names:
        c=maps(root/f"map_{n}.log"); result=next(x for x in (root/f"run_{n}.log").read_text().splitlines() if x.startswith("RESULT"))
        lines.append(f"{n}: {result}")
        lines.append(f"  versus_nospill_g64 removed={list((base-c).elements())} added={list((c-base).elements())}")
    Path(o.output).write_text("\n".join(lines)+"\n");print("\n".join(lines))
if __name__=="__main__":main()
