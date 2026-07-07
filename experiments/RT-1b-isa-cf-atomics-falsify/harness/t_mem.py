#!/usr/bin/env python3
# RT-1b item 1: INDEPENDENT re-proof of memory-op fields (byte+5 index, byte+6
# inert, byte+1 space, immediate offset), + edge cases. Different harness
# (one-shot rt1b_run) + different ramp/indices than RT-1a.
import rt1b, struct, sys

BASE = 0xA000
NA = 256
def a_index(v):
    if BASE <= v < BASE + NA: return v - BASE
    return None
A = rt1b.u32([BASE + j for j in range(NA)])
IDX = rt1b.u32([41, 7, 83, 19])          # gid=0 -> idx[0..3]; primes != RT-1a
BANK_INS = {2: A, 3: IDX}                 # bank: out(0) out2(1) a(2) idx(3)
BANK_OUTS = {0: 4, 1: 4}

def loads(h):
    return [t for t in h.tokens() if t["byte0"] == 0x67]

def sweep_byte(h, load_off, bpos, values, ins, outs=BANK_OUTS, label=""):
    print(f"  -- sweep byte+{bpos} of load@+0x{load_off:x} {label}")
    rows = []
    for v in values:
        r = h.run(splices=[(load_off + bpos, bytes([v]))], grid=1, tg=1, ins=ins, outs=outs, timeout=15)
        if r["status"] != "OK":
            print(f"     0x{v:02x} -> {r['status']} {r.get('error','')}")
            rows.append((v, r["status"], None)); continue
        o0 = rt1b.du32(r["outs"][0])[0]
        k = a_index(o0)
        note = f"a[{k}]" if k is not None else (f"raw<256={o0}" if o0 < 256 else f"0x{o0:x}")
        print(f"     0x{v:02x} -> o0={o0:<8d} {note}")
        rows.append((v, "OK", o0))
    return rows

print("### BANK kernel: identify the a[i0] load and prove byte+5 = index reg")
h = rt1b.Harness("kernels/mem.metal", "bank", workdir=".")
print("  main_len", h.main_len)
for t in loads(h):
    print(f"    load @+0x{t['off']:x}: {t['hex']}")
ins = BANK_INS
# baseline
rb = h.run(grid=1, tg=1, ins=ins, outs=BANK_OUTS)
print("  baseline out0 =", rt1b.du32(rb["outs"][0])[0], "expect a[41]=", BASE+41)

# find the a[i0] load: the 0x67 load whose byte+5 sweep produces a[k] values
aload = None
for t in loads(h):
    r0 = h.run(splices=[(t["off"]+5, bytes([0x00]))], grid=1, tg=1, ins=ins, outs=BANK_OUTS)
    r1 = h.run(splices=[(t["off"]+5, bytes([0x01]))], grid=1, tg=1, ins=ins, outs=BANK_OUTS)
    if r0["status"]=="OK" and r1["status"]=="OK":
        v0 = rt1b.du32(r0["outs"][0])[0]; v1 = rt1b.du32(r1["outs"][0])[0]
        if a_index(v0) is not None and a_index(v1) is not None and v0!=v1:
            aload = t["off"]
            print(f"  => a[i0] load @+0x{aload:x}  (byte+5=0->a[{a_index(v0)}], =1->a[{a_index(v1)}])")
            break
if aload is None:
    print("  !! could not identify a-load; dumping first load sweeps")
    aload = loads(h)[0]["off"]

print("\n[byte+5 = INDEX REGISTER]")
sweep_byte(h, aload, 5, [0,1,2,3,4,0x80,0x81,0x82,0x83], ins, label="(expect r0..r3 = i0..i3 = a[41/7/83/19])")
print("\n[byte+6 = INERT]")
sweep_byte(h, aload, 6, [0x00,0x01,0x02,0x10,0x20,0x40,0x80,0xff], ins, label="(expect constant = a[41])")
print("\n[byte+1 = ADDRESS SPACE]")
sweep_byte(h, aload, 1, [0x00,0x01,0x02,0x03,0x04], ins, label="(expect 0x02 -> tg/uninit = 0)")

print("\n### ONE kernel: immediate index-offset field (byte+9 bit7 / +10 / +11)")
h1 = rt1b.Harness("kernels/mem.metal", "one", workdir=".")
ld = [t for t in h1.tokens() if t["byte0"]==0x67][0]["off"]
print(f"  a[i0] load @+0x{ld:x}: {[t['hex'] for t in h1.tokens() if t['byte0']==0x67][0]}")
IDX1 = rt1b.u32([41,0,0,0])
rb = h1.run(grid=1, tg=1, ins={1:A,2:IDX1}, outs={0:4})
print("  baseline out0 =", a_index(rt1b.du32(rb['outs'][0])[0]))
orig = h1.base[h1.main_off+ld+9], h1.base[h1.main_off+ld+10], h1.base[h1.main_off+ld+11]
print(f"  orig byte+9/+10/+11 = {orig[0]:#x}/{orig[1]:#x}/{orig[2]:#x}")
def off_sweep(bpos, values):
    print(f"  -- byte+{bpos}")
    for v in values:
        r = h1.run(splices=[(ld+bpos, bytes([v]))], grid=1, tg=1, ins={1:A,2:IDX1}, outs={0:4}, timeout=15)
        if r["status"]!="OK": print(f"     0x{v:02x} -> {r['status']}"); continue
        o=rt1b.du32(r["outs"][0])[0]; k=a_index(o)
        print(f"     0x{v:02x} -> a[{k}]  (delta {k-41 if k is not None else '?'})")
off_sweep(9, [orig[0], orig[0]|0x80])
off_sweep(10,[orig[1], orig[1]+1, orig[1]+2, orig[1]+4, orig[1]+8])
off_sweep(11,[orig[2], orig[2]+1, orig[2]+2])

print("\n### compiler-computed a[gid+1] vs a[gid-1]: offset in prior ALU, load identical?")
hp = rt1b.Harness("kernels/mem.metal", "plus1", workdir=".")
hm = rt1b.Harness("kernels/mem.metal", "minus1", workdir=".")
lp = [t for t in hp.tokens() if t["byte0"]==0x67]
lm = [t for t in hm.tokens() if t["byte0"]==0x67]
print("  plus1 loads :", [t["hex"] for t in lp])
print("  minus1 loads:", [t["hex"] for t in lm])
# semantics
AR = rt1b.i32(list(range(100,110)))
rp = hp.run(grid=8, tg=8, ins={1:AR}, outs={0:32})
rm = hm.run(grid=8, tg=8, ins={1:AR}, outs={0:32})
print("  a[gid+1] out:", rt1b.di32(rp["outs"][0]))
print("  a[gid-1] out:", rt1b.di32(rm["outs"][0]))
