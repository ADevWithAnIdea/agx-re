import rt1b
for fn in ["thresh","ifdata","loopsum","nested","brk","cont","eret"]:
    h = rt1b.Harness("kernels/cf.metal", fn, workdir=".")
    print("===", fn, "main_len", h.main_len)
    for t in h.tokens():
        m = t.get("mnemonic")
        flag = ""
        if t["byte0"] in (0x0a,0x02,0x05,0x16,0x0f): flag=" <=="
        print("    +0x%02x b0=0x%02x len=%d %-14s %s%s" % (t["off"], t["byte0"], t["length"], str(m), t["hex"], flag))
