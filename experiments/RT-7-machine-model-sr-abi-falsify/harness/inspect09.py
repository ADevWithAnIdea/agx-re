import os,sys,subprocess,importlib.util
HERE=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("ap",os.path.join(HERE,"agxparse.py")); ap=importlib.util.module_from_spec(spec); spec.loader.exec_module(ap)
arch=os.path.join(HERE,"rfmap.bin")
buf=open(arch,"rb").read(); _,pieces=ap.extract_agx(buf); main=pieces["_agc.main"]
print("MAIN_LEN",len(main))
i=0;n=len(main);c09=0
while i+2<=n:
    b0=main[i]
    if b0==0x09:
        length=8 if (i+2<n and main[i+2]&0x02) else 6
        seg=main[i:i+length]
        print("off=%-4d len=%d %s  opsel=%d bit39=%d byte1=0x%02x byte3=0x%02x"%(i,length,seg.hex(),main[i+2]&7,(main[i+4]>>7)&1 if i+4<n else -1,main[i+1],main[i+3]))
        c09+=1; i+=length
    elif b0 in (0x67,0xe7): i+=14
    elif b0==0x0e: i+=4
    elif (b0&0x0f)==0x0c: i+=4
    else: i+=2
    if c09>25: break
print("total-09 shown")
