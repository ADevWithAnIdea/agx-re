<!-- Source: https://alyssarosenzweig.ca/blog/vulkan-14-sur-asahi-linux.html -->
# Vulkan 1.4 on Asahi Linux

*By Alyssa Rosenzweig — Published December 2, 2024*

## Key Technical Announcements

**Driver Release**: The Asahi Linux project released the first Vulkan 1.4 conformant driver for Apple hardware, utilizing their "Honeykrisp" graphics driver, achieving Khronos recognition on day one of the specification launch.

**Installation Method**: Users can obtain the latest driver through Fedora Asahi Remix repositories via the command:

```
dnf upgrade --refresh
```

## Standardized Features in Vulkan 1.4

- Timestamps functionality
- Dynamic rendering local read capabilities

## Existing Compatibility Stack

The Asahi Linux graphics support includes:
- OpenGL 4.6 (conformant)
- OpenGL ES 3.2 (conformant)
- OpenCL 3.0 (conformant)

**Distinction**: These represent "the only conformant drivers on Apple hardware for any graphics standard."

## Implementation Notes

- Full Vulkan 1.4 support requires building an experimental Vulkan-Loader version
- New Vulkan 1.4 features are accessible as extensions in the existing Vulkan 1.3 driver, enabling immediate adoption without full loader updates

## Source Context

Published: December 2, 2024 by Rosenzweig on the Asahi Linux blog, with bilingual French/English content discussing industry expectations for standardized GPU acceleration features.
