#!/usr/bin/env python3
# census.py -- EXP-0036 byte0-group instruction census over the OWN-SHADER corpus.
#
# For every extracted stage (_agc.main) in hex/, walk the byte stream with the
# merged tools/agx-isa length rule + descriptor DB. This is a RESYNC tokenizer:
# where the DB assigns a length it consumes that instruction (recording whether a
# descriptor also NAMED it); where it cannot (LEN_UNKNOWN / no length), it records
# the leading byte as an UNDECODED group and advances one 2-byte parcel to resync,
# so one gap does not blind the rest of the stream. The objective "how complete is
# the ISA" number is: what fraction of instruction bytes the DB can length/decode,
# and which byte0 groups it still cannot.
#
# CLEAN-ROOM: every byte here is from the compiled form of MSL we wrote (OWN-SHADER).
import sys, os, glob, hashlib, collections

# --- portable repo root (repo was relocated; anchor to a sentinel, not a hardcoded path) ---
import os
def _repo_root(start):
    d = os.path.abspath(start)
    while d != os.path.dirname(d):
        if os.path.isfile(os.path.join(d, 'CLAUDE.md')) and os.path.isdir(os.path.join(d, 'tools', 'agx-isa')):
            return d
        d = os.path.dirname(d)
    raise RuntimeError('repo root not found from ' + start)
_REPO = _repo_root(os.path.dirname(os.path.abspath(__file__)))
# --- end portable repo root ---
sys.path.insert(0, os.path.join(_REPO, 'tools', 'agx-isa'))
import isadb

HEXDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hex')

def trim_padding(b):
    """Strip trailing region-alignment padding (a run of '06 00' pairs) that
    agxparse includes between _agc.main and the next symbol. Real programs end at
    the '0e 00 00 00' stop; only the fptr region carries this padding."""
    end = len(b)
    while end >= 2 and b[end-2:end] == b'\x06\x00':
        end -= 2
    return b[:end]

def _named_at(buf, off, n):
    """Length + a MATCHED descriptor at off, or (None, None)."""
    L = isadb.instr_length(buf, off)
    if L is None or off + L > n:
        return None, None
    try:
        rec, _ = isadb.decode_one(buf, off)
        return L, rec['mnemonic']
    except ValueError:
        return L, None                   # length known, no descriptor

def walk(buf):
    """Align-forward resync tokenizer. Returns per-instruction records:
       (off, byte0, length, mnemonic_or_None, status)
       status in {'named','length_only','undecoded'}.
    A NAMED op (descriptor matched) or a LENGTH-ONLY op (length rule gives a length)
    is consumed in-sequence. When neither, we are at an undecoded leader: skip 2-byte
    parcels forward until the next position that a descriptor NAMES, and record the
    whole skipped span as ONE undecoded region attributed to its leading byte0 -- so
    operand bytes of an undecodable op are not miscounted as separate instructions."""
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
        # undecoded leader: skip forward to the next descriptor-NAMED instruction.
        start = off
        off += 2
        while off < n:
            L2, mn2 = _named_at(buf, off, n)
            if mn2 is not None:
                break
            off += 2
        recs.append((start, b0, off - start, None, 'undecoded'))
    return recs

def main():
    files = sorted(glob.glob(os.path.join(HEXDIR, '*.hex')))
    streams = []            # (name, bytes)
    seen_hash = {}
    dup = 0
    for f in files:
        name = os.path.basename(f)[:-4]
        h = open(f).read().strip()
        if not h:
            continue
        b = trim_padding(bytes.fromhex(h))
        hh = hashlib.sha256(b).hexdigest()
        if hh in seen_hash:
            dup += 1
            streams.append((name, b, True, seen_hash[hh]))
        else:
            seen_hash[hh] = name
            streams.append((name, b, False, None))

    # Aggregate over UNIQUE stage-programs (dedup identical vertex stages etc.).
    tot_instr = tot_named = tot_length_only = tot_undecoded = 0
    tot_bytes = cov_bytes = undec_bytes = 0
    byte0_all = collections.Counter()          # every byte0 seen (aligned attempts)
    byte0_named = collections.Counter()
    byte0_lenonly = collections.Counter()
    byte0_undec = collections.Counter()
    undec_samples = {}                          # byte0 -> hex sample (16 bytes)
    mnem_count = collections.Counter()
    per_stream = []
    cat_cov = collections.Counter()      # category -> covered bytes
    cat_tot = collections.Counter()      # category -> total bytes

    def category(name):
        if name.startswith('k_tex'):        return 'compute:texture'
        if name.endswith('_vertex'):        return 'render:vertex'
        if name.endswith('_fragment'):      return 'render:fragment'
        if name.startswith('mesh_'):        return 'mesh'
        if name == 'k_fptr':                 return 'compute:function-table'
        return 'compute:core'

    for name, b, is_dup, orig in streams:
        if is_dup:
            per_stream.append((name, len(b), None, None, f"dup of {orig}"))
            continue
        recs = walk(b)
        s_named = s_len = s_undec = 0
        s_cov = 0
        for (off, b0, L, mn, status) in recs:
            byte0_all[b0] += 1
            if status == 'named':
                s_named += 1; s_cov += L; byte0_named[b0] += 1; mnem_count[mn] += 1
            elif status == 'length_only':
                s_len += 1; s_cov += L; byte0_lenonly[b0] += 1
            else:
                s_undec += 1; byte0_undec[b0] += 1; undec_bytes += L
                undec_samples.setdefault(b0, b[off:off+16].hex(' '))
        tot_instr += (s_named + s_len + s_undec)
        tot_named += s_named; tot_length_only += s_len; tot_undecoded += s_undec
        tot_bytes += len(b); cov_bytes += s_cov
        cat = category(name); cat_cov[cat] += s_cov; cat_tot[cat] += len(b)
        per_stream.append((name, len(b), s_named + s_len + s_undec, s_undec,
                           f"cov {100*s_cov/len(b):.0f}%"))

    uniq = sum(1 for _, _, d, _ in streams if not d)
    out = []
    def p(s=''): out.append(s)
    p("="*74)
    p("EXP-0036  BYTE0-GROUP INSTRUCTION CENSUS  (merged tools/agx-isa DB)")
    p("="*74)
    p(f"corpus: {len(streams)} extracted stage programs ({uniq} unique, {dup} duplicate "
      f"vertex/other stages)")
    p(f"total instructions walked (unique): {tot_instr}")
    p(f"  named (matched a descriptor):        {tot_named:5d}  ({100*tot_named/tot_instr:.1f}%)")
    p(f"  length-only (clean length, no desc): {tot_length_only:5d}  ({100*tot_length_only/tot_instr:.1f}%)")
    p(f"  UNDECODED regions (resync spans):    {tot_undecoded:5d}  ({100*tot_undecoded/tot_instr:.1f}%)")
    clean = tot_named + tot_length_only
    p(f"  --> cleanly tokenized (length known): {clean}/{tot_instr} = {100*clean/tot_instr:.1f}% of tokens")
    p(f"  --> BYTE COVERAGE: {cov_bytes}/{tot_bytes} = {100*cov_bytes/tot_bytes:.1f}% of instruction bytes "
      f"decoded ({undec_bytes} bytes / {100*undec_bytes/tot_bytes:.1f}% in undecoded regions)")
    p()
    p("--- byte coverage by stage category ---")
    for cat in sorted(cat_tot):
        p(f"  {cat:26s} {cat_cov[cat]:5d}/{cat_tot[cat]:5d} = {100*cat_cov[cat]/cat_tot[cat]:.1f}%")
    p()
    p(f"distinct byte0 groups seen: {len(byte0_all)}")
    decoded_groups = sorted(g for g in byte0_all if byte0_named[g] or byte0_lenonly[g])
    fully_undec = sorted(g for g in byte0_all if g not in decoded_groups)
    p(f"  byte0 groups the DB CAN length/decode: {len(decoded_groups)}")
    p(f"  byte0 groups the DB CANNOT decode at all: {len(fully_undec)}")
    p()
    p("--- byte0 groups DECODED (group: named/length-only counts, top mnemonics) ---")
    for g in decoded_groups:
        nm = byte0_named[g]; lo = byte0_lenonly[g]
        p(f"  0x{g:02x}: named={nm:4d} length_only={lo:4d}")
    p()
    p("--- byte0 groups still UNDECODED (the ISA gaps) ---")
    p("   (byte0: resync-count, hex sample of the undecoded region)")
    # sort by count desc
    for g, c in byte0_undec.most_common():
        p(f"  0x{g:02x}:  count={c:4d}   sample: {undec_samples.get(g,'')}")
    p()
    p("--- top named mnemonics ---")
    for mn, c in mnem_count.most_common(25):
        p(f"  {mn:20s} {c}")
    p()
    p("--- per-stage coverage ---")
    for (name, nb, ni, nu, note) in per_stream:
        if ni is None:
            p(f"  {name:22s} {nb:5d}B   {note}")
        else:
            p(f"  {name:22s} {nb:5d}B  {ni:3d} instr  undecoded={nu:2d}  {note}")

    text = "\n".join(out)
    print(text)
    rawdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'raw')
    os.makedirs(rawdir, exist_ok=True)
    with open(os.path.join(rawdir, 'census.txt'), 'w') as f:
        f.write(text + "\n")

if __name__ == "__main__":
    main()
