# Independent audit note

`graphics_binding` performed a read-only audit after the first capture. It inspected
only this experiment's authored MSL/runner, exact bytes compiled from that MSL, and raw
GPU results. It did not inspect Apple binary or auxiliary-program code and made no edits.

The audit verified two-run equality, `STATUS OK`, forced archive execution, and every
recorded own-main length/hash. It rejected native-instruction wording because no
independent assembly, splice, or opcode-isolation test exists. It also found that the
first min/max matrix lacked ordinary unequal finite operands, requested raw-bit identity
controls, identified missing capture-time/source/tool/revision metadata, and noted that
the README counted seven kernels while the source contained eight.

Those findings caused the append-only v2 and v3 controls, the self-binding v3 metadata,
the ten-kernel count correction, the source-path evidence label, and the explicit
P0.6/P1.8 limitations in `RESULTS.md`. The original captures were retained.

```text
Audit scope: authored EXP-0047 source, OWN-SHADER bytes, raw HW outputs
Apple binary introspection: NONE
Apple auxiliary/helper/program bytes inspected: NONE
Disposition: corrections incorporated; canonical evidence is raw/m4-two-run-v3.json
```
