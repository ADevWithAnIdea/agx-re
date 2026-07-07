# Progress Report: August 2021

> Source URL: https://asahilinux.org/2021/08/progress-report-august-2021/

## Overview

The Asahi Linux project delivered a substantial update after several months of development work. The team shifted from lengthy monthly reports to shorter, more frequent updates while maintaining focus on critical infrastructure development.

## Core Kernel Upstreaming

A major milestone was achieved when foundational bring-up work became part of Linux 5.13, released on June 27th. As the report notes, while this "is not very useful for end-users at this early stage," it represented significant effort to solve complex problems in ways acceptable to the upstream kernel community. This accomplishment strengthened relationships with established kernel developers, which the team identified as essential for future collaboration.

## Hardware Reverse Engineering Approach

The project developed an innovative methodology for understanding undocumented M1 hardware. Rather than disassembling proprietary drivers—which posed legal risks—the team constructed a custom hypervisor running macOS unmodified in a virtual machine that transparently logs hardware interactions.

This hypervisor, built on the m1n1 bootloader, operates differently from typical virtualization. It maintains the guest OS in an environment "as close to bare metal as possible" while capturing hardware access patterns. The implementation is notably flexible: portions are written in Python, enabling fast iteration and even live updates during execution.

## DCP Reverse Engineering

Understanding the Display Controller Processor presented substantial challenges. Apple integrated a coprocessor running proprietary firmware that handles most display functions through a remote procedure call interface. The complexity stems from split implementation: parts of the macOS display driver run on the main CPU while others execute on the DCP, with execution stacks extending across the boundary.

The reverse engineering process involved building tracers that decode the message formats and method calls. The team created a Python implementation of the RPC protocol and marshaling system, which serves multiple purposes: parsing hypervisor logs to understand macOS behavior, prototyping a DCP driver, and eventually generating code for the Linux kernel driver.

A significant finding emerged regarding firmware versioning: the DCP interface changes with each macOS release. The project decided to support only specific "golden" firmware versions rather than attempting to maintain compatibility across all releases. The initial kernel implementation will require firmware from macOS 12 "Monterey."

The team noted that while the DCP interface is complicated, the firmware handles substantial work—over 7MB of code implementing DisplayPort link training, memory bandwidth calculations, mode switching, and HDMI conversion. Leveraging this existing functionality rather than reimplementing it at the hardware level proved more efficient.

## Installation Infrastructure

To simplify the setup process, developers created a prototype installer addressing a critical pain point. Previously, users had to install macOS twice and manually replace kernels—a tedious process consuming approximately 70GB of disk space.

The new installer replicates the macOS installation structure by streaming necessary components from official Apple restore images on demand. Users can bootstrap the installation with a simple shell command and follow prompts, selecting from available free space and macOS versions for boot firmware. The installer creates the required APFS container structure, metadata files, paired firmware bundles, recovery environment, and authentication-related components.

## Additional Driver Development

Progress continued across multiple fronts. The DART IOMMU driver, essential for PCIe, USB, DCP, and other hardware support, was accepted upstream for inclusion in Linux 5.15. With this foundation, minimal additional patches were required for USB and PCIe functionality.

The team identified remaining dependencies including GPIO drivers, I²C support for USB Power Delivery, SPI for input devices on laptops, and NVMe patches. The current state already enabled using Asahi Linux as a development machine with a non-accelerated graphical interface, though refinement remained necessary before upstream acceptance.

## Next Steps

The report concludes by indicating that GPU kernel driver development represents the next major focus. This work promised to be "exciting" given the complexity of the graphics hardware and the foundational progress already established.
