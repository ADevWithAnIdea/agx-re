#!/usr/bin/env python3
# EXP-M5-03 byte-weighted ISA census over a hex corpus, using the UNMODIFIED
# G17P (A18/G17P) descriptor DB in tools/agx-isa. Classifies every instruction
# byte as fully-named / raw(length-only) / desync(unknown-length), and inventories
# the per-byte0 DESYNC-leader and RAW-leader histograms ranked by frequency.
#
# Resync tokenizer identical in spirit to EXP-M4-01 census.py: where the DB gives a
# length it consumes the instruction (recording whether a descriptor also NAMED it);
# where it cannot, it records the leading byte as an UNDECODED (desync) region and
# advances one 2-byte parcel to resync, so one gap does not blind the rest.
#
# CLEAN-ROOM: every byte is the compiled form of permissive third-party MSL WE
# compiled with our own toolchain. No Apple binary is introspected. DB is read-only.
import sys, os, glob, hashlib, collections, json, argparse

def _find_isadb():
    for c in (os.path.expanduser("~/cleanroom_work/tools/agx-isa"),
              "/Users/user/asahi_re/public/gpu/tools/agx-isa"):
        if os.path.isfile(os.path.join(c, "isadb.py")):
            return c
    raise RuntimeError("isadb.py not found")
sys.path.insert(0, _find_isadb())
import isadb

def trim_padding(b):
    end = len(b)
    while end >= 2 and b[end-2:end] == b'\x06\x00':
        end -= 2
    return b[:end]

def _named_at(buf, off, n):
    L = isadb.instr_length(buf, off)
    if L is None or off + L > n:
        return None, None
    try:
        rec, _ = isadb.decode_one(buf, off)
        return L, rec['mnemonic']
    except ValueError:
        return L, None

def walk(buf):
    recs = []
    off = 0
    n = len(buf)
    while off < n:
        b0 = buf[off]
        L, mn = _named_at(buf, off, n)
        if L is not None:
            recs.append((off, b0, L, mn, 'named' if mn else 'length_only'))
            off += L
            continue
        start = off
        off += 2
        while off < n:
            L2, mn2 = _named_at(buf, off, n)
            if mn2 is not None:
                break
            off += 2
        recs.append((start, b0, off - start, None, 'undecoded'))
    return recs

def load_unique(hexdir):
    files = sorted(glob.glob(os.path.join(hexdir, "*.hex")))
    seen = {}
    nfiles = 0
    per_project_files = collections.Counter()
    per_project_uniq = collections.Counter()
    for fp in files:
        base = os.path.basename(fp)
        # tp__<project>__<sub>__<stage>.hex
        proj = base.split("__")[1] if base.startswith("tp__") and "__" in base else "?"
        try:
            h = open(fp).read().strip()
        except Exception:
            continue
        if not h:
            continue
        try:
            buf = trim_padding(bytes.fromhex(h))
        except ValueError:
            continue
        nfiles += 1
        per_project_files[proj] += 1
        sig = hashlib.sha256(buf).hexdigest()
        if sig not in seen:
            seen[sig] = (base, buf, proj)
            per_project_uniq[proj] += 1
    return nfiles, list(seen.values()), per_project_files, per_project_uniq

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("hexdir")
    ap.add_argument("--out", default="census")
    args = ap.parse_args()

    nfiles, progs, ppf, ppu = load_unique(args.hexdir)

    tot_bytes = named_bytes = raw_bytes = desync_bytes = 0
    tot_named = tot_raw = tot_desync = 0
    byte0_named   = collections.Counter()
    byte0_raw     = collections.Counter()   # length-only leaders
    byte0_desync  = collections.Counter()   # desync region leaders (count of regions)
    byte0_desync_bytes = collections.Counter()
    desync_sample = {}
    raw_sample = {}
    mnem_count = collections.Counter()
    byte0_all = collections.Counter()
    # per-project byte accounting
    pj_bytes = collections.Counter(); pj_named = collections.Counter()
    pj_raw = collections.Counter(); pj_desync = collections.Counter()

    for name, buf, proj in progs:
        recs = walk(buf)
        pj_bytes[proj] += len(buf)
        for (off, b0, L, mn, status) in recs:
            byte0_all[b0] += 1
            tot_bytes += 0  # counted below via len
            if status == 'named':
                tot_named += 1; named_bytes += L; byte0_named[b0] += 1
                mnem_count[mn] += 1; pj_named[proj] += L
            elif status == 'length_only':
                tot_raw += 1; raw_bytes += L; byte0_raw[b0] += 1
                pj_raw[proj] += L
                raw_sample.setdefault(b0, buf[off:off+8].hex())
            else:
                tot_desync += 1; desync_bytes += L; byte0_desync[b0] += 1
                byte0_desync_bytes[b0] += L; pj_desync[proj] += L
                desync_sample.setdefault(b0, buf[off:off+16].hex())
        tot_bytes += len(buf)

    tot_instr = tot_named + tot_raw + tot_desync
    out = []
    def p(s=''): out.append(s)
    p("="*78)
    p("EXP-M5-03  THIRD-PARTY ISA CENSUS  (UNMODIFIED G17P DB, byte-weighted)")
    p("="*78)
    p(f"hex dir: {args.hexdir}")
    p(f"hex files: {nfiles}   unique stage-programs (dedup by sha256): {len(progs)}")
    p(f"instruction tokens walked: {tot_instr}")
    p(f"total instruction bytes: {tot_bytes}")
    p("")
    def pct(x): return 100.0*x/tot_bytes if tot_bytes else 0.0
    p("--- BYTE COVERAGE (of total instruction bytes) ---")
    p(f"  fully-named (descriptor matched): {named_bytes:8d}  {pct(named_bytes):6.2f}%")
    p(f"  raw (length known, no descriptor):{raw_bytes:8d}  {pct(raw_bytes):6.2f}%")
    p(f"  desync (unknown length / resync): {desync_bytes:8d}  {pct(desync_bytes):6.2f}%")
    clean = named_bytes + raw_bytes
    p(f"  --> cleanly tokenized (len known): {clean:8d}  {pct(clean):6.2f}%")
    p("")
    p("--- TOKEN COUNTS ---")
    p(f"  named={tot_named}  raw={tot_raw}  desync-regions={tot_desync}")
    p("")
    p(f"distinct byte0 groups seen: {len(byte0_all)}")
    p("")
    p("--- per-byte0 DESYNC (unknown-length) LEADERS, ranked by region count ---")
    p("   byte0 : #regions  desync-bytes   sample(16B)")
    for g, c in byte0_desync.most_common():
        p(f"   0x{g:02x} : {c:7d}  {byte0_desync_bytes[g]:10d}   {desync_sample.get(g,'')}")
    p("")
    p("--- per-byte0 RAW (length-only, unnamed) LEADERS, ranked by count ---")
    p("   byte0 : #tokens   sample(8B)")
    for g, c in byte0_raw.most_common():
        p(f"   0x{g:02x} : {c:7d}   {raw_sample.get(g,'')}")
    p("")
    p("--- top named mnemonics ---")
    for mn, c in mnem_count.most_common(30):
        p(f"  {mn:24s} {c}")
    p("")
    p("--- per-project (files / unique / bytes / named% / raw% / desync%) ---")
    p(f"  {'project':14s} {'files':>6s} {'uniq':>6s} {'bytes':>9s} {'named%':>7s} {'raw%':>7s} {'desync%':>8s}")
    for proj in sorted(ppf):
        b = pj_bytes[proj]
        if b == 0:
            p(f"  {proj:14s} {ppf[proj]:6d} {ppu[proj]:6d} {0:9d} {'-':>7s} {'-':>7s} {'-':>8s}")
            continue
        p(f"  {proj:14s} {ppf[proj]:6d} {ppu[proj]:6d} {b:9d} "
          f"{100*pj_named[proj]/b:6.2f}% {100*pj_raw[proj]/b:6.2f}% {100*pj_desync[proj]/b:7.2f}%")

    text = "\n".join(out)
    print(text)
    with open(args.out + ".txt", "w") as f:
        f.write(text + "\n")

    j = dict(
        hexdir=args.hexdir, hex_files=nfiles, unique_programs=len(progs),
        total_bytes=tot_bytes, named_bytes=named_bytes, raw_bytes=raw_bytes,
        desync_bytes=desync_bytes,
        pct_named=pct(named_bytes), pct_raw=pct(raw_bytes), pct_desync=pct(desync_bytes),
        tokens=dict(named=tot_named, raw=tot_raw, desync=tot_desync),
        distinct_byte0=len(byte0_all),
        byte0_desync={f"0x{g:02x}": dict(regions=c, bytes=byte0_desync_bytes[g],
                                         sample=desync_sample.get(g,"")) for g,c in byte0_desync.most_common()},
        byte0_raw={f"0x{g:02x}": dict(tokens=c, sample=raw_sample.get(g,"")) for g,c in byte0_raw.most_common()},
        byte0_named={f"0x{g:02x}": c for g,c in byte0_named.most_common()},
        byte0_all_seen=sorted(f"0x{g:02x}" for g in byte0_all),
        top_mnemonics=mnem_count.most_common(40),
        per_project={proj: dict(files=ppf[proj], unique=ppu[proj], bytes=pj_bytes[proj],
                                named_bytes=pj_named[proj], raw_bytes=pj_raw[proj],
                                desync_bytes=pj_desync[proj]) for proj in sorted(ppf)},
    )
    with open(args.out + ".json", "w") as f:
        json.dump(j, f, indent=2)
    print("\nwrote", args.out + ".txt", "and", args.out + ".json")

if __name__ == "__main__":
    main()
