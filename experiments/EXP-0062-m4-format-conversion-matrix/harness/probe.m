// EXP-0062 public-Metal format behavior harness; no archive, IOKit, or BO access.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <stdio.h>
#include <string.h>
#include <sys/utsname.h>

enum { GUARD = 64, ROW = 256, RENDER_BYTES = GUARD + ROW + GUARD, COMPUTE_BYTES = GUARD + 16 + GUARD };

static void hex(const uint8_t *p, size_t n) { for (size_t i = 0; i < n; ++i) printf("%02x", p[i]); }
static void jstr(NSString *s) {
    NSData *d = [NSJSONSerialization dataWithJSONObject:@[s ?: @""] options:0 error:nil];
    fwrite((const char *)d.bytes + 1, 1, d.length - 2, stdout);
}
static MTLPixelFormat fmt(const char *name) {
    if (!strcmp(name,"rgba8unorm_edges")) return MTLPixelFormatRGBA8Unorm;
    if (!strcmp(name,"bgra8unorm_edges")) return MTLPixelFormatBGRA8Unorm;
    if (!strcmp(name,"rgba8srgb_threshold")) return MTLPixelFormatRGBA8Unorm_sRGB;
    if (!strcmp(name,"r16unorm_midpoint")) return MTLPixelFormatR16Unorm;
    if (!strcmp(name,"rgba16float_edges")) return MTLPixelFormatRGBA16Float;
    if (!strcmp(name,"r32uint_exact")) return MTLPixelFormatR32Uint;
    return MTLPixelFormatInvalid;
}
static unsigned bpp(const char *name) {
    if (!strcmp(name,"r16unorm_midpoint")) return 2;
    if (!strcmp(name,"r32uint_exact")) return 4;
    if (!strcmp(name,"rgba16float_edges")) return 8;
    return 4;
}
int main(int argc, const char **argv) {
 @autoreleasepool {
    const char *sourcePath = NULL, *name = NULL;
    for (int i=1;i<argc;i++) { if (!strcmp(argv[i],"--source") && i+1<argc) sourcePath=argv[++i]; else if (!strcmp(argv[i],"--case") && i+1<argc) name=argv[++i]; }
    if (!sourcePath || !name || fmt(name)==MTLPixelFormatInvalid) return 2;
    NSError *err=nil; NSString *src=[NSString stringWithContentsOfFile:@(sourcePath) encoding:NSUTF8StringEncoding error:&err];
    if (!src) { printf("{\"phase\":\"source\",\"error\":"); jstr(err.localizedDescription); puts("}"); return 10; }
    id<MTLDevice> dev=MTLCreateSystemDefaultDevice(); if (!dev) { puts("{\"phase\":\"device\",\"error\":\"no-device\"}"); return 11; }
    MTLCompileOptions *opts=[MTLCompileOptions new]; opts.mathMode=MTLMathModeSafe;
    id<MTLLibrary> lib=[dev newLibraryWithSource:src options:opts error:&err];
    if (!lib) { printf("{\"phase\":\"compile\",\"error\":"); jstr(err.localizedDescription); puts("}"); return 12; }
    NSString *fragment=[@"f_" stringByAppendingString:@(name)];
    id<MTLFunction> vf=[lib newFunctionWithName:@"v_main"], ff=[lib newFunctionWithName:fragment];
    MTLRenderPipelineDescriptor *rd=[MTLRenderPipelineDescriptor new]; rd.vertexFunction=vf; rd.fragmentFunction=ff; rd.colorAttachments[0].pixelFormat=fmt(name);
    id<MTLRenderPipelineState> rp=[dev newRenderPipelineStateWithDescriptor:rd error:&err];
    if (!rp) { printf("{\"phase\":\"render_pipeline\",\"error\":"); jstr(err.localizedDescription); puts("}"); return 13; }
    id<MTLFunction> cf=[lib newFunctionWithName:(!strcmp(name,"r32uint_exact") ? @"k_read_uint" : @"k_read_float")];
    id<MTLComputePipelineState> cp=[dev newComputePipelineStateWithFunction:cf error:&err];
    if (!cp) { printf("{\"phase\":\"compute_pipeline\",\"error\":"); jstr(err.localizedDescription); puts("}"); return 14; }
    id<MTLBuffer> rb=[dev newBufferWithLength:RENDER_BYTES options:MTLResourceStorageModeShared];
    id<MTLBuffer> cbout=[dev newBufferWithLength:COMPUTE_BYTES options:MTLResourceStorageModeShared];
    if (!rb || !cbout) { puts("{\"phase\":\"allocation\",\"error\":\"shared-buffer\"}"); return 15; }
    memset(rb.contents,0x5a,GUARD); memset((uint8_t *)rb.contents+GUARD,0,ROW); memset((uint8_t *)rb.contents+GUARD+ROW,0xa5,GUARD);
    memset(cbout.contents,0x5a,GUARD); memset((uint8_t *)cbout.contents+GUARD,0,16); memset((uint8_t *)cbout.contents+GUARD+16,0xa5,GUARD);
    MTLTextureDescriptor *td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:fmt(name) width:1 height:1 mipmapped:NO]; td.storageMode=MTLStorageModeShared; td.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead;
    id<MTLTexture> tex=[rb newTextureWithDescriptor:td offset:GUARD bytesPerRow:ROW]; if (!tex) { puts("{\"phase\":\"texture\",\"error\":\"shared-texture\"}"); return 16; }
    id<MTLCommandQueue> q=[dev newCommandQueue]; id<MTLCommandBuffer> cmd=[q commandBuffer];
    MTLRenderPassDescriptor *pass=[MTLRenderPassDescriptor new]; pass.colorAttachments[0].texture=tex; pass.colorAttachments[0].loadAction=MTLLoadActionDontCare; pass.colorAttachments[0].storeAction=MTLStoreActionStore;
    id<MTLRenderCommandEncoder> re=[cmd renderCommandEncoderWithDescriptor:pass]; [re setRenderPipelineState:rp]; [re drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3]; [re endEncoding];
    id<MTLComputeCommandEncoder> ce=[cmd computeCommandEncoder]; [ce setComputePipelineState:cp]; [ce setTexture:tex atIndex:0]; [ce setBuffer:cbout offset:GUARD atIndex:0]; [ce dispatchThreads:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)]; [ce endEncoding]; [cmd commit]; [cmd waitUntilCompleted];
    uint8_t *r=rb.contents,*c=cbout.contents; BOOL rg1=YES,rg2=YES,cg1=YES,cg2=YES;
    for(unsigned i=0;i<GUARD;i++){rg1 &= r[i]==0x5a;rg2 &= r[GUARD+ROW+i]==0xa5;cg1 &= c[i]==0x5a;cg2 &= c[GUARD+16+i]==0xa5;}
    struct utsname u; uname(&u); uint32_t *words=(uint32_t *)(c+GUARD);
    printf("{\"phase\":\"execution\",\"case\":");jstr(@(name));printf(",\"device\":");jstr(dev.name);printf(",\"os\":");jstr([[NSProcessInfo processInfo] operatingSystemVersionString]);printf(",\"machine\":");jstr(@(u.machine));
    printf(",\"status\":%ld,\"bpp\":%u,\"render_hex\":\"",(long)cmd.status,bpp(name));hex(r,RENDER_BYTES);printf("\",\"compute_hex\":\"");hex(c,COMPUTE_BYTES);printf("\",\"physical_texel_hex\":\"");hex(r+GUARD,bpp(name));
    printf("\",\"compute_words_le\":[%u,%u,%u,%u],\"render_prefix_guard\":%s,\"render_suffix_guard\":%s,\"compute_prefix_guard\":%s,\"compute_suffix_guard\":%s,\"error\":",words[0],words[1],words[2],words[3],rg1?"true":"false",rg2?"true":"false",cg1?"true":"false",cg2?"true":"false");jstr(cmd.error.localizedDescription);puts("}");
    return cmd.status==MTLCommandBufferStatusCompleted && rg1&&rg2&&cg1&&cg2 ? 0 : 17;
 }
}
