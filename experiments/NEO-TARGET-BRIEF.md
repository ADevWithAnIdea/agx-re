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

## Concurrency: run in parallel by default; the lease is for hang-prone work ONLY

**Default: DO NOT take a lease. Run concurrently.** The GPU has many hardware contexts and they
isolate ordinary work correctly. Serializing every sweep would make an 8-agent wave effectively
single-threaded for no benefit.

**What breaks isolation is a GPU *hang*, not concurrency.** A hang triggers a device-level reset,
and that reset kills in-flight command buffers in *other* contexts. That is the recovery mechanism
behaving correctly — and crucially, **the driver tells you it happened**:

> `kIOGPUCommandBufferCallbackErrorInnocentVictim` — "Discarded (victim of GPU error/recovery)"

**Contamination is therefore 100% detectable, never silent.** EXP-0139's numbers: 1,552 victim
attempts against 2,656 genuine `…ErrorHang` and 50 `…ErrorPageFault`; **44% of gated-run faults did
not reproduce**; and after re-validation only **3 of 29,685 cases** were genuinely
nondeterministic. EXP-0144's revalidation reached a **0.02% hang rate** purely by re-running
victims — no lease involved.

### The rule

1. **Run your bulk sweep concurrently, unlocked.** Most cases never hang.
2. **Record the OS fault-classification string on every non-`ok` case.** This is what makes the
   scheme work — a victim is identifiable, so it is re-runnable.
3. **Never conclude `fault` from one observation.** Re-run every `fault`/`hang`/victim case;
   majority-of-3 minimum. This alone recovers essentially all contamination.
4. **Take the lease ONLY around work you have reason to believe HANGS**, because a hang harms
   every other agent on the device:
   ```sh
   ~/agxre/gpulease.sh EXP-NNNN 900 -- <the hang-prone sweep>
   ```
   Known hang-prone: `fspecial` byte+3 ≥ 192 (EXP-0138, three reproducible hangs); control-flow
   displacement sweeps (EXP-0128 stopped after two); `atomic_tg` byte+5 `0x7E`/`0x7F` (EXP-0141);
   `min_lod_clamp`, which took the compiler service down machine-wide on G16G (EXP-0106); and any
   arm that has already hung once for you.
5. **Also take it while re-validating**, so your re-runs are not themselves victims.

Lease mechanics: atomic via `mkdir` (macOS has no `flock`), stale leases broken after 15 minutes,
releases on EXIT/INT/TERM, exit **75** on timeout. Hold it around a batch, never per case, never
across analysis or file transfer.

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
