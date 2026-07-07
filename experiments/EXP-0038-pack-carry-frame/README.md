# EXP-0038: close remaining census-undecoded compute groups (half pack / u64 carry / non-leaf frame / cache-bit)

- **Date:** 2026-07-07
- **Clean-room category:** OWN-SHADER + HW-PROBE (+ PUBLIC for the applegpu *shape*)
- **Phase / question:** ROADMAP G-13 (instruction census → ~0 undecoded groups); wrap-up W2. Closes the
  concrete backlog EXP-0036's census flagged: half pack/unpack `0x18/0x30/0x38`, u64 carry-generate `0x32`,
  non-leaf frame prologue `0x6f` (+ `0x07` link save/restore), and the `0x54↔0x56` cache-bit gating for
  `simd_reduce` / pack / unpack.
- **Device state:** Apple A18 Pro / G17P, SoC T8140, macOS 26.6 (25G5043d), Metal 4 / Apple9. No boot-arg/nvram changes. No faults, no reboots.

## Hypothesis
The four census-undecoded compute groups are (1) 16-bit/half lane pack/assembly ops (`0x18/0x30/0x38`)
that combine the native-half (`0x10`) ALU lane results into a packed 32-bit register for storage;
(2) a `0x32` carry-generate op that produces the carry for the compiler's explicit 64-bit-add chain
(EXP-0033); (3) a `0x6f` non-leaf frame prologue + an `0x07` link save/restore that bracket nested
calls (EXP-0035 inferred); and (4) a `0x54↔0x56` byte+2 bit that is a source cache/last-use *hint*
(not an opcode change), so the byte+2-gated descriptors must accept both values.

## Method (clean-room legal: OWN-SHADER + HW-PROBE)
Write MSL that provokes each feature (half2/half4 pack, `unpack_*`, `pack_*`, `ulong` add, a non-leaf
call chain, `simd_*` reductions in different consumer contexts). Compile it on-device with our own
`shdump` (runtime `newLibraryWithSource:`), extract every `_agc.main` **and helper region** with our own
`agxparse.py`, tokenize with the READ-ONLY `tools/agx-isa` DB, byte-diff minimally-different kernels to
localize fields, and **splice-and-run on the real GPU** (`agxtest.py`) to hardware-validate semantics.
Every byte inspected is the compiled form of MSL we wrote; no Apple binary was disassembled.

## Procedure (reproducible)
On the device workspace `~/cleanroom_work/exp0038/` (tools copied from `tools/shdump`, `tools/agxtest`,
`tools/agx-isa`; build `shdump`/`agxrun`/`agxrun_persist` with `clang -fobjc-arc -framework Metal -framework Foundation`):

```sh
# 1. tokenize the four kernel families (per-op byte0/byte+2 detail):
python3 analyze.py halfpack ; python3 analyze.py u64carry ; python3 analyze.py cachebit
# 2. dump helper regions (the 0x6f non-leaf prologue lives in the HELPER, not _agc.main):
python3 dumpregions.py kernels/frame.metal k_chain   # + k_deep, k_bigframe
# 3. HW-validate semantics + splice-prove the 0x32 carry op is load-bearing:
python3 agxtest.py --source kernels/u64carry.metal --function k_u64add --grid 1 --tg 1 --int \
    --buf 0=-1,0 --buf 1=1,0 --out 2=2 --expect 2=0,1                 # carry: lo=0 hi=1
python3 agxtest.py ... --splice _agc.main@0x2a=00                     # neutralize 0x32 -> carry lost
python3 agxtest.py --source kernels/halfpack.metal --function k_h2roundtrip ... # half pack round-trip
python3 agxtest.py --source kernels/frame.metal --function k_chain ...          # non-leaf frame
```
Then, on the host, verify the proposed length-rule / match-gating fixes tokenize the previously-undecoded
streams to 0 leftover, WITHOUT editing `tools/agx-isa` (monkeypatch): `python3 verify_fixes.py`.

## Raw results
See `raw/`:
- `tokenize_dumps.txt` — per-op tokenization of every half/u64/frame/cachebit kernel (+ helper regions).
- `hw_validation.txt` — HW dispatch + splice results (half round-trip exact; all u64 carry cases; 0x32
  splice drops the carry; non-leaf frame + deep chain correct; simd_sum → 32).
- `verify_fixes.txt` — the proposed fixes tokenizing all six problem streams CLEAN (0 leftover),
  incl. the 0x54 cache-bit variants now NAMING as `simd_reduce` / `unpack_convert`.

Key raw op bytes (OUR OWN compiled kernels):
- half2 pack: `18 05 18 03` (add) · `18 05 19 03` (mul) · `18 05 1b 07` (fma) — 4 bytes, after the `0x10` half ALU.
- u64 add chain: `9f…`(low add) · **`32 01 35 03 22 81`**(carry-gen) · `05 00 20 80`(psel) · `9f…`(high) · `9f…`(+carry).
- non-leaf `mid()`: **`6f 03 04 00 00 20`**(prologue) · `07 00 54 00 81 00 00 00`(link save) · call · `07 00 54 00 81 ff 1f 00`(link restore) · … · `8f 12 54 00`(non-leaf ret).
- simd reduce cache-bit: standalone max = `bf 03 56 …`; the same max as 2nd consumer of a shared source = `bf 03 54 …`.

## Analysis
See `RESULTS.md` for the full decode. Established facts feed `docs/isa` via `new_descriptors.json`
(4 new descriptors + 6 length-rule additions + 3 match-gating relaxations, all in the `tools/agx-isa`
db.json schema). HW-validated vs inferred is marked per finding.

## Established facts → docs
- `carry_gen` (0x32), `frame_prologue` (0x6f), `link_save_restore` (0x07 8B), `half_pack` (0x18) → `docs/isa` (via `new_descriptors.json`).
- Length-rule + match-gating fixes (0x6f, 0x07 link-vs-barrier, 0x32, 0x18, simd_reduce/unpack/pack cache-bit) → `tools/agx-isa` (orchestrator merges) → clean re-run census.

## Follow-ups
- Isolate the `0x6f` frame-size field (byte+5) with a callee that genuinely spills scratch *around* a call.
- The `0x30/0x38` half-pack siblings + the 6-byte high-register `0x18` form (byte+2==0x24): exact length + role.
- The `0x73` (`73 00 00 01`) second frame/call marker EXP-0036 saw alongside `0x43`.
- Splice-isolate `carry_gen` / `link_save_restore` operand fields; the 3-operand `0x22`/`0x12` carry siblings.
