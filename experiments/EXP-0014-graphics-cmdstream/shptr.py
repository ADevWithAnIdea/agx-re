#!/usr/bin/env python3
# shptr.py -- find shaderVA>>6-style pointers among captured GPU BOs.
# Generalises bograph: for every 4- and 8-byte LE value v in every BO, test
# whether v<<6 (and v directly) lands inside another BO's [gpu_va, gpu_va+size).
# Catches the compute-style "shader-code pointer = VA>>6" that bograph's --min misses.
import glob, os, re, sys
HEXLINE = re.compile(r'^([0-9a-f]{8}):\s+(.*)$')
HDR = re.compile(r'gpu_va=0x([0-9a-f]+) cpu=0x([0-9a-f]+) size=0x([0-9a-f]+)')
def load(path):
    gpu_va=size=0; data=bytearray()
    with open(path) as f:
        for line in f:
            if line.startswith('#'):
                m=HDR.search(line)
                if m: gpu_va,_,size=(int(m.group(i),16) for i in (1,2,3))
                continue
            m=HEXLINE.match(line)
            if not m: continue
            off=int(m.group(1),16); b=bytes.fromhex(m.group(2).replace(' ',''))
            if len(data)<off+len(b): data.extend(b'\x00'*(off+len(b)-len(data)))
            data[off:off+len(b)]=b
    return {'path':path,'gpu_va':gpu_va,'size':size,'data':bytes(data)}
def main():
    d=sys.argv[1]; src=int(sys.argv[2],0) if len(sys.argv)>2 else None
    bos=[load(p) for p in sorted(glob.glob(os.path.join(d,'*.hex')))]
    bos=[b for b in bos if b['gpu_va']]
    wins=sorted(({'va':b['gpu_va'],'end':b['gpu_va']+max(b['size'],len(b['data'])),
                  'name':os.path.basename(b['path'])} for b in bos),key=lambda w:w['va'])
    def name_of(v):
        for w in wins:
            if w['va']<=v<w['end']:
                dd=v-w['va']; return f"va={w['va']:#x}+{dd:#x}" if dd else f"va={w['va']:#x}"
        return None
    for b in bos:
        if src is not None and b['gpu_va']!=src: continue
        data=b['data']; hits=[]
        for off in range(0,len(data)-3,4):
            v=int.from_bytes(data[off:off+4],'little')
            if v==0: continue
            # shaderVA>>6 form: reconstruct full VA = v<<6, but v is only low32,
            # high bits (the 0x4 nibble) live in the shader VM base 0x10000000000.
            for cand,tag in (((v<<6)|0x10000000000,'<<6|base'),(v<<6,'<<6')):
                nm=name_of(cand)
                if nm and 'va=0x10000000000' in nm:
                    hits.append((off,v,cand,nm,tag))
        if hits:
            print(f"\n=== BO {b['gpu_va']:#x} ({os.path.basename(b['path'])}) shader-ptr candidates ===")
            for off,v,cand,nm,tag in hits[:60]:
                print(f"  +{off:#06x}: raw={v:#010x}  {tag}->{cand:#014x} = {nm}")
if __name__=='__main__': main()
