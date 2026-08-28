# RESULTS — EXP-0144: is the Apple9 pack/convert family EMITTABLE?

**Clean-room provenance**

```
Clean-room provenance: OWN-SHADER + HW-PROBE (+ PUBLIC for IEEE-754 and the MSL
  format-conversion definitions, used only to write the host oracle, never to
  source an Apple9 encoding fact)
Inputs inspected: kernels/carriers.metal + kernels/anchors.metal (authored here)
  and the machine code compiled from them; tools/agx-isa/db.json (this project's
  own, read-only)
Apple binary introspection: NONE
Reproduction: README.md "Reproduction"
Evidence: raw/m4_20260828_run03/, raw/m4_20260828_run05/ (append-only JSONL);
  three retained partial captures with their own PARTIAL.md; analysis/*.json
```

**Target: local Apple M4 / G16G only** (10 GPU cores, macOS 26.6.2 build 25G82,
Metal 4). The A18 Pro was not touched. Nothing here is A18/G17P-validated.

**Concurrency (`FIELD-SWEEP-PROTOCOL.md` §7.4).** This experiment ran in
orchestrator batch 2 with **two** other GPU-contending experiments (EXP-0140,
EXP-0147) — three in total, not ten. Contention was directly visible and is
quantified in §6: 37 `...ErrorInnocentVictim` responses out of 8,412 dispatches in
one run, and one host-wide `MTLCompilerService` outage that killed a capture.

---

## 0. Headline

| | |
|---|---|
| Blocking fields at dispatch | **51** |
| Reached emitter grade | **44** (35 `hardware-run`, 9 `isolated-byte-diff`) |
| Still `untested` | **7** (2 dst nibbles, 5 `packed_half2_hi` fields) |
| Instruments fully measured | 8 of 9 |
| `db.json` defects found | **6**, all recorded under `db_defects`, none patched here |

The single most useful outcome is not a label count: **`pack_convert`'s and
`unpack_convert`'s operand structure in `db.json` is wrong**. Both model several
live operand bytes as one opaque raw descriptor (`fmt_word`, `convert_desc`). The
sweeps show those bytes are the destination register, the two per-lane source
registers, and an emittable **format selector** with a decoded code table. An
implementer following `db.json` today cannot emit either instruction; with §2 they
can.

---

## 1. What was actually run

| arm | cases | what |
|---|---|---|
| `C` | 19 | baselines + pre-registered falsifiers |
| `S` | 70 | semantics/rounding over hand-chosen boundary vectors |
| `F` | 15,829 | every byte of every instruction, dense 0..255 (byte 0 bounded to 24, §7) |
| `W` | 175 | whole-field values for `fmt_word` (40b) and `convert_desc` (32b) |
| `X` | 6,144 | format byte × 8 semantic vectors |
| | **22,237** | frozen matrix, sha256 `00529a0a…` |

Captures used for the results below: `m4_20260828_run03` (complete, 22,237 cases,
634 s) and `m4_20260828_run05` (8,412 cases; complete for `pack_convert` and for
`unpack_convert`'s `F` arm). Three further captures are **retained but unused**,
each with its own `PARTIAL.md` (§6).

### Controls — all passed

* **9 / 9 carrier baselines reproduced the host oracle exactly.** Without this the
  arms would be void.
* **10 / 10 pre-registered falsifiers failed the anchor oracle, as pre-registered.**
  Every instrument therefore demonstrably *can* show a difference; a "no effect"
  result elsewhere is a measurement, not an insensitive probe.
* **66 / 70 semantic vectors exact.** The 4 exceptions are `packed_half2_hi` and are
  themselves the finding of §4.

---

## 2. `pack_convert` — the model in `db.json` is wrong, and the real one is emittable

`db.json`: `src_desc`(+1) `fmt_class`(+2) `src`(+3) `mode`(+4) `fmt_word`(+5..+9, 40 bits raw).

**Measured** (dense 0..255 per byte; gated run03 ↔ run05 at **99.936 %**, 6,251/6,255
records byte-identical):

| byte | db name | what it actually is | emission rule |
|---|---|---|---|
| +1 | `src_desc` | operand descriptor | `v & 0x05 == 0x04` — bits 1,3,4,5,6,7 **don't care** |
| +2 | `fmt_class` | **1-bit enable** | reproduces the result **iff bit 1 is set**; bits 0,2–7 inert |
| +3 | `src` | **DESTINATION register** | `reg << 1`, bit 0 don't care — result redirected into **6 distinct** observed registers |
| +4 | `mode` | 1-bit enable | iff bit 1 set; all other bits inert |
| +5 | *(fmt_word)* | **lane-0 SOURCE register** | `reg << 2`, bits 0–1 don't care |
| +6 | *(fmt_word)* | **lane-1 SOURCE register** | `reg << 3`, bits 1–2 don't care, bit 0 must be 0 |
| +7 | *(fmt_word)* | unknown — **2 genuine hangs stopped this area at 8 values** | not established |
| +8 | *(fmt_word)* | conversion enable | `bits 2 and 6 both set` (exact over 256) |
| +9 | *(fmt_word)* | **FORMAT SELECTOR** | see the code table below |

**Format code table (byte +9), each code confirmed against 8 independent semantic
vectors — a code is only listed if ONE host model explains EVERY vector:**

| byte+9 | format produced |
|---|---|
| `0x42 0x46 0x4a 0x4e` | **snorm2x16** (scale 32767) |
| `0x82 0x86 0x8a 0x8e` | **unorm2x16** (scale 65535) |
| `0xc2 0xc6 0xca 0xce` | **unorm 8-bit lanes** (scale 255) into bits [7:0] and [15:8], bits 31:16 zero — consistent with the low half of a `unorm4x8` pack, since this carrier supplies only two lanes |

Bits 2 and 3 are don't-care (hence the four codes per format); bits 6:7 select the
format. **This is a third pack format reachable from the same instruction**, which
our corpus never showed because the compiler emitted only the two 16-bit forms here.
Spot-checks against the raw records: `0x42`, `(0.25, 0.75)` → `0x5fff2000` = snorm
`(8192, 24575)`; `-1` clamps to `0x8001` = `-32767`, the symmetric scale of EXP-0079;
`0x82`, same input → `0xbfff4000` = unorm `(16384, 49151)`; `0xc2`, same input →
`0x0000bf40` = `(64, 191)` = `round(0.25*255), round(0.75*255)`. Every code was
confirmed on all 8 vectors, NaN and out-of-range inputs included.

The per-lane source registers were read off directly: byte+5 values `{0,1,2,3}`
select the register holding `v1`, `{8..11}` the one holding `v0`, `{20..23}` `v5`,
and so on for six distinct registers; byte+6 does the same one bit-shift up.

---

## 3. `unpack_convert` — byte +2 characterised exactly, and `reg_sel` is not a register

The dispatch flagged byte +2 as newly open after commit `2b1cbc50` relaxed the
match. Dense 0..255:

> **`unpack_convert` byte+2 reproduces the conversion iff `(byte & 0x03) != 0`.**
> Bits 2–7 are completely inert. Exact over all 256 values.

This **reconciles two prior results that looked inconsistent**. EXP-0089 found
`0x56 → 0x54` breaks the instruction: `0x54 & 3 == 0`, so it does. EXP-0119's 7-bit
re-sweep flipped single bits of `0x56` and found all seven inert: every such flip
except bit 1 leaves `(byte & 3) != 0`, so it is. Neither observation was wrong;
both are the same two-bit OR-enable seen through a one-bit window. `db.json`'s
relaxed match (bit 1 only) is still not the hardware rule.

Rest of the instruction (`db.json` models bytes +3..+6 as one 32-bit `convert_desc`):

| byte | db name | what it actually is | emission rule |
|---|---|---|---|
| +1 | `src_class` | descriptor | `bits 0,2 == 0,1` (exact over 256) |
| +2 | `cache` | **2-bit OR enable** | `(v & 0x03) != 0`; bits 2–7 inert |
| +3 | *(convert_desc)* | **DESTINATION register** | result redirected into 3 distinct observed registers |
| +4 | *(convert_desc)* | **completely INERT** | all 256 values reproduce the result |
| +5 | *(convert_desc)* | **SOURCE register** | `reg << 3`, bits 0–2 don't care |
| +6 | *(convert_desc)* | opcode/descriptor | `bits 0,2 == 0,1` (exact over 256) |
| +7 | `size` + `reg_sel` | **FORMAT + a source-register bit** | see below |

**`reg_sel` is not a register selector.** `db.json` calls byte+7's high nibble "most
likely the unpack RESULT destination (role INFERRED)". Measured, with the source
identified by which live value came back:

| byte+7 | result |
|---|---|
| `0x0a 0x8a` | **unorm8** unpack of the low byte |
| `0x2a 0xaa` | **snorm16** unpack |
| `0x4a 0xca` | **unorm16** unpack (the anchor's format) |
| `0x6a 0xea` | **unorm8** |

so bits 6:5 select the format and bit 7 is don't-care, while **bit 3 changes which
register is read** (`0x_2` reads a different source than `0x_a`). This also explains
the pilot observation that our own compiler emits `…1cca` for unorm2x16 and `…1caa`
for snorm2x16 — a *format* difference that `db.json` attributes to a register.

---

## 4. The `cvt_*` cluster shares one operand layout — exploited with one sweep design

`cvt_i2f`, `cvt_i2f_src` and `cvt_f2i` share a byte layout, and the sweeps confirm it
byte for byte. `cvt_f2h` and `cvt_f2h_dst` turn out to be **the same encoding**.

| byte | `cvt_i2f` | `cvt_i2f_src` | `cvt_f2i` |
|---|---|---|---|
| +1 | `bits 1,2 set` | `bits 1,2 set` | `bits 0,1,2 set` |
| +2 (`mode`) | `(v & 3) != 0` | **INERT, all 256** | `(v & 3) != 0` |
| +3 (`dst`) | **`reg << 1`**, 6 registers observed | same | same |
| +4 (`src_class`) | bit 1 | bit 1 | bit 1 |
| +5 (`src`) | **`reg << 2`** | **`reg << 4`** | **`reg << 2`** |
| +6 (`cvtop`) | `bits 0,2,7 == 0,1,1` | same | `bits 1,2,6 don't care` |
| +7 (`signflag`) | bit 5 | bit 5 | `bits 3,5 == 1,0` |
| +8 (`dst_class`) | — | — | bit 1 |
| +9 (`b9`) | — | — | **INERT, all 256** |

The destination map is the strongest single result in the cluster: sweeping byte +3
moves the conversion result into **six different output slots**, each at a
predictable field value (`slot6←{0,1}`, `slot5←{6,7}`, `slot4←{10,11}`,
`slot3←{14,15}`, `slot2←{18,19}`, `slot1←{22,23}`, anchor `slot0←{24,25}`), i.e.
`field = register << 1` with bit 0 free. `pack_convert` byte +3 produces the
**identical** map, which is why §2 reclassifies it from `src` to `dst`.

**Rounding (both pre-registered hypotheses resolved):**

* **H5 — `pack_float_to_unorm2x16` ties round to NEAREST-EVEN.** All 16 pack
  semantic vectors matched an RTE oracle exactly, including three exact ties built
  with `Fraction` arithmetic. The competing pre-registered model (ties round **down**,
  as EXP-0133 measured for the unorm16 **storage** path) is **refuted for this
  instruction**. The ALU pack path and the PBE store path round differently — an
  implementer must not reuse one rule for the other.
* **H6 — `cvt_bf16` float→bfloat rounds RNE.** All bfloat semantic vectors, including
  three exact bf16 ties, matched the RNE oracle; the competing "truncate toward
  zero" model (EXP-0079's rule for reduced-float stores) is **refuted**.
* fp16 narrowing matched IEEE round-to-nearest-even throughout, including the
  65520.0 overflow tie that must carry to `+inf`, subnormals, and NaN/Inf.

**`packed_half2_hi` — a positive result from a purely synthesised encoding.** It
could not be provoked from any MSL shape tried, so it was assembled from `db.json`
and spliced over the carrier's own `half_alu`. It **executes**, and it computes the
packed-half2 multiply **for the high lane only**, leaving the low lane at zero —
reproducibly across all four semantic vectors. That matches the instruction's name
and explains why the compiler emits `half_alu` (low half) plus a 4-byte
`0x18`-leader companion as a pair. Its operand *fields* remain `untested`: the byte
sweep destabilised the carrier and was stopped by the cascade rule (§6).

---

## 5. The 0x54/0x56 bit position: three more distinct behaviours

The dispatch warned this position has ≥4 distinct behaviours across families. This
experiment adds three more, each now stated exactly rather than as a bit-flip:

| family | byte+2 behaviour, measured over all 256 values |
|---|---|
| `pack_convert` | enable = **bit 1 alone**; bits 0,2–7 inert |
| `cvt_i2f`, `cvt_f2i`, `unpack_convert` | enable = **bit 0 OR bit 1**; bits 2–7 inert |
| `cvt_i2f_src` | **completely inert** — all 256 values reproduce the result |

`cvt_i2f_src` is the notable one: it is the sibling that EXP-0089 identified as
carrying the load-bearing "source-consumed-by-a-following-ALU" routing, and in this
carrier — which *does* feed a following ALU add — the byte has no effect at any
value. This is reported as an unresolved tension with EXP-0089, not as a
refutation: the two carriers differ, and this experiment did not reproduce
EXP-0089's exact construction.

---

## 6. Contamination, faults, and what that cost — `FIELD-SWEEP-PROTOCOL.md` §7

Every §7 requirement was implemented before the first recorded case; the guards
earned their keep.

**§7.1 — never conclude `fault` from one observation.** Every faulting case was
re-measured after a carrier baseline re-validation. In run03, **134 fault
observations reproduced and 27 did not** (≈17 %). Without this guard those 27 legal
field values would have been labelled `fault` in `validation.json`. (EXP-0139
measured 44 % under a ten-agent load; 17 % under three is consistent.)

**§7.2 — the OS fault-classification string is recorded verbatim.** 37
`kIOGPUCommandBufferCallbackErrorInnocentVictim` responses in run05's 8,412
dispatches were retried and excluded from the gate as machine evidence, separately
from `…ErrorHang`, which is encoding evidence.

**EXP-0141's third mode — `STATUS OK` with nothing executed.** Every carrier writes
an integrity sentinel through an independent path. The first design was **wrong and
the data caught it**: a two-way clean/absent test marked 32 % of a smoke run
`invalid`, because a splice that changes an instruction's *length* desynchronises
the downstream stream and moves the sentinel store — the sentinel comes back
non-zero but wrong. That is a *result about the encoding*, not contamination.
Re-designed three-way (`clean` / `perturbed` / `absent`), only `absent` under
`STATUS OK` is `invalid_run`. The `perturbed` count is reported per byte in
`analysis/byte_scans.json` and is how a length-desync is told from a clean silent zero.

**Unique splice-archive path per request** (EXP-0141: ~8 % phantom `CMDBUF_ERROR`
from a shared path). Adopted; it cost throughput — the 2,400 dispatches/s measured
with a shared path was partly Metal serving a cached library, i.e. *not re-executing*.

**§7.3 — periodic baseline re-validation.** Every 250 cases. This fired twice for
real, and both times the honest action cost data (§6.1).

**Genuine GPU hangs: 7 in run03** (global cap 10, not reached), stopping three
areas: `cvt_f2i` byte+3, `cvt_i2f_src` byte+3, `pack_convert` byte+7. Hang areas are
`(instruction, swept byte)` — a hang while sweeping the opcode leader says nothing
about an operand byte five positions along.

### 6.1 Three retained partial captures, and one host outage

Per CODEX, each is retained unmodified with a `PARTIAL.md`, and none is used for any
verdict:

* **`run01`** (3,137/22,237) — killed by **our own oracle**: Python's
  `struct.pack('<e')` raises on fp16 overflow instead of producing `±inf`, and the
  boundary vector deliberately contains 65520.0. Replaced with an exact integer
  fp16 RNE encoder, cross-checked against Python over 20,000 random bit patterns,
  plus a mandatory pre-flight that evaluates the oracle over *every* case vector
  before a single dispatch.
* **`run02`** (5,219/22,237) — the baseline check failed *inside this sweep's own GPU
  error-recovery window* (five self-inflicted hangs in the preceding 300 cases) and
  was recorded rather than retried. Stopped by hand per §7.3. `baseline_check` now
  retries four times with a settle delay; only an all-attempts failure is a cascade.
* **`run04`** (record-complete, scientifically empty) — launched immediately after
  run03's cascade, before the device had recovered; cascaded at case 12105 after
  57 s. Runs now get a settle gap.

**`run05` was killed at 8,412 cases by a host-wide `MTLCompilerService` outage**
("The process is unavailable because the compiler is no longer active … Connection
init failed at lookup with error 141 - Reentrancy avoided"), triggered when the
persistent runner tried to restart its child after a GPU wedge. A fresh `shdump`
compile failed identically, so this was not confined to this experiment — with
three experiments driving the Metal compiler concurrently it is a plausible
contention effect. Per `CLAUDE.md` the host was **not** thrashed and no tool-based
reboot was attempted; the capture driver was restructured to **one process per
instrument** (`harness/capture.sh`) so a future outage costs one instrument rather
than a 22k-case run.

**A harness-ordering bug cost the top-priority instrument once.** run03 executed
carriers alphabetically, so when the MODE-A `packed_half2_hi` arm cascaded the GPU
the run stopped with `unpack_convert` entirely unrun. Fixed: priority order
(`pack_convert`, `unpack_convert` first, the dangerous synthesised carrier last) and
a cascade now stops only the offending carrier — which *is* §7.3's "resume in a
fresh process", because every carrier gets its own runner child.

### 6.2 Gate status — honest, and not uniform

| instrument | gate |
|---|---|
| `pack_convert` | **GATED**: run03 ↔ run05, 6,251/6,255 gated records byte-identical (**99.936 %**). The 4 differences are all the contained-hang vs watchdog-hang boundary the protocol warns about, plus one wide-field `wrong_value`/`silent_zero`. |
| `unpack_convert`, `cvt_*`, `packed_half2_hi` | **SINGLE OBSERVATION.** run03 covers the `cvt_*` cluster; run05 covers `unpack_convert`'s `F` arm. The second capture that would gate them was prevented by the `MTLCompilerService` outage. |

**Consequence, stated plainly:** the labels in `analysis/field_verdicts.json` are
derived from a dense hardware sweep, but for every instrument except
`pack_convert` they rest on **one** capture. Under this experiment's own
pre-registration §8 that is not the two-run reproducibility this project requires.
The orchestrator should either treat the non-`pack_convert` labels as provisional
pending a second capture (`./harness/capture.sh m4_YYYYMMDD_run06`, which re-runs
every instrument as an independent shard and is designed to merge with run03/run05
via `--runs "run03+run05" run06`), or downgrade each by one step.

---

## 7. Deliberate deviation from "sweep all 2^w"

Byte 0 is the **opcode leader**, not an operand field: changing it changes the
instruction's length and desynchronises the downstream stream. A smoke run produced
a genuine `kIOGPUCommandBufferCallbackErrorHang` from `cvt_bf16` byte0 = 0xFF, and
this host has no out-of-band recovery. Byte 0 therefore got a bounded 24-value probe
(all 16 values of the high nibble, which *is* the `dst` field in `cvt_f2h_dst`,
`cvt_bf16` and `packed_half2_hi`, plus 8 off-match values). **Every operand byte
still got the full dense 0..255.** The two `dst`-nibble fields are reported
`untested` rather than claimed from that bounded probe.

`pack_convert.fmt_word` (40 bits) and `unpack_convert.convert_desc` (32 bits) were
swept **per constituent byte, densely**, plus 175 whole-field values (0, all-ones,
every single-bit value, single-bit-cleared, anchor⊕bit). That exceeds the protocol's
`w>8` requirement but is **not** 2^40 / 2^32 coverage, and the `range` field of every
verdict says so.

---

## 8. `db.json` defects found (recorded, NOT patched — the orchestrator owns `db.json`)

Full detail with evidence in `analysis/field_verdicts.json → db_defects`.

1. **`pack_convert.fmt_word` is not one 40-bit field.** Bytes +5 and +6 are the two
   per-lane **source registers**, +8 a conversion enable, +9 the **format selector**.
2. **`pack_convert.src` (byte +3) is the DESTINATION**, not a source — it produces the
   same register-redirection map as `cvt_i2f`/`cvt_f2i`'s `dst`.
3. **`unpack_convert.convert_desc` is not one 32-bit field.** +3 destination register,
   +4 wholly inert, +5 source register, +6 opcode/descriptor.
4. **`unpack_convert.reg_sel` is a FORMAT selector**, not the result destination.
5. **`unpack_convert`'s byte+2 rule is still wrong after the relaxation**: the
   hardware enable is `(byte & 3) != 0`, not bit 1.
6. **`cvt_f2h` and `cvt_f2h_dst` are the same instruction** — identical bit rules on
   every byte; the two db entries differ only in the byte-0 dst nibble. Related:
   `cvt_f2h_dst` with dst nibble 0 (byte0 = `0x01`) has **no length rule**, so a whole
   class of the instruction fails to tokenize; and `byte0 = 0x18` (the
   `packed_half2_hi` family) has no length rule either.

Also recorded: `cvt_bf16`'s match pins byte+4 to `0x01`, but our own compiler emits
`0x05` there, so the descriptor fails to decode its own compiler's output.

---

## 9. Limitations

* **One capture for eight of nine instruments** (§6.2). This is the main limitation.
* The `signflag` sweeps used a **positive** fixed operand, so they separate
  "converts" from "silently zero" but **not signed from unsigned**. The sign
  semantics rest on the `S` arm's signed/unsigned vectors, not on the byte sweep.
* Absolute register *numbers* in the operand maps are inferred from the carrier's own
  compiler allocation; what is directly measured is the **scale** (`reg<<1`,
  `reg<<2`, `reg<<3`) and that six distinct registers are reachable.
* `pack_convert` byte +7 stopped at 8 values after two genuine hangs; it is the one
  operand byte in the two priority instruments left unmeasured.
* Compute only. No fragment/render-stage form of any of these instructions was tested.
* `packed_half2_hi`'s fields are untested; only its lane semantics are established.
