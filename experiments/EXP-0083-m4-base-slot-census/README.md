# EXP-0083 M4 device-buffer base-slot census (MEM-15..MEM-17)

Public-Metal splice-and-observe probe answering Part-II questionnaire items
**MEM-15, MEM-16, MEM-17** of `APPLE9_RE_IMPLEMENTATION_GAPS.md`
("P0 — Memory addressing and robustness"): the capacity, the alias/hole/
reservation map, and the unpopulated/out-of-range behavior of the
device-buffer **base_slot** field of the Apple9 memory family
(`device_load`/`device_store`/atomic, base-slot selector byte), for the
compute stage, on the local M4.

Method: nine authored kernels (a 31-binding census kernel + differential
variant, a 4-binding control + variant, an all-slots capacity kernel, a
store probe + variant, an atomic probe + variant) compiled from our own MSL
by `tools/shdump`; the probe instruction's base-slot selector byte located
pre-capture by differential compilation (census kernels: exactly one
differing byte) or unique-instruction decode (store/atomic); then ONE
spliced byte per case, one fresh harness process per case, all 31 MSL
buffer indices bound to 64-byte buffers filled with the frozen pattern
`P(k,w) = 0xC0DE0000|(k<<8)|w` so every 32-bit read anywhere identifies
(buffer, word). 351 frozen cases per run: the full 0..255 slot sweep on the
31-binding kernel, a 76-value boundary subset on the 4-binding control, the
capacity baseline, 8 store cases, 10 atomic cases. Faults, hangs, and kills
are recorded results (`watchdog`/`proc_fail`/`proc_timeout`), never retried
in place.

Process: pre-registration + capture contract with frozen hashes first;
`verify.py --selftest` proves every schema gate satisfiable and
fail-correct, the smoke validator pure against the EXP-0072 truncation
class, witness-corruption observations admissible, and — the EXP-0075 fix,
mandatory — a gate-sequence state-machine walk that proves every contracted
gate runnable and satisfiable at the state where the contract invokes it.
A NON-RECORDED smoke invocation (one scratch case) runs before the
append-only raw tree is created. Two contracted runs; the cross-run repeat
gate (identical statuses; identical probe_word in the zero/pattern classes)
is implemented once and shared by analysis and verify.

Successor to QUARANTINED `EXP-0078-m4-base-slot-census`: its run01 captured
clean (351/351 ok) but its verifier hardcoded the probe opcode as `0x67` for
every kernel, which is false for `storeprobe`'s `device_store` (`0xe7`) —
permanent `--between-runs` failure, never a real defect in the observations.
Fixed here with ONE shared definition (`run.insn_opcode`, taking the
expected opcode from the recorded `insn_hex` rather than assuming it) used
identically by the runner's self-check, `verify.py`'s `build_record_checks`,
and its `--selftest` synthetic-tree builder, plus a dedicated selftest
fixture pair (`ident_opcode_realistic_per_kernel_passes` /
`ident_opcode_mismatch_storeprobe`) proving the ident path passes on a valid
tree and fails on a mutated opcode in the run01-present state. The nine
kernels, harness, and 351-case matrix are otherwise unchanged from EXP-0078;
its disclosed run01 observations are re-registered in
`PRE_REGISTRATION.md` as hypotheses to independently re-establish.

Scope: **compute-stage, direct-binding, public-Metal splice evidence on the
local M4 (G16G) only.** No A18 (G17P) claim (hands-off), no Linux/UAPI
claim, no constant-program/uniform-pipe table claim (MEM-18/19 successor),
and no claim about slots beyond what the direct-binding path can populate
except their observable behavior.

Commands (in order):

```sh
python3 -B verify.py --selftest                       # required before any build
python3 -B make_manifest.py --write && python3 -B make_manifest.py --check
python3 -B verify.py --preflight                      # PRE_GPU: no raw tree may exist
python3 -B run.py --execute --run-id m4-20260827-run01
python3 -B make_manifest.py --write && python3 -B make_manifest.py --check
python3 -B verify.py --between-runs
python3 -B verify.py --selftest                       # must still run with run01 present
python3 -B run.py --execute --run-id m4-20260827-run02
python3 -B analysis.py --run-a m4-20260827-run01 --run-b m4-20260827-run02 --write
python3 -B make_manifest.py --write && python3 -B make_manifest.py --check
python3 -B verify.py --captured
```

Clean-room provenance: HW-PROBE / OWN-SHADER / PUBLIC API
Inputs inspected: authored MSL/harness/runner/verifier/analysis sources;
`tools/shdump`, `tools/agxtest`, `tools/agx-isa` invoked read-only
Apple binary introspection: NONE (only our own compiled shader bytes are
spliced and executed)
Reproduction: the command sequence above, from this directory
Evidence: `raw/m4-20260827-run01`, `raw/m4-20260827-run02`,
`analysis.json`, `manifest.json`
