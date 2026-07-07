import os,sys,glob,re
def scan(dumpdir):
    hits={}
    for hxf in glob.glob(os.path.join(dumpdir,"bo_*.hex")):
        for ln in open(hxf):
            m=re.match(r'^([0-9a-f]{8}):\s+(.*)$',ln.strip())
            if not m: continue
            base=int(m.group(1),16); words=m.group(2).split()
            for i,w in enumerate(words):
                if len(w)==8:
                    val=int(w,16)
                    if val in (0x00080000,0x00880000):
                        hits.setdefault(val,[]).append((os.path.basename(hxf).split('_')[2],base+i*4))
    return hits
for tag in sys.argv[1:]:
    d="cap_%s"%tag
    if not os.path.isdir(d): print(tag,"NO-DIR"); continue
    h=scan(d)
    clr=len(h.get(0x00080000,[])); st=len(h.get(0x00880000,[]))
    verdict = "CLEAR bit23=0" if (clr and not st) else ("SET bit23=1" if (st and not clr) else ("BOTH" if (clr and st) else "neither"))
    locs080=h.get(0x00080000,[])[:3]; locs880=h.get(0x00880000,[])[:3]
    print("%-6s %-16s  0x080000@%s  0x880000@%s"%(tag,verdict,locs080,locs880))
