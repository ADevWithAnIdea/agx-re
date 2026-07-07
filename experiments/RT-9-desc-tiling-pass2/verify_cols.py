import glob,os,re,sys,struct
HEX=re.compile(r'^([0-9a-f]{8}):\s+(.*)$');HDR=re.compile(r'gpu_va=0x([0-9a-f]+) cpu=0x([0-9a-f]+) size=0x([0-9a-f]+)')
def load(p):
    g=c=s=0;d=bytearray()
    for l in open(p):
        if l.startswith('#'):
            m=HDR.search(l)
            if m:g,c,s=(int(m.group(i),16) for i in(1,2,3))
            continue
        m=HEX.match(l)
        if not m:continue
        o=int(m.group(1),16);b=bytes.fromhex(m.group(2).replace(' ',''))
        if len(d)<o+len(b):d.extend(b'\x00'*(o+len(b)-len(d)))
        d[o:o+len(b)]=b
    return {'g':g,'s':s,'d':bytes(d)}
def np2(n):return 1<<((n-1).bit_length()) if n>1 else 1
def solve(dumpdir,fmt,W,H,bpp,decode):
    bos=[load(x) for x in sorted(glob.glob(dumpdir+'/*.hex'))]
    # find desc via 14-bit + base in BO, type 2
    base=None
    for b in bos:
        d=b['d']
        for o in range(0,len(d)-32,4):
            w0=int.from_bytes(d[o:o+4],'little');w1=int.from_bytes(d[o+4:o+8],'little')
            if (w0&0xf)!=2:continue
            wi=(((w0>>28)&0xf)|((w1&0x3ff)<<4))+1;hi=((w1>>10)&0x3fff)+1
            if wi!=W or hi!=H:continue
            w2=int.from_bytes(d[o+8:o+12],'little');w3=int.from_bytes(d[o+12:o+16],'little')
            bva=(w2|((w3&0xfff)<<32))<<4
            for bb in bos:
                if bb['g'] and bb['g']<=bva<bb['g']+bb['s']:
                    base=(bva,bb);break
            if base:break
        if base:break
    bva,bo=base;d=bo['d'];off=bva-bo['g']
    D=6 if bpp<=4 else 5;T=1<<D
    cols=-(-W//T)  # ceil(W/T) CORRECTED
    colsP=np2(W)//T # doc's ceil(Wp/T)
    def pred(x,y,c):
        tx=x>>D;ty=y>>D;xl=x&(T-1);yl=y&(T-1);m=0
        for i in range(D):m|=((xl>>i)&1)<<(2*i);m|=((yl>>i)&1)<<(2*i+1)
        return (ty*c+tx)*(T*T)+m
    xy2e={}
    cap=(len(d)-off)//bpp
    for e in range(cap):
        el=d[off+e*bpp:off+e*bpp+bpp]
        if len(el)<bpp:break
        r=decode(el)
        if r is None:continue
        x,y=r
        if not(0<=x<W and 0<=y<H):continue
        if (x,y) not in xy2e:xy2e[(x,y)]=e
    cov=len(xy2e)
    mmC=sum(1 for (x,y),e in xy2e.items() if pred(x,y,cols)!=e)
    mmP=sum(1 for (x,y),e in xy2e.items() if pred(x,y,colsP)!=e)
    print(f'{fmt} {W}x{H} bpp{bpp}: BOsz=0x{bo["s"]:x} tilePad={ (-(-W//T)*T) }x{ (-(-H//T)*T) } (bytes=0x{(-(-W//T)*T)*(-(-H//T)*T)*bpp:x})  pow2Pad={np2(W)}x{np2(H)}(0x{np2(W)*np2(H)*bpp:x})')
    print(f'   cov={cov}/{W*H}  CORRECTED cols=ceil(W/T)={cols}: {mmC} mismatch   DOC cols=Wp/T={colsP}: {mmP} mismatch')
# decoders
def d_rgba8(el):return (el[0]|(el[1]<<8), el[2]|(el[3]<<8))
def d_r32(el):
    v=int.from_bytes(el[:4],'little')
    return (v&0x3fff,(v>>14)&0x3fff) if (v>>28)==0xA else None
if __name__=='__main__':
    solve('raw/t_384_rgba8','rgba8',384,384,4,d_rgba8)
    solve('raw/t_300x500_r32','r32',300,500,4,d_r32)
    solve('raw/t_17x4095_r32','r32',17,4095,4,d_r32)
