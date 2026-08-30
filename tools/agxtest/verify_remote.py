#!/usr/bin/env python3
"""REMOTE HASH VERIFICATION -- run after every push, before every capture, AS ITS OWN STEP.

    export SSHPASS=...                                 # never written to any file
    bash harness/sync.sh push
    python3 ../../tools/agxtest/verify_remote.py \
        --contract CAPTURE_CONTRACT.json --remote agxre/EXP-0178    # SEPARATE, check $?

    exit 0 = every pushed blob on the device matches the frozen contract
    exit 3 = something is MISSING or STALE on the device -- do NOT start a capture
    exit 2 = transport/usage error (nothing was verified, which is also not a pass)

UPSTREAMED 2026-08-30 by EXP-0185 from `EXP-0178-g17p-sysval-tileread/harness/verify_remote.py`
(our own code, this repository), generalised: contract path, remote directory, pushed
prefixes and excludes are arguments, and the transport is pluggable so the check itself has
an offline gate.

WHY THIS EXISTS
===============

The gap it closes is one line:

    A frozen contract hashes what you AUTHORED. It says nothing about what the DEVICE is
    running.

Every experiment here freezes `authored_sha256` and re-verifies it before a capture --
against the LOCAL files, which of course match, because they are the files that were
hashed. Nothing in the protocol checked the remote copy, so a push that silently failed
left a contract **whose every hash was correct and whose every claim about the executing
harness was false**.

It caught exactly that against its own author, EXP-0178, on its first run: **11 of 18 blobs
matched.** Two files were MISSING on the neo and five were STALE -- every amendment since
the first push had failed to arrive. A gated pair started at that moment would have
executed the pre-amendment harness under a contract asserting otherwise, and no existing
check would have noticed, before or after.

EXP-0179 hit the same failure in the other order: its `sync.sh push` returned non-zero
inside an `&&` chain, so a gated pass ran against the STALE pre-amendment harness -- 6 cases
instead of 8 -- and burned a run id, which was retained and marked defective. The
orchestrator hit the same shape hours earlier with a `PROVENANCE.md` append that silently
did not execute inside a chain while the `git commit` beside it succeeded.

**NEVER CHAIN THIS BEHIND THE PUSH IT CHECKS.** That is the whole point: a silent no-op
inside a chain is indistinguishable from success in the exit code, and running the
verification inside the same chain as the push reintroduces the very defect it exists to
catch. Run it as its own command and read its exit code.

WHAT AN EXPERIMENT NEEDS TO USE IT
==================================

  * a `CAPTURE_CONTRACT.json` with `authored_sha256` (and optionally `pinned_inputs_sha256`);
  * `--prefix` for each subtree actually pushed to the device (default:
    `harness/ kernels/ analysis/ pinned/`) -- everything else in the contract's blob list
    (README, PRE_REGISTRATION, derived JSON) stays on the repo side;
  * `--remote` naming the remote working directory (relative paths resolve from `$HOME`).

It shells out to `shasum -a 256` over the remote paths in batches, so it costs one SSH per
150 files regardless of file count, and it exits 3 on the first run that shows any
mismatch, so it can be used as a gate.

OFFLINE GATE (no device, no SSH): `python3 tools/agxtest/selftest_tools.py` builds a fake
"remote" tree on the local filesystem via `LocalRunner` and asserts the checker reports
OK / MISSING / STALE correctly and returns 3 for the last two.

Clean-room: hashes of OUR OWN authored files. No Apple binary involved.
"""
import argparse
import fnmatch
import json
import os
import shlex
import subprocess
import sys

DEFAULT_PREFIXES = ("harness/", "kernels/", "analysis/", "pinned/")
BATCH = 150

SSHOPT = ["-o", "StrictHostKeyChecking=no",
          "-o", "UserKnownHostsFile=/dev/null",
          "-o", "ConnectTimeout=15"]


class SshRunner(object):
    """Run a shell command on the device. Uses `sshpass -e` when SSHPASS is set,
    plain `ssh` otherwise (key auth)."""

    def __init__(self, host, user="user", timeout=120):
        self.host, self.user, self.timeout = host, user, timeout

    def __call__(self, cmd):
        base = ["sshpass", "-e", "ssh"] if os.environ.get("SSHPASS") else ["ssh"]
        argv = base + SSHOPT + ["%s@%s" % (self.user, self.host), cmd]
        p = subprocess.run(argv, capture_output=True, text=True, timeout=self.timeout)
        return p.returncode, p.stdout, p.stderr

    def describe(self):
        return "%s@%s" % (self.user, self.host)


class LocalRunner(object):
    """Run the same shell command against a LOCAL directory tree. Used by the offline
    gate, and usable for a same-host capture."""

    def __init__(self, root, timeout=120):
        self.root, self.timeout = root, timeout

    def __call__(self, cmd):
        p = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True,
                           cwd=self.root, timeout=self.timeout)
        return p.returncode, p.stdout, p.stderr

    def describe(self):
        return "local:%s" % self.root


def wanted(contract, prefixes=DEFAULT_PREFIXES, excludes=()):
    """The set of {path: sha256} the DEVICE must hold, taken from the frozen contract."""
    want = {}
    for key in ("authored_sha256", "pinned_inputs_sha256"):
        for k, v in (contract.get(key) or {}).items():
            if prefixes and not k.startswith(tuple(prefixes)):
                continue
            if any(fnmatch.fnmatch(k, g) for g in excludes):
                continue
            want[k] = v
    return want


def remote_hashes(paths, runner, remote_dir):
    """-> ({path: sha}, [transport errors]). One `shasum -a 256` per BATCH paths."""
    got, errs = {}, []
    paths = sorted(paths)
    for i in range(0, len(paths), BATCH):
        chunk = paths[i:i + BATCH]
        cmd = "cd %s && shasum -a 256 %s 2>&1" % (
            shlex.quote(remote_dir), " ".join(shlex.quote(p) for p in chunk))
        try:
            rc, out, err = runner(cmd)
        except Exception as e:                       # noqa: BLE001
            errs.append("transport failed: %s" % e)
            continue
        if err.strip():
            errs.append(err.strip()[:400])
        for ln in out.splitlines():
            parts = ln.split(None, 1)
            if len(parts) == 2 and len(parts[0]) == 64:
                got[parts[1].strip()] = parts[0]
    return got, errs


def verify(contract_path, remote_dir, runner, prefixes=DEFAULT_PREFIXES, excludes=()):
    """-> (want, got, bad_lines). `bad_lines` empty == the device holds the frozen tree."""
    with open(contract_path) as fh:
        contract = json.load(fh)
    want = wanted(contract, prefixes, excludes)
    got, errs = remote_hashes(list(want), runner, remote_dir)
    bad = []
    for k, v in sorted(want.items()):
        if k not in got:
            bad.append("MISSING on the device: %s" % k)
        elif got[k] != v:
            bad.append("STALE on the device:   %s\n    local  %s\n    remote %s"
                       % (k, v, got[k]))
    return want, got, bad, errs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--contract", required=True, help="path to CAPTURE_CONTRACT.json")
    ap.add_argument("--remote", required=True,
                    help="remote working directory (relative resolves from $HOME)")
    ap.add_argument("--host", default=os.environ.get("NEO", "192.168.10.243"))
    ap.add_argument("--user", default=os.environ.get("NEO_USER", "user"))
    ap.add_argument("--prefix", action="append", default=None,
                    help="pushed subtree prefix; repeatable (default: %s)"
                         % " ".join(DEFAULT_PREFIXES))
    ap.add_argument("--exclude", action="append", default=[],
                    help="glob of contract keys to skip; repeatable")
    ap.add_argument("--local-root", default=None,
                    help="verify against a LOCAL directory instead of SSH (offline gate)")
    ap.add_argument("--timeout", type=float, default=120)
    a = ap.parse_args(argv)

    runner = (LocalRunner(a.local_root, a.timeout) if a.local_root
              else SshRunner(a.host, a.user, a.timeout))
    prefixes = tuple(a.prefix) if a.prefix else DEFAULT_PREFIXES
    try:
        want, got, bad, errs = verify(a.contract, a.remote, runner,
                                      prefixes, tuple(a.exclude))
    except Exception as e:                           # noqa: BLE001
        print("verify_remote: ERROR %s" % e)
        return 2
    for e in errs:
        if "No such file" not in e:                  # missing files are reported below
            print("transport note: %s" % e)
    for ln in bad:
        print(ln)
    print("verify_remote: %d/%d blobs match on %s:%s"
          % (len(want) - len(bad), len(want), runner.describe(), a.remote))
    if not want:
        print("REFUSING: the contract matched NO pushed blobs -- check --prefix. "
              "An empty check is not a pass.")
        return 2
    if bad:
        print("REFUSING: the device does not hold the frozen harness. Re-push and "
              "re-verify;\ndo NOT start a capture. (SUBAGENT_BRIEF: verify separately, "
              "never behind &&.)")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
