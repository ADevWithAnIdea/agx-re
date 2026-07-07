import rt1b
for fn in ["rmw1","cxchg","agg","tgadd","race"]:
    try:
        h = rt1b.Harness("kernels/atom.metal", fn, workdir=".")
    except Exception as e:
        print("===",fn,"COMPILE ERR",e); continue
    print("===", fn, "main_len", h.main_len)
    b=h.main
    for i in range(len(b)-1):
        if b[i]==0x67 and b[i+1] in (0x11,0x01,0x0e,0x16):
            print("  atomic/mem 0x67 @+0x%02x b+1=%#04x : %s  (op@+12=%#04x)"%(i,b[i+1],b[i:i+14].hex(),b[i+12] if i+12<len(b) else -1))
        if b[i]==0xe7 and b[i+1] in (0x11,0x01):
            print("  mem 0xe7 @+0x%02x : %s"%(i,b[i:i+14].hex()))
        if b[i]==0x07 and i+2<len(b) and b[i+2]==0x54:
            print("  barrier/fence 0x07 @+0x%02x : %s  (byte+3=%#04x)"%(i,b[i:i+6].hex(),b[i+3]))
