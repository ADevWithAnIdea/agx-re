#!/usr/bin/env python3
# mem_probe.py -- EXP-0012 memory-family HW validation (splice-and-observe on the
# real A18 Pro GPU). Runs ON DEVICE via the persistent runner. Reuses IntProbe
# (EXP-0007). CLEAN-ROOM: only OUR OWN compiled shader bytes are spliced/executed.
import os, sys, struct, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
def lm(n,p):
    s=importlib.util.spec_from_file_location(n,p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
IntProbe = lm("intprobe", os.path.join(HERE,"intprobe.py")).IntProbe

def banner(t): print("\n"+"="*74+"\n"+t+"\n"+"="*74)
def hx(v): return [f"0x{x&0xffffffff:08x}" for x in v]

def find_mem(main):
    """[(kind,off,bytes14)] for plausible 0x67/0xe7 mem ops (byte0 in{67,e7}, +13==0)."""
    out=[]; n=len(main)
    i=0
    # structural walk that respects 14B mem ops but tolerates unknown ALU in between
    while i < n-13:
        if main[i] in (0x67,0xe7) and main[i+13]==0x00:
            out.append(("LD" if main[i]==0x67 else "ST", i, bytes(main[i:i+14])))
            i+=14; continue
        i+=1
    return out

def M1_offset(pr):
    banner("M1  offset via prior ALU (element addressing), load has no offset field  [off1: a[gid+1]]")
    p=IntProbe(os.path.join(HERE,"kernels/off1.metal"),function="k",fast_math=False,
               workdir=os.path.join(HERE,"work"),shdump=os.path.join(HERE,"shdump"),
               agxparse=os.path.join(HERE,"agxparse.py"),agxrun_persist=os.path.join(HERE,"agxrun_persist"),
               persistrun=os.path.join(HERE,"persistrun.py"))
    m=p.main; print("  main:",m.hex())
    a=[i*10 for i in range(16)]   # [0,10,20,...,150]
    b=p.run({},ins={1:a},outs={0:8},grid=8,tg=8)
    print(f"  a={a}")
    print(f"  baseline out (expect a[1..8]=[10..80]) = {b.get(0)} [{b['_status']}]")
    # op9f iadd at main[4], imm=(K<<1) at instr byte+5 = main[9]
    print(f"  op9f iadd bytes main[4:14]={m[4:14].hex()}  imm(main[9])={m[9]:#04x} (=1<<1 for +1)")
    for kval,label in [(0x00,"k=0 -> a[gid]"),(0x02,"k=1 (orig)"),(0x04,"k=2"),(0x08,"k=4")]:
        r=p.run({9:kval},ins={1:a},outs={0:8},grid=8,tg=8)
        print(f"  splice main[9]={kval:#04x} ({label:14s}) -> {r.get(0)} [{r['_status']}]")
    p.close()

def M2_size(pr):
    banner("M2  access-size field (device load +12)  [copy1: out=a[gid], vary load size]")
    p=IntProbe(os.path.join(HERE,"kernels/copy1.metal"),function="k",fast_math=False,
               workdir=os.path.join(HERE,"work"),shdump=os.path.join(HERE,"shdump"),
               agxparse=os.path.join(HERE,"agxparse.py"),agxrun_persist=os.path.join(HERE,"agxrun_persist"),
               persistrun=os.path.join(HERE,"persistrun.py"))
    m=p.main
    mem=find_mem(m); ld=[x for x in mem if x[0]=="LD"][0]
    lo=ld[1]; print(f"  device_load at main[{lo}] = {m[lo:lo+14].hex()}  (+12=main[{lo+12}]={m[lo+12]:#04x}, +8={m[lo+8]:#04x})")
    a=[0x11223301+i for i in range(8)]  # low byte = 0x01..0x08, high bytes tag
    b=p.run({},ins={1:('u',a)},outs={0:8},grid=8,tg=8,signed=False)
    print(f"  a(hex)={hx(a)}")
    print(f"  baseline (32-bit) out = {hx(b.get(0))} [{b['_status']}]")
    for newsz,label in [(0x42,"8-bit"),(0x44,"16-bit"),(0x48,"64-bit")]:
        r=p.run({lo+12:newsz},ins={1:('u',a)},outs={0:8},grid=8,tg=8,signed=False)
        print(f"  splice +12 {m[lo+12]:#04x}->{newsz:#04x} ({label:6s}) -> {hx(r.get(0))} [{r['_status']}]")
    # also try splicing +8 together for 8-bit (copy1->ld_char had +8 51->61,+12 46->42)
    for over,label in [({lo+8:0x61,lo+12:0x42},"+8=61,+12=42 (full ld_char form)")]:
        r=p.run(over,ins={1:('u',a)},outs={0:8},grid=8,tg=8,signed=False)
        print(f"  splice {label:28s} -> {hx(r.get(0))} [{r['_status']}]")
    p.close()

def M3_sign(pr):
    banner("M3  sign vs zero extension (sub-32 loads)  [ld_char vs ld_uchar, byte 0xff etc]")
    chbytes=bytes([0x01,0x02,0x7f,0x80,0x81,0xfe,0xff,0x00])
    for kern,exp in [("ld_char","signed: [1,2,127,-128,-127,-2,-1,0]"),
                     ("ld_uchar","unsigned: [1,2,127,128,129,254,255,0]")]:
        p=IntProbe(os.path.join(HERE,f"kernels/{kern}.metal"),function="k",fast_math=False,
                   workdir=os.path.join(HERE,"work"),shdump=os.path.join(HERE,"shdump"),
                   agxparse=os.path.join(HERE,"agxparse.py"),agxrun_persist=os.path.join(HERE,"agxrun_persist"),
                   persistrun=os.path.join(HERE,"persistrun.py"))
        m=p.main; mem=find_mem(m); ld=[x for x in mem if x[0]=="LD"][0]; lo=ld[1]
        b=p.run({},ins={1:chbytes},outs={0:8},grid=8,tg=8,signed=True)
        print(f"  [{kern}] load={m[lo:lo+14].hex()} (+3={m[lo+3]:#04x},+5={m[lo+5]:#04x})")
        print(f"     out = {b.get(0)}   (expect {exp}) [{b['_status']}]")
        # splice the extend flag: on uchar set +3 0x02->0x00 & +5 0x00->0x01 (look signed);
        # on char set +3 0x00->0x02 & +5 0x01->0x00 (look unsigned)
        if kern=="ld_uchar":
            r=p.run({lo+3:0x00,lo+5:0x01},ins={1:chbytes},outs={0:8},grid=8,tg=8,signed=True)
            print(f"     splice +3->0x00,+5->0x01 (signed form) -> {r.get(0)} [{r['_status']}]")
        p.close()

def M4_vec(pr):
    banner("M4  vector width / component count (device load & store +5)  [vec4i: int4 copy]")
    p=IntProbe(os.path.join(HERE,"kernels/vec4i.metal"),function="k",fast_math=False,
               workdir=os.path.join(HERE,"work"),shdump=os.path.join(HERE,"shdump"),
               agxparse=os.path.join(HERE,"agxparse.py"),agxrun_persist=os.path.join(HERE,"agxrun_persist"),
               persistrun=os.path.join(HERE,"persistrun.py"))
    m=p.main; mem=find_mem(m); ld=[x for x in mem if x[0]=="LD"][0]; st=[x for x in mem if x[0]=="ST"][0]
    lo,so=ld[1],st[1]
    print(f"  ONE load moves 4 comps: load={m[lo:lo+14].hex()} (+5={m[lo+5]:#04x}=count)  store +5={m[so+5]:#04x}")
    a=list(range(1,33))  # 8 int4 = 32 ints
    b=p.run({},ins={1:a},outs={0:32},grid=8,tg=8)
    print(f"  baseline out (full copy 1..32) = {b.get(0)} [{b['_status']}]")
    # splice load count 4->1
    r=p.run({lo+5:0x01},ins={1:a},outs={0:32},grid=8,tg=8)
    print(f"  splice load +5 0x04->0x01 (count1) -> {r.get(0)} [{r['_status']}]")
    # splice store count 4->1
    r=p.run({so+5:0x01},ins={1:a},outs={0:32},grid=8,tg=8)
    print(f"  splice store +5 0x04->0x01 (count1) -> {r.get(0)} [{r['_status']}]")
    # splice load count 4->2
    r=p.run({lo+5:0x02},ins={1:a},outs={0:32},grid=8,tg=8)
    print(f"  splice load +5 0x04->0x02 (count2) -> {r.get(0)} [{r['_status']}]")
    p.close()

def M5_tg(pr):
    banner("M5  threadgroup memory roundtrip + byte+1=0x02 flag  [tg_copy identity, tg_rot8 rotate]")
    for kern,desc in [("tg_copy","out[gid]=tile[lid]; tile[lid]=a[gid]  (identity)"),
                      ("tg_rot8","out[gid]=tile[(lid+1)&7]  (rotate by 1)")]:
        p=IntProbe(os.path.join(HERE,f"kernels/{kern}.metal"),function="k",fast_math=False,
                   workdir=os.path.join(HERE,"work"),shdump=os.path.join(HERE,"shdump"),
                   agxparse=os.path.join(HERE,"agxparse.py"),agxrun_persist=os.path.join(HERE,"agxrun_persist"),
                   persistrun=os.path.join(HERE,"persistrun.py"))
        m=p.main; mem=find_mem(m)
        a=[10*(i+1) for i in range(8)]
        b=p.run({},ins={1:a},outs={0:8},grid=8,tg=8)
        print(f"\n  [{kern}] {desc}")
        for kind,off,bb in mem:
            asf="TG" if bb[1]==0x02 else "dev"
            print(f"     [{off:3d}] {kind} b1={bb[1]:#04x}[{asf}] +4={bb[4]:#04x}  {bb.hex()}")
        print(f"     a={a}")
        print(f"     baseline out = {b.get(0)} [{b['_status']}]")
        # find the threadgroup store & load (byte+1==0x02) and splice byte+1 -> 0x00
        tgst=[x for x in mem if x[0]=="ST" and x[2][1]==0x02]
        tgld=[x for x in mem if x[0]=="LD" and x[2][1]==0x02]
        if tgst:
            so=tgst[0][1]
            r=p.run({so+1:0x00},ins={1:a},outs={0:8},grid=8,tg=8)
            print(f"     splice TG-store +1 0x02->0x00 (make device) -> {r.get(0)} [{r['_status']}]")
        if tgld:
            lo=tgld[0][1]
            r=p.run({lo+1:0x00},ins={1:a},outs={0:8},grid=8,tg=8)
            print(f"     splice TG-load  +1 0x02->0x00 (make device) -> {r.get(0)} [{r['_status']}]")
        p.close()

def M6_const(pr):
    banner("M6  constant-address-space read encoding  [const_copy: constant int* a]")
    p=IntProbe(os.path.join(HERE,"kernels/const_copy.metal"),function="k",fast_math=False,
               workdir=os.path.join(HERE,"work"),shdump=os.path.join(HERE,"shdump"),
               agxparse=os.path.join(HERE,"agxparse.py"),agxrun_persist=os.path.join(HERE,"agxrun_persist"),
               persistrun=os.path.join(HERE,"persistrun.py"))
    m=p.main; mem=find_mem(m); ld=[x for x in mem if x[0]=="LD"][0]
    a=[10*(i+1) for i in range(8)]
    b=p.run({},ins={1:a},outs={0:8},grid=8,tg=8)
    print(f"  constant* load = {m[ld[1]:ld[1]+14].hex()}  (== device copy1 load? see analysis)")
    print(f"  a={a}")
    print(f"  baseline out = {b.get(0)} (expect a) [{b['_status']}]")
    # splice base_slot +4 0x01->0x00 to prove it selects the bound buffer (like device)
    lo=ld[1]
    r=p.run({lo+4:0x00},ins={1:a},outs={0:8},grid=8,tg=8)
    print(f"  splice load base_slot +4 0x01->0x00 -> {r.get(0)} [{r['_status']}] (0=out buf, expect zeros)")
    p.close()

FUNCS={"M1":M1_offset,"M2":M2_size,"M3":M3_sign,"M4":M4_vec,"M5":M5_tg,"M6":M6_const}
if __name__=="__main__":
    which=sys.argv[1:] or ["M1","M2","M3","M4","M5","M6"]
    for nm in which:
        try: FUNCS[nm](None)
        except Exception as e:
            import traceback; print(f"{nm} EXC:"); traceback.print_exc()
