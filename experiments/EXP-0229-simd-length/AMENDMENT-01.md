# EXP-0229 Amendment 01 — carrier include path

The first attempted capture, `g17p_e0229_pilot01`, stopped before any GPU
dispatch. `shdump` returned 4 because Metal's source-string compiler resolves
the include from the experiment working directory, whereas `carrier229.metal`
used a path relative to its own `kernels/` directory.

Only the include path changes:

```text
../../EXP-0228-low9-class/kernels/carrier228.metal
->
../EXP-0228-low9-class/kernels/carrier228.metal
```

The generated case matrix, instruction formula, observables, expected results,
and safety bounds are unchanged. The failed pre-dispatch artifact remains on
the Neo and is not evidence about hardware behavior.
