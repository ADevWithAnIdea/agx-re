#!/usr/bin/env python3
# RT-7 Task 1b: does register index r95/r96/r97+ ALIAS or FAULT?
# Method: a gather kernel that keeps K distinct KNOWN values live in K physical
# GPRs, then reads one back by splicing a load's index-register field (byte+5,
# the RT-1a-validated GPR-index selector). a[] is a ramp so out = content(reg).
#   idx_k = b[gid]*1000 + k  (distinct, decodable: k=content%1000)
# All idx_k kept live to the end by a trailing sum, forcing ~K physical regs.
# Splicing load[0].byte+5 = R makes out[0] = a[content(phys reg R)] = content(R).
# CLEAN-ROOM: OWN-SHADER + HW-PROBE.
import os, sys, subprocess, struct, importlib.util, shutil
HERE=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("ap",os.path.join(HERE,"agxparse.py")); ap=importlib.util.module_from_spec(spec); spec.loader.exec_module(ap)

K=int(os.environ.get("K","94"))

def kernel_src(K):
    L=["#include <metal_stdlib>","using namespace metal;",
       "kernel void k(device uint* out [[buffer(0)]],",
       "              device const uint* a [[buffer(1)]],",   # ramp a[i]=i
       "              device const uint* b [[buffer(2)]],",   # b[gid] base
       "              uint gid [[thread_position_in_grid]]) {"]
    for k in range(K): L.append("  uint i%d = b[gid]*1000u + %du;"%(k,k))
    for k in range(K): L.append("  uint v%d = a[i%d];"%(k,k))
    # trailing sum forces every i_k AND v_k live across the whole body
    L.append("  uint s = 0u;")
    for k in range(K): L.append("  s += i%d + v%d;"%(k,k))
    for k in range(K): L.append("  out[gid*%d+%d] = v%d;"%(K,k,k))
    L.append("  out[gid*%d+%d] = s;"%(K,K))
    L.append("}")
    return "\n".join(L)+"\n"

def build(K):
    src=kernel_src(K); kp=os.path.join(HERE,"kernels","gather%d.metal"%K)
    open(kp,"w").write(src)
    arch=os.path.join(HERE,"gather_%d.bin"%K)
    r=subprocess.run([os.path.join(HERE,"shdump"),"-o",arch,"-f","k","--no-fast-math",kp],capture_output=True,text=True)
    return kp,arch,r.stderr

if __name__=="__main__":
    kp,arch,err=build(K)
    if not os.path.exists(arch): print("COMPILE_FAIL",err[-300:]); sys.exit(1)
    buf=open(arch,"rb").read()
    _,pieces=ap.extract_agx(buf); main=pieces["_agc.main"]
    print("MAIN_LEN",len(main))
    # find 0x67 loads and print byte+1..+5 context
    loc=subprocess.run(["python3",os.path.join(HERE,"agxparse.py"),arch,"--stage","compute","--locate","_agc.main"],capture_output=True,text=True).stdout.strip()
    print("LOCATE",loc)
    i=0; n=len(main); loads=[]
    while i+14<=n:
        if main[i] in (0x67,0xe7):
            b=main[i:i+14]
            loads.append((i,main[i],b[4],b[5],b.hex()))
            i+=14
        else: i+=2
    print("num_memops",len(loads))
    for off,op,slot,idx,hx in loads[:12]:
        print("  memop off=%d op=0x%02x base_slot=%d idx_reg_byte5=0x%02x  %s"%(off,op,slot,idx,hx))
