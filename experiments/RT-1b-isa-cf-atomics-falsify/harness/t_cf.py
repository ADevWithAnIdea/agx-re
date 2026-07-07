#!/usr/bin/env python3
# RT-1b item 2: falsify predication / select / backward-jump / exec-mask.
import rt1b, struct

def pat(vals): return "".join("A" if v==100 else ("B" if v==200 else "?") for v in vals)

print("### thresh: out[gid] = gid<4 ? 100:200  (grid=8)")
h=rt1b.Harness("kernels/cf.metal","thresh",workdir=".")
cmp_off=h.find(byte0=0x02)                 # the 0x02 compare-feeds-select
sel_off=h.find(byte0=0x05)                 # psel
print("  cmp@+0x%x = %s   psel@+0x%x = %s"%(cmp_off, h.main[cmp_off:cmp_off+6].hex(),
      sel_off, h.main[sel_off:sel_off+4].hex()))
rb=h.run(grid=8,tg=8,outs={0:32})
base=rt1b.di32(rb["outs"][0]); print("  baseline:",base,"pat",pat(base))

# empirically LOCATE the threshold immediate: sweep each compare byte, watch boundary
print("  -- locate immediate (which byte moves the A/B boundary):")
for bpos in [1,2,3,4,5]:
    orig=h.main[cmp_off+bpos]
    line=[]
    for v in [orig, (orig+2)&0xff, (orig+4)&0xff, (orig-2)&0xff]:
        r=h.run(splices=[(cmp_off+bpos,bytes([v]))],grid=8,tg=8,outs={0:32},timeout=12)
        line.append("%#04x:%s"%(v, pat(rt1b.di32(r["outs"][0])) if r["status"]=="OK" else r["status"]))
    print("     byte+%d (orig %#04x): %s"%(bpos,orig," ".join(line)))

# invert: flip compare op 0x02 -> 0x0a
print("  -- invert: splice cmp byte0 0x02 -> 0x0a")
r=h.run(splices=[(cmp_off,bytes([0x0a]))],grid=8,tg=8,outs={0:32},timeout=12)
print("     0x0a ->", pat(rt1b.di32(r["outs"][0])) if r["status"]=="OK" else r["status"])
# select value splice: psel byte+3
print("  -- psel byte+3 (select constant) sweep:")
for v in [h.main[sel_off+3], 0x00, 0xfe]:
    r=h.run(splices=[(sel_off+3,bytes([v]))],grid=8,tg=8,outs={0:32},timeout=12)
    print("     %#04x ->"%v, rt1b.di32(r["outs"][0]) if r["status"]=="OK" else r["status"])

print("\n### ifdata: out = a[gid]>5 ? 100:200  (ramp a=0..7)")
h2=rt1b.Harness("kernels/cf.metal","ifdata",workdir=".")
cmp2=h2.find(byte0=0x02); sel2=h2.find(byte0=0x16)
print("  cmp@+0x%x=%s sel@+0x%x=%s"%(cmp2,h2.main[cmp2:cmp2+6].hex(),sel2,h2.main[sel2:sel2+4].hex()))
A=rt1b.i32(list(range(8)))
rb=h2.run(grid=8,tg=8,ins={1:A},outs={0:32}); print("  baseline:",rt1b.di32(rb["outs"][0]))
for bpos in [1,2,3,4,5]:
    orig=h2.main[cmp2+bpos]; line=[]
    for v in [orig,(orig+2)&0xff,(orig+4)&0xff]:
        r=h2.run(splices=[(cmp2+bpos,bytes([v]))],grid=8,tg=8,ins={1:A},outs={0:32},timeout=12)
        line.append("%#04x:%s"%(v,pat(rt1b.di32(r["outs"][0])) if r["status"]=="OK" else r["status"]))
    print("     byte+%d (orig %#04x): %s"%(bpos,orig," ".join(line)))

print("\n### backward jump: loopbig 0f 00 54 <off40>")
hl=rt1b.Harness("kernels/cf.metal","loopbig",workdir=".")
# locate 0f 00 54 back-edge
b=hl.main; je=None
for i in range(len(b)-2):
    if b[i]==0x0f and b[i+1]==0x00 and b[i+2]==0x54: je=i; break
print("  back-edge @+0x%x : %s"%(je, b[je:je+10].hex()))
off=int.from_bytes(b[je+3:je+8],"little")
if off & (1<<39): off -= (1<<40)
print("  off40 = %d (signed). instr@0x%x, target≈0x%x (instr+len+off)"%(off,je,je+10+off))
N=[7]
rb=hl.run(grid=1,tg=1,ins={1:rt1b.i32(N)},outs={0:4},timeout=12)
print("  baseline (n=7): out=",rt1b.di32(rb["outs"][0])[0] if rb["status"]=="OK" else rb["status"])
# zero the offset -> self-loop -> expect HANG (proves it is the taken edge)
r=hl.run(splices=[(je+3,bytes([0,0,0,0,0]))],grid=1,tg=1,ins={1:rt1b.i32(N)},outs={0:4},timeout=8)
print("  offset zeroed -> status=%s  %s"%(r["status"], "(HANG = taken back-edge)" if r["status"]=="HANG" else ""))
# recovery probe
rc=hl.run(grid=1,tg=1,ins={1:rt1b.i32(N)},outs={0:4},timeout=12)
print("  recovery run status=%s"%rc["status"])

print("\n### adversarial semantics (nested / brk / cont / eret) vs CPU ref")
def cpu_nested(x):
    if x<10:
        return (1 if x<2 else 2) if x<5 else (3 if x<8 else 4)
    else:
        return (5 if x<15 else 6) if x<20 else (7 if x<30 else 8)
xs=[0,3,6,9,12,17,25,40]
hn=rt1b.Harness("kernels/cf.metal","nested",workdir=".")
r=hn.run(grid=8,tg=8,ins={1:rt1b.i32(xs)},outs={0:32})
print("  nested gpu:",rt1b.di32(r["outs"][0]),"cpu:",[cpu_nested(x) for x in xs])
hb=rt1b.Harness("kernels/cf.metal","brk",workdir=".")
av=[0,1,3,5,10]; r=hb.run(grid=5,tg=5,ins={1:rt1b.i32(av)},outs={0:20})
print("  brk gpu:",rt1b.di32(r["outs"][0]),"cpu:",[sum(range(min(v,100))) for v in av])
hc=rt1b.Harness("kernels/cf.metal","cont",workdir=".")
r=hc.run(grid=5,tg=5,ins={1:rt1b.i32(av)},outs={0:20})
print("  cont gpu:",rt1b.di32(r["outs"][0]),"cpu:",[sum(i for i in range(v) if i%2==0) for v in av])
he=rt1b.Harness("kernels/cf.metal","eret")
r=he.run(grid=8,tg=8,ins={1:rt1b.i32([0]*8)},outs={0:32})
print("  eret gpu:",rt1b.di32(r["outs"][0]),"cpu:",[7,7,7,7,0,0,0,0])
