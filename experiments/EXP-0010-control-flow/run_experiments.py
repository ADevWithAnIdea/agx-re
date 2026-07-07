#!/usr/bin/env python3
# run_experiments.py -- EXP-0010 HW validations (runs ON DEVICE via persistent
# runner). E1 preamble=get_sr(gid); E2 branch/predicate (compare immediate,
# which-path); E3 branchless select; E4 termination; E5 constant_program /
# buffer-base; E6 backward loop jump offset. CLEAN-ROOM: our own bytes only.
import os, sys, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
def lm(n,p):
    s=importlib.util.spec_from_file_location(n,p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
C = lm("cf_probe", os.path.join(HERE,"cf_probe.py"))
IntProbe = C.IntProbe

def banner(t): print("\n"+"="*72+"\n"+t+"\n"+"="*72)

def E1():
    banner("E1  preamble = get_sr(thread_position_in_grid)   [gidonly out=gid]")
    p = IntProbe("kernels/gidonly.metal", function="k", fast_math=False)
    print("main:", p.main.hex())
    b = p.run({}, ins={}, outs={0:8}, grid=8, tg=8)
    print(f"  baseline out[0..7] = {b.get(0)}  [{b['_status']}]")
    for off in (0,1,2,3):
        for val in (0x00,0xff):
            r = p.run({off:val}, ins={}, outs={0:8}, grid=8, tg=8)
            print(f"  splice main[{off}]={val:#04x} -> {r.get(0)}  [{r['_status']}]")
    for val in (0x1c,0x2c,0x3c):
        r = p.run({0:val}, ins={}, outs={0:8}, grid=8, tg=8)
        print(f"  splice main[0]={val:#04x} (byte0 hi-nibble) -> {r.get(0)}  [{r['_status']}]")
    p.close()

def E2():
    banner("E2  branch/predicate  [eret4: if(gid>=4) return; out[gid]=7]")
    p = IntProbe("kernels/eret4.metal", function="k", fast_math=False)
    print("main:", p.main.hex())
    print("  compare instr at main[4:10], threshold immediate at main[7] (=0x82 for >=4)")
    b = p.run({}, ins={}, outs={0:8}, grid=8, tg=8)
    print(f"  baseline out[0..7] = {b.get(0)}  (0=lane returned, 7=lane stored)  [{b['_status']}]")
    for val,label in [(0x80,"thr2"),(0x84,"thr6"),(0x8e,"thr14/all"),(0x00,"thr0/none")]:
        r = p.run({7:val}, ins={}, outs={0:8}, grid=8, tg=8)
        print(f"  splice main[7]={val:#04x} ({label}) -> {r.get(0)}  [{r['_status']}]")
    # try to find a condition-sense bit: sweep bytes 4,5,8,9 of the 0a compare
    print("  -- sense/opcode byte sweep (looking for inversion: 0-3 store, 4-7 return) --")
    for off in (4,5,8,9):
        for val in (0x00,0x01,0x02,0x10,0x20,0x40,0x80):
            r = p.run({off:val}, ins={}, outs={0:8}, grid=8, tg=8)
            o=r.get(0)
            note=""
            if o==[0,0,0,0,7,7,7,7]: note="  <== INVERTED!"
            if o and o!=[7,7,7,7,0,0,0,0] and o!=[0,0,0,0,7,7,7,7] and r['_status']=="OK": note=note or "  (other)"
            print(f"    main[{off}]={val:#04x} -> {o} [{r['_status']}]{note}")
    p.close()

def E3():
    banner("E3  branchless select  [dsel5: out=(a>5)?100:200]")
    p = IntProbe("kernels/dsel5.metal", function="k", fast_math=False)
    print("main:", p.main.hex())
    a=[0,6,3,9,5,7,2,8]
    print("  compare (byte0 0x02) at main[18:24], immediate at main[21] (=0x84 for >5)")
    b = p.run({}, ins={1:a}, outs={0:8}, grid=8, tg=8)
    print(f"  a={a}")
    print(f"  baseline out = {b.get(0)}  (expect 100 if a>5 else 200)  [{b['_status']}]")
    for val,label in [(0x80,"a>1"),(0x8e,"a>7"),(0x00,"a>?")]:
        r = p.run({21:val}, ins={1:a}, outs={0:8}, grid=8, tg=8)
        print(f"  splice cmp-imm main[21]={val:#04x} ({label}) -> {r.get(0)}  [{r['_status']}]")
    p.close()

def E4():
    banner("E4  program termination  [copy1: out=a]")
    p = IntProbe("kernels/copy1.metal", function="k", fast_math=False)
    m=p.main; print("main:", m.hex(), " len", len(m))
    a=[11,22,33,44,55,66,77,88]
    b = p.run({}, ins={1:a}, outs={0:8}, grid=8, tg=8)
    print(f"  baseline out = {b.get(0)}  [{b['_status']}]")
    stop_off = len(m)-4
    print(f"  trailing stop 0e000000 at main[{stop_off}]")
    for over,label in [
        ({stop_off:0x00},"stop b0 0x0e->0x00"),
        ({stop_off:0xff},"stop b0 0x0e->0xff"),
        ({stop_off:0x67},"stop b0->0x67(load-op)"),
        ({stop_off+1:0xff,stop_off+2:0xff,stop_off+3:0xff},"stop payload->ff"),
    ]:
        r = p.run(over, ins={1:a}, outs={0:8}, grid=8, tg=8)
        ok = r.get(0)==a
        print(f"  splice {label:26s} -> {r.get(0)} match={ok} [{r['_status']}]")
    # corrupt a byte INSIDE the store to see if the store is what 'ends' work
    store_off = 4+14  # preamble(4)+load(14)
    print(f"  store instr at main[{store_off}:{store_off+14}] = {m[store_off:store_off+14].hex()}")
    for off in range(store_off, store_off+14):
        r = p.run({off:(m[off]^0x01)}, ins={1:a}, outs={0:8}, grid=8, tg=8)
        if r.get(0)!=a or r['_status']!="OK":
            print(f"  store bit-flip main[{off}]^1 ({m[off]:#04x}->{m[off]^1:#04x}) -> {r.get(0)} [{r['_status']}]")
    p.close()

def E5():
    banner("E5  constant_program / buffer base  [copy1]")
    p = IntProbe("kernels/copy1.metal", function="k", fast_math=False)
    loc = C.region(p, "_agc.main.constant_program")
    cp = C.hexdump_region(p, "_agc.main.constant_program")
    print(f"  const_program region abs_off={loc[0]} len={loc[1]}")
    print(f"  const_program bytes: {cp.hex()}")
    a=[11,22,33,44,55,66,77,88]
    b = p.run({}, ins={1:a}, outs={0:8}, grid=8, tg=8)
    print(f"  baseline out = {b.get(0)}  [{b['_status']}]")
    cpoff = loc[0]
    # splice the '0300070002000000 6000' prefix (present iff a device load exists)
    for over,label in [
        ({cpoff:0x00},"cp[0] 0x03->0x00"),
        ({cpoff+8:0x00},"cp[8] 0x60->0x00"),
        ({cpoff:0x0e,cpoff+1:0x00,cpoff+2:0x00,cpoff+3:0x00},"cp[0:4]->0e000000 (no-load variant head)"),
    ]:
        r = C.run_abs(p, over, ins={1:a}, outs={0:8}, grid=8, tg=8)
        print(f"  splice {label:34s} -> {r.get(0)} match={r.get(0)==a} [{r['_status']}]")
    p.close()

def E6():
    banner("E6  backward loop jump  [prodloop: s=1; for i<n: s=s*3+1; out=s]")
    p = IntProbe("kernels/prodloop.metal", function="k", fast_math=False)
    m=p.main; print("main:", m.hex())
    # locate the backward jump: 0f 00 54 <6-byte signed offset with high ff>
    j=-1
    for i in range(len(m)-9):
        if m[i]==0x0f and m[i+1]==0x00 and m[i+2]==0x54 and m[i+8]==0xff and m[i+7]==0xff:
            j=i; break
    a=[0,1,2,3,4,5,6,7]
    b = p.run({}, ins={1:a}, outs={0:8}, grid=8, tg=8)
    print(f"  a={a}")
    print(f"  baseline out = {b.get(0)}  (expect [1,4,13,40,121,364,1093,3280])  [{b['_status']}]")
    if j<0:
        print("  jump pattern 0f0054..ff not found"); p.close(); return
    off_field = m[j+3:j+9]
    signed = int.from_bytes(off_field,"little")
    if signed >= (1<<47): signed -= (1<<48)
    print(f"  backward jump at main[{j}] = {m[j:j+10].hex()}  offset_field={off_field.hex()} (signed {signed})")
    # neutralise: zero the offset (jump-to-self -> expect hang/fault OR broken loop)
    r = p.run({j+3:0x00,j+4:0x00,j+5:0x00,j+6:0x00,j+7:0x00,j+8:0x00}, ins={1:a}, outs={0:8}, grid=8, tg=8, timeout=6.0)
    print(f"  splice offset->0 (jump to self) -> {r.get(0)}  [{r['_status']}]")
    # make offset small-positive (forward, exit loop after ~1 pass)
    r = p.run({j+3:0x08,j+4:0x00,j+5:0x00,j+6:0x00,j+7:0x00,j+8:0x00}, ins={1:a}, outs={0:8}, grid=8, tg=8, timeout=6.0)
    print(f"  splice offset->+8 (forward) -> {r.get(0)}  [{r['_status']}]")
    # halve the backward distance
    newoff = (signed//2)
    ob = (newoff & ((1<<48)-1)).to_bytes(6,"little")
    ov = {j+3+k: ob[k] for k in range(6)}
    r = p.run(ov, ins={1:a}, outs={0:8}, grid=8, tg=8, timeout=6.0)
    print(f"  splice offset->{newoff} (half) -> {r.get(0)}  [{r['_status']}]")
    p.close()

if __name__ == "__main__":
    which = sys.argv[1:] or ["E1","E2","E3","E4","E5","E6"]
    for name in which:
        try: globals()[name]()
        except Exception as e:
            import traceback; print(f"{name} EXCEPTION:"); traceback.print_exc()
