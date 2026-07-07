# M2 is here! July 2022 Release & Progress Report

> Source URL: https://asahilinux.org/2022/07/july-2022-release/

## Welcome to Another Progress Report

The Asahi Linux project announced a significant update featuring Mac Studio compatibility, Bluetooth support, and experimental M2 machine support. This represented a major milestone for the initiative to bring Linux to Apple Silicon Macs.

## Mac Studio Joins the Family

Apple's Mac Studio announcement prompted the development team to adapt their bootloader and device trees to accommodate the M1 Ultra's multi-die architecture. Most hardware functions worked as expected, though certain USB ports remained unsupported pending additional firmware infrastructure development.

## Bluetooth: A New Challenge Overcome

The implementation of Bluetooth support required reverse engineering Apple's proprietary PCIe interface. One contributor tackled this challenge, creating an initial proof-of-concept driver in userspace. A team member subsequently developed a proper kernel driver, bringing functional Bluetooth support to the platform. However, WiFi and Bluetooth coexistence issues required users to disable 2.4GHz networks temporarily.

The Bluetooth integration demonstrated the project's "seamless upgrade" philosophy:

- Bootloader modifications propagated device tree information
- Installer enhancements extracted and processed firmware
- Device tree bundling with kernel releases ensured synchronization
- Automatic package dependencies enabled effortless user upgrades

Existing users could simply upgrade packages and reboot without manual configuration steps.

## M2 Support: Theory Meets Practice

The M2 represented the first comprehensive test of the hypothesis that newer chip support would require substantially less effort than initial M1 development. Following a twelve-hour intensive development session, Linux successfully booted on M2 hardware with USB, NVMe, battery management, CPU frequency scaling, and WiFi functionality operational.

### Caveats for Early Adopters

M2 support remained highly experimental, requiring expert mode activation in the installer. The keyboard driver had not yet been implemented for bootloader environments. Only the M2 MacBook Pro 13" received comprehensive testing, though the team added untested MacBook Air support.

The firmware implementation relied on a special macOS 12.4 release, which might necessitate future upgrades through macOS itself rather than through seamless Linux package updates.

## Trackpad Engineering: A Deep Dive

Apple's trackpad architecture evolved significantly with the M2 generation. Previous implementations utilized SPI connectivity, with the BCM5976 touchscreen controller and STM32 microcontroller handling input processing and Force Touch functionality.

The M2 introduced a paradigm shift through the MTP (Multitouch Processor), relocating trackpad intelligence directly into the main SoC. While the BCM5976 and STM32 components remained physically present, their firmware responsibilities drastically diminished. The M2's dedicated coprocessor assumed responsibility for comprehensive multitouch algorithm processing.

This architectural change offered several advantages: simplified firmware updates integrated with macOS releases, reduced component costs through smaller STM32 variants, and enhanced flexibility for feature introduction.

Apple implemented communication between MTP and the main OS through DockChannel, Apple's FIFO-based design. While DockChannel itself proved straightforward, the HID transport protocol layered atop it required substantial complexity, resulting in over one thousand lines of kernel driver code. The implementation needed to handle firmware uploads, GPIO proxying, and intricate nested data structures.

The firmware processing pipeline presented additional complications. macOS stored BCM5976 firmware as XML property list files wrapped in ASN.1 IMG4 format. The Asahi installer incorporated a dedicated module converting this to binary format, allowing the Linux kernel to avoid embedding an XML parser while maintaining compatibility.

## macOS Ventura Compatibility Challenges

The macOS 13.0 Ventura beta revealed compatibility issues with existing Asahi Linux installations. Though most firmware maintained OS-specific associations, a small system firmware subset remained shared across operating systems, including NVMe, SMC, and Thunderbolt components.

U-Boot's NVMe driver implementation included an undocumented optimization that proved incompatible with updated firmware. Additionally, the Linux SMC driver contained a single-line bug that went undetected with earlier firmware but caused the new SMC firmware to malfunction.

The team released corrected packages restoring compatibility. These issues stemmed from implementation oversights rather than Apple intentionally breaking compatibility, and the team anticipated decreasing frequency of such problems.

## Display Controller Processor Insights

The Mac Mini and Mac Studio experienced reliability challenges with HDMI output during boot sequences. Since Apple discontinued display initialization at the operating system level beginning with macOS 12.0, Asahi Linux maintained display initialization at the bootloader level using a framebuffer approach.

However, display controller processor hotplug event handling caused complications. Certain monitors exhibited unusual behavior by disconnecting inputs momentarily after waking from standby, triggering DCP shutdown and resulting in blank displays throughout the Linux boot sequence.

After investigating potential DCP commands to disable hotplug reactivity, the team discovered that complete DCP shutdown during bootloader operation resolved the issue. Monitors remained unaffected by DCP inactivity, maintaining signal integrity independent of device status changes. This approach enabled Linux to subsequently reinitialize DCP without complications.

This modification improved compatibility with problematic monitors and enabled seamless monitor power cycling during Linux operation.

## Security Considerations

Recent malware targeting Apple devices exploited DCP vulnerabilities. The Asahi Linux DCP driver development adopted a security-first approach, treating DCP as potentially compromised. The implementation avoided exposing DCP directly to userspace in exploitable configurations, protecting the system despite running identical vulnerable DCP firmware as macOS and iOS.

## DART and IOMMU Progress

The M1 Pro, Max, and Ultra introduced revised DART (IOMMU) hardware variants, utilized for Thunderbolt ports and media codec hardware. Existing M2 systems standardized on this variant throughout, necessitating bootloader and kernel driver support during M2 development.

Community contributions also advanced DART support consolidation upstream, moving Apple-specific page table implementations into dedicated code modules. This refactoring aimed to unblock upstream integration of M1 Pro/Max support into the mainline Linux kernel.

## U-Boot Advancement

U-Boot 2022.07 achieved near-complete M1 system support, including M1 Pro/Max/Ultra variants, alongside preliminary M2 compatibility. PCIe USB3 controller support for Mac Mini Type-A ports remained outstanding.

## Beyond Linux: OpenBSD Compatibility

OpenBSD 7.1 introduced M1 and M1 Pro/Max/Ultra support through reliance on the Asahi installer's m1n1 bootloader infrastructure. This provided standard UEFI boot environments enabling straightforward OpenBSD installation. The OpenBSD installer recognized Apple-specific disk partitions, ensuring macOS installation safety during dual-boot scenarios.

WiFi firmware automatic detection during installation simplified the OpenBSD setup process, with firmware accessible from the EFI system partition pre-staged by the Asahi installer.

OpenBSD support for M2 systems remained pending OpenBSD 7.2's November release.

## GPU Development: A Teaser

The project recently welcomed a GPU driver developer who undertook reverse engineering of M1 GPU hardware interfaces. Early prototype implementations achieved functional graphics processing through remote driver execution via USB connection, successfully rendering complex scenes at high frame rates. The open-source implementation achieved approximately 94% compliance with dEQP-GLES2 testing standards.

The team indicated that comprehensive GPU driver documentation would receive dedicated coverage in subsequent articles.
