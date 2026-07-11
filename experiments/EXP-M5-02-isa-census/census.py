#!/usr/bin/env python3
# census.py -- EXP-M5-02 byte0-group instruction census of the OWN-MSL corpus
# compiled on Apple M5 (T8142), decoded with the UNMODIFIED G17P (A18) ISA DB.
#
# Same align-forward resync tokenizer as EXP-M4-01: where the DB assigns a length
# it consumes that instruction (recording whether a descriptor also NAMED it);
# where it cannot (LEN_UNKNOWN), it records the leading byte0 as an UNDECODED region
# and advances one 2-byte parcel to resync. Adds M5-delta analysis:
#   - per-byte0 histogram of undecoded/desync leaders, ranked by frequency
#   - top diverging opcodes with example hex contexts + data-driven hypothesis
#   - "silent delta" candidates: NAMED ops that systematically precede a desync
#     (length likely changed on M5) and length_only byte0 groups (unnamed).
#
# CLEAN-ROOM: every byte here is the compiled form of MSL we wrote. No Apple binary
# was disassembled; the DB is the pre-existing G17P descriptor set, used unmodified.
import sys, os, glob, hashlib, collections

# G17P DB location: prefer a sibling tools/agx-isa (device layout) or repo root.
def _find_isadb():
    here = os.path.dirname(os.path.abspath(__file__))
    d = here
    while d != os.path.dirname(d):
        cand = os.path.join(d, 'tools', 'agx-isa')
        if os.path.isfile(os.path.join(cand, 'isadb.py')):
            return cand
        d = os.path.dirname(d)
    # fallback: env or device default
    for cand in (os.environ.get('AGXISA_DIR'),
                 os.path.expanduser('~/cleanroom_work/tools/agx-isa')):
        if cand and os.path.isfile(os.path.join(cand, 'isadb.py')):
            return cand
    raise RuntimeError('isadb.py not found')
sys.path.insert(0, _find_isadb())
import isadb

HEXDIR = os.environ.get('M5_HEXDIR',
             os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hex'))
OUTDIR = os.environ.get('M5_OUTDIR', os.path.dirname(os.path.abspath(__file__)))

def trim_padding(b):
    """Strip trailing region-alignment padding (a run of '06 00' pairs) that
    agxparse includes between _agc.main and the next symbol."""
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
    """Align-forward resync tokenizer. Returns records:
       (off, byte0, length, mnemonic_or_None, status) with status in
       {'named','length_only','undecoded'}."""
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

def main():
    files = sorted(glob.glob(os.path.join(HEXDIR, '*.hex')))
    streams = []
    seen_hash = {}
    dup = 0
    for f in files:
        name = os.path.basename(f)[:-4]
        h = open(f).read().strip()
        if not h:
            continue
        b = trim_padding(bytes.fromhex(h))
        if not b:
            continue
        hh = hashlib.sha256(b).hexdigest()
        if hh in seen_hash:
            dup += 1
            streams.append((name, b, True, seen_hash[hh]))
        else:
            seen_hash[hh] = name
            streams.append((name, b, False, None))

    tot_instr = tot_named = tot_length_only = tot_undecoded = 0
    tot_bytes = cov_bytes = undec_bytes = 0
    byte0_all = collections.Counter()
    byte0_named = collections.Counter()
    byte0_lenonly = collections.Counter()
    byte0_undec = collections.Counter()
    undec_samples = collections.defaultdict(list)   # byte0 -> [hex context ...]
    mnem_count = collections.Counter()
    # silent-delta: how often a NAMED mnemonic is immediately followed by a desync
    mnem_total = collections.Counter()
    mnem_pre_desync = collections.Counter()
    b0_named_ctx = collections.defaultdict(list)     # byte0 -> sample named contexts

    for name, b, is_dup, orig in streams:
        if is_dup:
            continue
        recs = walk(b)
        for i, (off, b0, L, mn, status) in enumerate(recs):
            byte0_all[b0] += 1
            nxt_desync = (i+1 < len(recs) and recs[i+1][4] == 'undecoded')
            if status == 'named':
                tot_named += 1; cov_bytes += L; byte0_named[b0] += 1; mnem_count[mn] += 1
                mnem_total[mn] += 1
                if nxt_desync:
                    mnem_pre_desync[mn] += 1
                if len(b0_named_ctx[b0]) < 2:
                    b0_named_ctx[b0].append((mn, b[off:off+L].hex(' ')))
            elif status == 'length_only':
                tot_length_only += 1; cov_bytes += L; byte0_lenonly[b0] += 1
            else:
                tot_undecoded += 1; byte0_undec[b0] += 1; undec_bytes += L
                if len(undec_samples[b0]) < 4:
                    # region bytes + a little following context
                    undec_samples[b0].append(b[off:off+min(L,12)].hex(' '))
        tot_bytes += len(b)
    tot_instr = tot_named + tot_length_only + tot_undecoded

    uniq = sum(1 for _, _, d, _ in streams if not d)
    out = []
    def p(s=''): out.append(s)
    p("="*76)
    p("EXP-M5-02  BYTE0 INSTRUCTION CENSUS  --  Apple M5 (T8142) corpus vs G17P/A18 DB")
    p("="*76)
    p(f"corpus: {len(streams)} extracted stage programs "
      f"({uniq} unique, {dup} duplicate stages)")
    p(f"instructions walked (unique streams): {tot_instr}")
    if tot_instr == 0:
        print("\n".join(out)); return
    p(f"  named (matched a G17P descriptor):    {tot_named:6d}  ({100*tot_named/tot_instr:.2f}%)")
    p(f"  length-only (length known, unnamed):  {tot_length_only:6d}  ({100*tot_length_only/tot_instr:.2f}%)")
    p(f"  UNDECODED regions (desync/unknown):   {tot_undecoded:6d}  ({100*tot_undecoded/tot_instr:.2f}%)")
    clean = tot_named + tot_length_only
    p(f"  --> cleanly tokenized (length known): {clean}/{tot_instr} = {100*clean/tot_instr:.2f}% of tokens")
    p(f"  --> FULLY-NAMED:                      {tot_named}/{tot_instr} = {100*tot_named/tot_instr:.2f}% of tokens")
    p(f"  --> BYTE COVERAGE (named+lenonly):    {cov_bytes}/{tot_bytes} = {100*cov_bytes/tot_bytes:.2f}% of bytes")
    p(f"      undecoded bytes:                  {undec_bytes}/{tot_bytes} = {100*undec_bytes/tot_bytes:.2f}%")
    p()
    p(f"distinct byte0 groups seen: {len(byte0_all)}")
    decoded_groups = sorted(g for g in byte0_all if byte0_named[g] or byte0_lenonly[g])
    fully_undec = sorted(g for g in byte0_all if g not in decoded_groups)
    p(f"  byte0 groups the DB CAN length/name somewhere: {len(decoded_groups)}")
    p(f"  byte0 groups NEVER decoded (pure gaps):        {len(fully_undec)}"
      f"  {['0x%02x'%g for g in fully_undec]}")
    p()

    # ---- (b) per-byte0 histogram of UNDECODED/desync leaders, ranked ----
    p("-"*76)
    p("(b) UNDECODED/DESYNC byte0 HISTOGRAM (ranked by resync-region count)")
    p("    columns: byte0 | undec_regions | undec_bytes | also_named_elsewhere | also_lenonly")
    p("-"*76)
    b0_undec_bytes = collections.Counter()
    # recompute per-byte0 undecoded bytes
    # (undec_bytes above is global; recompute per group by re-walking is costly, so
    #  approximate per-group bytes from samples is wrong -> track precisely below.)
    # We instead recompute here cheaply using stored counts is not enough; do a 2nd pass:
    for name, b, is_dup, orig in streams:
        if is_dup: continue
        for (off, b0, L, mn, status) in walk(b):
            if status == 'undecoded':
                b0_undec_bytes[b0] += L
    for g, c in byte0_undec.most_common():
        p(f"  0x{g:02x} | regions={c:5d} | bytes={b0_undec_bytes[g]:6d} | "
          f"named_elsewhere={byte0_named[g]:5d} | lenonly={byte0_lenonly[g]:4d}")
    p()

    # ---- (c) TOP diverging opcodes: prioritized delta table ----
    p("-"*76)
    p("(c) TOP DIVERGING byte0 LEADERS  (prioritized delta list)")
    p("-"*76)
    for rank, (g, c) in enumerate(byte0_undec.most_common(20), 1):
        also_named = byte0_named[g]
        also_len = byte0_lenonly[g]
        if also_named == 0 and also_len == 0:
            hyp = ("UNKNOWN LEADER: byte0 0x%02x is never length-resolved anywhere in "
                   "the M5 corpus. Candidate NEW opcode/leader on M5, or a G17P op whose "
                   "length rule no longer fires (relocated match bits)." % g)
        elif also_named > 0:
            hyp = ("KNOWN LEADER, VARIANT DIVERGES: byte0 0x%02x decodes+NAMES in %d other "
                   "contexts but desyncs here -> a specific sub-encoding (op-select/modifier) "
                   "or the length of a variant changed on M5." % (g, also_named))
        else:
            hyp = ("LENGTH-ONLY LEADER: byte0 0x%02x gets a length in %d places but is never "
                   "NAMED; here even the length rule fails -> field/length delta on a "
                   "descriptor-less form." % (g, also_len))
        p(f"[{rank:2d}] byte0=0x{g:02x}  regions={c}  bytes={b0_undec_bytes[g]}")
        p(f"     hypothesis: {hyp}")
        for s in undec_samples[g][:3]:
            p(f"     ctx: {s}")
        if b0_named_ctx[g]:
            mn, hx = b0_named_ctx[g][0]
            p(f"     (same byte0 NAMED elsewhere as '{mn}': {hx})")
        p()

    # ---- (d) SILENT-DELTA candidates: named ops that precede a desync ----
    p("-"*76)
    p("(d) SILENT-DELTA CANDIDATES  (NAMED ops that systematically precede a desync;")
    p("    a mis-length/mis-decode on M5 would corrupt the FOLLOWING token)")
    p("    columns: mnemonic | pre_desync / total | ratio")
    p("-"*76)
    rows = []
    for mn, tot in mnem_total.items():
        pd = mnem_pre_desync[mn]
        if pd >= 2 and tot >= 2 and pd/tot >= 0.25:
            rows.append((pd/tot, pd, tot, mn))
    rows.sort(reverse=True)
    if not rows:
        p("  (none: no NAMED mnemonic reliably precedes a desync -> no obvious silent length delta)")
    for ratio, pd, tot, mn in rows[:25]:
        p(f"  {mn:24s} {pd:4d}/{tot:<5d}  {100*ratio:.0f}%")
    p()
    p("    length-only byte0 groups (length known but NO descriptor names them -> "
      "decode-but-unnamed, candidate silent deltas):")
    for g in sorted(byte0_lenonly):
        if byte0_lenonly[g]:
            p(f"      0x{g:02x}: length_only={byte0_lenonly[g]:4d}  named={byte0_named[g]:4d}")
    p()

    # ---- top named mnemonics (sanity) ----
    p("-"*76)
    p("top NAMED mnemonics (sanity check the decode is meaningful)")
    p("-"*76)
    for mn, c in mnem_count.most_common(30):
        p(f"  {mn:26s} {c}")
    p()

    text = "\n".join(out)
    print(text)
    os.makedirs(OUTDIR, exist_ok=True)
    with open(os.path.join(OUTDIR, 'census.txt'), 'w') as f:
        f.write(text + "\n")

if __name__ == "__main__":
    main()
