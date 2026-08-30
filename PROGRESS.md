- Adopted the three mandated guards: integrity sentinel (buffer 2, three-way
  clean/perturbed/absent), unique splice-archive path per request, and
  fault-never-from-one-observation with periodic baseline re-validation.
- Smoke `smoke02` exposed my first sentinel design as WRONG: it treated a
  length-desync (sentinel present but at the wrong index) as "nothing executed",
  which would have discarded 32% of cases as invalid. Re-designed to three-way.
- Smoke `smoke03` (8,363 cases, cvt_bf16 + pack_convert): 77 faults, **all 77
  reproduced** on the confirm re-run; 4 cases did NOT reproduce and were correctly
  re-scored; 1 InnocentVictim in 8,363; every periodic baseline check passed.
  Two genuine hangs at `pack_convert` byte+3 (src) values 0xc4/0xc9 -> that area
  stopped, as designed.
- Byte 0 sweep bounded to 24 values after a genuine GPU hang from cvt_bf16
  byte0=0xFF; documented as a deliberate safety deviation.
- **PRE_REGISTRATION.md + CAPTURE_CONTRACT.json FROZEN** at repo rev 8904a082,
  22,237 cases, matrix sha256 00529a0a...
- run01 launched.
- run01 PARTIAL (3,137/22,237): our own oracle raised OverflowError on the fp16
  overflow tie 65520.0 (`struct.pack('<e')` refuses instead of producing inf).
  RETAINED unmodified with PARTIAL.md; replaced the fp16 encoder with an exact
  integer RNE implementation (cross-checked against Python over 20k random
  patterns) and added a mandatory oracle pre-flight over EVERY case vector.
- run02 PARTIAL (5,219/22,237): the periodic baseline check failed inside THIS
  sweep's own GPU error-recovery window (5 self-inflicted hangs in the preceding
  300 cases). Stopped by hand per protocol 7.3, RETAINED with PARTIAL.md.
  baseline_check now retries 4x with a settle delay; only an all-attempts failure
  counts as a cascade and it now stops the run outright.
- **run03 COMPLETE**: 22,237/22,237 in 634 s. 7 genuine hangs (global cap 10),
  3 areas stopped: cvt_f2i byte3, cvt_i2f_src byte3, pack_convert byte7.
  Fault confirmations: 134 reproduced, **27 did NOT reproduce** (~17%) -- without
  the protocol 7.1 guard those 27 legal values would have been labelled `fault`.
- run04 (gate pair) launched.
