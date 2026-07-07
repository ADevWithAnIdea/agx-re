import glob,sys,importlib
V=importlib.import_module('verify_cols')
AD={0:'edge',1:'repeat',2:'mirror',3:'clampZero/Border',5:'mirrorClampEdge'}
def bits(v,a,b): return (v>>a)&((1<<(b-a+1))-1)
def decode(v):
    return dict(lodMin=bits(v,0,11)/64.0, lodMax=bits(v,13,19)/8.0, aniso=1<<bits(v,20,22),
        mag=bits(v,23,23),minf=bits(v,25,25),mip=bits(v,27,28),
        S=AD.get(bits(v,29,31),bits(v,29,31)),T=AD.get(bits(v,32,34),bits(v,32,34)),R=AD.get(bits(v,35,37),bits(v,35,37)),
        unnorm=bits(v,38,38),cmp_sense=bits(v,39,39),cmp_test=bits(v,40,42),border=bits(v,61,62))
def samp(dir):
    bos=[V.load(x) for x in sorted(glob.glob('raw/%s/*.hex'%dir))]
    ref=bytes.fromhex('00000e0080070000')
    seen=set()
    print(f'--- {dir} ---')
    for b in bos:
        d=b['d']
        for o in range(0,len(d)-8,8):
            w=d[o:o+8]
            if w==ref or (w[2]&0x0f)==0x0e or (w[2]==0x0e):
                v=int.from_bytes(w,'little')
                if v in seen: continue
                seen.add(v)
                dd=decode(v)
                tag='REF(never)' if w==ref else ''
                print(f'  @0x{b["g"]:x}+0x{o:x} {w.hex()} {tag} cmp(sense={dd["cmp_sense"]},test={dd["cmp_test"]}) S={dd["S"]} T={dd["T"]} R={dd["R"]} border={dd["border"]} lodMax={dd["lodMax"]}')
for dir in ['s_never','s_less','s_gequal']: samp(dir)
