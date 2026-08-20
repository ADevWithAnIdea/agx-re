#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <sys/utsname.h>
#include <stdio.h>
#include <string.h>

static void js(NSString *s) { NSData *d=[NSJSONSerialization dataWithJSONObject:@[s ?: @""] options:0 error:nil]; fwrite(d.bytes,1,d.length,stdout); }
static void hex(const unsigned char *p, NSUInteger n) { for(NSUInteger i=0;i<n;i++) printf("%02x",p[i]); }
static MTLPixelFormat fmt(const char *n) { if(!strcmp(n,"rgba8unorm_edges"))return MTLPixelFormatRGBA8Unorm; if(!strcmp(n,"bgra8unorm_edges"))return MTLPixelFormatBGRA8Unorm; if(!strcmp(n,"rgba8srgb_threshold"))return MTLPixelFormatRGBA8Unorm_sRGB; if(!strcmp(n,"r16unorm_midpoint"))return MTLPixelFormatR16Unorm; if(!strcmp(n,"rgba16float_finite"))return MTLPixelFormatRGBA16Float; if(!strcmp(n,"r32uint_exact"))return MTLPixelFormatR32Uint; return MTLPixelFormatInvalid; }
static BOOL isuint(const char*n) { return !strcmp(n,"r32uint_exact"); }
static BOOL guard(const unsigned char *p, NSUInteger n, unsigned char v) { for(NSUInteger i=0;i<n;i++) if(p[i]!=v)return NO; return YES; }
int main(int ac, const char **av) { @autoreleasepool {
    const char *source=NULL,*name=NULL; for(int i=1;i<ac;i++) { if(!strcmp(av[i],"--source")&&i+1<ac)source=av[++i]; else if(!strcmp(av[i],"--case")&&i+1<ac)name=av[++i]; }
    if(!source || !name || fmt(name)==MTLPixelFormatInvalid) return 2;
    NSError *e=nil; NSString *msl=[NSString stringWithContentsOfFile:@(source) encoding:NSUTF8StringEncoding error:&e];
    id<MTLDevice> d=MTLCreateSystemDefaultDevice(); id<MTLLibrary> lib=[d newLibraryWithSource:msl options:nil error:&e];
    NSString *frag=[@"f_" stringByAppendingString:@(name)]; MTLRenderPipelineDescriptor *pd=[MTLRenderPipelineDescriptor new]; pd.vertexFunction=[lib newFunctionWithName:@"v_main"]; pd.fragmentFunction=[lib newFunctionWithName:frag]; pd.colorAttachments[0].pixelFormat=fmt(name);
    id<MTLRenderPipelineState> rp=[d newRenderPipelineStateWithDescriptor:pd error:&e]; id<MTLComputePipelineState> cp=[d newComputePipelineStateWithFunction:[lib newFunctionWithName:isuint(name)?@"k_read_uint":@"k_read_float"] error:&e];
    if(!d||!lib||!rp||!cp) { printf("{\"case\":");js(@(name));printf(",\"error\":");js(e.localizedDescription);puts("}");return 3; }
    id<MTLBuffer> rb=[d newBufferWithLength:384 options:MTLResourceStorageModeShared]; id<MTLBuffer> cb=[d newBufferWithLength:144 options:MTLResourceStorageModeShared]; unsigned char *r=rb.contents,*c=cb.contents; memset(r,0x5a,64);memset(r+64,0,256);memset(r+320,0xa5,64);memset(c,0x5a,64);memset(c+64,0,16);memset(c+80,0xa5,64);
    MTLTextureDescriptor *td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:fmt(name) width:1 height:1 mipmapped:NO]; td.storageMode=MTLStorageModeShared;td.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead; id<MTLTexture> t=[rb newTextureWithDescriptor:td offset:64 bytesPerRow:256];
    id<MTLCommandBuffer> q=[[d newCommandQueue] commandBuffer]; MTLRenderPassDescriptor *pass=[MTLRenderPassDescriptor new];pass.colorAttachments[0].texture=t;pass.colorAttachments[0].loadAction=MTLLoadActionDontCare;pass.colorAttachments[0].storeAction=MTLStoreActionStore; id<MTLRenderCommandEncoder> re=[q renderCommandEncoderWithDescriptor:pass];[re setRenderPipelineState:rp];[re drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];[re endEncoding]; id<MTLComputeCommandEncoder> ce=[q computeCommandEncoder];[ce setComputePipelineState:cp];[ce setTexture:t atIndex:0];[ce setBuffer:cb offset:64 atIndex:0];[ce dispatchThreads:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];[ce endEncoding];[q commit];[q waitUntilCompleted];
    struct utsname u; uname(&u); uint32_t *w=(uint32_t *)(c+64); printf("{\"case\":");js(@(name));printf(",\"command_buffer_status\":%ld,\"device\":",(long)q.status);js(d.name);printf(",\"error\":");js(q.error.localizedDescription);printf(",\"machine\":");js(@(u.machine));printf(",\"os\":");js(NSProcessInfo.processInfo.operatingSystemVersionString);printf(",\"physical_texel_hex\":\""); hex(r+64, fmt(name)==MTLPixelFormatR16Unorm?2:(fmt(name)==MTLPixelFormatRGBA16Float?8:4));printf("\",\"render_hex\":\"");hex(r,384);printf("\",\"compute_hex\":\"");hex(c,144);printf("\",\"compute_words_le\":[%u,%u,%u,%u],\"render_prefix_guard\":%s,\"render_suffix_guard\":%s,\"compute_prefix_guard\":%s,\"compute_suffix_guard\":%s}\n",w[0],w[1],w[2],w[3],guard(r,64,0x5a)?"true":"false",guard(r+320,64,0xa5)?"true":"false",guard(c,64,0x5a)?"true":"false",guard(c+80,64,0xa5)?"true":"false"); return q.status==MTLCommandBufferStatusCompleted?0:4;
} }
