#!/usr/bin/env python3
# Parse __GPU_METADATA / __GPU_STATS_MD FlatBuffers of our own compiled shaders
# and print the compiler's stat fields (register footprint etc.) vs K.
# CLEAN-ROOM: OWN-SHADER -- our own archive's own metadata.
import os, sys, subprocess, struct, importlib.util
HERE=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("ap",os.path.join(HERE,"agxparse.py")); ap=importlib.util.module_from_spec(spec); spec.loader.exec_module(ap)

def gpu(buf):
    for off,size,note in ap.iter_gpu_images(buf):
        try: mo=ap.MachO(buf,off)
        except ValueError: continue
        if mo.cputype==ap.APPLE_GPU_CPUTYPE: return mo

def sections(K, srcpat):
    kp=srcpat%K
    arch=os.path.join(HERE,"fb_%d.bin"%K)
    subprocess.run([os.path.join(HERE,"shdump"),"-o",arch,"-f","k","--no-fast-math",kp],capture_output=True)
    if not os.path.exists(arch): return None
    buf=open(arch,"rb").read(); mo=gpu(buf)
    s=mo.find_section("__TEXT","__compute"); nb=mo.base+s["offset"]; nm=ap.MachO(buf,nb)
    out={}
    for sec in nm.sections:
        if sec["seg"].startswith("__GPU"):
            o=nb+sec["offset"]; out[sec["seg"]]=bytes(buf[o:o+sec["size"]])
    os.remove(arch); return out

def table_fields(buf, tpos):
    soff=struct.unpack_from('<i',buf,tpos)[0]; vt=tpos-soff
    vtsize=struct.unpack_from('<H',buf,vt)[0]; nf=(vtsize-4)//2
    fields={}
    for i in range(nf):
        foff=struct.unpack_from('<H',buf,vt+4+i*2)[0]
        if foff: fields[i]=tpos+foff
    return fields

def meta_regfields(meta):
    # root -> field0 uoffset -> stats table; return {fieldidx: (pos, u32)}
    root=struct.unpack_from('<I',meta,0)[0]
    rf=table_fields(meta,root)
    if 0 not in rf: return {}
    f0pos=rf[0]; sub=f0pos+struct.unpack_from('<I',meta,f0pos)[0]
    ff=table_fields(meta,sub)
    return {i:(p,struct.unpack_from('<I',meta,p)[0] if p+4<=len(meta) else meta[p]) for i,p in ff.items()}

if __name__=="__main__":
    srcpat=os.path.join(HERE,"kernels","pf%d.metal")
    if len(sys.argv)>1 and sys.argv[1]=="half":
        srcpat=os.path.join(HERE,"kernels","ph%d.metal")
    Ks=[int(x) for x in sys.argv[2:]] if len(sys.argv)>2 else [2,4,8,12,16,24,32,40,48,56,64,72,80,88,96,104,112,120,128,144,160,192,224,256]
    print("%-5s %-8s %-8s %s"%("K","METALEN","f0(regs)","other_small_fields"))
    for K in Ks:
        secs=sections(K,srcpat)
        if not secs: print("K=%d COMPILE_FAIL"%K); continue
        meta=secs.get("__GPU_METADATA",b"")
        rf=meta_regfields(meta)
        f0=rf.get(0,(0,0))[1]
        small={i:(v if v<10000 else hex(v)) for i,(p,v) in sorted(rf.items()) if i!=0 and meta[p]<200}
        print("%-5d %-8d %-8d %s"%(K,len(meta),f0,small))
        sys.stdout.flush()
