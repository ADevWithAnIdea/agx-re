import rt1b
h=rt1b.Harness("kernels/call.metal","twocall",workdir=".")
b=h.main
def off40(o):
    v=int.from_bytes(b[o:o+5],"little")
    return v-(1<<40) if v&(1<<39) else v
calls=[i for i in range(len(b)-6) if b[i]==0x0f and b[i+1]==0x05 and b[i+2]==0x54 and b[i+4]==0x8f]
print("call sites:",[hex(c) for c in calls])
for c in calls:
    print("  @+0x%02x byte+6=%#04x off40=%d target=call+4+off40=%d  full=%s"%(
        c,b[c+6],off40(c+7),c+4+off40(c+7),b[c:c+14].hex()))
ts=set(c+4+off40(c+7) for c in calls)
print("distinct targets:",ts,"=> SAME target" if len(ts)==1 else "=> DIFFERENT")
