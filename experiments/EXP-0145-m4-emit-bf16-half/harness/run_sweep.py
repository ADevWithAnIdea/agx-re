#!/usr/bin/env python3
"""EXP-0145 sweep runner.  Usage:
    python3 harness/run_sweep.py <run_id> <FAMILY>[,<FAMILY>...]
Appends one JSON object per case to raw/<run_id>/sweep.jsonl, flushed
immediately, and writes raw/<run_id>/{00_inputs.json,05_run_manifest.json}.

CLEAN-ROOM: OWN-SHADER + HW-PROBE. Only our own compiled shader bytes are
spliced and executed; no Apple binary is introspected.
"""
import os, sys, json, time, struct, hashlib, subprocess, datetime
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lib145 as L, matrix as M, oracles_num as O

EXP = L.EXP
BASE = os.path.join(EXP, 'work', 'base')
BASELINE_EVERY = 250
GLOBAL_HANG_CAP = 10
ARM_HANG_CAP = 2

def now(): return datetime.datetime.now().isoformat(timespec='seconds')

def progress(msg):
    with open(os.path.join(EXP, 'PROGRESS.md'), 'a') as f:
        f.write('- %s  %s\n' % (now(), msg)); f.flush()
    print('[%s] %s' % (now(), msg), flush=True)

def classify(res, oracle_bytes, nbytes, tol=None):
    """-> (outcome, detail, match). outcome uses ONLY the protocol-4 vocabulary."""
    if res['status'] == 'HANG':          return 'hang', 'watchdog', False
    if res['status'] != 'OK':            return 'fault', res['status'], False
    o = bytes.fromhex(res['out']) if res['out'] else b''
    if len(o) < nbytes:                  return 'undecodable', 'short readback', False
    got = o[:nbytes]
    if res['sent'] == 'not_run':         return 'fault', 'sentinel_not_run', False
    if res['sent'] == 'corrupt':         return 'wrong_value', 'sentinel_corrupt', False
    if got == struct.pack('<I', L.POISON)[:nbytes] or \
       (nbytes == 2 and got == b'\xef\xbe'):
        return 'wrong_value', 'store_never_wrote(poison_intact)', False
    if oracle_bytes is not None:
        if got == oracle_bytes:          return 'ok', 'match', True
        if tol is not None and nbytes == 4:
            try:
                g = struct.unpack('<f', got)[0]; e = struct.unpack('<f', oracle_bytes)[0]
                if e == e and abs(g - e) <= tol * max(1.0, abs(e)):
                    return 'ok', 'match_tol', True
            except Exception: pass
    if all(b == 0 for b in got):         return 'silent_zero', 'zero', False
    return 'wrong_value', 'differs', False

class Ctx:
    def __init__(self, run_id):
        self.run_id = run_id
        self.raw = os.path.join(EXP, 'raw', run_id)
        os.makedirs(self.raw, exist_ok=True)
        self.sp = os.path.join(EXP, 'work', run_id, 'sp')
        self.ind = os.path.join(EXP, 'work', run_id, 'in')
        os.makedirs(self.sp, exist_ok=True); os.makedirs(self.ind, exist_ok=True)
        self.f = open(os.path.join(self.raw, 'sweep.jsonl'), 'a')
        self.n = 0; self.hangs = 0; self.faults = []
        self.arms = {}
        self.ins = {}
    def emit(self, rec):
        self.f.write(json.dumps(rec, sort_keys=True) + '\n'); self.f.flush()
        os.fsync(self.f.fileno()); self.n += 1
    def arm(self, cid):
        if cid not in self.arms:
            c = M.CARRIERS[cid]
            io = c['io']
            sets = {s: M.materialise(io, s, self.ind) for s in ('S1', 'S2')}
            self.arms[cid] = L.Arm(cid, os.path.join(EXP, 'kernels', c['src'] + '.metal'),
                                   os.path.join(BASE, cid + '.bin'), sets,
                                   out_bytes=M.OUTB, spdir=self.sp)
        return self.arms[cid]
    def close(self):
        for a in self.arms.values(): a.close()
        self.f.close()

def outw(cid):
    """bytes of the output element under test."""
    return {'C1_bf_f32': 4, 'C2_bfmul_f32': 4, 'C9_fabs': 4, 'C10_orimm': 4,
            'C14_sfutan': 4, 'C8_h2fma': 4, 'C11_bf2': 4, 'C12_hcoord': 4}.get(cid, 2)

def baseline_check(ctx, cid, tries=4):
    a = ctx.arm(cid); nb = outw(cid)
    for t in range(tries):
        ok = True
        for s in ('S1', 'S2'):
            r = a.run(a.buf, s)
            oc, det, m = classify(r, M.oracle(cid, s)[:nb], nb, M.ORACLE_TOL.get(cid))
            if not m: ok = False
        if ok: return True
        time.sleep(0.5 * (t + 1))
    return False

# ------------------------------------------------------------------ families
def run_bytewise(ctx, cases):
    last_cid = None
    for i, c in enumerate(cases):
        cid = c['carrier']; a = ctx.arm(cid); nb = outw(cid)
        if cid != last_cid:
            progress('BYTEWISE arm %s: baseline %s' % (cid, 'OK' if baseline_check(ctx, cid) else 'FAIL'))
            last_cid = cid; a.hangs = 0
        if a.hangs >= ARM_HANG_CAP:
            ctx.emit(dict(instr=M.CARRIERS[cid]['targets'], field='byte+%d' % c['pos'],
                          value=c['value'], bytes='', observed={}, oracle={}, match=False,
                          outcome='hang', carrier=cid, note='ARM STOPPED after %d hangs' % a.hangs,
                          family='BYTEWISE', input_set='-', sentinel='-', gpu_error=None))
            continue
        sp = a.splice(c['pos'], c['value'])
        newb = sp[a.off + c['pos']:a.off + c['pos'] + 1].hex()
        for s in ('S1', 'S2'):
            r = a.run(sp, s)
            orc = M.oracle(cid, s)[:nb]
            oc, det, m = classify(r, orc, nb, M.ORACLE_TOL.get(cid))
            if oc == 'hang': ctx.hangs += 1
            if oc in ('fault', 'hang'): ctx.faults.append((cid, c['pos'], c['value'], s))
            ctx.emit(dict(instr=M.CARRIERS[cid]['targets'], field='byte+%d' % c['pos'],
                          value=c['value'], bytes=newb, observed=dict(out=r['out'], sent=r['sent']),
                          oracle=dict(baseline=orc.hex()), match=m, outcome=oc, detail=det,
                          carrier=cid, family='BYTEWISE', input_set=s,
                          sentinel=r['sent'], gpu_error=r['error'], note=''))
            if oc == 'hang': break
        if ctx.hangs >= GLOBAL_HANG_CAP:
            progress('GLOBAL HANG CAP reached (%d) -- stopping BYTEWISE' % ctx.hangs); return
        if ctx.n % BASELINE_EVERY < 2 and ctx.n:
            if not baseline_check(ctx, cid):
                progress('CASCADE: baseline for %s failed all attempts at n=%d -- STOPPING' % (cid, ctx.n))
                return

def run_generated(ctx, cases):
    cid = 'C3_bf_native'; a = ctx.arm(cid); nb = 2
    progress('GENERATED arm %s: baseline %s' % (cid, 'OK' if baseline_check(ctx, cid) else 'FAIL'))
    for c in cases:
        g = c['gen']; ib = M.bf8(**g)
        sp = a.splice_bytes(c['pos'], ib)
        for s in ('S1', 'S2'):
            v = M.INPUTS['bf2x1'][s]
            ab, bb = L.bf16_rne(v['a']), L.bf16_rne(v['b'])
            # host model: r0.lo = a, r0.hi = b (from the carrier's own dataflow)
            def operand(reg, half, fmt):
                if reg != 0: return None
                bits = bb if half else ab
                if fmt: return ('fp16', bits)
                return ('bf16', bits)
            oa, ob = operand(g['sA'], g['selA'], g['fA']), operand(g['sB'], g['selB'], g['fB'])
            exp = None; oname = 'unpredictable'
            if g['dst'] != 2:
                exp = None; oname = 'dst_not_read_by_store'
            elif oa and ob and g['opsel'] in M.GEN_OPS and g['dsthi'] == 0:
                fa = O.bf_to_frac(oa[1]) if oa[0] == 'bf16' else O.fp_to_frac(oa[1])
                fb = O.bf_to_frac(ob[1]) if ob[0] == 'bf16' else O.fp_to_frac(ob[1])
                if fa is not None and fb is not None:
                    r = fa + fb if M.GEN_OPS[g['opsel']] == 'add' else fa * fb
                    exp = struct.pack('<H', O.frac_to_bf(r) if r != 0 else 0)
                    oname = 'rule_model_%s' % M.GEN_OPS[g['opsel']]
            r = a.run(sp, s)
            oc, det, m = classify(r, exp, nb, None)
            if exp is None: oc = 'wrong_value' if oc == 'ok' else oc; m = False
            if oc == 'hang': ctx.hangs += 1
            ctx.emit(dict(instr='bf_add_dst/bf_mul_dst(generated)',
                          field='full-instruction', value=ib.hex(), bytes=ib.hex(),
                          observed=dict(out=r['out'], sent=r['sent']),
                          oracle=dict(name=oname, expect=exp.hex() if exp else None),
                          match=m, outcome=oc, detail=det, carrier=cid, family='GENERATED',
                          input_set=s, sentinel=r['sent'], gpu_error=r['error'],
                          gen=g, refuter=c.get('refuter'), note=''))

def run_numeric(ctx, cases):
    def wbits(cid, bits, tag):
        io = M.CARRIERS[cid]['io']; d = ctx.ind; out = {}
        def w(i, vals):
            p = os.path.join(d, 'num_%s_%s_%d.bin' % (cid, tag, i))
            open(p, 'wb').write(b''.join(struct.pack('<H', v & 0xFFFF) for v in vals)); out[i] = p
        if io in ('bf2x1', 'h2x1'):
            w(1, [bits['a']] * 8); w(2, [bits['b']] * 8)
        elif io == 'bf3x1':
            w(1, [bits['a']] * 8); w(2, [bits['b']] * 8); w(3, [bits['c']] * 8)
        elif io == 'h3x2':
            w(1, [bits['a'], bits['a']] * 8); w(2, [bits['b'], bits['b']] * 8)
            w(3, [bits['c'], bits['c']] * 8)
        return out
    last = None
    for c in cases:
        cid = c['carrier']; a = ctx.arm(cid); nb = 2
        if cid != last:
            progress('NUMERIC arm %s: baseline %s' % (cid, 'OK' if baseline_check(ctx, cid) else 'FAIL'))
            last = cid
        bits = c['bits']
        ins = wbits(cid, bits, c['case'])
        a.ins_sets['NUM'] = ins
        if cid in ('C3_bf_native',):     cand = O.bf_candidates('add', bits['a'], bits['b'])
        elif cid in ('C4_bfmul_native',):cand = O.bf_candidates('mul', bits['a'], bits['b'])
        elif cid == 'C5_bffma_native':   cand = O.bf_candidates('fma', bits['a'], bits['b'], bits['c'])
        elif cid == 'C6_hmin':           cand = O.fp_minmax_candidates('min', bits['a'], bits['b'])
        elif cid == 'C7_hmax':           cand = O.fp_minmax_candidates('max', bits['a'], bits['b'])
        else:                            cand = O.fp_fma_candidates(bits['a'], bits['b'], bits['c'])
        r = a.run(a.buf, 'NUM')
        got = bytes.fromhex(r['out'])[:nb] if r['out'] else b''
        hits = sorted(k for k, v in cand.items() if v == got)
        oc = 'ok' if hits else ('fault' if r['status'] != 'OK' else
                                ('silent_zero' if got == b'\x00\x00' else 'wrong_value'))
        if r['status'] == 'HANG': oc = 'hang'; ctx.hangs += 1
        ctx.emit(dict(instr=M.CARRIERS[cid]['targets'], field='NUMERIC:' + c['case'],
                      value='a=%04x b=%04x%s' % (bits['a'], bits['b'],
                            ' c=%04x' % bits['c'] if 'c' in bits else ''),
                      bytes='', observed=dict(out=r['out'], bits='%s' % got.hex(), sent=r['sent']),
                      oracle={k: v.hex() for k, v in sorted(cand.items())},
                      match=bool(hits), outcome=oc, detail=','.join(hits) or 'no_candidate',
                      carrier=cid, family='NUMERIC', input_set='NUM', sentinel=r['sent'],
                      gpu_error=r['error'], note=''))

def confirm_faults(ctx):
    """Protocol 7.1: no single fault observation is believed. Re-run each."""
    if not ctx.faults: return
    progress('confirming %d fault observations in isolation' % len(ctx.faults))
    seen = []
    for cid, pos, val, s in ctx.faults[:400]:
        a = ctx.arm(cid); nb = outw(cid)
        sp = a.splice(pos, val)
        r = a.run(sp, s)
        oc, det, m = classify(r, M.oracle(cid, s)[:nb], nb, M.ORACLE_TOL.get(cid))
        ctx.emit(dict(instr=M.CARRIERS[cid]['targets'], field='byte+%d' % pos, value=val,
                      bytes='', observed=dict(out=r['out'], sent=r['sent']), oracle={},
                      match=False, outcome=oc, detail='CONFIRM:' + det, carrier=cid,
                      family='FAULT_CONFIRM', input_set=s, sentinel=r['sent'],
                      gpu_error=r['error'], note='re-run of a fault/hang observation'))

def main():
    run_id = sys.argv[1]; fams = sys.argv[2].split(',')
    ctx = Ctx(run_id)
    rev = subprocess.run(['git', '-C', L.REPO, 'rev-parse', 'HEAD'],
                         capture_output=True, text=True).stdout.strip()
    man = dict(run_id=run_id, families=fams, started=now(), repo_rev=rev,
               matrix_sha256=hashlib.sha256(M.matrix_json().encode()).hexdigest(),
               device='Apple M4 (G16G) local host', harness_sha={
                   f: L.sha(open(os.path.join(HERE, f), 'rb').read())
                   for f in ('lib145.py', 'matrix.py', 'oracles_num.py', 'run_sweep.py')},
               carrier_sha={cid: L.sha(open(os.path.join(BASE, cid + '.bin'), 'rb').read())
                            for cid in M.CARRIERS},
               kernel_sha={cid: L.sha(open(os.path.join(EXP, 'kernels',
                            M.CARRIERS[cid]['src'] + '.metal'), 'rb').read())
                           for cid in M.CARRIERS})
    json.dump(man, open(os.path.join(ctx.raw, '05_run_manifest.json'), 'w'), indent=1, sort_keys=True)
    json.dump({'INPUTS': M.INPUTS, 'BF_PAIRS': M.BF_PAIRS, 'FP_PAIRS': M.FP_PAIRS,
               'FP_FMA_TRIPLES': M.FP_FMA_TRIPLES, 'CARRIERS': M.CARRIERS},
              open(os.path.join(ctx.raw, '00_inputs.json'), 'w'), indent=1, sort_keys=True, default=str)
    t0 = time.time()
    try:
        for fam in fams:
            cases = list(M.FAMILIES[fam]())
            progress('run %s family %s: %d cases' % (run_id, fam, len(cases)))
            {'BYTEWISE': run_bytewise, 'GENERATED': run_generated,
             'NUMERIC': run_numeric}[fam](ctx, cases)
            progress('run %s family %s DONE (%d records, %.0f s)' % (run_id, fam, ctx.n, time.time() - t0))
        confirm_faults(ctx)
    finally:
        progress('run %s finished: %d records, %d hangs, %.0f s' % (run_id, ctx.n, ctx.hangs, time.time() - t0))
        ctx.close()

if __name__ == '__main__':
    main()
