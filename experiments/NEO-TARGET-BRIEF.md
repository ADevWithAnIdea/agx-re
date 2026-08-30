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

## Concurrency: unrestricted. There is no lease.

**Run every sweep concurrently and unlocked.** The GPU's hardware contexts isolate ordinary work.
The lease that used to live here has been removed — it serialized an eight-agent wave behind one
bulk run and bought nothing that instrumentation does not buy more cheaply.

What replaces it, per `FIELD-SWEEP-PROTOCOL.md` §7:

1. **Poison your read-back buffer** with `0xDEADBEEF`. This distinguishes *wrote the right value* /
   *wrote a wrong value* / **never ran at all** — and on this ISA a wrong field value usually
   produces a silent zero, so a zero-initialised buffer cannot tell "wrote 0" from "did not
   execute". EXP-0153 settled five suspect faults **offline from already-captured data** this way.
2. **Integrity sentinel** through a path independent of the instruction under test, in a register
   no descriptor under test can name.
3. **Record the OS fault-classification string** on every non-`ok` case.
   `…ErrorInnocentVictim` = a sibling's device reset, not your encoding.
4. **Never conclude `fault` from one observation** — majority-of-3 minimum, and adjudicate from the
   poisoned buffer where you can.

If you are about to sweep a region you know hangs, note it in `PROGRESS.md` as a courtesy — a hang
resets the device for everyone — but do not serialize for it.

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
