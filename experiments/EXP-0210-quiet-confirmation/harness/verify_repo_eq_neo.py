#!/usr/bin/env python3
"""EXP-0210 -- verify that the neo holds byte-for-byte what THIS REPO holds.

    python3 harness/verify_repo_eq_neo.py <local_exp_dir> <remote_rel_dir> <rel_path>...

Each source experiment's own `verify_remote.py` compares the neo against that experiment's
`CAPTURE_CONTRACT.json`.  That is the right check for the experiment itself, but it answers a
different question from the one a confirmation needs: a contract frozen before a late harness
edit will refuse even when the neo is a perfect copy of the committed tree.  This check
answers "is the device running the committed code", and its result is reported alongside --
never instead of -- the experiment's own verify_remote exit code.
"""
import hashlib
import os
import subprocess
import sys

NEO = os.environ.get("NEO", "192.168.170.254")
SSHOPT = ["-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
          "-o", "ConnectTimeout=15"]


def main():
    local_dir, remote_dir = sys.argv[1], sys.argv[2]
    rels = sys.argv[3:]
    want = {}
    for r in rels:
        p = os.path.join(local_dir, r)
        if os.path.isfile(p):
            want[r] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    paths = " ".join("%s/%s" % (remote_dir, k) for k in sorted(want))
    res = subprocess.run(["sshpass", "-e", "ssh"] + SSHOPT + ["user@%s" % NEO,
                         "cd $HOME && shasum -a 256 %s 2>&1" % paths],
                         capture_output=True, text=True, timeout=240)
    got = {}
    for ln in res.stdout.splitlines():
        parts = ln.split(None, 1)
        if len(parts) == 2 and len(parts[0]) == 64:
            got[parts[1].strip()[len(remote_dir) + 1:]] = parts[0]
    bad = 0
    for k, v in sorted(want.items()):
        if got.get(k) != v:
            print("DIFFERS repo vs neo: %s  repo=%s neo=%s" % (k, v[:12], (got.get(k) or "MISSING")[:12]))
            bad += 1
    print("repo==neo: %d/%d blobs match" % (len(want) - bad, len(want)))
    return 0 if bad == 0 else 3


if __name__ == "__main__":
    sys.exit(main())
