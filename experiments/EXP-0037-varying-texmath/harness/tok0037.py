# EXP-0037 final candidate length function: current isadb rule + the EXP-0037
# fixes (varying store 0x57, tex companion-gate widen, standalone sampler op,
# coordinate-math low-nibble-b/e, refined float-ALU op-select 0x26/0x2e/0x18).
import sys
sys.path.insert(0,'/Users/user/cleanroom_gpu/tools/agx-isa')
import isadb
TEX_VARIANTS={0x00,0x04,0x07,0x09,0x13,0x17,0x1b,0x20,0x21,0x29,0x39,0x53,0x79,0x80,0x97}
def plen(buf,off):
    b0=buf[off]; lo=b0&0x0f
    b1=buf[off+1] if off+1<len(buf) else -1
    b2=buf[off+2] if off+2<len(buf) else -1
    b4=buf[off+4] if off+4<len(buf) else -1
    if (b0&0x07)==0x05 and (b1&0xf0)==0x80 and b2==0x0c: return 14      # tex bundle (companion widened)
    if b0 in (0x30,0x90,0xb0) and b2 in TEX_VARIANTS: return 10          # standalone sampler op
    if b0==0x57: return 8                                                 # varying store
    if lo==0x0b and b2 in (0x27,0x2f): return 10                          # coord/addr setup
    if lo==0x0e and b0!=0x0e and b2==0x23: return 10                      # coord ALU leader (0x2e/0x3e, sig 23 a0 42)
    if b0==0xf0: return 4
    if lo==0x09:                                                          # refined float ALU
        if b2 in (0x18,0x38): return 4
        if b2==0x1e: return 8
        if b2 in (0x26,0x2e): return 8 if (b4 & 0x02) else 6
        return 8 if (b2 & 0x02) else 6
    return isadb.instr_length(buf,off)
def walk(b):
    off=0; und=0; toks=[]
    while off<len(b):
        L=plen(b,off)
        if L is None or off+L>len(b):
            st=off; off+=2
            while off<len(b):
                L2=plen(b,off)
                if L2 is not None and off+L2<=len(b): break
                off+=2
            und+=off-st; toks.append((st,b[st],off-st,False))
        else:
            toks.append((off,b[off],L,True)); off+=L
    return und,toks
