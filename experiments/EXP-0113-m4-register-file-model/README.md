# EXP-0113 -- M4 register-file model (H1/H2/H3)

## Question

Three ISA unknowns that block register allocation:

- **H1.** How (if at all) are registers 64-95 addressed as a SOURCE
  operand by an ALU instruction? `get_sr`'s own `dst`/`dst_hi` write path
  reaches them (EXP-0092), but `falu2`/`falu2i`'s packed source-register
  field only aliases to its low 6 bits (EXP-0099/EXP-0105).
- **H2.** Is byte0=0x2b (hex `2b0009c0`, EXP-0087's own "undecoded"
  instance) the real GPR-to-GPR move `reg_move`'s own family was never
  shown to be (EXP-0101)?
- **H3.** What does `reg_move`'s `src_reg` (`src_flag=0`) actually
  address? EXP-0101 found it reads a fixed, per-kernel PRELOADED/
  uniform-file slot, not a live GPR -- this experiment tries to pin down
  the addressing rule for that resource.

Plus two cheap follow-ups: finish EXP-0105's own disclosed `ctrl` bits
4-6 gap (falu2's 7-bit `ctrl` field), and re-examine the EXP-0105 iminmax
splice anomaly with a fresh harness.

## Method

See `PRE_REGISTRATION.md` for the full hypothesis/falsifier table and
`casematrix.py`'s own module docstring for the per-group design
rationale (including the pilot-phase findings -- flush-to-zero on
denormal float ALU inputs, a 16-bit ceiling on `device_store`'s
index-register addressing, and the H1_LOADFWD anomaly -- that shaped this
design). `PROGRESS.md` has the full pilot-phase trail.

Six case groups, 46 cases total, two independent gated hardware runs.

## Commands

```sh
python3 -B baseline.py                       # re-derive carrier lengths (no GPU)
python3 -B verify.py --selftest              # no GPU
python3 -B verify.py --seqtest               # no GPU
python3 -B verify.py --preflight             # no GPU, pre-run01
python3 -B run.py --execute --run-id m4-20260828-run01
python3 -B verify.py --between-runs          # no GPU, pre-run02
python3 -B run.py --execute --run-id m4-20260828-run02
python3 -B verify.py --captured
python3 -B analysis.py --write
```

## Clean-room provenance

```text
Clean-room provenance: OWN-SHADER + HW-PROBE + PUBLIC
Inputs inspected: kernels/*.metal (our own MSL), tools/agx-isa's
  isadb.assemble()/disassemble()/imm_encode()/imm_decode() (read-only),
  tools/agxtest (read-only, splice-and-run), tools/shdump (read-only,
  compile+extract). EXP-0087/0092/0099/0101/0105's own RESULTS.md content
  is cited as prior, already-committed repository evidence (PUBLIC-to-
  this-experiment category), never re-derived from any Apple binary.
  Every instruction byte executed in the gated capture is either our own
  field values passed through our own assembler, or an untouched byte
  range of our own compiled kernel.
Apple binary introspection: NONE.
Reproduction: see Commands above.
Evidence: raw/m4-20260828-run01/, raw/m4-20260828-run02/ (see RESULTS.md
  for the sha256 of the byte-identical 01_results.jsonl).
```
