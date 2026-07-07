# Progress Report: September 2021

> Source URL: https://asahilinux.org/2021/10/progress-report-september-2021/

## Linux drivers galore

The Asahi Linux project achieved significant momentum in kernel development during September 2021. Multiple essential drivers were either merged or entered review for Linux 5.16, demonstrating progress toward a usable desktop environment without GPU acceleration.

**PCIe Infrastructure**: Mark Kettenis contributed Device Tree bindings for PCI Express hardware, enabling multiple open-source operating systems to share bootloader compatibility. Marc Zyngier's PCIe driver (`pcie-apple`) manages physical port configuration, MSI interrupt mapping to the AIC controller, and IOMMU group assignment, enabling USB-A and Ethernet functionality on Mac Mini systems.

**USB-C Power Delivery**: Sven Peter adapted the existing TPS6598X driver to support Apple's CD3217/CD3218 variants in M1 machines. The implementation required handling special USB-C controller handshakes and eUSB2 repeater configuration for proper charging and hotplugging support.

**GPIO/Pinctrl Interface**: Joey Gouly developed the `apple-gpio-pinctrl` driver after collaborative hardware analysis using test equipment. This driver manages general-purpose I/O pins essential for peripheral reset control and PCIe functionality.

**I²C Communications**: Sven submitted patches to the existing `i2c-pasemi` driver to support platform device configurations. Notably, this hardware traces back to the PA Semi PWRficient architecture, demonstrating Apple's hardware reuse across generations.

**ASC Mailbox Layer**: The `apple-mailbox` driver handles fundamental 96-bit message communication between the main CPU and auxiliary coprocessors running Apple's RTKit embedded operating system.

**IOMMU Page Size Handling**: Sven developed patches allowing Linux's IOMMU layer to function with hardware supporting larger page sizes than the kernel. This breakthrough enables viable 4K kernel configurations despite the DART IOMMU being designed for 16K pages.

**Device Power Management**: The `apple-pmgr-pwrstate` driver represents hardware as Linux Generic Power Domains, providing automatic power state transitions and hardware reset capabilities integrated with the device framework.

**CPU Frequency Scaling**: Two drivers manage cluster performance states and memory controller configuration. The implementation leverages `cpufreq-dt` while providing hardware-specific latency metrics for optimal scheduling decisions.

**NVMe Storage**: The `apple-ans-nvme` and `apple-sart` drivers handle M1's non-standard NVMe implementation, including ASC management and companion IOMMU functionality. Development requires core NVMe subsystem modifications.

**Display Controller**: Alyssa Rosenzweig implemented the `apple-dcp` driver supporting resolution switching, 4K HDMI output, and tear-free page flipping through RTKit and mailbox integration.

## Unique Hardware Approach

Apple emphasizes interface compatibility across SoC generations, allowing drivers designed for the M1 to potentially work unchanged on future processors. This contrasts with typical embedded systems requiring extensive hardware-specific modifications.

The implementation philosophy prioritizes Device Tree representation of hardware parameters rather than hard-coded layouts. Power management, GPIO, and frequency drivers instantiate per-device with dynamic dependency relationships, enabling forward compatibility with architectural variations.

Upstream maintainers unfamiliar with this approach may require education on its advantages. This methodology could inspire industry-wide shifts toward forward-compatible SoC design practices previously unavailable in ARM64 systems.

## Desktop Viability

M1 Macs achieved functional desktop capability despite lacking GPU acceleration. The CPU architecture proves sufficiently powerful for software-rendered interfaces to exceed performance on ARM64 boards with hardware acceleration.

Rough edges persist—USB3, Thunderbolt, cameras, audio, and GPU support remain incomplete. WiFi drivers require substantial rewrites. Nevertheless, developers like Alyssa daily-drive custom kernel builds, validating the self-hosted development capability.

## Installer Development

The alpha installer now supports older macOS versions, variable recovery configurations, and multiple macOS installations within APFS containers. An official release installer will guide users through macOS resizing, m1n1 and U-Boot installation, EFI configuration, and optional Arch Linux ARM distribution deployment.

Mark Kettenis recently submitted upstream U-Boot M1 support patches, advancing bootloader compatibility.

## Reverse Engineering Progress

**Hypervisor SMP**: The m1n1 hypervisor now exposes all eight CPU cores with virtualized startup hardware, enabling faster boot times and practical testing without serial cables. The virtual UART and debugging features significantly improve developer accessibility.

**Audio Hardware**: Martin Povišer reverse-engineered M1 audio subsystems, developing m1n1 proof-of-concept drivers for DMA and amplifier hardware. Linux ASoC driver development commenced. Additional `apple-clocksel` driver support appears necessary based on macOS audio driver behavior.

**USB3/DisplayPort/Thunderbolt**: Collaborative investigation identified multiple interacting driver requirements for SuperSpeed hardware. Novel kernel-level implementations without precedent on other SoCs were anticipated.

## Future Direction

GPU kernel interface development represents the next major milestone, pending completion of outstanding kernel submissions. Alyssa's substantial Mesa userspace work, functional under macOS, requires porting to the Linux kernel driver interface.
