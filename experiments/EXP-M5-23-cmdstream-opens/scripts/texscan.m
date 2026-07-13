// texscan.m — M5 intra-tile Morton byte-order probe that does NOT depend on the IOKit
// data-trace. On M5, standalone StorageModeShared texture backings are registered through
// a path invisible to iotrace's sel-9 tracker, and heap textures are lossless-compressed.
// But a StorageModeShared texture's raw bytes live in OUR OWN process VM. Here we:
//   1) compute-write texel(x,y)=(y<<16)|x into an uncompressed (ShaderWrite) 2-D texture,
//   2) walk our OWN task's VM regions and search for the Morton needle (the first 32 texels
//      in Z-order), then dump the raw texture backing to a .hex file.
// Clean-room: we read OUR OWN process memory holding OUR OWN texture's data. No Apple binary
// is introspected; this is the same non-copyrightable hardware-layout data a data-trace logs.
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <mach/mach.h>
#include <mach/mach_vm.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
static uint32_t mval(int p){ // value at Morton position p: decode (x,y), return (y<<16)|x
  uint32_t x=0,y=0; for(int i=0;i<8;i++){ x|=((p>>(2*i))&1)<<i; y|=((p>>(2*i+1))&1)<<i; } return (y<<16)|x;
}
int main(int argc,char**argv){@autoreleasepool{
  long W=192,H=192; const char*out="texbacking.hex";
  for(int i=1;i<argc;i++){
    if(!strcmp(argv[i],"--w")&&i+1<argc)W=atol(argv[++i]);
    else if(!strcmp(argv[i],"--h")&&i+1<argc)H=atol(argv[++i]);
    else if(!strcmp(argv[i],"--out")&&i+1<argc)out=argv[++i];
  }
  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatR32Uint width:W height:H mipmapped:NO];
  td.usage=MTLTextureUsageShaderRead|MTLTextureUsageShaderWrite; td.storageMode=MTLStorageModeShared; // uncompressed
  id<MTLTexture> tex=[dev newTextureWithDescriptor:td];
  size_t imgBytes=(size_t)W*H*4;
  printf("DEVICE %s TEXSCAN W=%ld H=%ld allocatedSize=0x%lx imgBytes=0x%zx\n",
    [[dev name]UTF8String],W,H,(unsigned long)[tex allocatedSize],imgBytes);
  NSError*err=nil;
  NSString*cs=@"#include <metal_stdlib>\nusing namespace metal;\n"
    "kernel void wr(texture2d<uint,access::write> t[[texture(0)]],uint2 g[[thread_position_in_grid]]){t.write(uint4((g.y<<16)|g.x,0,0,0),g);}\n";
  id<MTLLibrary> cl=[dev newLibraryWithSource:cs options:nil error:&err];
  if(!cl){printf("COMPILE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
  id<MTLComputePipelineState> cpso=[dev newComputePipelineStateWithFunction:[cl newFunctionWithName:@"wr"] error:&err];
  if(!cpso){printf("PIPELINE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
  id<MTLCommandQueue> q=[dev newCommandQueue];
  id<MTLCommandBuffer> cb=[q commandBuffer];
  id<MTLComputeCommandEncoder> enc=[cb computeCommandEncoder];
  [enc setComputePipelineState:cpso];[enc setTexture:tex atIndex:0];
  [enc dispatchThreads:MTLSizeMake(W,H,1) threadsPerThreadgroup:MTLSizeMake(8,8,1)];
  [enc endEncoding];[cb commit];[cb waitUntilCompleted];
  printf("STATUS=%ld\n",(long)[cb status]);
  uint32_t chk=0;[tex getBytes:&chk bytesPerRow:4 fromRegion:MTLRegionMake2D(3,2,1,1) mipmapLevel:0];
  printf("PIXEL(3,2)=0x%08x (expect 0x00020003)\n",chk);

  // Locate the texture backing by anchoring on the UNIQUE corner value U=texel(W-1,H-1)
  // and counting DISTINCT valid texel values in the imgBytes window preceding it (a bitset
  // over W*H possible values). The real texture window has ~W*H distinct values; a repetitive
  // noise region has few. Order-independent. Dump the winning window for offline analysis.
  uint32_t U=((uint32_t)(H-1)<<16)|(uint32_t)(W-1);
  size_t NBIT=(size_t)W*H; uint8_t*bits=malloc((NBIT+7)/8);
  mach_port_t me=mach_task_self();
  mach_vm_address_t addr=0; mach_vm_size_t sz=0; natural_t depth=0;
  size_t bestdist=0; uint8_t*bestbuf=NULL; size_t best_ws=0,best_we=0; mach_vm_address_t best_rbase=0;
  const size_t WIN=(size_t)imgBytes;
  while(1){
    struct vm_region_submap_info_64 info; mach_msg_type_number_t cnt=VM_REGION_SUBMAP_INFO_COUNT_64;
    mach_vm_address_t a=addr; natural_t d=depth;
    kern_return_t kr=mach_vm_region_recurse(me,&a,&sz,&d,(vm_region_recurse_info_t)&info,&cnt);
    if(kr!=KERN_SUCCESS) break;
    if(info.is_submap){ depth=d+1; addr=a; continue; }
    if((info.protection&VM_PROT_READ)&&sz>=imgBytes){   // READ-only regions included too
      size_t rsz=(size_t)sz; if(rsz>1024*1024*1024) rsz=1024*1024*1024;
      uint8_t*buf=malloc(rsz);
      if(buf){
        mach_vm_size_t got=0;
        if(mach_vm_read_overwrite(me,a,rsz,(mach_vm_address_t)buf,&got)==KERN_SUCCESS){
          for(size_t off=0;off+4<=got;off+=4){
            uint32_t v; memcpy(&v,buf+off,4);
            if(v!=U) continue;
            size_t ws = off>=WIN ? off-WIN : 0;
            size_t we = off+64<got ? off+64 : got;
            memset(bits,0,(NBIT+7)/8); size_t dist=0;
            for(size_t o=ws;o+4<=we;o+=4){ uint32_t w; memcpy(&w,buf+o,4); uint32_t x=w&0xffff,y=w>>16;
              if(x<(uint32_t)W&&y<(uint32_t)H){ size_t idx=(size_t)y*W+x; if(!(bits[idx>>3]&(1<<(idx&7)))){bits[idx>>3]|=(1<<(idx&7));dist++;} } }
            if(dist>bestdist){ if(bestbuf&&bestbuf!=buf) free(bestbuf); bestdist=dist; best_rbase=a; best_ws=ws; best_we=we; bestbuf=buf; }
          }
        }
        if(bestbuf!=buf) free(buf);
      }
    }
    addr=a+sz; depth=d;
  }
  if(!bestbuf || bestdist < (size_t)(W*H*0.9)){
    printf("NO_DENSE_TEXTURE (best distinct=%zu of %ld) — uncompressed backing not raw-CPU-scannable on M5\n",bestdist,W*H);
    return 2;
  }
  printf("TEXTURE window: region-base 0x%llx win[0x%zx,0x%zx) distinct_texels=%zu/%ld -> %s\n",
    (unsigned long long)best_rbase,best_ws,best_we,bestdist,W*H,out);
  FILE*f=fopen(out,"w");
  fprintf(f,"# TEXBACKING region_va=0x%llx win_start=0x%zx distinct=%zu W=%ld H=%ld bpp=4\n",
    (unsigned long long)best_rbase,best_ws,bestdist,W,H);
  for(size_t o=best_ws;o<best_we;o+=16){
    fprintf(f,"%08zx: ",o-best_ws);
    for(size_t k=0;k<16 && o+k<best_we;k++) fprintf(f,"%02x",bestbuf[o+k]);
    fprintf(f,"\n");
  }
  fclose(f);
  printf("WROTE %s (0x%zx bytes)\n",out,best_we-best_ws);
  return 0;
}}
