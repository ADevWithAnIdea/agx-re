import rt1b
for fn in ["one","twocall","chain","recur","spill"]:
    h = rt1b.Harness("kernels/call.metal", fn, workdir=".")
    print("===", fn, "main_len", h.main_len)
    b=h.main
    # find call/return/frame markers
    for i in range(len(b)-1):
        pair=b[i:i+2].hex()
        if b[i]==0x0f and b[i+1] in (0x05,0x80): print("  0f%02x @+0x%02x : %s"%(b[i+1],i,b[i:i+14].hex()))
        if b[i]==0x8f: print("  8f   @+0x%02x : %s"%(i,b[i:i+4].hex()))
        if b[i]==0x43 and b[i+1]==0x00: print("  43   @+0x%02x : %s"%(i,b[i:i+4].hex()))
        if b[i]==0x6f: print("  6f   @+0x%02x : %s"%(i,b[i:i+6].hex()))
