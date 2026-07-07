# EXP-0037 candidate length function = current isadb rule + proposed fixes.
import sys
sys.path.insert(0,'/Users/user/cleanroom_gpu/tools/agx-isa')
import isadb
TEX_VARIANTS={0x00,0x04,0x07,0x09,0x13,0x17,0x1b,0x20,0x21,0x29,0x39,0x53,0x79,0x80,0x97}
def plen(buf,off):
    b0=buf[off]; b1=buf[off+1] if off+1<len(buf) else -1; b2=buf[off+2] if off+2<len(buf) else -1
    # (1) TEX companion gate WIDENED: byte+1 hi-nibble 8 (0x80/82/84/86/88) + byte+2==0x0c
    if (b0&0x07)==0x05 and (b1&0xf0)==0x80 and b2==0x0c:
        return 14
    # (2) standalone sampler op 0x30/0x90/0xb0 (low-nibble0, hi=result reg) -> 10
    if b0 in (0x30,0x90,0xb0) and b2 in TEX_VARIANTS:
        return 10
    # (3) vertex/mesh varying store
    if b0==0x57:
        return 8
    # (4) texture coordinate/address ALU (low-nibble b) with byte+2 in {0x27,0x2f} -> 10
    if (b0&0x0f)==0x0b and b2 in (0x27,0x2f):
        return 10
    # (5) low-nibble-e ALU (0x2e/0x3e...) coordinate math -> 10
    if (b0&0x0f)==0x0e and b0 not in (0x0e,):
        return 10
    # (6) 0xf0 4-byte move-ish
    if b0==0xf0:
        return 4
    return isadb.instr_length(buf,off)

def walk(b):
    off=0; regions=[]
    while off<len(b):
        L=plen(b,off)
        if L is None or off+L>len(b):
            # resync
            start=off; off+=2
            while off<len(b):
                L2=plen(b,off)
                if L2 is not None and off+L2<=len(b):
                    # require it also decodes or is a plausible leader; accept length
                    break
                off+=2
            regions.append((start,b[start],off-start,'UND'))
        else:
            regions.append((off,b[off],L,'ok'))
            off+=L
    und=sum(r[2] for r in regions if r[3]=='UND')
    return regions,und
