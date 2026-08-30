#!/usr/bin/env python3
"""EXP-0178 REMOTE HASH VERIFICATION -- run after every push, before every capture.

SUBAGENT_BRIEF (added 2026-08-30): *do not chain a state-changing step behind
`&&` and assume it ran.* EXP-0179's `sync.sh push` returned non-zero inside a
chained command and a gated pass executed against the **stale pre-amendment
harness** -- 6 cases instead of 8, remote hashes not matching local. It burned a
run id. The orchestrator hit the same shape hours earlier with a silently
skipped `PROVENANCE.md` append. A silent no-op inside a chain is
indistinguishable from success in the exit code.

So this is a SEPARATE verification step, never chained behind the push it
checks. It reads the frozen `authored_sha256` + `pinned_inputs_sha256` from
CAPTURE_CONTRACT.json, hashes the same paths ON THE NEO, and exits non-zero on
the first mismatch or missing file. A capture must not start until it passes.

  export SSHPASS=...            # never written to any file
  bash harness/sync.sh push
  python3 harness/verify_remote.py          # SEPARATE step, check the exit code

================================ UPSTREAM NOTES ================================

Intended for `experiments/SUBAGENT_BRIEF.md` as a REQUIRED pre-capture step, not
an experiment-local nicety. The gap it closes is stated in one line:

    A frozen contract hashes what you AUTHORED. It says nothing about what the
    DEVICE is running.

Every experiment here freezes `authored_sha256` and re-verifies it before a
capture -- against the LOCAL files, which of course match, because they are the
files that were hashed. Nothing in the protocol checked the remote copy, so a
push that silently failed left a contract whose every hash was correct and whose
every claim about the executing harness was false.

It caught exactly that against EXP-0178 on its first run: **11 of 18 blobs
matched.** Two files were MISSING on the neo and five were STALE -- every
amendment since the first push had failed to arrive. A gated pair started at
that moment would have executed the pre-amendment harness under a contract
asserting otherwise, and no existing check would have noticed, before or after.

To generalise it, an experiment needs only three things:
  * a `CAPTURE_CONTRACT.json` with `authored_sha256` (+ `pinned_inputs_sha256`);
  * `PUSHED_PREFIXES` naming the subtrees actually pushed to the device;
  * `REMOTE` naming the remote working directory.
Everything else is generic. It shells out to `shasum -a 256` over the remote
paths in one round trip, so it costs one SSH regardless of file count, and it
exits 3 on the first mismatch so it can be used as a gate.

**It must never be chained behind the push it checks.** That is the whole point:
`SUBAGENT_BRIEF` records two failures on 2026-08-30 where a state-changing step
behind `&&` silently did not run while the exit code looked clean (a dropped
`PROVENANCE.md` append; EXP-0179's gated pass against a stale harness). This
script is the separate verification those failures argued for, and running it
inside the same chain as the push would reintroduce the defect it exists to
catch.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
NEO = os.environ.get("NEO", "192.168.10.243")
USER = os.environ.get("NEO_USER", "user")
REMOTE = "agxre/EXP-0178"
SSHOPT = ["-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
          "-o", "ConnectTimeout=15"]

# Only these subtrees are pushed to the neo; the rest of the contract's blob list
# (README, PRE_REGISTRATION, the analysis JSON) stays on the repo side.
PUSHED_PREFIXES = ("harness/", "kernels/", "analysis/", "pinned/")


def main():
    c = json.load(open(os.path.join(EXP, "CAPTURE_CONTRACT.json")))
    want = {}
    want.update({k: v for k, v in c["authored_sha256"].items()
                 if k.startswith(PUSHED_PREFIXES)})
    want.update(c["pinned_inputs_sha256"])
    want = {k: v for k, v in want.items() if not k.endswith(".json")
            or k.startswith("pinned/")}

    paths = " ".join("%s/%s" % (REMOTE, k) for k in sorted(want))
    r = subprocess.run(["sshpass", "-e", "ssh"] + SSHOPT + ["%s@%s" % (USER, NEO),
                       "cd $HOME && shasum -a 256 %s 2>&1" % paths],
                       capture_output=True, text=True, timeout=120)
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
            bad.append("STALE on the neo: %s\n    local  %s\n    remote %s" % (k, v, got[k]))
    for k in sorted(bad):
        print(k)
    print("verify_remote: %d/%d blobs match" % (len(want) - len(bad), len(want)))
    if bad:
        print("REFUSING: the neo does not hold the frozen harness. Re-push and re-verify;\n"
              "do NOT start a capture. (SUBAGENT_BRIEF: verify separately, never behind &&.)")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
