# EXP-0059 — FALU2I semantic property vectors

The frozen question, domain, exclusions, and clean-room boundary are in
`PRE_REGISTRATION.md`. After the preregistration commit, reproduce once with:

```sh
python3 -B analysis/audit_falu2i.py
```

The output is append-only and structural only. It does not inspect Apple code
or invoke a hardware/compiler-output probe.
