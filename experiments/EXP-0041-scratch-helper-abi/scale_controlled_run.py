#!/usr/bin/env python3
"""Equal-allocation high-occupancy control for EXP-0041's scratch sweep."""
import argparse, os, shutil, subprocess, time
from pathlib import Path
HERE=Path(__file__).resolve().parent; H=HERE/"harness"; K=HERE/"kernels"
CASES=[("nospill_k72_g65536_t32_alloc160",72,32),("spill_k160_g65536_t32_alloc160",160,32),
       ("spill_k160_g65536_t256_alloc160",160,256)]
def run(cmd,path,timeout,env=None):
    start=time.time()
    try: cp=subprocess.run([str(x) for x in cmd],capture_output=True,text=True,timeout=timeout,env=env)
    except subprocess.TimeoutExpired as e:
        path.write_text(f"COMMAND {cmd!r}\nTIMEOUT {timeout}\nSTDOUT\n{e.stdout or ''}\nSTDERR\n{e.stderr or ''}");raise
    path.write_text(f"COMMAND {cmd!r}\nEXIT {cp.returncode}\nSECONDS {time.time()-start:.3f}\nSTDOUT\n{cp.stdout}\nSTDERR\n{cp.stderr}")
    if cp.returncode:raise SystemExit(f"failed: {path}")
def main():
    p=argparse.ArgumentParser();p.add_argument("--run-id",required=True);o=p.parse_args();raw=HERE/"raw"/o.run_id;raw.mkdir(parents=True,exist_ok=False);work=HERE/"work"/o.run_id;work.mkdir(parents=True,exist_ok=False)
    mt=work/"maptrace.dylib";probe=work/"probe"
    run(["clang","-dynamiclib","-o",mt,H/"maptrace.c","-framework","IOKit","-framework","CoreFoundation"],raw/"build_maptrace.log",30)
    run(["clang","-fobjc-arc","-framework","Metal","-framework","Foundation","-o",probe,H/"probe.m"],raw/"build_probe.log",30)
    for name,k,tg in CASES:
        env=os.environ.copy();env.update({"DYLD_INSERT_LIBRARIES":str(mt),"MAPTRACE_LOG":str(raw/f"map_{name}.log"),"MAPTRACE_DUMP_DIR":str(raw/"unused"),"MAPTRACE_DUMP_GPU_VAS":""})
        source=K/f"cs_{'nospill_k72' if k==72 else 'spill_k160'}.metal"
        run([probe,"--stage","cs","--source",source,"--k",k,"--alloc-k",160,"--grid",65536,"--tg",tg],raw/f"run_{name}.log",90,env)
    shutil.rmtree(work);print(raw)
if __name__=="__main__":main()
