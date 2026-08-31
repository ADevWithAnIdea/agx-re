#!/usr/bin/env python3
"""EXP-0213 -- prove the neo is running EXACTLY the committed harness, as a SEPARATE step.

    python3 harness/verify_repo_eq_neo.py <local_exp_dir> <remote_exp> [--also f1 f2 ...]

Never chained behind a push: EXP-0179's `sync.sh push` returned non-zero inside a chained
command and a gated pass executed against the STALE harness, burning a run id.  Exit 0 iff
every dispatch-relevant file on the neo has the same sha256 as the committed repo file.
"""
import argparse, hashlib, os, subprocess, sys

SSHOPT = ["-o","StrictHostKeyChecking=no","-o","UserKnownHostsFile=/dev/null",
          "-o","ConnectTimeout=15"]
DIRS = ("harness","kernels","pinned")
TOP = ("run.py","CAPTURE_CONTRACT.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("local"); ap.add_argument("remote")
    ap.add_argument("--host", default="192.168.170.254"); ap.add_argument("--user", default="user")
    a = ap.parse_args()
    want = {}
    for d in DIRS:
        p = os.path.join(a.local, d)
        if not os.path.isdir(p):
            continue
        for f in sorted(os.listdir(p)):
            fp = os.path.join(p, f)
            if os.path.isfile(fp) and not f.endswith(".pyc"):
                want["%s/%s" % (d, f)] = hashlib.sha256(open(fp,"rb").read()).hexdigest()
    for f in TOP:
        fp = os.path.join(a.local, f)
        if os.path.isfile(fp):
            want[f] = hashlib.sha256(open(fp,"rb").read()).hexdigest()
    cmd = ("cd ~/%s && for f in %s; do if [ -f \"$f\" ]; then shasum -a 256 \"$f\"; "
           "else echo \"MISSING  $f\"; fi; done"
           % (a.remote, " ".join("'%s'" % k for k in sorted(want))))
    out = subprocess.check_output(["sshpass","-e","ssh"]+SSHOPT+
                                  ["%s@%s" % (a.user,a.host), cmd], text=True, timeout=300)
    got = {}
    for ln in out.splitlines():
        parts = ln.split(None,1)
        if len(parts)==2:
            got[parts[1].strip()] = parts[0].strip()
    bad = [(k,v,got.get(k,"ABSENT")) for k,v in sorted(want.items()) if got.get(k)!=v]
    for k,w,g in bad:
        print("MISMATCH %-46s repo=%s neo=%s" % (k,w[:12],g[:12]))
    print("repo==neo for %d/%d files  (%s -> ~/%s)" % (len(want)-len(bad),len(want),a.local,a.remote))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
