// EXP-O2C capability probe (runs ON DEVICE). Reports the A18 Pro RT/tensor
// feature flags relevant to this experiment. CLEAN-ROOM: we only query the
// PUBLIC MTLDevice capability API on our own process; no Apple binary inspected.
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
int main(void){ @autoreleasepool{
    id<MTLDevice> d = MTLCreateSystemDefaultDevice();
    printf("device = %s\n", d.name.UTF8String);
    printf("supportsRaytracing            = %d\n", (int)[d supportsRaytracing]);
    if ([d respondsToSelector:@selector(supportsRaytracingFromRender)])
        printf("supportsRaytracingFromRender  = %d\n", (int)[d supportsRaytracingFromRender]);
    else printf("supportsRaytracingFromRender  = (selector absent)\n");
    if ([d respondsToSelector:@selector(supportsPrimitiveMotionBlur)])
        printf("supportsPrimitiveMotionBlur   = %d\n", (int)[d supportsPrimitiveMotionBlur]);
    else printf("supportsPrimitiveMotionBlur   = (selector absent)\n");
    if ([d respondsToSelector:@selector(supportsFunctionPointers)])
        printf("supportsFunctionPointers      = %d\n", (int)[d supportsFunctionPointers]);
    if ([d respondsToSelector:@selector(supportsFunctionPointersFromRender)])
        printf("supportsFunctionPointersFromRender = %d\n", (int)[d supportsFunctionPointersFromRender]);
    // feature-set family checks
    printf("Apple9 = %d\n", (int)[d supportsFamily:MTLGPUFamilyApple9]);
    return 0;
}}
