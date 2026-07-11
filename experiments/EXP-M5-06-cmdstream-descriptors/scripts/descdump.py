import sys,re,glob,struct,os
def load(path):
    data=bytearray()
    for line in open(path):
        m=re.match(r'^([0-9a-f]{8}): (.*)',line)
        if not m:continue
        base=int(m.group(1),16); b=bytes.fromhex(m.group(2).replace(' ',''))
        if base+len(b)>len(data):data.extend(b'\x00'*(base+len(b)-len(data)))
        data[base:base+len(b)]=b
    return bytes(data)
def u64(d,o):return int.from_bytes(d[o:o+8],'little')
label=sys.argv[1]; mapdir=sys.argv[2]
# arg buffer = the BO of size 0x9480
cand=glob.glob(os.path.join(mapdir,'*sz9480.hex'))
if not cand:
    print("%-10s NO-ARGBUF"%label);sys.exit(0)
d=load(cand[0])
# find arg-buf base from filename vaXXXX
m=re.search(r'va([0-9a-f]+)_cpu',cand[0]); BASE=int(m.group(1),16)
texptr=u64(d,0x14a0); sampptr=u64(d,0x14a8); buf=u64(d,0x14b0)
to=texptr-BASE; so=sampptr-BASE
if to<0 or to+32>len(d):
    print("%-10s bad texptr 0x%x (base 0x%x) table=%s"%(label,texptr,BASE,d[0x14a0:0x14b8].hex()));sys.exit(0)
tex=d[to:to+32]
samp=d[so:so+8] if 0<=so and so+8<=len(d) else b''
w0,w1,w2,w3,w4,w5=struct.unpack('<6I',tex[:24])
typ=tex[0]&7; arr=tex[0]>>4; byte1=tex[1]; numtype=byte1>>5; sizecls=byte1&0x1f
swz=(w0>>16)&0xfff; sw=[(swz>>(3*i))&7 for i in range(4)]
# A18 interpretation
wA=((w0>>28)&0xf)|((w1&0x3ff)<<4); hA=(w1>>10)&0x3fff
# M5 candidate: width low 11 bits, height [11:24]
wM=((w0>>28)&0xf)|((w1&0x7ff)<<4); hM=(w1>>11)&0x3fff
baseVA=((w2)|((w3&0xfff)<<32))<<4
print("%-10s tex=%s"%(label,tex.hex()))
print("           w0=%08x w1=%08x w2=%08x w3=%08x w4=%08x w5=%08x baseVA=0x%x"%(w0,w1,w2,w3,w4,w5,baseVA))
print("           type=%d arrnib=%d byte1=0x%02x(num=%d sz=0x%02x) swz=%s | A18: W-1=%d H-1=%d | M5: W-1=%d H-1=%d | samp=%s"%(
      typ,arr,byte1,numtype,sizecls,sw,wA,hA,wM,hM,samp.hex()))
