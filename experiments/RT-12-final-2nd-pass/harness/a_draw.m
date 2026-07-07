// a_draw.m -- RT-12 Part A: independent re-verify of indirect-draw opcodes + args-ptr layout.
// DIFFERENT from RT-6/midraw: uses a 6-vertex quad (two-tri list) and a 6-index indexed draw,
// distinct colors/pixel format, and a single-mode-per-run capture so a host analyzer can diff
// direct vs indirect at the VDM stream (fw-ctx 0x18000).
//
// modes: direct | indirect | idxdirect | idxindirect
//   direct       drawPrimitives(triangle, start=0, count=6)               -> opcode 0x61c4, vtxCount@+0x68
//   indirect     drawPrimitives(triangle, indirectBuffer)                 -> opcode 0x6404, argptr@+0x68(hi)/+0x6c(lo)
//   idxdirect    drawIndexedPrimitives(triangle, 6, u16)                  -> opcode 0x61f2 (shifted record)
//   idxindirect  drawIndexedPrimitives(triangle, indirectBuffer)         -> opcode 0x6432, argptr@+0x74/+0x78
//
// CLEAN-ROOM: OWN-SHADER + public Metal API + DATA-TRACE (read-only iotrace). No Apple binary
// disassembled. See ../../CLAUDE.md.
// Build: clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o a_draw a_draw.m
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
static void pv(const char*l,uint64_t v){printf("VA %-12s = 0x%016llx\n",l,(unsigned long long)v);}
int main(int argc,char**argv){ @autoreleasepool{
  const char*mode="direct"; int doDump=0;
  for(int i=1;i<argc;i++){ if(!strcmp(argv[i],"--mode")&&i+1<argc) mode=argv[++i];
    else if(!strcmp(argv[i],"--dump")) doDump=1; }
  id<MTLDevice> dev=MTLCreateSystemDefaultDevice(); NSError*err=nil;
  printf("DEVICE %s MODE %s\n",[[dev name]UTF8String],mode);
  NSString*g=@"#include <metal_stdlib>\nusing namespace metal;\n"
    "struct VO{float4 pos [[position]];float4 col;};\n"
    "vertex VO v_main(uint vid [[vertex_id]], const device float2* p [[buffer(0)]]){VO o;o.pos=float4(p[vid],0,1);o.col=float4(0.9,0.1,0.4,1);return o;}\n"
    "fragment float4 f_main(VO in [[stage_in]]){return in.col;}\n";
  id<MTLLibrary> gl=[dev newLibraryWithSource:g options:nil error:&err];
  MTLRenderPipelineDescriptor*pd=[MTLRenderPipelineDescriptor new];
  pd.vertexFunction=[gl newFunctionWithName:@"v_main"];
  pd.fragmentFunction=[gl newFunctionWithName:@"f_main"];
  pd.colorAttachments[0].pixelFormat=MTLPixelFormatRGBA8Unorm; // distinct from RT-6's BGRA8
  id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithDescriptor:pd error:&err];
  if(!pso){printf("PSO_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
  long W=48,H=48; NSUInteger bpr=((W*4)+255)&~255UL;
  id<MTLBuffer> rtb=[dev newBufferWithLength:bpr*H options:MTLResourceStorageModeShared];
  MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:W height:H mipmapped:NO];
  td.usage=MTLTextureUsageRenderTarget; td.storageMode=MTLStorageModeShared;
  id<MTLTexture> target=[rtb newTextureWithDescriptor:td offset:0 bytesPerRow:bpr];
  // 6-vertex quad (two triangles)
  float verts[12]={-1,-1, 1,-1, -1,1,  1,-1, 1,1, -1,1};
  id<MTLBuffer> vb=[dev newBufferWithBytes:verts length:sizeof(verts) options:MTLResourceStorageModeShared];
  pv("vtxBuf",[vb gpuAddress]);
  uint16_t idx[6]={0,1,2,3,4,5};
  id<MTLBuffer> ib=[dev newBufferWithBytes:idx length:sizeof(idx) options:MTLResourceStorageModeShared];
  pv("idxBuf",[ib gpuAddress]);
  // indirect args buffers
  MTLDrawPrimitivesIndirectArguments da={6,1,0,0};
  id<MTLBuffer> ab=[dev newBufferWithBytes:&da length:sizeof(da) options:MTLResourceStorageModeShared];
  pv("argBuf",[ab gpuAddress]);
  MTLDrawIndexedPrimitivesIndirectArguments dia={6,1,0,0,0};
  id<MTLBuffer> iab=[dev newBufferWithBytes:&dia length:sizeof(dia) options:MTLResourceStorageModeShared];
  pv("idxArgBuf",[iab gpuAddress]);

  id<MTLCommandQueue> q=[dev newCommandQueue];
  MTLRenderPassDescriptor*rp=[MTLRenderPassDescriptor new];
  rp.colorAttachments[0].texture=target; rp.colorAttachments[0].loadAction=MTLLoadActionClear;
  rp.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,1); rp.colorAttachments[0].storeAction=MTLStoreActionStore;
  id<MTLCommandBuffer> cb=[q commandBuffer];
  id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
  MTLViewport vpt={0,0,(double)W,(double)H,0,1}; [enc setViewport:vpt];
  [enc setRenderPipelineState:pso]; [enc setVertexBuffer:vb offset:0 atIndex:0];
  if(!strcmp(mode,"direct"))
    [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:6];
  else if(!strcmp(mode,"indirect"))
    [enc drawPrimitives:MTLPrimitiveTypeTriangle indirectBuffer:ab indirectBufferOffset:0];
  else if(!strcmp(mode,"idxdirect"))
    [enc drawIndexedPrimitives:MTLPrimitiveTypeTriangle indexCount:6 indexType:MTLIndexTypeUInt16 indexBuffer:ib indexBufferOffset:0];
  else if(!strcmp(mode,"idxindirect"))
    [enc drawIndexedPrimitives:MTLPrimitiveTypeTriangle indexType:MTLIndexTypeUInt16 indexBuffer:ib indexBufferOffset:0 indirectBuffer:iab indirectBufferOffset:0];
  else { printf("BAD_MODE\n"); return 2; }
  [enc endEncoding]; [cb commit]; [cb waitUntilCompleted];
  printf("SUBMIT status=%ld\n",(long)[cb status]);
  if(doDump){fflush(stdout);kill(getpid(),SIGUSR1);usleep(500000);}
  return 0;
}}
