#!/usr/bin/env python3
# EXP-M5-03 third-party MSL corpus compile+extract harness (runs ON the M5 device).
# Clean-room: compiles ONLY permissive third-party MSL we are licensed to compile,
# using our OWN shdump (builds an MTLBinaryArchive; never dispatches -> no GPU hang),
# and extracts _agc.main with our OWN agxparse.py. No Apple binary is introspected.
# COMPILE-ONLY, no GPU dispatch, no git.
import os, re, sys, subprocess, tempfile, threading, json, collections
from concurrent.futures import ThreadPoolExecutor

HOME     = os.path.expanduser("~")
EXP      = os.path.join(HOME, "cleanroom_work/EXP-M5-03")
SRC      = os.path.join(EXP, "src")
HEXDIR   = os.path.join(EXP, "tp_hex")
WORK     = os.path.join(EXP, "work")
SHDUMP   = os.path.join(HOME, "cleanroom_work/tools/shdump/shdump")
AGXPARSE = os.path.join(HOME, "cleanroom_work/tools/shdump/agxparse.py")
NWORK    = 8
CTIMEOUT = 60   # per-compile seconds

os.makedirs(HEXDIR, exist_ok=True)
os.makedirs(WORK, exist_ok=True)

find = subprocess.run(
    r'find "%s" -type f \( -name "*.metal" -o -name "*.msl" \) | sort' % SRC,
    shell=True, capture_output=True, text=True)
allfiles = [l for l in find.stdout.splitlines() if l.strip()]

RE_KERNEL   = re.compile(r'\bkernel\s')
RE_VERTEX   = re.compile(r'\bvertex\s')
RE_FRAGMENT = re.compile(r'\bfragment\s')

def read_src(f):
    try:
        with open(f, 'r', encoding='utf-8', errors='ignore') as fh:
            return fh.read()
    except Exception:
        return ""

def san(s):
    return re.sub(r'[^A-Za-z0-9._-]', '_', s)

def project_of(f):
    rel = os.path.relpath(f, SRC)
    return rel.split(os.sep)[0]

def hexname(f, stage):
    rel = os.path.relpath(f, SRC)
    parts = rel.split(os.sep)
    project = parts[0]
    sub = os.sep.join(parts[1:]) if len(parts) > 1 else parts[0]
    return os.path.join(HEXDIR, "tp__%s__%s__%s.hex" % (san(project), san(sub), stage))

def run(cmd):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=CTIMEOUT)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "shdump: TIMEOUT after %ds" % CTIMEOUT

def extract(binpath, stage):
    if stage == 'compute':
        cmd = ['python3', AGXPARSE, binpath, '--extract-hex']
    else:
        cmd = ['python3', AGXPARSE, binpath, '--stage', stage, '--extract-hex']
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return None
    if p.returncode != 0:
        return None
    h = p.stdout.strip()
    return h if h else None

lock = threading.Lock()
# per-project counters
proj = collections.defaultdict(lambda: dict(files=0, ok=0, hex=0, failed=0, lone=0, noentry=0))
cls_counts = collections.Counter()
samples = {}

def bump(project, key, n=1):
    with lock:
        proj[project][key] += n

def record_fail(project, err):
    cls, sample = classify(err)
    with lock:
        proj[project]['failed'] += 1
        cls_counts[cls] += 1
        if cls not in samples:
            samples[cls] = sample

def classify(err):
    lines = [l.strip() for l in err.splitlines() if l.strip()]
    first = None
    for ln in lines:
        if 'error:' in ln.lower():
            first = ln; break
    if first is None:
        for ln in lines:
            if ln.startswith('shdump:'):
                first = ln
        if first is None:
            first = lines[-1] if lines else 'unknown'
    low = first.lower()
    if 'timeout' in low: cls = 'compile-timeout'
    elif 'file not found' in low or 'metal_stdlib' in low or "'metal/" in low: cls = 'include-not-found'
    elif ('no kernel function' in low or 'no vertex function' in low
          or 'no fragment function' in low or 'named function not found' in low): cls = 'no-entry-point'
    elif 'metal language version' in low or ('metal' in low and 'version' in low): cls = 'msl-version'
    elif 'unsupported' in low or 'not supported' in low or 'requires' in low or 'unavailable' in low or 'deprecated' in low: cls = 'unsupported-feature'
    elif ('undeclared identifier' in low or 'unknown type name' in low or 'no member' in low
          or 'no matching' in low or 'expected' in low or 'unknown attribute' in low
          or 'redefinition' in low or "did you mean" in low or 'call to' in low): cls = 'parse-error'
    elif 'binding' in low or 'buffer' in low or 'argument' in low or 'attribute' in low or 'index' in low: cls = 'missing-binding'
    elif 'pipeline' in low: cls = 'pipeline-creation'
    else: cls = 'other'
    return cls, first[:240]

def write_hex(f, stage, h):
    with open(hexname(f, stage), 'w') as fh:
        fh.write(h + "\n")
    bump(project_of(f), 'hex')

def do_compute(f, tmp):
    rc, out, err = run([SHDUMP, '-o', tmp, f])
    if rc == 0:
        bump(project_of(f), 'ok')
        h = extract(tmp, 'compute')
        if h: write_hex(f, 'compute', h)
        return True, err
    return False, err

def do_render(f, tmp):
    rc, out, err = run([SHDUMP, '-o', tmp, '--render', f])
    if rc == 0:
        bump(project_of(f), 'ok')
        for st in ('vertex', 'fragment'):
            h = extract(tmp, st)
            if h: write_hex(f, st, h)
        return True, err
    return False, err

def process(f):
    project = project_of(f)
    bump(project, 'files')
    src = read_src(f)
    hk = bool(RE_KERNEL.search(src))
    hv = bool(RE_VERTEX.search(src))
    hf = bool(RE_FRAGMENT.search(src))
    fd, tmp = tempfile.mkstemp(suffix='.bin', dir=WORK)
    os.close(fd)
    try:
        if hk:
            ok, err = do_compute(f, tmp)
            if ok: return
            if 'no kernel function' in err.lower():
                if hv and hf:
                    ok2, err2 = do_render(f, tmp)
                    if ok2: return
                    e2 = err2.lower()
                    if 'no vertex function' in e2 or 'no fragment function' in e2:
                        bump(project, 'lone'); return
                    record_fail(project, err2); return
                elif hv or hf:
                    bump(project, 'lone'); return
                else:
                    bump(project, 'noentry'); return
            record_fail(project, err); return
        elif hv and hf:
            ok, err = do_render(f, tmp)
            if ok: return
            e = err.lower()
            if 'no vertex function' in e or 'no fragment function' in e:
                bump(project, 'lone'); return
            record_fail(project, err); return
        elif hv or hf:
            bump(project, 'lone'); return
        else:
            bump(project, 'noentry'); return
    finally:
        try: os.remove(tmp)
        except OSError: pass

def main():
    total = len(allfiles)
    done = [0]
    def wrap(f):
        try:
            process(f)
        except Exception as e:
            record_fail(project_of(f), 'harness: %s' % repr(e)[:180])
        with lock:
            done[0] += 1
            if done[0] % 500 == 0:
                sys.stderr.write("...%d/%d\n" % (done[0], total)); sys.stderr.flush()
    with ThreadPoolExecutor(max_workers=NWORK) as ex:
        list(ex.map(wrap, allfiles))

    summary = dict(total_files=total, per_project={}, class_counts=dict(cls_counts), samples=samples)
    agg = dict(files=0, ok=0, hex=0, failed=0, lone=0, noentry=0)
    for pj in sorted(proj):
        d = dict(proj[pj]); summary['per_project'][pj] = d
        for k in agg: agg[k] += d.get(k, 0)
    summary['aggregate'] = agg
    with open(os.path.join(EXP, 'compile_summary.json'), 'w') as fh:
        json.dump(summary, fh, indent=2)

    print("=== EXP-M5-03 compile summary ===")
    print("total files: %d" % total)
    print("%-14s %7s %5s %5s %6s %5s %6s" % ("project","files","ok","hex","failed","lone","noent"))
    for pj in sorted(proj):
        d = proj[pj]
        print("%-14s %7d %5d %5d %6d %5d %6d" % (pj, d['files'], d['ok'], d['hex'], d['failed'], d['lone'], d['noentry']))
    print("%-14s %7d %5d %5d %6d %5d %6d" % ("TOTAL", agg['files'], agg['ok'], agg['hex'], agg['failed'], agg['lone'], agg['noentry']))
    print("hex files written:", agg['hex'])
    print("class_counts:", dict(cls_counts.most_common()))

if __name__ == '__main__':
    main()
