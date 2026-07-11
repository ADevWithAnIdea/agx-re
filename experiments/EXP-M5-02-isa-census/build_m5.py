#!/usr/bin/env python3
# build_m5.py -- EXP-M5-02: compile OUR-OWN MSL corpus on the M5, extract _agc.main hex.
# CLEAN-ROOM: our own shdump + our own agxparse over MSL we wrote. NO GPU dispatch.
# Walks m4_13/ and m4_14/ corpus trees, detects kernel/vertex/fragment functions,
# compiles each, and extracts the AGX bytes of each stage into hex/.
import os, re, sys, json, subprocess, collections

BASE   = os.path.expanduser("~/cleanroom_work/EXP-M5-02")
CROOT  = os.path.expanduser("~/cleanroom_work")
SHDUMP = os.path.join(CROOT, "tools/shdump/shdump")
AGXP   = os.path.join(CROOT, "tools/shdump/agxparse.py")
HEXDIR = os.path.join(BASE, "hex")
TMPBIN = os.path.join(BASE, "tmp", "o.bin")
os.makedirs(HEXDIR, exist_ok=True)
os.makedirs(os.path.dirname(TMPBIN), exist_ok=True)

CORPUS_ROOTS = [os.path.join(BASE, "m4_13"), os.path.join(BASE, "m4_14")]
HEX_RE = re.compile(r'^[0-9a-fA-F]+$')

def strip_comments(s):
    s = re.sub(r'/\*.*?\*/', ' ', s, flags=re.S)
    s = re.sub(r'//[^\n]*', ' ', s)
    return s

def names_after(text, qual):
    """All function names defined with a given qualifier: the identifier
    immediately before the first '(' following each whole-word qualifier."""
    out = []
    for m in re.finditer(r'\b' + qual + r'\b', text):
        seg = text[m.end(): m.end()+400]
        p = seg.find('(')
        if p < 0:
            continue
        ids = re.findall(r'[A-Za-z_]\w*', seg[:p])
        if ids:
            out.append(ids[-1])
    # de-dup preserve order
    seen = set(); res = []
    for n in out:
        if n not in seen:
            seen.add(n); res.append(n)
    return res

def run(cmd, timeout=120):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 124, '', 'TIMEOUT'
    except Exception as e:
        return 125, '', 'EXC:%s' % e

def extract(stage_args):
    rc, out, err = run(['python3', AGXP, TMPBIN, '--extract-hex'] + stage_args, timeout=60)
    if rc != 0:
        return None
    hx = out.strip().replace('\n', '')
    if not hx or not HEX_RE.match(hx):
        return None
    return hx

def sanitize(s):
    return re.sub(r'[^A-Za-z0-9]', '_', s)

files = []
for root in CORPUS_ROOTS:
    for dp, _, fns in os.walk(root):
        for fn in fns:
            if fn.endswith('.metal'):
                files.append(os.path.join(dp, fn))
files.sort()

manifest = []            # per (file,fn/stage) outcome rows
n_files = len(files)
compute_ok = compute_fail = 0
render_ok = render_fail = 0
hex_written = 0
no_entry = 0
fail_samples = collections.Counter()

for path in files:
    rel = os.path.relpath(path, BASE)
    try:
        raw = open(path, errors='ignore').read()
    except Exception:
        continue
    text = strip_comments(raw)
    kfns = names_after(text, 'kernel')
    vfns = names_after(text, 'vertex')
    ffns = names_after(text, 'fragment')
    base = sanitize(os.path.splitext(rel)[0])

    did_any = False
    # ---- compute kernels ----
    for kf in kfns:
        did_any = True
        rc, out, err = run([SHDUMP, '-o', TMPBIN, '-f', kf, path])
        if rc != 0:
            compute_fail += 1
            el = [l for l in err.splitlines() if 'error:' in l]
            fail_samples[(el[0].strip()[:80] if el else 'compile-fail')] += 1
            manifest.append((rel, 'compute:'+kf, 'FAIL', ''))
            continue
        compute_ok += 1
        hx = extract([])
        if hx:
            name = "%s__k_%s" % (base, sanitize(kf))
            open(os.path.join(HEXDIR, name + '.hex'), 'w').write(hx + '\n')
            hex_written += 1
            manifest.append((rel, 'compute:'+kf, 'OK', name+'.hex (%dB)' % (len(hx)//2)))
        else:
            manifest.append((rel, 'compute:'+kf, 'NOHEX', ''))

    # ---- render pairs ----
    if vfns and ffns:
        did_any = True
        vf, ff = vfns[0], ffns[0]
        rc, out, err = run([SHDUMP, '-o', TMPBIN, '--render', '--vertex', vf, '--fragment', ff, path])
        if rc != 0:
            render_fail += 1
            el = [l for l in err.splitlines() if 'error:' in l]
            fail_samples[(el[0].strip()[:80] if el else 'render-fail')] += 1
            manifest.append((rel, 'render:%s/%s' % (vf, ff), 'FAIL', ''))
        else:
            render_ok += 1
            for stage in ('vertex', 'fragment'):
                hx = extract(['--stage', stage])
                if hx:
                    name = "%s__%s" % (base, stage)
                    open(os.path.join(HEXDIR, name + '.hex'), 'w').write(hx + '\n')
                    hex_written += 1
                    manifest.append((rel, 'render:'+stage, 'OK', name+'.hex (%dB)' % (len(hx)//2)))
                else:
                    manifest.append((rel, 'render:'+stage, 'NOHEX', ''))
    if not did_any:
        no_entry += 1
        manifest.append((rel, '-', 'NO-ENTRY', ''))

summary = {
    'corpusFiles': n_files,
    'computeCompiledOk': compute_ok,
    'computeCompileFail': compute_fail,
    'renderCompiledOk': render_ok,
    'renderCompileFail': render_fail,
    'hexWritten': hex_written,
    'noEntryFiles': no_entry,
    'topFailSamples': fail_samples.most_common(15),
}
open(os.path.join(BASE, 'build_summary.json'), 'w').write(json.dumps(summary, indent=2))
with open(os.path.join(BASE, 'manifest.txt'), 'w') as f:
    f.write("# EXP-M5-02 compile manifest: relpath | function/stage | status | artifact\n")
    for row in manifest:
        f.write(" | ".join(row) + "\n")
    f.write("\n# SUMMARY\n")
    for k, v in summary.items():
        f.write("%s = %s\n" % (k, v))
print(json.dumps(summary, indent=2))
