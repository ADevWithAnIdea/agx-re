# Tales of the M1 GPU

> Source URL: https://asahilinux.org/2022/11/tales-of-the-m1-gpu/

## Introduction

Asahi Lina presents a comprehensive technical overview of developing GPU drivers for Apple's M1 architecture on Linux. The article documents the collaborative reverse-engineering efforts between multiple developers to create functional graphics drivers.

## Understanding GPU Architecture

Modern GPUs share common fundamental components. As explained in the article, these include "shader cores, which process triangles (vertex data) and pixels" along with rasterization units, texture samplers, and rendering output units. Additionally, every GPU requires "a command processor that takes drawing commands from the app and sets up the shader cores to process them."

GPU driver architecture follows a consistent pattern across operating systems: "modern GPU drivers are split into two parts: a user space driver and a kernel driver." The user space component handles shader compilation and API translation, while the kernel portion manages memory protection and work scheduling.

## The M1 GPU's Unique Architecture

The M1 GPU differs fundamentally from typical mobile GPUs. Rather than direct hardware communication, "the GPU has a coprocessor called an ASC that runs Apple firmware and manages the GPU."

This firmware coprocessor handles numerous responsibilities including power management, scheduling, fault recovery, and performance monitoring. The firmware manages extensive data structures: initialization parameters with "almost 1000 fields," submission rings, device control messages, event notifications, statistics, command queues, buffer information, and specialized vertex and fragment rendering commands.

A particularly unusual characteristic involves memory management. The GPU "uses the same page tables" as the firmware, creating a shared kernel address space where "GPU memory is firmware memory."

## Reverse Engineering Approach

Alyssa Rosenzweig began reverse-engineering efforts in 2021, initially working on macOS. She "reverse engineered the macOS GPU driver UAPI enough to allocate memory and submit her own commands to the GPU," allowing development without a Linux kernel driver. Within months, her OpenGL implementation was "passing 75% of the OpenGL ES 2 conformance tests."

When Asahi Lina began kernel driver development in April 2022, she employed innovative prototyping methods. Rather than immediately writing C code, she created a Python-based driver prototype using the m1n1 development framework.

## The Python Prototype Phase

The prototyping strategy proved unconventional. Lina noted: "what if I stuck a Python interpreter inside drm_shim, and called my entire Python driver prototype from it?" This allowed running complete applications through multiple abstraction layers to validate design decisions before committing to kernel code.

## Rust Implementation Decision

Rather than implementing the final driver in C, the team chose Rust—an emerging language gaining official Linux kernel support. This decision addressed multiple concerns: managing complex object lifetimes, preventing memory safety bugs, and handling multi-version firmware compatibility through macro-based metaprogramming.

On August 18, 2022, Lina began the Rust implementation. She wrote approximately 1500 lines of DRM subsystem abstractions before implementing the driver proper. By September 24, she successfully rendered test geometry, and "just a few days later, I could run a full GNOME desktop session."

## Safety and Stability Benefits

The Rust implementation demonstrated unexpected stability. Rather than typical new driver problems—"race conditions, memory leaks, use-after-free issues"—the code required minimal debugging. Lina observed that "Rust is truly magical! Its safety features mean that the design of the driver is guaranteed to be thread-safe and memory-safe."

This stability stemmed from Rust's design philosophy: "error and cleanup handling! All the error-prone goto cleanup style error handling to clean up resources in C just… vanishes with Rust."

## Current Capabilities

The collaborative effort now supports multiple M-series processors and achieves substantial compatibility. Alyssa's Mesa driver achieved "OpenGL ES 2.0 conformance practically complete and 3.0 conformance at over 96%." Real-world testing showed impressive performance: "tested Xonotic at 1080p inside a GNOME session, and the estimated battery runtime was over 8 hours."

## Future Development

The driver remains under development with several objectives ahead. The user-facing API requires refinement before upstream Linux integration. Vulkan support is in progress through contributor Ella. Some advanced features like tessellation and geometry shaders require significant emulation work.

The team anticipates making the driver "an opt-in testing build before the end of the year," though current builds require custom kernel, bootloader, and Mesa compilation.
