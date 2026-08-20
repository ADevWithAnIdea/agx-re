# EXP-0071 M4 vertex/fragment ABI contract

Static pre-GPU P0.8 public-Metal scaffold. Run only:

```sh
python3 -B verify.py --preflight
python3 -B analysis.py --static
python3 -B make_manifest.py --check
```

`run.py` refuses device work absent explicit `--execute`; that action is not
authorized by this record. See `PRE_REGISTRATION.md` for the frozen matrix.

Clean-room provenance: OWN-SHADER / PUBLIC API (pre-GPU)
Apple binary introspection: NONE
Evidence: authored contract only
