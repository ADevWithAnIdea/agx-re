#!/usr/bin/env python3
# EXP-0018 HW validation driver. Runs on the device. CLEAN-ROOM: OWN-SHADER.
import sys, os
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE)
from hwval import H, find

def show(name, got, exp):
    ok = got==exp
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        print(f"    got={got}")
        print(f"    exp={exp}")
    return ok

W=32  # SIMD width hypothesis (verified below)
N=W
IN=[i+1 for i in range(N)]          # distinct: 1..32
fails=0

# ===================== SIMD WIDTH =====================
hs=H("kernels/simd.metal")
r=hs.run("s_width_sr",N,N,{},{2:('u',N)}); print("s_width_sr:",r[2][:4],"... (threads_per_simdgroup)")
r=hs.run("s_laneid",64,64,{},{2:('u',64)}); print("s_laneid[0:40]:",r[2][:40])
r=hs.run("s_sum1",N,N,{},{2:('i',N)}); print("s_sum1(active count):",r[2][:4])

# ===================== SIMD BROADCAST / SHUFFLE =====================
def sg(fn,exp,dt='i',inb=IN):
    global fails
    r=hs.run(fn,N,N,{1:(dt,inb)},{2:(dt,N)})
    if r["_status"]!="OK": print(f"[FAIL] {fn} status={r['_status']} {r['_err']}"); fails+=1; return
    fails+= not show(fn,r[2],exp)

sg("s_bcast0",[IN[0]]*N)
sg("s_bcast5",[IN[5]]*N)
sg("s_bcast_first",[IN[0]]*N)
sg("s_shuf_xor1",[IN[i^1] for i in range(N)])
sg("s_shuf_lane",[IN[i^1] for i in range(N)])
sg("s_shuf_up1",[IN[i-1] if i>=1 else IN[i] for i in range(N)])     # lane0 keeps own (impl-defined; check)
sg("s_shuf_down1",[IN[i+1] if i+1<N else IN[i] for i in range(N)])
# ===================== SIMD REDUCTIONS =====================
sg("s_sum",[sum(IN)]*N)
sg("s_min",[min(IN)]*N)
sg("s_max",[max(IN)]*N)
AND=IN[0]
for v in IN: AND&=v
OR=0
for v in IN: OR|=v
XOR=0
for v in IN: XOR^=v
sg("s_and",[AND]*N)
sg("s_or",[OR]*N)
sg("s_xor",[XOR]*N)
# product overflows int; use small distinct values to keep in range: 1,1,..2 pattern
r=hs.run("s_prod",N,N,{1:('i',[2 if i==0 else 1 for i in range(N)])},{2:('i',N)})
fails+= not show("s_prod(one 2 rest 1)",r[2],[2]*N)
# float sum
r=hs.run("s_fsum",N,N,{1:('f',[float(i+1) for i in range(N)])},{2:('f',N)})
fs=[round(x,2) for x in r[2]]; fails+= not show("s_fsum",fs,[float(sum(IN))]*N)
# ===================== SIMD PREFIX SCANS =====================
inc=[sum(IN[:i+1]) for i in range(N)]
exc=[sum(IN[:i]) for i in range(N)]
sg("s_prefix_inc",inc)
sg("s_prefix_exc",exc)
# ===================== BALLOT / VOTE / ELECT =====================
r=hs.run("s_ballot",N,N,{1:('i',IN)},{2:('u',N)})   # all in>0 -> mask all-ones (32 bits)
fails+= not show("s_ballot(all>0) low32",[hex(x) for x in r[2][:2]],[hex(0xFFFFFFFF)]*2)
# mixed: even lanes >0, odd lanes 0
mix=[1 if i%2==0 else 0 for i in range(N)]
r=hs.run("s_ballot",N,N,{1:('i',mix)},{2:('u',N)})
expmask=0
for i in range(N):
    if mix[i]>0: expmask|=(1<<i)
fails+= not show("s_ballot(even>0) low32",hex(r[2][0]),hex(expmask))
r=hs.run("s_all",N,N,{1:('i',IN)},{2:('i',N)}); fails+= not show("s_all(all>0)",r[2],[1]*N)
r=hs.run("s_all",N,N,{1:('i',mix)},{2:('i',N)}); fails+= not show("s_all(mixed)",r[2],[0]*N)
r=hs.run("s_any",N,N,{1:('i',mix)},{2:('i',N)}); fails+= not show("s_any(mixed)",r[2],[1]*N)
r=hs.run("s_any",N,N,{1:('i',[0]*N)},{2:('i',N)}); fails+= not show("s_any(none)",r[2],[0]*N)
r=hs.run("s_is_first",N,N,{},{2:('i',N)}); fails+= not show("s_is_first",r[2],[1]+[0]*(N-1))
r=hs.run("s_active_mask",N,N,{},{2:('u',N)}); print("s_active_mask low32:",hex(r[2][0]))

print("\n================ QUAD ================")
hq=H("kernels/quad.metal")
def qg(fn,exp,dt='i',inb=IN):
    global fails
    r=hq.run(fn,N,N,{1:(dt,inb)},{2:(dt,N)})
    if r["_status"]!="OK": print(f"[FAIL] {fn} status={r['_status']}"); fails+=1; return
    fails+= not show(fn,r[2],exp)
r=hq.run("q_laneid",N,N,{},{2:('u',N)}); fails+= not show("q_laneid",r[2],[i%4 for i in range(N)])
qg("q_bcast0",[IN[(i//4)*4] for i in range(N)])
qg("q_bcast2",[IN[(i//4)*4+2] for i in range(N)])
qg("q_shuf_xor1",[IN[i^1] for i in range(N)])
qg("q_shuf_lane",[IN[i^2] for i in range(N)])
qg("q_shuf_up1",[IN[i-1] if (i%4)>=1 else IN[i] for i in range(N)])
qg("q_shuf_down1",[IN[i+1] if (i%4)<3 else IN[i] for i in range(N)])
qg("q_sum",[sum(IN[(i//4)*4:(i//4)*4+4]) for i in range(N)])
qg("q_max",[max(IN[(i//4)*4:(i//4)*4+4]) for i in range(N)])
qg("q_min",[min(IN[(i//4)*4:(i//4)*4+4]) for i in range(N)])
qand=[]
for i in range(N):
    a=IN[(i//4)*4]
    for k in range(1,4): a&=IN[(i//4)*4+k]
    qand.append(a)
qg("q_and",qand)
qg("q_prefix_inc",[sum(IN[(i//4)*4:i+1]) for i in range(N)])

print("\n================ ATOMIC AGGREGATE ================")
ha=H("kernels/atomics.metal")
G,T=1024,256
r=ha.run("agg_add1",G,T,{0:('i',[0])},{0:('i',1)},timeout=12)
fails+= not show(f"agg_add1 grid={G}: counter==grid",r[0],[G])

print("\n================ ATOMIC OP-FIELD SPLICE (byte+12) ================")
# locate the 67 11 .. atomic RMW op in agg_add1 and splice byte+12 add(0x20)->max(0x28)
mh,off,length=ha.main_hex("agg_add1")
i=find(mh,"6711")
print(f"agg_add1 67 11 op at main-offset {i}; op bytes = {mh[i*2:i*2+28]}; byte+12 = {mh[(i+12)*2:(i+12)*2+2]}")
# add -> max: with each simdgroup contributing count=32, atomic max over threadgroups -> 32
r=ha.run("agg_add1",G,T,{0:('i',[0])},{0:('i',1)},splices={i+12:0x28},timeout=12)
fails+= not show(f"agg_add1 spliced add->max(0x28): counter==simdwidth(32)",r[0],[32])
# add -> or(0x2c): OR of 32 (0x20) across groups -> 32
r=ha.run("agg_add1",G,T,{0:('i',[0])},{0:('i',1)},splices={i+12:0x2c},timeout=12)
fails+= not show(f"agg_add1 spliced add->or(0x2c): counter==32",r[0],[32])

print("\n================ ATOMIC RETURN VALUE (device fetch_add) ================")
# da_add_r: each lane adds in[i]; returns the value BEFORE its add. Sum of returns
# + sum(in) relationship; final counter = sum(in). Read counter (buf0) + returns.
r=ha.run("da_add_r",N,N,{0:('i',[0]),1:('i',IN)},{0:('i',1),2:('i',N)},timeout=10)
print("da_add_r final counter:",r[0]," (expect sum(in)=",sum(IN),")")
print("da_add_r returns[0:8]:",r[2][:8]," (each is value-before-this-lane's-add; a valid prefix)")
fails+= not show("da_add_r counter==sum(in)",r[0],[sum(IN)])
# returns must be a permutation-consistent prefix: sorted(returns) == exclusive prefix of sorted contributions
fails+= not show("da_add_r sorted(returns)==exclusive-prefix",sorted(r[2]),[sum(IN[:k]) for k in range(N)])

print(f"\n==== {'ALL PASS' if fails==0 else str(fails)+' FAIL(S)'} ====")
sys.exit(1 if fails else 0)
