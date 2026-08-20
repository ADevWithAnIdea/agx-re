# EXP-0070 M4 typed-format conversion contract

Static-only P1.2 experiment bundle. It provides an authored public-Metal MSL
matrix, an owned-buffer in-bounds harness, opt-in runner, deterministic analyzer,
manifest generator, and fail-closed verifier. It has **no GPU capture**, therefore
no observed hardware claim.

Run only static checks now:

```sh
python3 -B verify.py --preflight
python3 -B analysis.py --static
python3 -B make_manifest.py --check
```

The runner refuses to perform a build or device operation unless given
`--execute`; its use is intentionally deferred. See `PRE_REGISTRATION.md` and
`CAPTURE_CONTRACT.json` for the precise capture and stop contract.

Clean-room provenance: OWN-SHADER / PUBLIC API (pre-GPU tooling only)
Inputs inspected: authored text sources and static JSON only
Apple binary introspection: NONE
Reproduction: commands above
Evidence: no raw observations; manifest covers authored bundle only
