#!/usr/bin/env python3
# Device-side splice-SCAN: for each offset in [lo,hi), zero one byte of rtk.bin _agc.main,
# run rtsplice with the real AS, print a compact per-ray-t line. Baseline: 3,3,3,3,3,-1.
import sys, os, subprocess, importlib.util, re
HERE=os.path.expanduser("~/cleanroom_work/EXP-M5-19")
PARSE=os.path.expanduser("~/cleanroom_work/tools/shdump/agxparse.py")
spec=importlib.util.spec_from_file_location("agxparse", PARSE)
ap=importlib.util.module_from_spec(spec); spec.loader.exec_module(ap)
with open(os.path.join(HERE,"rtk.bin"),"rb") as f: PRIST=bytes(f.read())
loc=ap.locate_region(PRIST,"_agc.main"); base,length=loc

def run_splice(off, val):
    buf=bytearray(PRIST)
    ao=base+off; old=buf[ao]; buf[ao]=val
    outp=os.path.join(HERE,"rtk_scan.bin")
    with open(outp,"wb") as f: f.write(buf)
    try:
        r=subprocess.run(["./rtsplice","--archive","rtk_scan.bin","--source","rtk.metal","--function","rtk"],
                         cwd=HERE, capture_output=True, text=True, timeout=20)
    except subprocess.TimeoutExpired:
        return old, "HANG"
    ts=[]
    for line in r.stdout.splitlines():
        m=re.search(r"-> t=(-?\d+\.\d+)", line)
        if m: ts.append(f"{float(m.group(1)):g}")
    ok = "OK" if "STATUS OK" in r.stdout else ("MISS" if "PIPELINE_MISS" in r.stdout else "?")
    return old, (",".join(ts) if ts else ok)

lo=int(sys.argv[1],0); hi=int(sys.argv[2],0)
val=int(sys.argv[3],0) if len(sys.argv)>3 else 0x00
print(f"# baseline = 3,3,3,3,3,-1 ; scan [{lo:#x},{hi:#x}) setting byte={val:#04x}")
for off in range(lo,hi):
    old,res=run_splice(off,val)
    flag="" if res=="3,3,3,3,3,-1" else "   <-- DELTA"
    print(f"  @{off:#06x} ({old:#04x}->{val:#04x}): {res}{flag}")
