# Dissecting the Apple M1 GPU, The End

**Source URL:** https://alyssarosenzweig.ca/blog/asahi-gpu-part-n.html  
**Author:** Alyssa Rosenzweig  
**Publication Date:** 26 August 2025  
**Project:** Asahi Linux  

---

## Overview

This final post in the "Dissecting the Apple M1 GPU" series is a retrospective covering the entire arc of the project from December 2020 through 2024, documenting all major milestones achieved and the author's transition away from Apple GPU work.

---

## Project Timeline and Milestones

### December 2020: Project Kickoff
- The Asahi Linux project launched
- Author began reverse-engineering the Apple M1 GPU shader instruction set
- Initial work: poking at shader instruction set, establishing interception infrastructure

### January 2021: Drawing a Triangle
- First triangle rendered using entirely open-source custom code
- Shaders handwritten in M1 GPU machine code
- GPU driven via IOKit kernel interface

### April 2021: Shader Compiler (Milestone 1)
- First week of compiler development: basic vertex and fragment shaders compilable
- Sufficient to render simple 3D scenes
- Integrated into Mesa using NIR

### May 2021: Gallium Driver (OpenGL ES 2.0 basis)
- Gallium3D driver enabled `glxgears` and `glmark2` scenes
- ~75% OpenGL ES 2.0 conformance test pass rate

### December 2022: Kernel Driver Shipped
- Full GPU-accelerated desktop shipped in Asahi Linux
- OpenGL 2.1 and OpenGL ES 2.0 support
- 60fps at 4K for compatible applications

### ~Early 2023: OpenGL 3.1 Conformance
- Achieved within approximately one month of full-time work after kernel driver shipped

### August 2023: OpenGL ES 3.1 Conformance
- First (and only) conformant OpenGL ES 3.1 implementation for M1/M2 hardware
- Passed tens of thousands of Khronos conformance tests
- Submitted to Khronos adopters list

### 2023–2024: Advanced Feature Implementation
- **Geometry shader emulation:** Implemented despite not being supported natively by either ARM or Apple hardware — a novel open-source solution with no prior Mesa implementation to reference
- **Tessellation shader emulation:** Similarly novel; required inventing new approaches
- These emulation layers required significant architectural work

### January 2024: Full Conformance Achieved
- **OpenGL 4.6** conformant
- **OpenGL ES 3.2** conformant
- **Vulkan 1.3** conformant
- **OpenCL 3.0** support

### Same Day as Vulkan 1.4 Specification Release
- **Vulkan 1.4** support shipped the same day the specification was released

### Proton Gaming
- **Proton** (Steam's compatibility layer for Windows games) support enabled
- Windows games running on Linux on Apple Silicon Macs via Steam/Proton

---

## Technical Highlights

### Geometry and Tessellation Shader Emulation

This was described as the most technically challenging portion of the work:

- Neither ARM GPU hardware nor Apple GPU hardware natively supports geometry shaders
- No prior Mesa implementation existed to reference for this approach
- Required novel design and implementation from scratch
- Tessellation similarly required emulation on hardware that doesn't support it natively

The author drew on experience with Intel Xe HPG Architecture documentation when reasoning about geometry pipeline design.

### Standards Conformance Philosophy

The project maintained a strong commitment to formal conformance testing throughout:

- Each milestone targeted Khronos conformance certification
- Tests covered tens of thousands of cases per API
- The open-source driver achieved conformance the manufacturer's own driver never did

---

## Related Projects and Collaborators

- **Asahi Lina** — Kernel driver development
- **Dougall Johnson** — Instruction set reverse-engineering throughout the project
- **Ella Stanforth** — Vulkan driver development
- **Collabora / Panfrost team** — Prior work on Mali GPU drivers that informed methodology
- **LunarG's KosmicKrisp project** — Related work in the ecosystem
- **Valve's Proton/Steam Deck team** — Proton gaming infrastructure

---

## Author's Transition

The author announced transitioning away from Apple GPU work after achieving the initial goals:

1. ✓ Conformant graphics drivers for Apple Silicon
2. ✓ AAA gaming support via Proton

The author cited the University of Toronto as their next focus.

---

## Legacy and Impact

The project demonstrated that:

1. A modern, fully conformant GPU driver could be written entirely through black-box reverse engineering of a proprietary GPU
2. The open-source driver achieved correctness (conformance) that the manufacturer's own driver did not
3. Tile-based deferred rendering architectures (AGX/PowerVR lineage) are fully tractable for open-source driver development
4. The Mesa infrastructure (NIR, Gallium, etc.) is capable of supporting new GPU architectures efficiently

---

## Technical Stack Summary

| Component | Technology |
|-----------|-----------|
| Kernel driver | Custom Linux DRM driver (Asahi Lina) |
| Compiler IR | Mesa NIR |
| Driver framework | Mesa Gallium3D |
| ISA documentation | Dougall Johnson's reverse-engineering |
| Command buffer format | Reverse-engineered via Metal interception |
| Hardware packets | GenXML descriptions |
| Testing | VK-GL-CTS (Khronos conformance test suite) |

---

## References

- Asahi Linux project: https://asahilinux.org
- Mesa repository: https://gitlab.freedesktop.org/asahi/mesa
- Panfrost (Mali GPU drivers) — predecessor work
- Intel Xe HPG Architecture documentation — referenced for geometry pipeline design
