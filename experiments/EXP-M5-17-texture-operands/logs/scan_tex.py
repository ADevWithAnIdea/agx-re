import sys, glob, os, collections
hexdir = sys.argv[1]
b5 = collections.Counter(); b2 = collections.Counter(); total=0
examples=[]
for fn in glob.glob(os.path.join(hexdir,"*.hex")):
    data=open(fn).read().strip()
    try: buf=bytes.fromhex(data)
    except: continue
    for i in range(len(buf)-6):
        if (buf[i]&0x0f)==0x0f and buf[i+1] in (0x04,0x05,0x06,0x07) and buf[i+2] in (0x12,0x16,0x1a) and (buf[i+4]&0xf0)==0x40:
            total+=1; b5[buf[i+5]]+=1; b2[buf[i+2]]+=1
            if len(examples)<12: examples.append((os.path.basename(fn)[:30], buf[i:i+10].hex()))
print(f"{hexdir}: {total} candidate tex leaders")
print("  byte+2 (class):", dict(b2))
print("  byte+5 dist   :", dict(b5.most_common(12)))
for n,h in examples: print("   ",n,h)
