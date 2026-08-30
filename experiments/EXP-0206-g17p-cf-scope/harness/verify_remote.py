#!/usr/bin/env python3
"""EXP-0206 remote verifier -- a SEPARATE step, never chained behind a push.

EXP-0179's `sync.sh push` returned non-zero inside a chained command and a gated
pass executed against the STALE pre-amendment harness -- 6 cases instead of 8,
remote hashes not matching local. It burned a run id. The rule that came out of
that: after any push, write, or generate step whose output you will then depend
on, VERIFY IT SEPARATELY.

This asks the neo for the sha256 of every file the frozen contract names and
compares it to the contract. Exit 0 iff every file matches. Nothing is chained.

  export SSHPASS=...
  python3 harness/verify_remote.py --contract CAPTURE_CONTRACT.json \
          --remote agxre/EXP-0206 --host 192.168.170.254
"""
import argparse, json, subprocess, sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
SSHOPT = ["-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
          "-o", "ConnectTimeout=15"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--contract", default=str(EXP / "CAPTURE_CONTRACT.json"))
    ap.add_argument("--remote", default="agxre/EXP-0206")
    ap.add_argument("--host", default="192.168.170.254")
    ap.add_argument("--user", default="user")
    a = ap.parse_args()
    doc = json.loads(Path(a.contract).read_text())
    want = {k: v["sha256"] for k, v in doc["files"].items()
            if k.split("/")[0] in ("harness", "kernels", "analysis", "pinned")
            or k == "run.py"}
    cmd = ("cd ~/%s && for f in %s; do if [ -f \"$f\" ]; then shasum -a 256 \"$f\"; "
           "else echo \"MISSING  $f\"; fi; done"
           % (a.remote, " ".join("'%s'" % k for k in sorted(want))))
    out = subprocess.check_output(
        ["sshpass", "-e", "ssh"] + SSHOPT + ["%s@%s" % (a.user, a.host), cmd],
        text=True, timeout=180)
    got = {}
    for ln in out.splitlines():
        parts = ln.split(None, 1)
        if len(parts) == 2:
            got[parts[1].strip()] = parts[0].strip()
    bad = []
    for k, h in sorted(want.items()):
        if got.get(k) != h:
            bad.append((k, h[:12], (got.get(k) or "ABSENT")[:12]))
    for k, w, g in bad:
        print("MISMATCH %-46s want=%s got=%s" % (k, w, g))
    print("verified %d/%d files against %s" % (len(want) - len(bad), len(want),
                                               a.contract))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
