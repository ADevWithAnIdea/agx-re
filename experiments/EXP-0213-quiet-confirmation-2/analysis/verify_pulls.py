#!/usr/bin/env python3
"""EXP-0213 -- prove every pulled run directory is byte-identical to the neo's copy.

    python3 analysis/verify_pulls.py

Nothing is chained behind the pull: this is a separate step that asks the neo for the sha256
of every file in every g17p_e0213_* run directory and compares it with the repo copy.  Exit 0
iff every file matches and no expected file is missing.
"""
import glob
import hashlib
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SSHOPT = ["-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
          "-o", "ConnectTimeout=15"]
PAIRS = [("../EXP-0204-g17p-tex-carrier-dimensions", "agxre/EXP-0204"),
         ("../EXP-0206-g17p-cf-scope", "agxre/EXP-0206")]


def main():
    bad, n = [], 0
    for local, remote in PAIRS:
        base = os.path.join(HERE, local, "raw")
        dirs = sorted(os.path.basename(d) for d in glob.glob(os.path.join(base, "g17p_e0213_*")))
        if not dirs:
            continue
        cmd = ("cd ~/%s/raw && for d in %s; do for f in \"$d\"/*; do shasum -a 256 \"$f\"; "
               "done; done" % (remote, " ".join("'%s'" % d for d in dirs)))
        out = subprocess.check_output(["sshpass", "-e", "ssh"] + SSHOPT +
                                      ["user@192.168.170.254", cmd], text=True, timeout=600)
        remote_h = {}
        for ln in out.splitlines():
            p = ln.split(None, 1)
            if len(p) == 2:
                remote_h[p[1].strip()] = p[0].strip()
        for d in dirs:
            for f in sorted(os.listdir(os.path.join(base, d))):
                rel = "%s/%s" % (d, f)
                h = hashlib.sha256(open(os.path.join(base, d, f), "rb").read()).hexdigest()
                n += 1
                if remote_h.get(rel) != h:
                    bad.append((local, rel, h[:12], (remote_h.get(rel) or "ABSENT")[:12]))
    for b in bad:
        print("MISMATCH", b)
    print("pulled files verified byte-identical to the neo: %d/%d" % (n - len(bad), n))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
