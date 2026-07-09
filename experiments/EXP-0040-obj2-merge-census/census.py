#!/usr/bin/env python3
# census.py -- EXP-0040 byte0-group instruction census over the OWN-SHADER corpus,
# re-run with the tools/agx-isa DB AFTER merging the EXP-O2C + EXP-O2D
# ("objective-2") descriptors. Same align-forward resync tokenizer as
# EXP-0036/EXP-0039; the DB is the merged one.
#
# Corpus = the reused EXP-0036 hex set (the SAME 61 extracted stage _agc.main
# programs -- so the delta on that subcorpus is attributable purely to the merge)
# PLUS the NEW objective-2 kernel families (RT / tensor / MPP matrix / bfloat /
# imageblock-tile) extracted by extract_new_hex.py into ./hex/.
#
# Reports three views: the EXP-0036 subcorpus (apples-to-apples vs EXP-0039's
# 87.9%), the NEW families alone, and the combined corpus.
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

HERE = os.path.dirname(os.path.abspath(__file__))
# Reuse the EXP-0036 corpus (same broad set of extracted stage programs).
BASEDIR = os.path.normpath(os.path.join(HERE, '..', 'EXP-0036-consolidation-census', 'hex'))
# The new objective-2 families extracted locally.
NEWDIR = os.path.join(HERE, 'hex')

def trim_padding(b):
    """Strip trailing region-alignment padding (a run of '06 00' pairs)."""
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
        return L, None                   # length known, no descriptor

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

def category(name):
    if name.startswith('k_tex'):        return 'compute:texture'
    if name.startswith('tensor_') or name.startswith('mpp_'): return 'objective2:matrix/tensor'
    if name.startswith('rt_'):          return 'objective2:raytracing'
    if name.startswith('bf_'):          return 'objective2:bfloat'
    if name.startswith('tile_'):        return 'objective2:imageblock-tile'
    if name.endswith('_vertex'):        return 'render:vertex'
    if name.endswith('_fragment'):      return 'render:fragment'
    if name.startswith('mesh_'):        return 'mesh'
    if name == 'k_fptr':                 return 'compute:function-table'
    return 'compute:core'

def load_streams(hexdir, seen_hash):
    streams = []
    dup = 0
    for f in sorted(glob.glob(os.path.join(hexdir, '*.hex'))):
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
    return streams, dup

def tally(streams):
    """Return per-stream + aggregate tallies for a list of (name,b,is_dup,orig)."""
    t = dict(instr=0, named=0, lenonly=0, undec=0, bytes=0, cov=0, undec_bytes=0)
    byte0_all = collections.Counter(); byte0_named = collections.Counter()
    byte0_lenonly = collections.Counter(); byte0_undec = collections.Counter()
    undec_samples = {}; mnem_count = collections.Counter()
    cat_cov = collections.Counter(); cat_tot = collections.Counter()
    per_stream = []
    for name, b, is_dup, orig in streams:
        if is_dup:
            per_stream.append((name, len(b), None, None, f"dup of {orig}"))
            continue
        recs = walk(b)
        s_named = s_len = s_undec = s_cov = 0
        for (off, b0, L, mn, status) in recs:
            byte0_all[b0] += 1
            if status == 'named':
                s_named += 1; s_cov += L; byte0_named[b0] += 1; mnem_count[mn] += 1
            elif status == 'length_only':
                s_len += 1; s_cov += L; byte0_lenonly[b0] += 1
            else:
                s_undec += 1; byte0_undec[b0] += 1; t['undec_bytes'] += L
                undec_samples.setdefault(b0, b[off:off+16].hex(' '))
        t['instr'] += s_named + s_len + s_undec
        t['named'] += s_named; t['lenonly'] += s_len; t['undec'] += s_undec
        t['bytes'] += len(b); t['cov'] += s_cov
        cat = category(name); cat_cov[cat] += s_cov; cat_tot[cat] += len(b)
        per_stream.append((name, len(b), s_named + s_len + s_undec, s_undec,
                           f"cov {100*s_cov/len(b):.0f}%"))
    return dict(t=t, byte0_all=byte0_all, byte0_named=byte0_named,
                byte0_lenonly=byte0_lenonly, byte0_undec=byte0_undec,
                undec_samples=undec_samples, mnem_count=mnem_count,
                cat_cov=cat_cov, cat_tot=cat_tot, per_stream=per_stream)

def main():
    out = []
    def p(s=''): out.append(s)

    seen = {}
    base_streams, base_dup = load_streams(BASEDIR, seen)
    new_streams, new_dup = load_streams(NEWDIR, seen)

    base = tally(base_streams)
    new = tally(new_streams)
    comb = tally(base_streams + new_streams)   # fresh dedup already applied via `seen`

    def headline(label, R):
        t = R['t']
        clean = t['named'] + t['lenonly']
        p(f"--- {label} ---")
        p(f"  streams: {sum(1 for s in R['per_stream'] if s[4] and not s[4].startswith('dup'))} unique")
        p(f"  instructions walked:            {t['instr']}")
        p(f"    named (matched a descriptor):   {t['named']:5d}  ({pct(t['named'],t['instr'])})")
        p(f"    length-only (length, no desc):  {t['lenonly']:5d}  ({pct(t['lenonly'],t['instr'])})")
        p(f"    UNDECODED resync regions:       {t['undec']:5d}  ({pct(t['undec'],t['instr'])})")
        p(f"    --> cleanly tokenized:          {clean}/{t['instr']} = {pct(clean,t['instr'])}")
        p(f"    --> BYTE COVERAGE:              {t['cov']}/{t['bytes']} = {pct(t['cov'],t['bytes'])} "
          f"({t['undec_bytes']} bytes / {pct(t['undec_bytes'],t['bytes'])} undecoded)")
        p()

    def pct(a, b):
        return f"{100*a/b:.1f}%" if b else "n/a"

    p("=" * 78)
    p("EXP-0040  BYTE0-GROUP INSTRUCTION CENSUS  (merged objective-2 tools/agx-isa DB)")
    p("=" * 78)
    p(f"DB: {len(isadb.DB)} descriptors.  Corpus = EXP-0036 subcorpus ({sum(1 for _,_,d,_ in base_streams if not d)} "
      f"unique) + NEW objective-2 families ({sum(1 for _,_,d,_ in new_streams if not d)} unique: RT/tensor/MPP/bfloat/tile).")
    p()
    headline("A. EXP-0036 SUBCORPUS (apples-to-apples vs EXP-0039 = 87.9% bytes)", base)
    headline("B. NEW objective-2 families ONLY (RT / tensor / MPP / bfloat / imageblock-tile)", new)
    headline("C. COMBINED corpus", comb)

    p("--- byte coverage by stage category (COMBINED) ---")
    for cat in sorted(comb['cat_tot']):
        p(f"  {cat:28s} {comb['cat_cov'][cat]:6d}/{comb['cat_tot'][cat]:6d} = {pct(comb['cat_cov'][cat],comb['cat_tot'][cat])}")
    p()

    ba = comb['byte0_all']; bn = comb['byte0_named']; bl = comb['byte0_lenonly']; bu = comb['byte0_undec']
    decoded_groups = sorted(g for g in ba if bn[g] or bl[g])
    fully_undec = sorted(g for g in ba if g not in decoded_groups)
    p(f"distinct byte0 groups seen (COMBINED): {len(ba)}")
    p(f"  byte0 groups the DB CAN length/decode:    {len(decoded_groups)}")
    p(f"  byte0 groups the DB CANNOT decode at all: {len(fully_undec)}")
    p()
    p("--- byte0 groups DECODED (group: named/length-only counts, COMBINED) ---")
    for g in decoded_groups:
        p(f"  0x{g:02x}: named={bn[g]:5d} length_only={bl[g]:4d}")
    p()
    p("--- byte0 groups still UNDECODED (the residue, COMBINED) ---")
    p("   (byte0: resync-count, hex sample of the undecoded region)")
    for g, c in bu.most_common():
        p(f"  0x{g:02x}:  count={c:4d}   sample: {comb['undec_samples'].get(g,'')}")
    p()
    p("--- top named mnemonics (COMBINED) ---")
    for mn, c in comb['mnem_count'].most_common(40):
        p(f"  {mn:22s} {c}")
    p()
    p("--- per-stream coverage (COMBINED) ---")
    for (name, nb, ni, nu, note) in comb['per_stream']:
        if ni is None:
            p(f"  {name:28s} {nb:6d}B   {note}")
        else:
            p(f"  {name:28s} {nb:6d}B  {ni:4d} instr  undecoded={nu:3d}  {note}")

    text = "\n".join(out)
    print(text)
    rawdir = os.path.join(HERE, 'raw')
    os.makedirs(rawdir, exist_ok=True)
    with open(os.path.join(rawdir, 'census.txt'), 'w') as f:
        f.write(text + "\n")

if __name__ == "__main__":
    main()
