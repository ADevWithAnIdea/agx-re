import sys,re,glob,os
def load(path):
    d=bytearray()
    for line in open(path):
        m=re.match(r'^([0-9a-f]{8}): (.*)',line)
        if not m:continue
        b=int(m.group(1),16);by=bytes.fromhex(m.group(2).replace(' ',''))
        if b+len(by)>len(d):d.extend(b'\x00'*(b+len(by)-len(d)))
        d[b:b+len(by)]=by
    return bytes(d)
d1,d2,va=sys.argv[1],sys.argv[2],sys.argv[3]
f1=glob.glob(os.path.join(d1,'bo_sigusr1_h0_va%s_*.hex'%va))
f2=glob.glob(os.path.join(d2,'bo_sigusr1_h0_va%s_*.hex'%va))
if not f1 or not f2:print("  missing va %s"%va);sys.exit(0)
a=load(f1[0]);b=load(f2[0]);n=min(len(a),len(b))
print("  diff va %s (%s vs %s)"%(va,os.path.basename(d1),os.path.basename(d2)))
i=0
while i<n:
    if a[i:i+4]!=b[i:i+4]:
        print("   +0x%04x: %s -> %s"%(i,a[i:i+4].hex(),b[i:i+4].hex()))
    i+=4
