# EXP-0229 Amendment 02 — make the carrier self-contained

The second attempted capture, `g17p_e0229_pilot02`, also stopped before GPU
dispatch. The corrected relative include still failed because the prior
experiment's carrier source was not installed on this Neo. `shdump` again
returned 4 at Metal compilation.

`kernels/carrier229.metal` is now a byte-for-byte local copy of the already
authored EXP-0228 carrier instead of a preprocessor include. This changes no
generated instruction, case, observable, oracle, or safety bound. It only
removes an undeclared remote-file dependency. Both failed pre-dispatch
artifacts remain non-hardware evidence.
