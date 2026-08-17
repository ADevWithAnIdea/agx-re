#!/usr/bin/env python3
"""Repeatable paired analysis of metadata, allocation logs, and allowlisted command BOs."""
from collections import Counter
import argparse
import json
from pathlib import Path
import re
import struct

HERE = Path(__file__).resolve().parents[1]
PAIRS = [("cs_nospill_k72", x) for x in ("cs_spill_k80","cs_spill_k96","cs_spill_k112","cs_spill_k160")]
PAIRS += [("vs_nospill_k72","vs_spill_k112"),("fs_nospill_k72","fs_spill_k112")]

def meta(name):
    text = (RAW / f"metadata_{name}.log").read_text()
    line = next(x for x in text.splitlines() if x.startswith("{"))
    return json.loads(line)

def maps(name):
    ans = []
    for line in (RAW / f"map_{name}.log").read_text().splitlines():
        m = re.match(r"RESOURCE_MAP class=(\S+) gpu_va=(0x[0-9a-f]+) size=(0x[0-9a-f]+) handle=(\d+)", line)
        if m: ans.append((m.group(1), int(m.group(2),16), int(m.group(3),16)))
    return Counter(ans)

def hexfile(path):
    data = bytearray()
    for line in path.read_text().splitlines():
        if line.startswith("#"): continue
        _, body = line.split(":",1)
        data.extend(bytes.fromhex("".join(body.split())))
    return bytes(data)

def cmd(name):
    return {int(re.search(r"va([0-9a-f]+)_", p.name).group(1),16): hexfile(p)
            for p in (RAW / f"cmd_{name}").glob("bo_*.hex")}

def main():
    global RAW
    p = argparse.ArgumentParser(); p.add_argument("--run-dir", required=True); p.add_argument("--output")
    opts = p.parse_args(); RAW = Path(opts.run_dir).resolve()
    if not RAW.is_dir(): raise SystemExit(f"not a directory: {RAW}")
    out = []
    out.append("METADATA (direct observations from OWN-MSL archive metadata)")
    for name in sorted({x for pair in PAIRS for x in pair}):
        m = meta(name)
        stage = "compute" if name.startswith("cs_") else ("vertex" if name.startswith("vs_") else "fragment")
        s = m["stages"][stage]
        out.append(f"{name}: stage={stage} gpr={s['gpr_field_0']} scratchB={s['scratch_field_41_or_14']}")
    out.append("\nRESOURCE MAP DIFFERENCES (class, GPU VA, bytes; CPU addresses excluded)")
    for a,b in PAIRS:
        ma, mb = maps(a), maps(b); removed = list((ma-mb).elements()); added = list((mb-ma).elements())
        out.append(f"{a} -> {b}: removed={removed} added={added}")
    out.append("\nALLOWLISTED COMMAND/STATE BO DIFFERENCES (never follows pointer values)")
    for a,b in PAIRS:
        ca, cb = cmd(a), cmd(b)
        for va in sorted(set(ca)&set(cb)):
            aa,bb=ca[va],cb[va]; n=min(len(aa),len(bb)); diffs=[i for i in range(n) if aa[i]!=bb[i]]
            out.append(f"{a} -> {b} va=0x{va:x}: sizes={len(aa)}/{len(bb)} ndiff={len(diffs)} first={[hex(x) for x in diffs[:64]]}")
            # Report changed aligned words as raw values only. They may be cfg/data/address fields;
            # no target memory is read and no program bytes are interpreted.
            words=sorted({i & ~7 for i in diffs})[:64]
            for off in words:
                if off+8<=n:
                    x=struct.unpack_from('<Q',aa,off)[0]; y=struct.unpack_from('<Q',bb,off)[0]
                    out.append(f"  +0x{off:04x}: 0x{x:016x} -> 0x{y:016x}")
    report="\n".join(out)+"\n"
    if opts.output: Path(opts.output).write_text(report)
    print(report,end="")

if __name__ == "__main__": main()
