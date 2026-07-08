#!/usr/bin/env python3
# EXP-M4-11 item 4a: >96-live kernels spill to scratch and STILL compute correctly.
# Reuse copy96's self-n copy kernel at high K (heavy spill); exact copy => spill correct.
import os, subprocess, importlib.util
HERE=os.path.dirname(os.path.abspath(__file__)); H=os.path.join(HERE,"harness")
ROOT="/Users/user/cleanroom_gpu"; AGXTEST=os.path.join(ROOT,"tools/agxtest/agxtest.py")
spec=importlib.util.spec_from_file_location("cp",os.path.join(HERE,"copy96.py")); cp=importlib.util.module_from_spec(spec); spec.loader.exec_module(cp)
for K in [112,128,160,200,256]:
    kp=os.path.join(HERE,"kernels","cp%d.metal"%K); open(kp,"w").write(cp.src(K))
    f0,scr=cp.footprint(kp)
    invals=[float(1000+i) for i in range(K)]
    cmd=["python3",AGXTEST,"--source",kp,"--function","k","--grid","1","--tg","1",
         "--buf","1="+",".join("%g"%v for v in invals),"--out","0=%d"%K,"--run-timeout","25"]
    r=subprocess.run(cmd,capture_output=True,text=True); st=res=None
    for line in r.stdout.splitlines():
        if line.startswith("STATUS"): st=line.split()[1]
        if line.startswith("RESULT"): res=[round(float(x)) for x in line.split()[2:]]
    ok=res==[int(v) for v in invals]
    print("K=%-3d f0=%-3d scratch=%-5d STATUS=%-10s spill_copy_exact=%s"%(K,f0,scr,st,ok))
