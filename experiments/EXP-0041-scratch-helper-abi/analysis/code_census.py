#!/usr/bin/env python3
"""Census only _agc.main bytes compiled from EXP-0041's authored MSL."""
import argparse
from collections import Counter
import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ISADB = REPO / "tools/agx-isa/isadb.py"
spec = importlib.util.spec_from_file_location("isadb", ISADB)
db = importlib.util.module_from_spec(spec); spec.loader.exec_module(db)

def main():
    p=argparse.ArgumentParser(); p.add_argument("--raw-dir",required=True); p.add_argument("--output"); a=p.parse_args()
    root=Path(a.raw_dir); lines=[]
    for path in sorted(root.glob("code_*/*_agc_main.hex")):
        buf=bytes.fromhex(path.read_text())
        recs,left=db.disassemble(buf); c=Counter(r.get("mnemonic","UNKNOWN") for r in recs)
        specials={k:c[k] for k in sorted(c) if any(x in k for x in ("spill","frame","link","special","sr"))}
        exact_spill=[i for i in range(len(buf)-3) if buf[i:i+4] == bytes.fromhex("60000000")]
        lines.append(f"{path.parent.name}/{path.name}: bytes={len(buf)} recs={len(recs)} leftover={len(left)} specials={specials} exact_60000000_offsets={exact_spill}")
        lines.append("  opcounts="+repr(dict(sorted(c.items()))))
        if left: lines.append("  leftover_hex="+left[:64].hex()+("..." if len(left)>64 else ""))
    report="\n".join(lines)+"\n"
    if a.output: Path(a.output).write_text(report)
    print(report,end="")
if __name__=="__main__": main()
