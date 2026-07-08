import sys, importlib.util
spec=importlib.util.spec_from_file_location('isadb','isadb_local.py')
isadb=importlib.util.module_from_spec(spec); spec.loader.exec_module(isadb)
def trim(b):
    while len(b)>=2 and b[-2:]==b'\x06\x00': b=b[:-2]
    return b
def named(buf,off,n):
    L=isadb.instr_length(buf,off)
    if L is None or L<=0 or off+L>n: return None,None
    try: rec,_=isadb.decode_one(buf,off); return L,rec['mnemonic']
    except Exception: return L,None
def trace(b):
    b=trim(b); n=len(b); off=0
    while off<n:
        L,mn=named(b,off,n)
        if L is not None:
            tag=mn if mn else '<len%d>'%L
            print(f"{off:4x}: {b[off:off+L].hex(' '):42s} {tag}")
            off+=L; continue
        s=off; off+=2
        while off<n:
            L2,mn2=named(b,off,n)
            if mn2 is not None: break
            off+=2
        print(f"{s:4x}: {b[s:off].hex(' '):42s} *** UNDECODED {off-s}B ***")
trace(bytes.fromhex(open(sys.argv[1]).read().strip()))
