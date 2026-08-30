#!/usr/bin/env python3
"""Verify that the neo is running EXACTLY the blobs we authored.

A frozen contract hashes what we WROTE, not what the device is EXECUTING, and
`sync.sh push` returning non-zero inside an `&&` chain is a silent no-op that is
indistinguishable from success in the exit code. That already cost this
experiment one burned run id (`MAPPING_..._run07N`, which ran against a stale
harness). EXP-0178 hit the identical failure and built the same check.

  SSHPASS=... python3 harness/verify_remote.py
Exit 0 iff every authored blob on the neo matches this repo byte for byte.
"""
import hashlib
import subprocess
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
NEO = "192.168.10.243"
REMOTE = "agxre/EXP-0179"
PATS = ("harness/*.py", "kernels/*.metal", "kernels/census/*.metal",
        "work/frozen/db.json", "work/frozen/isadb.py")


# This verifier runs on the REPO HOST and is deliberately not shipped to the
# neo, so it must not check for itself. Same for the device-free self-test stubs.
SKIP = {"harness/verify_remote.py", "harness/fakechild.py", "harness/selftest.py"}


def local():
    out = {}
    for pat in PATS:
        for p in sorted(EXP.glob(pat)):
            rel = str(p.relative_to(EXP))
            if rel in SKIP:
                continue
            out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def remote(paths):
    cmd = ("cd ~/%s && shasum -a 256 %s 2>&1"
           % (REMOTE, " ".join("'%s'" % p for p in paths)))
    r = subprocess.run(
        ["sshpass", "-e", "ssh", "-o", "StrictHostKeyChecking=no",
         "-o", "UserKnownHostsFile=/dev/null", "-o", "LogLevel=ERROR",
         "-o", "ConnectTimeout=15", "user@%s" % NEO, cmd],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
    got = {}
    for ln in r.stdout.decode().splitlines():
        bits = ln.split()
        if len(bits) == 2 and len(bits[0]) == 64:
            got[bits[1]] = bits[0]
    return got


loc = local()
rem = remote(sorted(loc))
match, stale, missing = [], [], []
for k, v in sorted(loc.items()):
    if k not in rem:
        missing.append(k)
    elif rem[k] != v:
        stale.append(k)
    else:
        match.append(k)
print("matched %d / %d" % (len(match), len(loc)))
for k in stale:
    print("  STALE   %s" % k)
for k in missing:
    print("  MISSING %s" % k)
print("VERIFY %s" % ("PASS" if not stale and not missing else "FAIL"))
sys.exit(0 if not stale and not missing else 1)
