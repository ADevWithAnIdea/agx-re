# The neo (A18 Pro / G17P) — how to run experiments on the test target

**Read with** `../CLAUDE.md`, `../CODEX.md`, `SUBAGENT_BRIEF.md`, `FIELD-SWEEP-PROTOCOL.md`.
Written by the orchestrator 2026-08-28 after porting and verifying the toolchain end-to-end.

## Connection

```sh
export SSHPASS='<ask the orchestrator>'          # never hardcode into a committed file
NEO=192.168.10.243                                # DHCP; if it moves, ASK — do not scan
sshpass -e ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null user@$NEO '<cmd>'
sshpass -e scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null <f> user@$NEO:~/agxre/
```

Wrap every remote call in a hard timeout — `perl -e 'alarm 120; exec @ARGV' sshpass -e ssh …` —
because a wedged neo otherwise hangs your whole dispatch.

## Verified working (2026-08-28, by the orchestrator)

| | |
|---|---|
| Device | `Apple A18 Pro`, arch **`applegpu_g17p`**, `AGXAcceleratorG17P`, **5 GPU cores**, Metal family **Apple9**, `Mac17,5`, macOS 26.6 |
| Toolchain | `clang` 21.0.0, `python3`, **full Xcode** at `/Applications/Xcode.app` — richer than the M4 ever had |
| Runtime MSL | `newLibraryWithSource:` compiles; dispatch returns correct values; `CB_STATUS 4` |
| Ported + built | `~/agxre/tools/shdump/shdump`, `~/agxre/tools/agxtest/{agxrun,agxrun_persist,agxrender}`, `~/agxre/tools/agx-isa/` |
| `agx-isa` round-trip **on the neo** | **ALL PASS** |
| **G17P bytes decode with the Apple9 DB** | a compiled `a[i]*2+1` kernel gives `get_sr · device_load · falu3 · device_store · stop`, **0 leftover bytes** |

That last row matters: the DB built from M4 evidence tokenizes A18 code cleanly, so the port is a
change of target, not a restart.

## Layout and the evidence rule

Work under **`~/agxre/<EXP-NNNN>/`** on the neo. Rebuild binaries there rather than copying them.

> **Nothing on the neo is evidence until it is pulled back into your experiment directory in this
> repo and committed.** The neo is a compute target; a reboot loses whatever is only there. Copy
> `raw/` back as you go, not at the end.

Do not read or modify anything on the neo outside your own working directory.

## GPU lease — REQUIRED for every device run

One GPU, many agents. On the M4 concurrent sweeps contaminated each other badly: EXP-0139 measured
**44% of gated-run faults failing to reproduce**, and without mitigation **692 legal field values
would have been labelled `fault`**. That is now solved by serialization rather than by limiting how
many agents exist.

**`~/agxre/gpulease.sh` (source: `tools/gpulease.sh`) — wrap every GPU-touching command:**

```sh
~/agxre/gpulease.sh EXP-0154 900 -- <your command>
```

- `EXP-NNNN` is your holder name, so a stuck lease is attributable.
- Second argument is how long you will wait for the lease before giving up (exit **75**).
- Atomic via `mkdir` (macOS has no `flock`). Leases older than **15 minutes are broken
  automatically**, so a killed agent cannot deadlock the device.
- Releases on EXIT/INT/TERM.

**Hold the lease for a batch, not for each dispatch** — take it once around a whole sweep run, not
once per case, or you will spend all your time queueing. Conversely do **not** hold it across
analysis or file transfer; release, think, re-acquire.

If you get exit 75, another agent has the device. Back off and retry; do not force it, and do not
delete `/tmp/agx_gpu.lock` by hand — the staleness rule already handles genuinely dead holders.

§7's mitigations still apply *inside* your lease (majority-of-3 on faults, fault-class strings,
baseline re-validation, integrity sentinel, poisoned read-back buffer). The lease removes
*cross-agent* interference; it does not remove the hardware's own nondeterminism.

## Recovery

If the neo stops answering: **STOP and report BLOCKED** with exactly where you were.
`macvdmtool` is **forbidden to subagents without exception** — recovery is the orchestrator's job,
and a reboot moves the machine to a new DHCP address that has to be re-found.

## What changes about your evidence

**G17P is now the documentation target and the test target.** A result measured here is **direct**,
not `INFERRED` — that is the whole point of the pivot. Committed M4/G16G results stay valid on
their own target but no longer satisfy a closure row by themselves.

So label honestly: `target: G17P` for anything you run here. **Never carry an M4 label onto a G17P
result or vice versa**, and where you are deliberately re-running an M4 experiment to convert it,
say which M4 result you are testing against and whether it reproduced. A G16G↔G17P *disagreement*
is a first-class finding — we already have one open (`tg_addr_compute`: on M4 only byte0 `0x1c`
works, and EXP-M4-14's A18 `0xfc` does not reproduce).
