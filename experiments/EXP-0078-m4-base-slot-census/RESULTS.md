# EXP-0078 results — M4 device-buffer base-slot census (MEM-15..MEM-17)

## STOP — run 01 captured clean, run 02 structurally unreachable (frozen-verifier defect)

`raw/m4-20260827-run01` was captured **complete and internally consistent**
(351/351 cases, all `ok`, zero faults/timeouts/watchdogs, smoke gate passed,
probe identification recorded pre-capture). The frozen post-capture verifier
then cannot close it: `python3 -B verify.py --between-runs` fails **forever**
with

```text
FAIL ident probe opcode m4-20260827-run01 storeprobe
```

because `verify.py`'s identification check requires the probe instruction
opcode byte to be `0x67` for **every** kernel, but the store probe is a
`device_store` (`0xe7`, exactly as identified and recorded in
`02_build.json`). The gate is unsatisfiable against any real capture of the
contracted matrix — the EXP-0075 landmine class, in a new disguise: the
self-test's synthetic identification fixtures were *internally* consistent
(the synthetic storeprobe main carried `0x67` at the probe offset) but
*reality-inconsistent* (`run.identify` on the real kernel returns a `0xe7`
store), so `--selftest` (36/36 PASS) could not see it. Per `CODEX.md` there
is **no post-capture repair**: any fix changes `verify.py`'s frozen hash and
breaks the capture-time hash binding in `00_inputs.json`. The one-line fix
was applied, diagnosed, and **reverted**; the frozen bytes are restored and
the failure above is reproducible from this directory.

**Disposition: run 01 is retained append-only as process history —
single-run, repeat-unverified, NOT promotable evidence.** Everything below
is the verbatim record of what run 01 observed, to be re-established by the
successor (requirements at the end). MEM-15/16/17 remain **Open** in
`docs/` terms.

---

## OBSERVED (directly, from `raw/m4-20260827-run01/`, before interpretation)

- One run, `m4-20260827-run01`, 351 cases, one fresh harness process per
  case (fresh device, library, pipeline, 31 bound buffers, queue, command
  buffer). Status counts: `ok` 351, `cb_error` 0, `watchdog` 0,
  `proc_fail` 0, `proc_timeout` 0. **No fault, no hang, no command-buffer
  error anywhere in the matrix** — including every store and atomic through
  every unpopulated and mirrored slot value.
- Environment (recorded at capture): git revision
  `203c3138ab883dcc29385227a3781bb1fefe1d23` (repo dirty: this untracked
  experiment dir), python 3.14.6, `sw_vers` macOS 26.6.2 (25G82), device
  `Apple M4` (registryID 4294968259), `fast_math=true`, default
  `mathMode`/`languageVersion` recorded raw in every receipt.
- Probe identification (pre-capture, `02_build.json`): census31
  diff-single-byte at main+430 (slot byte 1↔2); census4 diff-single-byte at
  main+56; storeprobe unique non-out `device_store` at main+490 (byte+4 =
  29↔28 across variants); atomicprobe unique atomic at main+824 with the
  selector at **byte+5** (29↔28). All splice offsets derived from these
  records; one spliced byte per case.
- **census31 full 0..255 sweep** (31 buffers bound, MSL indices 0..30,
  probe = one `device_load`'s base_slot byte, reading word 5):
  - slots **1..30 → P(slot,5)** — every slot returns exactly its own
    buffer's word 5. No alias, no hole, `witness_ok` true and `changed`
    empty in all 256 cases.
  - **slot 0 → P(5,0)** — buffer 5's word **0** (a word-0 value under a
    word-5 probe), not buffer 0.
  - slots **31..127 → 0x00000000** (status `ok`).
  - slots **128..255 → exact mirror of 0..127** (128→P(5,0), 129→P(1,5),
    …, 255→0). Class histogram over the 256 slots: 30×P(k=1..30,w=5)
    twice (S and S+128), 2×P(5,0), 194×zero.
- **census4 boundary subset** (4 buffers bound, MSL indices 0..3):
  slots **0..3 → P(slot,5)** (slot 0 → P(0,5), i.e. the out buffer!),
  slots 4..127 → 0x00000000, slots 128..131 mirror 0..3, 132..255 zero.
- **capacity_baseline** (never spliced; reads all 31 bindings at once):
  status `ok`, `witness_ok` true, probe `P(1,5)`, `changed` empty — every
  one of the 31 simultaneous reads correct.
- **store cases**: baseline → `changed=[29]` (the probe store wrote
  buffer 29 word 5). slot 3 → `changed=[3]` (write retargeted to buffer
  3). slots 31, 32, 63, 127, 255 → `changed=[]`, status `ok` (discarded,
  no fault). **slot 128 → `changed=[]` but `witness_ok=false`: out word 5
  holds `0x5A17C0DE`** — the store landed in the OUT buffer (binding 0).
- **atomic cases** (32-bit exchange, selector byte+5): baseline → old
  value `P(29,5)`, `changed=[29]`. selector 3 → old `P(3,5)`,
  `changed=[3]`. selectors 31, 32, 63, 127, 255 → old value `0x00000000`,
  `changed=[]`, status `ok`. **selector 128 → old value `P(5,0)`,
  write discarded.** byte+4 probes (value 1 and 255 at the fixed selector)
  → old value 0, write discarded.
- Atomic/store kernels show `witness_ok=false` at exactly one word each
  (`out[29]=0` in atomicprobe; `out[31]=0` in several kernels): the
  compiler's vectorized stores write zero lanes into out words the source
  never writes. A compiler-output observation, not a slot observation;
  the one real slot-driven witness corruption is `st_store_slot_128`'s
  `out[5]=0x5A17C0DE`.

## INTERPRETED (candidate findings for the successor to re-establish)

1. **MEM-15 — capacity (compute stage, direct-binding path).** At least
   **31 base slots are simultaneously usable and independently correct**
   (the capacity kernel reads all 31 bindings at once; the census finds a
   30-slot bijective load map plus the store path). 31 is also the MSL
   `[[buffer(N)]]` API maximum (index must be "between 0 and 30"), so the
   direct path cannot probe beyond 31; the architectural ceiling above 31
   is NOT established by this experiment — slots 31..127 are simply
   unpopulated by this binding path (see MEM-17: they read zero, no
   fault). First failing slot by the mandated scan: **slot 31** (first
   slot returning zero instead of a distinct buffer value) — a
   binding-population edge, not a demonstrated architectural limit.
2. **MEM-16 — alias/hole/reservation map (tested range 0..255, every
   value).** Below the populated edge: **no aliasing and no holes** —
   slots 1..30 (census31) and 0..3 (census4) hold exactly their own
   binding, bijectively, including boundaries 7/8 and 15/16 which behave
   identically to their neighbors. **Slot 0 is a reservation candidate on
   the load path**: in census31 (whose thread-invariant loads were hoisted
   into the constant program, uniform-pipe slots {0,2,4,6,8,10,12}) a load
   through slot 0 reads a word-0 value at +20 B — consistent with a
   uniform-register window overlapping the constant program's preloads —
   while in census4 (no hoisting) load-slot 0 is the plain out buffer, and
   the STORE path through slot 0/128 hits binding 0 in both. I.e. load
   base 0 is pipeline-configuration-dependent (reserved), store base 0 is
   binding 0. **The selector is effectively 7-bit**: values 128..255
   mirror 0..127 byte-for-byte on all three op paths (load census, store
   128→out, atomic 128→the slot-0 load-path value).
3. **MEM-17 — unpopulated/out-of-range behavior, per op class.**
   - **LOAD**: reads `0x00000000`, command-buffer status OK, no bound
     buffer changes (194 zero observations across both censuses, including
     every boundary value 31/32/63/64/127/255).
   - **STORE**: discarded (no buffer changes, no fault). Through a
     populated slot it writes that slot's buffer (slot 3 → buffer 3); through
     128 (=0) it writes binding 0.
   - **ATOMIC (32-bit exchange)**: returns `0x00000000` and the write is
     discarded, no fault. Through a populated selector it exchanges that
     buffer (selector 3 → old `P(3,5)`, buffer 3 word 5 exchanged); through
     128 it returns the load-path slot-0 value and discards. Perturbing
     byte+4 (1/255) kills the access (returns 0, discards) — byte+4 is live
     but not the selector for this emitted form (selector = byte+5).
   - Fault containment: **no case in the matrix faulted the command buffer
     or the process.** A bad slot is a silent zero/discard, not a fault —
     which is fault-containment information, not a license to emit an
     invalid slot.
4. **ISA note for the orchestrator (tools are read-only here).** The
   emitted atomic form's base selector is **byte+5** (spliced 29→28 and
   29→3 retarget the exchange), byte+4 = 0x00 in both variants and is live
   (0→1 or 0xff → returns 0/discards). `tools/agx-isa`'s atomic_rmw /
   atomic_mem descriptors type byte+4 as `base_slot` and byte+5 as
   `index_reg` — at minimum PARTIAL/incorrect for these emitted forms on
   M4. The DB should be re-examined before any MEM-18/19 work builds on it.

## Exact tested range

census31: every slot byte value 0..255 (256 cases). census4: 76 boundary
values (0..16, 24..40, 56..72, 120..136, 248..255). store: baseline + slots
{3, 31, 32, 63, 127, 128, 255}. atomic: baseline + selectors {3, 31, 32,
63, 127, 128, 255} + byte+4 ∈ {1, 255} at fixed selector. capacity: one
unspliced baseline. All on the local **Apple M4 (G16G)**, compute stage,
direct `setBuffer:atIndex:` binding, runtime MSL compile, one spliced byte
per case, 1×1 thread dispatch. No A18 (G17P) claim; no Linux/UAPI claim; no
constant-program-table claim beyond the load-path slot-0 observation.

## What would have come next (frozen contract, blocked at run 02)

`run02`, `analysis.py --run-a --run-b --write` (cross-run repeat gate),
`verify.py --captured`, final manifest — the full sequence is frozen in
`CAPTURE_CONTRACT.json` (`full_gate_sequence`) and was proven walkable on
synthetic trees; only the real capture trips the opcode-check defect.

## Successor requirements (EXP-0080 or the orchestrator's choice)

1. `verify.py` `build_record_checks`: derive the expected probe opcode from
   the identification record itself (`insn_hex[0:2]`: 0x67 for loads and
   atomics, 0xe7 for the store probe) and additionally require
   `main[probe:probe+14].hex() == insn_hex`.
2. Harden `--selftest` against this class: synthetic identification
   fixtures must be REALITY-consistent — the minimal fix is to run
   `run.identify()` over the synthetic mains (with matching v2 mains) and
   require success, so the fixture builder cannot invent an opcode the
   real identifier would never produce; or embed the real run01
   `02_build.json` ident/insn bytes as the synthetic fixture.
3. Re-register the same 351-case matrix with run01's observations as
   hypotheses-to-re-establish (H2 sharpened: slot-0 load-path reservation;
   H3 extended: the 7-bit mirror), and re-run both captures.
4. The nine kernels, `harness/probe.m`, and `run.py` are unchanged by this
   defect and reusable verbatim (their frozen hashes match the capture).

Clean-room provenance: HW-PROBE / OWN-SHADER / PUBLIC API
Inputs inspected: authored MSL/harness/runner/verifier/analysis sources;
`tools/shdump`, `tools/agxtest`, `tools/agx-isa` invoked read-only
Apple binary introspection: NONE (only our own compiled shader bytes were
spliced and executed)
Reproduction: `python3 -B run.py --execute --run-id m4-20260827-run02`
is refused by the frozen gate (`FAIL ident probe opcode ... storeprobe`
at `--between-runs`); run01 replay requires deleting the append-only raw
tree, which the contract forbids
Evidence: `raw/m4-20260827-run01/` (351 case lines + 351 receipts + build
and identification records), `manifest.json`
