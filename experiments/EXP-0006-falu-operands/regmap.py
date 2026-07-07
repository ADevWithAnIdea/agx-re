#!/usr/bin/env python3
# regmap.py -- confirm the source-operand register encoding across several
# physical registers by sweeping srcB (b3) of map5's fadd. map5 loads 5 distinct
# buffer values into distinct registers; out = a + reg[idx]. Classifying (out-a)
# maps each index to the physical register / buffer, exposing reg=idx>>1 and the
# bit0 size select over multiple registers. CLEAN-ROOM: our own shader bytes.
import os, sys, importlib.util
HERE=os.path.dirname(os.path.abspath(__file__))
def load_mod(n,p):
    s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
probe=load_mod("probe",os.path.join(HERE,"probe.py"))
analyze=load_mod("analyze",os.path.join(HERE,"analyze.py"))

# distinct values per buffer (broadcast across 4 lanes)
VALS={0:100.0, 1:200.0, 2:300.0, 3:400.0, 4:500.0}   # a,b,c,d,e
def buf(v): return [v,v,v,v]

def main():
    p=probe.Probe("kernels/map5.metal")
    toks=analyze.structural_tokens(p.main)
    aluoff, alu=[ (t[1],t[3]) for t in toks if t[0]=="ALU"][0]
    print(f"# map5 ALU@{aluoff:#x}={alu.hex()}  srcA(b1)={alu[1]:#x} srcB(b3)={alu[3]:#x}")
    ins={i:buf(VALS[i]) for i in range(5)}
    # a is buffer0=100 -> out = 100 + reg[idx]
    known={100.0:"a(buf0)",200.0:"b(buf1)",300.0:"c(buf2)",400.0:"d(buf3)",500.0:"e(buf4)"}
    print("# out = a(100) + reg[idx];  idx bit0 = 32-bit(1)/16-bit(0)")
    out=open("raw/map5_srcB_sweep.log","w")
    for idx in range(0,0x100):
        r=p.run({aluoff+3:idx}, ins, {5:4}, grid=4)
        if r["_status"]!="OK":
            line=f"{idx:#04x} FAULT {r['_status']}"
        else:
            v=r.get(5,[0,0,0,0])[0]
            reg=idx>>1; sz="32" if idx&1 else "16"
            src=v-100.0
            tag=known.get(round(src,3), f"val={src:g}") if abs(v)>1e-9 else "zero/uninit"
            line=f"{idx:#04x}  reg{reg:<2d}/{sz}b  out0={v:g}  reg[idx]={src:g}  -> {tag}"
        print(line); out.write(line+"\n")
    out.close(); p.close()

if __name__=="__main__": main()
