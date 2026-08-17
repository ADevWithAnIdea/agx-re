#!/usr/bin/env python3
"""Compare allocation shapes for equal user buffers at high occupancy."""
import argparse
from collections import Counter
from pathlib import Path
import re
def entries(path):
    out=[]
    for line in path.read_text().splitlines():
        m=re.match(r"RESOURCE_MAP class=(\S+) gpu_va=(0x[0-9a-f]+) size=(0x[0-9a-f]+)",line)
        if m:out.append((m.group(1),int(m.group(2),16),int(m.group(3),16)))
    return out
def main():
    p=argparse.ArgumentParser();p.add_argument("--run-dir",required=True);p.add_argument("--output",required=True);o=p.parse_args();root=Path(o.run_dir);lines=[]
    names=sorted(x.stem[4:] for x in root.glob("map_*.log"));base=entries(root/f"map_{names[0]}.log")
    for n in names:
        cur=entries(root/f"map_{n}.log"); sizes=Counter((x[0],x[2]) for x in cur); bs=Counter((x[0],x[2]) for x in base)
        result=next(x for x in (root/f"run_{n}.log").read_text().splitlines() if x.startswith("RESULT"))
        lines.append(f"{n}: {result}")
        lines.append(f"  allocation_count={len(cur)} ordered_map_sequence_equal={cur==base} size_multiset_removed={list((bs-sizes).elements())} size_multiset_added={list((sizes-bs).elements())}")
    Path(o.output).write_text("\n".join(lines)+"\n");print("\n".join(lines))
if __name__=="__main__":main()
