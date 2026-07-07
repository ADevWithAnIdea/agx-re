# X.Org Developer Conference (XDC) Talks on Apple GPU

Collection of XDC conference talks covering Apple GPU reverse engineering and Asahi Linux GPU driver development.

---

## XDC 2021: "The Occult and the Apple GPU"

**Speaker:** Alyssa Rosenzweig (Collabora)  
**Date:** September 15, 2021  
**Duration:** 45 minutes  
**Format:** Virtual (Main Track)  
**Indico:** https://indico.freedesktop.org/event/1/contributions/10/  
**YouTube:** https://www.youtube.com/watch?v=ObS6sdfus2w  
**Slides:** Available as Slides-Final.pdf at the Indico page  
**Phoronix coverage:** https://www.phoronix.com/news/Apple-AGX-XDC2021

### Abstract
The presentation explores Apple's M1 GPU architecture through reverse-engineering. Rosenzweig questions whether the chip's performance reputation is justified or merely perceived marketing, using investigative techniques to "spill the chip's secrets, solve mysteries we were never supposed to know about, and gain a Mesa driver."

### Topics Covered
- M1 system-on-chip architecture analysis
- GPU performance comparison with industry standards
- Reverse-engineering methodology
- Mesa driver development for Apple GPU
- Early ISA discoveries

### Context
This was the **first major public technical talk** on the Apple M1 GPU reverse engineering effort, presented just months after the M1 was released (November 2020). At this point, Dougall Johnson had already documented the shader ISA, and Rosenzweig was working on the command stream and Mesa driver.

---

## XDC 2022: "Tasting the Forbidden Apple"

**Speakers:** Alyssa Rosenzweig (Collabora) and Asahi Lina  
**Date:** October 4, 2022, 2:00 PM  
**Duration:** 45 minutes  
**Location:** Opus Hall (201), Minneapolis  
**Format:** In-person  
**Indico:** https://indico.freedesktop.org/event/2/contributions/66/  
**YouTube:** https://www.youtube.com/watch?v=SDJCzJ1ETsM

### Abstract
Presenters describe the Apple GPU hardware as containing "dark magic," with "magic ring buffers" embedded in the firmware. Goal: freeing the GPU "from its Metal chains" to enable broader Linux support. Documents their technical journey using "reverse-engineering tricks" to enable GPU functionality in Asahi Linux.

### Topics Covered
- Apple GPU firmware architecture and ASC coprocessor
- Ring buffer communication protocol
- Reverse-engineering methodologies for proprietary hardware
- Driver development for unconventional GPU designs
- Asahi Linux GPU support implementation status

### Context
Delivered around the time they were close to releasing initial GPU support in Asahi Linux (shipped December 2022). The entire talk was reportedly **run on an M1 using their own drivers** - a live demonstration of working M1 GPU support.

---

## XDC 2023: "Unleash the (Graphics) Magic"

**Speakers:** Asahi Lina and Alyssa Rosenzweig  
**Date:** October 17, 2023, 12:15  
**Format:** In-person  
**Indico:** https://indico.freedesktop.org/event/4/  
**YouTube:** https://www.youtube.com/watch?v=O36VFNdQHsE

### Abstract
> "Twelve moons ago, we demoed early OpenGL 2.1 and OpenGL ES 2.0 drivers running on Linux on the Apple M1. [We have since] shipped OpenGL 3.1 and passed the OpenGL ES 3.1 conformance tests on the M1 and M2 families, reveal[ing] the hardware incantations that make the magic happen... involving some _truly_ cursed driver code."

### Topics Covered
- Progress from OpenGL 2.1 → OpenGL 3.1/ES 3.1
- Apple M1 and M2 GPU hardware details enabling this work
- Cursed/unusual driver implementation requirements
- Conformance testing methodology and results

---

## XDC 2024: "AAA!! She's a Witch!"

**Speaker:** Alyssa Rosenzweig (Valve contractor)  
**Date:** October 10, 2024, 9:15 AM  
**Duration:** 45 minutes  
**Location:** Room 9AB  
**Format:** In-person with live demo  
**Indico:** https://indico.freedesktop.org/event/6/contributions/284/  
**YouTube:** https://www.youtube.com/watch?v=TtLP5sAXYKo  
**Slides:** slides.pdf (available on Indico page)

### Abstract
Building on previous OpenGL ES 3.1 work, announces "conformant Vulkan 1.3 on the M1 supporting the most cursed features... Geometry shaders, tessellation, transform feedback, and more."

### Technical Topics Covered

**Vulkan 1.3 implementation:**
- Geometry shaders (emulated via compute - no hardware support)
- Tessellation (emulated via compute - hardware too limited)
- Transform feedback
- Out-of-bounds robustness: "reserve 64 gigabytes of zeroes using virtual memory" for efficient address substitution

**Hardware tessellator limitations:**
- Apple's hardware tessellator missing features required by DirectX, Vulkan, OpenGL
- Missing: point mode, isoline support
- Software tessellator using Microsoft reference tessellator (converted to OpenCL C)
  - Software-only: <1 fps
  - OpenCL-based: 265 fps
  - Hardware (where possible): 820 fps

**AAA Gaming Stack:**
- FEX: x86 emulation on ARM64
- Wine: Windows → Linux translation
- DXVK/vkd3d-proton: DirectX → Vulkan translation
- muvm: lightweight VM for 4KB page size compatibility (Apple uses 16KB pages)

**Games demonstrated:** Portal, Portal 2, The Witcher 3, Fallout 4, Control, Ghostrunner, Cyberpunk 2077

### LWN Coverage
https://lwn.net/Articles/995383/

---

## Full XDC 2023 Conference GPU Talk List

For context, all GPU-related talks at XDC 2023:
1. Apple M1/M2 OpenGL drivers (Lina Asahi, Alyssa Rosenzweig) - see above
2. AMD display driver & color management (Melissa Wen)
3. HDR + Color Management in Gamescope/SteamOS (Joshua Ashton)
4. Nouveau/NVK driver updates (Faith Ekstrand)
5. Rust compiler development for graphics (Faith Ekstrand)
6. RADV raytracing improvements (Friedrich Vock)
7. GPU resets in Linux (André Almeida)
8. Rusticl OpenCL implementation status (Karol Herbst)
