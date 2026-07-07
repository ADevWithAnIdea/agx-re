# Metal Overview - Apple Developer

Source: https://developer.apple.com/metal/
Fetched: 2026-05-09

## Main Description

**Metal** is a modern, tightly integrated graphics and compute API coupled with a powerful shading language designed to take full advantage of Apple silicon. The low-overhead model provides:

- Direct control over GPU tasks
- Maximized efficiency of graphics and compute software
- Incredible visual experiences
- Tight ML integration with scalable performance across Apple platforms
- Comprehensive GPU profiling and debugging tools

### Documentation
- https://developer.apple.com/documentation/metal

---

## Metal 4 (Latest, 2025)

The latest version of Metal is built to scale to modern app needs.

**Key Features:**
- Entirely new ways to integrate machine learning
- More efficient command encoding
- More efficient shader compilation

**Resources:**
- Discover Metal 4 (WWDC 2025): https://developer.apple.com/videos/play/wwdc2025/205/

---

## Hardware Requirements

Metal 4 is supported on:
- **iPhone, iPad, and Apple TV:** A14 Bionic or later
- **Mac:** Apple silicon (M1 or later)
- **Vision Pro**

---

## Games and Graphics

### MetalFX for Game Performance

MetalFX provides tools to maximize performance:
- **MetalFX Upscaling** - Save rendering time
- **Frame Interpolation** - Improve frame rates
- **Denoising** - Optimize quality

Documentation: https://developer.apple.com/documentation/metalfx

### Game Porting Toolkit

Complete toolkit for bringing games to Apple platforms:
- Game evaluation tools
- Shader conversion
- Asset conversion
- Human Interface Guidelines
- Code samples

---

## Machine Learning

### ML-Powered Graphics

Combine traditional graphics with ML inference:
- Encode inference networks at command level
- Integrate directly into shaders
- Compute lighting, materials, and geometry
- Enable highly realistic visuals

### Metal Performance Shaders

#### Metal Performance Shaders Framework
Highly optimized compute and graphics shaders
- Documentation: https://developer.apple.com/documentation/metalperformanceshaders

#### Metal Performance Shaders Graph Framework
Integrate Core ML models directly
- Documentation: https://developer.apple.com/documentation/metalperformanceshadersgraph

### Machine Learning Framework Support

Accelerate ML model training in third-party frameworks on Mac:
- **PyTorch Metal Backend**: https://developer.apple.com/metal/pytorch/
- **JAX Metal Backend**: https://developer.apple.com/metal/jax/

---

## Metal Developer Tools

### Inspection and Debugging

**Metal Debugger:**
- Inspect entire rendering pipeline
- Debug from mesh shading to ray tracing to machine learning
- Monitor performance in real time with Metal performance HUD

### Validation

**Validation Layers:**
- Metal API validation
- Shader validation

### Performance Analysis

**Metal System Trace in Instruments:**
- Inspect parallel work on CPU and GPU
- Monitor memory usage

Tools overview: https://developer.apple.com/metal/tools/

---

## Key Links

| Category | Links |
|----------|-------|
| Documentation | https://developer.apple.com/documentation/metal |
| MetalFX | https://developer.apple.com/documentation/metalfx |
| Metal Performance Shaders | https://developer.apple.com/documentation/metalperformanceshaders |
| MPS Graph | https://developer.apple.com/documentation/metalperformanceshadersgraph |
| PyTorch Metal | https://developer.apple.com/metal/pytorch/ |
| JAX Metal | https://developer.apple.com/metal/jax/ |
| Tools | https://developer.apple.com/metal/tools/ |
| WWDC 2025 Metal 4 | https://developer.apple.com/videos/play/wwdc2025/205/ |
| Sample Code | https://developer.apple.com/metal/sample-code/ |
| Resources | https://developer.apple.com/metal/resources/ |

---

## Featured Developer Notes (from Apple)

- Assassin's Creed Shadows by Ubisoft uses Metal on Mac
- Resident Evil: Village port to Mac
- Lies of P by ROUND8 Studio
