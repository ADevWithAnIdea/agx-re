// dvar2.m — RT-2a adversarial VDM DRAW-RECORD harness.
//
// Red-team extension of EXP-0014's dvar.m: adds base-vertex / base-instance /
// vertexStart(firstIndex) so we can falsify the VDM draw-record field map
//   primitive @+0x65, vertexCount @+0x68, instanceCount @+0x6c,
//   indexed opcode 0x61c4->0x61f2 + index-buf @+0x70.
// Every draw parameter is a CLI flag -> change exactly ONE, re-capture registered
// BOs under the iotrace interposer, byte-diff.  CLEAN-ROOM: OWN-SHADER + public
// Metal API only; nothing disassembles any Apple binary.
//
// Build (device): clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o dvar2 dvar2.m
//
// Usage:
//   dvar2 [--w W --h H] [--prim P] [--verts N] [--inst N] [--start N]
//         [--indexed] [--itype u16|u32] [--basevert N] [--baseinst N]
//         [--idxoff BYTES] [--iters N] [--dump]
//   --prim : tri | strip | line | linestrip | point

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

static void print_va(const char *label, uint64_t va){
    unsigned char b[8]; for(int i=0;i<8;i++) b[i]=(va>>(8*i))&0xff;
    printf("VA %-12s = 0x%016llx  le=",label,(unsigned long long)va);
    for(int i=0;i<8;i++) printf("%02x",b[i]); printf("\n");
}
static MTLPrimitiveType parse_prim(const char *s){
    if(!strcmp(s,"point"))     return MTLPrimitiveTypePoint;
    if(!strcmp(s,"line"))      return MTLPrimitiveTypeLine;
    if(!strcmp(s,"linestrip")) return MTLPrimitiveTypeLineStrip;
    if(!strcmp(s,"strip"))     return MTLPrimitiveTypeTriangleStrip;
    return MTLPrimitiveTypeTriangle;
}

int main(int argc,char**argv){
  @autoreleasepool{
    long W=64,H=64,verts=3,inst=1,start=0,basevert=0,baseinst=0,iters=1,idxoff=0;
    const char *primS="tri",*itypeS="u16";
    int indexed=0,doDump=0;
    for(int i=1;i<argc;i++){
      const char*a=argv[i];
      #define NEXT (i+1<argc?argv[++i]:(char*)"0")
      if(!strcmp(a,"--w"))W=strtol(NEXT,0,0);
      else if(!strcmp(a,"--h"))H=strtol(NEXT,0,0);
      else if(!strcmp(a,"--prim"))primS=NEXT;
      else if(!strcmp(a,"--verts"))verts=strtol(NEXT,0,0);
      else if(!strcmp(a,"--inst"))inst=strtol(NEXT,0,0);
      else if(!strcmp(a,"--start"))start=strtol(NEXT,0,0);
      else if(!strcmp(a,"--basevert"))basevert=strtol(NEXT,0,0);
      else if(!strcmp(a,"--baseinst"))baseinst=strtol(NEXT,0,0);
      else if(!strcmp(a,"--idxoff"))idxoff=strtol(NEXT,0,0);
      else if(!strcmp(a,"--itype")){indexed=1;itypeS=NEXT;}
      else if(!strcmp(a,"--indexed"))indexed=1;
      else if(!strcmp(a,"--iters"))iters=strtol(NEXT,0,0);
      else if(!strcmp(a,"--dump"))doDump=1;
      else printf("UNKNOWN ARG %s\n",a);
      #undef NEXT
    }
    MTLPrimitiveType prim=parse_prim(primS);
    int u32=!strcmp(itypeS,"u32");

    id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
    printf("DEVICE %s\n",[[dev name] UTF8String]);
    printf("CONFIG w=%ld h=%ld prim=%s verts=%ld inst=%ld start=%ld indexed=%d itype=%s "
           "basevert=%ld baseinst=%ld idxoff=%ld iters=%ld\n",
           W,H,primS,verts,inst,start,indexed,itypeS,basevert,baseinst,idxoff,iters);

    NSError*err=nil;
    NSString*vsrc=@"#include <metal_stdlib>\nusing namespace metal;\n"
      "struct VO{float4 pos [[position]];float4 col;};\n"
      "vertex VO v_main(uint vid [[vertex_id]],uint iid [[instance_id]],\n"
      "                 const device float2* p [[buffer(0)]]){\n"
      "  VO o;o.pos=float4(p[vid],0,1);o.col=float4(0.25,0.5,0.75,1)*(1.0+float(iid)*1e-9);return o;}\n";
    NSString*fsrc=@"#include <metal_stdlib>\nusing namespace metal;\n"
      "struct VO{float4 pos [[position]];float4 col;};\n"
      "fragment float4 f_main(VO in [[stage_in]]){return in.col;}\n";
    id<MTLLibrary> vl=[dev newLibraryWithSource:vsrc options:nil error:&err];
    id<MTLLibrary> fl=[dev newLibraryWithSource:fsrc options:nil error:&err];
    if(!vl||!fl){printf("SHADER_FAIL %s\n",[[err localizedDescription] UTF8String]);return 1;}
    MTLRenderPipelineDescriptor*pd=[MTLRenderPipelineDescriptor new];
    pd.vertexFunction=[vl newFunctionWithName:@"v_main"];
    pd.fragmentFunction=[fl newFunctionWithName:@"f_main"];
    pd.colorAttachments[0].pixelFormat=MTLPixelFormatBGRA8Unorm;
    id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithDescriptor:pd error:&err];
    if(!pso){printf("PIPELINE_FAIL %s\n",[[err localizedDescription] UTF8String]);return 1;}

    NSUInteger bpr=((W*4+255)&~255UL);
    MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm
                             width:(NSUInteger)W height:(NSUInteger)H mipmapped:NO];
    td.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead;td.storageMode=MTLStorageModeShared;
    id<MTLBuffer> rtb=[dev newBufferWithLength:bpr*H options:MTLResourceStorageModeShared];
    id<MTLTexture> target=[rtb newTextureWithDescriptor:td offset:0 bytesPerRow:bpr];
    print_va("rtBuf",[rtb gpuAddress]);

    // vertex buffer: enough verts to cover start+verts+basevert
    long nv=start+verts+basevert; if(nv<8)nv=8;
    id<MTLBuffer> vb=[dev newBufferWithLength:(NSUInteger)(nv*8) options:MTLResourceStorageModeShared];
    float*vp=(float*)[vb contents];
    for(long i=0;i<nv;i++){vp[2*i+0]=-1.0f+2.0f*((float)i/(float)(nv-1));vp[2*i+1]=(i%2)?-1.0f:1.0f;}
    vp[0]=-1;vp[1]=-1;vp[2]=3;vp[3]=-1;vp[4]=-1;vp[5]=3;
    print_va("vtxBuf",[vb gpuAddress]);

    id<MTLBuffer> ib=nil; long nidx=start+verts;
    if(indexed){
      long cap=nidx+8;
      ib=[dev newBufferWithLength:(NSUInteger)(cap*(u32?4:2)) options:MTLResourceStorageModeShared];
      if(u32){uint32_t*ip=(uint32_t*)[ib contents];for(long i=0;i<cap;i++)ip[i]=(uint32_t)i;}
      else   {uint16_t*ip=(uint16_t*)[ib contents];for(long i=0;i<cap;i++)ip[i]=(uint16_t)i;}
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
      MTLViewport vp2={0,0,(double)W,(double)H,0,1};[enc setViewport:vp2];
      [enc setVertexBuffer:vb offset:0 atIndex:0];
      @try{
        if(indexed)
          [enc drawIndexedPrimitives:prim indexCount:(NSUInteger)verts
               indexType:(u32?MTLIndexTypeUInt32:MTLIndexTypeUInt16)
               indexBuffer:ib indexBufferOffset:(NSUInteger)(idxoff)
               instanceCount:(NSUInteger)inst baseVertex:basevert baseInstance:(NSUInteger)baseinst];
        else
          [enc drawPrimitives:prim vertexStart:(NSUInteger)start vertexCount:(NSUInteger)verts
               instanceCount:(NSUInteger)inst baseInstance:(NSUInteger)baseinst];
      }@catch(NSException*e){printf("DRAW_EXC %s\n",[[e reason] UTF8String]);}
      [enc endEncoding];[cb commit];[cb waitUntilCompleted];
      printf("SUBMIT iter=%ld done status=%ld\n",it,(long)[cb status]);
      if([cb error])printf("CB_ERROR %s\n",[[[cb error] localizedDescription] UTF8String]);
      if(doDump&&it==iters-1){fflush(stdout);kill(getpid(),SIGUSR1);usleep(400000);}
    }
    return 0;
  }
}
