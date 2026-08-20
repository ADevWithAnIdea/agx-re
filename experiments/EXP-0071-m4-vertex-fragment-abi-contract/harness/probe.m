#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <stdio.h>
#include <string.h>
/* Future public-API harness: accepts --source and --case, creates fresh device,
 * descriptor, two guarded shared 4x4 targets, one command buffer, and prints a
 * closed JSON case record. It deliberately contains no binary/archive/BO path. */
int main(int ac,const char**av){@autoreleasepool{if(ac!=5||strcmp(av[1],"--source")||strcmp(av[3],"--case"))return 2;id<MTLDevice>d=MTLCreateSystemDefaultDevice();if(!d){fputs("DEVICE_FAIL\n",stderr);return 3;}/* Execution intentionally deferred to audited capture implementation. */fprintf(stderr,"HARNESS_PRE_GPU_CONTRACT_ONLY\n");return 4;}}
