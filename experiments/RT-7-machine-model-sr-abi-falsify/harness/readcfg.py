import os,sys,glob,re
VA=0x10000000000; OFF=0x5298
def readword(dumpdir,va,off):
    for hxf in glob.glob(os.path.join(dumpdir,"bo_*.hex")):
        cur=None
        for ln in open(hxf):
            mh=re.search(r'gpu_va=0x([0-9a-f]+)',ln)
            if mh and cur is None: cur=int(mh.group(1),16); continue
            m=re.match(r'^([0-9a-f]{8}):\s+(.*)$',ln.strip())
            if not m: continue
            base=int(m.group(1),16); words=m.group(2).split()
            if base<=off<base+len(words)*4 and cur==va:
                idx=(off-base)//4
                if idx<len(words) and len(words[idx])==8: return int(words[idx],16)
    return None
print("va=0x%x off=0x%x  (config/tier word)"%(VA,OFF))
print("%-6s %-12s %s"%("tag","word","bit23"))
for tag in sys.argv[1:]:
    d="cap_%s"%tag
    if not os.path.isdir(d): print(tag,"NO-DIR"); continue
    w=readword(d,VA,OFF)
    print("%-6s 0x%08x   %d"%(tag,w if w is not None else -1,((w>>23)&1) if w is not None else -1))
