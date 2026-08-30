# EXP-0169 progress log (append-only)

## 2026-08-30 — M0: dispatch received, governing docs read
Read `CLAUDE.md`, `CODEX.md`, `experiments/SUBAGENT_BRIEF.md`,
`experiments/FIELD-SWEEP-PROTOCOL.md`, EXP-0164's `analysis/collect_raw.py` +
`analysis/audit.py` + `analysis/withhold_unverifiable.json`.
Device work is BLOCKED (EXP-0167 holds a quiet window, EXP-0168 queued).
Plan: all analysis + pre-registration offline first, then request the window.

## 2026-08-30 — M1: the 144 withheld fields characterised offline
144 fields, reasons: no-field-records 60, no-raw 47,
field-named-but-unstructured 24, raw-present-but-unattributable 13.
By descriptor: falu2 13, tex_addr_setup 11, matrix_mac 10, falu2i 9,
half_alu_ext8 7, link_save_restore 6, reg_move_* 23 (c0 5 / c1 4 / c2var 5 /
c9 5 / cb 4), tex_sample 5, half_alu 4, ... 
By citing experiment: EXP-M4-14 49, EXP-0140 20, EXP-0119 10, EXP-0112 10,
EXP-O2C 10, EXP-0090 8, ...

## 2026-08-30 — M2: 12 of the 144 need a CITATION FIX, not a device
Wrote `analysis/recitation.py`. EXP-0164's `audit.py::gather()` collects
observations ONLY from the experiments named in that field's `evidence` array,
so a field promoted on EXP-0016 is judged on EXP-0016's raw alone even when a
later experiment swept the same db field value-by-value with bit-exact records.
Re-running EXP-0164's OWN gate (`stable_live`, thresholds copied verbatim) over
the WHOLE raw index instead of only the cited experiments:

  RECOVERABLE-BY-CITATION   12
  RECORDS-BUT-FAILS-GATE     3   (icmp_pred.cond 97.66%, pixel_order.kind
                                  single run, ray_move.b3 255 values 0 moved)
  NO-RECORDS-ANYWHERE      129

The 12: device_load.base_slot, device_load.idx_off (EXP-0141);
falu2.opsel, falu2.srcA_reg, falu2.srcB_reg, falu2.srcB_reg_top (EXP-0153 —
G17P, i.e. BETTER than the cited M4/A18 evidence); falu2.srcB_reg_top also
EXP-0138; falu_srcmod12b.ctrl, falu_srcmod12b.opsel (EXP-0138);
ibitcount.form, ibitcount.op_enable, ibitcount.srcdesc (EXP-0139);
icmp_pred.dst_pred (EXP-0139).
NOTE: several of these move the field's `target` from A18 to M4, because the
uncited experiment ran on the M4. That is the orchestrator's call, not mine.

## 2026-08-30 — M3: scope split with EXP-0168 applied
Coordinator directive: EXP-0168 owns the field NAME `dst` on all 14 descriptors
that carry it, plus the 12 "one-field-away" fields (incl. `mov_imm.imm_top`,
`pixel_order.kind`, `stop.reserved`). Removed from my verdict scope:
falu2.dst, falu2i.dst, get_sr.dst, reg_move_{c0,c1,c2var,c9,cb}.dst,
mov_imm.imm_top, stop.reserved  (10 fields).
`dst` is still SWEPT here as the primary liveness-ladder instrument (which
register slot changed is my detection oracle) but NO VERDICT is emitted for any
`.dst` field — the raw is recorded and attributable, the verdict is EXP-0168's.
Open question for the orchestrator: is `get_sr.dst_hi` one of the 12?
My design already answers the coordinator's `uniform_mov.dst` hypothesis: the
oracle is the FULL 16-GPR dump, so "which register slot changed" is visible.

Device scope after the split: 57 fields.
  A falu2 family 17 : falu2 8, falu2i 8, falu2_uni 1
  B EXP-M4-14 ALU 15: half_alu 4, half_alu_ext8 7, half_alu_fma12 2, iunary 2
  C reg_move     18 : c0 4, c1 3, c2var 4, c9 4, cb 3
  D misc          7 : bf_alu.opsel, icmp_pred.cond, get_sr.{dst_hi,sr_sel},
                      device_store.{base_slot,idx_off,index_reg}
Out of scope, explicitly handed on (needs a graphics / texture / RT / control-
flow / spill-frame harness): tex_addr_setup 11, matrix_mac 10,
link_save_restore 6, tex_sample 5, frag_color_pack 3, frame_prologue 3,
rt_query_traverse 3, simd_shuffle 3, spill_frame_marker 3, frag_color_store 2,
iter 2, simd_reduce 2, vary_store 2, call 1, if_push_pred 1,
imageblock_load 1, imageblock_store 1, jump 1, ray_move 1, rt_intersect 1,
simd_ballot 1, tex_deriv 1  = 64 fields.

## 2026-08-30 — M4: harness written, offline code test green, contract FROZEN
Built (all authored here, structure reused-and-cited from EXP-0154/0141/0140/0138):
  kernels/probes.metal        28 authored probe kernels
  kernels/carrier_dag.metal   SYNTH host (3 buffers)
  kernels/carrier_uni.metal   uniform-preloaded host (our own EXP-0138 body, verbatim)
  harness/isa_helpers.py      3 seed provenances, sentinels, program builder,
                              the inline-minifloat host oracle
  harness/anchors.py          compile + tokenize + resolve arms (rule, not offsets)
  harness/casematrix.py       arms, carriers, coverage, ladder, falu2 crossings
  harness/run.py              gated driver + the semantic oracle
  harness/smoke.py            pilot S1-S5 incl. the liveness ladder
  harness/procsample.py       measures the quiet window instead of claiming it
  harness/selftest.py         OFFLINE code test (no device, NOT evidence)
  analysis/collect_raw.py     byte-identical copy of EXP-0164's indexer
  analysis/recitation.py      the 12 citation-recoverable fields
  analysis/verdicts.py        raw -> field_verdicts.json + reproduction.json
  analysis/reindex_check.py   THE ACCEPTANCE TEST

`python3 harness/selftest.py` -> 0 checks failed (66 checks). It verifies: matrix
determinism; set_field/get_field exactness and non-overlap across every falu2 field;
dense coverage of all 29 falu2/falu2i fields; the crossings; that the host-side
inline_minifloat reproduces EXP-0138's ten HW-confirmed points; that all three
program shapes build; that every reg_move SYNTH base tokenizes as its target
descriptor; and that every (arm,carrier) has a falsifier + >=2 ladder steps.

Matrix estimate 38,660 cases/gated run. At EXP-0154's MEASURED G17P throughput
(44.9 cases/s, from its own per-record timestamps) that is ~15 min/run, ~35 min for
the pair + pilot + anchor compiles.

CAPTURE_CONTRACT.json frozen: 18 authored blobs sha256'd, gate is the blob hashes
and NOT live HEAD, gated run ids fixed, promotion gate identical to EXP-0164's
audit.py::stable_live.

COURTESY WARNING for the orchestrator (FIELD-SWEEP-PROTOCOL 7 "courtesy"):
the DSTORE arm sweeps device_store.base_slot 0..255, i.e. stores through unbound
binding slots. Faults are expected and are results. If it wedges the device it will
be this arm.

STATUS: BLOCKED on the device. Messaging the orchestrator for (a) the SSH password,
(b) a ~75-minute quiet window, (c) a ruling on whether get_sr.dst_hi is one of
EXP-0168's 12 "one-field-away" fields.

## 2026-08-30 — M5: self-falsification of my own headline, and the coordinator's rulings
Tried to break the §1 finding before reporting it, and found a real caveat.
EXP-0164's gate (`stable_live`) has NO coverage term — `THIN_COMMON=8` exists in
audit.py but only sets an informational `thin_cross_run` flag and the gate never
consults it (audit.py:28, :188). So RECOVERABLE-BY-CITATION means "clears
EXP-0164's gate", NOT "meets the evidence-classification §2 hardware-run range
bar". Measured against each field's encodable range:
  FULL RANGE (4): falu2.srcB_reg 64/64, falu2.srcB_reg_top 2/2,
                  ibitcount.srcdesc 256/256, icmp_pred.dst_pred 16/16
  THIN     (8): falu_srcmod12b.opsel 7/8, .ctrl 62/128, falu2.opsel 2/8,
                device_load.base_slot 16/256, ibitcount.op_enable 16/256,
                falu2.srcA_reg 2/64, ibitcount.form 8/256,
                device_load.idx_off 14/2048
For the 8, the citation fix repairs ATTRIBUTION and leaves RANGE open. falu2.*,
ibitcount.* and icmp_pred.* are swept densely by my matrix anyway (I sweep every
field of every target descriptor), so their range closes on G17P for free;
falu_srcmod12b.* and device_load.* are in no arm of mine and stay open.
Recorded as amendment_04. RESULTS §1 now carries the coverage table.

Coordinator rulings applied:
  R1 get_sr.dst_hi is MINE; get_sr.form is EXP-0172's -> FOREIGN_FIELDS is now
     per-descriptor {"dst" (any), "get_sr.form"}. Device field count still 57.
     (amendment_02)
  R2 the re-citation finding is his to act on; keep it quarantined from the
     re-record verdicts. Already so — separate file, separate RESULTS section.
  R3 icmp_pred.cond stays in device scope; re-measure, do not argue 97.66% past
     the bar. Unchanged.
  Concurrency: gated runs go UNLOCKED alongside EXP-0168/0171/0172; offline
     adjudication (poison + both sentinels + 16-GPR dump, EXP-0160's filter)
     becomes the primary defence and procsample.py measures what was actually
     running. (amendment_01)
  Scheduling: TWO gated pairs. run01/run02 = every arm except DSTORE.
     run03/run04 = DSTORE only, LAST, after pair 1 is pulled back and after
     telling the orchestrator so others are held off. verdicts.py now takes N
     runs and pairs PER FIELD by most-distinct-values (EXP-0164 cross_run's own
     rule) so the DSTORE pair is not diluted. (amendment_03)

selftest still green (0 failures). Contract re-frozen, 18 authored blobs.
STATUS: still BLOCKED on the device — EXP-0167 then EXP-0163 are ahead of me.
Credentials received; SSHPASS only, never written to any file.

## 2026-08-30 — M6: resumed after the session-limit kill; two integrity findings BEFORE any dispatch

Re-oriented from disk, not memory: `raw/` held exactly its own `README.md`, so
**zero device dispatches had occurred**. Re-verified the frozen contract and found
two things that had to be fixed before the first dispatch. Both are recorded, not
erased.

**(1) Four `authored_sha256` entries were stale — `amendment_05`.**
`analysis/recitation.py`, `analysis/verdicts.py`, `harness/run.py`,
`harness/selftest.py` did not match the contract. The M5 entry above claims the
contract was re-frozen over 18 blobs after the amendment_03/04 edits; for these four
it was not — the kill landed between editing them and recomputing their hashes. The
four hashes the contract named match **no git object** (they were an in-session
version, never committed), so the named versions are unrecoverable. Verified the
files on disk contain exactly the amendment-authorized changes and nothing else:
recitation.py carries the amendment_04 coverage columns, verdicts.py the amendment_03
N-run per-field pairing. `harness/selftest.py` -> **0 of 66 checks failed**. The three
`.metal` kernels and every other blob hash UNCHANGED. Corrected with the stale/actual
pairs recorded verbatim in the amendment. This is legitimate only because raw/ was
empty: with any capture in hand the correct action would have been a new experiment
number.

**(2) The hardware was about to run against a STALE `db.json` — `amendment_06`.**
`harness/sync.sh frozen` pulled the neo's `tools/agx-isa` and it is **1036 fields /
171 instructions**; my pinned `work/db.snapshot.json` is **1060 / 172**. **65 field
geometries differ, 3 of them on `falu2` — my wave A primary descriptor**:

| | pinned snapshot (83b83a35) | neo's stale copy (f5db942f) |
|---|---|---|
| `falu2.srcA_class` | (40, 1) | absent |
| `falu2.srcB_class` | (41, 2) | absent |
| `falu2.mod_lo` | absent | (40, 3) |

The stale copy predates EXP-0138's split of bits 40..42 into `srcA_class` +
`srcB_class`. `isa_helpers._find_isadb()` searches `work/frozen` FIRST for exactly
this reason, but that directory did not exist on the neo, so it fell through to
`~/agxre/tools/agx-isa`. Consequence had it gone unnoticed: `H4(a)` tests EXP-0138's
model **at `srcB_class==1`**, a field name that does not exist in the stale db;
`raw_schema.field_is_a_db_field_name` would have been violated; and
`verdicts.field_geometry()` would have keyed every falu2 verdict to `mod_lo`, silently
dropping two in-scope fields and inventing one out-of-scope field.

Fixed by installing the **pinned snapshot** (contract authority, not live repo —
the repo's live db.json has already drifted on to 1062 fields under EXP-0165) as
`work/frozen/db.json`, paired with `tools/agx-isa/isadb.py`
(`c97c2a22fe4eb3aaa2140ff716686dcdbbbb099dcd68d2af77f7f9054174dd36`), verified
assemble/disassemble round-trip on falu2 and `imm_encode/imm_decode`, and pushed to
`~/agxre/EXP-0169/work/frozen/`. `isa_helpers.ISA_DIR` on the neo now resolves to it.
**The neo's shared `~/agxre/tools/` was NOT touched** — EXP-0168/0171/0172 are running
against it right now and changing it under them would have been a courtesy violation.

## 2026-08-30 — M7: anchors resolved (twice), and the db drift cost nothing observable

Ran `harness/anchors.py` on G17P **before** and **after** the db fix. The two
`anchor_report.json` / `arm_resolution.json` pairs are **BYTE-IDENTICAL**: the
snapshot-vs-stale difference is a field *partition* over the same bits 40..42, not a
length-rule change, so tokenization and every anchor offset are stable across both db
versions. The stale-db run is retained at `work/anchors_staledb_20260830/` and the
stale pull at `work/frozen_neo_stale_20260830/` as evidence of the near-miss. The
danger was entirely in the *analysis* keying, and it is now closed.

28 authored probe kernels compiled via the public runtime API; `_agc.main` extracted
and tokenized. **9 of 12 lift/nat arms resolved:**

    BF_ALU/bf_alu           k_bfadd      block[32:40] len=8
    FALU2/falu2             k_fadd       block[32:38] len=6
    FALU2I/falu2i           k_faddi      block[18:24] len=6
    FALU2UNI/falu2_uni      k_funichain  block[24:30] len=6
    GET_SR/get_sr           k_sr         block[0:4]   len=4
    HALF_ALU/half_alu       k_hadd       block[32:38] len=6
    HALF_EXT8/half_alu_ext8 k_hfma       block[46:54] len=8
    HALF_FMA12/half_alu_fma12 k_hfma_abs block[46:58] len=12
    IBITCOUNT/ibitcount     k_popcount   block[18:26] len=8

**3 arms UNRESOLVED — reported, not patched around** (`kernels/probes.metal` is
frozen; adding a kernel to chase an anchor is exactly the post-hoc fitting the freeze
exists to prevent):

  * `IUNARY` on C1_alu and C2_load — `iunary` appears in **none** of the 28 compiled
    probes. The 5 integer-unary probes compiled to `cvt_f2i`/`cvt_i2f`/`iadd2`/
    `ibitcount`/`isel10` instead.
  * `ICMP` (nat, `icmp_pred`) — `icmp_pred` appears in none of the 28 either. All four
    comparison probes compiled to `isel10` / `isel8` / `isel10_c` / `isel_reg`.
    OBSERVATION, G17P: for these authored MSL comparison patterns the compiler selects
    the `isel*` family, never `icmp_pred`. Consistent with EXP-0139 having had to
    construct `icmp_pred` rather than find it.

Cost: `iunary` (2 fields) and `icmp_pred.cond` (1 field) have **no arm**, so they will
report `untested / NO-DETECTION-POWER`. 54 of the 57 device-scope fields keep >=1 arm.

**A DB gap, incidentally:** `k_hchain` tokenizes as
`get_sr@0 device_load@4 device_load@18 <unknown>@32` with **52 bytes leftover** — the
half-precision chain emits a 4-byte-group instruction whose length rule `db.json`
cannot resolve, under BOTH db versions. Not blocking (HALF_ALU anchors from `k_hadd`),
recorded as a finding.

STATUS: about to run the pilot (`pilot01`).
