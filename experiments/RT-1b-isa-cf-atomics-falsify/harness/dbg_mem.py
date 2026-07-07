import rt1b
for fn in ["bank","one","dev","v4"]:
    h = rt1b.Harness("kernels/mem.metal", fn, workdir=".")
    print("===", fn, "main_len", h.main_len)
    print("  raw:", h.main.hex())
    for t in h.tokens():
        m = t.get("mnemonic")
        print("    +0x%02x b0=0x%02x len=%d %s %s" % (t["off"], t["byte0"], t["length"], m, t["hex"]))
