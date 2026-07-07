// iotile.m — OWN tile-shader (dispatchThreadsPerTile) draw+dispatch, for HW
// validation of imageblock WRITE and iotrace capture of the tile-dispatch cmdstream.
// A full-screen triangle writes color X; then a TILE kernel overwrites the
// imageblock with color Y; read-back == Y proves the mid-render tile dispatch ran.
// CLEAN-ROOM: OWN-SHADER + public Metal API only. EXP-O2D.
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
#include <simd/simd.h>

static void print_va(const char *l, uint64_t va){ printf("VA %-10s = 0x%016llx le=",l,(unsigned long long)va);
  for(int i=0;i<8;i++) printf("%02x",(unsigned)((va>>(8*i))&0xff)); printf("\n"); }

int main(int argc, char **argv){ @autoreleasepool {
    long W=32,H=32; int doDump=0, doDraw=1, doTile=1;
    for(int i=1;i<argc;i++){ if(!strcmp(argv[i],"--w")&&i+1<argc)W=strtol(argv[++i],0,0);
        else if(!strcmp(argv[i],"--h")&&i+1<argc)H=strtol(argv[++i],0,0);
        else if(!strcmp(argv[i],"--dump"))doDump=1; else if(!strcmp(argv[i],"--no-draw"))doDraw=0; else if(!strcmp(argv[i],"--no-tile"))doTile=0; }
    id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
    printf("DEVICE %s\nTILE w=%ld h=%ld draw=%d\n",[[dev name] UTF8String],W,H,doDraw);

    NSString *src=@"#include <metal_stdlib>\n"
      "using namespace metal;\n"
      "struct VO { float4 pos [[position]]; };\n"
      "vertex VO v_main(uint vid [[vertex_id]]){ float2 p[3]={float2(-1,-1),float2(3,-1),float2(-1,3)};"
      " VO o; o.pos=float4(p[vid],0,1); return o; }\n"
      "struct IB { half4 c [[color(0)]]; };\n"
      "fragment IB f_main(VO in [[stage_in]]){ IB o; o.c=half4(0.20h,0.40h,0.60h,1.0h); return o; }\n"
      "kernel void tile_paint(imageblock<IB> img, ushort2 t [[thread_position_in_threadgroup]]){"
      " IB v; v.c=half4(0.90h,0.10h,0.40h,1.0h); img.write(v,t); }\n";
    NSError *err=nil;
    id<MTLLibrary> lib=[dev newLibraryWithSource:src options:nil error:&err];
    if(!lib){ printf("COMPILE_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }

    MTLRenderPipelineDescriptor *pd=[MTLRenderPipelineDescriptor new];
    pd.vertexFunction=[lib newFunctionWithName:@"v_main"];
    pd.fragmentFunction=[lib newFunctionWithName:@"f_main"];
    pd.colorAttachments[0].pixelFormat=MTLPixelFormatRGBA16Float; // 115
    id<MTLRenderPipelineState> rpso=[dev newRenderPipelineStateWithDescriptor:pd error:&err];
    if(!rpso){ printf("RENDER_PIPELINE_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }

    MTLTileRenderPipelineDescriptor *tdsc=[MTLTileRenderPipelineDescriptor new];
    tdsc.tileFunction=[lib newFunctionWithName:@"tile_paint"];
    tdsc.threadgroupSizeMatchesTileSize=YES;
    tdsc.colorAttachments[0].pixelFormat=MTLPixelFormatRGBA16Float;
    id<MTLRenderPipelineState> tpso=[dev newRenderPipelineStateWithTileDescriptor:tdsc options:0 reflection:nil error:&err];
    if(!tpso){ printf("TILE_PIPELINE_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }
    printf("TILE_PIPELINE_OK maxThreads=%lu\n",(unsigned long)[tpso maxTotalThreadsPerThreadgroup]);

    MTLTextureDescriptor *ttd=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA16Float width:(NSUInteger)W height:(NSUInteger)H mipmapped:NO];
    ttd.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead; ttd.storageMode=MTLStorageModeShared;
    id<MTLTexture> target=[dev newTextureWithDescriptor:ttd];

    id<MTLCommandQueue> q=[dev newCommandQueue];
    printf("SUBMIT begin\n");
    MTLRenderPassDescriptor *rp=[MTLRenderPassDescriptor new];
    rp.colorAttachments[0].texture=target;
    rp.colorAttachments[0].loadAction=MTLLoadActionClear;
    rp.colorAttachments[0].clearColor=MTLClearColorMake(0.0,0.0,0.0,1.0);
    rp.colorAttachments[0].storeAction=MTLStoreActionStore;
    id<MTLCommandBuffer> cb=[q commandBuffer];
    id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
    if(doDraw){ [enc setRenderPipelineState:rpso]; [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3]; }
    // ---- mid-render TILE dispatch (the tile shader) ----
    if(doTile){ [enc setRenderPipelineState:tpso]; [enc dispatchThreadsPerTile:MTLSizeMake(W,H,1)]; }
    [enc endEncoding];
    [cb commit];
    [cb waitUntilCompleted];
    printf("SUBMIT done status=%ld\n",(long)[cb status]);
    if(cb.error) printf("CB_ERROR %s\n",[[cb.error localizedDescription] UTF8String]);
    if(doDump){ fflush(stdout); kill(getpid(),SIGUSR1); usleep(400000); }

    // read back half4 pixel (RGBA16Float = 8 bytes)
    uint16_t px[4];
    [target getBytes:px bytesPerRow:8 fromRegion:MTLRegionMake2D(0,0,1,1) mipmapLevel:0];
    // decode half -> float (simple)
    printf("PIXEL half-bits = %04x %04x %04x %04x\n",px[0],px[1],px[2],px[3]);
    // 0.9h=0x3b33, 0.1h=0x2e66, 0.4h=0x3666, 1.0h=0x3c00 (tile-written color Y)
    printf("EXPECT tile Y ~ 3b33 2e66 3666 3c00 (0.9,0.1,0.4,1.0)\n");
    return 0;
} }
