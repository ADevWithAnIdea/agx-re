#!/usr/bin/env python3
# RT-1b: clean test of the in-instruction immediate index-offset field on a
# single-index register load (bank a-load @ byte+5=0 reads r0=i0=41), plus the
# signed-offset investigation raised by a[gid-1] populating byte+9/10/11.
import rt1b
BASE=0xA000; NA=512
def ai(v): return v-BASE if BASE<=v<BASE+NA else None
A=rt1b.u32([BASE+j for j in range(NA)])
IDX=rt1b.u32([41,7,83,19])
BINS={2:A,3:IDX}; BOUTS={0:4,1:4}

h=rt1b.Harness("kernels/mem.metal","bank",workdir=".")
aload=0x1c
# force byte+5=0x00 so the index reg is r0=i0=41 for every splice below
base_sp=[(aload+5, bytes([0x00]))]
r=h.run(splices=base_sp,grid=1,tg=1,ins=BINS,outs=BOUTS);
print("baseline (byte5=0) ->", ai(rt1b.du32(r['outs'][0])[0]))
b9=h.base[h.main_off+aload+9]; b10=h.base[h.main_off+aload+10]; b11=h.base[h.main_off+aload+11]
print("orig byte+9/10/11 = %#x/%#x/%#x"%(b9,b10,b11))
def sw(bpos,vals):
    print("byte+%d:"%bpos)
    for v in vals:
        sp=base_sp+[(aload+bpos,bytes([v]))]
        r=h.run(splices=sp,grid=1,tg=1,ins=BINS,outs=BOUTS,timeout=15)
        if r['status']!='OK': print("  %#04x -> %s"%(v,r['status'])); continue
        k=ai(rt1b.du32(r['outs'][0])[0])
        print("  %#04x -> a[%s]  delta=%s"%(v,k,(k-41 if k is not None else '?')))
sw(9,[b9,b9|0x80])
sw(10,[b10,b10+1,b10+2,b10+4,b10+8,b10+0x10])
sw(11,[b11,b11+1,b11+2,b11+4])

print("\n## signed offset check: replicate minus1's byte+9/10/11 = 89/ff/5f on bank a-load")
# does a large/negative-looking offset move the index backward (signed)?
for (n9,n10,n11) in [(0x89,0xff,0x5f)]:
    sp=base_sp+[(aload+9,bytes([n9])),(aload+10,bytes([n10])),(aload+11,bytes([n11]))]
    r=h.run(splices=sp,grid=1,tg=1,ins=BINS,outs=BOUTS,timeout=15)
    o=rt1b.du32(r['outs'][0])[0] if r['status']=='OK' else None
    print("  set 89/ff/5f -> status=%s a[%s] delta=%s"%(r['status'], ai(o) if o else o, (ai(o)-41) if o and ai(o) is not None else '?'))
