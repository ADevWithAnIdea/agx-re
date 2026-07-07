import rt1b
for fn in ["loopsum","loopbig"]:
    h = rt1b.Harness("kernels/cf.metal", fn, workdir=".")
    hx = h.main.hex()
    print("===", fn, "main_len", h.main_len)
    print(hx)
    # find all 0f?? parcels (control-flow group) and 0f00 back-jumps
    b = h.main
    for i in range(0, len(b)-1):
        if b[i]==0x0f:
            # show the next several bytes as a candidate CF word
            print("  0f @+0x%02x : %s" % (i, b[i:i+10].hex()))
