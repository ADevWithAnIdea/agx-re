# EXP-0044 — Unchanged-Asahi-UAPI closure baseline

## Question

What exact userspace responsibilities must the Apple9 documentation satisfy if the
existing Asahi UAPI and its userspace/kernel division of responsibility are preserved?

This is the public-source requirements baseline for the P0/P1 closure campaign. It does
not establish any A18 or M4 hardware value.

## Hypothesis and falsifier

Hypothesis: the UAPI revision audited by `AGX_RE_INFORMATION_GAPS.md` explicitly assigns
helper programs, scratch sideband data, BG/EOT programs, render control-register values,
and command-stream addresses to userspace. Therefore these cannot be dismissed as
kernel-managed without an unchanged-UAPI-compatible mapping.

Falsifier: the pinned UAPI source omits those fields, supplies the values internally, or
assigns them exclusively to the kernel.

## Public input

- Project: Mesa
- Revision: `3c4d3e46d19f2f4e951f3ae059543b03592f7944`
- File: `include/drm-uapi/asahi_drm.h`
- URL:
  `https://gitlab.freedesktop.org/mesa/mesa/-/raw/3c4d3e46d19f2f4e951f3ae059543b03592f7944/include/drm-uapi/asahi_drm.h`
- SPDX: MIT
- SHA-256: `69fe416b7294dfec4794217bd11379effd53caff4e86010bb803f1b34bdf5e89`

## Reproduction

Run:

```sh
./verify.sh
```

The script downloads the single pinned public header into a temporary directory, checks
its SHA-256, and prints only the declarations relevant to the closure matrix. It does not
read or inspect any Apple binary.

## Clean-room provenance

```text
Clean-room provenance: PUBLIC
Inputs inspected: pinned MIT-licensed Mesa UAPI header
Apple binary introspection: NONE
Reproduction: experiments/EXP-0044-uapi-closure-baseline/verify.sh
Evidence: raw/uapi_sha256.txt and RESULTS.md
```

