import os,importlib.util
HERE=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("ap",os.path.join(HERE,"agxparse.py")); ap=importlib.util.module_from_spec(spec); spec.loader.exec_module(ap)
buf=open(os.path.join(HERE,"allst.bin"),"rb").read(); _,pieces=ap.extract_agx(buf); main=pieces["_agc.main"]
n=len(main); print("MAIN_LEN",n)
# walk and collect all 0x09
i=0; ops=[]
while i+2<=n:
    b0=main[i]
    if b0==0x09:
        length=8 if (i+2<n and main[i+2]&0x02) else 6
        ops.append((i,length,main[i:i+length].hex(),main[i+2]&7,(main[i+4]>>7)&1 if i+4<n else -1))
        i+=length
    elif b0 in (0x67,0xe7): i+=14
    elif b0==0x0e: i+=4
    elif (b0&0x0f)==0x0c: i+=4
    else: i+=2
print("total 0x09:",len(ops))
print("first 3:",ops[:3])
print("LAST 6 (probe region):")
for o in ops[-6:]: print("  off=%d len=%d %s opsel=%d bit39=%d"%o)
# also show last 40 bytes raw
print("tail bytes:",main[-40:].hex())
