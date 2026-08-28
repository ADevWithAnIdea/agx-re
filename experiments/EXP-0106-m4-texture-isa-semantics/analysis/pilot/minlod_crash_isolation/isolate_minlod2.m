#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
int main() { @autoreleasepool {
    id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
    NSString *src = @"#include <metal_stdlib>\nusing namespace metal;\n"
        "kernel void k(texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]], constant float& minlod [[buffer(1)]], device float4* out [[buffer(0)]]) {\n"
        "  out[0] = t.sample(s, float2(0.5,0.5), min_lod_clamp(minlod));\n"
        "}\n";
    NSError *e = nil;
    id<MTLLibrary> lib = [dev newLibraryWithSource:src options:nil error:&e];
    NSLog(@"lib_ok=%d err=%@", lib!=nil, e);
    id<MTLFunction> fn = [lib newFunctionWithName:@"k"];
    NSError *pe = nil;
    id<MTLComputePipelineState> pso = [dev newComputePipelineStateWithFunction:fn error:&pe];
    NSLog(@"pso_ok=%d err=%@", pso!=nil, pe);
    return 0;
} }
