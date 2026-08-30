#!/usr/bin/env python3
"""EXP-0200 REMOTE HASH VERIFICATION -- a SEPARATE step after every push.

    A frozen contract hashes what you AUTHORED. It says nothing about what the
    DEVICE is running.

EXP-0178 introduced this check and it caught exactly that against its own author
on the first run: 11 of 18 blobs matched, two files MISSING and five STALE. A
gated pair started at that moment would have executed the pre-amendment harness
under a contract asserting otherwise.

This experiment has a second reason to run it: target 1 is EXP-0187's frozen
contract honoured UNCHANGED, so the `t1/` tree must hash-match EXP-0187's OWN
`CAPTURE_CONTRACT.json` both locally and on the device. If it does not, this is
not a replication of that contract and must not be reported as one.

NEVER chain it behind the push it checks. Run it on its own; check the exit code.

  export SSHPASS=...
  bash harness/sync200.sh push
  python3 harness/verify_remote200.py          # SEPARATE; exit 0 required
"""
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
NEO = os.environ.get("NEO", "192.168.170.254")
USER = os.environ.get("NEO_USER", "user")
REMOTE = "agxre/EXP-0200"
SSHOPT = ["-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
          "-o", "ConnectTimeout=15"]
PUSHED_PREFIXES = ("harness/", "kernels/", "analysis/", "run200.py", "t1/")


def local_sha(rel):
    p = os.path.join(EXP, rel)
    if not os.path.exists(p):
        return None
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def t1_unchanged():
    """t1/ must byte-match EXP-0187's own contract, or target 1 is not a
    replication of that contract."""
    c = json.load(open(os.path.join(EXP, "t1", "CAPTURE_CONTRACT.json")))
    bad = []
    checked = 0
    for grp in ("authored_sha256", "pinned_inputs_sha256"):
        for f, h in c[grp].items():
            checked += 1
            g = local_sha(os.path.join("t1", f))
            if g is None:
                bad.append("t1/%s ABSENT locally" % f)
            elif g != h:
                bad.append("t1/%s DIFFERS from EXP-0187's frozen hash" % f)
    return checked, bad


def main():
    checked, bad = t1_unchanged()
    for b in bad:
        print(b)
    print("t1 verbatim check: %d/%d blobs match EXP-0187's CAPTURE_CONTRACT"
          % (checked - len(bad), checked))
    if bad:
        print("REFUSING: target 1 is NOT EXP-0187's contract honoured unchanged.")
        return 4

    c = json.load(open(os.path.join(EXP, "CAPTURE_CONTRACT.json")))
    want = {k: v for k, v in c["authored_sha256"].items()
            if k.startswith(PUSHED_PREFIXES)}
    paths = " ".join("%s/%s" % (REMOTE, k) for k in sorted(want))
    r = subprocess.run(["sshpass", "-e", "ssh"] + SSHOPT + ["%s@%s" % (USER, NEO),
                       "cd $HOME && shasum -a 256 %s 2>&1" % paths],
                      capture_output=True, text=True, timeout=300)
    got = {}
    for ln in r.stdout.splitlines():
        parts = ln.split(None, 1)
        if len(parts) == 2 and len(parts[0]) == 64:
            got[parts[1].strip()[len(REMOTE) + 1:]] = parts[0]
    bad = []
    for k, v in sorted(want.items()):
        if k not in got:
            bad.append("MISSING on the neo: %s" % k)
        elif got[k] != v:
            bad.append("STALE on the neo: %s\n    local  %s\n    remote %s"
                       % (k, v, got[k]))
    for k in bad:
        print(k)
    print("verify_remote200: %d/%d blobs match" % (len(want) - len(bad), len(want)))
    if bad:
        print("REFUSING: the neo does not hold the frozen harness. Re-push and "
              "re-verify; do NOT start a capture.")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
