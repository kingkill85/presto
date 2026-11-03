/*===================================================================*/
/*                                                                   */
/*  InfoNES_Mapper.cpp : InfoNES Mapper Function                     */
/*                                                                   */
/*  2000/05/16  InfoNES Project ( based on NesterJ and pNesX )       */
/*                                                                   */
/*===================================================================*/

/*-------------------------------------------------------------------*/
/*  Include files                                                    */
/*-------------------------------------------------------------------*/

#include "InfoNES.h"
#include "InfoNES_System.h"
#include "InfoNES_Mapper.h"
#include "K6502.h"

/*-------------------------------------------------------------------*/
/*  Mapper resources                                                 */
/*-------------------------------------------------------------------*/

/* Disk System RAM */
BYTE *DRAM; // No FDS mapper in this port

/*-------------------------------------------------------------------*/
/*  Table of Mapper initialize function                              */
/*-------------------------------------------------------------------*/

const struct MapperTable_tag MapperTable[] = {
 {0,Map0_Init}, {1,Map1_Init}, {2,Map2_Init}, {3,Map3_Init}, {4,Map4_Init}, {7,Map7_Init}, {-1,NULL}
};
#include "mapper/InfoNES_Mapper_000.c"
#include "mapper/InfoNES_Mapper_001.c"
#include "mapper/InfoNES_Mapper_002.c"
#include "mapper/InfoNES_Mapper_003.c"
#include "mapper/InfoNES_Mapper_004.c"
#include "mapper/InfoNES_Mapper_007.c"
