# Dissecting the Apple M1 GPU, part I

> Source URL: https://rosenzweig.io/blog/asahi-gpu-part-1.html
> Redirect: https://alyssarosenzweig.ca/blog/asahi-gpu-part-1.html

**7 Jan 2021**

Apple's latest line of Macs includes their in-house "M1" system-on-chip, featuring a custom GPU. This poses a problem for those of us in the [Asahi Linux](https://asahilinux.org) project who wish to run Linux on our devices, as this custom Apple GPU has neither public documentation nor open source drivers. Some speculate it might descend from PowerVR GPUs, as used in older iPhones, while others believe the GPU to be completely custom. But rumours and speculations are no fun when we can peek under the hood ourselves!

A few weeks ago, I purchased a Mac Mini with an M1 GPU as a development target to study the instruction set and command stream, to understand the GPU's architecture at a level not previously publicly understood, and ultimately to accelerate the development of a Mesa driver for the hardware. Today I've reached my first milestone: "I now understand enough of the instruction set to disassemble simple shaders with a free and open-source tool chain, released on GitHub."

The process for decoding the instruction set and command stream of the GPU parallels the same process used for reverse-engineering Mali GPUs in the Panfrost project, originally pioneered by the Lima, Freedreno, and Nouveau free software driver projects. Typically, for Linux or Android driver reverse-engineering, a small wrap library will be written to inject into a test application via `LD_PRELOAD` that hooks key system calls like `ioctl` and `mmap` in order to analyze user-kernel interactions. Once the "submit command buffer" call is issued, the library can dump all (mapped) shared memory for offline analysis.

The same overall process will work for the M1, but there are some macOSisms that need to be translated. First, there is no `LD_PRELOAD` on macOS; the equivalent is `DYLD_INSERT_LIBRARIES`, which has some extra security features which are easy enough to turn off for our purposes. Second, while the standard Linux/BSD system calls do exist on macOS, they are not used for graphics drivers. Instead, Apple's own `IOKit` framework is used for both kernel and userspace drivers, with the critical entry point of `IOConnectCallMethod`, an analogue of `ioctl`. These differences are easy enough to paper over, but they do add a layer of distance from the standard Linux tooling.

The bigger issue is orienting ourselves in the IOKit world. Since Linux is under a copyleft license, (legal) kernel drivers are open source, so the `ioctl` interface is public, albeit vendor-specific. macOS's kernel (XNU) being under a permissive license brings no such obligations; the kernel interface is proprietary and undocumented. Even after wrapping `IOConnectCallMethod`, it took some elbow grease to identify the three critical calls: memory allocation, command buffer creation, and command buffer submission. Wrapping the allocation and creation calls is essential for tracking GPU-visible memory (what we are interested in studying), and wrapping the submission call is essential for timing the memory dump.

With those obstacles cleared, we can finally get to the shader binaries, black boxes in themselves. However, the process from here on out is standard: start with the simplest fragment or compute shader possible, make a small change in the input source code, and compare the output binaries. Iterating on this process is tedious but will quickly reveal key structures, including opcode numbers.

The findings of the process documented in the free software disassembler confirm a number of traits of the GPU:

**One**, the architecture is scalar. Unlike some GPUs that are scalar for 32-bits but vectorized for 16-bits, "the M1's GPU is scalar at all bit sizes." Yet Metal optimization resources imply 16-bit arithmetic should be significantly faster, in addition to a reduction of register usage leading to higher thread count (occupancy). This suggests the hardware is superscalar, with more 16-bit ALUs than 32-bit ALUs, allowing the part to benefit from low-precision graphics shaders much more than competing chips can, while removing a great deal of complexity from the compiler.

**Two**, the architecture seems to handle scheduling in hardware, common among desktop GPUs but less so in the embedded space. This again makes the compiler simpler at the expense of more hardware. Instructions seem to have minimal encoding overhead, unlike other architectures which need to pad out instructions with _nop_'s to accommodate highly constrained instruction sets.

**Three**, various modifiers are supported. Floating-point ALUs can do clamps (saturate), negates, and absolute value modifiers "for free", a common shader architecture trait. Further, "most (all?) instructions can type-convert between 16-bit and 32-bit 'for free' on both the destination and the sources," which allows the compiler to be much more aggressive about using 16-bit operations without risking conversion overheads. On the integer side, various bitwise complements and shifts are allowed on certain instructions for free. None of this is unique to Apple's design, but it's worth noting all the same.

**Finally**, not all ALU instructions have the same timing. Instructions like `imad`, used to multiply two integers and add a third, are avoided in favour of repeated `iadd` integer addition instructions where possible. This also suggests a superscalar architecture; software-scheduled designs like those used in similar work cannot exploit differences in pipeline length, inadvertently slowing down simple instructions to match the speed of complex ones.

From prior experience working with GPUs, one might expect to find some unusual complexity waiting in the instruction set, to balloon compiler complexity. Though the above work currently covers only a small surface area of the instruction set, so far everything seems sound. There are no convoluted optimization tricks, but doing away with the trickery creates a streamlined, efficient design that does one thing and does it well. Maybe Apple's hardware engineers discovered "it's hard to beat simplicity."

Alas, a shader tool chain isn't much use without an open source userspace driver. Next up: dissecting the command stream!

_Disclaimer: This work is a hobby project conducted based on public information. Opinions expressed may not reflect those of my employer._
