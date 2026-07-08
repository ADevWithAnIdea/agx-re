// dvar4.m — CMD-4 draw matrix harness: primitive x index-type x instancing.
// Extends dvar.m with: --itype u16|u32, --basevertex N, --baseinstance N, and the
// FULL drawIndexedPrimitives:...:instanceCount:baseVertex:baseInstance: /
// drawPrimitives:...:instanceCount:baseInstance: forms. Purpose: actually RUN the
// u32-index path (opcode 0x61f4, previously inferred-not-run) and map the VDM draw
// record field positions per primitive/index/instancing combination.
// CLEAN-ROOM: OWN-SHADER + public Metal API only. Nothing disassembled.
// Build: clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o dvar4 dvar4.m

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

static void print_va(const char *l, uint64_t va){ printf("VA %-12s = 0x%016llx\n", l,(unsigned long long)va); }

static MTLPrimitiveType parse_prim(const char *s){
  if(!strcmp(s,"point"))     return MTLPrimitiveTypePoint;
  if(!strcmp(s,"line"))      return MTLPrimitiveTypeLine;
  if(!strcmp(s,"linestrip")) return MTLPrimitiveTypeLineStrip;
  if(!strcmp(s,"tristrip"))  return MTLPrimitiveTypeTriangleStrip;
  return MTLPrimitiveTypeTriangle;
}

int main(int argc,char**argv){
 @autoreleasepool{
  long W=64,H=64,verts=6,inst=1,basev=0,basei=0,iters=1;
  const char *primS="tri",*itypeS="u16"; int indexed=0,doDump=0;
  for(int i=1;i<argc;i++){
    const char*a=argv[i];
    #define NEXT (i+1<argc?argv[++i]:(char*)"0")
    if(!strcmp(a,"--w"))W=strtol(NEXT,0,0);
    else if(!strcmp(a,"--h"))H=strtol(NEXT,0,0);
    else if(!strcmp(a,"--verts"))verts=strtol(NEXT,0,0);
    else if(!strcmp(a,"--prim"))primS=NEXT;
    else if(!strcmp(a,"--indexed"))indexed=1;
    else if(!strcmp(a,"--itype")){indexed=1;itypeS=NEXT;}
    else if(!strcmp(a,"--inst"))inst=strtol(NEXT,0,0);
    else if(!strcmp(a,"--basevertex")){indexed=1;basev=strtol(NEXT,0,0);}
    else if(!strcmp(a,"--baseinstance"))basei=strtol(NEXT,0,0);
    else if(!strcmp(a,"--iters"))iters=strtol(NEXT,0,0);
    else if(!strcmp(a,"--dump"))doDump=1;
    else printf("UNKNOWN ARG %s\n",a);
    #undef NEXT
  }
  MTLPrimitiveType prim=parse_prim(primS);
  int u32=!strcmp(itypeS,"u32");

  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  printf("DEVICE %s\n",[[dev name]UTF8String]);
  printf("CONFIG w=%ld h=%ld verts=%ld prim=%s indexed=%d itype=%s inst=%ld basev=%ld basei=%ld\n",
         W,H,verts,primS,indexed,itypeS,inst,basev,basei);

  NSString*vsrc=@"#include <metal_stdlib>\nusing namespace metal;\n"
    "struct VO{float4 pos [[position]];float4 col;};\n"
    "vertex VO v_main(uint vid [[vertex_id]],uint iid [[instance_id]],const device float2* p [[buffer(0)]]){\n"
    "  VO o;o.pos=float4(p[vid],0,1);o.col=float4(0.25,0.5,0.75,1);return o;}\n";
  NSString*fsrc=@"#include <metal_stdlib>\nusing namespace metal;\n"
    "struct VO{float4 pos [[position]];float4 col;};\n"
    "fragment float4 f_main(VO in [[stage_in]]){return in.col;}\n";
  NSError*err=nil;
  id<MTLLibrary> vl=[dev newLibraryWithSource:vsrc options:nil error:&err];
  id<MTLLibrary> fl=[dev newLibraryWithSource:fsrc options:nil error:&err];
  if(!vl||!fl){printf("SHADER_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
  MTLRenderPipelineDescriptor*pd=[MTLRenderPipelineDescriptor new];
  pd.vertexFunction=[vl newFunctionWithName:@"v_main"];
  pd.fragmentFunction=[fl newFunctionWithName:@"f_main"];
  pd.colorAttachments[0].pixelFormat=MTLPixelFormatBGRA8Unorm;
  id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithDescriptor:pd error:&err];
  if(!pso){printf("PIPELINE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}

  NSUInteger bpr=((W*4+255)&~255UL);
  MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:W height:H mipmapped:NO];
  td.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead;td.storageMode=MTLStorageModeShared;
  id<MTLBuffer> rtb=[dev newBufferWithLength:bpr*H options:MTLResourceStorageModeShared];
  id<MTLTexture> target=[rtb newTextureWithDescriptor:td offset:0 bytesPerRow:bpr];
  print_va("rtBuf",[rtb gpuAddress]);

  long nv=verts>0?verts:6;
  id<MTLBuffer> vb=[dev newBufferWithLength:(NSUInteger)(nv*8+64) options:MTLResourceStorageModeShared];
  float*vp=(float*)[vb contents];
  for(long i=0;i<nv+8;i++){ float t=(float)(i%nv)/(float)(nv>1?nv-1:1); vp[2*i+0]=-1+2*t; vp[2*i+1]=(i&1)?-1:1; }
  vp[0]=-1;vp[1]=-1;vp[2]=3;vp[3]=-1;vp[4]=-1;vp[5]=3;
  print_va("vtxBuf",[vb gpuAddress]);

  id<MTLBuffer> ib=nil; NSUInteger idxCount=(NSUInteger)nv;
  if(indexed){
    if(u32){ ib=[dev newBufferWithLength:idxCount*4 options:MTLResourceStorageModeShared];
             uint32_t*q=(uint32_t*)[ib contents]; for(long k=0;k<(long)idxCount;k++)q[k]=(uint32_t)k; }
    else   { ib=[dev newBufferWithLength:idxCount*2 options:MTLResourceStorageModeShared];
             uint16_t*q=(uint16_t*)[ib contents]; for(long k=0;k<(long)idxCount;k++)q[k]=(uint16_t)k; }
    print_va("idxBuf",[ib gpuAddress]);
  }

  id<MTLCommandQueue> q=[dev newCommandQueue];
  for(long it=0;it<iters;it++){
    printf("SUBMIT iter=%ld begin\n",it);
    MTLRenderPassDescriptor*rp=[MTLRenderPassDescriptor new];
    rp.colorAttachments[0].texture=target;
    rp.colorAttachments[0].loadAction=MTLLoadActionClear;
    rp.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,1);
    rp.colorAttachments[0].storeAction=MTLStoreActionStore;
    id<MTLCommandBuffer> cb=[q commandBuffer];
    id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
    [enc setRenderPipelineState:pso];
    MTLViewport vpt={0,0,(double)W,(double)H,0,1};[enc setViewport:vpt];
    [enc setVertexBuffer:vb offset:0 atIndex:0];
    @try{
    if(indexed)
      [enc drawIndexedPrimitives:prim indexCount:idxCount
           indexType:(u32?MTLIndexTypeUInt32:MTLIndexTypeUInt16)
           indexBuffer:ib indexBufferOffset:0 instanceCount:(NSUInteger)inst
           baseVertex:basev baseInstance:(NSUInteger)basei];
    else
      [enc drawPrimitives:prim vertexStart:0 vertexCount:idxCount
           instanceCount:(NSUInteger)inst baseInstance:(NSUInteger)basei];
    }@catch(NSException*e){printf("DRAW_EXC %s\n",[[e reason]UTF8String]);}
    [enc endEncoding];[cb commit];[cb waitUntilCompleted];
    printf("SUBMIT iter=%ld done status=%ld\n",it,(long)[cb status]);
    if([cb error])printf("CB_ERROR %s\n",[[[cb error]localizedDescription]UTF8String]);
    if(doDump&&it==iters-1){fflush(stdout);kill(getpid(),SIGUSR1);usleep(400000);}
  }
  return 0;
 }
}
