#!/usr/bin/env python3
"""EXP-0207: verify the neo's copy of every authored blob matches this repo.

SUBAGENT_BRIEF: "after any push, write or generate step whose output you will
then depend on, VERIFY IT SEPARATELY."  A `sync.sh push` chained behind `&&`
returning non-zero has already made one experiment run a gated pass against a
STALE harness.  This is that separate step: it compares sha256 of every authored
file, one by one, and exits non-zero on the first mismatch.

  SSHPASS=... python3 harness/verify_remote.py
"""
import hashlib
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
NEO = os.environ.get("NEO", "192.168.170.254")
USER = os.environ.get("NEO_USER", "user")
SSHOPT = ["-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
          "-o", "ConnectTimeout=15"]


def local_files():
    out = []
    for d in ("harness", "kernels", "analysis", "pinned"):
        p = os.path.join(EXP, d)
        if not os.path.isdir(p):
            continue
        for fn in sorted(os.listdir(p)):
            f = os.path.join(p, fn)
            if os.path.isfile(f) and not fn.endswith(".pyc"):
                out.append((d + "/" + fn, f))
    return out


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 16), b""):
            h.update(c)
    return h.hexdigest()


def main():
    files = local_files()
    cmd = "cd $HOME/agxre/EXP-0207 && shasum -a 256 " + " ".join(r for r, _ in files)
    r = subprocess.run(["sshpass", "-e", "ssh"] + SSHOPT + ["%s@%s" % (USER, NEO), cmd],
                       capture_output=True, text=True, timeout=180)
    remote = {}
    for line in r.stdout.splitlines():
        parts = line.split()
        if len(parts) == 2:
            remote[parts[1]] = parts[0]
    bad = 0
    for rel, f in files:
        want = sha256(f)
        got = remote.get(rel)
        if got != want:
            print("MISMATCH %-40s local=%s remote=%s" % (rel, want[:16], (got or "ABSENT")[:16]))
            bad += 1
    print("%d/%d blobs match on the device" % (len(files) - bad, len(files)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
