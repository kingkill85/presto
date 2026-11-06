// Prints pitch and envelope of one OPL note at the configured OPL_RATE_DIV.
#include <math.h>
#include <stdio.h>
#include "vendor/emu8950.h"
#define RATE 22050
int main(void){
    unsigned r=3579545/72/OPL_RATE_DIV;OPL *o=OPL_new(3579545,r);OPL_setChipType(o,2);OPL_writeReg(o,1,32);
    static const int regs[][2]={{0x20,0x01},{0x40,0x10},{0x60,0xF4},{0x80,0x46},{0x23,0xC1},{0x43,0x00},
        {0x63,0xA3},{0x83,0x36},{0xC0,0x06},{0xBD,0xC0},{0xA0,0x44},{0xB0,0x20|(4<<2)|1}};
    for(unsigned i=0;i<sizeof regs/sizeof regs[0];i++)OPL_writeReg(o,regs[i][0],regs[i][1]);
    unsigned phase=0;int prev=0,crossings=0,n=0;double energy=0;
    for(int i=0;i<RATE;i++){
        int sum=0,count=0;phase+=r;while(phase>=RATE){phase-=RATE;sum+=OPL_calc(o);count++;}
        int s=count?sum/count:0;if(prev<0&&s>=0)crossings++;prev=s;
        energy+=(double)s*s;if(++n==2205){printf("%.1f ",sqrt(energy/n));energy=0;n=0;}
    }
    printf("%d\n",crossings);OPL_delete(o);return 0;
}
