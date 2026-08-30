#!/usr/bin/env python3
"""EXP-0203 remote-hash verifier.

SUBAGENT_BRIEF: "after any push, write, or generate step whose output you will then depend
on, VERIFY IT SEPARATELY."  EXP-0179 burned a gated run because a push returned non-zero
inside a chained command and the run executed against the STALE harness.  This compares the
sha256 of every authored file here against the copy on the neo and exits non-zero on any
difference.

Usage:  SSHPASS=... python3 harness/verify_remote.py
"""
import hashlib
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
NEO = os.environ.get("NEO", "192.168.170.254")
REM = "agxre/EXP-0203"
SSHOPT = ["-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
          "-o", "ConnectTimeout=15"]


def local_files():
    out = {}
    for sub, pat in (("harness", "*.py"), ("kernels", "*.metal"), ("analysis", "*.py"),
                     ("work/frozen", "db.json"), ("work/frozen", "isadb.py"),
                     ("work/stub", "fakerunner.py")):
        for p in sorted((EXP / sub).glob(pat)):
            out["%s/%s" % (sub, p.name)] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def main():
    loc = local_files()
    cmd = ["sshpass", "-e", "ssh"] + SSHOPT + ["user@%s" % NEO,
           "cd %s && shasum -a 256 %s" % (REM, " ".join(sorted(loc)))]
    r = subprocess.run(["perl", "-e", "alarm 120; exec @ARGV"] + cmd,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
    rem = {}
    for line in r.stdout.decode().splitlines():
        parts = line.split()
        if len(parts) == 2:
            rem[parts[1]] = parts[0]
    bad = [k for k in loc if rem.get(k) != loc[k]]
    for k in sorted(loc):
        print("%-40s %s" % (k, "OK" if rem.get(k) == loc[k] else
                            "MISMATCH local=%s remote=%s" % (loc[k][:12],
                                                             (rem.get(k) or "MISSING")[:12])))
    if bad:
        print("\n%d MISMATCHED FILE(S) -- do NOT run" % len(bad))
        print(r.stderr.decode()[-400:])
        sys.exit(1)
    print("\nall %d files match" % len(loc))


if __name__ == "__main__":
    main()
