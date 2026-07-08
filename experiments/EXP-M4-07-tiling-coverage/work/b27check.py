#!/usr/bin/env python3
# robust compression-eligibility check: scan ALL type-2 descriptors whose decoded
# dims == W,H and whose base VA lands in a captured BO; report word1 bit27.
import glob,sys,os
from cmpx import load
def check(dumpdir,W,H):
    bos=[load(p) for p in glob.glob(os.path.join(dumpdir,'*.hex'))]
    for b in bos:
        d=b['data']
        for o in range(0,len(d)-24,4):
            w=[int.from_bytes(d[o+4*i:o+4*i+4],'little') for i in range(6)]
            if (w[0]&0xf)!=2: continue
            width=(((w[0]>>28)&0xf)|((w[1]&0x3ff)<<4))+1; height=((w[1]>>10)&0x3fff)+1
            if width!=W or height!=H: continue
            bva=(w[2]|((w[3]&0xfff)<<32))<<4
            if any(bb['gpu_va'] and bb['gpu_va']<=bva<bb['gpu_va']+bb['size'] for bb in bos):
                return (w[1]>>27)&1
    return None
if __name__=='__main__':
    r=check(sys.argv[1],int(sys.argv[2]),int(sys.argv[3]))
    print('none' if r is None else r)
