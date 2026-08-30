#!/usr/bin/env python3
"""EXP-0202 REMOTE HASH VERIFICATION -- a SEPARATE step after every push.

    A frozen contract hashes what you AUTHORED. It says nothing about what the
    DEVICE is running.

EXP-0178 introduced this check and it caught exactly that against its own
author on the first run: **11 of 18 blobs matched** -- two files MISSING on the
neo and five STALE, every amendment since the first push having silently failed
to arrive. A gated pair started at that moment would have executed the
pre-amendment harness under a contract asserting otherwise.

It must NEVER be chained behind the push it checks (SUBAGENT_BRIEF records two
failures on 2026-08-30 where a state-changing step behind `&&` silently did not
run while the exit code looked clean). Run it on its own; check the exit code.

  export SSHPASS=...
  bash harness/sync.sh push
  python3 harness/verify_remote.py          # SEPARATE; exit 0 required
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
NEO = os.environ.get("NEO", "192.168.170.254")
USER = os.environ.get("NEO_USER", "user")
REMOTE = "agxre/EXP-0202"
SSHOPT = ["-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
          "-o", "ConnectTimeout=15"]
PUSHED_PREFIXES = ("harness/", "kernels/", "analysis/", "run.py")


def main():
    c = json.load(open(os.path.join(EXP, "CAPTURE_CONTRACT.json")))
    want = {k: v for k, v in c["authored_sha256"].items()
            if k.startswith(PUSHED_PREFIXES)}
    want.update({"pinned/" + os.path.basename(k): v
                 for k, v in c["pinned_inputs_sha256"].items()})
    paths = " ".join("%s/%s" % (REMOTE, k) for k in sorted(want))
    r = subprocess.run(["sshpass", "-e", "ssh"] + SSHOPT + ["%s@%s" % (USER, NEO),
                       "cd $HOME && shasum -a 256 %s 2>&1" % paths],
                       capture_output=True, text=True, timeout=180)
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
    print("verify_remote: %d/%d blobs match" % (len(want) - len(bad), len(want)))
    if bad:
        print("REFUSING: the neo does not hold the frozen harness. Re-push and "
              "re-verify; do NOT start a capture.")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
