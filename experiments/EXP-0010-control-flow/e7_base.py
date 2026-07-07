#!/usr/bin/env python3
# e7_base.py -- EXP-0010 E7: locate the buffer-base / binding-select field in the
# device_load (0x67) instruction by sweeping each byte of add2's load-a and
# watching for the output to switch from a+b to b+b (load-a now reads buffer-b's
# base) or to 0+b (reads the zero out buffer). HW-validates that the base pointer
# is selected by a field in the load (i.e. comes from a preloaded uniform slot,
# not the constant_program). Runs ON DEVICE. CLEAN-ROOM: our own bytes only.
import os, importlib.util
HERE=os.path.dirname(os.path.abspath(__file__))
def lm(n,p):
    s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
C=lm("cf_probe",os.path.join(HERE,"cf_probe.py")); IntProbe=C.IntProbe

A=[1,2,3,4,5,6,7,8]; B=[10,20,30,40,50,60,70,80]
AB=[a+b for a,b in zip(A,B)]; BB=[2*b for b in B]; AA=[2*a for a in A]; JB=B[:]; JA=A[:]

def classify(o):
    if o==AB: return "a+b (orig)"
    if o==BB: return "b+b  (load-a -> buffer B!)"
    if o==AA: return "a+a  (load-a -> buffer A-as-B?)"
    if o==JB: return "0+b  (load-a -> zero/out buffer)"
    if o==JA: return "a+0"
    if not o: return "FAULT/empty"
    if all(x==0 for x in o): return "all-zero"
    return f"other {o}"

def main():
    p=IntProbe("kernels/add2.metal",function="k",fast_math=False)
    m=p.main; print("main:",m.hex())
    # load-a is the first 0x67 after the preamble.
    la=m.index(0x67)
    print(f"load-a at main[{la}] = {m[la:la+14].hex()}")
    lb=m.index(0x67, la+14)
    print(f"load-b at main[{lb}] = {m[lb:lb+14].hex()}")
    b=p.run({},ins={1:A,2:B},outs={0:8},grid=8,tg=8)
    print("baseline:",b.get(0),classify(b.get(0)),b["_status"])
    # sweep each byte of load-a (skip opcode byte0). Report only outputs that
    # DIFFER from baseline (to find the buffer-select field).
    for bi in range(1,14):
        hits={}
        for val in range(256):
            if val==m[la+bi]: continue
            r=p.run({la+bi:val},ins={1:A,2:B},outs={0:8},grid=8,tg=8)
            c=classify(r.get(0))
            if c not in ("a+b (orig)",) and r["_status"]=="OK" and c!="all-zero" and not c.startswith("other"):
                hits.setdefault(c,[]).append(val)
        if hits:
            print(f"\nload-a byte[{bi}] (orig {m[la+bi]:#04x}) interesting values:")
            for c,vals in hits.items():
                vs=",".join(f"{v:#04x}" for v in vals[:12])
                print(f"   -> {c:32s} at {vs}{' ...' if len(vals)>12 else ''}")
    p.close()

if __name__=="__main__": main()
