import struct, random, multiprocessing as mp, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "analysis"))
import exact_ref as E

def f32_bits(f):
    return struct.unpack("<I", struct.pack("<f", f))[0]

def worker(bits, which, q):
    if which == "log2":
        r = E.ref_log2(bits, E.F32)
    else:
        r = E.ref_sin(bits, E.F32)
    q.put(r)

def run_with_timeout(bits, which, timeout=2):
    ctx = mp.get_context("fork")
    q = ctx.Queue()
    p = ctx.Process(target=worker, args=(bits, which, q))
    p.start()
    p.join(timeout)
    if p.is_alive():
        p.terminate()
        p.join()
        return None
    try:
        return q.get_nowait()
    except Exception:
        return "ERR"

if __name__ == "__main__":
    which = sys.argv[1]
    lo, hi = float(sys.argv[2]), float(sys.argv[3])
    seed = int(sys.argv[4])
    n = int(sys.argv[5])
    random.seed(seed)
    bad = []
    for i in range(n):
        x = random.uniform(lo, hi)
        bits = f32_bits(x)
        r = run_with_timeout(bits, which, timeout=2)
        if r is None:
            bad.append((x, hex(bits)))
            print("HANG", which, x, hex(bits))
    print("scan done, bad=", bad)
