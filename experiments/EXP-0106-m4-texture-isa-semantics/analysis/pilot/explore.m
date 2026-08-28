// NON-RECORDED pre-freeze exploration harness for EXP-0106. NOT part of the
// frozen contract; used only to determine which failure MODE (NSException,
// hard process abort/SIGABRT, or a clean nil-returning API rejection) each
// boundary case actually produces on M4, so CAPTURE_CONTRACT.json can encode
// the correct expect_status before any raw/ capture begins. Public Metal API
// only. One test per process invocation (isolates a possible hard abort).
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>

static void pr(NSString *s) { fprintf(stderr, "%s\n", s.UTF8String); fflush(stderr); }

int main(int argc, const char **argv) { @autoreleasepool {
    if (argc < 2) { pr(@"usage: explore --test NAME"); return 2; }
    NSString *test = @(argv[2] ? argv[2] : argv[1]);
    id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
    if (!dev) { pr(@"NO_DEVICE"); return 3; }
    pr([NSString stringWithFormat:@"device=%@", dev.name]);

    if ([test isEqualToString:@"dim2d_16384"] || [test isEqualToString:@"dim2d_16385"]) {
        NSUInteger w = [test hasSuffix:@"16385"] ? 16385 : 16384;
        MTLTextureDescriptor *d = [MTLTextureDescriptor new];
        d.textureType = MTLTextureType2D; d.pixelFormat = MTLPixelFormatR8Uint;
        d.width = w; d.height = 1; d.usage = MTLTextureUsageShaderRead; d.storageMode = MTLStorageModeShared;
        @try {
            id<MTLTexture> t = [dev newTextureWithDescriptor:d];
            pr([NSString stringWithFormat:@"RESULT width=%lu texture=%@", (unsigned long)w, t]);
        } @catch (NSException *ex) {
            pr([NSString stringWithFormat:@"EXCEPTION width=%lu %@: %@", (unsigned long)w, ex.name, ex.reason]);
        }
        return 0;
    }
    if ([test isEqualToString:@"dim3d_2048"] || [test isEqualToString:@"dim3d_2049"]) {
        NSUInteger d3 = [test hasSuffix:@"2049"] ? 2049 : 2048;
        MTLTextureDescriptor *d = [MTLTextureDescriptor new];
        d.textureType = MTLTextureType3D; d.pixelFormat = MTLPixelFormatR8Uint;
        d.width = 4; d.height = 4; d.depth = d3; d.usage = MTLTextureUsageShaderRead; d.storageMode = MTLStorageModeShared;
        @try {
            id<MTLTexture> t = [dev newTextureWithDescriptor:d];
            pr([NSString stringWithFormat:@"RESULT depth=%lu texture=%@", (unsigned long)d3, t]);
        } @catch (NSException *ex) {
            pr([NSString stringWithFormat:@"EXCEPTION depth=%lu %@: %@", (unsigned long)d3, ex.name, ex.reason]);
        }
        return 0;
    }
    if ([test isEqualToString:@"arraylen_2048"] || [test isEqualToString:@"arraylen_2049"]) {
        NSUInteger al = [test hasSuffix:@"2049"] ? 2049 : 2048;
        MTLTextureDescriptor *d = [MTLTextureDescriptor new];
        d.textureType = MTLTextureType2DArray; d.pixelFormat = MTLPixelFormatR8Uint;
        d.width = 4; d.height = 4; d.arrayLength = al; d.usage = MTLTextureUsageShaderRead; d.storageMode = MTLStorageModeShared;
        @try {
            id<MTLTexture> t = [dev newTextureWithDescriptor:d];
            pr([NSString stringWithFormat:@"RESULT arrayLength=%lu texture=%@", (unsigned long)al, t]);
        } @catch (NSException *ex) {
            pr([NSString stringWithFormat:@"EXCEPTION arrayLength=%lu %@: %@", (unsigned long)al, ex.name, ex.reason]);
        }
        return 0;
    }
    if ([test isEqualToString:@"msaa8"]) {
        BOOL supports = [dev supportsTextureSampleCount:8];
        pr([NSString stringWithFormat:@"supportsTextureSampleCount(8)=%d", supports]);
        MTLTextureDescriptor *d = [MTLTextureDescriptor new];
        d.textureType = MTLTextureType2DMultisample; d.pixelFormat = MTLPixelFormatR32Uint;
        d.width = 4; d.height = 4; d.sampleCount = 8; d.usage = MTLTextureUsageShaderRead; d.storageMode = MTLStorageModeShared;
        @try {
            id<MTLTexture> t = [dev newTextureWithDescriptor:d];
            pr([NSString stringWithFormat:@"RESULT sampleCount=8 texture=%@", t]);
        } @catch (NSException *ex) {
            pr([NSString stringWithFormat:@"EXCEPTION sampleCount=8 %@: %@", ex.name, ex.reason]);
        }
        return 0;
    }
    if ([test isEqualToString:@"mip15"]) {
        MTLTextureDescriptor *d = [MTLTextureDescriptor new];
        d.textureType = MTLTextureType2D; d.pixelFormat = MTLPixelFormatR8Uint;
        d.width = 16384; d.height = 1; d.mipmapLevelCount = 15;
        d.usage = MTLTextureUsageShaderRead; d.storageMode = MTLStorageModeShared;
        @try {
            id<MTLTexture> t = [dev newTextureWithDescriptor:d];
            pr([NSString stringWithFormat:@"RESULT mip15 texture=%@ numLevels(query-by-construction only)", t]);
        } @catch (NSException *ex) {
            pr([NSString stringWithFormat:@"EXCEPTION mip15 %@: %@", ex.name, ex.reason]);
        }
        return 0;
    }
    if ([test isEqualToString:@"minlod_gather_compile"]) {
        NSString *src = @"#include <metal_stdlib>\nusing namespace metal;\n"
            "kernel void k(texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]], device float4 *o [[buffer(0)]]) {\n"
            "  o[0] = t.gather(s, float2(0.5,0.5), int2(0), component::x, min_lod_clamp(1.0));\n"
            "}\n";
        NSError *e = nil;
        id<MTLLibrary> lib = [dev newLibraryWithSource:src options:nil error:&e];
        pr([NSString stringWithFormat:@"lib=%@ error=%@", lib, e]);
        return 0;
    }
    if ([test isEqualToString:@"dynamic_offset_compile"]) {
        NSString *src = @"#include <metal_stdlib>\nusing namespace metal;\n"
            "kernel void k(texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]], device int2 *off [[buffer(0)]],"
            " device float4 *o [[buffer(1)]], uint tid [[thread_position_in_grid]]) {\n"
            "  o[tid] = t.sample(s, float2(0.5,0.5), off[tid]);\n"
            "}\n";
        NSError *e = nil;
        id<MTLLibrary> lib = [dev newLibraryWithSource:src options:nil error:&e];
        pr([NSString stringWithFormat:@"lib=%@ error=%@", lib, e]);
        return 0;
    }
    if ([test isEqualToString:@"sampler17_compile"]) {
        NSMutableString *src = [NSMutableString stringWithString:@"#include <metal_stdlib>\nusing namespace metal;\n"
            "kernel void k(texture2d<float> t [[texture(0)]], device float4 *o [[buffer(0)]]"];
        for (int i = 0; i < 17; i++) [src appendFormat:@", sampler s%d [[sampler(%d)]]", i, i];
        [src appendString:@") {\n  float4 acc = float4(0);\n"];
        for (int i = 0; i < 17; i++) [src appendFormat:@"  acc += t.sample(s%d, float2(0.5,0.5));\n", i];
        [src appendString:@"  o[0] = acc;\n}\n"];
        NSError *e = nil;
        id<MTLLibrary> lib = [dev newLibraryWithSource:src options:nil error:&e];
        pr([NSString stringWithFormat:@"lib=%@ error=%@", lib, e]);
        return 0;
    }

    if ([test isEqualToString:@"minlod_alone_compile"]) {
        NSString *src = @"#include <metal_stdlib>\nusing namespace metal;\n"
            "kernel void k(texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]], device float4 *o [[buffer(0)]]) {\n"
            "  o[0] = t.sample(s, float2(0.5,0.5), min_lod_clamp(1.0));\n"
            "}\n";
        NSError *e = nil;
        id<MTLLibrary> lib = [dev newLibraryWithSource:src options:nil error:&e];
        pr([NSString stringWithFormat:@"lib=%@ error=%@", lib, e]);
        return 0;
    }
    if ([test isEqualToString:@"level_minlod_compile"]) {
        NSString *src = @"#include <metal_stdlib>\nusing namespace metal;\n"
            "kernel void k(texture2d<float> t [[texture(0)]], sampler s [[sampler(0)]], device float4 *o [[buffer(0)]]) {\n"
            "  o[0] = t.sample(s, float2(0.5,0.5), level(2.0), min_lod_clamp(1.0));\n"
            "}\n";
        NSError *e = nil;
        id<MTLLibrary> lib = [dev newLibraryWithSource:src options:nil error:&e];
        pr([NSString stringWithFormat:@"lib=%@ error=%@", lib, e]);
        return 0;
    }
    if ([test isEqualToString:@"comparelod_minlod_compile"]) {
        NSString *src = @"#include <metal_stdlib>\nusing namespace metal;\n"
            "kernel void k(depth2d<float> t [[texture(0)]], sampler s [[sampler(0)]], device float4 *o [[buffer(0)]]) {\n"
            "  o[0].x = t.sample_compare(s, float2(0.5,0.5), 0.5, min_lod_clamp(1.0));\n"
            "}\n";
        NSError *e = nil;
        id<MTLLibrary> lib = [dev newLibraryWithSource:src options:nil error:&e];
        pr([NSString stringWithFormat:@"lib=%@ error=%@", lib, e]);
        return 0;
    }


    if ([test isEqualToString:@"dim1d_16384"] || [test isEqualToString:@"dim1d_16385"]) {
        NSUInteger w = [test hasSuffix:@"16385"] ? 16385 : 16384;
        MTLTextureDescriptor *d = [MTLTextureDescriptor new];
        d.textureType = MTLTextureType1D; d.pixelFormat = MTLPixelFormatR8Uint;
        d.width = w; d.height = 1; d.usage = MTLTextureUsageShaderRead; d.storageMode = MTLStorageModeShared;
        @try {
            id<MTLTexture> t = [dev newTextureWithDescriptor:d];
            pr([NSString stringWithFormat:@"RESULT 1d width=%lu texture=%@", (unsigned long)w, t]);
        } @catch (NSException *ex) {
            pr([NSString stringWithFormat:@"EXCEPTION 1d width=%lu %@: %@", (unsigned long)w, ex.name, ex.reason]);
        }
        return 0;
    }
    if ([test isEqualToString:@"dimcube_16384"] || [test isEqualToString:@"dimcube_16385"]) {
        NSUInteger w = [test hasSuffix:@"16385"] ? 16385 : 16384;
        MTLTextureDescriptor *d = [MTLTextureDescriptor new];
        d.textureType = MTLTextureTypeCube; d.pixelFormat = MTLPixelFormatR8Uint;
        d.width = w; d.height = w; d.usage = MTLTextureUsageShaderRead; d.storageMode = MTLStorageModeShared;
        @try {
            id<MTLTexture> t = [dev newTextureWithDescriptor:d];
            pr([NSString stringWithFormat:@"RESULT cube width=%lu texture=%@", (unsigned long)w, t]);
        } @catch (NSException *ex) {
            pr([NSString stringWithFormat:@"EXCEPTION cube width=%lu %@: %@", (unsigned long)w, ex.name, ex.reason]);
        }
        return 0;
    }


    if ([test isEqualToString:@"dim3dw_2048"] || [test isEqualToString:@"dim3dw_2049"]) {
        NSUInteger w = [test hasSuffix:@"2049"] ? 2049 : 2048;
        MTLTextureDescriptor *d = [MTLTextureDescriptor new];
        d.textureType = MTLTextureType3D; d.pixelFormat = MTLPixelFormatR8Uint;
        d.width = w; d.height = 4; d.depth = 4; d.usage = MTLTextureUsageShaderRead; d.storageMode = MTLStorageModeShared;
        @try {
            id<MTLTexture> t = [dev newTextureWithDescriptor:d];
            pr([NSString stringWithFormat:@"RESULT 3dw=%lu texture=%@", (unsigned long)w, t]);
        } @catch (NSException *ex) {
            pr([NSString stringWithFormat:@"EXCEPTION 3dw=%lu %@: %@", (unsigned long)w, ex.name, ex.reason]);
        }
        return 0;
    }


    if ([test hasPrefix:@"msaa_"]) {
        NSInteger sc = [[test substringFromIndex:5] integerValue];
        BOOL supports = [dev supportsTextureSampleCount:sc];
        pr([NSString stringWithFormat:@"supportsTextureSampleCount(%ld)=%d", (long)sc, supports]);
        MTLTextureDescriptor *d = [MTLTextureDescriptor new];
        d.textureType = MTLTextureType2DMultisample; d.pixelFormat = MTLPixelFormatR32Uint;
        d.width = 4; d.height = 4; d.sampleCount = sc; d.usage = MTLTextureUsageShaderRead; d.storageMode = MTLStorageModeShared;
        @try {
            id<MTLTexture> t = [dev newTextureWithDescriptor:d];
            pr([NSString stringWithFormat:@"RESULT sampleCount=%ld texture=%@ actualSampleCount=%lu", (long)sc, t, t ? (unsigned long)t.sampleCount : 0]);
        } @catch (NSException *ex) {
            pr([NSString stringWithFormat:@"EXCEPTION sampleCount=%ld %@: %@", (long)sc, ex.name, ex.reason]);
        }
        return 0;
    }

    pr(@"UNKNOWN_TEST");
    return 2;
} }
