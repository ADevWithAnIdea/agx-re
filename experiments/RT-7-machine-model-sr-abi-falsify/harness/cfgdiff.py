import os,sys,glob,re
def load(dumpdir):
    # gpu_va -> {offset: value}
    bos={}
    for hxf in glob.glob(os.path.join(dumpdir,"bo_*.hex")):
        va=None
        d={}
        for ln in open(hxf):
            mh=re.search(r'gpu_va=0x([0-9a-f]+)',ln)
            if mh and va is None: va=int(mh.group(1),16); continue
            m=re.match(r'^([0-9a-f]{8}):\s+(.*)$',ln.strip())
            if not m: continue
            base=int(m.group(1),16); words=m.group(2).split()
            for i,w in enumerate(words):
                if len(w)==8: d[base+i*4]=int(w,16)
        if va is not None: bos[va]=d
    return bos
a=load(sys.argv[1]); b=load(sys.argv[2])
print("config-word candidates (val flips 0x00080000<->0x00880000 at same va+off):")
cands=[]
for va in sorted(set(a)&set(b)):
    for off in sorted(set(a[va])&set(b[va])):
        va_,vb_=a[va][off],b[va][off]
        if {va_,vb_}=={0x00080000,0x00880000}:
            print("  va=0x%x off=0x%x : %s=0x%08x  %s=0x%08x"%(va,off,sys.argv[1],va_,sys.argv[2],vb_))
            cands.append((va,off))
# broader: any offset where exactly bit23 differs and low bits match a plausible config
print("\nbit23-only differences (val_a ^ val_b == 0x00800000):")
for va in sorted(set(a)&set(b)):
    for off in sorted(set(a[va])&set(b[va])):
        if (a[va][off]^b[va][off])==0x00800000:
            print("  va=0x%x off=0x%x : 0x%08x vs 0x%08x"%(va,off,a[va][off],b[va][off]))
